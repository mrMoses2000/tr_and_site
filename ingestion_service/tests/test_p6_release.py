import os
import pytest
from pathlib import Path

def test_p6_imports():
    from ingestion_service.release.models import ReleaseManifest, ChecksumEntry
    from ingestion_service.release.staging import StagingManager
    from ingestion_service.release.validator import ReleaseValidator, ReleaseValidationError
    from ingestion_service.release.promoter import ReleasePromoter

def test_failure_after_scans_leaves_live_library_untouched(tmp_path):
    from ingestion_service.release.staging import StagingManager
    from ingestion_service.release.promoter import ReleasePromoter

    releases_dir = tmp_path / "releases"
    staging_dir = tmp_path / "staging"
    current_symlink = tmp_path / "current"

    # Setup initial live release "v1"
    v1_dir = releases_dir / "rel-initial-v1"
    v1_dir.mkdir(parents=True)
    (v1_dir / "manifest.json").write_text('{"version": "1.0", "slug": "test"}')
    current_symlink.symlink_to(v1_dir)

    staging_mgr = StagingManager(staging_dir)

    # Job starts staging scans
    job_id = "job-fail-scans"
    stage_path = staging_mgr.create_stage(job_id, "test", "rel-v2")
    scan_file = stage_path / "scans" / "page_1.webp"
    scan_file.parent.mkdir(parents=True)
    scan_file.write_bytes(b"RIFFdummywebp")

    # Fault injection: process crashes or aborts after scans
    staging_mgr.cleanup_stage(job_id)

    # Current live release must still point to v1 without any partial v2 scans or files
    assert current_symlink.resolve() == v1_dir.resolve()
    assert (current_symlink / "manifest.json").read_text() == '{"version": "1.0", "slug": "test"}'
    assert not (v1_dir / "scans" / "page_1.webp").exists()

def test_failure_during_validation_leaves_live_library_untouched(tmp_path):
    from ingestion_service.release.staging import StagingManager
    from ingestion_service.release.promoter import ReleasePromoter
    from ingestion_service.release.validator import ReleaseValidationError

    releases_dir = tmp_path / "releases"
    staging_dir = tmp_path / "staging"
    current_symlink = tmp_path / "current"

    v1_dir = releases_dir / "rel-v1"
    v1_dir.mkdir(parents=True)
    (v1_dir / "manifest.json").write_text('{"version": "1.0"}')
    current_symlink.symlink_to(v1_dir)

    staging_mgr = StagingManager(staging_dir)
    promoter = ReleasePromoter(releases_dir, current_symlink, staging_mgr)

    # Stage invalid release: manifest references page 2 scan, but page 2 scan is missing!
    job_id = "job-invalid-stage"
    stage_path = staging_mgr.create_stage(job_id, "test", "rel-v2")
    staging_mgr.stage_manifest(job_id, {
        "schemaVersion": "2.0",
        "slug": "test",
        "pageRange": {"start": 1, "end": 2},
        "pages": [
            {"pageNumber": 1, "imageSrc": "/scans/test/page_1.webp"},
            {"pageNumber": 2, "imageSrc": "/scans/test/page_2.webp"}
        ]
    })
    # Only supply page 1 scan
    p1 = stage_path / "scans" / "test" / "page_1.webp"
    p1.parent.mkdir(parents=True, exist_ok=True)
    p1.write_bytes(b"WEBP1")
    staging_mgr.compute_checksums(job_id)

    # Promotion must fail validation and abort before altering live pointer
    with pytest.raises(ReleaseValidationError):
        promoter.promote(job_id, "test", "rel-v2", lease_checker=lambda: True)

    assert current_symlink.resolve() == v1_dir.resolve()

def test_stale_lease_holder_cannot_promote_release(tmp_path):
    from ingestion_service.release.staging import StagingManager
    from ingestion_service.release.promoter import ReleasePromoter
    from ingestion_service.jobs.repository import StaleLeaseError

    releases_dir = tmp_path / "releases"
    staging_dir = tmp_path / "staging"
    current_symlink = tmp_path / "current"
    releases_dir.mkdir(parents=True)

    staging_mgr = StagingManager(staging_dir)
    promoter = ReleasePromoter(releases_dir, current_symlink, staging_mgr)

    job_id = "job-stale-promoter"
    stage_path = staging_mgr.create_stage(job_id, "test", "rel-stale")
    staging_mgr.stage_manifest(job_id, {
        "schemaVersion": "2.0",
        "slug": "test",
        "pageRange": {"start": 1, "end": 1},
        "pages": [{"pageNumber": 1, "imageSrc": "/scans/test/page_1.webp"}]
    })
    p1 = stage_path / "scans" / "test" / "page_1.webp"
    p1.parent.mkdir(parents=True, exist_ok=True)
    p1.write_bytes(b"WEBP1")
    staging_mgr.compute_checksums(job_id)

    # Fake lease checker returning False (lease expired or hijacked)
    def stale_lease_checker():
        return False

    with pytest.raises(StaleLeaseError):
        promoter.promote(job_id, "test", "rel-stale", lease_checker=stale_lease_checker)

def test_atomic_promotion_and_rollback_pointer(tmp_path):
    from ingestion_service.release.staging import StagingManager
    from ingestion_service.release.promoter import ReleasePromoter

    releases_dir = tmp_path / "releases"
    staging_dir = tmp_path / "staging"
    current_symlink = tmp_path / "current"

    staging_mgr = StagingManager(staging_dir)
    # Initial release v1 must itself be checksum-valid: rollback never points
    # at an unverified historical directory.
    initial_stage = staging_mgr.create_stage("job-initial", "test", "rel-v1")
    staging_mgr.stage_manifest("job-initial", {
        "schemaVersion": "2.0",
        "slug": "test",
        "pageRange": {"start": 1, "end": 1},
        "pages": [{"pageNumber": 1, "imageSrc": "/scans/test/page_1.webp"}],
    })
    initial_scan = initial_stage / "scans" / "test" / "page_1.webp"
    initial_scan.parent.mkdir(parents=True, exist_ok=True)
    initial_scan.write_bytes(b"WEBP0")
    staging_mgr.compute_checksums("job-initial")
    v1_dir = releases_dir / "rel-v1"
    releases_dir.mkdir(parents=True)
    initial_stage.rename(v1_dir)
    current_symlink.symlink_to(v1_dir)

    promoter = ReleasePromoter(releases_dir, current_symlink, staging_mgr)

    # Stage valid v2
    job_id = "job-v2"
    stage_path = staging_mgr.create_stage(job_id, "test", "rel-v2")
    staging_mgr.stage_manifest(job_id, {
        "schemaVersion": "2.0",
        "slug": "test",
        "pageRange": {"start": 1, "end": 1},
        "pages": [{"pageNumber": 1, "imageSrc": "/scans/test/page_1.webp"}]
    })
    p1 = stage_path / "scans" / "test" / "page_1.webp"
    p1.parent.mkdir(parents=True, exist_ok=True)
    p1.write_bytes(b"WEBP1")
    staging_mgr.compute_checksums(job_id)

    promoted_path = promoter.promote(job_id, "test", "rel-v2", lease_checker=lambda: True)
    assert promoted_path.exists()
    assert current_symlink.resolve() == promoted_path.resolve()

    # Verify rollback pointer exists
    previous_symlink = tmp_path / "previous"
    assert previous_symlink.resolve() == v1_dir.resolve()

    # Rollback to v1
    rolled_back = promoter.rollback()
    assert rolled_back is True
    assert current_symlink.resolve() == v1_dir.resolve()

def test_concurrent_same_slug_promotion_is_serialized(tmp_path):
    import threading
    from ingestion_service.release.staging import StagingManager
    from ingestion_service.release.promoter import ReleasePromoter

    releases_dir = tmp_path / "releases"
    staging_dir = tmp_path / "staging"
    current_symlink = tmp_path / "current"

    v1_dir = releases_dir / "rel-v1"
    v1_dir.mkdir(parents=True)
    (v1_dir / "manifest.json").write_text('{"version": "1.0"}')
    current_symlink.symlink_to(v1_dir)

    staging_mgr = StagingManager(staging_dir)
    promoter_a = ReleasePromoter(releases_dir, current_symlink, staging_mgr)
    promoter_b = ReleasePromoter(releases_dir, current_symlink, staging_mgr)

    # Prepare two releases
    for job_id, rel_id in [("job-c1", "rel-c1"), ("job-c2", "rel-c2")]:
        stage_path = staging_mgr.create_stage(job_id, "same-slug", rel_id)
        staging_mgr.stage_manifest(job_id, {
            "schemaVersion": "2.0",
            "slug": "same-slug",
            "pageRange": {"start": 1, "end": 1},
            "pages": [{"pageNumber": 1, "imageSrc": f"/scans/same-slug/page_{job_id}.webp"}]
        })
        p = stage_path / "scans" / "same-slug" / f"page_{job_id}.webp"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"WEBP")
        staging_mgr.compute_checksums(job_id)

    errors = []
    def do_promote(promoter, job_id, rel_id):
        try:
            promoter.promote(job_id, "same-slug", rel_id, lease_checker=lambda: True)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=do_promote, args=(promoter_a, "job-c1", "rel-c1"))
    t2 = threading.Thread(target=do_promote, args=(promoter_b, "job-c2", "rel-c2"))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(errors) == 0
    assert current_symlink.exists()
    assert current_symlink.resolve() in ((releases_dir / "rel-c1").resolve(), (releases_dir / "rel-c2").resolve())


def test_release_identifiers_and_manifest_paths_are_contained(tmp_path):
    from ingestion_service.release.paths import ReleasePathError
    from ingestion_service.release.staging import StagingManager
    from ingestion_service.release.validator import ReleaseValidationError, ReleaseValidator

    staging_mgr = StagingManager(tmp_path / "staging")
    with pytest.raises(ReleasePathError):
        staging_mgr.create_stage("../escape", "safe-book", "rel-safe")
    with pytest.raises(ReleasePathError):
        staging_mgr.create_stage("job-safe", "Unsafe Book", "rel-safe")
    with pytest.raises(ReleasePathError):
        staging_mgr.create_stage("job-safe", "safe-book", "../rel-escape")

    stage_path = staging_mgr.create_stage("job-safe", "safe-book", "rel-safe")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    (stage_path / "manifest.json").write_text("{}", encoding="utf-8")
    checksums = {
        "release_id": "rel-safe",
        "job_id": "job-safe",
        "slug": "safe-book",
        "created_at": "2026-01-01T00:00:00+00:00",
        "files": [{"path": "../outside.bin", "sha256": "0" * 64, "byte_size": 7}],
    }
    import json
    (stage_path / "checksums.json").write_text(json.dumps(checksums), encoding="utf-8")
    with pytest.raises(ReleaseValidationError, match="escapes root|not allowed"):
        ReleaseValidator().validate_staged_release(stage_path)

    checksums["files"][0]["path"] = str(outside)
    (stage_path / "checksums.json").write_text(json.dumps(checksums), encoding="utf-8")
    with pytest.raises(ReleaseValidationError, match="Absolute release path|escapes root"):
        ReleaseValidator().validate_staged_release(stage_path)


def test_validator_rejects_unlisted_regular_files(tmp_path):
    import hashlib
    import json
    from ingestion_service.release.staging import StagingManager
    from ingestion_service.release.validator import ReleaseValidationError, ReleaseValidator

    staging_mgr = StagingManager(tmp_path / "staging")
    stage_path = staging_mgr.create_stage("job-extra", "safe-book", "rel-extra")
    manifest_path = staging_mgr.stage_manifest("job-extra", {"pages": []})
    extra_path = stage_path / "extra.txt"
    extra_path.write_text("not represented in checksums", encoding="utf-8")
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    checksums = {
        "release_id": "rel-extra",
        "job_id": "job-extra",
        "slug": "safe-book",
        "created_at": "2026-01-01T00:00:00+00:00",
        "files": [{
            "path": "manifest.json",
            "sha256": manifest_hash,
            "byte_size": manifest_path.stat().st_size,
        }],
    }
    (stage_path / "checksums.json").write_text(json.dumps(checksums), encoding="utf-8")

    with pytest.raises(ReleaseValidationError, match="Unlisted files.*extra.txt"):
        ReleaseValidator().validate_staged_release(stage_path)


def test_symlink_in_staging_is_rejected(tmp_path):
    from ingestion_service.release.paths import ReleasePathError
    from ingestion_service.release.staging import StagingManager

    staging_mgr = StagingManager(tmp_path / "staging")
    stage_path = staging_mgr.create_stage("job-symlink", "safe-book", "rel-safe")
    target = tmp_path / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    (stage_path / "leak.txt").symlink_to(target)

    with pytest.raises(ReleasePathError, match="Symlink"):
        staging_mgr.compute_checksums("job-symlink")


def test_existing_release_is_never_deleted_or_replaced(tmp_path):
    from ingestion_service.release.promoter import ReleaseAlreadyExistsError, ReleasePromoter
    from ingestion_service.release.staging import StagingManager

    releases_dir = tmp_path / "releases"
    staging_mgr = StagingManager(tmp_path / "staging")
    promoter = ReleasePromoter(releases_dir, tmp_path / "current", staging_mgr)
    stage_path = staging_mgr.create_stage("job-existing", "safe-book", "rel-existing")
    staging_mgr.stage_manifest("job-existing", {
        "schemaVersion": "2.0",
        "slug": "safe-book",
        "pageRange": {"start": 1, "end": 1},
        "pages": [{"pageNumber": 1, "imageSrc": "/scans/safe-book/page_1.webp"}],
    })
    scan_path = stage_path / "scans" / "safe-book" / "page_1.webp"
    scan_path.parent.mkdir(parents=True, exist_ok=True)
    scan_path.write_bytes(b"candidate")
    staging_mgr.compute_checksums("job-existing")

    existing = releases_dir / "rel-existing"
    existing.mkdir()
    sentinel = existing / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(ReleaseAlreadyExistsError):
        promoter.promote("job-existing", "safe-book", "rel-existing", lease_checker=lambda: True)
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "current").exists()


def test_promotion_requires_a_lease_checker(tmp_path):
    from ingestion_service.release.promoter import ReleasePromoter
    from ingestion_service.release.staging import StagingManager

    promoter = ReleasePromoter(tmp_path / "releases", tmp_path / "current", StagingManager(tmp_path / "staging"))
    with pytest.raises(TypeError):
        promoter.promote("job", "safe-book", "rel-safe")
    with pytest.raises(TypeError):
        promoter.promote("job", "safe-book", "rel-safe", lease_checker=None)


def test_rollback_pointer_failure_is_not_suppressed(tmp_path):
    from ingestion_service.release.promoter import ReleasePromotionError, ReleasePromoter
    from ingestion_service.release.staging import StagingManager

    releases_dir = tmp_path / "releases"
    v1_dir = releases_dir / "rel-v1"
    v1_dir.mkdir(parents=True)
    current = tmp_path / "current"
    current.symlink_to(v1_dir)
    (tmp_path / "previous").mkdir()

    staging_mgr = StagingManager(tmp_path / "staging")
    promoter = ReleasePromoter(releases_dir, current, staging_mgr)
    stage_path = staging_mgr.create_stage("job-pointer-fail", "safe-book", "rel-v2")
    staging_mgr.stage_manifest("job-pointer-fail", {
        "schemaVersion": "2.0",
        "slug": "safe-book",
        "pageRange": {"start": 1, "end": 1},
        "pages": [{"pageNumber": 1, "imageSrc": "/scans/safe-book/page_1.webp"}],
    })
    scan_path = stage_path / "scans" / "safe-book" / "page_1.webp"
    scan_path.parent.mkdir(parents=True, exist_ok=True)
    scan_path.write_bytes(b"candidate")
    staging_mgr.compute_checksums("job-pointer-fail")

    with pytest.raises((ReleasePromotionError, OSError)):
        promoter.promote("job-pointer-fail", "safe-book", "rel-v2", lease_checker=lambda: True)
    assert current.resolve() == v1_dir.resolve()


def test_promotion_lock_rejects_symlink_without_touching_target(tmp_path):
    from ingestion_service.release.paths import ReleasePathError
    from ingestion_service.release.promoter import ReleasePromoter
    from ingestion_service.release.staging import StagingManager

    releases_dir = tmp_path / "releases"
    releases_dir.mkdir()
    outside_lock = tmp_path / "outside.lock"
    outside_lock.write_bytes(b"sentinel")
    (releases_dir / ".promotion.lock").symlink_to(outside_lock)

    promoter = ReleasePromoter(
        releases_dir,
        tmp_path / "current",
        StagingManager(tmp_path / "staging"),
    )
    with pytest.raises(ReleasePathError, match="Promotion lock cannot be a symlink"):
        promoter.rollback()
    assert outside_lock.read_bytes() == b"sentinel"


def test_validator_rejects_invalid_manifest_contracts(tmp_path):
    import json
    from ingestion_service.release.staging import StagingManager
    from ingestion_service.release.validator import ReleaseValidationError, ReleaseValidator

    cases = [
        (
            "wrong-schema",
            {"schemaVersion": "1.0", "slug": "safe-book", "pageRange": {"start": 1, "end": 1},
             "pages": [{"pageNumber": 1, "imageSrc": "/scans/safe-book/page_1.webp"}]},
            "schemaVersion",
        ),
        (
            "slug-mismatch",
            {"schemaVersion": "2.0", "slug": "other-book", "pageRange": {"start": 1, "end": 1},
             "pages": [{"pageNumber": 1, "imageSrc": "/scans/safe-book/page_1.webp"}]},
            "slug mismatch",
        ),
        (
            "bad-range",
            {"schemaVersion": "2.0", "slug": "safe-book", "pageRange": {"start": 2, "end": 3},
             "pages": [{"pageNumber": 1, "imageSrc": "/scans/safe-book/page_1.webp"}]},
            "pageRange",
        ),
        (
            "empty-pages",
            {"schemaVersion": "2.0", "slug": "safe-book", "pageRange": {"start": 1, "end": 1},
             "pages": []},
            "pages must be a list",
        ),
        (
            "missing-image",
            {"schemaVersion": "2.0", "slug": "safe-book", "pageRange": {"start": 1, "end": 1},
             "pages": [{"pageNumber": 1, "imageSrc": "/scans/safe-book/missing.webp"}]},
            "does not exist",
        ),
    ]

    for index, (job_suffix, manifest, message) in enumerate(cases):
        staging_mgr = StagingManager(tmp_path / f"staging-{index}")
        job_id = f"job-{job_suffix}"
        stage_path = staging_mgr.create_stage(job_id, "safe-book", f"rel-{job_suffix}")
        staging_mgr.stage_manifest(job_id, manifest)
        if job_suffix != "missing-image":
            scan_path = stage_path / "scans" / "safe-book" / "page_1.webp"
            scan_path.parent.mkdir(parents=True, exist_ok=True)
            scan_path.write_bytes(b"WEBP")
        staging_mgr.compute_checksums(job_id)

        with pytest.raises(ReleaseValidationError, match=message):
            ReleaseValidator().validate_staged_release(stage_path)


def test_validator_rejects_image_not_in_checksums(tmp_path):
    import json
    from ingestion_service.release.staging import StagingManager
    from ingestion_service.release.validator import ReleaseValidationError, ReleaseValidator

    staging_mgr = StagingManager(tmp_path / "staging")
    job_id = "job-unchecked-image"
    stage_path = staging_mgr.create_stage(job_id, "safe-book", "rel-unchecked-image")
    staging_mgr.stage_manifest(job_id, {
        "schemaVersion": "2.0",
        "slug": "safe-book",
        "pageRange": {"start": 1, "end": 1},
        "pages": [{"pageNumber": 1, "imageSrc": "/scans/safe-book/page_1.webp"}],
    })
    scan_path = stage_path / "scans" / "safe-book" / "page_1.webp"
    scan_path.parent.mkdir(parents=True, exist_ok=True)
    scan_path.write_bytes(b"WEBP")
    staging_mgr.compute_checksums(job_id)

    checksums_path = stage_path / "checksums.json"
    checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
    checksums["files"] = [entry for entry in checksums["files"] if entry["path"] != "scans/safe-book/page_1.webp"]
    checksums_path.write_text(json.dumps(checksums), encoding="utf-8")

    with pytest.raises(ReleaseValidationError, match="Unlisted files.*page_1.webp"):
        ReleaseValidator().validate_staged_release(stage_path)
