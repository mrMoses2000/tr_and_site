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
    promoter = ReleasePromoter(releases_dir, current_symlink, staging_mgr)

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
    p1 = stage_path / "scans" / "page_1.webp"
    p1.parent.mkdir(parents=True, exist_ok=True)
    p1.write_bytes(b"WEBP1")
    staging_mgr.compute_checksums(job_id)

    # Promotion must fail validation and abort before altering live pointer
    with pytest.raises(ReleaseValidationError):
        promoter.promote(job_id, "test", "rel-v2")

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
    p1 = stage_path / "scans" / "page_1.webp"
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

    # Initial release v1
    v1_dir = releases_dir / "rel-v1"
    v1_dir.mkdir(parents=True)
    (v1_dir / "manifest.json").write_text('{"version": "1.0"}')
    current_symlink.symlink_to(v1_dir)

    staging_mgr = StagingManager(staging_dir)
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
    p1 = stage_path / "scans" / "page_1.webp"
    p1.parent.mkdir(parents=True, exist_ok=True)
    p1.write_bytes(b"WEBP1")
    staging_mgr.compute_checksums(job_id)

    promoted_path = promoter.promote(job_id, "test", "rel-v2")
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
    promoter = ReleasePromoter(releases_dir, current_symlink, staging_mgr)

    # Prepare two releases
    for job_id, rel_id in [("job-c1", "rel-c1"), ("job-c2", "rel-c2")]:
        stage_path = staging_mgr.create_stage(job_id, "same-slug", rel_id)
        staging_mgr.stage_manifest(job_id, {
            "schemaVersion": "2.0",
            "slug": "same-slug",
            "pageRange": {"start": 1, "end": 1},
            "pages": [{"pageNumber": 1, "imageSrc": f"/scans/same-slug/page_{job_id}.webp"}]
        })
        p = stage_path / "scans" / f"page_{job_id}.webp"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"WEBP")
        staging_mgr.compute_checksums(job_id)

    errors = []
    def do_promote(job_id, rel_id):
        try:
            promoter.promote(job_id, "same-slug", rel_id)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=do_promote, args=("job-c1", "rel-c1"))
    t2 = threading.Thread(target=do_promote, args=("job-c2", "rel-c2"))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(errors) == 0
    assert current_symlink.exists()
    assert current_symlink.resolve() in ((releases_dir / "rel-c1").resolve(), (releases_dir / "rel-c2").resolve())
