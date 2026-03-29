from strix.tools.thinking.thinking_actions import think


def test_think_success():
    result = think("This is a valid thought.")
    assert result["success"] is True
    assert "Thought recorded successfully" in result["message"]


def test_think_empty():
    result = think("")
    assert result["success"] is False
    assert result["message"] == "Thought cannot be empty"


def test_think_whitespace():
    result = think("   ")
    assert result["success"] is False
    assert result["message"] == "Thought cannot be empty"


def test_think_exception():
    class BadThought:
        def __bool__(self):
            return True

        def strip(self):
            raise TypeError("mock error")

    result = think(BadThought())
    assert result["success"] is False
    assert "Failed to record thought" in result["message"]
