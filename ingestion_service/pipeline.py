import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable, List, Dict, Any, TYPE_CHECKING, Protocol

from .config import STORAGE_DIR, PROCESSED_DIR, BATCH_SIZE
from .db import update_job, get_job
from .pdf_extractor import PDFExtractor
from .agy_bridge import AgyCliBridge
from .publisher import BookPublisher
from .jobs.repository import StaleLeaseError

if TYPE_CHECKING:
    from .jobs.worker import JobExecutionContext

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, int], Awaitable[None]]


class PublicationPort(Protocol):
    async def publish(self, slug: str) -> str:
        """Publish a validated staged release and return its public URL."""


class JobPublicationPort(Protocol):
    async def publish_job(
        self,
        *,
        job_id: str,
        slug: str,
        metadata: Dict[str, Any],
        pages: List[Dict[str, Any]],
        scans_source_dir: Path,
        execution_context: "JobExecutionContext",
        on_phase: Callable[[str, str], Awaitable[None]],
    ) -> str:
        """Build and publish one exact job release under a live lease."""


class PublicationUnavailableError(RuntimeError):
    """Raised until the P6/P11 atomic release adapter is configured."""

class IngestionPipeline:
    """
    Hexagonal Orchestration Pipeline for automated book ingestion.
    Coordinates PDF extraction and translation. Release publication is an
    explicit dependency and remains fail-closed until the staged release
    adapter is supplied by the release workstream.
    """

    def __init__(
        self,
        bridge: Optional[AgyCliBridge] = None,
        publisher: Optional[BookPublisher] = None,
        publication_port: Optional[PublicationPort] = None,
        batch_size: int = BATCH_SIZE
    ):
        self.bridge = bridge or AgyCliBridge()
        self.publisher = publisher
        self.publication_port = publication_port
        self.batch_size = batch_size

    async def run(
        self,
        job_id: str,
        on_progress: Optional[ProgressCallback] = None,
        execution_context: Optional["JobExecutionContext"] = None,
    ) -> str:
        job = get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in database")
        staged_port = self.publication_port if callable(getattr(self.publication_port, "publish_job", None)) else None
        if staged_port is not None and execution_context is None:
            raise TypeError("staged publication requires JobExecutionContext")
        if staged_port is None and (self.publisher is None or self.publication_port is None):
            raise PublicationUnavailableError(
                "No staged release publisher configured; publication is disabled until P6/P11."
            )

        async def notify(status: str, text: str, processed: int, total: int):
            if execution_context:
                execution_context.assert_active()
                execution_context.checkpoint(
                    step=status,
                    data={"status": text[:500], "processed_pages": processed, "total_pages": total},
                    processed_pages=processed,
                )
                execution_context.renew_lease()
            else:
                update_job(
                    job_id,
                    status=status,
                    status_text=text,
                    total_pages=total,
                    processed_pages=processed
                )
            if on_progress:
                try:
                    if execution_context:
                        execution_context.assert_active()
                    await on_progress(text, processed, total)
                except StaleLeaseError:
                    raise
                except Exception as e:
                    logger.warning(f"Error calling on_progress callback: {e}")

        pdf_path = Path(job.file_path)
        slug = job.book_slug
        book_processed_dir = PROCESSED_DIR / slug
        scans_dir = book_processed_dir / "scans"
        if execution_context:
            execution_context.assert_active()
        scans_dir.mkdir(parents=True, exist_ok=True)

        extractor: Optional[PDFExtractor] = None
        try:
            # Step 1: Extraction & Scan rendering
            await notify("EXTRACTING", "📄 Извлечение текста и генерация WebP-сканов страниц...", 0, 0)
            
            extractor = PDFExtractor(pdf_path)
            metadata = extractor.get_metadata()
            total_pages = extractor.total_pages
            
            target_lang = getattr(job, "target_lang", "kk") or "kk"
            lang_label = {
                "kk": "на казахский язык (Қазақша)",
                "ru": "на русский язык",
                "original": "в оригинале (без перевода)"
            }.get(target_lang, target_lang)

            all_pages: List[Dict[str, Any]] = []

            if target_lang == "original":
                # High-precision direct extraction without AI overhead
                for idx in range(total_pages):
                    if execution_context:
                        execution_context.assert_active()
                    page_num = idx + 1
                    img_path = extractor.render_page_as_webp(idx, scans_dir, slug)
                    structured_page = extractor.extract_page_structure(idx)
                    structured_page["imagePath"] = str(img_path)
                    all_pages.append(structured_page)

                    if page_num % 10 == 0 or page_num == total_pages:
                        await notify(
                            "EXTRACTING",
                            f"📑 Структурирование страниц и сносок ({page_num}/{total_pages})...",
                            page_num,
                            total_pages
                        )
            else:
                # Step 1.1: Extract raw text & render scans
                extracted_pages = []
                for idx in range(total_pages):
                    if execution_context:
                        execution_context.assert_active()
                    page_num = idx + 1
                    text = extractor.extract_page_text(idx)
                    img_path = extractor.render_page_as_webp(idx, scans_dir, slug)
                    extracted_pages.append({
                        "pageNumber": page_num,
                        "text": text,
                        "imagePath": str(img_path)
                    })
                    if page_num % 10 == 0 or page_num == total_pages:
                        await notify(
                            "EXTRACTING",
                            f"📄 Извлечено {page_num} из {total_pages} страниц...",
                            page_num,
                            total_pages
                        )

                # Step 1.2: Translation via agy CLI
                await notify(
                    "TRANSLATING",
                    f"🧠 Богословский перевод {lang_label} через agy CLI (0/{total_pages})...",
                    0,
                    total_pages
                )

                batch_chunks = [
                    extracted_pages[i : i + self.batch_size]
                    for i in range(0, len(extracted_pages), self.batch_size)
                ]

                processed_count = 0
                for batch in batch_chunks:
                    if execution_context:
                        execution_context.assert_active()
                    translated_batch = await self.bridge.translate_batch(
                        pages_data=batch,
                        book_title=metadata.get("title", slug),
                        author=metadata.get("author", "Unknown"),
                        target_lang=target_lang,
                        source_lang=metadata.get("sourceLanguage"),
                    )
                    for item in translated_batch:
                        all_pages.append(item.model_dump())

                    processed_count += len(batch)
                    await notify(
                        "TRANSLATING",
                        f"🧠 Переведено {processed_count} из {total_pages} страниц ({lang_label})...",
                        processed_count,
                        total_pages
                    )

            metadata["targetLanguage"] = target_lang

            # Step 3: Compile and validate in a per-job staged release.  The
            # job-aware port owns the production builder and never calls the
            # legacy checkout-writing BookPublisher.
            if execution_context:
                execution_context.assert_active()
            await notify(
                "COMPILING",
                "📦 Сборка манифеста библиотеки и запуск тестов качества Vitest...",
                total_pages,
                total_pages
            )
            if staged_port is not None:
                # ProductionReleaseBuilder runs the quality gate in its
                # isolated workspace before the stage can be promoted.
                live_url = await staged_port.publish_job(
                    job_id=job_id,
                    slug=slug,
                    metadata=metadata,
                    pages=all_pages,
                    scans_source_dir=scans_dir,
                    execution_context=execution_context,
                    on_phase=lambda status, text: notify(
                        status, text, total_pages, total_pages
                    ),
                )
            else:
                await self.publisher.compile_manifest(
                    slug=slug,
                    metadata=metadata,
                    pages=all_pages,
                    scans_source_dir=scans_dir
                )

                if execution_context:
                    execution_context.assert_active()
                await notify(
                    "TESTING",
                    "🧪 Запуск Vitest: проверка регрессий и целостности...",
                    total_pages,
                    total_pages
                )
                await self.publisher.run_quality_gate()

                await notify(
                    "PUBLISHING",
                    "🚀 Публикация подготовленного staged-релиза...",
                    total_pages,
                    total_pages
                )
                if execution_context:
                    execution_context.assert_active()
                live_url = await self.publication_port.publish(slug)

            # Step 5: Completed
            await notify(
                "DEPLOYED",
                f"✅ Книга успешно опубликована и доступна онлайн!\n{live_url}",
                total_pages,
                total_pages
            )
            if execution_context:
                execution_context.assert_active()
                execution_context.checkpoint(
                    "pipeline_complete",
                    {"live_url": live_url, "total_pages": total_pages},
                    processed_pages=total_pages,
                )
            else:
                update_job(job_id, status="DEPLOYED", live_url=live_url)
            return live_url

        except Exception as e:
            logger.error(f"Pipeline failed for job {job_id}: {e}", exc_info=True)
            if execution_context:
                # The worker owns the fenced FAILED transition.  Never let a
                # stale pipeline mutate the legacy DB directly.
                logger.error("Fenced pipeline failure; worker will record state")
            else:
                update_job(job_id, status="FAILED", status_text=str(e))
            raise
        finally:
            if extractor is not None:
                extractor.close()
