from unittest.mock import patch

from strix.tools.agents_graph import agents_graph_actions
from strix.tools.load_skill import load_skill_actions
from tests.tools.test_load_skill_tool import _DummyAgent, _DummyAgentState, _DummyLLM


def test_load_skill_empty_skills():
    state = _DummyAgentState("test_empty")
    result = load_skill_actions.load_skill(state, "")
    assert result["success"] is False
    assert "No skills provided" in result["error"]


def test_load_skill_exception():
    state = _DummyAgentState("test_exception")
    instances = agents_graph_actions.__dict__["_agent_instances"]
    instances[state.agent_id] = _DummyAgent()

    class _FailingLLM(_DummyLLM):
        def add_skills(self, skills):  # noqa: ARG002
            raise ValueError("Something went wrong")

    instances[state.agent_id].llm = _FailingLLM()

    result = load_skill_actions.load_skill(state, "ffuf")
    assert result["success"] is False
    assert "Something went wrong" in result["error"]
    assert result["requested_skills"] == ["ffuf"]


def test_load_skill_exception_before_requested_skills_assigned():
    state = _DummyAgentState("test_exception_early")

    with patch("strix.skills.parse_skill_list", side_effect=ValueError("Early failure")):
        result = load_skill_actions.load_skill(state, "a, b")
        assert result["success"] is False
        assert "Early failure" in result["error"]
        assert result["requested_skills"] == ["a", "b"]


def test_load_skill_fallback_with_prior_skills_not_list():
    state = _DummyAgentState("test_prior_not_list")
    state.context["loaded_skills"] = "not_a_list"

    instances = agents_graph_actions.__dict__["_agent_instances"]
    instances[state.agent_id] = _DummyAgent()

    result = load_skill_actions.load_skill(state, "ffuf")
    assert result["success"] is True
    assert state.context["loaded_skills"] == ["ffuf"]
