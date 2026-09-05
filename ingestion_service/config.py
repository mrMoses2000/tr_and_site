import os
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict

class ConfigurationError(Exception):
    """Raised when application security configuration is missing or invalid."""
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
INBOX_DIR = STORAGE_DIR / "inbox"
PROCESSED_DIR = STORAGE_DIR / "processed"
DB_PATH = STORAGE_DIR / "ingestion.db"

APP_DIR = BASE_DIR / "app"
APP_PUBLIC_SCANS_DIR = APP_DIR / "public" / "scans"
APP_DATA_DIR = APP_DIR / "src" / "data"

BOT_TOKEN_REGEX = re.compile(r'^[0-9]{8,12}:[a-zA-Z0-9_-]{30,45}$')

@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    admin_user_ids: List[int]
    agy_bin: str = "/home/moses/.local/bin/agy"
    batch_size: int = 5
    max_upload_bytes: int = 512 * 1024 * 1024
    worker_lease_seconds: int = 300
    worker_poll_interval: float = 2.0
    storage_dir: Path = STORAGE_DIR
    inbox_dir: Path = INBOX_DIR
    processed_dir: Path = PROCESSED_DIR
    db_path: Path = DB_PATH

def validate_config(env_override: Optional[Dict[str, str]] = None) -> Settings:
    """
    Validates runtime security configuration using strict deny-by-default.
    Raises ConfigurationError if required secrets or admin allowlists are missing.
    Never prints or leaks secret token values in error messages.
    """
    env = os.environ if env_override is None else env_override

    # 1. TELEGRAM_BOT_TOKEN check
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ConfigurationError("TELEGRAM_BOT_TOKEN environment variable is required")
    if not BOT_TOKEN_REGEX.fullmatch(token):
        raise ConfigurationError("TELEGRAM_BOT_TOKEN has invalid format")

    # 2. TELEGRAM_ADMIN_IDS check (strict deny-by-default allowlist)
    raw_admin_ids = env.get("TELEGRAM_ADMIN_IDS") or env.get("TELEGRAM_ADMIN_ID", "")
    if not raw_admin_ids or not raw_admin_ids.strip():
        raise ConfigurationError(
            "TELEGRAM_ADMIN_IDS is required for secure operation (deny-by-default allowlist)"
        )

    admin_ids: List[int] = []
    for part in raw_admin_ids.split(","):
        p = part.strip()
        if not p:
            continue
        try:
            admin_ids.append(int(p))
        except ValueError:
            raise ConfigurationError(
                "TELEGRAM_ADMIN_IDS must be a comma-separated list of integer Telegram user IDs"
            )

    if not admin_ids:
        raise ConfigurationError("TELEGRAM_ADMIN_IDS cannot be empty (deny-by-default allowlist)")

    # 3. Optional settings
    agy_bin = env.get("AGY_BIN", "/home/moses/.local/bin/agy")

    def positive_int(name: str, default: int, maximum: Optional[int] = None) -> int:
        raw = env.get(name, str(default)).strip()
        try:
            value = int(raw)
        except ValueError as exc:
            raise ConfigurationError(f"{name} must be an integer") from exc
        if value <= 0 or (maximum is not None and value > maximum):
            limit = f" and <= {maximum}" if maximum is not None else ""
            raise ConfigurationError(f"{name} must be > 0{limit}")
        return value

    def positive_float(name: str, default: float) -> float:
        raw = env.get(name, str(default)).strip()
        try:
            value = float(raw)
        except ValueError as exc:
            raise ConfigurationError(f"{name} must be a number") from exc
        if value <= 0:
            raise ConfigurationError(f"{name} must be > 0")
        return value

    batch_size = positive_int("BATCH_SIZE", 5, maximum=100)
    max_upload_bytes = positive_int("MAX_UPLOAD_BYTES", 512 * 1024 * 1024)
    worker_lease_seconds = positive_int("WORKER_LEASE_SECONDS", 300)
    worker_poll_interval = positive_float("WORKER_POLL_INTERVAL", 2.0)

    return Settings(
        telegram_bot_token=token,
        admin_user_ids=admin_ids,
        agy_bin=agy_bin,
        batch_size=batch_size,
        max_upload_bytes=max_upload_bytes,
        worker_lease_seconds=worker_lease_seconds,
        worker_poll_interval=worker_poll_interval,
    )

def get_settings() -> Settings:
    return validate_config()

# Legacy aliases for backward compatibility without hardcoded secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", None)
AGY_BIN = os.getenv("AGY_BIN", "/home/moses/.local/bin/agy")
BATCH_SIZE = 5
try:
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))
except ValueError:
    # Import-time compatibility alias; validate_config() is authoritative.
    BATCH_SIZE = 5

# Ensure required directories exist
for directory in [STORAGE_DIR, INBOX_DIR, PROCESSED_DIR, APP_PUBLIC_SCANS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
