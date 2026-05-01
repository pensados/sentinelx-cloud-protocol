"""SentinelX wire protocol — shared between core and hub."""

PROTOCOL_VERSION = "1.0.0"
PROTOCOL_MAJOR = 1

MAX_FRAME_BYTES = 1_048_576  # 1 MB
RECOMMENDED_CHUNK_BYTES = 262_144  # 256 KB
HEARTBEAT_INTERVAL_SECONDS = 30
HEARTBEAT_TIMEOUT_SECONDS = 90

from sentinelx_protocol.messages import (
    ErrorMessage,
    EventMessage,
    HelloMessage,
    HostInfo,
    PingMessage,
    PongMessage,
    RequestMessage,
    ResponseError,
    ResponseMessage,
    WelcomeMessage,
    parse_message,
)

__all__ = [
    "PROTOCOL_VERSION",
    "PROTOCOL_MAJOR",
    "MAX_FRAME_BYTES",
    "RECOMMENDED_CHUNK_BYTES",
    "HEARTBEAT_INTERVAL_SECONDS",
    "HEARTBEAT_TIMEOUT_SECONDS",
    "HelloMessage",
    "HostInfo",
    "WelcomeMessage",
    "RequestMessage",
    "ResponseMessage",
    "ResponseError",
    "PingMessage",
    "PongMessage",
    "EventMessage",
    "ErrorMessage",
    "parse_message",
]
