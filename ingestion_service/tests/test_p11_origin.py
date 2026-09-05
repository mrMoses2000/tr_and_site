from __future__ import annotations

import json
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from ingestion_service.origin.health import HealthArtifactError, HealthSnapshot
from ingestion_service.release.paths import ReleasePathError, resolve_contained_path


ROOT = Path(__file__).parents[2]


def test_release_relative_paths_reject_traversal_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "release"
    root.mkdir()
    (tmp_path / "outside").mkdir()
    (root / "escape").symlink_to(tmp_path / "outside", target_is_directory=True)

    with pytest.raises(ReleasePathError):
        resolve_contained_path(root, "../outside/file.json")
    with pytest.raises(ReleasePathError):
        resolve_contained_path(root, "escape/file.json")
    with pytest.raises(ReleasePathError):
        resolve_contained_path(root, "")


def test_health_contract_is_strict_and_deterministic() -> None:
    snapshot = HealthSnapshot(
        status="ok",
        service="logos-origin",
        releaseId="release-2026.09",
        checkedAt="2026-09-05T12:00:00Z",
    )
    assert snapshot.to_json() == (
        '{"checkedAt":"2026-09-05T12:00:00Z","releaseId":"release-2026.09",'
        '"service":"logos-origin","status":"ok","version":"1"}\n'
    )
    assert HealthSnapshot.from_dict(json.loads(snapshot.to_json())) == snapshot
    with pytest.raises(HealthArtifactError):
        HealthSnapshot.from_dict({**snapshot.to_dict(), "secret": "no"})
    with pytest.raises(HealthArtifactError):
        HealthSnapshot(status="ok", service="other", releaseId="x", checkedAt="2026-09-05T12:00:00Z")


def test_caddy_template_keeps_assets_file_only_and_binds_loopback() -> None:
    template = (ROOT / "infra/caddy/Caddyfile.template").read_text(encoding="utf-8")
    assert "http://127.0.0.1:__ORIGIN_PORT__" in template
    assert "@static_asset path_regexp" in template
    assert "handle @static_asset" in template
    assert "try_files {path} /index.html" in template
    static_block = template.split("handle @static_asset", 1)[1].split("# Shell", 1)[0]
    assert "try_files" not in static_block
    assert "immutable" in template
    assert "no-cache" in template
    assert ":80" not in template and ":443" not in template


def test_origin_templates_have_no_credentials_and_use_service_identities() -> None:
    caddy_unit = (ROOT / "infra/systemd/logos-origin.service").read_text(encoding="utf-8")
    tunnel_unit = (ROOT / "infra/systemd/logos-cloudflared.service").read_text(encoding="utf-8")
    tunnel_config = (ROOT / "infra/cloudflared/config.yml.template").read_text(encoding="utf-8")
    assert "User=logos" in caddy_unit and "NoNewPrivileges=true" in caddy_unit
    assert "User=cloudflared" in tunnel_unit and "ProtectSystem=strict" in tunnel_unit
    assert "__TUNNEL_UUID__" in tunnel_config
    assert "credentials-file:" in tunnel_config
    assert "moses2000nsu" not in (caddy_unit + tunnel_unit + tunnel_config)
    assert "<TUNNEL_TOKEN>" not in (caddy_unit + tunnel_unit + tunnel_config)


@pytest.mark.parametrize("script_name", ["bootstrap_origin.sh", "verify_origin.sh"])
def test_origin_scripts_are_executable_and_fail_closed(script_name: str) -> None:
    path = ROOT / "scripts" / script_name
    mode = path.stat().st_mode
    assert mode & stat.S_IXUSR
    text = path.read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "rm -rf" not in text


def test_bootstrap_check_mode_accepts_safe_inputs_and_rejects_injection() -> None:
    script = ROOT / "scripts/bootstrap_origin.sh"
    valid = subprocess.run(
        [
            "bash", str(script), "--check", "--root", "/srv/logos",
            "--config-dir", "/etc/logos", "--tunnel-uuid", "01234567-89ab-cdef-0123-456789abcdef",
            "--hostname", "reader.example.org", "--writer-user", "moses",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert valid.returncode == 0, valid.stderr
    invalid = subprocess.run(
        [
            "bash", str(script), "--check", "--root", "/srv/logos;touch /tmp/pwned",
            "--config-dir", "/etc/logos", "--tunnel-uuid", "01234567-89ab-cdef-0123-456789abcdef",
            "--hostname", "reader.example.org",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert invalid.returncode != 0


def test_bootstrap_origin_only_needs_no_tunnel_identity() -> None:
    script = ROOT / "scripts/bootstrap_origin.sh"
    result = subprocess.run(
        [
            "bash", str(script), "--check", "--origin-only", "--root", "/srv/logos",
            "--config-dir", "/etc/logos", "--origin-port", "8080", "--writer-user", "moses",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "origin-only" in result.stdout


@pytest.mark.parametrize("uuid", ["0123456789abcdef", "01234567-89ab-cdef-0123-456789abcdeG"])
def test_full_bootstrap_rejects_noncanonical_uuid(uuid: str) -> None:
    result = subprocess.run(
        [
            "bash", str(ROOT / "scripts/bootstrap_origin.sh"), "--check", "--root", "/srv/logos",
            "--config-dir", "/etc/logos", "--tunnel-uuid", uuid, "--hostname", "reader.example.org",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


@pytest.mark.parametrize("hostname", ["reader..example.org", "-reader.example.org", "reader-.example.org", "reader.example-"])
def test_full_bootstrap_rejects_invalid_fqdn_labels(hostname: str) -> None:
    result = subprocess.run(
        [
            "bash", str(ROOT / "scripts/bootstrap_origin.sh"), "--check", "--root", "/srv/logos",
            "--config-dir", "/etc/logos", "--tunnel-uuid", "01234567-89ab-cdef-0123-456789abcdef",
            "--hostname", hostname,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_cloudflared_validation_is_skipped_without_binary() -> None:
    if shutil.which("cloudflared"):
        pytest.skip("host has cloudflared; validate the rendered host config instead")
    assert "cloudflared tunnel ingress validate" in (ROOT / "scripts/verify_origin.sh").read_text()


def test_caddy_validation_is_explicitly_optional_on_developer_host() -> None:
    if shutil.which("caddy"):
        pytest.skip("host has caddy; validate the rendered host config instead")
    result = subprocess.run(["bash", str(ROOT / "scripts/verify_origin.sh"), "--help"], check=False)
    assert result.returncode == 0
