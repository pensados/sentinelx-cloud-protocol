# Changelog

All notable changes to the SentinelX protocol will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.9.0] - 2026-08-17

### Added
- `git` operation (`sentinel_git`). Structured Git operations dispatched
  agent-side: `diff` (read-only, gated by the file_ops READ allowlist) and
  `apply_patch` (mutating, gated by file_ops RW). Additive and backward
  compatible — older agents simply do not advertise or handle the op, and
  older hubs never request it. Protocol MAJOR stays 1, so 1.8.0 agents keep
  connecting.

## [1.8.0] - 2026-08-15

### Added
- Cross-host file transfer: binary streaming relay through the Hub.
  - New INTERNAL agent operations `file_export_init`, `file_export_chunk`, and
    `file_export_complete` (source side). Driven by the Hub's
    `sentinel_transfer_file` coordinator; NOT exposed as model-visible MCP
    tools. `file_export_init` stats the source file (size + sha256 + filename)
    gated by the existing file_ops READ allowlist; `file_export_chunk` streams
    one raw binary frame per chunk; `file_export_complete` tears down the
    source-side export session.
  - New binary transport dimension (`sentinelx_protocol.binary`): control
    messages stay JSON text frames, file bytes travel as WebSocket **binary**
    frames on the same connection. Self-describing mini-framing
    `[transfer_id: 16B][chunk_index: 4B uint32 BE][payload]` routes a raw frame
    to its transfer/chunk without an interleaved control message. Constants:
    `TRANSFER_CHUNK_BYTES` (1 MiB payload), `BINARY_HEADER_BYTES` (20),
    `MAX_BINARY_FRAME_BYTES` (2 MiB — the WS frame ceiling the agent/hub must
    allow, above chunk+header for headroom).
  - Capability advertisement is additive: the Hub only relays a transfer when
    BOTH source and destination advertise binary-transfer support. Backward
    compatible — older agents don't advertise/handle the ops, older hubs never
    request them. Protocol MAJOR stays 1, so 1.7.0 agents keep connecting.

## [1.7.0] - 2026-08-14

### Added
- `project_snapshot` operation (read-only). Returns a bounded, deterministic
  summary of a project/repository in a single call: git state (branch, HEAD,
  detached, dirty, ahead/behind), change stats (staged/unstaged/untracked
  counts, insertions/deletions), and repository facts (tracked-file count,
  top-level directories, and file-extension counts). For a non-git but readable
  directory it returns a plain filesystem summary (`kind: "directory"`) instead
  of failing. The op aggregates work a client would otherwise do with several
  `list`/`read`/`search`/`exec(git …)` round-trips, reducing tool-call and
  context overhead — it adds no new capability, only a compact, deterministic
  shape. Reuses the existing file-ops path allowlist and read-only semantics;
  the git root reported by the repository is re-validated against the allowlist
  before use. Backward compatible: older agents don't advertise or handle the
  op, and older hubs simply never request it.

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
