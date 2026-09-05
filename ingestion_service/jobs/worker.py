import asyncio
import inspect
import logging
import signal
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from .repository import JobRepository, JobRecord, StaleLeaseError

logger = logging.getLogger("ingestion_worker")

ProcessorResult = Optional[str]
Processor = Callable[[JobRecord, "JobExecutionContext"], Awaitable[ProcessorResult] | ProcessorResult]


@dataclass
class JobExecutionContext:
    """Fenced operations exposed to a processor for one leased job."""

    repository: JobRepository
    job: JobRecord
    worker_id: str
    _lease_seconds: int = 60

    def checkpoint(
        self,
        step: str,
        data: dict[str, Any],
        processed_pages: Optional[int] = None,
    ) -> None:
        self.repository.save_checkpoint(
            job_id=self.job.id,
            worker_id=self.worker_id,
            step=step,
            checkpoint_data=data,
            processed_pages=processed_pages,
            lease_epoch=self.job.lease_epoch,
        )

    def renew_lease(self, extension_seconds: Optional[int] = None) -> None:
        renewed = self.repository.renew_lease(
            job_id=self.job.id,
            worker_id=self.worker_id,
            extension_seconds=extension_seconds or self._lease_seconds,
            lease_epoch=self.job.lease_epoch,
        )
        if not renewed:
            raise StaleLeaseError(f"Worker '{self.worker_id}' lost the lease for job '{self.job.id}'")


class IngestionWorker:
    def __init__(
        self,
        worker_id: str,
        repository: JobRepository,
        lease_seconds: int = 60,
        processor: Optional[Processor] = None,
    ):
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be greater than zero")
        self.worker_id = worker_id
        self.repository = repository
        self.lease_seconds = lease_seconds
        self.processor = processor
        self._running = True

    def stop(self):
        logger.info("Worker %s received stop signal", self.worker_id)
        self._running = False

    def setup_signal_handlers(self):
        def _sig_handler(sig, frame):
            self.stop()

        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT, _sig_handler)

    def acquire(self) -> Optional[JobRecord]:
        job = self.repository.acquire_next_job(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if job:
            logger.info(
                "Worker %s acquired job %s (attempt=%s epoch=%s)",
                self.worker_id,
                job.id,
                job.attempt_count,
                job.lease_epoch,
            )
        return job

    async def process_once(self) -> Optional[JobRecord]:
        job = self.acquire()
        if not job:
            return None

        if self.processor is None:
            # Compatibility mode for callers that only use repository polling.
            return job

        context = JobExecutionContext(
            repository=self.repository,
            job=job,
            worker_id=self.worker_id,
            _lease_seconds=self.lease_seconds,
        )
        processor_task = asyncio.create_task(self._invoke_processor(job, context))
        renewal_task = asyncio.create_task(self._renew_until_done(context))
        try:
            done, _ = await asyncio.wait(
                {processor_task, renewal_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            # A renewal failure is a hard fencing event.  Cancel the
            # processor before it can perform more extraction/deploy side
            # effects, then let the caller reclaim the expired job.
            if renewal_task in done:
                processor_task.cancel()
                await asyncio.gather(processor_task, return_exceptions=True)
                renewal_error = renewal_task.exception()
                if renewal_error is not None:
                    raise renewal_error
                raise StaleLeaseError(f"Lease renewal stopped for job '{job.id}'")

            result = processor_task.result()
            context.renew_lease()
            self.repository.complete_job(
                job_id=job.id,
                worker_id=self.worker_id,
                live_url=result,
                lease_epoch=job.lease_epoch,
            )
            return job
        except StaleLeaseError:
            logger.error("Worker %s lost lease for job %s", self.worker_id, job.id)
            raise
        except Exception as exc:
            logger.error("Worker %s failed job %s: %s", self.worker_id, job.id, exc, exc_info=True)
            try:
                self.repository.fail_job(
                    job_id=job.id,
                    worker_id=self.worker_id,
                    error_message=str(exc)[:1000],
                    lease_epoch=job.lease_epoch,
                )
            except StaleLeaseError:
                logger.error("Worker %s could not record failure for stale job %s", self.worker_id, job.id)
            return job
        finally:
            processor_task.cancel()
            renewal_task.cancel()
            await asyncio.gather(processor_task, renewal_task, return_exceptions=True)

    async def _invoke_processor(
        self,
        job: JobRecord,
        context: JobExecutionContext,
    ) -> ProcessorResult:
        if self.processor is None:
            return None
        result = self.processor(job, context)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _renew_until_done(self, context: JobExecutionContext) -> None:
        interval = max(1.0, self.lease_seconds / 3)
        while True:
            await asyncio.sleep(interval)
            context.renew_lease()

    def run_once(self) -> Optional[JobRecord]:
        """Synchronous compatibility wrapper; use process_once in async daemons."""
        return self.acquire()

    async def run_async(self, poll_interval: float = 2.0):
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero")
        logger.info("Worker %s started async loop (poll=%ss)", self.worker_id, poll_interval)
        while self._running:
            try:
                job = await self.process_once()
                if not job:
                    await asyncio.sleep(poll_interval)
            except StaleLeaseError:
                await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Worker %s unhandled error in loop", self.worker_id)
                await asyncio.sleep(poll_interval)
        logger.info("Worker %s stopped cleanly", self.worker_id)

    def run_loop(self, poll_interval: float = 2.0):
        """Blocking compatibility entrypoint for a dedicated worker process."""
        self.setup_signal_handlers()
        asyncio.run(self.run_async(poll_interval=poll_interval))
