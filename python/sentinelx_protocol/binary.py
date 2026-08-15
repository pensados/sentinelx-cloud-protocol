"""Binary WebSocket frame framing for cross-host file transfer.

Control messages (requests/responses) stay JSON *text* frames; file bytes
travel as *binary* frames on the same WebSocket. A binary frame is
self-describing so a raw frame knows which transfer and chunk it carries,
decoupled from ordering:

    [ transfer_id : 16 bytes ][ chunk_index : 4 bytes uint32 big-endian ][ payload... ]

The 20-byte header lets either side route a frame without consulting an
interleaved JSON control message. ``transfer_id`` is an opaque 16-byte token
(``uuid4().bytes`` on the Hub side); ``chunk_index`` is 0-based.

This module is intentionally dependency-free (stdlib ``struct`` only) so both
the agent (sentinelx-core) and the Hub (sentinelx-cloud-hub) can import it.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

# Header layout: 16-byte transfer_id + 4-byte big-endian uint32 chunk_index.
TRANSFER_ID_BYTES = 16
CHUNK_INDEX_BYTES = 4
BINARY_HEADER_BYTES = TRANSFER_ID_BYTES + CHUNK_INDEX_BYTES  # 20

# Max raw chunk PAYLOAD carried in one binary frame (1 MiB).
TRANSFER_CHUNK_BYTES = 1_048_576  # 1 MiB

# Max total binary frame size on the wire = payload + header (+ headroom).
# The WebSocket layer must allow at least this: the agent's
# ``websockets.connect(max_size=...)`` on the receive side and the Hub's
# uvicorn ``ws_max_size``. Kept comfortably above chunk+header so a future
# chunk-size bump does not silently exceed the frame cap.
MAX_BINARY_FRAME_BYTES = 2_097_152  # 2 MiB

_CHUNK_INDEX_STRUCT = struct.Struct(">I")  # 4-byte big-endian uint32


class BinaryFrame(NamedTuple):
    """A decoded transfer frame: which transfer, which chunk, the raw bytes."""

    transfer_id: bytes  # exactly TRANSFER_ID_BYTES
    chunk_index: int
    payload: bytes


class BinaryFrameError(ValueError):
    """Raised when a binary frame cannot be encoded or decoded."""


def encode_binary_frame(transfer_id: bytes, chunk_index: int, payload: bytes) -> bytes:
    """Build a wire frame: ``transfer_id || chunk_index || payload``."""
    if len(transfer_id) != TRANSFER_ID_BYTES:
        raise BinaryFrameError(
            f"transfer_id must be {TRANSFER_ID_BYTES} bytes, got {len(transfer_id)}"
        )
    if not 0 <= chunk_index <= 0xFFFFFFFF:
        raise BinaryFrameError(f"chunk_index out of uint32 range: {chunk_index}")
    return bytes(transfer_id) + _CHUNK_INDEX_STRUCT.pack(chunk_index) + bytes(payload)


def decode_binary_frame(frame: bytes) -> BinaryFrame:
    """Parse a wire frame back into ``(transfer_id, chunk_index, payload)``."""
    if len(frame) < BINARY_HEADER_BYTES:
        raise BinaryFrameError(
            f"frame too short: {len(frame)} < {BINARY_HEADER_BYTES} header bytes"
        )
    transfer_id = bytes(frame[:TRANSFER_ID_BYTES])
    (chunk_index,) = _CHUNK_INDEX_STRUCT.unpack(
        frame[TRANSFER_ID_BYTES:BINARY_HEADER_BYTES]
    )
    payload = bytes(frame[BINARY_HEADER_BYTES:])
    return BinaryFrame(transfer_id=transfer_id, chunk_index=chunk_index, payload=payload)


def is_binary_transfer_frame(data: object) -> bool:
    """Cheap guard for WS read loops: is ``data`` a header-sized bytes frame?

    Read loops receive either ``str`` (JSON control) or ``bytes`` (binary
    transfer). A bytes frame at least ``BINARY_HEADER_BYTES`` long is treated
    as a transfer frame; anything shorter is malformed and rejected upstream.
    """
    return isinstance(data, (bytes, bytearray)) and len(data) >= BINARY_HEADER_BYTES
