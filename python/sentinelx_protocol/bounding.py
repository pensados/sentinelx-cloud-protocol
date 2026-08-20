"""Outbound response payload bounding — shared by core (agent) and hub.

Issue #24, repro C: a handler can produce a result too large for the WebSocket
frame. The transport then closes with code 1009 ("message too big") and the
response is lost even though the operation already executed. This module bounds
an outbound response *before* it is sent, so an executed operation is never
turned into a delivery failure: it truncates the largest string leaves inside
``result`` (keeping a head and a tail) and attaches truncation metadata.

Contract (mirrors the existing fileops ``truncated`` precedent)::

    result["_truncation"] = {
        "response_truncated": True,
        "original_bytes": <int>,          # serialized envelope size before bounding
        "delivered_bytes": <int>,         # serialized envelope size after bounding
        "continuation_available": False,  # v1: honest truncation, no fetch-the-rest
        "execution_status": "completed" | "failed",  # the op ran regardless
    }

The soft limit sits well below the ~1 MiB websockets default inbound ceiling
(:data:`MAX_FRAME_BYTES`) that triggers the observed 1009. Shared by core and
hub so the limit and the metadata contract cannot drift. See BookStack page 42.

Sizing note: :func:`serialized_size` mirrors the agent's wire send at
client.py — ``json.dumps(response, default=str)`` (``ensure_ascii=True``), so
sizing is exact on that path. A caller that serializes differently (e.g. the hub
via pydantic ``model_dump_json``, which does not escape non-ASCII) will size
conservatively, never under.
"""
from __future__ import annotations

import json
from typing import Any

__all__ = [
    "RESPONSE_SOFT_LIMIT_BYTES",
    "RESPONSE_HEAD_RATIO",
    "TRUNCATION_KEY",
    "bound_response",
    "serialized_size",
]

# Soft limit for a serialized response envelope on the wire, in bytes. Well below
# MAX_FRAME_BYTES (~1 MiB) so a bounded frame never trips the 1009 ceiling.
# Validated locally at ~132 KiB (BookStack page 33). Named constant on purpose.
RESPONSE_SOFT_LIMIT_BYTES = 131_072  # 128 KiB

# Of the bytes retained from a truncated string, the fraction kept from the head
# (the remainder is kept from the tail). Head-biased: orientation up front, the
# most recent / actionable lines at the end.
RESPONSE_HEAD_RATIO = 0.6

# Key under which truncation metadata is attached inside ``result``.
TRUNCATION_KEY = "_truncation"

# Room reserved (bytes) for the metadata block added after trimming.
_META_RESERVE = 512
# Undershoot factor: recut slightly below target so we converge in few passes.
_SHRINK_SLACK = 0.95
# Hard ceiling on truncation passes, so a pathological payload can never spin.
_MAX_PASSES = 64
# Smallest string worth truncating; below this, trimming buys nothing.
_MIN_TRUNCATABLE = 256


def serialized_size(payload: Any) -> int:
    """Byte length of ``payload`` serialized the way the agent's wire send does."""
    return len(json.dumps(payload, default=str).encode("utf-8"))


def _marker(omitted: int) -> str:
    return f"\n\u2026[sentinelx: truncated {omitted} bytes]\u2026\n"


def _truncate_text(text: str, keep_bytes: int) -> str:
    """Keep a head+tail slice of ``text`` fitting roughly ``keep_bytes`` raw
    UTF-8 bytes. Cuts on character boundaries (``errors="ignore"`` drops a
    partial char at the seam) and inserts a marker naming the dropped bytes."""
    raw = text.encode("utf-8")
    original = len(raw)
    if original <= keep_bytes or keep_bytes <= 0:
        return text
    head_budget = int(keep_bytes * RESPONSE_HEAD_RATIO)
    tail_budget = keep_bytes - head_budget
    head = raw[:head_budget].decode("utf-8", errors="ignore")
    tail = raw[original - tail_budget:].decode("utf-8", errors="ignore") if tail_budget > 0 else ""
    omitted = original - len(head.encode("utf-8")) - len(tail.encode("utf-8"))
    return head + _marker(omitted) + tail


def _largest_string_ref(node: Any):
    """Return ``(container, key, raw_utf8_len)`` of the largest truncatable
    string leaf reachable from ``node`` (descending dicts and lists), or
    ``None``. Iterative DFS — safe on deep structures."""
    best = None
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            items = cur.items()
        elif isinstance(cur, list):
            items = enumerate(cur)
        else:
            continue
        for key, val in items:
            if isinstance(val, str):
                n = len(val.encode("utf-8"))
                if n >= _MIN_TRUNCATABLE and (best is None or n > best[2]):
                    best = (cur, key, n)
            elif isinstance(val, (dict, list)):
                stack.append(val)
    return best


def _shrink_largest(root: Any, budget: int, envelope: dict) -> bool:
    """Proportionally shrink the largest string leaf under ``root`` so the whole
    ``envelope`` trends toward ``budget``. Proportional (not byte-subtractive)
    so it converges for non-ASCII too, where JSON escaping makes serialized cost
    differ from raw UTF-8 length. Returns False when nothing is left to trim."""
    for _ in range(_MAX_PASSES):
        cur = serialized_size(envelope)
        if cur <= budget:
            return True
        ref = _largest_string_ref(root)
        if ref is None:
            return False
        container, key, n = ref
        keep = int(n * (budget / cur) * _SHRINK_SLACK)
        keep = max(_MIN_TRUNCATABLE, min(keep, n - 1))
        container[key] = _truncate_text(container[key], keep)
    return serialized_size(envelope) <= budget


def bound_response(response: dict, soft_limit: int = RESPONSE_SOFT_LIMIT_BYTES):
    """Bound a response envelope dict so its serialized size fits ``soft_limit``.

    ``response`` is the wire dict ``{"type","id","ok","result"?,"error"?}``.
    Returns ``(response, meta)`` — ``meta`` is the truncation metadata dict if
    bounding happened, else ``None``. The input is mutated in place (and also
    returned). ``ok``/``type``/``id``/``error`` are always preserved — an
    executed op is never turned into a delivery failure."""
    original = serialized_size(response)
    if original <= soft_limit:
        return response, None

    budget = soft_limit - _META_RESERVE
    ok = bool(response.get("ok", False))
    execution_status = "completed" if ok else "failed"
    result = response.get("result")

    def _meta() -> dict:
        return {
            "response_truncated": True,
            "original_bytes": original,
            "delivered_bytes": serialized_size(response),
            "continuation_available": False,
            "execution_status": execution_status,
        }

    if isinstance(result, dict):
        if not _shrink_largest(result, budget, response):
            # Safety net: bloat we cannot trim field-wise (huge nested non-string
            # structure). Replace result wholesale so something valid and
            # under-limit always ships.
            result = {"note": "result omitted: too large to bound field-wise"}
            response["result"] = result
        meta = _meta()
        result[TRUNCATION_KEY] = meta
        meta["delivered_bytes"] = serialized_size(response)
        return response, meta

    # No result dict to hang metadata on. Bound a large error message in place
    # (same proportional loop), then expose metadata as a minimal result.
    error = response.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        _shrink_largest(error, budget, response)
    meta = _meta()
    if response.get("result") is None:
        response["result"] = {TRUNCATION_KEY: meta}
    meta["delivered_bytes"] = serialized_size(response)
    return response, meta
