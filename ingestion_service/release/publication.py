"""Job-aware publication port backed by the fenced staged adapter."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Sequence, TYPE_CHECKING

from .adapter import (
    ExecutionContext,
    PreparedRelease,
    ProductionReleaseBuilderUnavailable,
    ReleaseAdapterError,
    ReleaseIdentity,
    StagedPublicationAdapter,
)
from .builder import ProductionReleaseBuilder
from .promoter import ReleaseBaseChangedError

if TYPE_CHECKING:
    from ..jobs.worker import JobExecutionContext


class StagedReleasePublicationPort:
    """Build and publish one job's exact release artifact.

    The pipeline calls ``publish_job`` with all job inputs.  There is no
    process-wide candidate, and a missing execution context is rejected before
    a build or promotion side effect.
    """

    def __init__(
        self,
        adapter: StagedPublicationAdapter,
        *,
        app_dir: Path | str,
        workspace_root: Path | str,
        public_base_url: str = "",
        npm_bin: str = "npm",
        build_timeout_seconds: int = 900,
        test_before_build: bool = True,
    ) -> None:
        if any(char in public_base_url for char in "\r\n"):
            raise ValueError("public_base_url cannot contain control characters")
        self.adapter = adapter
        self.app_dir = Path(app_dir)
        self.workspace_root = Path(workspace_root)
        self.public_base_url = public_base_url.rstrip("/")
        self.npm_bin = npm_bin
        self.build_timeout_seconds = build_timeout_seconds
        self.test_before_build = test_before_build

    async def publish_job(
        self,
        *,
        job_id: str,
        slug: str,
        metadata: Mapping[str, Any],
        pages: Sequence[Mapping[str, Any]],
        scans_source_dir: Path | str,
        execution_context: ExecutionContext,
        on_phase: Callable[[str, str], Awaitable[None]],
    ) -> str:
        if execution_context is None or not callable(getattr(execution_context, "assert_active", None)):
            raise TypeError("execution_context with assert_active() is required")
        execution_context.assert_active()
        identity = ReleaseIdentity(job_id=job_id, slug=slug, release_id=f"rel-{slug}-{job_id}")
        for attempt in range(1, 4):
            base_release = self.adapter.promoter.current_release()
            builder = ProductionReleaseBuilder(
                app_dir=self.app_dir,
                workspace_root=self.workspace_root,
                metadata=metadata,
                pages=pages,
                scans_source_dir=scans_source_dir,
                npm_bin=self.npm_bin,
                build_timeout_seconds=self.build_timeout_seconds,
                test_before_build=self.test_before_build,
                active_checkout=self.adapter.active_checkout,
                base_release_dir=base_release,
            )
            await on_phase(
                "TESTING",
                "🧪 Проверка и production-сборка изолированного staged-релиза...",
            )
            prepared: PreparedRelease = await asyncio.to_thread(
                self.adapter.prepare,
                identity,
                builder,
                execution_context,
            )
            await on_phase("PUBLISHING", "🚀 Атомарное переключение validated-релиза...")
            try:
                await asyncio.to_thread(self.adapter.publish, prepared, execution_context)
                return self._book_url(slug, prepared.manifest)
            except ReleaseBaseChangedError:
                self.adapter.staging.cleanup_stage(identity.job_id)
                if attempt == 3:
                    raise
                execution_context.assert_active()
        raise AssertionError("unreachable publication retry state")

    async def publish(self, slug: str) -> str:
        """Reject the legacy un-fenced port shape explicitly."""
        raise ProductionReleaseBuilderUnavailable(
            f"Staged publication for {slug!r} requires publish_job(..., execution_context=...)"
        )

    def _book_url(self, slug: str, manifest: Any) -> str:
        start_page = getattr(manifest, "start_page", 1)
        suffix = f"/#book={slug}&page={start_page}"
        return f"{self.public_base_url}{suffix}" if self.public_base_url else suffix
