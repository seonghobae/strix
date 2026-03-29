"""Unit tests for PythonSessionManager behavior."""

from __future__ import annotations

from typing import Any

import pytest

import strix.tools.python.python_manager as python_manager_module
from strix.tools.python.python_manager import PythonSessionManager, get_python_session_manager


class DummySession:
    """Lightweight fake Python session used for manager unit tests."""

    def __init__(
        self,
        session_id: str,
        *,
        execute_result: dict[str, Any] | None = None,
        is_running: bool = True,
        is_alive: bool = True,
        close_raises: bool = False,
    ) -> None:
        self.session_id = session_id
        self.execute_result = execute_result or {
            "session_id": session_id,
            "stdout": "",
            "stderr": "",
            "result": None,
        }
        self.is_running = is_running
        self._is_alive = is_alive
        self.close_raises = close_raises
        self.closed = False
        self.execute_calls: list[tuple[str, int]] = []

    def execute_code(self, code: str, timeout: int) -> dict[str, Any]:
        self.execute_calls.append((code, timeout))
        return dict(self.execute_result)

    def close(self) -> None:
        self.closed = True
        if self.close_raises:
            raise RuntimeError("close failed")

    def is_alive(self) -> bool:
        return self._is_alive


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch) -> PythonSessionManager:
    """Build a manager with deterministic agent-id and no atexit side effects."""
    monkeypatch.setattr(python_manager_module, "get_current_agent_id", lambda: "agent-1")
    monkeypatch.setattr(python_manager_module.atexit, "register", lambda _: None)
    return PythonSessionManager()


def test_create_session_default_id(
    monkeypatch: pytest.MonkeyPatch, manager: PythonSessionManager
) -> None:
    created_ids: list[str] = []

    def _factory(session_id: str) -> DummySession:
        created_ids.append(session_id)
        return DummySession(session_id)

    monkeypatch.setattr(python_manager_module, "PythonInstance", _factory)

    payload = manager.create_session()

    assert payload == {
        "session_id": "default",
        "message": "Python session 'default' created successfully",
    }
    assert created_ids == ["default"]


def test_create_session_explicit_id(
    monkeypatch: pytest.MonkeyPatch, manager: PythonSessionManager
) -> None:
    def _factory(session_id: str) -> DummySession:
        return DummySession(session_id)

    monkeypatch.setattr(
        python_manager_module,
        "PythonInstance",
        _factory,
    )

    payload = manager.create_session("custom")

    assert payload["session_id"] == "custom"
    assert payload["message"] == "Python session 'custom' created successfully"


def test_create_session_duplicate_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
    manager: PythonSessionManager,
) -> None:
    def _factory(session_id: str) -> DummySession:
        return DummySession(session_id)

    monkeypatch.setattr(
        python_manager_module,
        "PythonInstance",
        _factory,
    )

    manager.create_session("dup")

    with pytest.raises(ValueError, match="already exists"):
        manager.create_session("dup")


def test_create_session_with_initial_code_appends_success_message(
    monkeypatch: pytest.MonkeyPatch,
    manager: PythonSessionManager,
) -> None:
    session = DummySession("s1", execute_result={"session_id": "s1", "stdout": "ok", "stderr": ""})
    monkeypatch.setattr(python_manager_module, "PythonInstance", lambda _: session)

    payload = manager.create_session("s1", initial_code="print(1)", timeout=9)

    assert session.execute_calls == [("print(1)", 9)]
    assert payload["message"] == "Python session 's1' created successfully with initial code"
    assert payload["stdout"] == "ok"


@pytest.mark.parametrize("code", [None, ""])
def test_execute_code_without_code_raises_value_error(
    manager: PythonSessionManager,
    code: str | None,
) -> None:
    with pytest.raises(ValueError, match="No code provided"):
        manager.execute_code("default", code=code)


def test_execute_code_missing_session_raises_value_error(manager: PythonSessionManager) -> None:
    with pytest.raises(ValueError, match="not found"):
        manager.execute_code("missing", code="print(1)")


def test_execute_code_success_appends_message(manager: PythonSessionManager) -> None:
    session = DummySession("s1", execute_result={"session_id": "s1", "stdout": "42", "stderr": ""})
    manager._sessions_by_agent["agent-1"] = {"s1": session}

    payload = manager.execute_code("s1", "print(42)", timeout=5)

    assert payload["stdout"] == "42"
    assert payload["message"] == "Code executed in session 's1'"
    assert session.execute_calls == [("print(42)", 5)]


def test_execute_code_uses_default_session_id_when_missing(manager: PythonSessionManager) -> None:
    session = DummySession("default")
    manager._sessions_by_agent["agent-1"] = {"default": session}

    payload = manager.execute_code(code="print('x')")

    assert payload["message"] == "Code executed in session 'default'"
    assert session.execute_calls == [("print('x')", 30)]


def test_close_session_missing_session_raises_value_error(manager: PythonSessionManager) -> None:
    with pytest.raises(ValueError, match="not found"):
        manager.close_session("missing")


def test_close_session_success_payload_and_state(manager: PythonSessionManager) -> None:
    session = DummySession("s1")
    manager._sessions_by_agent["agent-1"] = {"s1": session}

    payload = manager.close_session("s1")

    assert payload == {
        "session_id": "s1",
        "message": "Python session 's1' closed successfully",
        "is_running": False,
    }
    assert session.closed is True
    assert manager._sessions_by_agent["agent-1"] == {}


def test_close_session_uses_default_session_id_when_missing(manager: PythonSessionManager) -> None:
    session = DummySession("default")
    manager._sessions_by_agent["agent-1"] = {"default": session}

    payload = manager.close_session()

    assert payload["session_id"] == "default"
    assert payload["is_running"] is False
    assert session.closed is True


def test_list_sessions_reports_running_alive_and_total_count(manager: PythonSessionManager) -> None:
    manager._sessions_by_agent["agent-1"] = {
        "live": DummySession("live", is_running=True, is_alive=True),
        "stopped": DummySession("stopped", is_running=False, is_alive=False),
    }

    payload = manager.list_sessions()

    assert payload == {
        "sessions": {
            "live": {"is_running": True, "is_alive": True},
            "stopped": {"is_running": False, "is_alive": False},
        },
        "total_count": 2,
    }


def test_cleanup_agent_closes_sessions_and_removes_agent_key(manager: PythonSessionManager) -> None:
    target_sessions = {
        "a": DummySession("a"),
        "b": DummySession("b"),
    }
    manager._sessions_by_agent = {
        "agent-1": target_sessions,
        "agent-2": {"x": DummySession("x")},
    }

    manager.cleanup_agent("agent-1")

    assert "agent-1" not in manager._sessions_by_agent
    assert "agent-2" in manager._sessions_by_agent
    assert all(session.closed for session in target_sessions.values())


def test_cleanup_dead_sessions_removes_dead_and_suppresses_close_errors(
    manager: PythonSessionManager,
) -> None:
    alive = DummySession("alive", is_alive=True)
    dead_closing_ok = DummySession("dead-ok", is_alive=False)
    dead_closing_fails = DummySession("dead-fail", is_alive=False, close_raises=True)
    manager._sessions_by_agent = {
        "agent-1": {
            "alive": alive,
            "dead-ok": dead_closing_ok,
            "dead-fail": dead_closing_fails,
        }
    }

    manager.cleanup_dead_sessions()

    assert manager._sessions_by_agent["agent-1"] == {"alive": alive}
    assert dead_closing_ok.closed is True
    assert dead_closing_fails.closed is True


def test_close_all_sessions_clears_map_and_suppresses_close_errors(
    manager: PythonSessionManager,
) -> None:
    session_ok = DummySession("ok")
    session_err = DummySession("err", close_raises=True)
    manager._sessions_by_agent = {
        "agent-1": {"ok": session_ok},
        "agent-2": {"err": session_err},
    }

    manager.close_all_sessions()

    assert manager._sessions_by_agent == {}
    assert session_ok.closed is True
    assert session_err.closed is True


def test_register_cleanup_handlers_registers_close_all_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered: list[Any] = []
    manager = PythonSessionManager.__new__(PythonSessionManager)
    monkeypatch.setattr(python_manager_module.atexit, "register", registered.append)

    manager._register_cleanup_handlers()

    assert registered == [manager.close_all_sessions]


def test_get_python_session_manager_returns_singleton_object() -> None:
    manager_a = get_python_session_manager()
    manager_b = get_python_session_manager()

    assert manager_a is manager_b
    assert manager_a is python_manager_module._python_session_manager
