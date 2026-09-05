# ADR-006: Ubuntu immutable origin behind Cloudflare Tunnel

## Status

Accepted for P11 foundation; production cutover is still owner-gated.

## Context

The reader must serve a growing library of PDF scans, page JSON, audio and VTT
without using Netlify as the artifact transport. The existing release publisher
already produces versioned release directories and an atomic `current` pointer.
The home Ubuntu host is reachable through outbound connectivity but must not
receive router port-forwarding.

## Decision

- Caddy serves only `/srv/logos/current` and binds to `127.0.0.1`.
- Static assets are file-only; a missing asset is never rewritten to the SPA shell.
- `index.html`, registry metadata and health are revalidated; hash-versioned
  assets can use immutable caching.
- A named Cloudflare Tunnel publishes one owner-approved hostname to Caddy.
- Tunnel UUID and credential JSON are provisioned on Ubuntu under `/etc/logos`
  and are never stored in Git.
- Provisioning has an explicit `--origin-only` mode for a loopback-only Caddy
  install/check. Full Tunnel configuration requires an owner-supplied canonical
  UUID, approved FQDN and pre-existing credential JSON.
- `logos-origin` and `logos-cloudflared` run as dedicated service identities.
- Releases remain immutable and are switched only by the existing publisher;
  bootstrap does not alter the active checkout or pointer.
- The release writer identity is an explicit provisioning choice. Bootstrap can
  grant a selected local writer access to staging, but it does not rewrite the
  existing bot/worker unit; that unit must deliberately use the same writer or
  a member of the `logos` group before P11 acceptance.

## Alternatives considered

- Netlify/Pages artifact delivery — simple, but unsuitable for the expected
  volume and source/PDF storage boundary.
- Direct router port-forward — exposes a home origin and adds certificate and
  firewall responsibilities.
- R2-first storage — a viable future overflow/backup adapter, but unnecessary
  for the first Ubuntu-origin acceptance gate.

## Consequences

Positive: large files stay on the Ubuntu disk, rollback is a pointer switch,
and the public edge is isolated from the home network.

Negative: uptime, disk capacity, backups, upload bandwidth and power become
owner responsibilities. Tunnel connectivity does not prove that Caddy or the
selected release is healthy.

## Acceptance gates

Owner must approve the domain/hostname, Cloudflare account and tunnel
credentials, publication rights for each book, backup target, and an external
smoke test outside the home LAN before production enablement.
