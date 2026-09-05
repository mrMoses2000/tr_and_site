#!/usr/bin/env bash
set -euo pipefail

RELEASE_ROOT="/srv/logos"
CONFIG_DIR="/etc/logos"
ORIGIN_PORT="8080"
LOW_WATERMARK_MIB="${LOGOS_LOW_WATERMARK_MIB:-10240}"
PROBE=0
ORIGIN_ONLY=0

die() { printf 'verify_origin: %s\n' "$*" >&2; exit 1; }
while (($#)); do
  case "$1" in
    --root) [[ $# -ge 2 ]] || die "--root needs a value"; RELEASE_ROOT="$2"; shift 2 ;;
    --config-dir) [[ $# -ge 2 ]] || die "--config-dir needs a value"; CONFIG_DIR="$2"; shift 2 ;;
    --origin-port) [[ $# -ge 2 ]] || die "--origin-port needs a value"; ORIGIN_PORT="$2"; shift 2 ;;
    --low-watermark-mib) [[ $# -ge 2 ]] || die "--low-watermark-mib needs a value"; LOW_WATERMARK_MIB="$2"; shift 2 ;;
    --probe) PROBE=1; shift ;;
    --origin-only) ORIGIN_ONLY=1; shift ;;
    -h|--help) printf '%s\n' 'verify_origin.sh [--origin-only] [--root PATH] [--config-dir PATH] [--origin-port PORT] [--low-watermark-mib MIB] [--probe]'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ "$RELEASE_ROOT" =~ ^/srv/[-A-Za-z0-9._/]+$ && "$RELEASE_ROOT" != *..* && "$RELEASE_ROOT" != *//* && "$RELEASE_ROOT" != */ ]] || die "unsafe release root"
[[ "$CONFIG_DIR" =~ ^/etc/[-A-Za-z0-9._/]+$ && "$CONFIG_DIR" != *..* && "$CONFIG_DIR" != *//* && "$CONFIG_DIR" != */ ]] || die "unsafe config dir"
[[ "$ORIGIN_PORT" =~ ^[0-9]+$ && "$ORIGIN_PORT" -ge 1024 && "$ORIGIN_PORT" -le 65535 ]] || die "invalid origin port"
[[ "$LOW_WATERMARK_MIB" =~ ^[0-9]+$ ]] || die "invalid low watermark"

for command in readlink stat find df awk; do command -v "$command" >/dev/null || die "missing command: $command"; done
[[ -d "$RELEASE_ROOT/releases" && -d "$RELEASE_ROOT/staging" && -d "$RELEASE_ROOT/backups" ]] || die "origin directories are incomplete"
[[ -L "$RELEASE_ROOT/current" ]] || die "current must be a symlink"
CURRENT_TARGET="$(readlink -f -- "$RELEASE_ROOT/current")"
RELEASES_REAL="$(readlink -f -- "$RELEASE_ROOT/releases")"
[[ "$CURRENT_TARGET" = "$RELEASES_REAL"/* ]] || die "current escapes a release directory"
[[ -d "$CURRENT_TARGET" ]] || die "current target is not a directory"
[[ "$(dirname -- "$CURRENT_TARGET")" = "$RELEASES_REAL" ]] || die "current must point to a direct release child"
[[ -z "$(find "$CURRENT_TARGET" -type l -print -quit)" ]] || die "release contains a symlink"

FREE_KIB="$(df -Pk -- "$RELEASE_ROOT" | awk 'NR==2 {print $4}')"
[[ "$FREE_KIB" =~ ^[0-9]+$ ]] || die "could not read free disk space"
(( FREE_KIB >= LOW_WATERMARK_MIB * 1024 )) || die "free disk is below low watermark"

if [[ -f "$CONFIG_DIR/Caddyfile" ]]; then
  grep -Eq "^[[:space:]]*http://127\\.0\\.0\\.1:$ORIGIN_PORT[[:space:]]*\\{[[:space:]]*$" "$CONFIG_DIR/Caddyfile" || die 'Caddy site address is not loopback-only'
  grep -Eq '^[[:space:]]*bind[[:space:]]+127\.0\.0\.1[[:space:]]*$' "$CONFIG_DIR/Caddyfile" || die 'Caddy bind directive is not loopback-only'
fi
if command -v caddy >/dev/null && [[ -f "$CONFIG_DIR/Caddyfile" ]]; then
  caddy validate --config "$CONFIG_DIR/Caddyfile" --adapter caddyfile
else
  printf 'warning: caddy/config unavailable; syntax validation skipped\n' >&2
fi
if (( ! ORIGIN_ONLY )) && command -v cloudflared >/dev/null && [[ -f "$CONFIG_DIR/cloudflared/config.yml" ]]; then
  cloudflared tunnel ingress validate --config "$CONFIG_DIR/cloudflared/config.yml"
elif (( ! ORIGIN_ONLY )); then
  printf 'warning: cloudflared/config unavailable; ingress validation skipped\n' >&2
fi

if ((PROBE)); then
  command -v curl >/dev/null || die 'curl is required for --probe'
  curl --fail --silent --show-error "http://127.0.0.1:$ORIGIN_PORT/healthz" >/dev/null || die 'health probe failed'
  HEAD_STATUS="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --head "http://127.0.0.1:$ORIGIN_PORT/index.html")"
  [[ "$HEAD_STATUS" = 200 ]] || die "HEAD index probe returned $HEAD_STATUS"
  RANGE_HEADERS="$(curl --silent --show-error --dump-header - --output /dev/null -H 'Range: bytes=0-31' "http://127.0.0.1:$ORIGIN_PORT/index.html")"
  grep -qi '^HTTP/.* 206' <<<"$RANGE_HEADERS" || die 'Range probe did not return 206'
  MISSING_STATUS="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:$ORIGIN_PORT/__logos_missing_asset__.js")"
  [[ "$MISSING_STATUS" = 404 ]] || die "missing asset returned $MISSING_STATUS"
  ROUTE_STATUS="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:$ORIGIN_PORT/__logos_probe_route__")"
  [[ "$ROUTE_STATUS" = 200 ]] || die "deep-link route returned $ROUTE_STATUS"
  grep -qi '^Content-Type:.*text/html' <<<"$(curl --silent --show-error --head "http://127.0.0.1:$ORIGIN_PORT/index.html")" || die 'HTML MIME header missing'
  INDEX_HEADERS="$(curl --silent --show-error --head "http://127.0.0.1:$ORIGIN_PORT/index.html")"
  grep -qi '^ETag:' <<<"$INDEX_HEADERS" || die 'ETag header missing'
  grep -qi '^Cache-Control:.*no-cache' <<<"$INDEX_HEADERS" || die 'HTML cache policy missing'
fi
printf 'origin verification passed: current=%s free_kib=%s\n' "$CURRENT_TARGET" "$FREE_KIB"
