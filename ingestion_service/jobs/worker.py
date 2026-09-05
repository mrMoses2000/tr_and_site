import logging
import signal
import time
from typing import Optional
from .repository import JobRepository, JobRecord, JobState, StaleLeaseError

logger = logging.getLogger("ingestion_worker")


class IngestionWorker:
    def __init__(
        self,
        worker_id: str,
        repository: JobRepository,
        lease_seconds: int = 60,
    ):
        self.worker_id = worker_id
        self.repository = repository
        self.lease_seconds = lease_seconds
        self._running = True

    def stop(self):
        logger.info(f"Worker {self.worker_id} received stop signal")
        self._running = False

    def setup_signal_handlers(self):
        def _sig_handler(sig, frame):
            self.stop()

        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT, _sig_handler)

    def run_once(self) -> Optional[JobRecord]:
        """Polls repository for the next queued or expired job and processes it."""
        job = self.repository.acquire_next_job(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if not job:
            return None

        logger.info(f"Worker {self.worker_id} acquired job {job.id} (attempt {job.attempt_count})")
        return job

    def run_loop(self, poll_interval: float = 2.0):
        self.setup_signal_handlers()
        logger.info(f"Worker {self.worker_id} started loop (poll={poll_interval}s)")
        while self._running:
            try:
                job = self.run_once()
                if not job:
                    time.sleep(poll_interval)
            except Exception as e:
                logger.error(f"Worker {self.worker_id} unhandled error in loop: {e}", exc_info=True)
                time.sleep(poll_interval)
        logger.info(f"Worker {self.worker_id} stopped cleanly")
