"""Path and identifier guards shared by staging, validation, and promotion."""

import os
import re
import stat
from pathlib import Path
from typing import Iterator


class ReleasePathError(ValueError):
    """Raised when a release path or identifier is unsafe."""


_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_component(value: str, field: str, *, slug: bool = False) -> str:
    """Validate a value before it is used as a single filesystem component."""
    pattern = _SLUG_RE if slug else _COMPONENT_RE
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or not pattern.fullmatch(value):
        kind = "slug" if slug else "identifier"
        raise ReleasePathError(f"Invalid {field} {kind}: {value!r}")
    return value


def _root_path(root: Path) -> Path:
    root = Path(root)
    if root.is_symlink():
        raise ReleasePathError(f"Release root cannot be a symlink: {root}")
    if not root.exists() or not root.is_dir():
        raise ReleasePathError(f"Release root is not an existing directory: {root}")
    return root.resolve(strict=True)


def resolve_contained_path(root: Path, relative_path: str, *, allow_leading_slash: bool = False) -> Path:
    """Resolve a release-relative path and reject traversal, absolute paths, and symlinks."""
    root = _root_path(root)
    if not isinstance(relative_path, str) or not relative_path or "\x00" in relative_path:
        raise ReleasePathError(f"Invalid release path: {relative_path!r}")

    if relative_path.startswith("/"):
        if not allow_leading_slash or relative_path.startswith("//"):
            raise ReleasePathError(f"Absolute release path is not allowed: {relative_path!r}")
        relative_path = relative_path[1:]

    candidate = root / relative_path
    # lstat every component so a symlink cannot redirect a supposedly contained path.
    current = root
    for component in Path(relative_path).parts:
        if component in ("", "."):
            continue
        if component == "..":
            raise ReleasePathError(f"Parent traversal is not allowed: {relative_path!r}")
        current = current / component
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise ReleasePathError(f"Symlink in release path is not allowed: {relative_path!r}")

    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ReleasePathError(f"Release path escapes root: {relative_path!r}") from exc
    if resolved == root:
        raise ReleasePathError(f"Release path must identify a file: {relative_path!r}")
    return candidate


def iter_regular_files(root: Path) -> Iterator[Path]:
    """Yield regular files below root while rejecting symlinks anywhere in the tree."""
    root = _root_path(root)
    stack = [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISLNK(mode):
                    raise ReleasePathError(f"Symlink in staged release is not allowed: {path}")
                if stat.S_ISDIR(mode):
                    stack.append(path)
                elif stat.S_ISREG(mode):
                    yield path
                else:
                    raise ReleasePathError(f"Unsupported filesystem entry in release: {path}")


def ensure_no_symlinks(root: Path) -> None:
    """Reject symlinks in a copied candidate before it can be published."""
    for _ in iter_regular_files(root):
        pass
