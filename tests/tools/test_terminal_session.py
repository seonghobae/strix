"""Unit tests for terminal session helpers and command routing."""

# ruff: noqa: E402, I001

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# libtmux is optional outside sandbox extras; tests use lightweight fakes.
sys.modules.setdefault("libtmux", MagicMock())

import strix.tools.terminal.terminal_session as terminal_session_module
from strix.tools.terminal.terminal_session import (
    BashCommandStatus,
    TerminalSession,
    _remove_command_prefix,
)


class FakePane:
    """Tiny pane fake capturing send_keys calls."""

    def __init__(self) -> None:
        self.send_calls: list[tuple[str, bool]] = []

    def send_keys(self, command: str, enter: bool = True) -> None:
        self.send_calls.append((command, enter))


def _build_session(
    monkeypatch: pytest.MonkeyPatch,
    *,
    initialized: bool = True,
) -> TerminalSession:
    """Construct a TerminalSession instance without touching real libtmux."""

    def _fake_initialize(self: TerminalSession) -> None:
        self.server = None
        self.session = None
        self.window = None
        self.pane = None
        self.prev_status = None
        self.prev_output = ""
        self._closed = False
        self._cwd = self.work_dir
        self._initialized = initialized

    monkeypatch.setattr(TerminalSession, "initialize", _fake_initialize)
    return TerminalSession("session-1", work_dir="/tmp")


def test_ps1_property_returns_expected_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)

    assert session.PS1 == r"[STRIX_$?]$ "


def test_initialize_configures_tmux_state_with_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    class _InitPane(FakePane):
        def __init__(self) -> None:
            super().__init__()
            self.cmd_calls: list[tuple[str, ...]] = []

        def cmd(self, *args: str) -> SimpleNamespace:
            self.cmd_calls.append(args)
            return SimpleNamespace(stdout=[])

    class _InitialWindow:
        def __init__(self) -> None:
            self.killed = False

        def kill(self) -> None:
            self.killed = True

    class _SessionWindow:
        def __init__(self, pane: _InitPane) -> None:
            self.active_pane = pane

    class _TmuxSession:
        def __init__(self, pane: _InitPane, initial_window: _InitialWindow) -> None:
            self.active_window = initial_window
            self._pane = pane
            self.set_option_calls: list[tuple[str, str]] = []
            self.history_limit: int | None = None
            self.new_window_calls: list[dict[str, str]] = []

        def set_option(self, key: str, value: str) -> None:
            self.set_option_calls.append((key, value))

        def new_window(self, **kwargs: str) -> _SessionWindow:
            self.new_window_calls.append(kwargs)
            return _SessionWindow(self._pane)

    class _TmuxServer:
        def __init__(self, tmux_session: _TmuxSession) -> None:
            self._session = tmux_session
            self.new_session_calls: list[dict[str, object]] = []

        def new_session(self, **kwargs: object) -> _TmuxSession:
            self.new_session_calls.append(kwargs)
            return self._session

    pane = _InitPane()
    initial_window = _InitialWindow()
    tmux_session = _TmuxSession(pane, initial_window)
    tmux_server = _TmuxServer(tmux_session)
    sleep_calls: list[float] = []

    monkeypatch.setattr(terminal_session_module.libtmux, "Server", lambda: tmux_server)
    monkeypatch.setattr(terminal_session_module.time, "sleep", sleep_calls.append)

    session = TerminalSession("init-1", work_dir="/tmp")

    assert session._initialized is True
    assert tmux_server.new_session_calls[0]["session_name"].startswith("strix-init-1-")
    assert tmux_server.new_session_calls[0]["start_directory"] == session.work_dir
    assert tmux_session.set_option_calls == [("history-limit", str(TerminalSession.HISTORY_LIMIT))]
    assert tmux_session.history_limit == TerminalSession.HISTORY_LIMIT
    assert tmux_session.new_window_calls == [
        {
            "window_name": "bash",
            "window_shell": "/bin/bash",
            "start_directory": session.work_dir,
        }
    ]
    assert initial_window.killed is True
    assert pane.send_calls[0][0].startswith("export PROMPT_COMMAND=")
    assert pane.send_calls[1] == ("C-l", False)
    assert pane.cmd_calls == [("clear-history",)]
    assert sleep_calls == [0.1, 0.1]


def test_get_pane_content_requires_initialized_pane(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)
    session.pane = None

    with pytest.raises(RuntimeError, match="not properly initialized"):
        session._get_pane_content()


def test_get_pane_content_returns_joined_stripped_output(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)

    class _CapturePane:
        def cmd(self, *_args: str) -> SimpleNamespace:
            return SimpleNamespace(stdout=["line one   ", "line two  "])

    session.pane = _CapturePane()

    assert session._get_pane_content() == "line one\nline two"


def test_clear_screen_requires_pane(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)
    session.pane = None

    with pytest.raises(RuntimeError, match="not properly initialized"):
        session._clear_screen()


def test_clear_screen_sends_ctrl_l_and_clears_history(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)

    class _ClearPane(FakePane):
        def __init__(self) -> None:
            super().__init__()
            self.cmd_calls: list[tuple[str, ...]] = []

        def cmd(self, *args: str) -> SimpleNamespace:
            self.cmd_calls.append(args)
            return SimpleNamespace(stdout=[])

    pane = _ClearPane()
    sleep_calls: list[float] = []
    session.pane = pane
    monkeypatch.setattr(terminal_session_module.time, "sleep", sleep_calls.append)

    session._clear_screen()

    assert pane.send_calls == [("C-l", False)]
    assert pane.cmd_calls == [("clear-history",)]
    assert sleep_calls == [0.1]


def test_extract_exit_code_returns_none_for_no_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)

    assert session._extract_exit_code_from_matches([]) is None


def test_remove_command_prefix_removes_leading_command_text_regression() -> None:
    output = _remove_command_prefix("  ls -la\nfile.txt", "ls -la")

    assert output == "file.txt"


def test_remove_command_prefix_keeps_output_when_command_not_present() -> None:
    output = _remove_command_prefix("result line", "echo hi")

    assert output == "result line"


@pytest.mark.parametrize(
    ("command", "expected"),
    [("C-c", True), ("^D", True), ("S-Tab", True), ("M-a", True), ("noop", False)],
)
def test_control_key_classification(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    expected: bool,
) -> None:
    session = _build_session(monkeypatch)

    assert session._is_control_key(command) is expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [("F1", True), ("F12", True), ("F0", False), ("F13", False), ("Fn", False)],
)
def test_function_key_classification(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    expected: bool,
) -> None:
    session = _build_session(monkeypatch)

    assert session._is_function_key(command) is expected


def test_function_key_classification_handles_index_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)

    class _BrokenSliceStr(str):
        def __getitem__(self, _item: object) -> str:
            raise IndexError("slice failed")

    assert session._is_function_key(_BrokenSliceStr("F1")) is False


@pytest.mark.parametrize(
    ("command", "expected"),
    [("Up", True), ("PageDown", True), ("Tab", True), ("Escape", True), ("EnterX", False)],
)
def test_navigation_and_special_key_classification(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    expected: bool,
) -> None:
    session = _build_session(monkeypatch)

    assert session._is_navigation_or_special_key(command) is expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [("C-S-c", True), ("M-C-x", True), ("S-C-z", True), ("C-c", False), ("noop", False)],
)
def test_complex_modifier_key_classification(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    expected: bool,
) -> None:
    session = _build_session(monkeypatch)

    assert session._is_complex_modifier_key(command) is expected


def test_is_special_key_uses_trimmed_input(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)

    assert session._is_special_key("  C-c  ") is True
    assert session._is_special_key("   ") is False


def test_ps1_matching_and_exit_code_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)
    pane_content = "line\n[STRIX_7]]$ "

    matches = session._matches_ps1_metadata(pane_content)

    assert len(matches) == 1
    assert session._extract_exit_code_from_matches(matches) == 7


def test_extract_exit_code_returns_none_when_match_group_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)

    class _BrokenMatch:
        def group(self, _index: int) -> str:
            raise ValueError("invalid group")

    assert session._extract_exit_code_from_matches([_BrokenMatch()]) is None


def test_combine_outputs_between_matches_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)

    single = "before\n[STRIX_0]]$ \nafter"
    single_matches = session._matches_ps1_metadata(single)
    assert session._combine_outputs_between_matches(single, single_matches) == "after"
    assert (
        session._combine_outputs_between_matches(
            single,
            single_matches,
            get_content_before_last_match=True,
        )
        == "before\n"
    )

    multiple = "one\n[STRIX_0]]$ \ntwo\n[STRIX_1]]$ \nthree"
    multi_matches = session._matches_ps1_metadata(multiple)
    assert session._combine_outputs_between_matches(multiple, multi_matches) == "two\n\nthree"

    assert session._combine_outputs_between_matches("raw-no-match", []) == "raw-no-match"


def test_get_command_output_removes_command_and_tracks_previous_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)

    output = session._get_command_output("echo hi", "echo hi\nhello")

    assert output == "hello"
    assert session.prev_output == "echo hi\nhello"


def test_get_command_output_uses_prev_output_and_continue_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    session.prev_output = "older"

    output = session._get_command_output("", "older\nnext", continue_prefix="[continue]\n")

    assert output == "[continue]\n\nnext"
    assert session.prev_output == "older\nnext"


def test_get_command_output_uses_prev_output_without_continue_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    session.prev_output = "older"

    output = session._get_command_output("", "older\nnext")

    assert output == "next"
    assert session.prev_output == "older\nnext"


def test_execute_raises_when_session_not_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch, initialized=False)

    with pytest.raises(RuntimeError, match="not initialized"):
        session.execute("echo hi")


def test_execute_routes_empty_command_to_empty_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)
    monkeypatch.setattr(session, "_get_pane_content", lambda: "ready]$ ")
    monkeypatch.setattr(session, "_matches_ps1_metadata", lambda _content: [])

    captured: dict[str, object] = {}

    def _fake_empty_handler(
        cur_pane_output: str,
        ps1_matches: list[object],
        is_command_running: bool,
        timeout: float,
    ) -> dict[str, str]:
        captured["args"] = (cur_pane_output, ps1_matches, is_command_running, timeout)
        return {"status": "completed", "content": ""}

    monkeypatch.setattr(session, "_handle_empty_command", _fake_empty_handler)

    result = session.execute("   ", timeout=3.5)

    assert result == {"status": "completed", "content": ""}
    assert captured["args"] == ("ready]$ ", [], False, 3.5)


def test_execute_routes_input_path_to_input_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)
    monkeypatch.setattr(session, "_get_pane_content", lambda: "ready]$ ")
    monkeypatch.setattr(session, "_matches_ps1_metadata", lambda _content: [])

    observed: list[tuple[str, bool, bool]] = []

    def _fake_input_handler(
        command: str, no_enter: bool, is_command_running: bool
    ) -> dict[str, str]:
        observed.append((command, no_enter, is_command_running))
        return {"status": "running", "content": "typed"}

    monkeypatch.setattr(session, "_handle_input_command", _fake_input_handler)

    result = session.execute("answer", is_input=True)

    assert result == {"status": "running", "content": "typed"}
    assert observed == [("answer", False, False)]


def test_execute_routes_special_key_to_input_handler_when_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    monkeypatch.setattr(session, "_get_pane_content", lambda: "process is still running")
    monkeypatch.setattr(session, "_matches_ps1_metadata", lambda _content: [])

    observed: list[tuple[str, bool, bool]] = []

    def _fake_input_handler(
        command: str, no_enter: bool, is_command_running: bool
    ) -> dict[str, str]:
        observed.append((command, no_enter, is_command_running))
        return {"status": "running", "content": "interrupt sent"}

    monkeypatch.setattr(session, "_handle_input_command", _fake_input_handler)

    result = session.execute("C-c")

    assert result == {"status": "running", "content": "interrupt sent"}
    assert observed == [("C-c", False, True)]


def test_execute_returns_error_when_non_input_command_arrives_while_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    monkeypatch.setattr(session, "_get_pane_content", lambda: "still running")
    monkeypatch.setattr(session, "_matches_ps1_metadata", lambda _content: [])

    result = session.execute("ls -la")

    assert result["status"] == "error"
    assert "already running" in result["content"]
    assert result["exit_code"] is None
    assert result["working_dir"] == session.get_working_dir()


def test_execute_routes_ready_shell_to_new_command_path(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)
    monkeypatch.setattr(session, "_get_pane_content", lambda: "ready]$ ")
    monkeypatch.setattr(session, "_matches_ps1_metadata", lambda _content: [])

    observed: list[tuple[str, bool, float]] = []

    def _fake_execute_new(command: str, no_enter: bool, timeout: float) -> dict[str, str]:
        observed.append((command, no_enter, timeout))
        return {"status": "completed", "content": "ok"}

    monkeypatch.setattr(session, "_execute_new_command", _fake_execute_new)

    result = session.execute("pwd", no_enter=True, timeout=8.0)

    assert result == {"status": "completed", "content": "ok"}
    assert observed == [("pwd", True, 8.0)]


def test_handle_empty_command_returns_completed_when_nothing_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)

    result = session._handle_empty_command(
        cur_pane_output="plain output",
        ps1_matches=[],
        is_command_running=False,
        timeout=5.0,
    )

    assert result == {
        "content": "plain output",
        "status": "completed",
        "exit_code": 0,
        "working_dir": session.get_working_dir(),
    }


def test_handle_empty_command_running_path_completes_when_prompt_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    monkeypatch.setattr(session, "_get_pane_content", lambda: "done\n[STRIX_4]]$ ")

    ready_calls: list[str] = []
    monkeypatch.setattr(session, "_ready_for_next_command", lambda: ready_calls.append("ready"))

    result = session._handle_empty_command(
        cur_pane_output="still running",
        ps1_matches=[],
        is_command_running=True,
        timeout=5.0,
    )

    assert result["status"] == "completed"
    assert result["exit_code"] == 4
    assert session.prev_status == BashCommandStatus.COMPLETED
    assert session.prev_output == ""
    assert ready_calls == ["ready"]


def test_handle_empty_command_running_path_timeout_returns_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    monkeypatch.setattr(session, "_get_pane_content", lambda: "still running")
    monkeypatch.setattr(terminal_session_module.time, "sleep", lambda _seconds: None)

    times = iter([0.0, 1.0])
    monkeypatch.setattr(terminal_session_module.time, "time", lambda: next(times))

    result = session._handle_empty_command(
        cur_pane_output="still running",
        ps1_matches=[],
        is_command_running=True,
        timeout=0.5,
    )

    assert result["status"] == "running"
    assert result["exit_code"] is None
    assert "still running after 0.5s" in result["content"]


def test_handle_empty_command_running_path_tracks_output_changes_before_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    pane_outputs = iter(["progress", "progress"])
    monkeypatch.setattr(session, "_get_pane_content", lambda: next(pane_outputs))
    monkeypatch.setattr(session, "_matches_ps1_metadata", lambda _content: [])

    sleep_calls: list[float] = []
    monkeypatch.setattr(terminal_session_module.time, "sleep", sleep_calls.append)

    times = iter([0.0, 0.1, 0.6])
    monkeypatch.setattr(terminal_session_module.time, "time", lambda: next(times))

    result = session._handle_empty_command(
        cur_pane_output="still running",
        ps1_matches=[],
        is_command_running=True,
        timeout=0.5,
    )

    assert result["status"] == "running"
    assert result["exit_code"] is None
    assert "progress" in result["content"]
    assert sleep_calls == [session.POLL_INTERVAL]


def test_handle_empty_command_running_path_sleeps_when_output_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    pane_outputs = iter(["progress", "progress", "done\n[STRIX_0]]$ "])
    monkeypatch.setattr(session, "_get_pane_content", lambda: next(pane_outputs))

    ready_calls: list[str] = []
    monkeypatch.setattr(session, "_ready_for_next_command", lambda: ready_calls.append("ready"))

    sleep_calls: list[float] = []
    monkeypatch.setattr(terminal_session_module.time, "sleep", sleep_calls.append)

    times = iter([0.0, 0.1, 0.2])
    monkeypatch.setattr(terminal_session_module.time, "time", lambda: next(times))

    result = session._handle_empty_command(
        cur_pane_output="still running",
        ps1_matches=[],
        is_command_running=True,
        timeout=1.0,
    )

    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert sleep_calls == [session.POLL_INTERVAL, session.POLL_INTERVAL]
    assert ready_calls == ["ready"]


def test_execute_new_command_completed_path(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)
    pane = FakePane()
    session.pane = pane

    outputs = iter(["ready]$ ", "result\n[STRIX_0]]$ "])
    monkeypatch.setattr(session, "_get_pane_content", lambda: next(outputs))

    ready_calls: list[str] = []
    monkeypatch.setattr(session, "_ready_for_next_command", lambda: ready_calls.append("ready"))

    result = session._execute_new_command("echo hi", no_enter=False, timeout=3.0)

    assert pane.send_calls == [("echo hi", True)]
    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert "result" in result["content"]
    assert session.prev_status == BashCommandStatus.COMPLETED
    assert session.prev_output == ""
    assert ready_calls == ["ready"]


def test_execute_new_command_timeout_sets_continue_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    pane = FakePane()
    session.pane = pane
    outputs = iter(["start", "still-running"])
    monkeypatch.setattr(session, "_get_pane_content", lambda: next(outputs))
    monkeypatch.setattr(terminal_session_module.time, "sleep", lambda _seconds: None)

    times = iter([0.0, 2.0])
    monkeypatch.setattr(terminal_session_module.time, "time", lambda: next(times))

    result = session._execute_new_command("long-job", no_enter=False, timeout=1.0)

    assert pane.send_calls == [("long-job", True)]
    assert result["status"] == "running"
    assert result["exit_code"] is None
    assert result["content"].startswith("still-running")
    assert "still running after 1.0s" in result["content"]
    assert session.prev_status == BashCommandStatus.CONTINUE


def test_execute_new_command_loops_and_sleeps_before_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    pane = FakePane()
    session.pane = pane

    outputs = iter(["busy", "busy", "result\n[STRIX_0]]$ "])
    monkeypatch.setattr(session, "_get_pane_content", lambda: next(outputs))

    sleep_calls: list[float] = []
    monkeypatch.setattr(terminal_session_module.time, "sleep", sleep_calls.append)

    ready_calls: list[str] = []
    monkeypatch.setattr(session, "_ready_for_next_command", lambda: ready_calls.append("ready"))

    result = session._execute_new_command("echo hi", no_enter=False, timeout=3.0)

    assert pane.send_calls == [("echo hi", True)]
    assert result["status"] == "completed"
    assert result["exit_code"] == 0
    assert sleep_calls == [session.POLL_INTERVAL]
    assert ready_calls == ["ready"]


def test_execute_new_command_raises_when_pane_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)
    session.pane = None

    with pytest.raises(RuntimeError, match="not properly initialized"):
        session._execute_new_command("pwd", no_enter=False, timeout=1.0)


def test_handle_input_command_returns_error_when_no_command_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)

    result = session._handle_input_command("hello", no_enter=False, is_command_running=False)

    assert result == {
        "content": "No command is currently running. Cannot send input.",
        "status": "error",
        "exit_code": None,
        "working_dir": session.get_working_dir(),
    }


def test_handle_input_command_raises_when_running_but_pane_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    session.pane = None

    with pytest.raises(RuntimeError, match="not properly initialized"):
        session._handle_input_command("text", no_enter=False, is_command_running=True)


def test_handle_input_command_running_path_uses_enter_for_regular_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    pane = FakePane()
    session.pane = pane
    monkeypatch.setattr(terminal_session_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(session, "_get_pane_content", lambda: "still-running")
    monkeypatch.setattr(session, "_matches_ps1_metadata", lambda _content: [])

    result = session._handle_input_command("typed text", no_enter=False, is_command_running=True)

    assert pane.send_calls == [("typed text", True)]
    assert result["status"] == "running"
    assert result["exit_code"] is None


def test_handle_input_command_completed_path_special_key_skips_enter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    pane = FakePane()
    session.pane = pane
    monkeypatch.setattr(terminal_session_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(session, "_get_pane_content", lambda: "line\n[STRIX_3]]$ ")

    ready_calls: list[str] = []
    monkeypatch.setattr(session, "_ready_for_next_command", lambda: ready_calls.append("ready"))

    result = session._handle_input_command("C-c", no_enter=False, is_command_running=True)

    assert pane.send_calls == [("C-c", False)]
    assert result["status"] == "completed"
    assert result["exit_code"] == 3
    assert session.prev_status == BashCommandStatus.COMPLETED
    assert session.prev_output == ""
    assert ready_calls == ["ready"]


def test_is_running_returns_true_when_session_exists_on_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    session._closed = False
    session.session = SimpleNamespace(id="s-1")
    session.server = SimpleNamespace(
        sessions=[SimpleNamespace(id="s-1"), SimpleNamespace(id="s-2")]
    )

    assert session.is_running() is True


def test_is_running_returns_false_when_session_closed_or_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    session._closed = True
    session.session = SimpleNamespace(id="s-1")

    assert session.is_running() is False

    session._closed = False
    session.session = None
    assert session.is_running() is False


def test_is_running_returns_false_when_server_lookup_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    session._closed = False
    session.session = SimpleNamespace(id="s-1")

    class _BrokenServer:
        @property
        def sessions(self) -> list[object]:
            raise OSError("session list unavailable")

    session.server = _BrokenServer()

    assert session.is_running() is False


def test_close_kills_session_and_clears_references(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)
    tmux_session = MagicMock()
    session.session = tmux_session
    session.server = object()
    session.window = object()
    session.pane = object()

    session.close()

    tmux_session.kill.assert_called_once_with()
    assert session._closed is True
    assert session.server is None
    assert session.session is None
    assert session.window is None
    assert session.pane is None


def test_close_returns_early_when_already_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)
    tmux_session = MagicMock()
    session._closed = True
    session.session = tmux_session

    session.close()

    tmux_session.kill.assert_not_called()


def test_close_swallows_kill_errors_and_still_clears_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    tmux_session = MagicMock()
    tmux_session.kill.side_effect = OSError("cannot kill")
    session.session = tmux_session
    session.server = object()
    session.window = object()
    session.pane = object()

    session.close()

    assert session._closed is True
    assert session.server is None
    assert session.session is None
    assert session.window is None
    assert session.pane is None


def test_close_without_session_still_clears_references(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _build_session(monkeypatch)
    session.session = None
    session.server = object()
    session.window = object()
    session.pane = object()

    session.close()

    assert session._closed is True
    assert session.server is None
    assert session.session is None
    assert session.window is None
    assert session.pane is None


def test_ready_for_next_command_delegates_to_clear_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _build_session(monkeypatch)
    clear_calls: list[str] = []
    monkeypatch.setattr(session, "_clear_screen", lambda: clear_calls.append("cleared"))

    session._ready_for_next_command()

    assert clear_calls == ["cleared"]
