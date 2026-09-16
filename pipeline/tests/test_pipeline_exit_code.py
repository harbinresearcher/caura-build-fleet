"""Tests for pipeline exit status."""

import os
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import run_pipeline


_REQUIRED_ENV = {
    "LLM_GATEWAY_API_KEY": "test-key",
    "LLM_GATEWAY_API_URL": "https://example.com/v1",
    "LLM_GATEWAY_MODEL": "test-model",
    "MEMCLAW_API_KEY": "test-key",
    "MEMCLAW_TENANT_ID": "test-tenant",
    "MEMCLAW_FLEET_ID": "test-fleet",
}


def test_exit_code_is_zero_when_all_steps_succeed():
    results = {
        "frontend": {"status": "ok"},
        "performance": {"status": "ok"},
    }

    assert run_pipeline.exit_code(results) == 0


def test_exit_code_is_nonzero_when_any_step_fails():
    results = {
        "frontend": {"status": "ok"},
        "performance": {"status": "error"},
    }

    assert run_pipeline.exit_code(results) == 1


def _prepare_main(monkeypatch, results, *args):
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", *args])
    for name, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(run_pipeline, "print_banner", lambda: None)
    monkeypatch.setattr(run_pipeline, "print_pipeline_table", lambda steps: None)
    monkeypatch.setattr(run_pipeline, "print_summary", lambda result: None)
    monkeypatch.setattr(run_pipeline, "run_pipeline", lambda steps: results)


def test_main_exits_zero_when_all_steps_succeed(monkeypatch):
    _prepare_main(monkeypatch, {"frontend": {"status": "ok"}})

    with pytest.raises(SystemExit) as exc_info:
        run_pipeline.main()

    assert exc_info.value.code == 0


def test_main_exits_nonzero_when_a_step_fails(monkeypatch):
    _prepare_main(monkeypatch, {"frontend": {"status": "error"}})

    with pytest.raises(SystemExit) as exc_info:
        run_pipeline.main()

    assert exc_info.value.code == 1


def test_loop_waits_for_input_after_failed_iteration(monkeypatch):
    _prepare_main(monkeypatch, {"frontend": {"status": "error"}}, "--loop")
    input_mock = Mock(side_effect=KeyboardInterrupt)
    monkeypatch.setattr("builtins.input", input_mock)
    monkeypatch.setattr(run_pipeline, "reset_fleet_memories", lambda: True)

    with pytest.raises(SystemExit) as exc_info:
        run_pipeline.main()

    input_mock.assert_called_once_with()
    assert exc_info.value.code == 1


def _patch_call_tool(monkeypatch, list_result=None, list_error=None, delete_errors=()):
    """Route mcp.call_tool to a stub that answers memclaw_list / memclaw_manage."""
    delete_errors = set(delete_errors)

    def call_tool(name, payload, agent_id=None):
        if name == "memclaw_list":
            if list_error is not None:
                raise list_error
            return list_result
        if name == "memclaw_manage":
            mid = payload["memory_id"]
            if mid in delete_errors:
                raise RuntimeError(f"403 forbidden for {mid}")
            return {"status": "ok"}
        raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(run_pipeline.mcp, "call_tool", call_tool)


def test_reset_reports_success_when_the_fleet_is_already_empty(monkeypatch):
    _patch_call_tool(monkeypatch, list_result={"items": []})

    assert run_pipeline.reset_fleet_memories() is True


def test_reset_reports_success_when_every_delete_succeeds(monkeypatch):
    _patch_call_tool(monkeypatch, list_result={"items": [{"id": "a"}, {"id": "b"}]})

    assert run_pipeline.reset_fleet_memories() is True


def test_reset_reports_failure_when_a_delete_fails(monkeypatch):
    _patch_call_tool(
        monkeypatch, list_result={"items": [{"id": "a"}, {"id": "b"}]}, delete_errors={"b"}
    )

    assert run_pipeline.reset_fleet_memories() is False


def test_reset_reports_failure_when_listing_memories_raises(monkeypatch):
    _patch_call_tool(monkeypatch, list_error=RuntimeError("403 trust too low"))

    assert run_pipeline.reset_fleet_memories() is False


def test_reset_failure_makes_a_reset_run_exit_nonzero(monkeypatch):
    """A --reset that deleted nothing must not look like a successful run."""
    _prepare_main(monkeypatch, {"frontend": {"status": "ok"}}, "--reset")
    monkeypatch.setattr(run_pipeline, "reset_fleet_memories", lambda: False)

    with pytest.raises(SystemExit) as exc_info:
        run_pipeline.main()

    assert exc_info.value.code == 1


def test_failed_reset_stops_the_loop_without_prompting(monkeypatch):
    """A loop must not run a second iteration against a fleet the reset failed to clear."""
    _prepare_main(monkeypatch, {"frontend": {"status": "ok"}}, "--loop")
    input_mock = Mock()
    monkeypatch.setattr("builtins.input", input_mock)
    monkeypatch.setattr(run_pipeline, "reset_fleet_memories", lambda: False)

    with pytest.raises(SystemExit) as exc_info:
        run_pipeline.main()

    input_mock.assert_not_called()
    assert exc_info.value.code == 1

