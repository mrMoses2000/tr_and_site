"""Staged release, checksum manifest, and atomic promotion package."""

from .adapter import (
    ExecutionContext,
    FakeReleaseBuilder,
    PreparedRelease,
    ProductionReleaseBuilderUnavailable,
    PublishedRelease,
    ReleaseAdapterError,
    ReleaseBuildError,
    ReleaseBuilder,
    ReleaseIdentity,
    StagedPublicationAdapter,
    UnavailableReleaseBuilder,
)

__all__ = [
    "ExecutionContext",
    "FakeReleaseBuilder",
    "PreparedRelease",
    "ProductionReleaseBuilderUnavailable",
    "PublishedRelease",
    "ReleaseAdapterError",
    "ReleaseBuildError",
    "ReleaseBuilder",
    "ReleaseIdentity",
    "StagedPublicationAdapter",
    "UnavailableReleaseBuilder",
]
