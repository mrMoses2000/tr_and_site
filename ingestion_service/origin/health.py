"""Pure, dependency-free health artifact contract for the static origin."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

HealthStatus = Literal["ok", "degraded", "fail"]
_RELEASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CHECKED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")


class HealthArtifactError(ValueError):
    """Raised when a health artifact violates the public contract."""


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    status: HealthStatus
    service: str
    releaseId: str
    checkedAt: str
    version: str = "1"

    def __post_init__(self) -> None:
        if self.status not in {"ok", "degraded", "fail"}:
            raise HealthArtifactError(f"Unsupported status: {self.status!r}")
        if self.service != "logos-origin":
            raise HealthArtifactError("service must be 'logos-origin'")
        if not isinstance(self.releaseId, str) or not _RELEASE_ID.fullmatch(self.releaseId):
            raise HealthArtifactError("releaseId must be one safe filesystem identifier")
        if not isinstance(self.checkedAt, str) or not _CHECKED_AT.fullmatch(self.checkedAt):
            raise HealthArtifactError("checkedAt must be a UTC ISO-8601 timestamp ending in Z")
        try:
            parsed = datetime.fromisoformat(self.checkedAt.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HealthArtifactError("checkedAt is not a valid timestamp") from exc
        if parsed.tzinfo != timezone.utc:
            raise HealthArtifactError("checkedAt must be UTC")
        if self.version != "1":
            raise HealthArtifactError("Unsupported health contract version")

    @classmethod
    def now(cls, release_id: str, status: HealthStatus = "ok") -> "HealthSnapshot":
        checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        return cls(status=status, service="logos-origin", releaseId=release_id, checkedAt=checked_at)

    def to_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"

    @classmethod
    def from_dict(cls, value: Any) -> "HealthSnapshot":
        if not isinstance(value, dict):
            raise HealthArtifactError("Health artifact must be an object")
        expected = {"status", "service", "releaseId", "checkedAt", "version"}
        if set(value) != expected:
            raise HealthArtifactError("Health artifact has missing or unknown fields")
        if any(not isinstance(item, str) for item in value.values()):
            raise HealthArtifactError("Health artifact fields must be strings")
        return cls(**value)


def write_health_artifact(path: Path | str, snapshot: HealthSnapshot) -> Path:
    """Atomically write a validated artifact before a release is promoted."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(snapshot.to_json())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return destination
