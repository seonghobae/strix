"""Tests for thinking tool actions."""

from strix.tools.thinking.thinking_actions import think


def test_think_success():
    """Test successful thought recording."""
    result = think("This is a test thought.")
    assert result["success"] is True
    assert "Thought recorded successfully" in result["message"]
    assert "23" in result["message"]  # len("This is a test thought.")


def test_think_empty():
    """Test empty thought."""
    result = think("")
    assert result["success"] is False
    assert result["message"] == "Thought cannot be empty"

    result = think("   ")
    assert result["success"] is False
    assert result["message"] == "Thought cannot be empty"


def test_think_error():
    """Test error handling in think action."""

    class BadBool:
        """Mock object to trigger errors."""

        def __bool__(self):
            """Raise ValueError when evaluated for truthiness."""
            raise ValueError("Bad boolean")

    result = think(BadBool())  # type: ignore[arg-type]
    assert result["success"] is False
    assert "Failed to record thought" in result["message"]
