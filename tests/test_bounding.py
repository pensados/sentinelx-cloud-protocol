"""Tests for sentinelx_protocol.bounding (issue #24, repro C).

Runnable two ways: `pytest` (test_* functions) or directly
`python tests/test_bounding.py` (self-contained assert runner, no pytest dep).
"""
import json

from sentinelx_protocol.bounding import (
    bound_response,
    serialized_size,
    RESPONSE_SOFT_LIMIT_BYTES as SOFT,
    TRUNCATION_KEY,
)


def _env(o):
    return len(json.dumps(o, default=str).encode("utf-8"))


def test_under_limit_passthrough():
    r = {"type": "response", "id": "a", "ok": True,
         "result": {"stdout": "hi", "exit_code": 0}}
    out, meta = bound_response(r)
    assert meta is None
    assert out["result"] == {"stdout": "hi", "exit_code": 0}


def test_huge_ascii_truncates_and_fits():
    r = {"type": "response", "id": "b", "ok": True,
         "result": {"stdout": "x" * 500_000, "stderr": "", "exit_code": 0}}
    out, meta = bound_response(r)
    assert _env(out) <= SOFT
    assert out["ok"] is True
    assert out["result"]["exit_code"] == 0            # sibling preserved
    t = out["result"][TRUNCATION_KEY]
    assert t["response_truncated"] is True
    assert t["execution_status"] == "completed"
    assert t["continuation_available"] is False
    assert t["original_bytes"] > t["delivered_bytes"]
    assert "truncated" in out["result"]["stdout"]     # marker present


def test_error_response_preserves_failure():
    r = {"type": "response", "id": "c", "ok": False,
         "error": {"code": "boom", "message": "E" * 500_000}}
    out, meta = bound_response(r)
    assert _env(out) <= SOFT
    assert out["ok"] is False
    assert out["error"]["code"] == "boom"
    assert meta["execution_status"] == "failed"


def test_non_ascii_delivers_near_budget():
    # euro sign is 3 bytes UTF-8 but escapes to \u20ac (6 bytes) in JSON;
    # proportional shrink must not over-truncate to a few hundred bytes.
    r = {"type": "response", "id": "d", "ok": True,
         "result": {"stdout": "\u20ac" * 200_000}}
    out, meta = bound_response(r)
    assert _env(out) <= SOFT
    assert _env(out) > SOFT * 0.5
    assert isinstance(out["result"]["stdout"], str)   # boundary-safe decode


def test_multiple_large_strings_small_preserved():
    r = {"type": "response", "id": "e", "ok": True,
         "result": {"a": "1" * 300_000, "b": "2" * 300_000,
                    "c": "keep-me", "n": 42}}
    out, meta = bound_response(r)
    assert _env(out) <= SOFT
    assert out["result"]["c"] == "keep-me"
    assert out["result"]["n"] == 42


def test_safety_net_non_string_bloat():
    r = {"type": "response", "id": "f", "ok": True,
         "result": {"nums": list(range(200_000))}}
    out, meta = bound_response(r)
    assert _env(out) <= SOFT
    assert out["result"][TRUNCATION_KEY]["response_truncated"] is True
    assert "note" in out["result"]


def test_nested_string_truncated():
    r = {"type": "response", "id": "g", "ok": True,
         "result": {"outer": {"inner": {"blob": "z" * 400_000}}, "tag": "ok"}}
    out, meta = bound_response(r)
    assert _env(out) <= SOFT
    assert out["result"]["tag"] == "ok"


def test_delivered_bytes_matches_wire():
    r = {"type": "response", "id": "h", "ok": True,
         "result": {"stdout": "y" * 400_000}}
    out, meta = bound_response(r)
    # delivered_bytes is measured AFTER the metadata block is attached, so it
    # matches the real wire size within a couple of bytes (digit growth).
    assert abs(meta["delivered_bytes"] - _env(out)) <= 8
    assert meta["original_bytes"] > SOFT


if __name__ == "__main__":
    import sys
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print("PASS", fn.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL", fn.__name__, "->", repr(e))
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
