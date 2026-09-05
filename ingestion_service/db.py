import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from .config import DB_PATH

class Job(BaseModel):
    id: str
    telegram_user_id: int
    telegram_chat_id: int
    telegram_message_id: int
    file_name: str
    file_path: str
    book_slug: str
    target_lang: str = "kk"  # 'kk' (Kazakh), 'ru' (Russian), 'original' (no translation)
    source_lang: str = "auto"
    total_pages: int = 0
    processed_pages: int = 0
    status: str = "QUEUED" # QUEUED, EXTRACTING, TRANSLATING, COMPILING, TESTING, DEPLOYED, FAILED
    status_text: str = "В очереди на обработку"
    error_message: Optional[str] = None
    live_url: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                telegram_user_id INTEGER,
                telegram_chat_id INTEGER,
                telegram_message_id INTEGER,
                file_name TEXT,
                file_path TEXT,
                book_slug TEXT,
                target_lang TEXT DEFAULT 'kk',
                source_lang TEXT DEFAULT 'auto',
                total_pages INTEGER DEFAULT 0,
                processed_pages INTEGER DEFAULT 0,
                status TEXT DEFAULT 'QUEUED',
                status_text TEXT DEFAULT 'В очереди на обработку',
                error_message TEXT,
                live_url TEXT,
                created_at TEXT,
                updated_at TEXT
            );
        """)
        # Safe migration for existing DB
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN target_lang TEXT DEFAULT 'kk';")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN source_lang TEXT DEFAULT 'auto';")
        except sqlite3.OperationalError:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                slug TEXT PRIMARY KEY,
                title TEXT,
                title_ru TEXT,
                author TEXT,
                author_ru TEXT,
                total_pages INTEGER,
                created_at TEXT
            );
        """)
        conn.commit()

def create_job(
    job_id: str,
    telegram_user_id: int,
    telegram_chat_id: int,
    telegram_message_id: int,
    file_name: str,
    file_path: str,
    book_slug: str,
    target_lang: str = "kk",
    source_lang: str = "auto"
) -> Job:
    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO jobs (
                id, telegram_user_id, telegram_chat_id, telegram_message_id,
                file_name, file_path, book_slug, target_lang, source_lang,
                status, status_text, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'QUEUED', 'В очереди на обработку', ?, ?)
        """, (
            job_id, telegram_user_id, telegram_chat_id, telegram_message_id,
            file_name, file_path, book_slug, target_lang, source_lang,
            now, now
        ))
        conn.commit()
    
    return Job(
        id=job_id,
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=telegram_message_id,
        file_name=file_name,
        file_path=file_path,
        book_slug=book_slug,
        target_lang=target_lang,
        source_lang=source_lang,
        created_at=now,
        updated_at=now
    )

def update_job(
    job_id: str,
    status: Optional[str] = None,
    status_text: Optional[str] = None,
    total_pages: Optional[int] = None,
    processed_pages: Optional[int] = None,
    error_message: Optional[str] = None,
    live_url: Optional[str] = None,
    target_lang: Optional[str] = None
):
    now = datetime.now(timezone.utc).isoformat()
    fields = ["updated_at = ?"]
    params = [now]

    if status is not None:
        fields.append("status = ?")
        params.append(status)
    if status_text is not None:
        fields.append("status_text = ?")
        params.append(status_text)
    if total_pages is not None:
        fields.append("total_pages = ?")
        params.append(total_pages)
    if processed_pages is not None:
        fields.append("processed_pages = ?")
        params.append(processed_pages)
    if error_message is not None:
        fields.append("error_message = ?")
        params.append(error_message)
    if live_url is not None:
        fields.append("live_url = ?")
        params.append(live_url)
    if target_lang is not None:
        fields.append("target_lang = ?")
        params.append(target_lang)

    params.append(job_id)
    with get_db_connection() as conn:
        conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()

def get_job(job_id: str) -> Optional[Job]:
    with get_db_connection() as conn:
        cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cur.fetchone()
        if row:
            return Job(**dict(row))
    return None

def get_recent_jobs(limit: int = 10) -> List[Job]:
    with get_db_connection() as conn:
        cur = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
        return [Job(**dict(row)) for row in cur.fetchall()]
