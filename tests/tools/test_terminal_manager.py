"""Unit tests for TerminalManager behavior."""

# ruff: noqa: E402, I001

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

# libtmux is optional outside sandbox extras; tests use lightweight fakes.
sys.modules.setdefault("libtmux", MagicMock())

import strix.tools.terminal.terminal_manager as terminal_manager_module
from strix.tools.terminal.terminal_manager import TerminalManager, get_terminal_manager


class DummyTerminalSession:
    """Minimal fake terminal session used by TerminalManager unit tests."""

    def __init__(
        self,
        terminal_id: str,
        *,
        execute_result: dict[str, Any] | None = None,
        execute_raises: BaseException | None = None,
        running: bool = True,
        working_dir: str = "/workspace",
        close_raises: BaseException | None = None,
    ) -> None:
        self.terminal_id = terminal_id
        self.execute_result = execute_result or {
            "content": "",
            "status": "completed",
            "exit_code": 0,
            "working_dir": working_dir,
        }
        self.execute_raises = execute_raises
        self.running = running
        self.working_dir = working_dir
        self.close_raises = close_raises
        self.closed = False
        self.execute_calls: list[tuple[str, bool, float, bool]] = []

    def execute(
        self, command: str, is_input: bool, timeout: float, no_enter: bool
    ) -> dict[str, Any]:
        self.execute_calls.append((command, is_input, timeout, no_enter))
        if self.execute_raises:
            raise self.execute_raises
        return dict(self.execute_result)

    def is_running(self) -> bool:
        return self.running

    def get_working_dir(self) -> str:
        return self.working_dir

    def close(self) -> None:
        self.closed = True
        if self.close_raises:
            raise self.close_raises


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch) -> TerminalManager:
    """Create manager with deterministic agent-id and no atexit side-effects."""

    def _noop_register_cleanup_handlers(_self: TerminalManager) -> None:
        return None

    monkeypatch.setattr(terminal_manager_module, "get_current_agent_id", lambda: "agent-1")
    monkeypatch.setattr(
        TerminalManager, "_register_cleanup_handlers", _noop_register_cleanup_handlers
    )
    return TerminalManager()


def test_execute_command_success_payload(
    manager: TerminalManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = DummyTerminalSession(
        "term-1",
        execute_result={
            "content": "ok",
            "status": "completed",
            "exit_code": 0,
            "working_dir": "/tmp/work",
        },
    )
    monkeypatch.setattr(manager, "_get_or_create_session", lambda _: session)

    payload = manager.execute_command("echo ok", timeout=5.0, terminal_id="term-1")

    assert payload == {
        "content": "ok",
        "command": "echo ok",
        "terminal_id": "term-1",
        "status": "completed",
        "exit_code": 0,
        "working_dir": "/tmp/work",
    }
    assert session.execute_calls == [("echo ok", False, 5.0, False)]


def test_execute_command_uses_default_terminal_id_when_not_provided(
    manager: TerminalManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = DummyTerminalSession("default")
    monkeypatch.setattr(manager, "_get_or_create_session", lambda _: session)

    payload = manager.execute_command("pwd")

    assert payload["terminal_id"] == "default"
    assert session.execute_calls == [("pwd", False, 30.0, False)]


def test_execute_command_runtime_error_returns_error_payload(
    manager: TerminalManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = DummyTerminalSession("term-1", execute_raises=RuntimeError("execution failed"))
    monkeypatch.setattr(manager, "_get_or_create_session", lambda _: session)

    payload = manager.execute_command("bad", terminal_id="term-1")

    assert payload == {
        "error": "execution failed",
        "command": "bad",
        "terminal_id": "term-1",
        "content": "",
        "status": "error",
        "exit_code": None,
        "working_dir": None,
    }


def test_execute_command_os_error_returns_system_error_payload(
    manager: TerminalManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = DummyTerminalSession("term-1", execute_raises=OSError("disk unavailable"))
    monkeypatch.setattr(manager, "_get_or_create_session", lambda _: session)

    payload = manager.execute_command("bad", terminal_id="term-1")

    assert payload["status"] == "error"
    assert payload["command"] == "bad"
    assert payload["terminal_id"] == "term-1"
    assert payload["content"] == ""
    assert payload["exit_code"] is None
    assert payload["working_dir"] is None
    assert payload["error"] == "System error: disk unavailable"


def test_get_or_create_session_creates_once_and_reuses_existing(
    manager: TerminalManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_ids: list[str] = []

    def _factory(terminal_id: str) -> DummyTerminalSession:
        created_ids.append(terminal_id)
        return DummyTerminalSession(terminal_id)

    monkeypatch.setattr(terminal_manager_module, "TerminalSession", _factory)

    first = manager._get_or_create_session("terminal-x")
    second = manager._get_or_create_session("terminal-x")

    assert first is second
    assert created_ids == ["terminal-x"]


def test_close_session_missing_terminal_returns_not_found(manager: TerminalManager) -> None:
    payload = manager.close_session("missing")

    assert payload == {
        "terminal_id": "missing",
        "message": "Terminal 'missing' not found",
        "status": "not_found",
    }


def test_close_session_returns_error_when_close_raises(manager: TerminalManager) -> None:
    failing = DummyTerminalSession("term-1", close_raises=RuntimeError("close failure"))
    manager._sessions_by_agent["agent-1"] = {"term-1": failing}

    payload = manager.close_session("term-1")

    assert payload["status"] == "error"
    assert payload["terminal_id"] == "term-1"
    assert payload["error"] == "Failed to close terminal 'term-1': close failure"
    assert manager._sessions_by_agent["agent-1"] == {}
    assert failing.closed is True


def test_close_session_returns_closed_when_successful(manager: TerminalManager) -> None:
    session = DummyTerminalSession("term-1")
    manager._sessions_by_agent["agent-1"] = {"term-1": session}

    payload = manager.close_session("term-1")

    assert payload == {
        "terminal_id": "term-1",
        "message": "Terminal 'term-1' closed successfully",
        "status": "closed",
    }
    assert manager._sessions_by_agent["agent-1"] == {}
    assert session.closed is True


def test_close_session_uses_default_terminal_id_when_not_provided(manager: TerminalManager) -> None:
    session = DummyTerminalSession("default")
    manager._sessions_by_agent["agent-1"] = {"default": session}

    payload = manager.close_session()

    assert payload["terminal_id"] == "default"
    assert payload["status"] == "closed"
    assert session.closed is True


def test_list_sessions_reports_running_state_and_working_dir(manager: TerminalManager) -> None:
    manager._sessions_by_agent["agent-1"] = {
        "live": DummyTerminalSession("live", running=True, working_dir="/tmp/live"),
        "dead": DummyTerminalSession("dead", running=False, working_dir="/tmp/dead"),
    }

    payload = manager.list_sessions()

    assert payload == {
        "sessions": {
            "live": {"is_running": True, "working_dir": "/tmp/live"},
            "dead": {"is_running": False, "working_dir": "/tmp/dead"},
        },
        "total_count": 2,
    }


def test_cleanup_agent_closes_sessions_and_removes_only_target_agent(
    manager: TerminalManager,
) -> None:
    target = {"a": DummyTerminalSession("a"), "b": DummyTerminalSession("b")}
    other = {"x": DummyTerminalSession("x")}
    manager._sessions_by_agent = {"agent-1": target, "agent-2": other}

    manager.cleanup_agent("agent-1")

    assert "agent-1" not in manager._sessions_by_agent
    assert "agent-2" in manager._sessions_by_agent
    assert all(session.closed for session in target.values())
    assert other["x"].closed is False


def test_cleanup_dead_sessions_removes_dead_and_suppresses_close_errors(
    manager: TerminalManager,
) -> None:
    alive = DummyTerminalSession("alive", running=True)
    dead_ok = DummyTerminalSession("dead-ok", running=False)
    dead_err = DummyTerminalSession("dead-err", running=False, close_raises=OSError("boom"))
    manager._sessions_by_agent = {
        "agent-1": {"alive": alive, "dead-ok": dead_ok, "dead-err": dead_err}
    }

    manager.cleanup_dead_sessions()

    assert manager._sessions_by_agent["agent-1"] == {"alive": alive}
    assert dead_ok.closed is True
    assert dead_err.closed is True


def test_close_all_sessions_clears_state_and_suppresses_close_errors(
    manager: TerminalManager,
) -> None:
    ok = DummyTerminalSession("ok")
    err = DummyTerminalSession("err", close_raises=RuntimeError("close failed"))
    manager._sessions_by_agent = {"agent-1": {"ok": ok}, "agent-2": {"err": err}}

    manager.close_all_sessions()

    assert manager._sessions_by_agent == {}
    assert ok.closed is True
    assert err.closed is True


def test_register_cleanup_handlers_registers_close_all_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered: list[Any] = []
    manager = TerminalManager.__new__(TerminalManager)
    monkeypatch.setattr(terminal_manager_module.atexit, "register", registered.append)

    manager._register_cleanup_handlers()

    assert registered == [manager.close_all_sessions]


def test_get_terminal_manager_returns_singleton_instance() -> None:
    manager_a = get_terminal_manager()
    manager_b = get_terminal_manager()

    assert manager_a is manager_b
    assert manager_a is terminal_manager_module._terminal_manager
