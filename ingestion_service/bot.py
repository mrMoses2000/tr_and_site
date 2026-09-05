import os
import sys
import uuid
import re
import html
import asyncio
import logging
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

from typing import Optional, List

from .config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_ADMIN_ID,
    INBOX_DIR,
    BASE_DIR,
    DB_PATH,
    validate_config,
    Settings,
    ConfigurationError
)
from .jobs.repository import DuplicateSourceError, JobRepository, JobState, sha256_file
from .jobs.worker import IngestionWorker, JobExecutionContext
from .pipeline import IngestionPipeline
from .agy_bridge import AgyCliBridge
from .pdf_extractor import PDFExtractor, slugify_cyrillic
from .lang_detector import detect_language, get_language_options
from .release import StagedPublicationAdapter, assert_paths_outside_checkout
from .release.publication import StagedReleasePublicationPort
from .release.promoter import ReleasePromoter
from .release.staging import StagingManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("telegram_bot")

def is_user_authorized(user_id: Optional[int], allowlist: List[int]) -> bool:
    """Strict deny-by-default check for Telegram user ID."""
    if user_id is None:
        return False
    return int(user_id) in allowlist

def sanitize_inbox_path(job_id: str, original_filename: str, base_inbox_dir: Path) -> Path:
    """
    Prevents path traversal and directory escape attacks across Linux and Windows paths.
    Guarantees destination file resides directly in base_inbox_dir with no traversal components.
    """
    # Normalize path separators (handles both / and \)
    normalized = original_filename.replace("\\", "/")
    raw_name = [part for part in normalized.split("/") if part][-1] if "/" in normalized else original_filename
    stem = Path(raw_name).stem
    # Only allow alphanumeric, underscores and hyphens in stem (no dots, no slashes, no spaces)
    clean_stem = re.sub(r'[^a-zA-Z0-9_-]', '_', stem)
    clean_stem = re.sub(r'_+', '_', clean_stem).strip('_') or "document"
    safe_filename = f"{job_id}_{clean_stem}.pdf"
    resolved_inbox = base_inbox_dir.resolve()
    safe_path = (resolved_inbox / safe_filename).resolve()
    
    if not safe_path.is_relative_to(resolved_inbox) or safe_path.parent != resolved_inbox:
        raise ValueError(f"Security violation: path traversal detected for filename {original_filename}")
    if ".." in safe_path.name:
        raise ValueError(f"Security violation: dot-dot traversal detected in filename {original_filename}")
    return safe_path


def remove_created_upload(save_path: Path, base_inbox_dir: Path) -> bool:
    """Remove only a regular file directly inside the configured inbox.

    The handler passes the exact path it generated.  Refuse symlinks and any
    path outside the inbox so cleanup cannot become an arbitrary file delete.
    """
    try:
        candidate = Path(save_path)
        inbox = Path(base_inbox_dir).resolve()
        if candidate.parent.resolve() != inbox or candidate.is_symlink():
            logger.error("Refusing unsafe upload cleanup path: %s", candidate)
            return False
        if candidate.exists() and candidate.is_file():
            candidate.unlink()
            return True
    except OSError:
        logger.warning("Could not remove temporary upload %s", save_path, exc_info=True)
    return False


def validate_pdf_content(pdf_path: Path) -> int:
    """Validate PDF magic and parser readability, returning its page count."""
    with Path(pdf_path).open("rb") as uploaded_pdf:
        if uploaded_pdf.read(5) != b"%PDF-":
            raise ValueError("file does not have a valid PDF signature")
    extractor = PDFExtractor(pdf_path)
    try:
        if extractor.total_pages <= 0:
            raise ValueError("PDF contains no pages")
        return extractor.total_pages
    finally:
        extractor.close()

def render_progress_bar(processed: int, total: int) -> str:
    if total <= 0:
        return "[▱▱▱▱▱▱▱▱▱▱] 0%"
    pct = min(100, int((processed / total) * 100))
    filled = pct // 10
    empty = 10 - filled
    return f"[{'▰' * filled}{'▱' * empty}] {pct}%"

async def safe_edit_message(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None
):
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception:
            pass
    except TelegramBadRequest as e:
        err_msg = str(e).lower()
        if "message is not modified" not in err_msg:
            # Fallback to plain text if HTML parsing error occurs
            try:
                clean_text = re.sub(r'<[^>]+>', '', text)
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=clean_text,
                    reply_markup=reply_markup,
                    parse_mode=None
                )
            except Exception:
                logger.warning(f"Could not edit message {message_id}: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error editing message {message_id}: {e}")

dp = Dispatcher()
pipeline = IngestionPipeline()
_job_repository: Optional[JobRepository] = None


def build_production_pipeline(settings: Settings) -> IngestionPipeline:
    """Construct the fenced production pipeline from explicit host paths.

    The default paths match the Ubuntu origin runbook.  No publication object
    is created at import time, and missing/unwritable origin configuration
    fails closed during bot startup instead of silently writing ``app/``.
    """
    release_root = Path(os.getenv("LOGOS_RELEASE_ROOT", "/srv/logos"))
    app_dir = Path(os.getenv("LOGOS_APP_DIR", str(BASE_DIR / "app")))
    assert_paths_outside_checkout(
        BASE_DIR,
        {
            "release root": release_root,
            "build workspace": Path(
                os.getenv("LOGOS_BUILD_WORK_ROOT", str(release_root / "build-work"))
            ),
        },
    )
    staging = StagingManager(release_root / "staging")
    promoter = ReleasePromoter(
        release_root / "releases",
        release_root / "current",
        staging,
    )
    adapter = StagedPublicationAdapter(
        staging,
        promoter,
        # Fence against the repository root, not just ``app/``.  A release
        # directory accidentally placed beside app/ must never become a live
        # checkout write.
        active_checkout=BASE_DIR,
    )
    publication = StagedReleasePublicationPort(
        adapter,
        app_dir=app_dir,
        workspace_root=Path(os.getenv("LOGOS_BUILD_WORK_ROOT", str(release_root / "build-work"))),
        public_base_url=os.getenv("LOGOS_PUBLIC_BASE_URL", ""),
        npm_bin=os.getenv("NPM_BIN", "npm"),
    )
    return IngestionPipeline(
        bridge=AgyCliBridge(agy_bin=settings.agy_bin),
        publication_port=publication,
    )


def get_job_repository() -> JobRepository:
    """Return the process-wide durable repository, initializing it lazily."""
    global _job_repository
    if _job_repository is None:
        _job_repository = JobRepository(str(DB_PATH))
        _job_repository.init_schema()
    return _job_repository

@dp.message(Command("start"))
async def handle_start(message: types.Message):
    welcome_text = (
        "👋 <b>Добро пожаловать в бота цифровой академической читалки!</b>\n\n"
        "Этот бот конвертирует и публикует книги (в формате PDF) "
        "в современную интерактивную веб-читалку с поддержкой казахского, русского и оригинального языков.\n\n"
        "✨ <b>Возможности системы:</b>\n"
        "• <b>🇰🇿 Перевод на казахский язык:</b> академический богословский перевод (академиялық қазақша теологиялық аударма).\n"
        "• <b>🇷🇺 Перевод на русский язык:</b> параллельный двуязычный текст и интерактивные сноски.\n"
        "• <b>📖 Публикация в оригинале:</b> для готовых книг на русском, казахском, английском с извлечением структуры.\n"
        "• <b>⚙️ Контроль качества:</b> сборка и проверки выполняются до отдельного staged-релиза.\n\n"
        "📥 <b>Чтобы начать:</b> просто отправьте сюда PDF-файл книги!"
    )
    await message.answer(welcome_text, parse_mode="HTML")

@dp.message(Command("library"))
async def handle_library(message: types.Message):
    text = (
        "📚 <b>Каталог библиотеки читалки:</b>\n\n"
        "1. <b>Размышления о богословии Нового Завета</b>\n"
        "   ✍️ Томас Р. Шрейнер (Baker Academic)\n"
        "   📄 Стр. 867–888 • Двуязычный режим + сноски\n"
        "   🔗 Ссылка появится после публикации staged-релиза.\n\n"
        "2. <b>Герменевтическая спираль</b>\n"
        "   ✍️ Грант Р. Осборн (ЕААА)\n"
        "   📄 736 стр. • Академическое издание со сносками и оглавлением\n"
        "   🔗 Ссылка появится после публикации staged-релиза.\n\n"
        "Чтобы добавить новую книгу, просто пришлите сюда PDF-файл!"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("status"))
async def handle_status(message: types.Message):
    jobs = get_job_repository().list_recent_jobs(limit=5)
    if not jobs:
        await message.answer("ℹ️ Нет активных или недавних задач.")
        return

    lines = ["📊 <b>Последние задачи обработки:</b>"]
    for j in jobs:
        bar = render_progress_bar(j.processed_pages, j.total_pages)
        safe_name = html.escape(j.file_name)
        target = getattr(j, "target_lang", "kk")
        lang_badge = {"kk": "🇰🇿 Казахский", "ru": "🇷🇺 Русский", "original": "📖 Оригинал", "en": "🇬🇧 Английский"}.get(target, target)
        lines.append(
            f"• <b>{safe_name}</b> (<code>{j.id}</code>) — {lang_badge}\n"
            f"  Статус: {j.status.value} {bar}\n"
            f"  Этап: <i>{html.escape(j.status_text)}</i>"
        )
        if j.live_url:
            safe_url = html.escape(j.live_url, quote=True)
            lines.append(f"  🔗 <a href='{safe_url}'>Читать онлайн</a>")

    await message.answer("\n\n".join(lines), parse_mode="HTML")

def make_worker_processor(bot: Bot):
    """Adapt the existing pipeline to the durable worker callback contract."""
    async def process_job(job, context: JobExecutionContext) -> Optional[str]:
        safe_name = html.escape(job.file_name)
        progress_total = job.total_pages
        lang_title = {
            "kk": "🇰🇿 Казахский академический (Қазақша)",
            "ru": "🇷🇺 Русский академический",
            "original": "📖 Публикация в оригинале (без перевода)",
            "en": "🇬🇧 Английский академический (English)"
        }.get(job.target_lang, job.target_lang)

        async def on_progress(text: str, processed: int, total: int):
            nonlocal progress_total
            context.assert_active()
            if total > 0:
                progress_total = total
            bar = render_progress_bar(processed, total)
            msg_text = (
                f"📖 <b>Обработка книги:</b> «{safe_name}»\n"
                f"🆔 <b>Задача:</b> <code>{job.id}</code>\n"
                f"🌐 <b>Режим:</b> {lang_title}\n\n"
                f"📊 <b>Прогресс:</b> {bar}\n"
                f"⏳ <b>Текущий этап:</b> {html.escape(text)}"
            )
            await safe_edit_message(bot, job.telegram_chat_id, job.telegram_message_id, msg_text)

        try:
            live_url = await pipeline.run(
                job_id=job.id,
                on_progress=on_progress,
                execution_context=context,
            )
            finish_text = (
                f"🎉 <b>Книга успешно обработана!</b>\n\n"
                f"📖 <b>Файл:</b> «{safe_name}»\n"
                f"🌐 <b>Режим:</b> {lang_title}\n"
                f"🆔 <b>Задача:</b> <code>{job.id}</code>\n"
                f"✅ <b>Статус:</b> Результат прошёл настроенные проверки.\n\n"
                f"🔗 <a href='{html.escape(live_url, quote=True)}'>Открыть результат</a>"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📖 Открыть результат", url=live_url)
            ]])
            context.assert_active()
            await safe_edit_message(
                bot,
                job.telegram_chat_id,
                job.telegram_message_id,
                finish_text,
                reply_markup=keyboard,
            )
            return live_url
        except Exception as exc:
            logger.error("Error in durable job %s: %s", job.id, exc, exc_info=True)
            safe_err = html.escape(str(exc)[:400])
            context.assert_active()
            await safe_edit_message(
                bot,
                job.telegram_chat_id,
                job.telegram_message_id,
                f"❌ <b>Ошибка обработки книги:</b> «{safe_name}»\n\n"
                f"Детали ошибки: <code>{safe_err}</code>",
            )
            raise

    return process_job

@dp.callback_query(F.data.startswith("mode:"))
async def handle_mode_selection(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    _, target_lang, job_id = parts

    try:
        settings = validate_config()
    except ConfigurationError:
        await callback.message.answer("⚠️ Сервис временно недоступен для изменения задачи.")
        return
    if not is_user_authorized(callback.from_user.id if callback.from_user else None, settings.admin_user_ids):
        await callback.message.answer("⛔ У вас нет прав на изменение этой задачи.")
        return

    repository = get_job_repository()
    job = repository.get_job(job_id)
    if not job:
        await callback.message.answer("❌ Задача не найдена.")
        return

    try:
        job = repository.update_queued_job(
            job_id,
            target_lang=target_lang,
            status_text="Задача поставлена в устойчивую очередь...",
        )
    except Exception:
        await callback.message.answer("⚠️ Задача уже выполняется или недоступна для изменения.")
        return
    safe_name = html.escape(job.file_name)
    lang_title = {
        "kk": "🇰🇿 Казахский академический (Қазақша)",
        "ru": "🇷🇺 Русский академический",
        "original": "📖 В оригинале (без перевода)",
        "en": "🇬🇧 Английский академический (English)"
    }.get(target_lang, target_lang)

    await safe_edit_message(
        bot,
        callback.message.chat.id,
        callback.message.message_id,
        f"⏳ <b>Запуск конвейера...</b>\n\n"
        f"📖 <b>Книга:</b> «{safe_name}»\n"
        f"🌐 <b>Выбран режим:</b> {lang_title}\n\n"
        f"Извлечение текста, сносок и WebP-сканов страниц..."
    )

    await callback.message.answer("✅ Задача сохранена в устойчивой очереди. Worker начнёт обработку автоматически.")

@dp.message(F.document)
async def handle_document(message: types.Message, bot: Bot):
    doc = message.document
    # Strict deny-by-default allowlist check BEFORE any download or DB action
    try:
        settings = validate_config()
    except ConfigurationError:
        logger.error("Rejecting upload because secure configuration is invalid")
        await message.reply("⚠️ Сервис временно недоступен. Администратор должен проверить конфигурацию.")
        return
    admin_ids = settings.admin_user_ids

    sender_id = message.from_user.id if message.from_user else None
    if not is_user_authorized(sender_id, admin_ids):
        logger.warning(f"Unauthorized upload attempt from user ID {sender_id}")
        await message.reply("⛔ Извините, у вас нет прав на добавление книг на этот сервер.")
        return

    file_name = doc.file_name or "book.pdf"
    if not file_name.lower().endswith(".pdf") or (
        doc.mime_type is not None and doc.mime_type != "application/pdf"
    ):
        await message.reply(
            "⚠️ Пожалуйста, отправьте файл книги в формате <b>PDF</b>.",
            parse_mode="HTML"
        )
        return

    job_id = uuid.uuid4().hex[:8]
    try:
        save_path = sanitize_inbox_path(job_id, file_name, INBOX_DIR)
    except ValueError as e:
        logger.error(f"Filename security error: {e}")
        await message.reply("⚠️ Недопустимое имя файла.", parse_mode="HTML")
        return

    safe_name = html.escape(file_name)

    init_msg = await message.reply(
        f"📥 <b>Файл получен!</b>\n\n"
        f"📖 <b>Файл:</b> «{safe_name}»\n"
        f"🆔 <b>Задача:</b> <code>{job_id}</code>\n"
        f"⏳ Скачивание и анализ структуры документа...",
        parse_mode="HTML"
    )

    # A random job id makes collisions unlikely, but never overwrite or later
    # clean up a pre-existing path.
    if save_path.exists() or save_path.is_symlink():
        await init_msg.edit_text("❌ Не удалось безопасно подготовить файл загрузки.", parse_mode="HTML")
        return

    if doc.file_size is not None and doc.file_size > settings.max_upload_bytes:
        await message.reply("⚠️ Файл превышает допустимый размер.")
        return

    try:
        await bot.download(doc, destination=save_path)
    except Exception as e:
        logger.error(f"Failed to download file from Telegram: {e}")
        remove_created_upload(save_path, INBOX_DIR)
        safe_err = html.escape(str(e))
        await init_msg.edit_text(f"❌ Не удалось скачать файл: {safe_err}", parse_mode="HTML")
        return

    try:
        downloaded_size = save_path.stat().st_size
    except OSError:
        await init_msg.edit_text("❌ Telegram не вернул содержимое файла.", parse_mode="HTML")
        return

    if downloaded_size > settings.max_upload_bytes:
        remove_created_upload(save_path, INBOX_DIR)
        await message.reply("⚠️ Файл превышает допустимый размер.")
        return

    # Validate both the PDF signature and that PyMuPDF can open the document.
    # Do not fall back to metadata for malformed or non-PDF uploads.
    try:
        validate_pdf_content(save_path)
        extractor = PDFExtractor(save_path)
    except Exception:
        remove_created_upload(save_path, INBOX_DIR)
        await init_msg.edit_text(
            "❌ Файл не является корректным PDF или повреждён.", parse_mode="HTML"
        )
        return

    source_sha256 = sha256_file(str(save_path))
    repository = get_job_repository()
    existing = repository.find_by_source_hash(source_sha256)
    if existing:
        extractor.close()
        remove_created_upload(save_path, INBOX_DIR)
        await message.reply(
            f"ℹ️ Этот PDF уже зарегистрирован в задаче <code>{html.escape(existing.id)}</code>.",
            parse_mode="HTML",
        )
        return

    # Extract real metadata and detect document language
    try:
        meta = extractor.get_metadata()
        total_pages = extractor.total_pages
        detected_lang = meta.get("sourceLanguage", "unknown")
        real_title = meta.get("title") or Path(file_name).stem
        real_author = meta.get("authorRu") or meta.get("author") or "Неизвестный автор"
        publisher = meta.get("publisher", "")
    except Exception as e:
        logger.warning(f"Error inspecting PDF metadata: {e}")
        remove_created_upload(save_path, INBOX_DIR)
        await init_msg.edit_text(
            "❌ Не удалось прочитать структуру корректного PDF-файла.", parse_mode="HTML"
        )
        return
    finally:
        # The extractor owns a native document handle; it is safe to close it
        # more than once and this also covers later enqueue errors.
        extractor.close()

    slug = slugify_cyrillic(real_title)

    # Register in DB
    try:
        repository.enqueue_job(
            job_id=job_id,
            source_sha256=source_sha256,
            telegram_user_id=message.from_user.id if message.from_user else 0,
            telegram_chat_id=message.chat.id,
            telegram_message_id=init_msg.message_id,
            file_name=file_name,
            file_path=str(save_path),
            book_slug=slug,
            target_lang="original" if detected_lang == "ru" else "kk",
            source_lang=detected_lang,
            total_pages=total_pages,
            initial_status=JobState.AWAITING_MODE,
        )
    except DuplicateSourceError as duplicate:
        remove_created_upload(save_path, INBOX_DIR)
        await init_msg.edit_text(
            f"ℹ️ Этот PDF уже зарегистрирован в задаче <code>{html.escape(duplicate.existing_job.id)}</code>.",
            parse_mode="HTML",
        )
        return
    except Exception:
        remove_created_upload(save_path, INBOX_DIR)
        logger.exception("Could not enqueue validated PDF job %s", job_id)
        await init_msg.edit_text(
            "❌ Не удалось поставить книгу в очередь обработки.", parse_mode="HTML"
        )
        return

    # Generate tailored language choices
    options = get_language_options(detected_lang)
    keyboard_buttons = [
        [InlineKeyboardButton(text=opt["label"], callback_data=f"mode:{opt['code']}:{job_id}")]
        for opt in options
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    lang_names = {
        "ru": "🇷🇺 Русский",
        "kk": "🇰🇿 Казахский (Қазақша)",
        "en": "🇬🇧 Английский (English)",
        "unknown": "❓ Не определен"
    }
    lang_display = lang_names.get(detected_lang, detected_lang)

    mode_text = (
        f"📥 <b>Книга успешно проанализирована!</b>\n\n"
        f"📖 <b>Название:</b> «{html.escape(real_title)}»\n"
        f"✍️ <b>Автор:</b> {html.escape(real_author)}\n"
    )
    if publisher:
        mode_text += f"🏢 <b>Издательство:</b> {html.escape(publisher)}\n"
    mode_text += (
        f"📄 <b>Объем:</b> {total_pages} стр.\n"
        f"🌐 <b>Язык оригинала:</b> {lang_display}\n\n"
        f"<b>Выберите необходимый режим обработки:</b>"
    )

    await safe_edit_message(bot, message.chat.id, init_msg.message_id, mode_text, reply_markup=keyboard)

async def main():
    settings = validate_config()
    global pipeline
    pipeline = build_production_pipeline(settings)
    repository = get_job_repository()
    repository.init_schema()
    bot = Bot(token=settings.telegram_bot_token)
    logger.info("Starting Telegram Bot with Long Polling (outbound HTTPS satisfying Telegram requirements)...")
    await bot.delete_webhook(drop_pending_updates=False)
    
    worker = IngestionWorker(
        worker_id=f"telegram-worker-{os.getpid()}",
        repository=repository,
        lease_seconds=settings.worker_lease_seconds,
        processor=make_worker_processor(bot),
    )
    polling_task = asyncio.create_task(dp.start_polling(bot))
    worker_task = asyncio.create_task(worker.run_async(settings.worker_poll_interval))
    try:
        done, _ = await asyncio.wait(
            {polling_task, worker_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        # A normally-returning polling task must not leave the durable worker
        # running forever.  Conversely, a stopped worker must release polling.
        for task in (polling_task, worker_task):
            if task not in done:
                task.cancel()
        await asyncio.gather(polling_task, worker_task, return_exceptions=True)
        for task in done:
            error = task.exception()
            if error is not None:
                raise error
    finally:
        worker.stop()
        for task in (polling_task, worker_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(polling_task, worker_task, return_exceptions=True)
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
