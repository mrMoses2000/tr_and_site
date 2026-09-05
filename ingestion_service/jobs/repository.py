import json
import sqlite3
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class JobState(str, Enum):
    QUEUED = "QUEUED"
    ACQUIRED = "ACQUIRED"
    EXTRACTING = "EXTRACTING"
    TRANSLATING = "TRANSLATING"
    COMPILING = "COMPILING"
    TESTING = "TESTING"
    DEPLOYED = "DEPLOYED"
    FAILED = "FAILED"


class StaleLeaseError(Exception):
    """Raised when a worker tries to update a job without a valid active lease."""
    pass


class MaxAttemptsExceededError(Exception):
    """Raised when a job has exceeded its configured max lease attempts."""
    pass


class JobRecord(BaseModel):
    id: str
    source_sha256: str = ""
    telegram_user_id: int
    telegram_chat_id: int
    telegram_message_id: int
    file_name: str
    file_path: str
    book_slug: str
    target_lang: str = "kk"
    source_lang: str = "auto"
    total_pages: int = 0
    processed_pages: int = 0
    status: JobState = JobState.QUEUED
    status_text: str = "В очереди на обработку"
    worker_id: Optional[str] = None
    lease_expires_at: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    current_step: Optional[str] = None
    checkpoint_data: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    live_url: Optional[str] = None
    created_at: str
    updated_at: str


class JobRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    source_sha256 TEXT DEFAULT '',
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
                    worker_id TEXT,
                    lease_expires_at TEXT,
                    attempt_count INTEGER DEFAULT 0,
                    max_attempts INTEGER DEFAULT 3,
                    current_step TEXT,
                    checkpoint_data TEXT,
                    error_message TEXT,
                    live_url TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
            """)

            # Safe migrations if table existed previously with fewer columns
            existing_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(jobs);").fetchall()
            }
            migrations = [
                ("source_sha256", "TEXT DEFAULT ''"),
                ("worker_id", "TEXT"),
                ("lease_expires_at", "TEXT"),
                ("attempt_count", "INTEGER DEFAULT 0"),
                ("max_attempts", "INTEGER DEFAULT 3"),
                ("current_step", "TEXT"),
                ("checkpoint_data", "TEXT"),
            ]
            for col_name, col_def in migrations:
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_def};")

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_status_lease 
                ON jobs (status, lease_expires_at);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_source_sha 
                ON jobs (source_sha256);
            """)
            conn.commit()

    def enqueue_job(
        self,
        job_id: str,
        source_sha256: str,
        file_name: str,
        file_path: str,
        telegram_user_id: int,
        telegram_chat_id: int,
        telegram_message_id: int,
        book_slug: str,
        target_lang: str = "kk",
        source_lang: str = "auto",
        max_attempts: int = 3,
    ) -> JobRecord:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO jobs (
                    id, source_sha256, file_name, file_path,
                    telegram_user_id, telegram_chat_id, telegram_message_id,
                    book_slug, target_lang, source_lang,
                    status, status_text, attempt_count, max_attempts,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'QUEUED', 'В очереди на обработку', 0, ?, ?, ?)
            """, (
                job_id, source_sha256, file_name, file_path,
                telegram_user_id, telegram_chat_id, telegram_message_id,
                book_slug, target_lang, source_lang,
                max_attempts, now_iso, now_iso,
            ))
            conn.commit()

        job = self.get_job(job_id)
        if not job:
            raise RuntimeError(f"Failed to retrieve created job {job_id}")
        return job

    def acquire_next_job(
        self,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> Optional[JobRecord]:
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        lease_expires = (now_dt + timedelta(seconds=lease_seconds)).isoformat()

        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM jobs 
                WHERE status = 'QUEUED' 
                   OR (status NOT IN ('DEPLOYED', 'FAILED') AND lease_expires_at IS NOT NULL AND lease_expires_at < ?)
                ORDER BY created_at ASC, id ASC
            """, (now_iso,))
            rows = cur.fetchall()

            for row in rows:
                job_dict = dict(row)
                attempt_count = job_dict.get("attempt_count") or 0
                max_attempts = job_dict.get("max_attempts") or 3

                # Expired lease recovery increments attempt_count
                if job_dict["status"] != "QUEUED":
                    attempt_count += 1
                else:
                    attempt_count = 1

                if attempt_count > max_attempts:
                    cur.execute("""
                        UPDATE jobs 
                        SET status = 'FAILED', 
                            error_message = ?, 
                            lease_expires_at = NULL,
                            updated_at = ?
                        WHERE id = ?
                    """, (f"Exceeded max attempts ({max_attempts})", now_iso, job_dict["id"]))
                    conn.commit()
                    continue

                cur.execute("""
                    UPDATE jobs 
                    SET status = 'ACQUIRED',
                        worker_id = ?,
                        lease_expires_at = ?,
                        attempt_count = ?,
                        updated_at = ?
                    WHERE id = ? 
                      AND (
                          status = 'QUEUED' 
                          OR (lease_expires_at IS NOT NULL AND lease_expires_at < ?)
                      )
                """, (worker_id, lease_expires, attempt_count, now_iso, job_dict["id"], now_iso))

                if cur.rowcount == 1:
                    conn.commit()
                    cur.execute("SELECT * FROM jobs WHERE id = ?", (job_dict["id"],))
                    updated_row = dict(cur.fetchone())
                    if updated_row.get("checkpoint_data"):
                        try:
                            updated_row["checkpoint_data"] = json.loads(updated_row["checkpoint_data"])
                        except Exception:
                            pass
                    return JobRecord(**updated_row)
                conn.commit()

        return None

    def save_checkpoint(
        self,
        job_id: str,
        worker_id: str,
        step: str,
        checkpoint_data: dict[str, Any],
        processed_pages: Optional[int] = None,
    ):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT worker_id, lease_expires_at FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            if not row:
                raise StaleLeaseError(f"Job {job_id} does not exist")

            db_worker = row["worker_id"]
            expires_at = row["lease_expires_at"]

            if db_worker != worker_id or not expires_at or expires_at < now_iso:
                raise StaleLeaseError(
                    f"Worker '{worker_id}' does not hold a valid lease for job '{job_id}' "
                    f"(current worker: '{db_worker}', expires: '{expires_at}')"
                )

            fields = ["current_step = ?", "checkpoint_data = ?", "updated_at = ?"]
            params: list[Any] = [step, json.dumps(checkpoint_data), now_iso]

            if processed_pages is not None:
                fields.append("processed_pages = ?")
                params.append(processed_pages)

            params.append(job_id)
            cur.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()

    def renew_lease(
        self,
        job_id: str,
        worker_id: str,
        extension_seconds: int = 60,
    ) -> bool:
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        new_expires = (now_dt + timedelta(seconds=extension_seconds)).isoformat()

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE jobs 
                SET lease_expires_at = ?, updated_at = ?
                WHERE id = ? 
                  AND worker_id = ? 
                  AND lease_expires_at >= ?
            """, (new_expires, now_iso, job_id, worker_id, now_iso))
            conn.commit()
            return cur.rowcount == 1

    def complete_job(
        self,
        job_id: str,
        worker_id: str,
        live_url: Optional[str] = None,
    ):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE jobs 
                SET status = 'DEPLOYED',
                    status_text = 'Готово',
                    live_url = ?,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE id = ? AND worker_id = ?
            """, (live_url, now_iso, job_id, worker_id))
            conn.commit()

    def fail_job(
        self,
        job_id: str,
        worker_id: str,
        error_message: str,
    ):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE jobs 
                SET status = 'FAILED',
                    status_text = 'Ошибка обработки',
                    error_message = ?,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE id = ? AND worker_id = ?
            """, (error_message, now_iso, job_id, worker_id))
            conn.commit()

    def find_by_source_hash(self, source_sha256: str) -> Optional[JobRecord]:
        if not source_sha256:
            return None
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM jobs WHERE source_sha256 = ? ORDER BY created_at DESC LIMIT 1",
                (source_sha256,),
            )
            row = cur.fetchone()
            if row:
                d = dict(row)
                if d.get("checkpoint_data"):
                    try:
                        d["checkpoint_data"] = json.loads(d["checkpoint_data"])
                    except Exception:
                        pass
                return JobRecord(**d)
        return None

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            if row:
                d = dict(row)
                if d.get("checkpoint_data"):
                    try:
                        d["checkpoint_data"] = json.loads(d["checkpoint_data"])
                    except Exception:
                        pass
                return JobRecord(**d)
        return None
