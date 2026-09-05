# Ubuntu origin runbook

This runbook is for the immutable release origin. Commands are intentionally
manual at the final enablement step so a production cutover cannot happen by
accident.

## Provisioning

1. Install Caddy and `cloudflared` from their official packages.
2. Create a named Tunnel and obtain its UUID and credential JSON in Cloudflare.
   Put the JSON at `/etc/logos/cloudflared/<TUNNEL_UUID>.json`, owned by
   `cloudflared:cloudflared`, mode `0600`; do not put it in the repository.
3. From a clean checkout run, with owner-approved values:

   ```bash
   sudo scripts/bootstrap_origin.sh \
     --tunnel-uuid '<TUNNEL_UUID>' \
     --hostname 'reader.example.org' \
     --writer-user 'moses'
   ```

   The script only creates explicit directories/configuration and installs unit
   files. It does not start services or create a tunnel. The selected writer
   user must also be the user/group configured for the ingestion worker; this
   script does not rewrite the existing bot/worker unit.

   For loopback-only preparation before Cloudflare account/hostname approval,
   use `sudo scripts/bootstrap_origin.sh --origin-only --writer-user moses`.
   This mode does not require or create Tunnel credentials, cloudflared config,
   or the cloudflared unit. Full mode remains fail-closed until the canonical
   Tunnel UUID, FQDN and credential JSON are present.

4. Validate before enabling anything:

   ```bash
   sudo scripts/verify_origin.sh --config-dir /etc/logos
   sudo caddy validate --config /etc/logos/Caddyfile --adapter caddyfile
   sudo cloudflared tunnel ingress validate --config /etc/logos/cloudflared/config.yml
   ```

## Release and local smoke test

The publisher writes to a per-job staging directory, validates checksums and
manifest boundaries, then atomically switches `/srv/logos/current`. Never copy
files into `current` by hand.

```bash
curl --fail --silent --show-error -D - http://127.0.0.1:8080/healthz -o /tmp/logos-health.json
curl --fail --silent --show-error -I http://127.0.0.1:8080/index.html
curl --fail --silent --show-error -H 'Range: bytes=0-31' -D - \
  http://127.0.0.1:8080/books/<book-id>/<release-id>/source/source.pdf -o /dev/null
curl --silent --show-error -o /dev/null -w '%{http_code}\n' \
  http://127.0.0.1:8080/assets/does-not-exist.js # must print 404
```

## Enable / disable

After the checks and external approval:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now logos-origin.service
sudo systemctl enable --now logos-cloudflared.service
sudo systemctl --no-pager --full status logos-origin.service logos-cloudflared.service
```

The Tunnel is connected only after Caddy is healthy. No router port-forward is
needed or permitted by this design.

With `admin off`, Caddy configuration changes are applied by restarting the
origin service after a successful `caddy validate`; there is no reload socket.

## Rollback and restore

- Application rollback: inspect `readlink -f /srv/logos/current`, then use the
  existing release promoter rollback operation. Do not delete a release while
  it may be referenced by `current` or `previous`.
- Origin rollback: `sudo systemctl restart logos-origin.service`; if the
  configuration is invalid, restore the last known-good `/etc/logos/Caddyfile`
  from the operator's protected backup and re-run validation.
- Data restore: restore a verified backup into a new release/staging directory,
  re-run checksum/manifest validation, and switch the pointer atomically. A
  backup is not accepted until a restore has been exercised and recorded.

## Troubleshooting

- Tunnel connected but public 502: check loopback `/healthz` and
  `journalctl -u logos-origin.service`; Tunnel readiness is not origin readiness.
- Missing PDF/scan returns 404: check the release manifest and path; never add
  a SPA rewrite for asset failures.
- Low disk watermark: stop new ingestion/promotion, preserve the current
  release, and expand storage or move approved overflow assets to a future R2
  adapter.
