import hashlib
import json
from pathlib import Path

from .models import ReleaseManifest


class ReleaseValidationError(Exception):
    """Raised when staged release fails integrity, checksum, or asset completeness checks."""
    pass


class ReleaseValidator:
    def validate_staged_release(self, stage_path: Path) -> ReleaseManifest:
        checksums_file = stage_path / "checksums.json"
        if not checksums_file.exists():
            raise ReleaseValidationError("Missing checksums.json in staged release")

        with open(checksums_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                manifest = ReleaseManifest.model_validate(data)
            except Exception as e:
                raise ReleaseValidationError(f"Invalid checksums.json schema: {e}")

        # 1. Verify all checksums match disk
        for entry in manifest.files:
            file_path = stage_path / entry.path
            if not file_path.exists():
                raise ReleaseValidationError(f"File listed in checksums not found: {entry.path}")

            if file_path.stat().st_size != entry.byte_size:
                raise ReleaseValidationError(
                    f"Size mismatch for {entry.path}: expected {entry.byte_size}, got {file_path.stat().st_size}"
                )

            h = hashlib.sha256()
            with open(file_path, "rb") as f_in:
                for chunk in iter(lambda: f_in.read(65536), b""):
                    h.update(chunk)
            if h.hexdigest() != entry.sha256:
                raise ReleaseValidationError(f"Checksum mismatch for {entry.path}")

        # 2. Verify manifest scan completeness
        manifest_file = stage_path / "manifest.json"
        if not manifest_file.exists():
            raise ReleaseValidationError("Missing manifest.json in staged release")

        with open(manifest_file, "r", encoding="utf-8") as f:
            try:
                m_data = json.load(f)
            except Exception as e:
                raise ReleaseValidationError(f"Corrupt manifest.json: {e}")

        pages = m_data.get("pages", [])
        for p in pages:
            img = p.get("imageSrc", "")
            if img:
                scan_name = Path(img).name
                candidate1 = stage_path / "scans" / scan_name
                candidate2 = stage_path / img.lstrip("/")
                if not candidate1.exists() and not candidate2.exists():
                    raise ReleaseValidationError(
                        f"Referenced scan '{img}' does not exist in release"
                    )

        return manifest
