"""SentinelX wire protocol — shared between core and hub."""

PROTOCOL_VERSION = "1.10.0"
PROTOCOL_MAJOR = 1

MAX_FRAME_BYTES = 1_048_576  # 1 MB
RECOMMENDED_CHUNK_BYTES = 262_144  # 256 KB
HEARTBEAT_INTERVAL_SECONDS = 30
HEARTBEAT_TIMEOUT_SECONDS = 90

from sentinelx_protocol.messages import (
    ConfigSummary,
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
from sentinelx_protocol.binary import (
    BINARY_HEADER_BYTES,
    MAX_BINARY_FRAME_BYTES,
    TRANSFER_CHUNK_BYTES,
    TRANSFER_ID_BYTES,
    BinaryFrame,
    BinaryFrameError,
    decode_binary_frame,
    encode_binary_frame,
    is_binary_transfer_frame,
)

from sentinelx_protocol.bounding import (
    RESPONSE_SOFT_LIMIT_BYTES,
    RESPONSE_HEAD_RATIO,
    TRUNCATION_KEY,
    bound_response,
    serialized_size,
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
    "ConfigSummary",
    "WelcomeMessage",
    "RequestMessage",
    "ResponseMessage",
    "ResponseError",
    "PingMessage",
    "PongMessage",
    "EventMessage",
    "ErrorMessage",
    "parse_message",
    # response bounding (issue #24, repro C)
    "RESPONSE_SOFT_LIMIT_BYTES",
    "RESPONSE_HEAD_RATIO",
    "TRUNCATION_KEY",
    "bound_response",
    "serialized_size",
    # binary transfer framing (cross-host file transfer)
    "BINARY_HEADER_BYTES",
    "MAX_BINARY_FRAME_BYTES",
    "TRANSFER_CHUNK_BYTES",
    "TRANSFER_ID_BYTES",
    "BinaryFrame",
    "BinaryFrameError",
    "decode_binary_frame",
    "encode_binary_frame",
    "is_binary_transfer_frame",
]
