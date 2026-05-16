# sentinelx-cloud-protocol

The wire format shared between [`sentinelx-cloud-core`](https://github.com/pensados/sentinelx-cloud-core)
(the agent on your server) and the SentinelX hub.

This repo is the source of truth for the WebSocket protocol. It contains no
business logic — only the spec, JSON schemas, and typed Python bindings that
both sides import.

## Why a separate repo

The agent is open source. The hub is closed source. They have to agree on
the wire format. Pinning that contract here means:

- Both sides import from a single versioned source
- Third parties can build alternate hubs or agents that interoperate
- Schema changes go through a real review process — they're a public artifact

## Architecture

```
   ┌─────────────────┐                   ┌──────────────────┐
   │  agent          │  WebSocket        │  hub             │
   │ (cloud-core)    │ ◄──── + JWT ────► │ (mcp.sentinelx)  │
   │                 │   request msgs    │                  │
   │                 │   reply msgs      │                  │
   └─────────────────┘                   └──────────────────┘
        ▲                                        ▲
        │                                        │
        └──── both import sentinelx_protocol ────┘
```

## Wire format

A single WebSocket per agent. Messages are JSON with a `type` discriminator.

### Request (hub → agent)

```json
{
  "type": "request",
  "id": "req_abc123",
  "op": "exec",
  "payload": {
    "cmd": "uptime"
  }
}
```

### Reply (agent → hub)

```json
{
  "type": "reply",
  "id": "req_abc123",
  "ok": true,
  "result": {
    "stdout": "...",
    "stderr": "",
    "rc": 0,
    "duration_ms": 4
  }
}
```

### Handshake (agent → hub, first message)

```json
{
  "type": "hello",
  "agent_version": "0.1.0",
  "protocol_version": "1.0",
  "host": {
    "hostname": "my-vps",
    "os": "linux",
    "arch": "x86_64"
  },
  "capabilities": ["exec", "edit", "service", "upload", "read", "list", "search", "move", "copy", "delete", "chmod", "chown"],
  "identity_token": "eyJ..."
}
```

The `identity_token` is a JWT issued by the hub at enrollment time, signed
with RS256. Claims: `iss=sentinelx-hub`, `sub=<user_id>`, `host_id=<...>`,
`iat`, `exp`. The hub validates this against its own private key.

## Operations

| `op` | Payload | Reply `result` |
|---|---|---|
| `ping` | `{}` | `{"pong": true}` |
| `capabilities` | `{}` | `{"exec": [...], "services": [...], ...}` |
| `help` | `{}` | `{"text": "..."}` |
| `state` | `{}` | Agent runtime state |
| `exec` | `{"cmd": "..."}` | `{"stdout", "stderr", "rc", "duration_ms"}` |
| `script_run` | `{"interpreter", "content", ...}` | Same as `exec` |
| `service` | `{"name", "action"}` | Same as `exec` |
| `restart` | `{"name"}` | Same as `exec` |
| `edit` | `{"path", "mode", "old", "new_text", ...}` | `{"changes": N, "backup": "..."}` |
| `edit_upload_init` | `{}` | `{"upload_id"}` |
| `edit_upload_file` | `{"upload_id", "role", "data"}` | `{"ok": true}` |
| `edit_upload_complete` | `{"upload_id", "path", "mode", ...}` | Same as `edit` |
| `upload_file` | `{"target_path", "content_base64", ...}` | `{"path", "size_bytes", "sha256"}` |
| `upload_init` | `{"target_path", "size_bytes"}` | `{"upload_id"}` |
| `upload_chunk` | `{"upload_id", "offset", "data"}` | `{"received_bytes"}` |
| `upload_complete` | `{"upload_id"}` | `{"path", "size_bytes", "sha256"}` |
| `read` | `{"path", "view_range"?, "max_bytes"?}` | `{"content", "encoding", "size_bytes", "total_lines", ...}` |
| `list` | `{"path", "depth"?, "glob"?, "show_hidden"?}` | `{"entries": [...], "total", "truncated"}` |
| `search` | `{"path", "pattern", "regex"?, "file_glob"?, ...}` | `{"matches": [...], "files_searched", "truncated"}` |
| `move` | `{"src", "dst", ...}` | `{"src", "dst", "backup"?}` |
| `copy` | `{"src", "dst", ...}` | `{"src", "dst", "backup"?}` |
| `delete` | `{"path", ...}` | `{"path", "backup"}` |
| `chmod` | `{"path", "mode"}` | `{"path", "mode"}` |
| `chown` | `{"path", "owner"?, "group"?}` | `{"path", "owner", "group"}` |

`read`, `list`, and `search` are read-only filesystem primitives; `edit`,
`move`, `copy`, `delete`, `chmod`, and `chown` are writing ones. Unlike
`exec` (gated by a command allowlist) they're all gated on the agent side by
a **path allowlist** (`file_ops` in the agent's config), where each path
declares an `r` or `rw` access level — read-only ops need `r`, writing ops
need `rw`. Destructive ops that overwrite or remove an existing target
report a `backup` path. Implementations live in
[`sentinelx-cloud-core`](https://github.com/pensados/sentinelx-cloud-core)
under `handlers/`; see that repo's README and `THREAT_MODEL.md` for the
security model.

## Python bindings

```python
from sentinelx_protocol import RequestMessage, ReplyMessage, HelloMessage

# Validate an incoming message
msg = RequestMessage.model_validate_json(raw_text)

# Build a reply
reply = ReplyMessage(id=msg.id, ok=True, result={"stdout": "..."})
ws.send(reply.model_dump_json())
```

Bindings are `pydantic` models with strict validation. Both agent and hub
import them from PyPI (TBD) or directly from a git tag.

## Versioning

The `protocol_version` in the handshake follows semver. The hub negotiates:

- **Same major** — fully compatible
- **Different minor** — best-effort, hub may degrade unsupported features
- **Different major** — connection refused

Today we're on `1.0`. The first incompatible change ships as `2.0`.

## Auth boundary

The protocol carries an opaque `identity_token`. The token format and
validation are NOT part of this protocol — they're the hub's responsibility.
This repo only specifies that:

- The hello message includes a string field `identity_token`
- The hub may close the connection with code `4001` ("auth failed") at any
  time

A reference token format is documented in
[`docs/auth.md`](docs/auth.md) (current: RS256 JWT, claims as above).

## Schemas

JSON Schema for every message type is in `schemas/`. Useful if you're
building an agent or hub in a non-Python language.

## Related

- [`sentinelx-cloud-core`](https://github.com/pensados/sentinelx-cloud-core) — reference agent implementation
- [`sentinelx-cloud-installer`](https://github.com/pensados/sentinelx-cloud-installer) — installer for `sentinelx-cloud-core`

## License

Apache 2.0
