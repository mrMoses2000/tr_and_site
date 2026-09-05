import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable, List, Dict, Any

from .config import STORAGE_DIR, PROCESSED_DIR, BATCH_SIZE
from .db import update_job, get_job
from .pdf_extractor import PDFExtractor
from .agy_bridge import AgyCliBridge
from .publisher import BookPublisher

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, int], Awaitable[None]]

class IngestionPipeline:
    """
    Hexagonal Orchestration Pipeline for automated book ingestion.
    Coordinates PDF extraction, agy CLI theological translation,
    manifest compilation, Vitest quality checks, and Netlify deployment.
    """

    def __init__(
        self,
        bridge: Optional[AgyCliBridge] = None,
        publisher: Optional[BookPublisher] = None,
        batch_size: int = BATCH_SIZE
    ):
        self.bridge = bridge or AgyCliBridge()
        self.publisher = publisher or BookPublisher()
        self.batch_size = batch_size

    async def run(
        self,
        job_id: str,
        on_progress: Optional[ProgressCallback] = None
    ) -> str:
        job = get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in database")

        async def notify(status: str, text: str, processed: int, total: int):
            update_job(
                job_id,
                status=status,
                status_text=text,
                total_pages=total,
                processed_pages=processed
            )
            if on_progress:
                try:
                    await on_progress(text, processed, total)
                except Exception as e:
                    logger.warning(f"Error calling on_progress callback: {e}")

        pdf_path = Path(job.file_path)
        slug = job.book_slug
        book_processed_dir = PROCESSED_DIR / slug
        scans_dir = book_processed_dir / "scans"
        scans_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: Extraction & Scan rendering
            await notify("EXTRACTING", "📄 Извлечение текста и генерация WebP-сканов страниц...", 0, 0)
            
            extractor = PDFExtractor(pdf_path)
            metadata = extractor.get_metadata()
            total_pages = extractor.total_pages
            
            extracted_pages = []
            for idx in range(total_pages):
                page_num = idx + 1
                text = extractor.extract_page_text(idx)
                img_path = extractor.render_page_as_webp(idx, scans_dir, slug)
                extracted_pages.append({
                    "pageNumber": page_num,
                    "text": text,
                    "imagePath": str(img_path)
                })
                if page_num % 5 == 0 or page_num == total_pages:
                    await notify(
                        "EXTRACTING",
                        f"📄 Извлечено {page_num} из {total_pages} страниц...",
                        page_num,
                        total_pages
                    )
            
            extractor.close()

            # Step 2: Translation & Paragraph Alignment via agy CLI
            target_lang = getattr(job, "target_lang", "kk") or "kk"
            lang_label = {
                "kk": "на казахский язык (Қазақша)",
                "ru": "на русский язык",
                "original": "в оригинале (без перевода)"
            }.get(target_lang, target_lang)

            if target_lang == "original":
                await notify(
                    "TRANSLATING",
                    f"📑 Структурирование страниц и сносок в оригинале (0/{total_pages})...",
                    0,
                    total_pages
                )
            else:
                await notify(
                    "TRANSLATING",
                    f"🧠 Богословский перевод {lang_label} через agy CLI (0/{total_pages})...",
                    0,
                    total_pages
                )

            all_translated_pages: List[Dict[str, Any]] = []
            batch_chunks = [
                extracted_pages[i : i + self.batch_size]
                for i in range(0, len(extracted_pages), self.batch_size)
            ]

            processed_count = 0
            for batch in batch_chunks:
                translated_batch = await self.bridge.translate_batch(
                    pages_data=batch,
                    book_title=metadata.get("title", slug),
                    author=metadata.get("author", "Unknown"),
                    target_lang=target_lang
                )
                for item in translated_batch:
                    all_translated_pages.append(item.model_dump())

                processed_count += len(batch)
                stage_label = "Обработано" if target_lang == "original" else "Переведено"
                await notify(
                    "TRANSLATING",
                    f"🧠 {stage_label} {processed_count} из {total_pages} страниц ({lang_label})...",
                    processed_count,
                    total_pages
                )

            metadata["targetLanguage"] = target_lang

            # Step 3: Compiling manifest & running Vitest Quality Gate
            await notify(
                "COMPILING",
                "📦 Сборка манифеста библиотеки и запуск тестов качества Vitest...",
                total_pages,
                total_pages
            )
            await self.publisher.compile_manifest(
                slug=slug,
                metadata=metadata,
                pages=all_translated_pages,
                scans_source_dir=scans_dir
            )

            await notify(
                "TESTING",
                "🧪 Запуск Vitest: проверка регрессий и целостности...",
                total_pages,
                total_pages
            )
            await self.publisher.run_quality_gate()

            # Step 4: Production Deployment to Netlify
            await notify(
                "DEPLOYING",
                "🚀 Деплой на Netlify Production...",
                total_pages,
                total_pages
            )
            live_url = await self.publisher.deploy_to_netlify(slug)

            # Step 5: Completed
            await notify(
                "DEPLOYED",
                f"✅ Книга успешно опубликована и доступна онлайн!\n{live_url}",
                total_pages,
                total_pages
            )
            update_job(job_id, status="DEPLOYED", live_url=live_url)
            return live_url

        except Exception as err:
            err_text = str(err)
            logger.error(f"Pipeline error for job {job_id}: {err}", exc_info=True)
            update_job(job_id, status="FAILED", error_message=err_text)
            if on_progress:
                try:
                    await on_progress(f"❌ Ошибка обработки книги: {err_text}", 0, 0)
                except Exception:
                    pass
            raise err
