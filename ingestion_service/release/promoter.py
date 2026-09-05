import errno
import fcntl
import os
import shutil
import stat
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Optional

from ingestion_service.jobs.repository import StaleLeaseError
from .paths import ReleasePathError, ensure_no_symlinks, validate_component
from .staging import StagingManager
from .validator import ReleaseValidator


class ReleasePromotionError(RuntimeError):
    """Raised when a release cannot be promoted safely."""


class ReleaseAlreadyExistsError(ReleasePromotionError):
    """Raised instead of replacing an immutable release directory."""


class ReleasePromoter:
    """
    Validates and promotes immutable releases under both thread and process locks.

    The lease checker is deliberately mandatory: a caller must prove ownership
    of the job immediately before any publication side effect.
    """

    def __init__(
        self,
        releases_dir: Path | str,
        current_pointer_path: Path | str,
        staging_mgr: StagingManager,
        validator: Optional[ReleaseValidator] = None,
    ):
        self.releases_dir = Path(releases_dir)
        if self.releases_dir.exists() and self.releases_dir.is_symlink():
            raise ReleasePathError(f"Releases directory cannot be a symlink: {self.releases_dir}")
        self.releases_dir.mkdir(parents=True, exist_ok=True)
        if not self.releases_dir.is_dir():
            raise ReleasePathError(f"Releases path is not a directory: {self.releases_dir}")
        self.releases_dir = self.releases_dir.resolve(strict=True)

        self.current_pointer_path = Path(current_pointer_path)
        self._validate_pointer_parent()
        self.staging_mgr = staging_mgr
        self.validator = validator or ReleaseValidator()
        self._lock = threading.Lock()
        self._process_lock_path = self.releases_dir / ".promotion.lock"

    def _validate_pointer_parent(self) -> None:
        parent = self.current_pointer_path.parent
        if parent.exists() and parent.is_symlink():
            raise ReleasePathError(f"Pointer parent cannot be a symlink: {parent}")
        parent.mkdir(parents=True, exist_ok=True)
        if not parent.is_dir():
            raise ReleasePathError(f"Pointer parent is not a directory: {parent}")

    @contextmanager
    def _promotion_lock(self) -> Iterator[None]:
        """Coordinate promotions from multiple threads and Python processes."""
        with self._lock:
            try:
                fd = os.open(
                    self._process_lock_path,
                    os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                    0o600,
                )
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise ReleasePathError(
                        f"Promotion lock cannot be a symlink: {self._process_lock_path}"
                    ) from exc
                raise

            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise ReleasePathError(
                        f"Promotion lock must be a regular file: {self._process_lock_path}"
                    )
                lock_file = os.fdopen(fd, "a+", encoding="ascii")
            except Exception:
                os.close(fd)
                raise

            with lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _assert_lease(lease_checker: Callable[[], bool]) -> None:
        if not callable(lease_checker):
            raise TypeError("lease_checker must be callable and is required for promotion")
        if not lease_checker():
            raise StaleLeaseError("Worker lease is expired or hijacked; cannot promote release.")

    def _existing_pointer_target(self, pointer: Path) -> Optional[Path]:
        if not os.path.lexists(pointer):
            return None
        if not pointer.is_symlink():
            raise ReleasePromotionError(f"Release pointer is not a symlink: {pointer}")
        try:
            target = pointer.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ReleasePromotionError(f"Release pointer target is invalid: {pointer}") from exc
        try:
            target.relative_to(self.releases_dir)
        except ValueError as exc:
            raise ReleasePromotionError(f"Release pointer escapes releases directory: {pointer}") from exc
        if target == self.releases_dir or not target.is_dir() or target.is_symlink():
            raise ReleasePromotionError(f"Release pointer target is not a directory: {target}")
        return target

    def promote(
        self,
        job_id: str,
        slug: str,
        release_id: str,
        lease_checker: Callable[[], bool],
    ) -> Path:
        validate_component(job_id, "job_id")
        validate_component(slug, "slug", slug=True)
        validate_component(release_id, "release_id")

        with self._promotion_lock():
            # Check before validation and again immediately before publication.
            self._assert_lease(lease_checker)

            stage_path = self.staging_mgr.get_stage_path(job_id)
            manifest = self.validator.validate_staged_release(stage_path)

            if manifest.job_id != job_id:
                raise ReleasePromotionError(
                    f"Staged manifest job_id mismatch: expected {job_id!r}, got {manifest.job_id!r}"
                )
            if manifest.slug != slug:
                raise ReleasePromotionError(
                    f"Staged manifest slug mismatch: expected {slug!r}, got {manifest.slug!r}"
                )
            if manifest.release_id != release_id:
                raise ReleasePromotionError(
                    f"Staged manifest release_id mismatch: expected {release_id!r}, got {manifest.release_id!r}"
                )

            target_release = self.releases_dir / release_id
            if os.path.lexists(target_release):
                raise ReleaseAlreadyExistsError(f"Immutable release already exists: {release_id}")

            # Copy to a private temporary directory. It is not reachable through
            # the public pointer until the complete candidate has been checked.
            temp_release = self.releases_dir / f".{release_id}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
            if os.path.lexists(temp_release):
                raise ReleasePromotionError(f"Temporary release path already exists: {temp_release}")
            temp_created = False
            try:
                temp_created = True
                shutil.copytree(stage_path, temp_release, symlinks=True)
                ensure_no_symlinks(temp_release)
                self._assert_lease(lease_checker)
                if os.path.lexists(target_release):
                    raise ReleaseAlreadyExistsError(f"Immutable release already exists: {release_id}")
                os.replace(temp_release, target_release)
            except Exception:
                if temp_created and os.path.lexists(temp_release):
                    shutil.rmtree(temp_release)
                raise

            # Pointer failures intentionally propagate. A partially promoted
            # immutable candidate is safer than silently hiding rollback damage.
            self._atomic_pointer_switch(target_release)
            self.staging_mgr.cleanup_stage(job_id)
            return target_release

    def _atomic_pointer_switch(self, new_target: Path) -> None:
        if new_target.is_symlink() or not new_target.is_dir():
            raise ReleasePromotionError(f"New release target is not a directory: {new_target}")
        try:
            new_target.resolve(strict=True).relative_to(self.releases_dir)
        except (OSError, ValueError) as exc:
            raise ReleasePromotionError("New release target escapes releases directory") from exc

        parent_dir = self.current_pointer_path.parent
        self._validate_pointer_parent()
        previous_symlink = parent_dir / "previous"
        old_target = self._existing_pointer_target(self.current_pointer_path)

        token = f"{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}"
        tmp_prev = parent_dir / f".previous.tmp.{token}"
        tmp_curr = parent_dir / f".current.tmp.{token}"
        prev_created = False
        curr_created = False
        try:
            if old_target is not None:
                tmp_prev.symlink_to(old_target)
                prev_created = True
                os.replace(tmp_prev, previous_symlink)

            tmp_curr.symlink_to(new_target)
            curr_created = True
            os.replace(tmp_curr, self.current_pointer_path)
        finally:
            # Only remove private names created by this invocation.
            if prev_created and os.path.lexists(tmp_prev):
                tmp_prev.unlink()
            if curr_created and os.path.lexists(tmp_curr):
                tmp_curr.unlink()

    def rollback(self) -> bool:
        with self._promotion_lock():
            parent_dir = self.current_pointer_path.parent
            previous_symlink = parent_dir / "previous"
            if not os.path.lexists(previous_symlink):
                return False
            if not previous_symlink.is_symlink():
                raise ReleasePromotionError(f"Rollback pointer is not a symlink: {previous_symlink}")

            prev_target = self._existing_pointer_target(previous_symlink)
            if prev_target is None:
                return False

            token = f"{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}"
            tmp_curr = parent_dir / f".current.rollback.tmp.{token}"
            curr_created = False
            try:
                tmp_curr.symlink_to(prev_target)
                curr_created = True
                os.replace(tmp_curr, self.current_pointer_path)
            finally:
                if curr_created and os.path.lexists(tmp_curr):
                    tmp_curr.unlink()
            return True
