"""Data-isolation reporting vs. allowlist-denied tool calls.

`agent_base.run_agent()` records a call refused by the allowlist with the tool's
real name and `status: "denied"`, so that the attempt stays visible:

    {"tool": "memclaw_write", "status": "denied", ...}

The isolation checks must not read that as a write. "Attempted, blocked, nothing
written" and "wrote to the store" are opposite outcomes, and the whole point of
denying the call is that nothing reached `mcp_client`. Counting it would make the
Manager's own report fail loudest exactly when the enforcement worked.

Run:  cd pipeline && pytest tests/test_isolation_denied.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("MEMCLAW_API_KEY", "test-key")
os.environ.setdefault("MEMCLAW_TENANT_ID", "test-tenant")
os.environ.setdefault("MEMCLAW_FLEET_ID", "test-fleet")
os.environ.setdefault("LLM_GATEWAY_API_KEY", "test-llm-key")

from unittest.mock import patch  # noqa: E402

import manager  # noqa: E402


def _run_manager(tool_calls, caplog):
    with patch(
        "agent_base.run_agent",
        return_value={
            "agent_id": "manager-tenant",
            "final_text": "audit",
            "tool_calls": tool_calls,
            "iterations": 1,
        },
    ):
        with caplog.at_level("INFO"):
            return manager.run()


def test_denied_write_keeps_isolation_verified(caplog):
    """A blocked write attempt is not a write."""
    _run_manager(
        [
            {"tool": "memclaw_list", "status": "ok"},
            {"tool": "memclaw_write", "status": "denied"},
        ],
        caplog,
    )
    assert "Data isolation VERIFIED" in caplog.text
    assert "unexpected write call(s)" not in caplog.text


def test_denied_write_still_appears_in_tool_calls(caplog):
    """The attempt stays visible — it is only excluded from the write count."""
    result = _run_manager(
        [
            {"tool": "memclaw_list", "status": "ok"},
            {"tool": "memclaw_write", "status": "denied"},
        ],
        caplog,
    )
    logged = [c["tool"] for c in result["tool_calls"]]
    assert "memclaw_write" in logged, "the denied attempt must remain in the log"
    # ...and it is still reported in the usage summary.
    assert "memclaw_write" in caplog.text


def test_successful_write_still_reports_violation(caplog):
    """A write that actually executed is still a violation."""
    _run_manager(
        [
            {"tool": "memclaw_list", "status": "ok"},
            {"tool": "memclaw_write", "status": "ok"},
        ],
        caplog,
    )
    assert "unexpected write call(s) detected" in caplog.text
    assert "Data isolation VERIFIED" not in caplog.text


def test_denied_manage_keeps_isolation_verified(caplog):
    """Only `denied` is exempt; other statuses still count."""
    _run_manager(
        [
            {"tool": "memclaw_list", "status": "ok"},
            {"tool": "memclaw_manage", "status": "denied"},
        ],
        caplog,
    )
    assert "Data isolation VERIFIED" in caplog.text


def test_non_denied_write_statuses_count(caplog):
    """`error` and `parse_error` are not exemptions — only an allowlist denial is."""
    for status in ("ok", "error", "parse_error"):
        caplog.clear()
        _run_manager(
            [
                {"tool": "memclaw_list", "status": "ok"},
                {"tool": "memclaw_write", "status": status},
            ],
            caplog,
        )
        assert "unexpected write call(s) detected" in caplog.text, status
