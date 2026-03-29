import sys
from unittest.mock import MagicMock, patch


# Mock libtmux to avoid ImportError since it's an optional dependency
sys.modules["libtmux"] = MagicMock()

from strix.tools.terminal.terminal_actions import terminal_execute  # noqa: E402


def test_terminal_execute_success():
    """Test successful terminal execution."""
    mock_manager = MagicMock()
    mock_manager.execute_command.return_value = {
        "content": "output",
        "status": "success",
        "exit_code": 0,
        "working_dir": "/tmp",
        "command": "ls",
        "terminal_id": "default",
    }

    with patch(
        "strix.tools.terminal.terminal_manager.get_terminal_manager", return_value=mock_manager
    ):
        result = terminal_execute(
            "ls", timeout=1.5, terminal_id="term1", is_input=True, no_enter=True
        )

        assert result["status"] == "success"
        assert result["content"] == "output"
        mock_manager.execute_command.assert_called_once_with(
            command="ls",
            is_input=True,
            timeout=1.5,
            terminal_id="term1",
            no_enter=True,
        )


def test_terminal_execute_error():
    """Test terminal execution handling exceptions."""
    mock_manager = MagicMock()
    mock_manager.execute_command.side_effect = ValueError("Invalid terminal")

    with patch(
        "strix.tools.terminal.terminal_manager.get_terminal_manager", return_value=mock_manager
    ):
        result = terminal_execute("ls", terminal_id="bad_term")

        assert result["status"] == "error"
        assert result["error"] == "Invalid terminal"
        assert result["command"] == "ls"
        assert result["terminal_id"] == "bad_term"


def test_terminal_execute_runtime_error():
    """Test terminal execution handling runtime error."""
    mock_manager = MagicMock()
    mock_manager.execute_command.side_effect = RuntimeError("Manager failed")

    with patch(
        "strix.tools.terminal.terminal_manager.get_terminal_manager", return_value=mock_manager
    ):
        result = terminal_execute("ls")  # No terminal_id, should default to "default"

        assert result["status"] == "error"
        assert result["error"] == "Manager failed"
        assert result["command"] == "ls"
        assert result["terminal_id"] == "default"
