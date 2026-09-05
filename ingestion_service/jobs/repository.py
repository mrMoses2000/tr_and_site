import json
import sqlite3
import hashlib
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class JobState(str, Enum):
    # A PDF has been accepted and inspected, but must not be visible to a
    # worker until the uploader chooses a processing mode.
    AWAITING_MODE = "AWAITING_MODE"
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


class DuplicateSourceError(Exception):
    """Raised when a source hash is already represented by an existing job."""

    def __init__(self, existing_job: "JobRecord"):
        self.existing_job = existing_job
        super().__init__(f"Source already enqueued as job {existing_job.id}")


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
    lease_epoch: int = 0
    version: int = 0
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
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            # A read-only or non-file SQLite backend may not support WAL.
            pass
        return conn

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> JobRecord:
        data = dict(row)
        if data.get("checkpoint_data"):
            try:
                data["checkpoint_data"] = json.loads(data["checkpoint_data"])
            except (TypeError, ValueError):
                data["checkpoint_data"] = None
        return JobRecord(**data)

    @staticmethod
    def _begin_immediate(conn: sqlite3.Connection) -> None:
        conn.execute("BEGIN IMMEDIATE")

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
                    lease_epoch INTEGER DEFAULT 0,
                    version INTEGER DEFAULT 0,
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
                ("lease_epoch", "INTEGER DEFAULT 0"),
                ("version", "INTEGER DEFAULT 0"),
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
        total_pages: int = 0,
        initial_status: JobState | str = JobState.QUEUED,
    ) -> JobRecord:
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            initial_status = JobState(initial_status)
        except ValueError as exc:
            raise ValueError(f"Unsupported initial job status: {initial_status}") from exc
        if initial_status not in {JobState.AWAITING_MODE, JobState.QUEUED}:
            raise ValueError("Jobs may only be enqueued as AWAITING_MODE or QUEUED")
        initial_status_text = (
            "Ожидается выбор режима обработки"
            if initial_status == JobState.AWAITING_MODE
            else "В очереди на обработку"
        )
        with self.get_connection() as conn:
            self._begin_immediate(conn)
            if source_sha256:
                existing_row = conn.execute(
                    "SELECT * FROM jobs WHERE source_sha256 = ? ORDER BY created_at ASC LIMIT 1",
                    (source_sha256,),
                ).fetchone()
                if existing_row:
                    conn.rollback()
                    raise DuplicateSourceError(self._decode_row(existing_row))
            conn.execute("""
                INSERT INTO jobs (
                    id, source_sha256, file_name, file_path,
                    telegram_user_id, telegram_chat_id, telegram_message_id,
                    book_slug, target_lang, source_lang,
                    total_pages, status, status_text, attempt_count, max_attempts,
                    lease_epoch, version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 0, 0, ?, ?)
            """, (
                job_id, source_sha256, file_name, file_path,
                telegram_user_id, telegram_chat_id, telegram_message_id,
                book_slug, target_lang, source_lang, total_pages,
                initial_status.value, initial_status_text,
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
            self._begin_immediate(conn)
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
                            version = version + 1,
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
                        lease_epoch = lease_epoch + 1,
                        version = version + 1,
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
                    return self._decode_row(cur.fetchone())
                conn.commit()

        return None

    def save_checkpoint(
        self,
        job_id: str,
        worker_id: str,
        step: str,
        checkpoint_data: dict[str, Any],
        processed_pages: Optional[int] = None,
        *,
        lease_epoch: int,
    ):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            self._begin_immediate(conn)
            cur = conn.cursor()
            cur.execute("SELECT worker_id, lease_expires_at, lease_epoch FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            if not row:
                raise StaleLeaseError(f"Job {job_id} does not exist")

            db_worker = row["worker_id"]
            expires_at = row["lease_expires_at"]
            current_epoch = row["lease_epoch"] or 0
            expected_epoch = lease_epoch

            if db_worker != worker_id or expected_epoch != current_epoch or not expires_at or expires_at < now_iso:
                raise StaleLeaseError(
                    f"Worker '{worker_id}' does not hold a valid lease for job '{job_id}' "
                    f"(current worker: '{db_worker}', expires: '{expires_at}')"
                )

            fields = ["current_step = ?", "checkpoint_data = ?", "version = version + 1", "updated_at = ?"]
            params: list[Any] = [step, json.dumps(checkpoint_data), now_iso]

            if processed_pages is not None:
                fields.append("processed_pages = ?")
                params.append(processed_pages)

            params.extend([job_id, worker_id, expected_epoch, now_iso])
            cur.execute(
                f"UPDATE jobs SET {', '.join(fields)} "
                "WHERE id = ? AND worker_id = ? AND lease_epoch = ? AND lease_expires_at >= ?",
                params,
            )
            if cur.rowcount != 1:
                raise StaleLeaseError(f"Worker '{worker_id}' lost the lease for job '{job_id}'")
            conn.commit()

    def renew_lease(
        self,
        job_id: str,
        worker_id: str,
        extension_seconds: int = 60,
        *,
        lease_epoch: int,
    ) -> bool:
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        new_expires = (now_dt + timedelta(seconds=extension_seconds)).isoformat()

        with self.get_connection() as conn:
            self._begin_immediate(conn)
            cur = conn.cursor()
            cur.execute("""
                UPDATE jobs 
                SET lease_expires_at = ?, version = version + 1, updated_at = ?
                WHERE id = ? 
                  AND worker_id = ? 
                  AND lease_epoch = ?
                  AND lease_expires_at >= ?
            """, (new_expires, now_iso, job_id, worker_id, lease_epoch, now_iso))
            conn.commit()
            return cur.rowcount == 1

    def complete_job(
        self,
        job_id: str,
        worker_id: str,
        live_url: Optional[str] = None,
        *,
        lease_epoch: int,
    ):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            self._begin_immediate(conn)
            cur = conn.cursor()
            cur.execute("""
                UPDATE jobs 
                SET status = 'DEPLOYED',
                    status_text = 'Готово',
                    live_url = ?,
                    lease_expires_at = NULL,
                    version = version + 1,
                    updated_at = ?
                WHERE id = ? AND worker_id = ? AND lease_epoch = ? AND lease_expires_at >= ?
            """, (live_url, now_iso, job_id, worker_id, lease_epoch, now_iso))
            if cur.rowcount != 1:
                raise StaleLeaseError(f"Worker '{worker_id}' lost the lease for job '{job_id}'")
            conn.commit()

    def fail_job(
        self,
        job_id: str,
        worker_id: str,
        error_message: str,
        *,
        lease_epoch: int,
    ):
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            self._begin_immediate(conn)
            cur = conn.cursor()
            cur.execute("""
                UPDATE jobs 
                SET status = 'FAILED',
                    status_text = 'Ошибка обработки',
                    error_message = ?,
                    lease_expires_at = NULL,
                    version = version + 1,
                    updated_at = ?
                WHERE id = ? AND worker_id = ? AND lease_epoch = ? AND lease_expires_at >= ?
            """, (error_message, now_iso, job_id, worker_id, lease_epoch, now_iso))
            if cur.rowcount != 1:
                raise StaleLeaseError(f"Worker '{worker_id}' lost the lease for job '{job_id}'")
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
                return self._decode_row(row)
        return None

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            if row:
                return self._decode_row(row)
        return None

    def update_queued_job(
        self,
        job_id: str,
        *,
        target_lang: Optional[str] = None,
        status_text: Optional[str] = None,
    ) -> JobRecord:
        """Atomically commit the mode choice and release a job to workers."""
        if target_lang is not None and target_lang not in {"original", "ru", "kk", "en"}:
            raise ValueError("Unsupported target language")
        if target_lang is None and status_text is None:
            job = self.get_job(job_id)
            if not job:
                raise KeyError(job_id)
            return job

        fields = ["status = 'QUEUED'", "version = version + 1", "updated_at = ?"]
        params: list[Any] = [datetime.now(timezone.utc).isoformat()]
        if target_lang is not None:
            fields.append("target_lang = ?")
            params.append(target_lang)
        if status_text is not None:
            fields.append("status_text = ?")
            params.append(status_text)
        params.append(job_id)
        with self.get_connection() as conn:
            self._begin_immediate(conn)
            cur = conn.execute(
                f"UPDATE jobs SET {', '.join(fields)} WHERE id = ? AND status = 'AWAITING_MODE'",
                params,
            )
            if cur.rowcount != 1:
                conn.rollback()
                raise StaleLeaseError(f"Job '{job_id}' is not awaiting mode selection")
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            conn.commit()
            return self._decode_row(row)

    def list_recent_jobs(self, limit: int = 10) -> list[JobRecord]:
        bounded_limit = max(1, min(int(limit), 100))
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (bounded_limit,)
            ).fetchall()
            return [self._decode_row(row) for row in rows]


def sha256_file(file_path: str) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
