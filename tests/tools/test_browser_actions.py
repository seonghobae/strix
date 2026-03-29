"""Tests for browser tool actions dispatch and validation."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from strix.tools.browser import browser_actions


@pytest.fixture
def manager() -> MagicMock:
    """Provide a mock browser tab manager."""
    return MagicMock()


@pytest.fixture
def patch_tab_manager(monkeypatch: pytest.MonkeyPatch, manager: MagicMock) -> MagicMock:
    """Patch runtime tab manager import used by browser_action."""
    fake_tab_module = SimpleNamespace(get_browser_tab_manager=lambda: manager)
    monkeypatch.setitem(sys.modules, "strix.tools.browser.tab_manager", fake_tab_module)
    return manager


@pytest.mark.parametrize(
    ("action", "method_name", "args"),
    [
        ("launch", "launch_browser", ("https://example.com",)),
        ("goto", "goto_url", ("https://example.com", "tab-1")),
        ("back", "back", ("tab-1",)),
        ("forward", "forward", ("tab-1",)),
    ],
)
def test_handle_navigation_actions_dispatches(
    action: str,
    method_name: str,
    args: tuple,
    manager: MagicMock,
) -> None:
    """Navigation handler dispatches each action to correct manager method."""
    expected = {"ok": action}
    getattr(manager, method_name).return_value = expected

    result = browser_actions._handle_navigation_actions(
        manager,
        action,
        url="https://example.com",
        tab_id="tab-1",
    )

    assert result == expected
    getattr(manager, method_name).assert_called_once_with(*args)


def test_handle_navigation_actions_validates_and_unknown(manager: MagicMock) -> None:
    """Navigation handler validates required URL and rejects unknown action."""
    with pytest.raises(ValueError, match="url parameter is required for goto action"):
        browser_actions._handle_navigation_actions(manager, "goto", url=None)

    with pytest.raises(ValueError, match="Unknown navigation action: noop"):
        browser_actions._handle_navigation_actions(manager, "noop")


@pytest.mark.parametrize("bad_url", [None, ""])
def test_handle_navigation_actions_goto_rejects_empty_url(
    bad_url: str | None,
    manager: MagicMock,
) -> None:
    """Goto rejects missing/empty URL values."""
    with pytest.raises(ValueError, match="url parameter is required for goto action"):
        browser_actions._handle_navigation_actions(manager, "goto", url=bad_url)


@pytest.mark.parametrize(
    ("action", "method_name"),
    [
        ("click", "click"),
        ("double_click", "double_click"),
        ("hover", "hover"),
    ],
)
def test_handle_interaction_pointer_actions_dispatch(
    action: str,
    method_name: str,
    manager: MagicMock,
) -> None:
    """Pointer interaction actions map to click/double_click/hover manager calls."""
    expected = {"ok": action}
    getattr(manager, method_name).return_value = expected

    result = browser_actions._handle_interaction_actions(
        manager,
        action,
        coordinate="100,200",
        tab_id="tab-1",
    )

    assert result == expected
    getattr(manager, method_name).assert_called_once_with("100,200", "tab-1")


@pytest.mark.parametrize("action", ["click", "double_click", "hover"])
def test_handle_interaction_pointer_actions_require_coordinate(
    action: str,
    manager: MagicMock,
) -> None:
    """Pointer interaction actions require coordinate parameter."""
    with pytest.raises(ValueError, match=f"coordinate parameter is required for {action} action"):
        browser_actions._handle_interaction_actions(manager, action, coordinate=None)


@pytest.mark.parametrize("action", ["click", "double_click", "hover"])
def test_handle_interaction_pointer_actions_reject_empty_coordinate(
    action: str,
    manager: MagicMock,
) -> None:
    """Pointer actions reject empty coordinate values."""
    with pytest.raises(ValueError, match=f"coordinate parameter is required for {action} action"):
        browser_actions._handle_interaction_actions(manager, action, coordinate="")


def test_handle_interaction_scroll_type_and_key_paths(manager: MagicMock) -> None:
    """Interaction handler maps scroll/type/key flows and validates fields."""
    manager.scroll.return_value = {"ok": "scroll"}
    manager.type_text.return_value = {"ok": "type"}
    manager.press_key.return_value = {"ok": "press"}

    down = browser_actions._handle_interaction_actions(manager, "scroll_down", tab_id="tab-1")
    up = browser_actions._handle_interaction_actions(manager, "scroll_up", tab_id="tab-1")
    typed = browser_actions._handle_interaction_actions(
        manager,
        "type",
        text="hello",
        tab_id="tab-1",
    )
    pressed = browser_actions._handle_interaction_actions(
        manager,
        "press_key",
        key="Enter",
        tab_id="tab-1",
    )

    assert down == {"ok": "scroll"}
    assert up == {"ok": "scroll"}
    assert typed == {"ok": "type"}
    assert pressed == {"ok": "press"}
    manager.scroll.assert_any_call("down", "tab-1")
    manager.scroll.assert_any_call("up", "tab-1")
    manager.type_text.assert_called_once_with("hello", "tab-1")
    manager.press_key.assert_called_once_with("Enter", "tab-1")


def test_handle_interaction_validates_and_unknown(manager: MagicMock) -> None:
    """Interaction handler raises for missing text/key and unknown action."""
    with pytest.raises(ValueError, match="text parameter is required for type action"):
        browser_actions._handle_interaction_actions(manager, "type", text=None)

    with pytest.raises(ValueError, match="key parameter is required for press_key action"):
        browser_actions._handle_interaction_actions(manager, "press_key", key=None)

    with pytest.raises(ValueError, match="Unknown interaction action: drag"):
        browser_actions._handle_interaction_actions(manager, "drag")


@pytest.mark.parametrize(
    ("action", "kwargs", "expected"),
    [
        ("type", {"text": ""}, "text parameter is required for type action"),
        ("press_key", {"key": ""}, "key parameter is required for press_key action"),
    ],
)
def test_handle_interaction_rejects_empty_text_and_key(
    action: str,
    kwargs: dict[str, str],
    expected: str,
    manager: MagicMock,
) -> None:
    """Type/press_key reject empty string input values."""
    with pytest.raises(ValueError, match=expected):
        browser_actions._handle_interaction_actions(manager, action, **kwargs)


def test_handle_tab_actions_dispatches_and_validates(manager: MagicMock) -> None:
    """Tab handler supports new/switch/close/list and validates tab id."""
    manager.new_tab.return_value = {"ok": "new_tab"}
    manager.switch_tab.return_value = {"ok": "switch_tab"}
    manager.close_tab.return_value = {"ok": "close_tab"}
    manager.list_tabs.return_value = {"ok": "list_tabs"}

    assert browser_actions._handle_tab_actions(manager, "new_tab", url="https://example.com") == {
        "ok": "new_tab"
    }
    assert browser_actions._handle_tab_actions(manager, "switch_tab", tab_id="tab-1") == {
        "ok": "switch_tab"
    }
    assert browser_actions._handle_tab_actions(manager, "close_tab", tab_id="tab-1") == {
        "ok": "close_tab"
    }
    assert browser_actions._handle_tab_actions(manager, "list_tabs") == {"ok": "list_tabs"}
    manager.new_tab.assert_called_once_with("https://example.com")
    manager.switch_tab.assert_called_once_with("tab-1")
    manager.close_tab.assert_called_once_with("tab-1")
    manager.list_tabs.assert_called_once_with()

    with pytest.raises(ValueError, match="tab_id parameter is required for switch_tab action"):
        browser_actions._handle_tab_actions(manager, "switch_tab", tab_id=None)
    with pytest.raises(ValueError, match="tab_id parameter is required for close_tab action"):
        browser_actions._handle_tab_actions(manager, "close_tab", tab_id=None)
    with pytest.raises(ValueError, match="Unknown tab action: move_tab"):
        browser_actions._handle_tab_actions(manager, "move_tab")


def test_handle_utility_actions_dispatches_and_validates(manager: MagicMock) -> None:
    """Utility handler maps actions and validates required parameters."""
    manager.wait_browser.return_value = {"ok": "wait"}
    manager.execute_js.return_value = {"ok": "js"}
    manager.save_pdf.return_value = {"ok": "pdf"}
    manager.get_console_logs.return_value = {"ok": "logs"}
    manager.view_source.return_value = {"ok": "source"}
    manager.close_browser.return_value = {"ok": "close"}

    assert browser_actions._handle_utility_actions(manager, "wait", duration=0, tab_id="tab-1") == {
        "ok": "wait"
    }

    assert browser_actions._handle_utility_actions(
        manager, "wait", duration=1.5, tab_id="tab-1"
    ) == {"ok": "wait"}
    assert browser_actions._handle_utility_actions(
        manager,
        "execute_js",
        js_code="return 1;",
        tab_id="tab-1",
    ) == {"ok": "js"}
    assert browser_actions._handle_utility_actions(
        manager,
        "save_pdf",
        file_path="/tmp/out.pdf",
        tab_id="tab-1",
    ) == {"ok": "pdf"}
    assert browser_actions._handle_utility_actions(
        manager,
        "get_console_logs",
        tab_id="tab-1",
        clear=True,
    ) == {"ok": "logs"}
    assert browser_actions._handle_utility_actions(manager, "view_source", tab_id="tab-1") == {
        "ok": "source"
    }
    assert browser_actions._handle_utility_actions(manager, "close") == {"ok": "close"}
    assert manager.wait_browser.call_count == 2
    manager.wait_browser.assert_any_call(0, "tab-1")
    manager.wait_browser.assert_any_call(1.5, "tab-1")
    manager.execute_js.assert_called_once_with("return 1;", "tab-1")
    manager.save_pdf.assert_called_once_with("/tmp/out.pdf", "tab-1")
    assert manager.get_console_logs.call_count == 1
    assert manager.get_console_logs.call_args.args == ("tab-1", True)
    manager.view_source.assert_called_once_with("tab-1")
    manager.close_browser.assert_called_once_with()

    with pytest.raises(ValueError, match="duration parameter is required for wait action"):
        browser_actions._handle_utility_actions(manager, "wait", duration=None)
    with pytest.raises(ValueError, match="js_code parameter is required for execute_js action"):
        browser_actions._handle_utility_actions(manager, "execute_js", js_code=None)
    with pytest.raises(ValueError, match="file_path parameter is required for save_pdf action"):
        browser_actions._handle_utility_actions(manager, "save_pdf", file_path=None)
    with pytest.raises(ValueError, match="Unknown utility action: snapshot"):
        browser_actions._handle_utility_actions(manager, "snapshot")


@pytest.mark.parametrize("bad_path", [None, ""])
def test_handle_utility_save_pdf_rejects_empty_path(
    bad_path: str | None,
    manager: MagicMock,
) -> None:
    """Save-pdf rejects missing/empty file path."""
    with pytest.raises(ValueError, match="file_path parameter is required for save_pdf action"):
        browser_actions._handle_utility_actions(manager, "save_pdf", file_path=bad_path)


def test_handle_utility_get_console_logs_default_clear_false(manager: MagicMock) -> None:
    """Get-console-logs forwards default clear=False when omitted."""
    manager.get_console_logs.return_value = {"ok": "logs"}
    result = browser_actions._handle_utility_actions(manager, "get_console_logs", tab_id="tab-1")

    assert result == {"ok": "logs"}
    assert manager.get_console_logs.call_count == 1
    assert manager.get_console_logs.call_args.args == ("tab-1", False)


def test_raise_unknown_action_helper() -> None:
    """Unknown action helper raises ValueError with action name."""
    with pytest.raises(ValueError, match="Unknown action: mystery"):
        browser_actions._raise_unknown_action("mystery")


@pytest.mark.parametrize(
    ("action", "handler_name"),
    [
        ("launch", "_handle_navigation_actions"),
        ("click", "_handle_interaction_actions"),
        ("new_tab", "_handle_tab_actions"),
        ("wait", "_handle_utility_actions"),
    ],
)
def test_browser_action_dispatches_to_expected_handler(
    action: str,
    handler_name: str,
    monkeypatch: pytest.MonkeyPatch,
    patch_tab_manager: MagicMock,
) -> None:
    """browser_action routes actions to the right handler group."""
    called = {"navigation": 0, "interaction": 0, "tab": 0, "utility": 0}
    captured: dict[str, tuple[tuple, dict]] = {}

    def nav(*_args, **_kwargs):
        called["navigation"] += 1
        captured["navigation"] = (_args, _kwargs)
        return {"handler": "navigation"}

    def inter(*_args, **_kwargs):
        called["interaction"] += 1
        captured["interaction"] = (_args, _kwargs)
        return {"handler": "interaction"}

    def tab(*_args, **_kwargs):
        called["tab"] += 1
        captured["tab"] = (_args, _kwargs)
        return {"handler": "tab"}

    def util(*_args, **_kwargs):
        called["utility"] += 1
        captured["utility"] = (_args, _kwargs)
        return {"handler": "utility"}

    monkeypatch.setattr(browser_actions, "_handle_navigation_actions", nav)
    monkeypatch.setattr(browser_actions, "_handle_interaction_actions", inter)
    monkeypatch.setattr(browser_actions, "_handle_tab_actions", tab)
    monkeypatch.setattr(browser_actions, "_handle_utility_actions", util)

    result = browser_actions.browser_action(
        action,  # type: ignore[arg-type]
        url="https://example.com",
        coordinate="1,1",
        text="x",
        tab_id="tab-1",
        duration=0.1,
        js_code="return 1;",
        file_path="/tmp/a.pdf",
        key="Enter",
        clear=True,
    )

    assert (
        result
        == {
            "launch": {"handler": "navigation"},
            "click": {"handler": "interaction"},
            "new_tab": {"handler": "tab"},
            "wait": {"handler": "utility"},
        }[action]
    )

    expected_calls = {
        "navigation": 1 if handler_name == "_handle_navigation_actions" else 0,
        "interaction": 1 if handler_name == "_handle_interaction_actions" else 0,
        "tab": 1 if handler_name == "_handle_tab_actions" else 0,
        "utility": 1 if handler_name == "_handle_utility_actions" else 0,
    }
    assert called == expected_calls
    if action == "launch":
        assert captured["navigation"][0] == (
            patch_tab_manager,
            "launch",
            "https://example.com",
            "tab-1",
        )
    elif action == "click":
        assert captured["interaction"][0] == (
            patch_tab_manager,
            "click",
            "1,1",
            "x",
            "Enter",
            "tab-1",
        )
    elif action == "new_tab":
        assert captured["tab"][0] == (patch_tab_manager, "new_tab", "https://example.com", "tab-1")
    elif action == "wait":
        assert captured["utility"][0] == (
            patch_tab_manager,
            "wait",
            0.1,
            "return 1;",
            "/tmp/a.pdf",
            "tab-1",
            True,
        )
    assert patch_tab_manager is not None


def test_browser_action_unknown_and_error_wrapping(
    monkeypatch: pytest.MonkeyPatch,
    patch_tab_manager: MagicMock,
) -> None:
    """browser_action wraps unknown action and handler exceptions."""
    unknown = browser_actions.browser_action("unknown_action", tab_id="tab-1")  # type: ignore[arg-type]
    assert unknown == {
        "error": "Unknown action: unknown_action",
        "tab_id": "tab-1",
        "screenshot": "",
        "is_running": False,
    }

    monkeypatch.setattr(
        browser_actions,
        "_handle_navigation_actions",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad value")),
    )
    wrapped_value = browser_actions.browser_action("launch", tab_id="tab-x")
    assert wrapped_value == {
        "error": "bad value",
        "tab_id": "tab-x",
        "screenshot": "",
        "is_running": False,
    }

    monkeypatch.setattr(
        browser_actions,
        "_handle_navigation_actions",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("runtime boom")),
    )
    wrapped_runtime = browser_actions.browser_action("launch", tab_id="tab-y")
    assert wrapped_runtime == {
        "error": "runtime boom",
        "tab_id": "tab-y",
        "screenshot": "",
        "is_running": False,
    }
    assert patch_tab_manager is not None
