"""Tests for load_skill tool."""

from unittest.mock import MagicMock, patch

from strix.tools.load_skill.load_skill_actions import load_skill


@patch("strix.skills.parse_skill_list")
def test_load_skill_no_skills(mock_parse):
    """Test load_skill when no skills are provided."""
    mock_parse.return_value = []

    result = load_skill(MagicMock(), "")

    assert result["success"] is False
    assert "No skills provided" in result["error"]
    assert result["requested_skills"] == []


@patch("strix.skills.validate_requested_skills")
@patch("strix.skills.parse_skill_list")
def test_load_skill_validation_error(mock_parse, mock_validate):
    """Test load_skill when skill validation fails."""
    mock_parse.return_value = ["bad-skill"]
    mock_validate.return_value = "Skill 'bad-skill' not found"

    result = load_skill(MagicMock(), "bad-skill")

    assert result["success"] is False
    assert result["error"] == "Skill 'bad-skill' not found"
    assert result["requested_skills"] == ["bad-skill"]
    assert result["loaded_skills"] == []


@patch("strix.skills.validate_requested_skills")
@patch("strix.skills.parse_skill_list")
def test_load_skill_agent_not_found(mock_parse, mock_validate):
    """Test load_skill when current agent instance is not found."""
    mock_parse.return_value = ["good-skill"]
    mock_validate.return_value = None

    agent_state = MagicMock()
    agent_state.agent_id = "agent1"

    with patch.dict(
        "sys.modules",
        {
            "strix.tools.agents_graph.agents_graph_actions": MagicMock(
                _agent_instances={"agent2": MagicMock()}
            )
        },
    ):
        result = load_skill(agent_state, "good-skill")

        assert result["success"] is False
        assert "Could not find running agent instance" in result["error"]


@patch("strix.skills.validate_requested_skills")
@patch("strix.skills.parse_skill_list")
def test_load_skill_agent_no_llm(mock_parse, mock_validate):
    """Test load_skill when current agent instance has no llm attribute."""
    mock_parse.return_value = ["good-skill"]
    mock_validate.return_value = None

    agent_state = MagicMock()
    agent_state.agent_id = "agent1"

    mock_agent = MagicMock()
    del mock_agent.llm

    with patch.dict(
        "sys.modules",
        {
            "strix.tools.agents_graph.agents_graph_actions": MagicMock(
                _agent_instances={"agent1": mock_agent}
            )
        },
    ):
        result = load_skill(agent_state, "good-skill")

        assert result["success"] is False
        assert "Could not find running agent instance" in result["error"]


@patch("strix.skills.validate_requested_skills")
@patch("strix.skills.parse_skill_list")
def test_load_skill_success(mock_parse, mock_validate):
    """Test load_skill on successful load."""
    mock_parse.return_value = ["skill1", "skill2"]
    mock_validate.return_value = None

    agent_state = MagicMock()
    agent_state.agent_id = "agent1"
    agent_state.context = {"loaded_skills": ["skill1"]}

    mock_llm = MagicMock()
    # Mock newly loaded vs already loaded
    mock_llm.add_skills.return_value = ["skill2"]

    mock_agent = MagicMock()
    mock_agent.llm = mock_llm

    with patch.dict(
        "sys.modules",
        {
            "strix.tools.agents_graph.agents_graph_actions": MagicMock(
                _agent_instances={"agent1": mock_agent}
            )
        },
    ):
        result = load_skill(agent_state, "skill1, skill2")

        assert result["success"] is True
        assert result["requested_skills"] == ["skill1", "skill2"]
        assert result["loaded_skills"] == ["skill1", "skill2"]
        assert result["newly_loaded_skills"] == ["skill2"]
        assert result["already_loaded_skills"] == ["skill1"]

        agent_state.update_context.assert_called_once_with("loaded_skills", ["skill1", "skill2"])


@patch("strix.skills.validate_requested_skills")
@patch("strix.skills.parse_skill_list")
def test_load_skill_success_bad_context(mock_parse, mock_validate):
    """Test load_skill success when context['loaded_skills'] is not a list."""
    mock_parse.return_value = ["skill1"]
    mock_validate.return_value = None

    agent_state = MagicMock()
    agent_state.agent_id = "agent1"
    # Bad context value
    agent_state.context = {"loaded_skills": "not_a_list"}

    mock_llm = MagicMock()
    mock_llm.add_skills.return_value = ["skill1"]

    mock_agent = MagicMock()
    mock_agent.llm = mock_llm

    with patch.dict(
        "sys.modules",
        {
            "strix.tools.agents_graph.agents_graph_actions": MagicMock(
                _agent_instances={"agent1": mock_agent}
            )
        },
    ):
        result = load_skill(agent_state, "skill1")

        assert result["success"] is True
        agent_state.update_context.assert_called_once_with("loaded_skills", ["skill1"])


@patch("strix.skills.parse_skill_list")
def test_load_skill_exception_before_requested_skills_defined(mock_parse):
    """Test load_skill exception when 'requested_skills' isn't defined yet."""
    # Raise exception in parse_skill_list
    mock_parse.side_effect = Exception("parse error")

    result = load_skill(MagicMock(), "skill1, skill2")

    assert result["success"] is False
    assert "Failed to load skill(s)" in result["error"]
    assert result["requested_skills"] == ["skill1", "skill2"]
    assert result["loaded_skills"] == []


@patch("strix.skills.validate_requested_skills")
@patch("strix.skills.parse_skill_list")
def test_load_skill_exception_after_requested_skills_defined(mock_parse, mock_validate):
    """Test load_skill exception when 'requested_skills' is already defined."""
    mock_parse.return_value = ["skill1"]
    # Raise exception in validate
    mock_validate.side_effect = Exception("validate error")

    result = load_skill(MagicMock(), "skill1")

    assert result["success"] is False
    assert "Failed to load skill(s)" in result["error"]
    assert result["requested_skills"] == ["skill1"]
    assert result["loaded_skills"] == []
