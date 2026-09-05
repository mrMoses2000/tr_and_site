import asyncio
import os
import re
import subprocess
from types import SimpleNamespace
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
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "12345678:abcdefghijklmnopqrstuvwxyzABCDE")
    monkeypatch.delenv("TELEGRAM_ADMIN_IDS", raising=False)
    monkeypatch.delenv("TELEGRAM_ADMIN_ID", raising=False)
    from ingestion_service.config import validate_config, ConfigurationError
    with pytest.raises(ConfigurationError) as exc_info:
        validate_config()
    assert "allowlist" in str(exc_info.value).lower() or "admin" in str(exc_info.value).lower()


def test_dummy_token_is_not_accepted_for_runtime(monkeypatch):
    from ingestion_service.config import validate_config, ConfigurationError

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy_token_for_test")
    monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "12345")
    with pytest.raises(ConfigurationError, match="invalid format"):
        validate_config()


def test_malformed_runtime_limits_fail_closed(monkeypatch):
    from ingestion_service.config import validate_config, ConfigurationError

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "12345678:abcdefghijklmnopqrstuvwxyzABCDE")
    monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "12345")
    monkeypatch.setenv("BATCH_SIZE", "not-a-number")
    with pytest.raises(ConfigurationError, match="BATCH_SIZE"):
        validate_config()

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


def test_document_handler_rejects_unauthorized_before_download(monkeypatch):
    """The actual handler must deny an upload before invoking Telegram download."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "12345678:abcdefghijklmnopqrstuvwxyzABCDE")
    monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "12345")

    from ingestion_service.bot import handle_document

    message = SimpleNamespace(
        document=SimpleNamespace(file_name="book.pdf", mime_type="application/pdf", file_size=10),
        from_user=SimpleNamespace(id=99999),
        reply=AsyncMock(),
    )
    bot = SimpleNamespace(download=AsyncMock())

    asyncio.run(handle_document(message, bot))

    bot.download.assert_not_awaited()
    message.reply.assert_awaited_once()
    assert "нет прав" in message.reply.await_args.args[0].lower()


def test_pdf_content_validation_rejects_non_pdf(tmp_path):
    from ingestion_service.bot import validate_pdf_content

    candidate = tmp_path / "not-a-pdf.pdf"
    candidate.write_bytes(b"this is not a pdf")
    with pytest.raises(ValueError, match="signature"):
        validate_pdf_content(candidate)


def test_upload_cleanup_only_removes_file_in_inbox(tmp_path):
    from ingestion_service.bot import remove_created_upload

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    upload = inbox / "job_book.pdf"
    upload.write_bytes(b"temporary")
    assert remove_created_upload(upload, inbox)
    assert not upload.exists()

    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"keep")
    assert not remove_created_upload(outside, inbox)
    assert outside.exists()


def test_upload_cleanup_refuses_symlink(tmp_path):
    from ingestion_service.bot import remove_created_upload

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"keep")
    link = inbox / "job_link.pdf"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable on this host")

    assert not remove_created_upload(link, inbox)
    assert link.is_symlink()
    assert outside.exists()

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
