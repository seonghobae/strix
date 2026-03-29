"""Tests for python actions."""

import sys
from unittest.mock import MagicMock


# Mock python_manager module before importing python_actions
mock_python_manager = MagicMock()
sys.modules["strix.tools.python.python_manager"] = mock_python_manager

from strix.tools.python.python_actions import python_action  # noqa: E402


def test_python_action_new_session():
    """Test new_session action."""
    mock_manager = MagicMock()
    mock_manager.create_session.return_value = {"stdout": "created"}
    mock_python_manager.get_python_session_manager.return_value = mock_manager

    result = python_action(
        action="new_session",
        code="print('hi')",
        timeout=10,
        session_id="session1",
    )

    mock_manager.create_session.assert_called_once_with("session1", "print('hi')", 10)
    assert result == {"stdout": "created"}


def test_python_action_execute():
    """Test execute action."""
    mock_manager = MagicMock()
    mock_manager.execute_code.return_value = {"stdout": "executed"}
    mock_python_manager.get_python_session_manager.return_value = mock_manager

    result = python_action(
        action="execute",
        code="print('hi')",
        timeout=10,
        session_id="session1",
    )

    mock_manager.execute_code.assert_called_once_with("session1", "print('hi')", 10)
    assert result == {"stdout": "executed"}


def test_python_action_execute_missing_code():
    """Test execute action with missing code."""
    mock_manager = MagicMock()
    mock_python_manager.get_python_session_manager.return_value = mock_manager

    result = python_action(
        action="execute",
        code=None,
        timeout=10,
        session_id="session1",
    )

    assert result["stderr"] == "code parameter is required for execute action"
    assert result["session_id"] == "session1"
    assert result["stdout"] == ""
    assert result["is_running"] is False


def test_python_action_close():
    """Test close action."""
    mock_manager = MagicMock()
    mock_manager.close_session.return_value = {"stdout": "closed"}
    mock_python_manager.get_python_session_manager.return_value = mock_manager

    result = python_action(
        action="close",
        session_id="session1",
    )

    mock_manager.close_session.assert_called_once_with("session1")
    assert result == {"stdout": "closed"}


def test_python_action_list_sessions():
    """Test list_sessions action."""
    mock_manager = MagicMock()
    mock_manager.list_sessions.return_value = {"sessions": []}
    mock_python_manager.get_python_session_manager.return_value = mock_manager

    result = python_action(action="list_sessions")

    mock_manager.list_sessions.assert_called_once_with()
    assert result == {"sessions": []}


def test_python_action_unknown():
    """Test unknown action."""
    mock_manager = MagicMock()
    mock_python_manager.get_python_session_manager.return_value = mock_manager

    result = python_action(
        action="unknown_action",  # type: ignore[arg-type]
        session_id="session1",
    )

    assert result["stderr"] == "Unknown action: unknown_action"
    assert result["session_id"] == "session1"
    assert result["stdout"] == ""
    assert result["is_running"] is False


def test_python_action_runtime_error():
    """Test runtime error handling."""
    mock_manager = MagicMock()
    mock_manager.list_sessions.side_effect = RuntimeError("Manager error")
    mock_python_manager.get_python_session_manager.return_value = mock_manager

    result = python_action(
        action="list_sessions",
        session_id="session1",
    )

    assert result["stderr"] == "Manager error"
    assert result["session_id"] == "session1"
    assert result["stdout"] == ""
    assert result["is_running"] is False
