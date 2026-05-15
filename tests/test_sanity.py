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
