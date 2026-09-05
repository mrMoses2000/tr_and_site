import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .models import ChecksumEntry, ReleaseManifest
from .paths import ReleasePathError, resolve_contained_path, validate_component


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class StagingManager:
    def __init__(self, staging_base_dir: Path | str):
        self.staging_base_dir = Path(staging_base_dir)
        if self.staging_base_dir.exists() and self.staging_base_dir.is_symlink():
            raise ReleasePathError(f"Staging base directory cannot be a symlink: {self.staging_base_dir}")
        self.staging_base_dir.mkdir(parents=True, exist_ok=True)
        if not self.staging_base_dir.is_dir():
            raise ReleasePathError(f"Staging base directory is not a directory: {self.staging_base_dir}")
        self.staging_base_dir = self.staging_base_dir.resolve(strict=True)

    def get_stage_path(self, job_id: str) -> Path:
        validate_component(job_id, "job_id")
        return resolve_contained_path(self.staging_base_dir, job_id)

    def create_stage(self, job_id: str, slug: str, release_id: str) -> Path:
        stage_path = self.get_stage_path(job_id)
        validate_component(slug, "slug", slug=True)
        validate_component(release_id, "release_id")
        if stage_path.exists() or stage_path.is_symlink():
            raise FileExistsError(f"Staging directory already exists: {stage_path}")
        stage_path.mkdir(parents=True, exist_ok=False)
        # Store metadata
        meta = {"job_id": job_id, "slug": slug, "release_id": release_id}
        with open(stage_path / ".stage_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f)
        return stage_path

    def stage_manifest(self, job_id: str, manifest_data: Dict[str, Any]) -> Path:
        stage_path = self.get_stage_path(job_id)
        manifest_file = resolve_contained_path(stage_path, "manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=2)
        return manifest_file

    def compute_checksums(self, job_id: str) -> ReleaseManifest:
        stage_path = self.get_stage_path(job_id)
        entries = []

        meta_file = stage_path / ".stage_meta.json"
        meta = {}
        if meta_file.exists() and meta_file.is_symlink():
            raise ReleasePathError(".stage_meta.json cannot be a symlink")
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

        for p in sorted(stage_path.rglob("*")):
            if p.is_symlink():
                raise ReleasePathError(f"Symlink in staged release is not allowed: {p}")
            rel = p.relative_to(stage_path)
            if p.is_file() and str(rel) not in ("checksums.json", ".stage_meta.json"):
                rel = str(rel)
                c_hash = sha256_file(p)
                size = p.stat().st_size
                entries.append(ChecksumEntry(path=rel, sha256=c_hash, byte_size=size))

        now_iso = datetime.now(timezone.utc).isoformat()
        rel_manifest = ReleaseManifest(
            release_id=meta.get("release_id", f"rel-{job_id}"),
            job_id=job_id,
            slug=meta.get("slug", "book"),
            created_at=now_iso,
            files=entries,
        )

        with open(stage_path / "checksums.json", "w", encoding="utf-8") as f:
            json.dump(rel_manifest.model_dump(), f, ensure_ascii=False, indent=2)

        return rel_manifest

    def cleanup_stage(self, job_id: str):
        stage_path = self.get_stage_path(job_id)
        if stage_path.is_symlink():
            raise ReleasePathError(f"Staging directory cannot be a symlink: {stage_path}")
        if stage_path.exists():
            shutil.rmtree(stage_path)
