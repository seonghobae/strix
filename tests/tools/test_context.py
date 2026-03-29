"""Tests for the context variables."""

from strix.tools.context import current_agent_id, get_current_agent_id, set_current_agent_id


def test_default_agent_id() -> None:
    """Test that the default agent ID is 'default'."""
    assert get_current_agent_id() == "default"


def test_set_and_get_agent_id() -> None:
    """Test setting and getting a custom agent ID."""
    token = current_agent_id.set("test_agent_1")
    try:
        assert get_current_agent_id() == "test_agent_1"

        set_current_agent_id("test_agent_2")
        assert get_current_agent_id() == "test_agent_2"
    finally:
        current_agent_id.reset(token)
