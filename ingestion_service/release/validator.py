import hashlib
import json
from pathlib import Path

from .models import ReleaseManifest
from .paths import ReleasePathError, ensure_no_symlinks, iter_regular_files, resolve_contained_path


class ReleaseValidationError(Exception):
    """Raised when staged release fails integrity, checksum, or asset completeness checks."""
    pass


class ReleaseValidator:
    def validate_staged_release(self, stage_path: Path) -> ReleaseManifest:
        stage_path = Path(stage_path)
        if not stage_path.exists() or not stage_path.is_dir() or stage_path.is_symlink():
            raise ReleaseValidationError(f"Invalid staged release directory: {stage_path}")
        stage_path = stage_path.resolve(strict=True)
        try:
            ensure_no_symlinks(stage_path)
        except ReleasePathError as exc:
            raise ReleaseValidationError(str(exc)) from exc

        checksums_file = stage_path / "checksums.json"
        if not checksums_file.exists():
            raise ReleaseValidationError("Missing checksums.json in staged release")

        with open(checksums_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                manifest = ReleaseManifest.model_validate(data)
            except Exception as e:
                raise ReleaseValidationError(f"Invalid checksums.json schema: {e}")

        # 1. Verify all checksums match disk and every entry stays inside staging.
        seen_paths: set[str] = set()
        for entry in manifest.files:
            if entry.path in seen_paths:
                raise ReleaseValidationError(f"Duplicate file in checksums: {entry.path}")
            seen_paths.add(entry.path)
            try:
                file_path = resolve_contained_path(stage_path, entry.path)
            except ReleasePathError as exc:
                raise ReleaseValidationError(str(exc)) from exc
            if not file_path.exists() or not file_path.is_file():
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

        # The checksum manifest must be complete. Unlisted regular files would
        # otherwise be publishable without integrity verification.
        try:
            actual_paths = {
                str(path.relative_to(stage_path))
                for path in iter_regular_files(stage_path)
                if str(path.relative_to(stage_path)) not in ("checksums.json", ".stage_meta.json")
            }
        except ReleasePathError as exc:
            raise ReleaseValidationError(str(exc)) from exc
        unlisted_paths = actual_paths - seen_paths
        if unlisted_paths:
            raise ReleaseValidationError(
                f"Unlisted files in staged release: {', '.join(sorted(unlisted_paths))}"
            )

        # 2. Verify manifest scan completeness
        manifest_file = stage_path / "manifest.json"
        if not manifest_file.exists():
            raise ReleaseValidationError("Missing manifest.json in staged release")

        with open(manifest_file, "r", encoding="utf-8") as f:
            try:
                m_data = json.load(f)
            except Exception as e:
                raise ReleaseValidationError(f"Corrupt manifest.json: {e}")

        if not isinstance(m_data, dict):
            raise ReleaseValidationError("Invalid manifest.json schema: expected object")
        if m_data.get("schemaVersion") != "2.0":
            raise ReleaseValidationError("Invalid manifest.json schemaVersion: expected '2.0'")
        if m_data.get("slug") != manifest.slug:
            raise ReleaseValidationError(
                f"Manifest slug mismatch: expected {manifest.slug!r}, got {m_data.get('slug')!r}"
            )

        page_range = m_data.get("pageRange")
        if not isinstance(page_range, dict):
            raise ReleaseValidationError("Invalid manifest.json pageRange: expected object")
        start_page = page_range.get("start")
        end_page = page_range.get("end")
        if (
            isinstance(start_page, bool)
            or isinstance(end_page, bool)
            or not isinstance(start_page, int)
            or not isinstance(end_page, int)
            or start_page < 1
            or end_page < start_page
        ):
            raise ReleaseValidationError("Invalid manifest.json pageRange bounds")

        pages = m_data.get("pages", [])
        if not isinstance(pages, list) or not pages:
            raise ReleaseValidationError("Invalid manifest.json schema: pages must be a list")
        page_numbers: list[int] = []
        for p in pages:
            if not isinstance(p, dict):
                raise ReleaseValidationError("Invalid page entry in manifest.json")
            page_number = p.get("pageNumber")
            if isinstance(page_number, bool) or not isinstance(page_number, int):
                raise ReleaseValidationError("Invalid pageNumber in manifest.json")
            page_numbers.append(page_number)
            img = p.get("imageSrc", "")
            if img:
                try:
                    scan_path = resolve_contained_path(
                        stage_path,
                        img,
                        allow_leading_slash=True,
                    )
                except ReleasePathError as exc:
                    raise ReleaseValidationError(str(exc)) from exc
                if not scan_path.exists() or not scan_path.is_file():
                    raise ReleaseValidationError(
                        f"Referenced scan '{img}' does not exist in release"
                    )
                scan_rel = str(scan_path.relative_to(stage_path))
                if scan_rel not in seen_paths:
                    raise ReleaseValidationError(
                        f"Referenced scan '{img}' is missing from checksums"
                    )

        if len(set(page_numbers)) != len(page_numbers):
            raise ReleaseValidationError("Duplicate pageNumber in manifest.json")
        expected_pages = set(range(start_page, end_page + 1))
        if set(page_numbers) != expected_pages:
            raise ReleaseValidationError(
                "Manifest pageRange does not exactly match pages/pageNumber entries"
            )

        catalog_file = stage_path / "catalog.json"
        if catalog_file.exists():
            try:
                catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ReleaseValidationError(f"Invalid catalog.json: {exc}") from exc
            books = catalog.get("books") if isinstance(catalog, dict) else None
            if (
                not isinstance(catalog, dict)
                or str(catalog.get("schemaVersion")) not in ("1", "1.0")
                or not isinstance(books, list)
            ):
                raise ReleaseValidationError("Invalid catalog.json contract")
            catalog_slugs: set[str] = set()
            for book in books:
                if not isinstance(book, dict) or not isinstance(book.get("slug"), str):
                    raise ReleaseValidationError("Invalid book entry in catalog.json")
                slug = book["slug"]
                if slug in catalog_slugs:
                    raise ReleaseValidationError(f"Duplicate catalog book slug: {slug}")
                catalog_slugs.add(slug)
                if book.get("releaseManaged") is not True:
                    continue
                try:
                    book_manifest_path = resolve_contained_path(
                        stage_path, f"books/{slug}/manifest.json"
                    )
                except ReleasePathError as exc:
                    raise ReleaseValidationError(str(exc)) from exc
                if not book_manifest_path.is_file():
                    raise ReleaseValidationError(
                        f"Managed catalog book has no manifest: {slug}"
                    )
                try:
                    book_manifest = json.loads(book_manifest_path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    raise ReleaseValidationError(
                        f"Invalid managed book manifest for {slug}: {exc}"
                    ) from exc
                if not isinstance(book_manifest, dict) or book_manifest.get("slug") != slug:
                    raise ReleaseValidationError(
                        f"Managed book manifest slug mismatch: {slug}"
                    )
                if str(book_manifest_path.relative_to(stage_path)) not in seen_paths:
                    raise ReleaseValidationError(
                        f"Managed book manifest is missing from checksums: {slug}"
                    )

        return manifest
