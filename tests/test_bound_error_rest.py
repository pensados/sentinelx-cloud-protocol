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


def test_the_schema_refuses_ids_and_codes_bound_response_cannot_trim():
    with pytest.raises(ValidationError):
        RequestMessage.model_validate({"type": "request", "id": "i" * (MAX_ID_LENGTH + 1), "op": "ping", "params": {}})
    with pytest.raises(ValidationError):
        ResponseMessage.model_validate({"type": "response", "id": "i" * (MAX_ID_LENGTH + 1), "ok": True, "result": {}})
    with pytest.raises(ValidationError):
        ResponseError.model_validate({"code": "c" * (MAX_ERROR_CODE_LENGTH + 1), "message": "m"})
    ResponseMessage.model_validate({"type": "response", "id": "i" * MAX_ID_LENGTH, "ok": True, "result": {}})
