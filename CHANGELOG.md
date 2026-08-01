# Changelog

All notable changes to the SentinelX protocol will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2026-08-01

### Added
- `read_audit` operation (read-only). Returns recent entries from the agent's
  own on-host audit log at `/var/lib/sentinelx/audit.jsonl`, which records
  each executed operation together with its payload. This is the only place
  the actual command/payload is retained; it never leaves the host except in
  response to this op, and entries are returned as-is (no redaction) since the
  log is the host owner's own record. Backward compatible: older agents don't
  advertise or handle the op, and older hubs simply never request it.

## [1.3.0] - 2026-05-16

### Added
- `ConfigSummary` on `HostInfo`, reported by the agent in its hello handshake.
  (This entry documents a version that shipped without a changelog note at the
  time; recorded here retroactively for completeness.)

## [1.2.0] - 2026-05-17

### Added
- 5 destructive filesystem operations: `move`, `copy`, `delete`, `chmod`,
  `chown`. These complement the read-only primitives from 1.1.0 and are
  gated agent-side by the unified `file_ops` path model (an entry must be
  `rw`, not just `r`). Destructive ops that overwrite or remove an
  existing target take a timestamped backup first.

### Changed
- `PROTOCOL_VERSION` is now `"1.2.0"`, matching the git tag. It had been
  left at `"1.0.0"` through the 1.1.0 release (see note below). Wire
  compatibility is unchanged: the hub negotiates on `PROTOCOL_MAJOR`
  only, which remains `1`. Adding operations is backward-compatible — an
  older peer simply never exercises an op it doesn't know.

### Note on versioning
The internal `PROTOCOL_VERSION` constant was not bumped when `v1.1.0`
was tagged, so it read `"1.0.0"` while git tags read `v1.0.0`/`v1.1.0`.
This release realigns the constant with the tag (`1.2.0`) and documents
the previously-undocumented 1.1.0 entry below. No behavioural change:
compatibility has always been keyed on the major version (`1.x`).

## [1.1.0] - 2026-05-14

> Documented retroactively. This version was tagged (`v1.1.0`) but its
> CHANGELOG entry was missing and `PROTOCOL_VERSION` was not bumped at
> the time; both are corrected as of 1.2.0.

### Added
- Read-only filesystem primitives (Story 6): `read`, `list`, `search`.
  Gated agent-side by a path allowlist (`file_ops`), separate from the
  command allowlist. No write capability.

## [1.0.0] - 2026-05-01

Initial protocol version.

### Added
- `hello` / `welcome` connection handshake
- `request` / `response` for synchronous tool calls
- `ping` / `pong` heartbeat
- `event` for async notifications from core
- `error` for fatal protocol errors
- 16 operation types (`exec`, `edit`, `service`, etc.)
