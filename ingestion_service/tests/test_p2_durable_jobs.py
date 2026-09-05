import os
import time
import asyncio
import pytest
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

def test_p2_imports():
    from ingestion_service.jobs.repository import (
        JobRepository,
        JobState,
        StaleLeaseError,
        MaxAttemptsExceededError
    )
    from ingestion_service.jobs.worker import IngestionWorker

def test_job_lease_acquisition_deterministic_order(tmp_path):
    from ingestion_service.jobs.repository import JobRepository, JobState
    db_path = str(tmp_path / "test_jobs.db")
    repo = JobRepository(db_path)
    repo.init_schema()

    # Enqueue two jobs at different times
    job1 = repo.enqueue_job(
        job_id="job-1",
        source_sha256="sha-1111",
        file_name="book1.pdf",
        file_path="/tmp/book1.pdf",
        telegram_user_id=1,
        telegram_chat_id=100,
        telegram_message_id=10,
        book_slug="book-1"
    )
    time.sleep(0.01)
    job2 = repo.enqueue_job(
        job_id="job-2",
        source_sha256="sha-2222",
        file_name="book2.pdf",
        file_path="/tmp/book2.pdf",
        telegram_user_id=1,
        telegram_chat_id=100,
        telegram_message_id=11,
        book_slug="book-2"
    )

    # Worker 1 acquires next job
    acquired = repo.acquire_next_job(worker_id="worker-A", lease_seconds=30)
    assert acquired is not None
    assert acquired.id == "job-1"
    assert acquired.status == JobState.ACQUIRED
    assert acquired.worker_id == "worker-A"
    assert acquired.attempt_count == 1

    # Next acquisition gets job-2
    acquired2 = repo.acquire_next_job(worker_id="worker-A", lease_seconds=30)
    assert acquired2 is not None
    assert acquired2.id == "job-2"

    # No more queued jobs
    assert repo.acquire_next_job(worker_id="worker-A", lease_seconds=30) is None

def test_expired_lease_reclaimed_by_new_worker(tmp_path):
    from ingestion_service.jobs.repository import JobRepository, JobState
    db_path = str(tmp_path / "test_jobs.db")
    repo = JobRepository(db_path)
    repo.init_schema()

    job = repo.enqueue_job(
        job_id="job-lease",
        source_sha256="sha-lease",
        file_name="lease.pdf",
        file_path="/tmp/lease.pdf",
        telegram_user_id=1,
        telegram_chat_id=100,
        telegram_message_id=10,
        book_slug="lease-book"
    )

    # Worker 1 acquires with 1 second lease
    acquired = repo.acquire_next_job(worker_id="worker-1", lease_seconds=1)
    assert acquired.id == "job-lease"
    assert acquired.worker_id == "worker-1"

    # Immediately, no job is available
    assert repo.acquire_next_job(worker_id="worker-2", lease_seconds=30) is None

    # Manually expire the lease in DB
    past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    with repo.get_connection() as conn:
        conn.execute("UPDATE jobs SET lease_expires_at = ? WHERE id = ?", (past_time, "job-lease"))
        conn.commit()

    # Worker 2 reclaims the expired job
    reclaimed = repo.acquire_next_job(worker_id="worker-2", lease_seconds=30)
    assert reclaimed is not None
    assert reclaimed.id == "job-lease"
    assert reclaimed.worker_id == "worker-2"
    assert reclaimed.attempt_count == 2

def test_stale_worker_rejected_on_reclaimed_lease(tmp_path):
    from ingestion_service.jobs.repository import JobRepository, StaleLeaseError
    db_path = str(tmp_path / "test_jobs.db")
    repo = JobRepository(db_path)
    repo.init_schema()

    repo.enqueue_job(
        job_id="job-stale",
        source_sha256="sha-stale",
        file_name="stale.pdf",
        file_path="/tmp/stale.pdf",
        telegram_user_id=1,
        telegram_chat_id=100,
        telegram_message_id=10,
        book_slug="stale-book"
    )

    # Worker 1 acquires
    acquired = repo.acquire_next_job(worker_id="worker-1", lease_seconds=1)

    # Force expiration and Worker 2 reclaims
    past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    with repo.get_connection() as conn:
        conn.execute("UPDATE jobs SET lease_expires_at = ? WHERE id = ?", (past_time, "job-stale"))
        conn.commit()
    repo.acquire_next_job(worker_id="worker-2", lease_seconds=30)

    # Now Worker 1 (stale) attempts to save checkpoint
    with pytest.raises(StaleLeaseError):
        repo.save_checkpoint(
            job_id="job-stale",
            worker_id="worker-1",
            step="extract",
            checkpoint_data={"last_page": 5},
            processed_pages=5,
            lease_epoch=acquired.lease_epoch,
        )

def test_duplicate_hash_detection(tmp_path):
    from ingestion_service.jobs.repository import JobRepository
    db_path = str(tmp_path / "test_jobs.db")
    repo = JobRepository(db_path)
    repo.init_schema()

    repo.enqueue_job(
        job_id="job-orig",
        source_sha256="hash-duplicate-check",
        file_name="original.pdf",
        file_path="/tmp/orig.pdf",
        telegram_user_id=1,
        telegram_chat_id=100,
        telegram_message_id=10,
        book_slug="orig-book"
    )

    existing = repo.find_by_source_hash("hash-duplicate-check")
    assert existing is not None
    assert existing.id == "job-orig"
    assert repo.find_by_source_hash("nonexistent-hash") is None

def test_max_attempts_exceeded_fails_job(tmp_path):
    from ingestion_service.jobs.repository import JobRepository, JobState
    db_path = str(tmp_path / "test_jobs.db")
    repo = JobRepository(db_path)
    repo.init_schema()

    repo.enqueue_job(
        job_id="job-fail-max",
        source_sha256="hash-fail-max",
        file_name="fail.pdf",
        file_path="/tmp/fail.pdf",
        telegram_user_id=1,
        telegram_chat_id=100,
        telegram_message_id=10,
        book_slug="fail-book",
        max_attempts=2
    )

    # Attempt 1
    repo.acquire_next_job(worker_id="worker-1", lease_seconds=1)
    past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    with repo.get_connection() as conn:
        conn.execute("UPDATE jobs SET lease_expires_at = ? WHERE id = ?", (past_time, "job-fail-max"))
        conn.commit()

    # Attempt 2
    repo.acquire_next_job(worker_id="worker-2", lease_seconds=1)
    with repo.get_connection() as conn:
        conn.execute("UPDATE jobs SET lease_expires_at = ? WHERE id = ?", (past_time, "job-fail-max"))
        conn.commit()

    # Next attempt should see max_attempts reached and mark job as FAILED
    reclaimed = repo.acquire_next_job(worker_id="worker-3", lease_seconds=30)
    assert reclaimed is None

    job = repo.get_job("job-fail-max")
    assert job.status == JobState.FAILED
    assert "max attempts" in job.error_message.lower()

def test_worker_resume_from_checkpoint_after_simulated_sigterm(tmp_path):
    from ingestion_service.jobs.repository import JobRepository, JobState
    from ingestion_service.jobs.worker import IngestionWorker
    db_path = str(tmp_path / "test_jobs.db")
    repo = JobRepository(db_path)
    repo.init_schema()

    job_id = "job-sigterm"
    repo.enqueue_job(
        job_id=job_id,
        source_sha256="hash-sigterm",
        file_name="sigterm.pdf",
        file_path="/tmp/sigterm.pdf",
        telegram_user_id=1,
        telegram_chat_id=100,
        telegram_message_id=10,
        book_slug="sigterm-book"
    )

    # Worker 1 starts, processes page 1-3, saves checkpoint, then "dies"
    w1 = IngestionWorker(worker_id="worker-1", repository=repo, lease_seconds=2)
    job = repo.acquire_next_job(worker_id="worker-1", lease_seconds=2)
    repo.save_checkpoint(
        job_id=job_id,
        worker_id="worker-1",
        step="extract",
        checkpoint_data={"last_verified_page": 3},
        processed_pages=3,
        lease_epoch=job.lease_epoch,
    )

    # Simulate crash & lease expiration
    past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    with repo.get_connection() as conn:
        conn.execute("UPDATE jobs SET lease_expires_at = ? WHERE id = ?", (past_time, job_id))
        conn.commit()

    # Worker 2 takes over
    w2 = IngestionWorker(worker_id="worker-2", repository=repo, lease_seconds=30)
    resumed_job = repo.acquire_next_job(worker_id="worker-2", lease_seconds=30)
    assert resumed_job is not None
    assert resumed_job.id == job_id
    assert resumed_job.checkpoint_data is not None
    assert resumed_job.checkpoint_data.get("last_verified_page") == 3
    assert resumed_job.processed_pages == 3


def test_enqueue_rejects_duplicate_source_hash_atomically(tmp_path):
    from ingestion_service.jobs.repository import JobRepository, DuplicateSourceError

    repo = JobRepository(str(tmp_path / "duplicate.db"))
    repo.init_schema()
    kwargs = dict(
        source_sha256="same-source",
        file_name="book.pdf",
        file_path="/tmp/book.pdf",
        telegram_user_id=1,
        telegram_chat_id=1,
        telegram_message_id=1,
        book_slug="book",
    )
    repo.enqueue_job(job_id="job-1", **kwargs)
    with pytest.raises(DuplicateSourceError) as exc_info:
        repo.enqueue_job(job_id="job-2", **kwargs)
    assert exc_info.value.existing_job.id == "job-1"


def test_awaiting_mode_job_is_invisible_until_mode_is_selected(tmp_path):
    from ingestion_service.jobs.repository import JobRepository, JobState

    repo = JobRepository(str(tmp_path / "awaiting-mode.db"))
    repo.init_schema()
    created = repo.enqueue_job(
        job_id="job-awaiting",
        source_sha256="awaiting-source",
        file_name="book.pdf",
        file_path="/tmp/book.pdf",
        telegram_user_id=1,
        telegram_chat_id=1,
        telegram_message_id=1,
        book_slug="book",
        total_pages=42,
        initial_status=JobState.AWAITING_MODE,
    )
    assert created.status == JobState.AWAITING_MODE
    assert created.total_pages == 42
    assert repo.acquire_next_job("worker", lease_seconds=30) is None

    queued = repo.update_queued_job(
        "job-awaiting", target_lang="kk", status_text="В очереди на обработку"
    )
    assert queued.status == JobState.QUEUED
    acquired = repo.acquire_next_job("worker", lease_seconds=30)
    assert acquired is not None
    assert acquired.target_lang == "kk"

    with pytest.raises(ValueError, match="Unsupported target language"):
        repo.update_queued_job("job-awaiting", target_lang="javascript")


def test_worker_cancels_processor_when_lease_renewal_fails(tmp_path):
    from ingestion_service.jobs.repository import JobRepository, JobState, StaleLeaseError
    from ingestion_service.jobs.worker import IngestionWorker

    repo = JobRepository(str(tmp_path / "lease-cancel.db"))
    repo.init_schema()
    repo.enqueue_job(
        job_id="job-lease-cancel",
        source_sha256="lease-cancel-source",
        file_name="book.pdf",
        file_path="/tmp/book.pdf",
        telegram_user_id=1,
        telegram_chat_id=1,
        telegram_message_id=1,
        book_slug="book",
    )
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def processor(job, context):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def lease_failure(context):
        await started.wait()
        raise StaleLeaseError("forced lease loss")

    async def scenario():
        worker = IngestionWorker("worker", repo, lease_seconds=30, processor=processor)
        worker._renew_until_done = lease_failure
        with pytest.raises(StaleLeaseError, match="forced lease loss"):
            await worker.process_once()

    asyncio.run(scenario())
    assert cancelled.is_set()
    assert repo.get_job("job-lease-cancel").status == JobState.ACQUIRED


def test_worker_executes_processor_and_fences_completion(tmp_path):
    from ingestion_service.jobs.repository import JobRepository
    from ingestion_service.jobs.worker import IngestionWorker

    repo = JobRepository(str(tmp_path / "processor.db"))
    repo.init_schema()
    repo.enqueue_job(
        job_id="job-processor",
        source_sha256="processor-source",
        file_name="book.pdf",
        file_path="/tmp/book.pdf",
        telegram_user_id=1,
        telegram_chat_id=1,
        telegram_message_id=1,
        book_slug="book",
    )
    seen = []

    async def processor(job, context):
        seen.append(job.id)
        context.checkpoint("extract", {"last_verified_page": 3}, processed_pages=3)
        return "https://example.test/book"

    worker = IngestionWorker("worker-processor", repo, lease_seconds=10, processor=processor)
    asyncio.run(worker.process_once())
    stored = repo.get_job("job-processor")
    assert seen == ["job-processor"]
    assert stored.status.value == "DEPLOYED"
    assert stored.live_url == "https://example.test/book"
    assert stored.checkpoint_data["last_verified_page"] == 3


def test_stale_epoch_cannot_complete_after_reclaim(tmp_path):
    from ingestion_service.jobs.repository import JobRepository, StaleLeaseError
    from datetime import datetime, timezone, timedelta

    repo = JobRepository(str(tmp_path / "fencing.db"))
    repo.init_schema()
    repo.enqueue_job(
        job_id="job-fence",
        source_sha256="fence-source",
        file_name="book.pdf",
        file_path="/tmp/book.pdf",
        telegram_user_id=1,
        telegram_chat_id=1,
        telegram_message_id=1,
        book_slug="book",
    )
    first = repo.acquire_next_job("worker-old", lease_seconds=30)
    with repo.get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET lease_expires_at = ? WHERE id = ?",
            ((datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(), "job-fence"),
        )
        conn.commit()
    second = repo.acquire_next_job("worker-new", lease_seconds=30)
    assert second.lease_epoch != first.lease_epoch
    with pytest.raises(StaleLeaseError):
        repo.complete_job("job-fence", "worker-old", lease_epoch=first.lease_epoch)
