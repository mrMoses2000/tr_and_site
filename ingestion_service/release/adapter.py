"""Explicit staged publication boundary for P6--P11.

The adapter deliberately has no ``current prepared release`` field.  A build
returns an immutable handle and promotion accepts that handle back, so two
jobs cannot accidentally publish whichever candidate happened to be prepared
last.  The active application checkout is never a build target.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .models import ReleaseManifest
from .paths import ReleasePathError, resolve_contained_path, validate_component
from .promoter import ReleasePromoter
from .staging import StagingManager
from .validator import ReleaseValidator


class ReleaseAdapterError(RuntimeError):
    """Base error for the staged publication boundary."""


class ReleaseBuildError(ReleaseAdapterError):
    """Raised when a candidate builder cannot produce a complete stage."""


class ProductionReleaseBuilderUnavailable(ReleaseBuildError):
    """The real shell/build integration is intentionally not enabled yet."""


def assert_paths_outside_checkout(
    active_checkout: Path | str,
    paths: Mapping[str, Path | str],
) -> None:
    """Reject publication paths inside checkout before constructors create them."""
    checkout = Path(active_checkout)
    if checkout.is_symlink() or not checkout.is_dir():
        raise ReleasePathError(
            f"Active checkout must be an existing non-symlink directory: {checkout}"
        )
    checkout = checkout.resolve(strict=True)
    for label, raw_path in paths.items():
        candidate = Path(raw_path)
        if candidate.is_symlink():
            raise ReleasePathError(f"{label} path cannot be a symlink: {candidate}")
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(checkout)
        except ValueError:
            continue
        raise ReleasePathError(f"{label} directory must be outside active checkout: {resolved}")


@dataclass(frozen=True, slots=True)
class ReleaseIdentity:
    """Stable identity shared by a job, book slug, and immutable release."""

    job_id: str
    slug: str
    release_id: str

    def validate(self) -> None:
        validate_component(self.job_id, "job_id")
        validate_component(self.slug, "slug", slug=True)
        validate_component(self.release_id, "release_id")


class ExecutionContext(Protocol):
    """Minimal fenced context required before any publication side effect."""

    def assert_active(self) -> None:
        """Raise when the worker no longer owns its active lease."""


class ReleaseBuilder(Protocol):
    """Build only into the supplied per-job stage directory."""

    def build(self, identity: ReleaseIdentity, stage_path: Path) -> None:
        """Write candidate files below ``stage_path``; never write the checkout."""


@dataclass(frozen=True, slots=True)
class PreparedRelease:
    """Validated candidate handle; no adapter-global mutable state is used."""

    identity: ReleaseIdentity
    stage_path: Path
    manifest: ReleaseManifest
    expected_current_release_id: str | None = None
    enforce_expected_current: bool = False


@dataclass(frozen=True, slots=True)
class PublishedRelease:
    """Result of promoting one exact prepared candidate."""

    identity: ReleaseIdentity
    release_path: Path


class UnavailableReleaseBuilder:
    """Explicit fail-closed placeholder until a production builder is wired."""

    def build(self, identity: ReleaseIdentity, stage_path: Path) -> None:
        raise ProductionReleaseBuilderUnavailable(
            "Production release builder is unavailable; no shell/build command is configured."
        )


@dataclass(frozen=True, slots=True)
class FakeReleaseBuilder:
    """Small deterministic builder for adapter/contract tests only."""

    manifest: Mapping[str, Any]
    files: Mapping[str, bytes] = field(default_factory=dict)

    def build(self, identity: ReleaseIdentity, stage_path: Path) -> None:
        stage_path = Path(stage_path).resolve(strict=True)
        try:
            manifest_path = resolve_contained_path(stage_path, "manifest.json")
            manifest_path.write_text(
                json.dumps(dict(self.manifest), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            for relative_path, contents in self.files.items():
                destination = resolve_contained_path(stage_path, relative_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(contents)
        except (OSError, ReleasePathError) as exc:
            raise ReleaseBuildError(f"Failed to build staged release {identity.release_id}") from exc


class StagedPublicationAdapter:
    """Prepare, validate, and promote immutable releases without checkout writes."""

    def __init__(
        self,
        staging: StagingManager,
        promoter: ReleasePromoter,
        *,
        active_checkout: Path | str,
        validator: ReleaseValidator | None = None,
    ) -> None:
        self.staging = staging
        self.promoter = promoter
        self.validator = validator or ReleaseValidator()

        checkout = Path(active_checkout)
        if checkout.is_symlink() or not checkout.exists() or not checkout.is_dir():
            raise ReleasePathError(f"Active checkout must be an existing non-symlink directory: {checkout}")
        self.active_checkout = checkout.resolve(strict=True)
        assert_paths_outside_checkout(
            self.active_checkout,
            {
                "staging": self.staging.staging_base_dir,
                "releases": self.promoter.releases_dir,
                "current pointer": self.promoter.current_pointer_path.parent,
            },
        )
        self._assert_outside_checkout(self.staging.staging_base_dir, "staging")
        self._assert_outside_checkout(self.promoter.releases_dir, "releases")
        self._assert_outside_checkout(self.promoter.current_pointer_path.parent, "current pointer")

    def _assert_outside_checkout(self, path: Path, label: str) -> None:
        resolved = Path(path).resolve(strict=True)
        try:
            resolved.relative_to(self.active_checkout)
        except ValueError:
            return
        raise ReleasePathError(f"{label} directory must be outside active checkout: {resolved}")

    @staticmethod
    def _assert_context(execution_context: ExecutionContext) -> None:
        if execution_context is None or not callable(getattr(execution_context, "assert_active", None)):
            raise TypeError("execution_context with assert_active() is required")
        execution_context.assert_active()

    @staticmethod
    def _lease_checker(execution_context: ExecutionContext) -> Callable[[], bool]:
        """Adapt the void context assertion to ReleasePromoter's bool port."""
        def check() -> bool:
            execution_context.assert_active()
            return True

        return check

    @staticmethod
    def _assert_manifest_identity(manifest: ReleaseManifest, identity: ReleaseIdentity) -> None:
        if manifest.job_id != identity.job_id:
            raise ReleaseAdapterError(
                f"Prepared manifest job_id mismatch: expected {identity.job_id!r}, got {manifest.job_id!r}"
            )
        if manifest.slug != identity.slug:
            raise ReleaseAdapterError(
                f"Prepared manifest slug mismatch: expected {identity.slug!r}, got {manifest.slug!r}"
            )
        if manifest.release_id != identity.release_id:
            raise ReleaseAdapterError(
                f"Prepared manifest release_id mismatch: expected {identity.release_id!r}, got {manifest.release_id!r}"
            )

    def prepare(
        self,
        identity: ReleaseIdentity,
        builder: ReleaseBuilder,
        execution_context: ExecutionContext,
    ) -> PreparedRelease:
        """Build and validate one candidate in an isolated job stage."""
        identity.validate()
        if not callable(getattr(builder, "build", None)):
            raise TypeError("builder with build(identity, stage_path) is required")
        self._assert_context(execution_context)

        stage_path = self.staging.create_stage(
            identity.job_id,
            identity.slug,
            identity.release_id,
        )
        try:
            # Re-check before and after the untrusted/long-running build.
            self._assert_context(execution_context)
            builder.build(identity, stage_path)
            self._assert_context(execution_context)
            self.staging.compute_checksums(identity.job_id)
            self._assert_context(execution_context)
            manifest = self.validator.validate_staged_release(stage_path)
            self._assert_manifest_identity(manifest, identity)
            return PreparedRelease(
                identity=identity,
                stage_path=stage_path.resolve(strict=True),
                manifest=manifest,
                expected_current_release_id=getattr(builder, "base_release_id", None),
                enforce_expected_current=bool(
                    getattr(builder, "enforce_expected_current", False)
                ),
            )
        except Exception:
            # A failed candidate is disposable; current/previous are untouched.
            self.staging.cleanup_stage(identity.job_id)
            raise

    def publish(
        self,
        prepared: PreparedRelease,
        execution_context: ExecutionContext,
    ) -> PublishedRelease:
        """Promote exactly ``prepared`` after a mandatory live lease check."""
        if not isinstance(prepared, PreparedRelease):
            raise TypeError("prepared must be a PreparedRelease handle")
        prepared.identity.validate()
        self._assert_context(execution_context)

        expected_stage = self.staging.get_stage_path(prepared.identity.job_id).resolve(strict=True)
        actual_stage = Path(prepared.stage_path).resolve(strict=True)
        if actual_stage != expected_stage:
            raise ReleaseAdapterError("Prepared release stage does not belong to its job_id")

        manifest = self.validator.validate_staged_release(actual_stage)
        self._assert_manifest_identity(manifest, prepared.identity)
        if manifest.model_dump() != prepared.manifest.model_dump():
            raise ReleaseAdapterError("Prepared release changed after validation")

        # ReleasePromoter checks this again immediately before and during the
        # atomic pointer switch. Passing the bound method is intentional: there
        # is no optional/default lease path for publication.
        release_path = self.promoter.promote(
            job_id=prepared.identity.job_id,
            slug=prepared.identity.slug,
            release_id=prepared.identity.release_id,
            lease_checker=self._lease_checker(execution_context),
            expected_current_release_id=prepared.expected_current_release_id,
            enforce_expected_current=prepared.enforce_expected_current,
        )
        return PublishedRelease(identity=prepared.identity, release_path=release_path)
