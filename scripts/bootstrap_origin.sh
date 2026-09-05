#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_ROOT="/srv/logos"
CONFIG_DIR="/etc/logos"
ORIGIN_PORT="8080"
TUNNEL_UUID="${LOGOS_TUNNEL_UUID:-}"
APPROVED_HOSTNAME="${LOGOS_APPROVED_HOSTNAME:-}"
WRITER_USER="${LOGOS_WRITER_USER:-${SUDO_USER:-moses}}"
CHECK_ONLY=0

usage() {
  cat <<'EOF'
Usage: bootstrap_origin.sh [--check] [--root PATH] [--config-dir PATH]
  [--origin-port PORT] [--writer-user USER] --tunnel-uuid UUID --hostname HOSTNAME

Creates explicit origin directories, rendered configs and systemd units.
It never starts services and never creates Cloudflare credentials.
EOF
}

die() { printf 'bootstrap_origin: %s\n' "$*" >&2; exit 2; }

while (($#)); do
  case "$1" in
    --check) CHECK_ONLY=1; shift ;;
    --root) [[ $# -ge 2 ]] || die "--root needs a value"; RELEASE_ROOT="$2"; shift 2 ;;
    --config-dir) [[ $# -ge 2 ]] || die "--config-dir needs a value"; CONFIG_DIR="$2"; shift 2 ;;
    --origin-port) [[ $# -ge 2 ]] || die "--origin-port needs a value"; ORIGIN_PORT="$2"; shift 2 ;;
    --writer-user) [[ $# -ge 2 ]] || die "--writer-user needs a value"; WRITER_USER="$2"; shift 2 ;;
    --tunnel-uuid) [[ $# -ge 2 ]] || die "--tunnel-uuid needs a value"; TUNNEL_UUID="$2"; shift 2 ;;
    --hostname) [[ $# -ge 2 ]] || die "--hostname needs a value"; APPROVED_HOSTNAME="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ "$RELEASE_ROOT" =~ ^/srv/[-A-Za-z0-9._/]+$ && "$RELEASE_ROOT" != *..* && "$RELEASE_ROOT" != *//* && "$RELEASE_ROOT" != */ ]] || die "--root must be a safe explicit path below /srv"
[[ "$RELEASE_ROOT" != /srv && "$RELEASE_ROOT" != /srv/ ]] || die "refusing broad /srv root"
[[ "$CONFIG_DIR" =~ ^/etc/[-A-Za-z0-9._/]+$ && "$CONFIG_DIR" != *..* && "$CONFIG_DIR" != *//* && "$CONFIG_DIR" != */ ]] || die "--config-dir must be a safe path below /etc"
[[ "$CONFIG_DIR" != /etc && "$CONFIG_DIR" != /etc/ ]] || die "refusing broad /etc config dir"
[[ "$ORIGIN_PORT" =~ ^[0-9]+$ && "$ORIGIN_PORT" -ge 1024 && "$ORIGIN_PORT" -le 65535 ]] || die "invalid origin port"
[[ "$TUNNEL_UUID" =~ ^[0-9a-fA-F-]{16,64}$ ]] || die "explicit tunnel UUID is required"
[[ "$APPROVED_HOSTNAME" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] || die "invalid approved hostname"
[[ "$WRITER_USER" =~ ^[A-Za-z_][A-Za-z0-9_.-]{0,31}$ ]] || die "invalid writer user"

CREDENTIALS_PATH="$CONFIG_DIR/cloudflared/$TUNNEL_UUID.json"
if ((CHECK_ONLY)); then
  printf 'check-only: root=%s config=%s port=%s hostname=%s writer=%s\n' "$RELEASE_ROOT" "$CONFIG_DIR" "$ORIGIN_PORT" "$APPROVED_HOSTNAME" "$WRITER_USER"
  [[ -f "$CREDENTIALS_PATH" ]] || printf 'warning: credentials not found at %s\n' "$CREDENTIALS_PATH" >&2
  exit 0
fi

[[ $EUID -eq 0 ]] || die "run as root on the Ubuntu host"
for command in install sed getent id usermod groupadd useradd; do command -v "$command" >/dev/null || die "missing command: $command"; done
id "$WRITER_USER" >/dev/null 2>&1 || die "writer user does not exist: $WRITER_USER"

getent group logos >/dev/null || groupadd --system logos
getent passwd logos >/dev/null || useradd --system --gid logos --home-dir /nonexistent --shell /usr/sbin/nologin logos
usermod -a -G logos "$WRITER_USER"
getent group cloudflared >/dev/null || groupadd --system cloudflared
getent passwd cloudflared >/dev/null || useradd --system --gid cloudflared --home-dir /nonexistent --shell /usr/sbin/nologin cloudflared

install -d -o "$WRITER_USER" -g logos -m 0750 "$RELEASE_ROOT"
for directory in releases staging backups; do
  mode=0750
  [[ "$directory" = staging || "$directory" = backups ]] && mode=0770
  install -d -o "$WRITER_USER" -g logos -m "$mode" "$RELEASE_ROOT/$directory"
done
install -d -o root -g root -m 0755 "$CONFIG_DIR" "$CONFIG_DIR/cloudflared"

[[ -f "$CREDENTIALS_PATH" ]] || die "credential JSON must be provisioned separately at $CREDENTIALS_PATH"
[[ ! -L "$CREDENTIALS_PATH" && -f "$CREDENTIALS_PATH" ]] || die "credentials must be a regular file"
chmod 0600 "$CREDENTIALS_PATH"
chown cloudflared:cloudflared "$CREDENTIALS_PATH"

rendered_caddy="$(mktemp "$CONFIG_DIR/.Caddyfile.XXXXXX")"
rendered_tunnel="$(mktemp "$CONFIG_DIR/cloudflared/.config.yml.XXXXXX")"
trap 'rm -f -- "$rendered_caddy" "$rendered_tunnel"' EXIT
sed -e "s|__RELEASE_ROOT__|$RELEASE_ROOT|g" -e "s|__ORIGIN_PORT__|$ORIGIN_PORT|g" \
  "$SCRIPT_DIR/infra/caddy/Caddyfile.template" > "$rendered_caddy"
sed -e "s|__TUNNEL_UUID__|$TUNNEL_UUID|g" -e "s|__APPROVED_HOSTNAME__|$APPROVED_HOSTNAME|g" \
  -e "s|__ORIGIN_PORT__|$ORIGIN_PORT|g" "$SCRIPT_DIR/infra/cloudflared/config.yml.template" > "$rendered_tunnel"
install -o root -g root -m 0644 "$rendered_caddy" "$CONFIG_DIR/Caddyfile"
install -o root -g cloudflared -m 0640 "$rendered_tunnel" "$CONFIG_DIR/cloudflared/config.yml"
install -o root -g root -m 0644 "$SCRIPT_DIR/infra/systemd/logos-origin.service" /etc/systemd/system/logos-origin.service
install -o root -g root -m 0644 "$SCRIPT_DIR/infra/systemd/logos-cloudflared.service" /etc/systemd/system/logos-cloudflared.service

printf 'origin foundation installed; services remain disabled\n'
printf 'next: scripts/verify_origin.sh --config-dir %s\n' "$CONFIG_DIR"
