"""Tests for agent graph actions and helpers."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from strix.tools.agents_graph import agents_graph_actions as aga


class DummyState:
    """Minimal agent state for tests."""

    def __init__(
        self,
        *,
        agent_id: str,
        parent_id: str | None,
        agent_name: str,
        task: str,
    ) -> None:
        self.agent_id = agent_id
        self.parent_id = parent_id
        self.agent_name = agent_name
        self.task = task
        self.stop_requested = False
        self.added_messages: list[tuple[str, str]] = []
        self.waiting_entered = False

    def add_message(self, role: str, content: str) -> None:
        self.added_messages.append((role, content))

    def model_dump(self) -> dict[str, str | None]:
        return {
            "agent_id": self.agent_id,
            "parent_id": self.parent_id,
            "agent_name": self.agent_name,
            "task": self.task,
        }

    def request_stop(self) -> None:
        self.stop_requested = True

    def enter_waiting_state(self) -> None:
        self.waiting_entered = True


@pytest.fixture(autouse=True)
def reset_agent_graph_globals() -> None:
    """Reset all mutable global stores before each test."""
    aga._agent_graph["nodes"].clear()
    aga._agent_graph["edges"].clear()
    aga._root_agent_id = None
    aga._agent_messages.clear()
    aga._running_agents.clear()
    aga._agent_instances.clear()
    aga._agent_states.clear()
    yield
    aga._agent_graph["nodes"].clear()
    aga._agent_graph["edges"].clear()
    aga._root_agent_id = None
    aga._agent_messages.clear()
    aga._running_agents.clear()
    aga._agent_instances.clear()
    aga._agent_states.clear()


def test_run_agent_in_thread_success_marks_completed_and_cleans_stores() -> None:
    """Thread runner marks completed and clears running/instance caches."""

    class Agent:
        async def agent_loop(self, task: str) -> dict[str, str]:
            return {"task": task, "status": "ok"}

    state = DummyState(
        agent_id="child-1", parent_id="parent-1", agent_name="Child", task="do thing"
    )
    aga._agent_graph["nodes"]["parent-1"] = {
        "name": "Parent",
        "status": "running",
        "task": "parent",
    }
    aga._agent_graph["nodes"]["child-1"] = {
        "name": "Child",
        "status": "running",
        "task": "do thing",
        "parent_id": "parent-1",
    }
    aga._running_agents["child-1"] = MagicMock()
    aga._agent_instances["child-1"] = MagicMock()

    result = aga._run_agent_in_thread(Agent(), state, [{"role": "user", "content": "hello"}])

    assert result == {"result": {"task": "do thing", "status": "ok"}}
    assert aga._agent_graph["nodes"]["child-1"]["status"] == "completed"
    assert aga._agent_graph["nodes"]["child-1"]["result"] == {"task": "do thing", "status": "ok"}
    assert "child-1" not in aga._running_agents
    assert "child-1" not in aga._agent_instances
    assert aga._agent_states["child-1"] is state
    assert ("user", "<inherited_context_from_parent>") in state.added_messages
    assert ("user", "</inherited_context_from_parent>") in state.added_messages


def test_run_agent_in_thread_stop_requested_marks_stopped() -> None:
    """Thread runner marks stopped when state.stop_requested is set."""

    class Agent:
        async def agent_loop(self, _task: str) -> dict[str, str]:
            return {"ok": "yes"}

    state = DummyState(
        agent_id="child-1", parent_id="parent-1", agent_name="Child", task="do thing"
    )
    state.stop_requested = True
    aga._agent_graph["nodes"]["parent-1"] = {
        "name": "Parent",
        "status": "running",
        "task": "parent",
    }
    aga._agent_graph["nodes"]["child-1"] = {
        "name": "Child",
        "status": "running",
        "task": "do thing",
        "parent_id": "parent-1",
    }

    aga._run_agent_in_thread(Agent(), state, [])

    assert aga._agent_graph["nodes"]["child-1"]["status"] == "stopped"


def test_run_agent_in_thread_exception_sets_error_and_reraises() -> None:
    """Thread runner updates error state then re-raises underlying exception."""

    class Agent:
        async def agent_loop(self, _task: str) -> dict[str, str]:
            msg = "boom"
            raise RuntimeError(msg)

    state = DummyState(
        agent_id="child-1", parent_id="parent-1", agent_name="Child", task="do thing"
    )
    aga._agent_graph["nodes"]["parent-1"] = {
        "name": "Parent",
        "status": "running",
        "task": "parent",
    }
    aga._agent_graph["nodes"]["child-1"] = {
        "name": "Child",
        "status": "running",
        "task": "do thing",
        "parent_id": "parent-1",
    }
    aga._running_agents["child-1"] = MagicMock()
    aga._agent_instances["child-1"] = MagicMock()

    with pytest.raises(RuntimeError, match="boom"):
        aga._run_agent_in_thread(Agent(), state, [])

    assert aga._agent_graph["nodes"]["child-1"]["status"] == "error"
    assert aga._agent_graph["nodes"]["child-1"]["result"] == {"error": "boom"}
    assert "child-1" not in aga._running_agents
    assert "child-1" not in aga._agent_instances


def test_view_agent_graph_tree_and_summary_counts() -> None:
    """Graph viewer builds hierarchy from delegation edges and computes counters."""
    aga._root_agent_id = "root"
    aga._agent_graph["nodes"].update(
        {
            "root": {"name": "Root", "task": "root-task", "status": "running", "parent_id": None},
            "child": {
                "name": "Child",
                "task": "child-task",
                "status": "completed",
                "parent_id": "root",
            },
            "wait": {"name": "Wait", "task": "wait-task", "status": "waiting", "parent_id": "root"},
            "stop": {
                "name": "Stop",
                "task": "stop-task",
                "status": "stopping",
                "parent_id": "root",
            },
            "halt": {"name": "Halt", "task": "halt-task", "status": "stopped", "parent_id": "root"},
            "err": {"name": "Err", "task": "err-task", "status": "error", "parent_id": "root"},
            "fail": {"name": "Fail", "task": "fail-task", "status": "failed", "parent_id": "root"},
        }
    )
    aga._agent_graph["edges"].extend(
        [
            {"from": "root", "to": "child", "type": "delegation"},
            {"from": "root", "to": "wait", "type": "delegation"},
            {"from": "root", "to": "stop", "type": "delegation"},
            {"from": "root", "to": "child", "type": "message"},
        ]
    )

    result = aga.view_agent_graph(SimpleNamespace(agent_id="child"))
    assert "=== AGENT GRAPH STRUCTURE ===" in result["graph_structure"]
    assert "Root (root)" in result["graph_structure"]
    assert "Child (child) ← This is you" in result["graph_structure"]
    assert "Wait (wait)" in result["graph_structure"]
    assert result["summary"] == {
        "total_agents": 7,
        "running": 1,
        "waiting": 1,
        "stopping": 1,
        "completed": 1,
        "stopped": 1,
        "failed": 2,
    }


def test_view_agent_graph_fallback_root_and_empty_graph() -> None:
    """Graph viewer falls back to parentless/first node and handles empty graph."""
    aga._agent_graph["nodes"]["a"] = {
        "name": "A",
        "task": "ta",
        "status": "running",
        "parent_id": None,
    }
    aga._agent_graph["nodes"]["b"] = {
        "name": "B",
        "task": "tb",
        "status": "running",
        "parent_id": "a",
    }

    fallback = aga.view_agent_graph(SimpleNamespace(agent_id="a"))
    assert "A (a)" in fallback["graph_structure"]

    aga._agent_graph["nodes"].clear()
    empty = aga.view_agent_graph(SimpleNamespace(agent_id="a"))
    assert "No agents in the graph yet" in empty["graph_structure"]


def test_view_agent_graph_exception_returns_error_payload() -> None:
    """Graph viewer returns error payload when malformed graph causes exception."""
    aga._agent_graph["nodes"]["x"] = {"name": "X", "status": "running"}
    result = aga.view_agent_graph(SimpleNamespace(agent_id="x"))
    assert result["graph_structure"] == "Error retrieving graph structure"
    assert result["error"].startswith("Failed to view agent graph:")


def test_create_agent_validation_error_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_agent exits early when requested skills fail validation."""
    monkeypatch.setattr("strix.skills.parse_skill_list", lambda _skills: ["bad"])
    monkeypatch.setattr("strix.skills.validate_requested_skills", lambda _lst: "skill invalid")

    result = aga.create_agent(
        SimpleNamespace(agent_id="parent"), task="t", name="child", skills="bad"
    )

    assert result == {"success": False, "error": "skill invalid", "agent_id": None}


def test_create_agent_success_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_agent builds state/agent/thread and starts asynchronous execution."""
    monkeypatch.setattr("strix.skills.parse_skill_list", lambda _skills: ["s1"])
    monkeypatch.setattr("strix.skills.validate_requested_skills", lambda _lst: None)

    class FakeAgentState:
        def __init__(
            self,
            task: str,
            agent_name: str,
            parent_id: str,
            max_iterations: int,
            waiting_timeout: int,
        ):
            self.task = task
            self.agent_name = agent_name
            self.parent_id = parent_id
            self.max_iterations = max_iterations
            self.waiting_timeout = waiting_timeout
            self.agent_id = "child-1"

    class FakeLLMConfig:
        def __init__(
            self, skills: list[str], timeout: int | None, scan_mode: str, interactive: bool
        ):
            self.skills = skills
            self.timeout = timeout
            self.scan_mode = scan_mode
            self.interactive = interactive

    class FakeStrixAgent:
        def __init__(self, cfg: dict[str, object]) -> None:
            self.llm_config = cfg["llm_config"]
            self.state = cfg["state"]

    created_threads: list[object] = []

    class FakeThread:
        def __init__(
            self, target: object, args: tuple[object, ...], daemon: bool, name: str
        ) -> None:
            self.target = target
            self.args = args
            self.daemon = daemon
            self.name = name
            self.started = False
            created_threads.append(self)

        def start(self) -> None:
            self.started = True

    monkeypatch.setitem(sys.modules, "strix.agents", SimpleNamespace(StrixAgent=FakeStrixAgent))
    monkeypatch.setitem(
        sys.modules, "strix.agents.state", SimpleNamespace(AgentState=FakeAgentState)
    )
    monkeypatch.setitem(sys.modules, "strix.llm.config", SimpleNamespace(LLMConfig=FakeLLMConfig))
    monkeypatch.setattr(aga.threading, "Thread", FakeThread)

    parent_agent = SimpleNamespace(
        llm_config=SimpleNamespace(timeout=30, scan_mode="quick", interactive=True)
    )
    aga._agent_instances["parent"] = parent_agent

    parent_state = SimpleNamespace(
        agent_id="parent", get_conversation_history=lambda: [{"role": "user", "content": "hi"}]
    )
    result = aga.create_agent(
        parent_state, task="do task", name="Child", inherit_context=True, skills="s1"
    )

    assert result["success"] is True
    assert result["agent_id"] == "child-1"
    assert result["agent_info"] == {
        "id": "child-1",
        "name": "Child",
        "status": "running",
        "parent_id": "parent",
    }
    assert len(created_threads) == 1
    thread = created_threads[0]
    assert thread.started is True
    assert thread.daemon is True
    assert thread.name == "Agent-Child-child-1"
    _, created_state, inherited = thread.args
    assert created_state.waiting_timeout == 300
    assert created_state.max_iterations == 300
    assert inherited == [{"role": "user", "content": "hi"}]
    assert "child-1" in aga._running_agents


def test_create_agent_defaults_and_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_agent uses defaults without parent config and returns outer exceptions."""
    monkeypatch.setattr("strix.skills.parse_skill_list", lambda _skills: [])
    monkeypatch.setattr("strix.skills.validate_requested_skills", lambda _lst: None)

    class FakeAgentState:
        def __init__(
            self,
            task: str,
            agent_name: str,
            parent_id: str,
            max_iterations: int,
            waiting_timeout: int,
        ):
            self.task = task
            self.agent_name = agent_name
            self.parent_id = parent_id
            self.max_iterations = max_iterations
            self.waiting_timeout = waiting_timeout
            self.agent_id = "child-2"

    class FakeLLMConfig:
        def __init__(
            self, skills: list[str], timeout: int | None, scan_mode: str, interactive: bool
        ):
            self.skills = skills
            self.timeout = timeout
            self.scan_mode = scan_mode
            self.interactive = interactive

    class BrokenStrixAgent:
        def __init__(self, _cfg: dict[str, object]) -> None:
            msg = "ctor failed"
            raise RuntimeError(msg)

    monkeypatch.setitem(sys.modules, "strix.agents", SimpleNamespace(StrixAgent=BrokenStrixAgent))
    monkeypatch.setitem(
        sys.modules, "strix.agents.state", SimpleNamespace(AgentState=FakeAgentState)
    )
    monkeypatch.setitem(sys.modules, "strix.llm.config", SimpleNamespace(LLMConfig=FakeLLMConfig))

    result = aga.create_agent(
        SimpleNamespace(
            agent_id="parent", get_conversation_history=lambda: [{"role": "x", "content": "y"}]
        ),
        task="do task",
        name="Child",
        inherit_context=False,
    )
    assert result == {
        "success": False,
        "error": "Failed to create agent: ctor failed",
        "agent_id": None,
    }


def test_create_agent_fast_completion_does_not_leave_stale_running_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fast-finishing thread should not leave stale entry in _running_agents."""
    monkeypatch.setattr("strix.skills.parse_skill_list", lambda _skills: [])
    monkeypatch.setattr("strix.skills.validate_requested_skills", lambda _lst: None)

    class FakeAgentState:
        def __init__(
            self,
            task: str,
            agent_name: str,
            parent_id: str,
            max_iterations: int,
            waiting_timeout: int,
        ):
            self.task = task
            self.agent_name = agent_name
            self.parent_id = parent_id
            self.max_iterations = max_iterations
            self.waiting_timeout = waiting_timeout
            self.agent_id = "fast-child"

    class FakeLLMConfig:
        def __init__(
            self, skills: list[str], timeout: int | None, scan_mode: str, interactive: bool
        ):
            self.skills = skills
            self.timeout = timeout
            self.scan_mode = scan_mode
            self.interactive = interactive

    class FakeStrixAgent:
        def __init__(self, cfg: dict[str, object]) -> None:
            self.llm_config = cfg["llm_config"]
            self.state = cfg["state"]

    class InlineThread:
        def __init__(
            self, target: object, args: tuple[object, ...], daemon: bool, name: str
        ) -> None:
            self.target = target
            self.args = args
            self.daemon = daemon
            self.name = name

        def start(self) -> None:
            self.target(*self.args)

    def fake_run(
        _agent: object, state: DummyState, _inherited: list[dict[str, object]]
    ) -> dict[str, object]:
        aga._running_agents.pop(state.agent_id, None)
        return {"result": "done"}

    monkeypatch.setitem(sys.modules, "strix.agents", SimpleNamespace(StrixAgent=FakeStrixAgent))
    monkeypatch.setitem(
        sys.modules, "strix.agents.state", SimpleNamespace(AgentState=FakeAgentState)
    )
    monkeypatch.setitem(sys.modules, "strix.llm.config", SimpleNamespace(LLMConfig=FakeLLMConfig))
    monkeypatch.setattr(aga.threading, "Thread", InlineThread)
    monkeypatch.setattr(aga, "_run_agent_in_thread", fake_run)

    result = aga.create_agent(
        SimpleNamespace(agent_id="parent", get_conversation_history=list),
        task="fast",
        name="Fast",
        inherit_context=False,
    )

    assert result["success"] is True
    assert "fast-child" not in aga._running_agents


def test_send_message_to_agent_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_message_to_agent handles missing target, success, and sender errors."""
    missing = aga.send_message_to_agent(SimpleNamespace(agent_id="sender"), "missing", "hello")
    assert missing == {
        "success": False,
        "error": "Target agent 'missing' not found in graph",
        "message_id": None,
    }

    class _UUID:
        hex = "abcdef123456"

    monkeypatch.setattr("uuid.uuid4", lambda: _UUID())
    aga._agent_graph["nodes"]["sender"] = {"name": "Sender", "status": "running"}
    aga._agent_graph["nodes"]["target"] = {"name": "Target", "status": "waiting"}

    success = aga.send_message_to_agent(
        SimpleNamespace(agent_id="sender"),
        "target",
        "hello",
        message_type="instruction",
        priority="urgent",
    )
    assert success["success"] is True
    assert success["message_id"].startswith("msg_")
    assert success["target_agent"] == {"id": "target", "name": "Target", "status": "waiting"}
    assert aga._agent_messages["target"][0]["delivered"] is True
    assert aga._agent_graph["edges"][0]["type"] == "message"

    del aga._agent_graph["nodes"]["sender"]
    sender_missing = aga.send_message_to_agent(
        SimpleNamespace(agent_id="sender"), "target", "hello"
    )
    assert sender_missing["success"] is False
    assert sender_missing["message_id"] is None
    assert sender_missing["error"].startswith("Failed to send message:")


def test_agent_finish_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """agent_finish enforces subagent usage, writes results, and notifies parent."""
    root = aga.agent_finish(SimpleNamespace(agent_id="root", parent_id=None), "summary")
    assert root == {
        "agent_completed": False,
        "error": (
            "This tool can only be used by subagents. "
            "Root/main agents must use finish_scan instead."
        ),
        "parent_notified": False,
    }

    missing = aga.agent_finish(SimpleNamespace(agent_id="a1", parent_id="p1"), "summary")
    assert missing == {"agent_completed": False, "error": "Current agent not found in graph"}

    class _UUID:
        hex = "1234567890ab"

    monkeypatch.setattr("uuid.uuid4", lambda: _UUID())
    aga._agent_graph["nodes"]["parent"] = {"name": "Parent", "status": "running", "task": "parent"}
    aga._agent_graph["nodes"]["child"] = {
        "name": "Child",
        "status": "running",
        "task": "task",
        "parent_id": "parent",
    }
    aga._running_agents["child"] = MagicMock()

    success = aga.agent_finish(
        SimpleNamespace(agent_id="child", parent_id="parent"),
        result_summary="done",
        findings=["f1", "f2"],
        success=True,
        report_to_parent=True,
        final_recommendations=["r1"],
    )
    assert success["agent_completed"] is True
    assert success["parent_notified"] is True
    assert success["completion_summary"]["findings_count"] == 2
    assert success["completion_summary"]["has_recommendations"] is True
    assert aga._agent_graph["nodes"]["child"]["status"] == "finished"
    assert aga._agent_messages["parent"][0]["id"].startswith("report_")
    assert "child" not in aga._running_agents

    aga._agent_graph["nodes"]["child2"] = {
        "name": "Child2",
        "status": "running",
        "task": "task2",
        "parent_id": "parent",
    }
    failed = aga.agent_finish(
        SimpleNamespace(agent_id="child2", parent_id="parent"),
        result_summary="failed",
        success=False,
        report_to_parent=False,
    )
    assert failed["agent_completed"] is True
    assert failed["parent_notified"] is False
    assert aga._agent_graph["nodes"]["child2"]["status"] == "failed"

    aga._agent_graph["nodes"]["boom"] = {"parent_id": "parent"}
    errored = aga.agent_finish(SimpleNamespace(agent_id="boom", parent_id="parent"), "oops")
    assert errored["agent_completed"] is False
    assert errored["parent_notified"] is False
    assert errored["error"].startswith("Failed to complete agent:")


def test_stop_agent_paths_with_tracer(monkeypatch: pytest.MonkeyPatch) -> None:
    """stop_agent handles not found, terminal, active, tracer, and exceptions."""
    missing = aga.stop_agent("missing")
    assert missing == {
        "success": False,
        "error": "Agent 'missing' not found in graph",
        "agent_id": "missing",
    }

    for status in ["completed", "error", "failed", "stopped"]:
        aga._agent_graph["nodes"]["terminal"] = {"name": "T", "status": status}
        terminal = aga.stop_agent("terminal")
        assert terminal == {
            "success": True,
            "message": "Agent 'T' was already stopped",
            "agent_id": "terminal",
            "previous_status": status,
        }

    tracer = MagicMock()
    monkeypatch.setitem(
        sys.modules,
        "strix.telemetry.tracer",
        SimpleNamespace(get_global_tracer=lambda: tracer),
    )
    state = DummyState(agent_id="active", parent_id="root", agent_name="A", task="t")
    agent_instance_state = DummyState(agent_id="active", parent_id="root", agent_name="A", task="t")
    agent_instance = SimpleNamespace(
        state=agent_instance_state,
        cancel_current_execution=MagicMock(),
    )
    aga._agent_graph["nodes"]["active"] = {"name": "A", "status": "running"}
    aga._agent_states["active"] = state
    aga._agent_instances["active"] = agent_instance

    active = aga.stop_agent("active")
    assert active == {
        "success": True,
        "message": "Stop request sent to agent 'A'",
        "agent_id": "active",
        "agent_name": "A",
        "note": "Agent will stop gracefully after current iteration",
    }
    assert aga._agent_graph["nodes"]["active"]["status"] == "stopping"
    assert aga._agent_graph["nodes"]["active"]["result"]["stopped_by_user"] is True
    assert state.stop_requested is True
    assert agent_instance_state.stop_requested is True
    agent_instance.cancel_current_execution.assert_called_once_with()
    tracer.update_agent_status.assert_called_once_with("active", "stopping")

    monkeypatch.setitem(sys.modules, "strix.telemetry.tracer", None)
    aga._agent_graph["nodes"]["importless"] = {"name": "I", "status": "running"}
    assert aga.stop_agent("importless")["success"] is True

    aga._agent_graph["nodes"]["broken"] = {"name": "Broken"}
    broken = aga.stop_agent("broken")
    assert broken["success"] is False
    assert broken["agent_id"] == "broken"
    assert broken["error"].startswith("Failed to stop agent:")


def test_send_user_message_to_agent_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_user_message_to_agent handles missing, success, and exception payloads."""
    missing = aga.send_user_message_to_agent("missing", "hello")
    assert missing == {
        "success": False,
        "error": "Agent 'missing' not found in graph",
        "agent_id": "missing",
    }

    class _UUID:
        hex = "abcd1234abcd"

    monkeypatch.setattr("uuid.uuid4", lambda: _UUID())
    aga._agent_graph["nodes"]["a1"] = {"name": "Agent One"}
    success = aga.send_user_message_to_agent("a1", "do this")
    assert success == {
        "success": True,
        "message": "Message sent to agent 'Agent One'",
        "agent_id": "a1",
        "agent_name": "Agent One",
    }
    assert aga._agent_messages["a1"][0]["id"].startswith("user_msg_")

    aga._agent_graph["nodes"]["bad"] = {}
    bad = aga.send_user_message_to_agent("bad", "x")
    assert bad["success"] is False
    assert bad["agent_id"] == "bad"
    assert bad["error"].startswith("Failed to send message to agent:")


def test_wait_for_message_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """wait_for_message sets waiting status and gracefully handles tracer/import errors."""
    tracer = MagicMock()
    monkeypatch.setitem(
        sys.modules,
        "strix.telemetry.tracer",
        SimpleNamespace(get_global_tracer=lambda: tracer),
    )

    state = DummyState(agent_id="a1", parent_id=None, agent_name="Agent One", task="t")
    aga._agent_graph["nodes"]["a1"] = {"name": "Agent One", "status": "running"}

    success = aga.wait_for_message(state, reason="waiting for dependency")
    assert success["success"] is True
    assert success["status"] == "waiting"
    assert success["reason"] == "waiting for dependency"
    assert state.waiting_entered is True
    assert aga._agent_graph["nodes"]["a1"]["status"] == "waiting"
    assert aga._agent_graph["nodes"]["a1"]["waiting_reason"] == "waiting for dependency"
    tracer.update_agent_status.assert_called_once_with("a1", "waiting")

    monkeypatch.setitem(sys.modules, "strix.telemetry.tracer", None)
    success_no_tracer = aga.wait_for_message(state)
    assert success_no_tracer["success"] is True

    class BrokenState(DummyState):
        def enter_waiting_state(self) -> None:
            msg = "cannot wait"
            raise RuntimeError(msg)

    error = aga.wait_for_message(
        BrokenState(agent_id="x", parent_id=None, agent_name="X", task="t")
    )
    assert error == {
        "success": False,
        "error": "Failed to enter waiting state: cannot wait",
        "status": "error",
    }


def test_view_agent_graph_fallback_to_first_node_when_no_parentless() -> None:
    """view_agent_graph falls back to first node if no parentless node exists."""
    aga._agent_graph["nodes"]["b"] = {
        "name": "B",
        "task": "tb",
        "status": "running",
        "parent_id": "x",
    }
    aga._agent_graph["nodes"]["a"] = {
        "name": "A",
        "task": "ta",
        "status": "running",
        "parent_id": "y",
    }

    result = aga.view_agent_graph(SimpleNamespace(agent_id="a"))
    assert "B (b)" in result["graph_structure"]


def test_create_agent_success_without_parent_llm_attrs_and_no_inherit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_agent keeps defaults when parent llm_config lacks optional attributes."""
    monkeypatch.setattr("strix.skills.parse_skill_list", lambda _skills: [])
    monkeypatch.setattr("strix.skills.validate_requested_skills", lambda _lst: None)

    class FakeAgentState:
        def __init__(
            self,
            task: str,
            agent_name: str,
            parent_id: str,
            max_iterations: int,
            waiting_timeout: int,
        ):
            self.task = task
            self.agent_name = agent_name
            self.parent_id = parent_id
            self.max_iterations = max_iterations
            self.waiting_timeout = waiting_timeout
            self.agent_id = "child-no-inherit"

    class FakeLLMConfig:
        def __init__(
            self, skills: list[str], timeout: int | None, scan_mode: str, interactive: bool
        ):
            self.skills = skills
            self.timeout = timeout
            self.scan_mode = scan_mode
            self.interactive = interactive

    class FakeStrixAgent:
        def __init__(self, cfg: dict[str, object]) -> None:
            self.llm_config = cfg["llm_config"]
            self.state = cfg["state"]

    created_threads: list[object] = []

    class FakeThread:
        def __init__(
            self, target: object, args: tuple[object, ...], daemon: bool, name: str
        ) -> None:
            self.target = target
            self.args = args
            self.daemon = daemon
            self.name = name
            self.started = False
            created_threads.append(self)

        def start(self) -> None:
            self.started = True

    monkeypatch.setitem(sys.modules, "strix.agents", SimpleNamespace(StrixAgent=FakeStrixAgent))
    monkeypatch.setitem(
        sys.modules, "strix.agents.state", SimpleNamespace(AgentState=FakeAgentState)
    )
    monkeypatch.setitem(sys.modules, "strix.llm.config", SimpleNamespace(LLMConfig=FakeLLMConfig))
    monkeypatch.setattr(aga.threading, "Thread", FakeThread)

    # parent exists but optional llm attrs are intentionally absent
    aga._agent_instances["parent"] = SimpleNamespace(llm_config=SimpleNamespace())
    parent_state = SimpleNamespace(
        agent_id="parent", get_conversation_history=lambda: [{"role": "user", "content": "unused"}]
    )

    result = aga.create_agent(parent_state, task="task", name="Child", inherit_context=False)
    assert result["success"] is True
    thread = created_threads[0]
    _, state, inherited = thread.args
    assert state.waiting_timeout == 600
    assert inherited == []


def test_agent_finish_report_to_missing_parent_and_existing_mailbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """agent_finish handles missing parent node and pre-existing parent mailbox branches."""

    class _UUID:
        hex = "fedcba987654"

    monkeypatch.setattr("uuid.uuid4", lambda: _UUID())

    aga._agent_graph["nodes"]["child"] = {
        "name": "Child",
        "status": "running",
        "task": "task",
        "parent_id": "missing-parent",
    }
    result_missing_parent = aga.agent_finish(
        SimpleNamespace(agent_id="child", parent_id="missing-parent"),
        result_summary="done",
        report_to_parent=True,
    )
    assert result_missing_parent["agent_completed"] is True
    assert result_missing_parent["parent_notified"] is False

    aga._agent_graph["nodes"]["parent"] = {"name": "Parent", "status": "running", "task": "p"}
    aga._agent_graph["nodes"]["child2"] = {
        "name": "Child2",
        "status": "running",
        "task": "task2",
        "parent_id": "parent",
    }
    aga._agent_messages["parent"] = []
    result_existing_mailbox = aga.agent_finish(
        SimpleNamespace(agent_id="child2", parent_id="parent"),
        result_summary="done2",
        report_to_parent=True,
    )
    assert result_existing_mailbox["agent_completed"] is True
    assert result_existing_mailbox["parent_notified"] is True
    assert len(aga._agent_messages["parent"]) == 1


def test_stop_agent_branches_for_missing_instance_attrs_and_null_tracer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stop_agent covers missing instance attrs and tracer returning None."""
    monkeypatch.setitem(
        sys.modules,
        "strix.telemetry.tracer",
        SimpleNamespace(get_global_tracer=lambda: None),
    )
    aga._agent_graph["nodes"]["active"] = {"name": "Active", "status": "running"}
    aga._agent_instances["active"] = SimpleNamespace()  # no state/cancel_current_execution

    result = aga.stop_agent("active")
    assert result["success"] is True
    assert aga._agent_graph["nodes"]["active"]["status"] == "stopping"


def test_send_user_message_existing_mailbox_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_user_message_to_agent appends into existing mailbox without re-init."""

    class _UUID:
        hex = "111122223333"

    monkeypatch.setattr("uuid.uuid4", lambda: _UUID())
    aga._agent_graph["nodes"]["a1"] = {"name": "Agent One"}
    aga._agent_messages["a1"] = [{"id": "existing"}]

    result = aga.send_user_message_to_agent("a1", "next")
    assert result["success"] is True
    assert len(aga._agent_messages["a1"]) == 2


def test_wait_for_message_without_graph_node_and_null_tracer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """wait_for_message succeeds even if node absent and tracer resolves to None."""
    monkeypatch.setitem(
        sys.modules,
        "strix.telemetry.tracer",
        SimpleNamespace(get_global_tracer=lambda: None),
    )
    state = DummyState(agent_id="ghost", parent_id=None, agent_name="Ghost", task="t")
    result = aga.wait_for_message(state)

    assert result["success"] is True
    assert result["status"] == "waiting"
    assert state.waiting_entered is True
