import os
import sys
import uuid
import re
import asyncio
import logging
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

from .config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_ADMIN_ID,
    INBOX_DIR,
    BASE_DIR
)
from .db import init_db, create_job, get_job, get_recent_jobs, update_job
from .pipeline import IngestionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("telegram_bot")

def generate_slug(filename: str) -> str:
    base = Path(filename).stem
    # Transliterate or clean to ascii-safe slug
    slug = re.sub(r'[^a-zA-Z0-9_-]', '-', base).strip('-').lower()
    slug = re.sub(r'-+', '-', slug)
    if not slug:
        slug = f"book-{uuid.uuid4().hex[:6]}"
    return slug

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
            parse_mode="Markdown"
        )
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.warning(f"Could not edit message {message_id}: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error editing message {message_id}: {e}")

dp = Dispatcher()
pipeline = IngestionPipeline()

@dp.message(Command("start"))
async def handle_start(message: types.Message):
    welcome_text = (
        "👋 *Добро пожаловать в бота цифровой богословской читалки!*\n\n"
        "Этот бот автоматически конвертирует и публикует академические книги (в формате PDF) "
        "в интерактивную двуязычную веб-читалку.\n\n"
        "✨ *Как это работает:*\n"
        "1. Отправьте боту файл книги в формате `.pdf`.\n"
        "2. Бот выполнит извлечение текста, заголовков и WebP-сканов страниц (PyMuPDF).\n"
        "3. Интеллектуальный агент `agy cli` произведет академический богословский перевод на русский язык, "
        "выровняет параллельные абзацы и свяжет сноски.\n"
        "4. Результат автоматически собирается, проходит проверку тестов Vitest и деплоится на Netlify в production.\n"
        "5. Вы получите прямую ссылку для чтения на смартфонах и компьютерах.\n\n"
        "📚 *Команды:*\n"
        "/library — Каталог опубликованных книг\n"
        "/status — Состояние текущих задач"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🌐 Открыть читалку",
                url="https://harmonious-hotteok-0204c0.netlify.app"
            )
        ]]
    )
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("library"))
async def handle_library(message: types.Message):
    # Could also read from libraryRegistry or jobs
    text = (
        "📚 *Каталог библиотеки читалки:*\n\n"
        "1. *Размышления о богословии Нового Завета*\n"
        "   ✍️ Томас Р. Шрейнер (Baker Academic)\n"
        "   📄 Стр. 867–888 • 22 стр. • Двуязычный режим + сноски\n"
        "   🔗 [Открыть книгу](https://harmonious-hotteok-0204c0.netlify.app/#book=schreiner-ntt&page=867)\n\n"
        "Чтобы добавить новую книгу, просто отправьте сюда PDF-файл!"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("status"))
async def handle_status(message: types.Message):
    jobs = get_recent_jobs(limit=5)
    if not jobs:
        await message.answer("ℹ️ Нет активных или недавних задач.")
        return

    lines = ["📊 *Последние задачи обработки:*"]
    for j in jobs:
        bar = render_progress_bar(j.processed_pages, j.total_pages)
        lines.append(
            f"• *{j.file_name}* (`{j.id}`)\n"
            f"  Статус: {j.status} {bar}\n"
            f"  Этап: _{j.status_text}_"
        )
        if j.live_url:
            lines.append(f"  🔗 [Читать онлайн]({j.live_url})")

    await message.answer("\n\n".join(lines), parse_mode="Markdown")

async def process_pdf_task(
    job_id: str,
    bot: Bot,
    chat_id: int,
    message_id: int,
    file_name: str
):
    async def on_progress(text: str, processed: int, total: int):
        bar = render_progress_bar(processed, total)
        msg_text = (
            f"📖 *Обработка книги:* «{file_name}»\n"
            f"🆔 *Задача:* `{job_id}`\n\n"
            f"📊 *Прогресс:* {bar}\n"
            f"⏳ *Текущий этап:* {text}"
        )
        await safe_edit_message(bot, chat_id, message_id, msg_text)

    try:
        live_url = await pipeline.run(job_id=job_id, on_progress=on_progress)
        
        finish_text = (
            f"🎉 *Книга успешно опубликована!*\n\n"
            f"📖 *Файл:* {file_name}\n"
            f"🆔 *Задача:* `{job_id}`\n"
            f"✅ *Статус:* Все этапы завершены, тесты Vitest пройдены, сайт обновлен на Netlify!\n\n"
            f"🔗 [Нажмите сюда, чтобы открыть книгу в читалке]({live_url})"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="📖 Открыть книгу онлайн", url=live_url)
            ]]
        )
        await safe_edit_message(bot, chat_id, message_id, finish_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error in task {job_id}: {e}", exc_info=True)
        fail_text = (
            f"❌ *Ошибка при обработке книги:*\n«{file_name}»\n\n"
            f"Детали ошибки: `{str(e)[:400]}`\n\n"
            f"Вы можете попробовать отправить файл повторно."
        )
        await safe_edit_message(bot, chat_id, message_id, fail_text)

@dp.message(F.document)
async def handle_document(message: types.Message, bot: Bot):
    doc = message.document
    if not doc:
        return

    # Check admin restrictions if configured
    if TELEGRAM_ADMIN_ID and message.from_user and message.from_user.id != int(TELEGRAM_ADMIN_ID):
        await message.reply("⛔ Извините, у вас нет прав на добавление книг на этот сервер.")
        return

    file_name = doc.file_name or "book.pdf"
    if not file_name.lower().endswith(".pdf") and doc.mime_type != "application/pdf":
        await message.reply(
            "⚠️ Пожалуйста, отправьте файл книги в формате *PDF*. "
            "Другие форматы в данный момент не поддерживаются.",
            parse_mode="Markdown"
        )
        return

    job_id = uuid.uuid4().hex[:8]
    slug = generate_slug(file_name)
    save_path = INBOX_DIR / f"{job_id}_{file_name}"

    # Initial confirmation message
    progress_msg = await message.reply(
        f"📥 *Файл принят в обработку!*\n\n"
        f"📖 *Файл:* {file_name}\n"
        f"🆔 *Задача:* `{job_id}`\n\n"
        f"⏳ *Статус:* Скачивание документа с серверов Telegram...",
        parse_mode="Markdown"
    )

    try:
        # Download file
        await bot.download(doc, destination=save_path)
    except Exception as e:
        logger.error(f"Failed to download file from Telegram: {e}")
        await progress_msg.edit_text(f"❌ Не удалось скачать файл: {e}")
        return

    # Register in DB
    create_job(
        job_id=job_id,
        telegram_user_id=message.from_user.id if message.from_user else 0,
        telegram_chat_id=message.chat.id,
        telegram_message_id=progress_msg.message_id,
        file_name=file_name,
        file_path=str(save_path),
        book_slug=slug
    )

    # Launch processing task asynchronously
    asyncio.create_task(
        process_pdf_task(
            job_id=job_id,
            bot=bot,
            chat_id=message.chat.id,
            message_id=progress_msg.message_id,
            file_name=file_name
        )
    )

async def main():
    init_db()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    logger.info("Starting Telegram Bot with Long Polling (outbound HTTPS satisfying Telegram requirements)...")
    
    # Delete any pending webhook to ensure long polling receives updates cleanly
    await bot.delete_webhook(drop_pending_updates=False)
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
