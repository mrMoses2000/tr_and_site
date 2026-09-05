"""Contract tests for the explicit P6--P11 staged publication boundary."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ingestion_service.jobs.repository import StaleLeaseError
from ingestion_service.release import (
    FakeReleaseBuilder,
    ProductionReleaseBuilderUnavailable,
    ReleaseBuildError,
    ReleaseIdentity,
    StagedPublicationAdapter,
    UnavailableReleaseBuilder,
)
from ingestion_service.release.promoter import ReleasePromoter
from ingestion_service.release.paths import ReleasePathError
from ingestion_service.release.staging import StagingManager


class FakeExecutionContext:
    def __init__(self, active: bool = True) -> None:
        self.active = active
        self.assertions = 0

    def assert_active(self) -> None:
        self.assertions += 1
        if not self.active:
            raise StaleLeaseError("fake lease is not active")


def _manifest(slug: str) -> dict:
    return {
        "schemaVersion": "2.0",
        "slug": slug,
        "pageRange": {"start": 1, "end": 1},
        "pages": [{"pageNumber": 1, "imageSrc": f"/scans/{slug}/page_1.webp"}],
    }


def _builder(slug: str, marker: bytes) -> FakeReleaseBuilder:
    return FakeReleaseBuilder(
        manifest=_manifest(slug),
        files={f"scans/{slug}/page_1.webp": marker},
    )


def _adapter(tmp_path: Path) -> tuple[StagedPublicationAdapter, Path, Path]:
    checkout = tmp_path / "app"
    checkout.mkdir()
    (checkout / "sentinel.txt").write_bytes(b"active checkout")

    staging = StagingManager(tmp_path / "staging")
    promoter = ReleasePromoter(tmp_path / "releases", tmp_path / "current", staging)
    initial = promoter.releases_dir / "initial"
    initial.mkdir()
    (initial / "live.txt").write_bytes(b"current release")
    promoter.current_pointer_path.symlink_to(initial)

    adapter = StagedPublicationAdapter(
        staging,
        promoter,
        active_checkout=checkout,
    )
    return adapter, checkout, promoter.current_pointer_path


def test_prepare_writes_only_to_per_job_stage_and_leaves_checkout_unchanged(tmp_path: Path) -> None:
    adapter, checkout, current = _adapter(tmp_path)
    identity = ReleaseIdentity("job-isolated", "safe-book", "release-isolated")
    before = {path.relative_to(checkout): path.read_bytes() for path in checkout.rglob("*") if path.is_file()}

    prepared = adapter.prepare(identity, _builder("safe-book", b"candidate"), FakeExecutionContext())

    after = {path.relative_to(checkout): path.read_bytes() for path in checkout.rglob("*") if path.is_file()}
    assert after == before
    assert prepared.stage_path.is_relative_to(tmp_path / "staging")
    assert current.resolve().name == "initial"


def test_publish_requires_active_execution_context_lease(tmp_path: Path) -> None:
    adapter, _checkout, current = _adapter(tmp_path)
    identity = ReleaseIdentity("job-lease", "safe-book", "release-lease")
    prepared = adapter.prepare(identity, _builder("safe-book", b"candidate"), FakeExecutionContext())
    stale = FakeExecutionContext(active=False)

    with pytest.raises(StaleLeaseError):
        adapter.publish(prepared, stale)

    assert current.resolve().name == "initial"
    assert prepared.stage_path.exists()


def test_adapter_rejects_current_pointer_inside_active_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "app"
    checkout.mkdir()
    staging = StagingManager(tmp_path / "staging")
    promoter = ReleasePromoter(tmp_path / "releases", checkout / "current", staging)

    with pytest.raises(ReleasePathError, match="current pointer.*outside active checkout"):
        StagedPublicationAdapter(staging, promoter, active_checkout=checkout)


def test_builder_failure_cleans_candidate_and_leaves_current_untouched(tmp_path: Path) -> None:
    adapter, _checkout, current = _adapter(tmp_path)
    identity = ReleaseIdentity("job-failed-build", "safe-book", "release-failed")

    class FailingBuilder:
        def build(self, _identity: ReleaseIdentity, _stage_path: Path) -> None:
            raise ReleaseBuildError("synthetic build failure")

    with pytest.raises(ReleaseBuildError):
        adapter.prepare(identity, FailingBuilder(), FakeExecutionContext())

    assert current.resolve().name == "initial"
    assert not adapter.staging.get_stage_path(identity.job_id).exists()


def test_exact_prepared_artifact_is_promoted_without_cross_job_mix(tmp_path: Path) -> None:
    adapter, _checkout, current = _adapter(tmp_path)
    context = FakeExecutionContext()
    first = ReleaseIdentity("job-first", "same-book", "release-first")
    second = ReleaseIdentity("job-second", "same-book", "release-second")
    prepared_first = adapter.prepare(first, _builder("same-book", b"first"), context)
    prepared_second = adapter.prepare(second, _builder("same-book", b"second"), context)

    promoted = adapter.publish(prepared_first, context)

    assert promoted.identity == first
    assert promoted.release_path == adapter.promoter.releases_dir / "release-first"
    assert (promoted.release_path / "scans/same-book/page_1.webp").read_bytes() == b"first"
    assert current.resolve() == promoted.release_path.resolve()
    assert prepared_second.stage_path.exists()


def test_concurrent_jobs_keep_identity_bound_to_their_staged_artifact(tmp_path: Path) -> None:
    adapter, _checkout, current = _adapter(tmp_path)
    context = FakeExecutionContext()
    identities = [
        ReleaseIdentity("job-concurrent-a", "same-book", "release-a"),
        ReleaseIdentity("job-concurrent-b", "same-book", "release-b"),
    ]
    prepared = [
        adapter.prepare(identity, _builder("same-book", marker), context)
        for identity, marker in zip(identities, (b"A", b"B"))
    ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda candidate: adapter.publish(candidate, context), prepared))

    assert {result.identity for result in results} == set(identities)
    for result, marker in zip(results, (b"A", b"B")):
        assert (result.release_path / "scans/same-book/page_1.webp").read_bytes() == marker
    assert current.resolve() in {result.release_path.resolve() for result in results}


def test_production_builder_fails_closed_until_explicitly_implemented() -> None:
    with pytest.raises(ProductionReleaseBuilderUnavailable):
        UnavailableReleaseBuilder().build(
            ReleaseIdentity("job-unavailable", "safe-book", "release-unavailable"),
            Path("/tmp/stage"),
        )
