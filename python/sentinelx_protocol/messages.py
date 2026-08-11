"""Pydantic models for SentinelX protocol messages.

These are the wire format. Both core and hub import from here to ensure
they're speaking the same language.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# --- Operation types -----------------------------------------------------------

OpType = Literal[
    "ping",
    "capabilities",
    "help",
    "state",
    "exec",
    "script_run",
    "edit",
    "edit_upload_init",
    "edit_upload_file",
    "edit_upload_complete",
    "restart",
    "service",
    "upload_init",
    "upload_chunk",
    "upload_complete",
    "upload_file",
    # File primitives (Story 6) — read-only filesystem ops constrained by
    # the file_ops path model on the agent side. With the unified r/rw
    # model these resolve under any file_ops path (r or rw).
    "read",
    "list",
    "search",
    # Local audit log (Story C) — read-only. Returns recent entries from the
    # agent's own on-host audit log (/var/lib/sentinelx/audit.jsonl), which
    # records each executed op WITH its payload. Unlike the hub's metadata
    # ring buffer, this is the only place the actual command/payload lives,
    # and it never leaves the host except in response to this op. Metadata is
    # returned as-is (no redaction) — the log is the host owner's own record.
    "read_audit",
    # Mutating filesystem ops (file-ops unificadas). These resolve ONLY
    # under a file_ops path declared access: rw on the agent side. The
    # agent canonicalizes the path (symlinks included) before checking,
    # so a hostile hub/LLM cannot escape the rw allowlist. Destructive
    # ops (delete, and move/copy that overwrite a destination) take an
    # automatic timestamped backup before mutating.
    "move",
    "copy",
    "delete",
    "chmod",
    "chown",
]


# --- Host info -----------------------------------------------------------------

class ConfigSummary(BaseModel):
    """Counts summarizing a host's policy — safe to expose to admins.

    These are aggregates only (how many, not which), so they reveal a
    host's posture (a power user with 100+ commands vs a locked-down new
    install) without leaking the actual command list, paths, or service
    names. The full lists stay on the host and are only shown to the host's
    own owner through a separate on-demand channel, never in this hello.

    All fields optional so an older hub that somehow receives this (or a
    partial summary) degrades gracefully.
    """

    model_config = ConfigDict(extra="forbid")

    allowed_command_count: int | None = None
    file_ops_path_count: int | None = None
    file_ops_rw_count: int | None = None
    service_count: int | None = None
    playbook_count: int | None = None
    trusted_fetch_host_count: int | None = None
    exec_timeout_default: int | None = None
    exec_timeout_max: int | None = None


class HostInfo(BaseModel):
    """Information about the host where sentinelx-core is running."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Unique host identifier (generated at install)")
    hostname: str
    os: str = "linux"
    kernel: str | None = None
    arch: str | None = None
    # Machine details (optional; older agents omit them). Gathered
    # best-effort at connect; any field the agent cannot determine is None.
    cpu_model: str | None = None
    cpu_cores: int | None = None
    mem_total_bytes: int | None = None
    disk_total_bytes: int | None = None
    machine_type: str | None = None  # physical | vm | container | wsl
    distro: str | None = None
    # Policy summary (counts only). Optional: older agents omit it, and the
    # hub treats a missing summary as "unknown" rather than an error.
    config_summary: ConfigSummary | None = None


# --- Connection lifecycle ------------------------------------------------------

class HelloMessage(BaseModel):
    """First message after WS handshake. core → hub."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["hello"] = "hello"
    protocol_version: str
    agent_version: str
    host: HostInfo
    capabilities: list[str] = Field(default_factory=list)


class WelcomeMessage(BaseModel):
    """Hub acknowledges hello and registers the agent."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["welcome"] = "welcome"
    session_id: str
    server_time: datetime
    heartbeat_interval_seconds: int = 30


# --- Request / Response --------------------------------------------------------

class RequestMessage(BaseModel):
    """Hub → core: execute an operation."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["request"] = "request"
    id: str
    op: OpType
    payload: dict[str, Any] = Field(default_factory=dict)
    deadline: datetime | None = None


class ResponseError(BaseModel):
    """Error details inside a response."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] | None = None


class ResponseMessage(BaseModel):
    """Core → hub: result of a request."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["response"] = "response"
    id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: ResponseError | None = None


# --- Heartbeat -----------------------------------------------------------------

class PingMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["ping"] = "ping"
    timestamp: datetime


class PongMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["pong"] = "pong"
    timestamp: datetime


# --- Async events --------------------------------------------------------------

class EventMessage(BaseModel):
    """Core → hub: async notification, no response expected."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["event"] = "event"
    kind: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


# --- Fatal errors --------------------------------------------------------------

class ErrorMessage(BaseModel):
    """Hub → core: fatal protocol error, WS will close."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["error"] = "error"
    code: str
    message: str
    fatal: bool = True


# --- Parser --------------------------------------------------------------------

AnyMessage = (
    HelloMessage
    | WelcomeMessage
    | RequestMessage
    | ResponseMessage
    | PingMessage
    | PongMessage
    | EventMessage
    | ErrorMessage
)

_MESSAGE_TYPES: dict[str, type[BaseModel]] = {
    "hello": HelloMessage,
    "welcome": WelcomeMessage,
    "request": RequestMessage,
    "response": ResponseMessage,
    "ping": PingMessage,
    "pong": PongMessage,
    "event": EventMessage,
    "error": ErrorMessage,
}


class UnknownMessageTypeError(ValueError):
    """Raised when a message has a type we don't recognize."""


def parse_message(data: dict[str, Any]) -> AnyMessage:
    """Parse a raw dict into the appropriate message model.

    Raises:
        UnknownMessageTypeError: if `type` field is missing or unknown.
        pydantic.ValidationError: if the payload doesn't match the schema.
    """
    msg_type = data.get("type")
    if not msg_type or msg_type not in _MESSAGE_TYPES:
        raise UnknownMessageTypeError(f"Unknown message type: {msg_type!r}")
    return _MESSAGE_TYPES[msg_type].model_validate(data)  # type: ignore[return-value]
