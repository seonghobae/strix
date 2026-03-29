"""Terminal execution actions and tool registrations."""

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
    """Execute a command in a persistent terminal session.

    Args:
        command: The command or input string to execute.
        is_input: Whether the command is raw input for an existing process.
        timeout: Maximum time to wait for output in seconds.
        terminal_id: Identifier for the terminal session.
        no_enter: If True, do not append a newline to the input.

    Returns:
        dict[str, Any]: The execution result including status, content, and error details.
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
