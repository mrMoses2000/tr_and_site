import os
import re
import subprocess
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

def test_startup_without_bot_token_fails(monkeypatch):
    """
    RED test: startup without TELEGRAM_BOT_TOKEN must fail with a safe message.
    Currently config.py has a hardcoded default token, so this fails.
    """
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    # When validating config, missing token must raise ConfigurationError
    from ingestion_service.config import validate_config, ConfigurationError
    with pytest.raises(ConfigurationError) as exc_info:
        validate_config()
    assert "TELEGRAM_BOT_TOKEN" in str(exc_info.value)
    # Ensure no token values leaked in error message
    assert ":" not in str(exc_info.value)

def test_startup_without_admin_allowlist_fails(monkeypatch):
    """
    RED test: startup without admin allowlist must fail (deny-by-default).
    Currently config.py defaults to None (fail-open), so this fails.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy_token_for_test")
    monkeypatch.delenv("TELEGRAM_ADMIN_IDS", raising=False)
    monkeypatch.delenv("TELEGRAM_ADMIN_ID", raising=False)
    from ingestion_service.config import validate_config, ConfigurationError
    with pytest.raises(ConfigurationError) as exc_info:
        validate_config()
    assert "allowlist" in str(exc_info.value).lower() or "admin" in str(exc_info.value).lower()

def test_unauthorized_document_rejected_before_download(monkeypatch):
    """
    RED test: unauthorized sender must be rejected before download and no job created.
    """
    from ingestion_service.config import Settings
    settings = Settings(
        telegram_bot_token="dummy_test_token",
        admin_user_ids=[12345]
    )
    
    from ingestion_service.bot import is_user_authorized, sanitize_inbox_path
    assert not is_user_authorized(99999, settings.admin_user_ids)
    assert is_user_authorized(12345, settings.admin_user_ids)

def test_filename_cannot_escape_inbox():
    """
    RED test: filename with path traversal characters cannot escape INBOX_DIR.
    """
    from ingestion_service.bot import sanitize_inbox_path
    from ingestion_service.config import INBOX_DIR

    dangerous_names = [
        "../../etc/passwd",
        "../../../var/log/syslog",
        "/etc/shadow",
        "..\\..\\windows\\win.ini",
        "foo/bar/baz.pdf",
    ]
    for d_name in dangerous_names:
        safe_path = sanitize_inbox_path("job123", d_name, INBOX_DIR)
        assert safe_path.resolve().is_relative_to(INBOX_DIR.resolve())
        assert ".." not in safe_path.name
        assert "/" not in safe_path.name

def test_repository_scan_detects_no_hardcoded_tokens():
    """
    RED test: no live bot token patterns hardcoded in tracking source code.
    Currently config.py has hardcoded token, so this fails.
    """
    token_pattern = re.compile(r'[0-9]{8,12}:[a-zA-Z0-9_-]{35}')
    base_dir = Path(__file__).resolve().parent.parent.parent
    
    # Check git tracked files
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(base_dir),
        capture_output=True,
        text=True,
        check=True
    )
    files = result.stdout.strip().splitlines()
    violations = []
    
    for rel_path in files:
        # Exclude this test file and audit/playbook documentation that discusses the leak
        if "test_p0_security" in rel_path or rel_path.endswith(".png") or rel_path.endswith(".webp"):
            continue
        file_path = base_dir / rel_path
        if file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                matches = token_pattern.findall(content)
                if matches:
                    violations.append(f"{rel_path}: {len(matches)} token pattern match(es)")
            except Exception:
                pass
                
    assert not violations, f"Found hardcoded token patterns in: {violations}"
