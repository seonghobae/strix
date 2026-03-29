"""Unit tests for PythonInstance behavior."""

from __future__ import annotations

import builtins
import sys
import threading
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import strix.tools.python.python_instance as python_instance_module
from strix.tools.python.python_instance import (
    MAX_STDERR_LENGTH,
    MAX_STDOUT_LENGTH,
    PythonInstance,
)


def _make_instance(session_id: str = "session-1", is_running: bool = True) -> PythonInstance:
    """Create a lightweight PythonInstance without importing IPython."""
    instance = PythonInstance.__new__(PythonInstance)
    instance.session_id = session_id
    instance.is_running = is_running
    instance._execution_lock = threading.Lock()
    instance.shell = MagicMock()
    return instance


def _exec_result(
    *,
    result: object | None = None,
    error_before_exec: object | None = None,
    error_in_exec: object | None = None,
) -> SimpleNamespace:
    """Build a fake InteractiveShell execution result object."""
    return SimpleNamespace(
        result=result,
        error_before_exec=error_before_exec,
        error_in_exec=error_in_exec,
    )


def test_validate_session_when_running_returns_none() -> None:
    instance = _make_instance(is_running=True)

    assert instance._validate_session() is None


def test_init_creates_running_instance_and_configures_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chdir_calls: list[str] = []

    class FakeShell:
        def __init__(self) -> None:
            self.user_ns: dict[str, object] = {}
            self.init_calls: list[str] = []

        def init_completer(self) -> None:
            self.init_calls.append("completer")

        def init_history(self) -> None:
            self.init_calls.append("history")

        def init_logger(self) -> None:
            self.init_calls.append("logger")

    fake_ipython = types.ModuleType("IPython")
    fake_ipython_core = types.ModuleType("IPython.core")
    fake_interactiveshell = types.ModuleType("IPython.core.interactiveshell")
    fake_interactiveshell.InteractiveShell = FakeShell

    monkeypatch.setitem(sys.modules, "IPython", fake_ipython)
    monkeypatch.setitem(sys.modules, "IPython.core", fake_ipython_core)
    monkeypatch.setitem(sys.modules, "IPython.core.interactiveshell", fake_interactiveshell)
    monkeypatch.setattr("os.chdir", chdir_calls.append)

    def _noop_setup_proxy_functions(self: PythonInstance) -> None:
        _ = self

    monkeypatch.setattr(PythonInstance, "_setup_proxy_functions", _noop_setup_proxy_functions)

    instance = PythonInstance("boot")

    assert instance.session_id == "boot"
    assert instance.is_running is True
    assert chdir_calls == ["/workspace"]
    assert instance.shell.init_calls == ["completer", "history", "logger"]


def test_setup_proxy_functions_populates_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _make_instance()
    instance.shell.user_ns = {}

    fake_proxy_module = types.ModuleType("strix.tools.proxy.proxy_actions")
    proxy_names = [
        "list_requests",
        "list_sitemap",
        "repeat_request",
        "scope_rules",
        "send_request",
        "view_request",
        "view_sitemap_entry",
    ]
    for name in proxy_names:
        setattr(fake_proxy_module, name, object())

    fake_proxy_package = types.ModuleType("strix.tools.proxy")
    fake_proxy_package.proxy_actions = fake_proxy_module
    monkeypatch.setitem(sys.modules, "strix.tools.proxy", fake_proxy_package)
    monkeypatch.setitem(sys.modules, "strix.tools.proxy.proxy_actions", fake_proxy_module)

    instance._setup_proxy_functions()

    assert set(instance.shell.user_ns) >= set(proxy_names)


def test_setup_proxy_functions_ignores_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _make_instance()
    instance.shell.user_ns = {}
    original_import = builtins.__import__

    def _raise_proxy_import_error(name: str, *args, **kwargs):
        if name.startswith("strix.tools.proxy"):
            raise ImportError("proxy unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _raise_proxy_import_error)

    instance._setup_proxy_functions()

    assert instance.shell.user_ns == {}


def test_validate_session_when_stopped_returns_error_payload() -> None:
    instance = _make_instance(is_running=False)

    assert instance._validate_session() == {
        "session_id": "session-1",
        "stdout": "",
        "stderr": "Session is not running",
        "result": None,
    }


def test_truncate_output_returns_original_when_under_limit() -> None:
    instance = _make_instance()

    assert instance._truncate_output("abc", 10, "... truncated") == "abc"


def test_truncate_output_applies_suffix_when_over_limit() -> None:
    instance = _make_instance()

    assert instance._truncate_output("abcdef", 3, "...") == "abc..."


def test_format_execution_result_appends_result_repr_to_stdout() -> None:
    instance = _make_instance()

    payload = instance._format_execution_result(
        _exec_result(result={"ok": True}),
        "line without newline",
        "",
    )

    assert payload["stdout"] == "line without newline\n{'ok': True}"
    assert payload["result"] == "{'ok': True}"
    assert payload["stderr"] == ""


def test_format_execution_result_truncates_stderr() -> None:
    instance = _make_instance()
    long_stderr = "x" * (MAX_STDERR_LENGTH + 20)

    payload = instance._format_execution_result(_exec_result(result=None), "", long_stderr)

    assert payload["stderr"].endswith("... [stderr truncated at 5k chars]")
    assert payload["result"] is None


@pytest.mark.parametrize("error_flag", ["error_before_exec", "error_in_exec"])
def test_format_execution_result_sets_fallback_stderr_on_error_flags(
    error_flag: str,
) -> None:
    instance = _make_instance()
    kwargs = {"result": None, error_flag: object()}

    payload = instance._format_execution_result(_exec_result(**kwargs), "", "")

    assert payload["stderr"] == "Execution error occurred"


def test_handle_execution_error_truncates_error_message() -> None:
    instance = _make_instance()
    long_error = RuntimeError("e" * (MAX_STDERR_LENGTH + 1))

    payload = instance._handle_execution_error(long_error)

    assert payload["stderr"].endswith("... [error truncated at 5k chars]")
    assert payload["stdout"] == ""
    assert payload["result"] is None


def test_execute_code_returns_not_running_error_when_session_stopped() -> None:
    instance = _make_instance(is_running=False)

    payload = instance.execute_code("print('hi')")

    assert payload["stderr"] == "Session is not running"
    instance.shell.run_cell.assert_not_called()


def test_execute_code_timeout_returns_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _make_instance()

    class _StuckThread:
        def __init__(self, target, **kwargs) -> None:
            self._target = target
            self._kwargs = kwargs

        def start(self) -> None:
            return None

        def join(self, timeout=None) -> None:
            _ = timeout

        def is_alive(self) -> bool:
            return True

    monkeypatch.setattr(python_instance_module.threading, "Thread", _StuckThread)

    payload = instance.execute_code("print('slow')", timeout=7)

    assert payload["stderr"] == "Code execution timed out after 7 seconds"
    instance.shell.run_cell.assert_not_called()


def test_execute_code_returns_captured_exception_error() -> None:
    instance = _make_instance()
    instance.shell.run_cell.side_effect = ValueError("boom")

    payload = instance.execute_code("raise ValueError('boom')")

    assert payload["stderr"] == "boom"
    assert payload["stdout"] == ""
    assert payload["result"] is None


@pytest.mark.parametrize(
    ("raised", "expected_stderr"),
    [
        (KeyboardInterrupt(), ""),
        (SystemExit("stop"), "stop"),
    ],
)
def test_execute_code_handles_keyboardinterrupt_and_systemexit(
    raised: BaseException,
    expected_stderr: str,
) -> None:
    instance = _make_instance()
    instance.shell.run_cell.side_effect = raised

    payload = instance.execute_code("raise")

    assert payload["stderr"] == expected_stderr
    assert payload["stdout"] == ""
    assert payload["result"] is None


def test_execute_code_success_formats_execution_result() -> None:
    instance = _make_instance()
    instance.shell.run_cell.return_value = _exec_result(result=42)

    payload = instance.execute_code("42")

    assert payload["result"] == "42"
    assert payload["stdout"] == "42"
    assert payload["stderr"] == ""


def test_execute_code_returns_unknown_error_when_no_thread_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _make_instance()

    class _NoResultThread:
        def __init__(self, target, **kwargs) -> None:
            self._target = target
            self._kwargs = kwargs

        def start(self) -> None:
            return None

        def join(self, timeout=None) -> None:
            _ = timeout

        def is_alive(self) -> bool:
            return False

    monkeypatch.setattr(python_instance_module.threading, "Thread", _NoResultThread)

    payload = instance.execute_code("print('unreachable path')")

    assert payload["stderr"] == "Unknown execution error"
    instance.shell.run_cell.assert_not_called()


def test_close_sets_not_running_and_resets_shell() -> None:
    instance = _make_instance(is_running=True)

    instance.close()

    assert instance.is_running is False
    instance.shell.reset.assert_called_once_with(new_session=False)


@pytest.mark.parametrize("is_running", [True, False])
def test_is_alive_reflects_running_state(is_running: bool) -> None:
    instance = _make_instance(is_running=is_running)

    assert instance.is_alive() is is_running


def test_format_execution_result_truncates_combined_stdout_after_result_append() -> None:
    instance = _make_instance()
    long_stdout = "a" * MAX_STDOUT_LENGTH

    payload = instance._format_execution_result(_exec_result(result="b" * 100), long_stdout, "")

    assert payload["stdout"].endswith("... [output truncated at 10k chars]")
