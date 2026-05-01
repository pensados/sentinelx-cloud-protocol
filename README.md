# sentinelx-cloud-protocol

The wire format shared between [`sentinelx-cloud-core`](https://github.com/pensados/sentinelx-cloud-core) (the agent on a user's server) and the SentinelX hub.

This repo is the source of truth for the WebSocket protocol. It contains no business logic — only the spec, JSON schemas, and typed bindings that both sides import.

---

## What's in here

- **`messages.md`** — prose specification of the protocol (read this first if you want to understand it)
- **`schemas/`** — JSON Schemas for each message type
- **`python/`** — Python bindings as Pydantic v2 models
- **`CHANGELOG.md`** — semantic version history

---

## Quick reference

The protocol is a small set of typed JSON messages exchanged over a single WebSocket connection per agent.

```
Agent → Hub                  Hub → Agent
─────────────                ─────────────
HelloMessage      ────▶
                  ◀────      WelcomeMessage
PongMessage       ────▶      PingMessage    (heartbeat, ~every 30s)
ResponseMessage   ◀────      RequestMessage (op invocation)
EventMessage      ────▶                     (unsolicited notifications)
                  ◀────      ErrorMessage   (protocol-level errors)
```

A typical session:

1. Agent connects to `wss://hub/agent/connect?token=<enrollment_jwt>`
2. Hub validates the JWT, replies on success — agent sends `HelloMessage` declaring its `protocol_version`, capabilities, and host info
3. Hub responds with `WelcomeMessage` echoing accepted heartbeat interval and session id
4. From here on: hub sends `RequestMessage`, agent runs the op, agent sends back `ResponseMessage` with matching `request_id`
5. Hub periodically sends `PingMessage`, agent replies `PongMessage`. Either side disconnects after `HEARTBEAT_TIMEOUT_SECONDS` of silence.

---

## Versioning

The protocol uses [SemVer](https://semver.org/):

- **MAJOR** — breaking change (an old core can't talk to a new hub)
- **MINOR** — additive change (new optional fields, new message types). Backward compatible.
- **PATCH** — doc clarifications, schema fixes with no functional change

The current version is exposed as `PROTOCOL_VERSION` in `sentinelx_protocol/__init__.py`.

The hub accepts any MINOR within its current MAJOR. When a core handshakes with a different MAJOR, the hub rejects it with `code: protocol_version_mismatch` and tells the core to upgrade.

---

## Use it from another project

```bash
pip install "git+https://github.com/pensados/sentinelx-cloud-protocol.git@v1.0.0"
```

```python
from sentinelx_protocol import (
    PROTOCOL_VERSION,
    HelloMessage, HostInfo,
    RequestMessage, ResponseMessage,
    parse_message,
)

# Construct a hello at the start of a connection
hello = HelloMessage(
    protocol_version=PROTOCOL_VERSION,
    agent_version="0.1.0",
    host=HostInfo(id="host_abc123", hostname="my-server"),
    capabilities=["ping", "exec", "state"],
)

# Parse anything that comes off the wire
incoming = parse_message(json.loads(raw_text))
match incoming:
    case RequestMessage(op="exec", payload=p):
        ...
```

---

## Constants

| Name | Value | Meaning |
|---|---|---|
| `PROTOCOL_VERSION` | `1.0.0` | Current SemVer string |
| `PROTOCOL_MAJOR` | `1` | Current major (compatibility boundary) |
| `MAX_FRAME_BYTES` | `1_048_576` | 1 MB hard cap on a single WS frame |
| `RECOMMENDED_CHUNK_BYTES` | `262_144` | 256 KB suggested chunk size for streaming uploads |
| `HEARTBEAT_INTERVAL_SECONDS` | `30` | How often hub sends ping |
| `HEARTBEAT_TIMEOUT_SECONDS` | `90` | When to consider the peer dead |

---

## Related repos

- [`sentinelx-cloud-core`](https://github.com/pensados/sentinelx-cloud-core) — the agent
- [`sentinelx-cloud-installer`](https://github.com/pensados/sentinelx-cloud-installer) — one-line installer

---

## License

Apache 2.0. See [`LICENSE`](./LICENSE).
