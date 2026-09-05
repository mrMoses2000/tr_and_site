#!/usr/bin/env python3
"""Repository entrypoint for the explicit immutable seed-release command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingestion_service.release.seed import main


if __name__ == "__main__":
    raise SystemExit(main())
