"""Tests for the load_skill tool."""

from typing import Any

from strix.tools.agents_graph import agents_graph_actions
from strix.tools.load_skill import load_skill_actions


class _DummyLLM:
    """A dummy LLM for testing skill loading."""

    def __init__(self, initial_skills: list[str] | None = None) -> None:
        """Initialize the dummy LLM with optional initial skills."""
        self.loaded: set[str] = set(initial_skills or [])

    def add_skills(self, skill_names: list[str]) -> list[str]:
        """Simulate adding skills to the LLM."""
        newly_loaded = [skill for skill in skill_names if skill not in self.loaded]
        self.loaded.update(newly_loaded)
        return newly_loaded


class _DummyAgent:
    """A dummy agent for testing skill loading."""

    def __init__(self, initial_skills: list[str] | None = None) -> None:
        """Initialize the dummy agent with optional initial skills."""
        self.llm = _DummyLLM(initial_skills)


class _DummyAgentState:
    """A dummy agent state for testing skill loading."""

    def __init__(self, agent_id: str) -> None:
        """Initialize the dummy agent state."""
        self.agent_id = agent_id
        self.context: dict[str, Any] = {}

    def update_context(self, key: str, value: Any) -> None:
        """Simulate updating the context of the agent state."""
        self.context[key] = value


def test_load_skill_success_and_context_update() -> None:
    """Test successful loading of skills and updating agent context."""
    instances = agents_graph_actions.__dict__["_agent_instances"]
    original_instances = dict(instances)
    try:
        state = _DummyAgentState("agent_test_load_skill_success")
        instances.clear()
        instances[state.agent_id] = _DummyAgent()

        result = load_skill_actions.load_skill(state, "ffuf,xss")

        assert result["success"] is True
        assert result["loaded_skills"] == ["ffuf", "xss"]
        assert result["newly_loaded_skills"] == ["ffuf", "xss"]
        assert state.context["loaded_skills"] == ["ffuf", "xss"]
    finally:
        instances.clear()
        instances.update(original_instances)


def test_load_skill_uses_same_plain_skill_format_as_create_agent() -> None:
    """Test loading a skill using plain skill format."""
    instances = agents_graph_actions.__dict__["_agent_instances"]
    original_instances = dict(instances)
    try:
        state = _DummyAgentState("agent_test_load_skill_short_name")
        instances.clear()
        instances[state.agent_id] = _DummyAgent()

        result = load_skill_actions.load_skill(state, "nmap")

        assert result["success"] is True
        assert result["loaded_skills"] == ["nmap"]
        assert result["newly_loaded_skills"] == ["nmap"]
        assert state.context["loaded_skills"] == ["nmap"]
    finally:
        instances.clear()
        instances.update(original_instances)


def test_load_skill_invalid_skill_returns_error() -> None:
    """Test loading an invalid skill returns an error."""
    instances = agents_graph_actions.__dict__["_agent_instances"]
    original_instances = dict(instances)
    try:
        state = _DummyAgentState("agent_test_load_skill_invalid")
        instances.clear()
        instances[state.agent_id] = _DummyAgent()

        result = load_skill_actions.load_skill(state, "definitely_not_a_real_skill")

        assert result["success"] is False
        assert "Invalid skills" in result["error"]
        assert "Available skills" in result["error"]
    finally:
        instances.clear()
        instances.update(original_instances)


def test_load_skill_rejects_more_than_five_skills() -> None:
    """Test loading more than five skills returns an error."""
    instances = agents_graph_actions.__dict__["_agent_instances"]
    original_instances = dict(instances)
    try:
        state = _DummyAgentState("agent_test_load_skill_too_many")
        instances.clear()
        instances[state.agent_id] = _DummyAgent()

        result = load_skill_actions.load_skill(state, "a,b,c,d,e,f")

        assert result["success"] is False
        assert result["error"] == (
            "Cannot specify more than 5 skills for an agent (use comma-separated format)"
        )
    finally:
        instances.clear()
        instances.update(original_instances)


def test_load_skill_missing_agent_instance_returns_error() -> None:
    """Test loading a skill without a running agent instance returns an error."""
    instances = agents_graph_actions.__dict__["_agent_instances"]
    original_instances = dict(instances)
    try:
        state = _DummyAgentState("agent_test_load_skill_missing_instance")
        instances.clear()

        result = load_skill_actions.load_skill(state, "httpx")

        assert result["success"] is False
        assert "running agent instance" in result["error"]
    finally:
        instances.clear()
        instances.update(original_instances)


def test_load_skill_does_not_reload_skill_already_present_from_agent_creation() -> None:
    """Test loading a skill that is already loaded does not reload it."""
    instances = agents_graph_actions.__dict__["_agent_instances"]
    original_instances = dict(instances)
    try:
        state = _DummyAgentState("agent_test_load_skill_existing_config_skill")
        instances.clear()
        instances[state.agent_id] = _DummyAgent(["xss"])

        result = load_skill_actions.load_skill(state, "xss,sql_injection")

        assert result["success"] is True
        assert result["loaded_skills"] == ["xss", "sql_injection"]
        assert result["newly_loaded_skills"] == ["sql_injection"]
        assert result["already_loaded_skills"] == ["xss"]
        assert state.context["loaded_skills"] == ["sql_injection", "xss"]
    finally:
        instances.clear()
        instances.update(original_instances)


def test_load_skill_no_skills_returns_error() -> None:
    """Test loading an empty skill list returns an error."""
    state = _DummyAgentState("agent_test_load_skill_no_skills")
    result = load_skill_actions.load_skill(state, "   ,  ")
    assert result["success"] is False
    assert result["error"] == "No skills provided. Pass one or more comma-separated skill names."
    assert result["requested_skills"] == []


def test_load_skill_with_invalid_prior_context() -> None:
    """Test that context is reset if loaded_skills is not a list."""
    instances = agents_graph_actions.__dict__["_agent_instances"]
    original_instances = dict(instances)
    try:
        state = _DummyAgentState("agent_test_load_skill_invalid_prior")
        state.context["loaded_skills"] = "not_a_list"  # Should be reset to []
        instances.clear()
        instances[state.agent_id] = _DummyAgent()

        result = load_skill_actions.load_skill(state, "ffuf")

        assert result["success"] is True
        assert state.context["loaded_skills"] == ["ffuf"]
    finally:
        instances.clear()
        instances.update(original_instances)


def test_load_skill_exception_handling(mocker: Any) -> None:
    """Test generic exception handling during skill loading."""
    instances = agents_graph_actions.__dict__["_agent_instances"]
    original_instances = dict(instances)
    try:
        state = _DummyAgentState("agent_test_load_skill_exception")
        instances.clear()

        # Make the LLM's add_skills raise an exception
        agent = _DummyAgent()
        mocker.patch.object(agent.llm, "add_skills", side_effect=ValueError("Test error"))
        instances[state.agent_id] = agent

        result = load_skill_actions.load_skill(state, "ffuf")

        assert result["success"] is False
        assert "Failed to load skill(s): Test error" in result["error"]
        assert result["requested_skills"] == ["ffuf"]
        assert result["loaded_skills"] == []
    finally:
        instances.clear()
        instances.update(original_instances)


def test_load_skill_exception_handling_before_requested_skills_defined(mocker: Any) -> None:
    """Test exception handling when error occurs before requested_skills is defined."""
    state = _DummyAgentState("agent_test_load_skill_exception_early")

    # Patch parse_skill_list to raise an error so requested_skills is not bound
    mocker.patch("strix.skills.parse_skill_list", side_effect=RuntimeError("Parsing failed"))

    result = load_skill_actions.load_skill(state, "ffuf, xss ")

    assert result["success"] is False
    assert "Failed to load skill(s): Parsing failed" in result["error"]
    assert result["requested_skills"] == ["ffuf", "xss"]
    assert result["loaded_skills"] == []
