import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
INBOX_DIR = STORAGE_DIR / "inbox"
PROCESSED_DIR = STORAGE_DIR / "processed"
DB_PATH = STORAGE_DIR / "ingestion.db"

APP_DIR = BASE_DIR / "app"
APP_PUBLIC_SCANS_DIR = APP_DIR / "public" / "scans"
APP_DATA_DIR = APP_DIR / "src" / "data"

AGY_BIN = os.getenv("AGY_BIN", "/home/moses/.local/bin/agy")
TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8770028671:AAF5k21SaOELy28F_m61qelnfM05nHruwFc"
)

# Admin chat ID (if set, only this user can upload; if None, opens to all who have access)
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", None)

# Batch size for agy processing (5-8 pages per macro-batch)
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))

# Ensure required directories exist
for directory in [STORAGE_DIR, INBOX_DIR, PROCESSED_DIR, APP_PUBLIC_SCANS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
