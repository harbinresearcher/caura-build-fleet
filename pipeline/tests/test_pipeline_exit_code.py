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
    monkeypatch.setattr(run_pipeline, "reset_fleet_memories", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        run_pipeline.main()

    input_mock.assert_called_once_with()
    assert exc_info.value.code == 1
