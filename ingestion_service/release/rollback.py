"""Explicit operator command for checksum-validated release rollback."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .promoter import ReleasePromoter
from .staging import StagingManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atomically roll Logos back to previous release")
    parser.add_argument("--confirm-rollback", action="store_true")
    parser.add_argument("--staging-dir", required=True, type=Path)
    parser.add_argument("--releases-dir", required=True, type=Path)
    parser.add_argument("--current-pointer", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.confirm_rollback:
        raise RuntimeError("operator rollback requires --confirm-rollback")
    staging = StagingManager(args.staging_dir)
    promoter = ReleasePromoter(args.releases_dir, args.current_pointer, staging)
    before = promoter.current_release()
    if before is None:
        raise RuntimeError("no current release exists")
    if not promoter.rollback():
        raise RuntimeError("no previous release exists")
    after = promoter.current_release()
    print(json.dumps({
        "rolledBackFrom": before.name,
        "currentRelease": after.name if after else None,
        "currentPointer": str(promoter.current_pointer_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
