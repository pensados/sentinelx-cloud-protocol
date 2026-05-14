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
    # policy.file_ops_allowed_read_paths on the agent side.
    "read",
    "list",
    "search",
]


# --- Host info -----------------------------------------------------------------

class HostInfo(BaseModel):
    """Information about the host where sentinelx-core is running."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Unique host identifier (generated at install)")
    hostname: str
    os: str = "linux"
    kernel: str | None = None
    arch: str | None = None


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
