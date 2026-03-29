"""Python actions module."""

from typing import Any, Literal

from strix.tools.registry import register_tool


PythonAction = Literal["new_session", "execute", "close", "list_sessions"]


@register_tool
def python_action(
    action: PythonAction,
    code: str | None = None,
    timeout: int = 30,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Execute Python code in isolated sessions."""
    from .python_manager import get_python_session_manager

    def _validate_code(action_name: str, code: str | None) -> None:
        """Validate that code is provided for actions that require it."""
        if not code:
            raise ValueError(f"code parameter is required for {action_name} action")

    def _validate_action(action_name: str) -> None:
        """Raise an error for an unknown action."""
        raise ValueError(f"Unknown action: {action_name}")

    manager = get_python_session_manager()

    try:
        match action:
            case "new_session":
                return manager.create_session(session_id, code, timeout)

            case "execute":
                _validate_code(action, code)
                assert code is not None
                return manager.execute_code(session_id, code, timeout)

            case "close":
                return manager.close_session(session_id)

            case "list_sessions":
                return manager.list_sessions()

            case _:
                _validate_action(action)  # type: ignore[unreachable]
                return {}  # pragma: no cover  # Fallback for pyright type checking

    except (ValueError, RuntimeError) as e:
        return {"stderr": str(e), "session_id": session_id, "stdout": "", "is_running": False}
