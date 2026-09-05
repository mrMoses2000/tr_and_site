import hashlib
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
import fitz

from .models import SourceDocumentRecord


class SourceRepository:
    def __init__(
        self,
        storage_dir: Path | str,
        allowed_source_roots: Iterable[Path | str] | None = None,
    ):
        self.storage_dir = Path(storage_dir)
        if self.storage_dir.is_symlink():
            raise ValueError(f"Storage directory must not be a symlink: {self.storage_dir}")
        if self.storage_dir.exists() and not self.storage_dir.is_dir():
            raise ValueError(f"Storage path is not a directory: {self.storage_dir}")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        # Callers must opt in to every directory from which owner-provided
        # source files may be read.  A storage directory is not an input root.
        self.allowed_source_roots = tuple(
            Path(root).resolve() for root in (allowed_source_roots or ())
        )

    def _resolve_allowed_source(self, input_path: Path | str) -> Path:
        path = Path(input_path)
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            raise FileNotFoundError(f"Source file not found: {path}")

        if not resolved.is_file():
            raise ValueError(f"Source path is not a regular file: {path}")
        if not self.allowed_source_roots:
            raise ValueError("No allowed source roots configured")
        if not any(resolved.is_relative_to(root) for root in self.allowed_source_roots):
            raise ValueError(f"Source path is outside configured source roots: {path}")
        return resolved

    def calculate_sha256(self, file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def store_source(self, input_path: Path | str) -> SourceDocumentRecord:
        path = self._resolve_allowed_source(input_path)

        source_hash_before = self.calculate_sha256(path)
        target_path = self.storage_dir / f"{source_hash_before}.pdf"

        if target_path.is_symlink() or (target_path.exists() and not target_path.is_file()):
            raise ValueError(f"CAS target must be a regular file: {target_path.name}")

        if target_path.exists():
            target_hash = self.calculate_sha256(target_path)
            if target_hash != source_hash_before:
                raise ValueError(
                    f"Existing content-addressed source has a hash mismatch: {target_path.name}"
                )
        else:
            # Copy to a same-directory temporary file so a partially copied
            # source can never become the addressable artifact.
            tmp_name: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=self.storage_dir,
                    prefix=f".{source_hash_before}.",
                    suffix=".tmp",
                    delete=False,
                ) as tmp:
                    tmp_name = tmp.name
                shutil.copy2(path, tmp_name)
                copied_hash = self.calculate_sha256(Path(tmp_name))
                source_hash_after = self.calculate_sha256(path)
                if copied_hash != source_hash_before or source_hash_after != source_hash_before:
                    raise ValueError("Source changed or copy hash verification failed")
                try:
                    # A hard link is an atomic create-if-absent operation on
                    # the same filesystem.  Unlike os.replace, it cannot
                    # overwrite an object published by a racing writer.
                    os.link(tmp_name, target_path)
                except FileExistsError:
                    if target_path.is_symlink() or not target_path.is_file():
                        raise ValueError(f"CAS target must be a regular file: {target_path.name}")
                    if self.calculate_sha256(target_path) != source_hash_before:
                        raise ValueError(
                            f"Concurrent CAS object has a hash mismatch: {target_path.name}"
                        )
                if self.calculate_sha256(target_path) != source_hash_before:
                    raise ValueError("Content-addressed source hash verification failed")
                os.chmod(target_path, 0o444)
            finally:
                if tmp_name:
                    try:
                        Path(tmp_name).unlink()
                    except FileNotFoundError:
                        pass

        sha256 = self.calculate_sha256(target_path)
        if sha256 != source_hash_before:
            raise ValueError("Content-addressed source hash verification failed")

        doc = fitz.open(str(target_path))
        page_count = len(doc)
        doc.close()

        byte_size = target_path.stat().st_size
        now_iso = datetime.now(timezone.utc).isoformat()

        return SourceDocumentRecord(
            sha256=sha256,
            original_filename=path.name,
            storage_path=str(target_path),
            byte_size=byte_size,
            page_count=page_count,
            created_at=now_iso,
            status="STORED",
        )

    def get_by_sha256(self, sha256: str) -> Optional[SourceDocumentRecord]:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
            return None
        target_path = self.storage_dir / f"{sha256}.pdf"
        if target_path.is_symlink() or (target_path.exists() and not target_path.is_file()):
            raise ValueError(f"CAS target must be a regular file: {target_path.name}")
        if not target_path.exists():
            return None

        if self.calculate_sha256(target_path).lower() != sha256.lower():
            raise ValueError(f"Stored source hash verification failed: {target_path.name}")

        doc = fitz.open(str(target_path))
        page_count = len(doc)
        doc.close()

        return SourceDocumentRecord(
            sha256=sha256,
            original_filename=target_path.name,
            storage_path=str(target_path),
            byte_size=target_path.stat().st_size,
            page_count=page_count,
            created_at=datetime.now(timezone.utc).isoformat(),
            status="STORED",
        )
