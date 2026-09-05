"""Contract tests for the per-job production release builder."""

from __future__ import annotations

import json
import shutil
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from ingestion_service.release import (
    ProductionReleaseBuilder,
    ReleaseIdentity,
    StagedPublicationAdapter,
)
from ingestion_service.release.promoter import ReleasePromoter
from ingestion_service.release.promoter import ReleaseBaseChangedError
from ingestion_service.release.staging import StagingManager
from ingestion_service.release.validator import ReleaseValidator


def _runner(command, *, cwd, **_kwargs):
    dist = Path(cwd) / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div>reader</div>", encoding="utf-8")
    public = Path(cwd) / "public"
    if public.is_dir():
        shutil.copytree(public, dist, dirs_exist_ok=True)
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def _builder(tmp_path: Path) -> tuple[ProductionReleaseBuilder, Path, Path]:
    app = tmp_path / "app"
    (app / "src").mkdir(parents=True)
    catalog = app / "src/data/library/generatedCatalog.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text('{"schemaVersion":"1","books":[]}', encoding="utf-8")
    (app / "package.json").write_text('{"scripts":{"build":"vite"}}', encoding="utf-8")
    (app / "checkout-sentinel").write_text("unchanged", encoding="utf-8")
    scans = tmp_path / "scans"
    scans.mkdir()
    (scans / "page_1.webp").write_bytes(b"scan")
    builder = ProductionReleaseBuilder(
        app_dir=app,
        workspace_root=tmp_path / "build-work",
        metadata={"title": "A book", "author": "An author", "sourceLanguage": "ru"},
        pages=[{"pageNumber": 1, "paragraphs": [], "footnotes": []}],
        scans_source_dir=scans,
        _runner=_runner,
        test_before_build=False,
    )
    return builder, app, scans


def test_builder_isolated_and_emits_operational_artifacts(tmp_path: Path) -> None:
    builder, app, scans = _builder(tmp_path)
    stage = tmp_path / "stage"
    stage.mkdir()
    identity = ReleaseIdentity("job-builder", "safe-book", "rel-safe-book-job-builder")

    before = {p.relative_to(app): p.read_bytes() for p in app.rglob("*") if p.is_file()}
    builder.build(identity, stage)
    after = {p.relative_to(app): p.read_bytes() for p in app.rglob("*") if p.is_file()}

    assert after == before
    assert (stage / "manifest.json").is_file()
    assert (stage / "healthz.json").is_file()
    assert (stage / "release.json").is_file()
    assert (stage / "catalog.json").is_file()
    assert (stage / "books/safe-book/manifest.json").is_file()
    assert (stage / "scans/safe-book/page_1.webp").read_bytes() == b"scan"
    assert json.loads((stage / "manifest.json").read_text())['releaseId'] == identity.release_id
    assert stat.S_IMODE((stage / "healthz.json").stat().st_mode) == 0o640
    assert stat.S_IMODE((stage / "scans").stat().st_mode) == 0o750


def test_staged_port_promotes_exact_builder_artifact(tmp_path: Path) -> None:
    builder, app, scans = _builder(tmp_path)
    staging = StagingManager(tmp_path / "staging")
    promoter = ReleasePromoter(tmp_path / "releases", tmp_path / "current", staging)
    adapter = StagedPublicationAdapter(staging, promoter, active_checkout=app)
    stage = staging.create_stage("job-builder", "safe-book", "rel-safe-book-job-builder")

    builder.build(ReleaseIdentity("job-builder", "safe-book", "rel-safe-book-job-builder"), stage)
    staging.compute_checksums("job-builder")
    manifest = ReleaseValidator().validate_staged_release(stage)
    assert manifest.release_id == "rel-safe-book-job-builder"


def test_builder_rejects_missing_scan_before_release_artifact(tmp_path: Path) -> None:
    builder, _app, _scans = _builder(tmp_path)
    stage = tmp_path / "stage"
    stage.mkdir()
    (tmp_path / "scans/page_1.webp").unlink()
    with pytest.raises(Exception, match="Missing scan"):
        builder.build(ReleaseIdentity("job-builder", "safe-book", "rel-safe-book-job-builder"), stage)


def test_adapter_rejects_release_root_nested_in_repository_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "repo"
    (checkout / "app").mkdir(parents=True)
    staging = StagingManager(tmp_path / "outside-staging")
    promoter = ReleasePromoter(checkout / "releases", checkout / "current", staging)
    with pytest.raises(ValueError, match="outside active checkout"):
        StagedPublicationAdapter(staging, promoter, active_checkout=checkout)


def test_second_release_preserves_first_runtime_book(tmp_path: Path) -> None:
    first_builder, app, _scans = _builder(tmp_path)
    staging = StagingManager(tmp_path / "staging")
    promoter = ReleasePromoter(tmp_path / "releases", tmp_path / "current", staging)
    adapter = StagedPublicationAdapter(staging, promoter, active_checkout=app)

    class Context:
        def assert_active(self) -> None:
            return None

    context = Context()
    first_identity = ReleaseIdentity("job-first", "first-book", "rel-first")
    first = adapter.prepare(first_identity, first_builder, context)
    adapter.publish(first, context)

    second_scans = tmp_path / "second-scans"
    second_scans.mkdir()
    (second_scans / "page_1.webp").write_bytes(b"second")
    second_builder = ProductionReleaseBuilder(
        app_dir=app,
        workspace_root=tmp_path / "second-build-work",
        metadata={"title": "Second", "author": "Author"},
        pages=[{"pageNumber": 1, "paragraphs": [], "footnotes": []}],
        scans_source_dir=second_scans,
        active_checkout=app,
        base_release_dir=promoter.current_release(),
        _runner=_runner,
        test_before_build=False,
    )
    second_identity = ReleaseIdentity("job-second", "second-book", "rel-second")
    second = adapter.prepare(second_identity, second_builder, context)
    published = adapter.publish(second, context)

    catalog = json.loads((published.release_path / "catalog.json").read_text(encoding="utf-8"))
    assert {book["slug"] for book in catalog["books"]} == {"first-book", "second-book"}
    assert (published.release_path / "books/first-book/manifest.json").is_file()
    assert (published.release_path / "scans/first-book/page_1.webp").read_bytes() == b"scan"
    assert (published.release_path / "scans/second-book/page_1.webp").read_bytes() == b"second"


def test_candidate_cannot_overwrite_a_release_published_after_its_build(tmp_path: Path) -> None:
    builder, app, _scans = _builder(tmp_path)
    staging = StagingManager(tmp_path / "staging")
    promoter = ReleasePromoter(tmp_path / "releases", tmp_path / "current", staging)
    adapter = StagedPublicationAdapter(staging, promoter, active_checkout=app)

    class Context:
        def assert_active(self) -> None:
            return None

    context = Context()
    first = adapter.prepare(
        ReleaseIdentity("job-race-a", "race-a", "rel-race-a"), builder, context
    )
    stale = adapter.prepare(
        ReleaseIdentity("job-race-b", "race-b", "rel-race-b"), builder, context
    )
    adapter.publish(first, context)

    with pytest.raises(ReleaseBaseChangedError, match="changed while candidate was building"):
        adapter.publish(stale, context)

    assert promoter.current_release().name == "rel-race-a"
    assert stale.stage_path.exists()


def test_builder_rejects_dependency_symlink_that_escapes_checkout(tmp_path: Path) -> None:
    builder, app, _scans = _builder(tmp_path)
    dependencies = app / "node_modules/.bin"
    dependencies.mkdir(parents=True)
    outside = tmp_path / "outside-tool"
    outside.write_text("tool", encoding="utf-8")
    (dependencies / "unsafe").symlink_to(outside)
    stage = tmp_path / "stage"
    stage.mkdir()

    with pytest.raises(Exception, match="symlink"):
        builder.build(ReleaseIdentity("job-link", "safe-book", "rel-link"), stage)
