import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import fitz

from .models import SourceDocumentRecord


class SourceRepository:
    def __init__(self, storage_dir: Path | str):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def calculate_sha256(self, file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def store_source(self, input_path: Path | str) -> SourceDocumentRecord:
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {path}")

        sha256 = self.calculate_sha256(path)
        target_path = self.storage_dir / f"{sha256}.pdf"

        if not target_path.exists():
            shutil.copy2(path, target_path)
            try:
                # Make immutable (read-only)
                os.chmod(target_path, 0o444)
            except Exception:
                pass

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
        target_path = self.storage_dir / f"{sha256}.pdf"
        if not target_path.exists():
            return None

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
