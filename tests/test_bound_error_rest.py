"""bound_response bounds the whole error, and the schema the fields it can't trim
(1.13.4, sxrep_TRP3VXQ98XNC reopened)."""
import pytest
from pydantic import ValidationError

from sentinelx_protocol.bounding import RESPONSE_SOFT_LIMIT_BYTES, bound_response, serialized_size
from sentinelx_protocol.messages import (MAX_ERROR_CODE_LENGTH, MAX_ID_LENGTH, RequestMessage,
                                         ResponseError, ResponseMessage)


def _envelope(details, result=None):
    r = {"type": "response", "id": "req-1", "ok": False,
         "error": {"code": "command_not_allowed", "message": "not allowed", "details": details}}
    if result is not None:
        r["result"] = result
    return r


@pytest.mark.parametrize("result", [None, {"a": 1}])
def test_a_huge_command_echoed_in_details_is_bounded(result):
    r, _ = bound_response(_envelope({"command": "x" * 300_000}, result))
    assert serialized_size(r) <= RESPONSE_SOFT_LIMIT_BYTES
    assert (r["type"], r["id"], r["ok"], r["error"]["code"]) == ("response", "req-1", False, "command_not_allowed")


def test_details_with_many_small_keys_are_trimmed_and_say_so():
    r, _ = bound_response(_envelope({f"k{i}": i for i in range(60_000)}))
    assert serialized_size(r) <= RESPONSE_SOFT_LIMIT_BYTES
    d = r["error"]["details"]
    assert "truncated" in d or "omitted" in d, "trimmed details must not pass for complete"


def test_a_long_code_is_cut_to_the_schema_maximum():
    env = _envelope({"command": "x" * 300_000})
    env["error"]["code"] = "c" * 50_000
    r, _ = bound_response(env)
    assert len(r["error"]["code"]) == MAX_ERROR_CODE_LENGTH and serialized_size(r) <= RESPONSE_SOFT_LIMIT_BYTES


def _an_op():
    import enum
    import typing

    from sentinelx_protocol.messages import OpType
    if isinstance(OpType, type) and issubclass(OpType, enum.Enum):
        return next(iter(OpType)).value
    return typing.get_args(OpType)[0]


def test_the_schema_refuses_ids_and_codes_bound_response_cannot_trim():
    ok = {"type": "request", "id": "i" * MAX_ID_LENGTH, "op": _an_op(), "payload": {}}
    RequestMessage.model_validate(ok)          # the limit itself is accepted
    with pytest.raises(ValidationError):
        RequestMessage.model_validate({**ok, "id": "i" * (MAX_ID_LENGTH + 1)})
    ResponseMessage.model_validate({"type": "response", "id": "i" * MAX_ID_LENGTH, "ok": True, "result": {}})
    with pytest.raises(ValidationError):
        ResponseMessage.model_validate({"type": "response", "id": "i" * (MAX_ID_LENGTH + 1), "ok": True, "result": {}})
    with pytest.raises(ValidationError):
        ResponseError.model_validate({"code": "c" * (MAX_ERROR_CODE_LENGTH + 1), "message": "m"})


def test_the_result_survives_a_huge_details():
    r, _ = bound_response(_envelope({"command": "x" * 300_000}, {"exit_code": 2, "stderr": "boom"}))
    assert serialized_size(r) <= RESPONSE_SOFT_LIMIT_BYTES
    assert r["result"].get("exit_code") == 2 and r["result"].get("stderr") == "boom", r["result"]
    d = r["error"]["details"]
    assert "truncated" in d or "omitted" in d


def test_a_long_code_is_cut_even_in_a_small_response():
    env = _envelope({"x": 1})
    env["error"]["code"] = "c" * 500
    r, _ = bound_response(env)
    assert len(r["error"]["code"]) == MAX_ERROR_CODE_LENGTH
