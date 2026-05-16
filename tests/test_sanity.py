"""Sanity check that the package imports cleanly and exposes its public API.

This repo is a pure protocol package — types and constants. The real
behavior is exercised by the consumers (sentinelx-cloud-core and
sentinelx-cloud-hub). But pytest needs at least one test to return a
healthy exit code, and there's value in verifying that the package
loads without errors and that __all__ stays consistent with what's
actually exported.
"""

from __future__ import annotations


def test_package_imports() -> None:
    """Importing the package must succeed without side effects or errors."""
    import sentinelx_protocol  # noqa: F401


def test_public_api_is_exported() -> None:
    """Every name in __all__ must be a real attribute of the package."""
    import sentinelx_protocol

    missing = [name for name in sentinelx_protocol.__all__
               if not hasattr(sentinelx_protocol, name)]
    assert not missing, f"declared in __all__ but not exported: {missing}"


def test_message_ops_include_filesystem_primitives() -> None:
    """The OpType Literal should include the Story 6 ops (read/list/search).

    This guards against a regression where a future refactor of
    RequestMessage drops one of the file-primitive ops without noticing.
    """
    from typing import get_args

    from sentinelx_protocol.messages import RequestMessage

    op_field = RequestMessage.model_fields["op"]
    ops = set(get_args(op_field.annotation))

    for required in ("read", "list", "search"):
        assert required in ops, f"OpType is missing '{required}'"


def test_message_ops_include_mutating_filesystem_ops() -> None:
    """The OpType Literal must include the unified file-ops mutating ops.

    These are gated on the agent side by the file_ops r/rw path model
    (they only resolve under an access: rw path). This test guards
    against a refactor silently dropping one of them from the wire
    contract — which would make the corresponding hub tool undeliverable.
    """
    from typing import get_args

    from sentinelx_protocol.messages import RequestMessage

    op_field = RequestMessage.model_fields["op"]
    ops = set(get_args(op_field.annotation))

    for required in ("move", "copy", "delete", "chmod", "chown"):
        assert required in ops, f"OpType is missing '{required}'"


def test_request_message_parses_new_ops() -> None:
    """A RequestMessage with each new op must validate cleanly.

    payload stays an open dict[str, Any] by design (each side validates
    its own shape), so here we only assert the op string is accepted by
    the Literal and the envelope round-trips through the generic parser.
    """
    from sentinelx_protocol.messages import RequestMessage, parse_message

    for op in ("move", "copy", "delete", "chmod", "chown"):
        msg = RequestMessage(id="req-1", op=op, payload={"path": "/tmp/x"})
        assert msg.op == op
        parsed = parse_message(msg.model_dump(mode="json"))
        assert isinstance(parsed, RequestMessage)
        assert parsed.op == op
