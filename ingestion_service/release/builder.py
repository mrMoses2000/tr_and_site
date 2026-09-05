"""Production release builder for immutable, per-job static artifacts.

The builder has no shared candidate slot and never writes the active checkout.
Each invocation gets a private workspace, assembles the reader there, runs the
frontend build and copies only the resulting static tree into the stage owned
by the caller's explicit :class:`PreparedRelease` handle.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from ..origin.health import HealthSnapshot, write_health_artifact
from ..publisher import build_manifest_data
from .adapter import ReleaseBuildError, ReleaseIdentity
from .paths import ReleasePathError, ensure_no_symlinks, resolve_contained_path, validate_component
from .validator import ReleaseValidator


BuildRunner = Callable[..., subprocess.CompletedProcess[str]]


def _copytree_ignore(_directory: str, names: list[str]) -> set[str]:
    """Keep job workspaces small and prevent source control metadata leakage."""
    ignored = {".git", "node_modules", "dist", "coverage", ".cache", ".vite"}
    return {name for name in names if name in ignored}


def _assert_symlink_targets_contained(root: Path, *, ignored_names: set[str] | None = None) -> None:
    """Reject copy inputs whose symlinks escape their declared immutable root."""
    resolved_root = root.resolve(strict=True)
    ignored = ignored_names or set()
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in ignored]
        for name in [*dirnames, *filenames]:
            candidate = Path(directory) / name
            if not candidate.is_symlink():
                continue
            if Path(os.readlink(candidate)).is_absolute():
                raise ReleasePathError(
                    f"Absolute build input symlink is not allowed: {candidate}"
                )
            try:
                candidate.resolve(strict=True).relative_to(resolved_root)
            except (OSError, ValueError) as exc:
                raise ReleasePathError(
                    f"Build input symlink escapes its root: {candidate}"
                ) from exc


@dataclass(frozen=True, slots=True)
class ProductionReleaseBuilder:
    """Build one complete release from immutable job inputs.

    A new instance should be created for each job.  Inputs are defensively
    copied during construction so later caller mutations cannot change the
    candidate associated with a prepared handle.
    """

    app_dir: Path | str
    workspace_root: Path | str
    metadata: Mapping[str, Any]
    pages: Sequence[Mapping[str, Any]]
    scans_source_dir: Path | str
    npm_bin: str = "npm"
    build_timeout_seconds: int = 900
    test_before_build: bool = True
    _runner: BuildRunner | None = None
    active_checkout: Path | str | None = None
    base_release_dir: Path | str | None = None
    base_release_id: str | None = field(init=False, default=None)
    enforce_expected_current: bool = field(init=False, default=True)

    def __post_init__(self) -> None:
        app = Path(self.app_dir)
        scans = Path(self.scans_source_dir)
        work = Path(self.workspace_root)
        checkout = Path(self.active_checkout) if self.active_checkout is not None else None
        base_release = Path(self.base_release_dir) if self.base_release_dir is not None else None
        if app.is_symlink() or not app.is_dir():
            raise ReleasePathError(f"app_dir must be an existing non-symlink directory: {app}")
        if not (app / "package.json").is_file():
            raise ReleaseBuildError(f"app_dir has no package.json: {app}")
        if scans.is_symlink() or not scans.is_dir():
            raise ReleasePathError(f"scans_source_dir must be an existing non-symlink directory: {scans}")
        if not isinstance(self.npm_bin, str) or not self.npm_bin.strip():
            raise ValueError("npm_bin must be a non-empty executable name")
        if self.build_timeout_seconds <= 0:
            raise ValueError("build_timeout_seconds must be greater than zero")
        object.__setattr__(self, "app_dir", app.resolve(strict=True))
        object.__setattr__(self, "scans_source_dir", scans.resolve(strict=True))
        object.__setattr__(self, "workspace_root", work.resolve(strict=False))
        if checkout is not None:
            if checkout.is_symlink() or not checkout.is_dir():
                raise ReleasePathError(f"active_checkout must be an existing non-symlink directory: {checkout}")
            checkout = checkout.resolve(strict=True)
            try:
                work.resolve(strict=False).relative_to(checkout)
            except ValueError:
                pass
            else:
                raise ReleasePathError(f"workspace_root must be outside active checkout: {work}")
            object.__setattr__(self, "active_checkout", checkout)
        if base_release is not None:
            if base_release.is_symlink() or not base_release.is_dir():
                raise ReleasePathError(f"base_release_dir must be an existing non-symlink directory: {base_release}")
            base_release = base_release.resolve(strict=True)
            object.__setattr__(self, "base_release_dir", base_release)
            object.__setattr__(self, "base_release_id", base_release.name)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        object.__setattr__(
            self,
            "pages",
            tuple(MappingProxyType(dict(page)) for page in self.pages),
        )

    def build(self, identity: ReleaseIdentity, stage_path: Path) -> None:
        """Create a complete Vite release below ``stage_path`` only."""
        identity.validate()
        stage = Path(stage_path).resolve(strict=True)
        if stage.is_symlink() or not stage.is_dir():
            raise ReleasePathError(f"stage_path must be an existing non-symlink directory: {stage_path}")

        self.workspace_root.mkdir(parents=True, exist_ok=True)
        if self.workspace_root.is_symlink() or not self.workspace_root.is_dir():
            raise ReleasePathError(f"workspace_root must be a non-symlink directory: {self.workspace_root}")

        workspace: Path | None = None
        try:
            workspace = Path(tempfile.mkdtemp(prefix=f"{identity.job_id}-", dir=self.workspace_root))
            workspace_app = workspace / "app"
            _assert_symlink_targets_contained(
                Path(self.app_dir),
                ignored_names={".git", "node_modules", "dist", "coverage", ".cache", ".vite"},
            )
            shutil.copytree(self.app_dir, workspace_app, ignore=_copytree_ignore, symlinks=False)
            # Keep the entire build workspace private.  npm/Vite may create
            # caches or rewrite package metadata, so sharing the checkout's
            # node_modules via a symlink would still be a checkout write.
            dependencies = self.app_dir / "node_modules"
            if dependencies.is_dir() and not dependencies.is_symlink():
                _assert_symlink_targets_contained(dependencies)
                # Relative links validated above keep pointing inside the
                # private copy (not back into the active checkout).
                shutil.copytree(dependencies, workspace_app / "node_modules", symlinks=True)

            self._merge_previous_release(workspace_app)

            manifest = build_manifest_data(
                identity.slug,
                self.metadata,
                [dict(page) for page in self.pages],
                release_id=identity.release_id,
            )
            manifest_path = workspace_app / "src" / "data" / "books" / identity.slug / "manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self._copy_scans(workspace_app, identity.slug, manifest)
            catalog_entry = {
                "slug": identity.slug,
                "title": manifest.get("title", identity.slug),
                "titleRu": manifest.get("titleRu", manifest.get("title", identity.slug)),
                "author": manifest.get("author", "Unknown"),
                "authorRu": manifest.get("authorRu", manifest.get("author", "Unknown")),
                "totalPages": manifest.get("totalPages", 0),
                "releaseId": identity.release_id,
                "releaseManaged": True,
            }
            catalog_entries = self._catalog_entries(workspace_app, catalog_entry)
            self._write_generated_catalog(workspace_app, catalog_entries)
            self._run_quality_and_build(workspace_app, identity)

            dist_dir = workspace_app / "dist"
            if not dist_dir.is_dir() or dist_dir.is_symlink():
                raise ReleaseBuildError("Frontend build did not produce a safe dist directory")
            self._copy_static_tree(dist_dir, stage)

            # Vite bundles imported JSON into JS chunks; the release contract
            # needs a stable root manifest for independent validation and
            # operational inspection.  Keep this copy beside the built shell.
            manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
            resolve_contained_path(stage, "manifest.json").write_text(manifest_json, encoding="utf-8")
            source_books = workspace_app / "src" / "data" / "books"
            if source_books.is_dir():
                shutil.copytree(source_books, resolve_contained_path(stage, "books"), symlinks=False)
            resolve_contained_path(stage, "catalog.json").write_text(
                json.dumps({"schemaVersion": "1", "books": catalog_entries}, ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )

            # These artifacts are served by the Caddy origin and are also
            # included in checksums.json by StagingManager after this method.
            report = {
                "contractVersion": "release-report/1",
                "jobId": identity.job_id,
                "slug": identity.slug,
                "releaseId": identity.release_id,
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "manifest": "manifest.json",
                "health": "healthz.json",
                "builder": "ProductionReleaseBuilder",
            }
            resolve_contained_path(stage, "release.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            write_health_artifact(stage / "healthz.json", HealthSnapshot.now(identity.release_id))
            self._normalize_stage_permissions(stage)
        except ReleaseBuildError:
            raise
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise ReleaseBuildError(
                f"Failed to build release {identity.release_id}: {exc}"
            ) from exc
        finally:
            if workspace is not None:
                shutil.rmtree(workspace, ignore_errors=True)

    def _copy_scans(self, workspace_app: Path, slug: str, manifest: Mapping[str, Any]) -> None:
        destination = workspace_app / "public" / "scans" / slug
        destination.mkdir(parents=True, exist_ok=True)
        expected: set[str] = set()
        for page in manifest.get("pages", []):
            image_src = page.get("imageSrc")
            if not isinstance(image_src, str) or not image_src:
                raise ReleaseBuildError(f"Page {page.get('pageNumber')} has no scan reference")
            expected.add(Path(image_src.lstrip("/")).name)

        for name in sorted(expected):
            source = self.scans_source_dir / name
            if source.is_symlink() or not source.is_file():
                raise ReleaseBuildError(f"Missing scan for release: {name}")
            target = destination / name
            shutil.copy2(source, target)

    def _merge_previous_release(self, workspace_app: Path) -> None:
        """Carry forward validated runtime-only books into this candidate."""
        if self.base_release_dir is None:
            return
        base = Path(self.base_release_dir)
        try:
            ReleaseValidator().validate_staged_release(base)
            ensure_no_symlinks(base)
            catalog_path = base / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            entries = catalog.get("books") if isinstance(catalog, dict) else None
            if not isinstance(entries, list):
                raise ReleaseBuildError("Previous release has no valid catalog; refusing to drop published books")
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("slug"), str):
                    raise ReleaseBuildError("Previous release catalog contains an invalid book entry")
                slug = validate_component(entry["slug"], "catalog slug", slug=True)
                if entry.get("releaseManaged") is not True:
                    continue
                previous_manifest = base / "books" / slug / "manifest.json"
                previous_scans = base / "scans" / slug
                if not previous_manifest.is_file() or previous_manifest.is_symlink():
                    raise ReleaseBuildError(f"Previous release manifest is missing for published book: {slug}")
                if not previous_scans.is_dir() or previous_scans.is_symlink():
                    raise ReleaseBuildError(f"Previous release scans are missing for published book: {slug}")
                target_manifest = workspace_app / "src" / "data" / "books" / slug / "manifest.json"
                target_manifest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(previous_manifest, target_manifest)
                target_scans = workspace_app / "public" / "scans" / slug
                shutil.copytree(previous_scans, target_scans, symlinks=False, dirs_exist_ok=True)
        except (OSError, ValueError, ReleaseBuildError) as exc:
            if isinstance(exc, ReleaseBuildError):
                raise
            raise ReleaseBuildError("Could not safely merge previous release") from exc

    def _catalog_entries(self, workspace_app: Path, current: dict[str, Any]) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        generated_catalog = workspace_app / "src" / "data" / "library" / "generatedCatalog.json"
        try:
            generated = json.loads(generated_catalog.read_text(encoding="utf-8"))
            built_in = generated.get("books", []) if isinstance(generated, dict) else []
            if not isinstance(built_in, list):
                raise ValueError("books must be a list")
            entries.extend(item for item in built_in if isinstance(item, dict))
        except (OSError, ValueError) as exc:
            raise ReleaseBuildError("Could not read the reader's generated catalog") from exc
        if self.base_release_dir is not None:
            base_catalog = Path(self.base_release_dir) / "catalog.json"
            try:
                value = json.loads(base_catalog.read_text(encoding="utf-8"))
                previous = value.get("books", []) if isinstance(value, dict) else []
                if isinstance(previous, list):
                    for item in previous:
                        if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
                            continue
                        entries = [entry for entry in entries if entry.get("slug") != item["slug"]]
                        entries.append(item)
            except (OSError, ValueError) as exc:
                raise ReleaseBuildError("Could not read previous release catalog") from exc
        for index, entry in enumerate(entries):
            if entry.get("slug") == current["slug"]:
                entries[index] = current
                break
        else:
            entries.append(current)
        return entries

    @staticmethod
    def _write_generated_catalog(workspace_app: Path, entries: list[dict[str, Any]]) -> None:
        catalog_path = workspace_app / "src" / "data" / "library" / "generatedCatalog.json"
        if catalog_path.is_symlink() or not catalog_path.parent.is_dir():
            raise ReleaseBuildError("Reader generated catalog path is unsafe")
        catalog_path.write_text(
            json.dumps({"schemaVersion": "1", "books": entries}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _run_quality_and_build(self, workspace_app: Path, identity: ReleaseIdentity) -> None:
        commands = []
        if self.test_before_build:
            commands.append(("test", [self.npm_bin, "run", "test"]))
        commands.append(("build", [self.npm_bin, "run", "build"]))
        runner = self._runner or subprocess.run
        for label, command in commands:
            try:
                result = runner(
                    command,
                    cwd=str(workspace_app),
                    check=False,
                    capture_output=True,
                    text=True,
                    shell=False,
                    timeout=self.build_timeout_seconds,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise ReleaseBuildError(f"Frontend {label} command could not run for {identity.release_id}") from exc
            if result.returncode != 0:
                output = ((result.stdout or "") + "\n" + (result.stderr or ""))[-4000:]
                raise ReleaseBuildError(
                    f"Frontend {label} command failed for {identity.release_id} (exit {result.returncode}): {output}"
                )

    @staticmethod
    def _copy_static_tree(source: Path, stage: Path) -> None:
        for child in source.iterdir():
            if child.is_symlink():
                raise ReleaseBuildError(f"Symlink in frontend dist is not allowed: {child}")
            target = resolve_contained_path(stage, child.name)
            if child.is_dir():
                shutil.copytree(child, target, symlinks=False, dirs_exist_ok=True)
            elif child.is_file():
                shutil.copy2(child, target)
            else:
                raise ReleaseBuildError(f"Unsupported frontend dist entry: {child}")

    @staticmethod
    def _normalize_stage_permissions(stage: Path) -> None:
        """Make the immutable candidate readable by the dedicated origin group."""
        for directory, dirnames, filenames in os.walk(stage, followlinks=False):
            directory_path = Path(directory)
            if directory_path.is_symlink():
                raise ReleaseBuildError(f"Symlink in staged release: {directory_path}")
            os.chmod(directory_path, 0o750)
            for name in [*dirnames, *filenames]:
                candidate = directory_path / name
                if candidate.is_symlink():
                    raise ReleaseBuildError(f"Symlink in staged release: {candidate}")
                if candidate.is_file():
                    os.chmod(candidate, 0o640)
