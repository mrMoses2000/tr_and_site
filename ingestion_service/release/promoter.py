import os
import shutil
import threading
from pathlib import Path
from typing import Callable, Optional

from ingestion_service.jobs.repository import StaleLeaseError
from .staging import StagingManager
from .validator import ReleaseValidator


class ReleasePromoter:
    """
    Serializes release promotions, verifies worker lease validity,
    validates staged assets, copies to immutable release location,
    and atomically switches the current pointer symlink.
    """
    def __init__(
        self,
        releases_dir: Path | str,
        current_pointer_path: Path | str,
        staging_mgr: StagingManager,
        validator: Optional[ReleaseValidator] = None,
    ):
        self.releases_dir = Path(releases_dir)
        self.releases_dir.mkdir(parents=True, exist_ok=True)
        self.current_pointer_path = Path(current_pointer_path)
        self.staging_mgr = staging_mgr
        self.validator = validator or ReleaseValidator()
        self._lock = threading.Lock()

    def promote(
        self,
        job_id: str,
        slug: str,
        release_id: str,
        lease_checker: Optional[Callable[[], bool]] = None,
    ) -> Path:
        with self._lock:
            # 1. Stale worker lease check
            if lease_checker is not None:
                if not lease_checker():
                    raise StaleLeaseError("Worker lease is expired or hijacked; cannot promote release.")

            # 2. Validate staged release (checksums, manifest, scans)
            stage_path = self.staging_mgr.get_stage_path(job_id)
            self.validator.validate_staged_release(stage_path)

            # 3. Copy to immutable releases directory
            target_release = self.releases_dir / release_id
            if target_release.exists():
                shutil.rmtree(target_release)

            shutil.copytree(stage_path, target_release)

            # 4. Atomic symlink replacement with rollback pointer
            self._atomic_pointer_switch(target_release)

            # 5. Clean up staging area
            self.staging_mgr.cleanup_stage(job_id)

            return target_release

    def _atomic_pointer_switch(self, new_target: Path):
        parent_dir = self.current_pointer_path.parent
        parent_dir.mkdir(parents=True, exist_ok=True)
        previous_symlink = parent_dir / "previous"

        # Record current as previous before switching
        if self.current_pointer_path.exists() or self.current_pointer_path.is_symlink():
            try:
                old_target = self.current_pointer_path.resolve()
                tmp_prev = parent_dir / f".tmp_prev_{os.getpid()}"
                if tmp_prev.is_symlink() or tmp_prev.exists():
                    tmp_prev.unlink()
                tmp_prev.symlink_to(old_target)
                os.replace(tmp_prev, previous_symlink)
            except Exception:
                pass

        # Atomically switch current
        tmp_curr = parent_dir / f".tmp_curr_{os.getpid()}"
        if tmp_curr.is_symlink() or tmp_curr.exists():
            tmp_curr.unlink()
        tmp_curr.symlink_to(new_target)
        os.replace(tmp_curr, self.current_pointer_path)

    def rollback(self) -> bool:
        with self._lock:
            parent_dir = self.current_pointer_path.parent
            previous_symlink = parent_dir / "previous"
            if not previous_symlink.is_symlink() and not previous_symlink.exists():
                return False

            prev_target = previous_symlink.resolve()
            tmp_curr = parent_dir / f".tmp_roll_{os.getpid()}"
            if tmp_curr.is_symlink() or tmp_curr.exists():
                tmp_curr.unlink()
            tmp_curr.symlink_to(prev_target)
            os.replace(tmp_curr, self.current_pointer_path)
            return True
