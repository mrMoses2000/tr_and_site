"""Explicit operator seed command for the immutable origin.

This is intentionally separate from the Telegram worker: it is useful for the
first known-good release and requires every filesystem boundary plus an
affirmative confirmation.  It still uses ``StagedPublicationAdapter`` and the
same builder, so ``current`` is changed only by the atomic promotion path.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapter import ReleaseIdentity, StagedPublicationAdapter, assert_paths_outside_checkout
from .builder import ProductionReleaseBuilder
from .promoter import ReleasePromoter
from .staging import StagingManager


@dataclass(frozen=True, slots=True)
class OperatorSeedContext:
    confirmed: bool

    def assert_active(self) -> None:
        if not self.confirmed:
            raise RuntimeError("operator seed requires --confirm-seed")


def _json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"metadata JSON must contain an object: {path}")
    return value


def _json_pages(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, list) or not all(isinstance(page, dict) for page in value):
        raise ValueError(f"pages JSON must contain an array of objects: {path}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and atomically promote one Logos seed release")
    parser.add_argument("--confirm-seed", action="store_true", help="required explicit promotion confirmation")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--checkout-root", required=True, type=Path)
    parser.add_argument("--app-dir", required=True, type=Path)
    parser.add_argument("--staging-dir", required=True, type=Path)
    parser.add_argument("--releases-dir", required=True, type=Path)
    parser.add_argument("--current-pointer", required=True, type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--scans-dir", required=True, type=Path)
    parser.add_argument(
        "--manifest-json",
        type=Path,
        help="existing reader manifest containing metadata and a pages array",
    )
    parser.add_argument("--metadata-json", type=Path)
    parser.add_argument("--pages-json", type=Path)
    parser.add_argument("--npm-bin", default="npm")
    parser.add_argument("--build-timeout-seconds", default=900, type=int)
    parser.add_argument("--skip-tests", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.manifest_json is not None:
        if args.metadata_json is not None or args.pages_json is not None:
            raise ValueError("--manifest-json cannot be combined with --metadata-json/--pages-json")
        metadata = _json_object(args.manifest_json)
        pages = metadata.get("pages")
        if not isinstance(pages, list) or not all(isinstance(page, dict) for page in pages):
            raise ValueError(f"manifest JSON must contain a pages array: {args.manifest_json}")
    else:
        if args.metadata_json is None or args.pages_json is None:
            raise ValueError("provide --manifest-json or both --metadata-json and --pages-json")
        metadata = _json_object(args.metadata_json)
        pages = _json_pages(args.pages_json)
    context = OperatorSeedContext(confirmed=args.confirm_seed)
    context.assert_active()
    identity = ReleaseIdentity(args.job_id, args.slug, args.release_id)
    assert_paths_outside_checkout(
        args.checkout_root,
        {
            "staging": args.staging_dir,
            "releases": args.releases_dir,
            "current pointer": args.current_pointer.parent,
            "build workspace": args.workspace_root,
        },
    )
    staging = StagingManager(args.staging_dir)
    promoter = ReleasePromoter(args.releases_dir, args.current_pointer, staging)
    adapter = StagedPublicationAdapter(staging, promoter, active_checkout=args.checkout_root)
    base_release = promoter.current_release()
    builder = ProductionReleaseBuilder(
        app_dir=args.app_dir,
        workspace_root=args.workspace_root,
        metadata=metadata,
        pages=pages,
        scans_source_dir=args.scans_dir,
        npm_bin=args.npm_bin,
        build_timeout_seconds=args.build_timeout_seconds,
        test_before_build=not args.skip_tests,
        active_checkout=args.checkout_root,
        base_release_dir=base_release,
    )
    prepared = adapter.prepare(identity, builder, context)
    published = adapter.publish(prepared, context)
    print(json.dumps({
        "jobId": identity.job_id,
        "slug": identity.slug,
        "releaseId": identity.release_id,
        "releasePath": str(published.release_path),
        "currentPointer": str(promoter.current_pointer_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
