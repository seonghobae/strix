from strix.tools.thinking.thinking_actions import think


def test_think_success():
    """Test successful thought recording."""
    result = think(thought="This is a test thought.")
    assert result["success"] is True
    assert "recorded successfully" in result["message"]
    assert "23 characters" in result["message"]


def test_think_empty():
    """Test thinking with empty thought."""
    result = think(thought="")
    assert result["success"] is False
    assert result["message"] == "Thought cannot be empty"

    result2 = think(thought="   ")
    assert result2["success"] is False
    assert result2["message"] == "Thought cannot be empty"


def test_think_exception():
    """Test exception handling in think."""
    # Force a TypeError by passing None or a wrong type if possible,
    # though type hints say str. Let's pass None to trigger exception or empty check.
    result = think(thought=None)
    assert result["success"] is False
    # None.strip() will raise AttributeError, which is not caught by (ValueError, TypeError).
    # Wait, the code has `not thought or not thought.strip()`.
    # If `thought` is None, `not thought` is True, so it returns "Thought cannot be empty".
    assert result["message"] == "Thought cannot be empty"

    # To hit the exception block, we need something that causes ValueError or TypeError.
    # Actually, `not thought` will handle most truthy/falsy cases.
    # What if we pass an object that raises ValueError on boolean evaluation?
    class BadBool:
        def __bool__(self):
            raise ValueError("Bad boolean")

    result3 = think(thought=BadBool())
    assert result3["success"] is False
    assert "Failed to record thought" in result3["message"]
    assert "Bad boolean" in result3["message"]
