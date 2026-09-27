import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from strix.config import Config


@pytest.mark.parametrize(
    "case,waiting",
    [("idle", False), ("interactive", True), ("child", True), ("peer", True),
     ("unread", True), ("unknown_instance", True), ("unknown_interactive", True),
     ("unknown_mailbox", True), ("unknown_root", True), ("unknown_parent", True),
     ("different_state", True), ("invalid_argument", False)],
)
def test_registered_wait_preserves_native_feedback(monkeypatch: Any, case: str, waiting: bool) -> None:
    monkeypatch.setattr(Config, "load", classmethod(lambda cls: {"env": {}}))
    monkeypatch.setenv("STRIX_SANDBOX_MODE", "false")
    monkeypatch.setenv("STRIX_DISABLE_BROWSER", "true")
    from strix.agents.state import AgentState
    from strix.telemetry import tracer
    from strix.tools.agents_graph import agents_graph_actions as graph
    from strix.tools.executor import process_tool_invocations
    from strix.tools.registry import get_tool_names

    assert "wait_for_message" in get_tool_names()
    state = AgentState(agent_id="test-root", agent_name="Test root")
    node: dict[str, Any] = {"parent_id": None, "status": "running"}
    nodes = {state.agent_id: node}
    instance: Any = SimpleNamespace(state=state, interactive=False)
    messages: Any = []
    root: Any = state.agent_id
    if case == "interactive":
        instance.interactive = True
    if case == "child":
        state.parent_id = "test-parent"
        node["parent_id"] = state.parent_id
    if case == "peer":
        nodes["test-peer"] = {"parent_id": state.agent_id, "status": "waiting"}
    if case == "unread":
        messages = [{"read": False}]
    if case == "unknown_instance":
        instance = None
    if case == "unknown_interactive":
        instance = SimpleNamespace(state=state)
    if case == "unknown_mailbox":
        messages = None
    if case == "unknown_root":
        root = None
    if case == "unknown_parent":
        node.pop("parent_id")
    if case == "different_state":
        instance.state = SimpleNamespace()
    monkeypatch.setattr(graph, "_agent_graph", {"nodes": nodes, "edges": []})
    monkeypatch.setattr(graph, "_agent_instances", {state.agent_id: instance})
    monkeypatch.setattr(graph, "_agent_messages", {state.agent_id: messages})
    monkeypatch.setattr(graph, "_root_agent_id", root)
    statuses: list[str] = []
    spy = SimpleNamespace(
        log_tool_execution_start=lambda *args: 1,
        update_tool_execution=lambda execution, status, result: statuses.append(status),
        update_agent_status=lambda *args: None,
    )
    monkeypatch.setattr(tracer, "get_global_tracer", lambda: spy)
    history: list[dict[str, Any]] = []
    args = {"message": "not a registered parameter"} if case == "invalid_argument" else {"reason": "Waiting"}
    finished = asyncio.run(process_tool_invocations([{"toolName": "wait_for_message", "args": args}], history, state))
    assert finished is False and state.completed is False
    assert state.waiting_for_input is waiting
    assert node["status"] == ("waiting" if waiting else "running")
    assert statuses == (["completed"] if waiting else ["error"])
    assert history[0]["role"] == "user"
    assert "<tool_name>wait_for_message</tool_name>" in history[0]["content"]
    if not waiting:
        assert "error" in history[0]["content"].casefold()
