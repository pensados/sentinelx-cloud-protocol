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


def test_a_long_list_is_trimmed_and_listed_in_the_metadata():
    # The wholesale safety net before 1.13.1; since 1.13.2 nothing is inserted
    # into the list: what was left out is in _truncation["omitted"].
    r = {"type": "response", "id": "f", "ok": True,
         "result": {"nums": list(range(200_000))}}
    out, meta = bound_response(r)
    assert _env(out) <= SOFT
    nums = out["result"]["nums"]
    assert "note" not in out["result"] and all(isinstance(x, int) for x in nums)
    assert nums[:3] == [0, 1, 2]
    (entry,) = meta["omitted"]
    assert entry["path"] == "/nums" and entry["kept"] == len(nums)
    assert entry["kept"] + entry["omitted"] == 200_000


def _capabilities_like():
    # The real shape of an agent's capabilities detail=full: services, locations
    # and playbooks are dicts keyed by name (sxrep_95SMJC6TJ0CE: 393 services).
    services = {f"svc-{i}": {"unit": f"svc-{i}.service", "backend": "service",
                             "actions": ["status", "restart"], "requires_sudo": True,
                             "description": "d" * 150} for i in range(400)}
    playbooks = {f"pb-{i}": {"description": "p" * 200, "steps": [f"step {j} " + "s" * 60 for j in range(40)]}
                 for i in range(13)}
    tooling = {f"tool-{i}": {"doc": "t" * 4000} for i in range(7)}
    return {"agent": "sentinelx-cloud-core", "version": "0.23.10",
            "host": {"hostname": "zen", "arch": "x86_64"},
            "ops_supported": [f"op_{i}" for i in range(40)],
            "allowed_commands": ["ls", "cat", "systemctl"],
            "services": services, "playbooks": playbooks, "tooling": tooling}


def test_a_dict_heavy_capabilities_result_is_trimmed_not_dropped():
    res = _capabilities_like()
    r = {"type": "response", "id": "c", "ok": True, "result": res}
    assert _env(r) > SOFT
    out, meta = bound_response(r)
    got = out["result"]
    assert _env(out) <= SOFT and "note" not in got
    assert got["version"] == "0.23.10" and got["host"]["hostname"] == "zen"
    assert len(got["ops_supported"]) == 40 and got["allowed_commands"] == ["ls", "cat", "systemctl"]
    assert isinstance(got["services"], dict) and 0 < len(got["services"]) < 400
    assert list(got["services"])[0] == "svc-0"
    paths = {e["path"]: e for e in meta["omitted"]}
    assert "/services" in paths and paths["/services"]["kept"] + paths["/services"]["omitted"] == 400


def test_trimmed_containers_keep_their_item_types():
    objs = [{"id": i, "v": "x" * 100} for i in range(5000)]
    r = {"type": "response", "id": "t", "ok": True, "result": {"objs": objs}}
    out, meta = bound_response(r)
    assert all(isinstance(o, dict) for o in out["result"]["objs"])


def test_a_container_trimmed_twice_keeps_its_original_total():
    from sentinelx_protocol.bounding import _shrink_largest
    root = {"a": list(range(5000)), "b": "y" * 10}
    env = {"result": root}
    omitted = {}
    assert _shrink_largest(root, 1500, env, omitted)
    entry = omitted[("a",)]
    assert entry["total"] == 5000 and entry["kept"] == len(root["a"])


def test_the_omitted_list_is_capped():
    import sentinelx_protocol.bounding as bnd
    saved = bnd._OMITTED_MAX_ENTRIES
    bnd._OMITTED_MAX_ENTRIES = 1
    try:
        r = {"type": "response", "id": "m", "ok": True,
             "result": {"a": list(range(100_000)), "b": list(range(100_000))}}
        out, meta = bound_response(r)
    finally:
        bnd._OMITTED_MAX_ENTRIES = saved
    assert _env(out) <= SOFT
    assert len(meta["omitted"]) == 1 and meta["omitted_more"] == 1


def test_untrimmable_bloat_still_falls_back_to_a_note():
    r = {"type": "response", "id": "u", "ok": True,
         "result": {f"k{i}": i for i in range(40_000)}}
    out, meta = bound_response(r)
    assert _env(out) <= SOFT
    assert "note" in out["result"] and out["result"][TRUNCATION_KEY]["response_truncated"] is True


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
