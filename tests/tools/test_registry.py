from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from strix.tools.registry import (
    ImplementedInClientSideOnlyError,
    _get_module_name,
    _get_schema_path,
    _has_perplexity_api,
    _is_browser_disabled,
    _is_sandbox_mode,
    _load_xml_schema,
    _parse_param_schema,
    _process_dynamic_content,
    _should_register_tool,
    clear_registry,
    get_tool_by_name,
    get_tool_names,
    get_tool_param_schema,
    get_tools_prompt,
    needs_agent_state,
    register_tool,
    should_execute_in_sandbox,
    tools,
)


@pytest.fixture(autouse=True)
def _clear_registry():
    """Clear registry before and after tests."""
    clear_registry()
    yield
    clear_registry()


def test_implemented_in_client_side_only_error():
    """Test exception."""
    err = ImplementedInClientSideOnlyError()
    assert err.message == "This tool is implemented in the client side only"


@patch("strix.tools.registry.logger")
def test_process_dynamic_content_success(mock_logger):
    """Test processing dynamic content with skills available."""
    content = "<tool>{{DYNAMIC_SKILLS_DESCRIPTION}}</tool>"

    with patch("strix.skills.generate_skills_description", return_value="Loaded skills"):
        result = _process_dynamic_content(content)
        assert result == "<tool>Loaded skills</tool>"


@patch("strix.tools.registry.logger")
def test_process_dynamic_content_import_error(mock_logger):
    """Test processing dynamic content when import fails."""
    content = "<tool>{{DYNAMIC_SKILLS_DESCRIPTION}}</tool>"

    with patch("builtins.__import__", side_effect=ImportError("No module")):
        result = _process_dynamic_content(content)
        assert "List of skills" in result


def test_load_xml_schema_non_existent():
    """Test loading non-existent schema."""
    assert _load_xml_schema(Path("non_existent_file.xml")) is None


def test_load_xml_schema_success(tmp_path):
    """Test loading valid schema."""
    schema_file = tmp_path / "schema.xml"
    schema_file.write_text(
        '<tool name="test_tool">\n  <description>Test</description>\n</tool>', encoding="utf-8"
    )

    result = _load_xml_schema(schema_file)
    assert "test_tool" in result
    assert (
        result["test_tool"] == '<tool name="test_tool">\n  <description>Test</description>\n</tool>'
    )


@patch("strix.tools.registry.logger")
def test_load_xml_schema_malformed_xml(mock_logger, tmp_path):
    """Test loading malformed schema missing quotes or end tags."""
    schema_file = tmp_path / "schema_no_quote.xml"
    schema_file.write_text('<tool name="test_tool', encoding="utf-8")
    result = _load_xml_schema(schema_file)
    assert result == {}

    schema_file2 = tmp_path / "schema_no_end.xml"
    schema_file2.write_text(
        '<tool name="test_tool">\n  <description>Test</description>', encoding="utf-8"
    )
    result2 = _load_xml_schema(schema_file2)
    assert result2 == {}


@patch("strix.tools.registry.logger")
def test_load_xml_schema_error(mock_logger, tmp_path):
    """Test loading invalid schema (IndexError/ValueError/UnicodeError)."""
    schema_file = tmp_path / "schema.xml"
    schema_file.write_text('<tool name="test_tool">', encoding="utf-8")

    with patch.object(Path, "read_text", side_effect=ValueError("Some value error")):
        result = _load_xml_schema(schema_file)
        assert result is None
        mock_logger.warning.assert_called_once()


def test_parse_param_schema_no_params():
    """Test parse schema without params."""
    assert _parse_param_schema("<tool></tool>") == {
        "params": set(),
        "required": set(),
        "has_params": False,
    }


def test_parse_param_schema_invalid_xml():
    """Test parse schema with invalid params xml."""
    assert _parse_param_schema("<parameters><parameter></parameters>") == {
        "params": set(),
        "required": set(),
        "has_params": False,
    }


def test_parse_param_schema_valid():
    """Test parse schema with valid params."""
    xml = """
    <parameters>
        <parameter name="arg1" required="true" />
        <parameter name="arg2" required="false" />
        <parameter name="arg3" />
        <parameter />
    </parameters>
    """
    res = _parse_param_schema(xml)
    assert res["params"] == {"arg1", "arg2", "arg3"}
    assert res["required"] == {"arg1"}
    assert res["has_params"] is True


def test_get_module_name():
    """Test getting module name."""

    def sample_func():
        pass

    # We patch inspect.getmodule
    mock_module = MagicMock()
    mock_module.__name__ = "strix.tools.mock_tool.actions"

    with patch("inspect.getmodule", return_value=mock_module):
        assert _get_module_name(sample_func) == "mock_tool"

    mock_module.__name__ = "strix.other.module"
    with patch("inspect.getmodule", return_value=mock_module):
        assert _get_module_name(sample_func) == "unknown"

    with patch("inspect.getmodule", return_value=None):
        assert _get_module_name(sample_func) == "unknown"


def test_get_schema_path():
    """Test getting schema path."""

    def sample_func():
        pass

    mock_module = MagicMock()
    mock_module.__name__ = "strix.tools.mock_tool.actions"

    with patch("inspect.getmodule", return_value=mock_module):
        path = _get_schema_path(sample_func)
        assert path is not None
        assert path.name == "actions_schema.xml"

    mock_module.__name__ = "strix.other.module"
    with patch("inspect.getmodule", return_value=mock_module):
        assert _get_schema_path(sample_func) is None

    mock_module.__name__ = "strix.tools.mock_tool"
    with patch("inspect.getmodule", return_value=mock_module):
        assert _get_schema_path(sample_func) is None

    with patch("inspect.getmodule", return_value=None):
        assert _get_schema_path(sample_func) is None


def test_is_sandbox_mode(monkeypatch):
    """Test checking sandbox mode."""
    monkeypatch.setenv("STRIX_SANDBOX_MODE", "true")
    assert _is_sandbox_mode() is True

    monkeypatch.setenv("STRIX_SANDBOX_MODE", "false")
    assert _is_sandbox_mode() is False


def test_is_browser_disabled(monkeypatch):
    """Test checking browser disabled."""
    monkeypatch.setenv("STRIX_DISABLE_BROWSER", "true")
    assert _is_browser_disabled() is True

    monkeypatch.delenv("STRIX_DISABLE_BROWSER", raising=False)
    with patch("strix.config.Config.load", return_value={"env": {"STRIX_DISABLE_BROWSER": "True"}}):
        assert _is_browser_disabled() is True


def test_has_perplexity_api(monkeypatch):
    """Test checking perplexity api key."""
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test")
    assert _has_perplexity_api() is True

    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    with patch("strix.config.Config.load", return_value={"env": {"PERPLEXITY_API_KEY": "test"}}):
        assert _has_perplexity_api() is True


def test_should_register_tool_sandbox(monkeypatch):
    """Test should register tool in sandbox."""
    monkeypatch.setenv("STRIX_SANDBOX_MODE", "true")
    assert (
        _should_register_tool(
            sandbox_execution=True, requires_browser_mode=False, requires_web_search_mode=False
        )
        is True
    )
    assert (
        _should_register_tool(
            sandbox_execution=False, requires_browser_mode=False, requires_web_search_mode=False
        )
        is False
    )


def test_should_register_tool_browser(monkeypatch):
    """Test should register tool with browser disabled."""
    monkeypatch.setenv("STRIX_SANDBOX_MODE", "false")
    monkeypatch.setenv("STRIX_DISABLE_BROWSER", "true")
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    assert (
        _should_register_tool(
            sandbox_execution=False, requires_browser_mode=True, requires_web_search_mode=False
        )
        is False
    )


def test_should_register_tool_web_search(monkeypatch):
    """Test should register tool with perplexity API missing."""
    monkeypatch.setenv("STRIX_SANDBOX_MODE", "false")
    monkeypatch.delenv("STRIX_DISABLE_BROWSER", raising=False)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    with patch("strix.config.Config.load", return_value={"env": {}}):
        assert (
            _should_register_tool(
                sandbox_execution=False, requires_browser_mode=False, requires_web_search_mode=True
            )
            is False
        )


def test_register_tool(monkeypatch):
    """Test registering a tool."""
    monkeypatch.setenv("STRIX_SANDBOX_MODE", "false")

    mock_module = MagicMock()
    mock_module.__name__ = "strix.tools.mock_tool.actions"

    with (
        patch("inspect.getmodule", return_value=mock_module),
        patch("strix.tools.registry._get_schema_path", return_value=None),
    ):

        @register_tool
        def sample_func():
            return 1

    assert "sample_func" in get_tool_names()
    assert get_tool_by_name("sample_func").__name__ == "sample_func"
    assert get_tool_param_schema("sample_func") == {
        "params": set(),
        "required": set(),
        "has_params": False,
    }
    assert should_execute_in_sandbox("sample_func") is True

    # Try calling the wrapper
    func = get_tool_by_name("sample_func")
    assert func() == 1


def test_register_tool_no_args():
    """Test calling register_tool directly with function (no args)."""

    def sample_func_no_args():
        return 2

    registered = register_tool(sample_func_no_args)
    assert "sample_func_no_args" in get_tool_names()
    assert registered() == 2


def test_register_tool_schema_load_error(monkeypatch):
    """Test registering a tool where schema loading raises an error."""
    monkeypatch.setenv("STRIX_SANDBOX_MODE", "false")

    mock_module = MagicMock()
    mock_module.__name__ = "strix.tools.mock_tool.actions"

    with (
        patch("inspect.getmodule", return_value=mock_module),
        patch("strix.tools.registry._get_schema_path", side_effect=TypeError("mock error")),
    ):

        @register_tool
        def sample_func_err():
            return 3

    assert "sample_func_err" in get_tool_names()
    assert "Error loading schema." in tools[-1]["xml_schema"]


def test_register_tool_disabled_browser(monkeypatch):
    """Test registering a tool when condition fails."""
    monkeypatch.setenv("STRIX_DISABLE_BROWSER", "true")

    @register_tool(requires_browser_mode=True)
    def sample_func_browser():
        pass

    assert "sample_func_browser" not in get_tool_names()


def test_needs_agent_state():
    """Test needs agent state."""

    @register_tool
    def sample_with_state(agent_state: Any):
        pass

    @register_tool
    def sample_no_state():
        pass

    assert needs_agent_state("sample_with_state") is True
    assert needs_agent_state("sample_no_state") is False
    assert needs_agent_state("non_existent") is False


def test_should_execute_in_sandbox():
    """Test sandbox execution setting."""

    @register_tool(sandbox_execution=False)
    def sample_non_sandbox():
        pass

    assert should_execute_in_sandbox("sample_non_sandbox") is False
    assert should_execute_in_sandbox("non_existent") is True


def test_get_tools_prompt():
    """Test building tool prompt."""

    def test_tool_func():
        pass

    test_tool_func.__module__ = "strix.tools.mock_tool.actions"

    tools.append(
        {
            "module": "mock_tool",
            "xml_schema": '<tool name="test_tool">\n<description>Test</description>\n</tool>',
        }
    )

    prompt = get_tools_prompt()
    assert "<mock_tool_tools>" in prompt
    assert '<tool name="test_tool">' in prompt
