"""Tests for python tool actions."""

from unittest.mock import MagicMock, patch

import pytest

import strix.tools.python.python_manager
from strix.tools.python.python_actions import python_action


@pytest.fixture
def mock_python_manager():
    """Mock the python session manager."""
    with patch("strix.tools.python.python_manager.get_python_session_manager") as mock_get:
        mock_manager = MagicMock()
        mock_get.return_value = mock_manager
        yield mock_manager


def test_python_action_new_session(mock_python_manager):
    """Test creating a new session."""
    mock_python_manager.create_session.return_value = {"session_id": "test_id"}
    result = python_action("new_session", code="print(1)", timeout=10, session_id="test_id")

    mock_python_manager.create_session.assert_called_once_with("test_id", "print(1)", 10)
    assert result == {"session_id": "test_id"}


def test_python_action_execute(mock_python_manager):
    """Test executing code."""
    mock_python_manager.execute_code.return_value = {"stdout": "1"}
    result = python_action("execute", code="print(1)", timeout=20, session_id="test_id")

    mock_python_manager.execute_code.assert_called_once_with("test_id", "print(1)", 20)
    assert result == {"stdout": "1"}


def test_python_action_execute_no_code(mock_python_manager):
    """Test executing code without providing code."""
    result = python_action("execute", code=None, timeout=20, session_id="test_id")
    assert "code parameter is required" in result["stderr"]


def test_python_action_execute_empty_code(mock_python_manager):
    """Test executing code with empty code."""
    result = python_action("execute", code="", timeout=20, session_id="test_id")
    assert "code parameter is required" in result["stderr"]


def test_python_action_close(mock_python_manager):
    """Test closing a session."""
    mock_python_manager.close_session.return_value = {"session_id": "test_id"}
    result = python_action("close", session_id="test_id")

    mock_python_manager.close_session.assert_called_once_with("test_id")
    assert result == {"session_id": "test_id"}


def test_python_action_list_sessions(mock_python_manager):
    """Test listing sessions."""
    mock_python_manager.list_sessions.return_value = {"sessions": []}
    result = python_action("list_sessions")

    mock_python_manager.list_sessions.assert_called_once()
    assert result == {"sessions": []}


def test_python_action_unknown_action(mock_python_manager):
    """Test unknown action."""
    result = python_action("unknown_action")  # type: ignore[arg-type]
    assert "Unknown action: unknown_action" in result["stderr"]


def test_python_action_value_error(mock_python_manager):
    """Test handling ValueError from manager."""
    mock_python_manager.create_session.side_effect = ValueError("Test error")
    result = python_action("new_session", code="print(1)", session_id="test_id")

    assert result == {
        "stderr": "Test error",
        "session_id": "test_id",
        "stdout": "",
        "is_running": False,
    }


def test_python_action_runtime_error(mock_python_manager):
    """Test handling RuntimeError from manager."""
    mock_python_manager.execute_code.side_effect = RuntimeError("Runtime error")
    result = python_action("execute", code="print(1)", session_id="test_id")

    assert result == {
        "stderr": "Runtime error",
        "session_id": "test_id",
        "stdout": "",
        "is_running": False,
    }
