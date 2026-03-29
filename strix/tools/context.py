"""Context variables for the tool execution environment.

This module provides thread-safe context variables to track the current
agent executing tools, ensuring isolated context across different agents.
"""

from contextvars import ContextVar


current_agent_id: ContextVar[str] = ContextVar("current_agent_id", default="default")


def get_current_agent_id() -> str:
    """Get the ID of the agent currently executing tools in this context.

    Returns:
        The current agent ID string.
    """
    return current_agent_id.get()


def set_current_agent_id(agent_id: str) -> None:
    """Set the ID of the agent currently executing tools in this context.

    Args:
        agent_id: The ID string of the current agent.
    """
    current_agent_id.set(agent_id)
