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
    assert_paths_outside_checkout,
)
from .builder import ProductionReleaseBuilder
from .publication import StagedReleasePublicationPort

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
    "assert_paths_outside_checkout",
    "ProductionReleaseBuilder",
    "StagedReleasePublicationPort",
]
