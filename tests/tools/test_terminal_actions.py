"""Tests for terminal tool actions."""

import sys
from unittest.mock import MagicMock, patch

# Mock libtmux before any terminal module is imported
sys.modules["libtmux"] = MagicMock()

from strix.tools.terminal.terminal_actions import terminal_execute


@patch("strix.tools.terminal.terminal_manager.get_terminal_manager")
def test_terminal_execute_success(mock_get_manager: MagicMock) -> None:
    """Test successful terminal command execution."""
    mock_manager = MagicMock()
    mock_manager.execute_command.return_value = {
        "content": "output",
        "status": "success",
        "exit_code": 0,
        "working_dir": "/tmp",
        "command": "ls",
        "terminal_id": "default",
    }
    mock_get_manager.return_value = mock_manager

    result = terminal_execute("ls", timeout=5.0)

    assert result["status"] == "success"
    assert result["content"] == "output"
    assert result["exit_code"] == 0
    mock_manager.execute_command.assert_called_once_with(
        command="ls",
        is_input=False,
        timeout=5.0,
        terminal_id=None,
        no_enter=False,
    )


@patch("strix.tools.terminal.terminal_manager.get_terminal_manager")
def test_terminal_execute_error(mock_get_manager: MagicMock) -> None:
    """Test terminal command execution with an error from the manager."""
    mock_manager = MagicMock()
    mock_manager.execute_command.side_effect = ValueError("Terminal not found")
    mock_get_manager.return_value = mock_manager

    result = terminal_execute("ls", terminal_id="missing_term")

    assert result["status"] == "error"
    assert result["error"] == "Terminal not found"
    assert result["command"] == "ls"
    assert result["terminal_id"] == "missing_term"
    assert result["exit_code"] is None
