"""Terminal actions for executing shell commands and providing input.

This module provides tools for interacting with long-running terminal sessions.
"""

from typing import Any

from strix.tools.registry import register_tool


@register_tool
def terminal_execute(
    command: str,
    is_input: bool = False,
    timeout: float | None = None,
    terminal_id: str | None = None,
    no_enter: bool = False,
) -> dict[str, Any]:
    """Execute a command or provide input to a terminal session.

    Args:
        command: The shell command to execute or text to input.
        is_input: Whether the command is input to an existing process.
        timeout: Optional timeout in seconds for command execution.
        terminal_id: Optional ID of a specific terminal session.
        no_enter: Whether to skip sending an Enter keystroke after input.

    Returns:
        A dictionary containing the execution result, including output content,
        exit code, working directory, and status.
    """
    from .terminal_manager import get_terminal_manager

    manager = get_terminal_manager()

    try:
        return manager.execute_command(
            command=command,
            is_input=is_input,
            timeout=timeout,
            terminal_id=terminal_id,
            no_enter=no_enter,
        )
    except (ValueError, RuntimeError) as e:
        return {
            "error": str(e),
            "command": command,
            "terminal_id": terminal_id or "default",
            "content": "",
            "status": "error",
            "exit_code": None,
            "working_dir": None,
        }
