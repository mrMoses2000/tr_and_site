#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "Starting Telegram Bot for Digital Book Reader..."
source .venv/bin/activate
exec python -m ingestion_service.bot
