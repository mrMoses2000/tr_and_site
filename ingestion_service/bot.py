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
            # Fallback to plain text if entity error occurs
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

@dp.message(Command("start"))
async def handle_start(message: types.Message):
    welcome_text = (
        "👋 <b>Добро пожаловать в бота цифровой академической читалки!</b>\n\n"
        "Этот бот конвертирует и публикует книги (в формате PDF) "
        "в современную интерактивную веб-читалку с поддержкой казахского, русского и оригинального языков.\n\n"
        "✨ <b>Возможности системы:</b>\n"
        "• <b>🇰🇿 Перевод на казахский язык:</b> академический богословский перевод (академиялық қазақша теологиялық аударма).\n"
        "• <b>🇷🇺 Перевод на русский язык:</b> параллельный двуязычный текст и сноски.\n"
        "• <b>📖 Публикация в оригинале:</b> для готовых книг на русском, казахском, английском без перевода.\n"
        "• <b>⚡ Автодеплой:</b> сборка, прогон тестов Vitest и моментальная публикация на Netlify.\n\n"
        "📥 <b>Чтобы начать:</b> просто отправьте сюда PDF-файл книги!"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🌐 Открыть главную страницу",
                url="https://harmonious-hotteok-0204c0.netlify.app"
            )
        ]]
    )
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

@dp.message(Command("library"))
async def handle_library(message: types.Message):
    text = (
        "📚 <b>Каталог библиотеки читалки:</b>\n\n"
        "1. <b>Размышления о богословии Нового Завета</b>\n"
        "   ✍️ Томас Р. Шрейнер (Baker Academic)\n"
        "   📄 Стр. 867–888 • 22 стр. • Двуязычный режим + сноски\n"
        "   🔗 <a href='https://harmonious-hotteok-0204c0.netlify.app/#book=schreiner-ntt&amp;page=867'>Открыть книгу</a>\n\n"
        "Чтобы добавить новую книгу, просто пришлите сюда PDF-файл!"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("status"))
async def handle_status(message: types.Message):
    jobs = get_recent_jobs(limit=5)
    if not jobs:
        await message.answer("ℹ️ Нет активных или недавних задач.")
        return

    lines = ["📊 <b>Последние задачи обработки:</b>"]
    for j in jobs:
        bar = render_progress_bar(j.processed_pages, j.total_pages)
        safe_name = html.escape(j.file_name)
        target = getattr(j, "target_lang", "kk")
        lang_badge = {"kk": "🇰🇿 Казахский", "ru": "🇷🇺 Русский", "original": "📖 Оригинал"}.get(target, target)
        lines.append(
            f"• <b>{safe_name}</b> (<code>{j.id}</code>) — {lang_badge}\n"
            f"  Статус: {j.status} {bar}\n"
            f"  Этап: <i>{html.escape(j.status_text)}</i>"
        )
        if j.live_url:
            lines.append(f"  🔗 <a href='{j.live_url}'>Читать онлайн</a>")

    await message.answer("\n\n".join(lines), parse_mode="HTML")

async def process_pdf_task(
    job_id: str,
    bot: Bot,
    chat_id: int,
    message_id: int,
    file_name: str,
    target_lang: str
):
    safe_name = html.escape(file_name)
    lang_title = {
        "kk": "🇰🇿 Казахский академический (Қазақша)",
        "ru": "🇷🇺 Русский академический",
        "original": "📖 Публикация в оригинале (без перевода)"
    }.get(target_lang, target_lang)

    async def on_progress(text: str, processed: int, total: int):
        bar = render_progress_bar(processed, total)
        msg_text = (
            f"📖 <b>Обработка книги:</b> «{safe_name}»\n"
            f"🆔 <b>Задача:</b> <code>{job_id}</code>\n"
            f"🌐 <b>Режим:</b> {lang_title}\n\n"
            f"📊 <b>Прогресс:</b> {bar}\n"
            f"⏳ <b>Текущий этап:</b> {html.escape(text)}"
        )
        await safe_edit_message(bot, chat_id, message_id, msg_text)

    try:
        live_url = await pipeline.run(job_id=job_id, on_progress=on_progress)
        
        finish_text = (
            f"🎉 <b>Книга успешно опубликована!</b>\n\n"
            f"📖 <b>Файл:</b> «{safe_name}»\n"
            f"🌐 <b>Язык / Режим:</b> {lang_title}\n"
            f"🆔 <b>Задача:</b> <code>{job_id}</code>\n"
            f"✅ <b>Статус:</b> Обработка завершена, тесты качества Vitest пройдены, сайт обновлен на Netlify!\n\n"
            f"🔗 <a href='{live_url}'>Нажмите сюда, чтобы открыть книгу в веб-читалке</a>"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="📖 Читать книгу онлайн", url=live_url)
            ]]
        )
        await safe_edit_message(bot, chat_id, message_id, finish_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error in task {job_id}: {e}", exc_info=True)
        safe_err = html.escape(str(e)[:400])
        fail_text = (
            f"❌ <b>Ошибка при обработке книги:</b>\n«{safe_name}»\n\n"
            f"Детали ошибки: <code>{safe_err}</code>\n\n"
            f"Вы можете попробовать отправить файл повторно."
        )
        await safe_edit_message(bot, chat_id, message_id, fail_text)

@dp.callback_query(F.data.startswith("mode:"))
async def handle_mode_selection(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    _, target_lang, job_id = parts

    job = get_job(job_id)
    if not job:
        await callback.message.answer("❌ Задача не найдена.")
        return

    update_job(job_id, target_lang=target_lang, status="QUEUED", status_text="Запуск обработки...")
    safe_name = html.escape(job.file_name)
    lang_title = {
        "kk": "🇰🇿 Казахский академический (Қазақша)",
        "ru": "🇷🇺 Русский академический",
        "original": "📖 В оригинале (без перевода)"
    }.get(target_lang, target_lang)

    await safe_edit_message(
        bot,
        callback.message.chat.id,
        callback.message.message_id,
        f"⏳ <b>Запуск конвейера...</b>\n\n"
        f"📖 <b>Книга:</b> «{safe_name}»\n"
        f"🌐 <b>Выбран режим:</b> {lang_title}\n\n"
        f"Извлечение текста и WebP-сканов страниц..."
    )

    asyncio.create_task(
        process_pdf_task(
            job_id=job_id,
            bot=bot,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            file_name=job.file_name,
            target_lang=target_lang
        )
    )

@dp.message(F.document)
async def handle_document(message: types.Message, bot: Bot):
    doc = message.document
    if not doc:
        return

    if TELEGRAM_ADMIN_ID and message.from_user and message.from_user.id != int(TELEGRAM_ADMIN_ID):
        await message.reply("⛔ Извините, у вас нет прав на добавление книг на этот сервер.")
        return

    file_name = doc.file_name or "book.pdf"
    if not file_name.lower().endswith(".pdf") and doc.mime_type != "application/pdf":
        await message.reply(
            "⚠️ Пожалуйста, отправьте файл книги в формате <b>PDF</b>.",
            parse_mode="HTML"
        )
        return

    job_id = uuid.uuid4().hex[:8]
    slug = generate_slug(file_name)
    save_path = INBOX_DIR / f"{job_id}_{file_name}"
    safe_name = html.escape(file_name)

    # Initial confirmation message
    init_msg = await message.reply(
        f"📥 <b>Файл получен!</b>\n\n"
        f"📖 <b>Файл:</b> «{safe_name}»\n"
        f"🆔 <b>Задача:</b> <code>{job_id}</code>\n"
        f"⏳ Скачивание документа...",
        parse_mode="HTML"
    )

    try:
        await bot.download(doc, destination=save_path)
    except Exception as e:
        logger.error(f"Failed to download file from Telegram: {e}")
        safe_err = html.escape(str(e))
        await init_msg.edit_text(f"❌ Не удалось скачать файл: {safe_err}", parse_mode="HTML")
        return

    # Register in DB with WAITING_MODE status
    create_job(
        job_id=job_id,
        telegram_user_id=message.from_user.id if message.from_user else 0,
        telegram_chat_id=message.chat.id,
        telegram_message_id=init_msg.message_id,
        file_name=file_name,
        file_path=str(save_path),
        book_slug=slug,
        target_lang="kk"
    )

    # Ask user for desired mode / language
    mode_text = (
        f"📥 <b>Файл успешно скачан!</b>\n\n"
        f"📖 <b>Книга:</b> «{safe_name}»\n"
        f"🆔 <b>Задача:</b> <code>{job_id}</code>\n\n"
        f"<b>Выберите необходимый режим обработки:</b>\n"
        f"• <b>Казахский:</b> богословский перевод на қазақ тілі + оригинал\n"
        f"• <b>Русский:</b> академический перевод на русский язык + оригинал\n"
        f"• <b>В оригинале:</b> быстрая публикация без перевода (для готовых книг)"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇰🇿 Перевести на казахский (KK)",
                    callback_data=f"mode:kk:{job_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🇷🇺 Перевести на русский (RU)",
                    callback_data=f"mode:ru:{job_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📖 Опубликовать в оригинале (без перевода)",
                    callback_data=f"mode:original:{job_id}"
                )
            ]
        ]
    )

    await safe_edit_message(bot, message.chat.id, init_msg.message_id, mode_text, reply_markup=keyboard)

async def main():
    init_db()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    logger.info("Starting Telegram Bot with Long Polling (outbound HTTPS satisfying Telegram requirements)...")
    
    await bot.delete_webhook(drop_pending_updates=False)
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
