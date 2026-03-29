"""Tests for finish actions."""

from unittest.mock import MagicMock, patch

from strix.tools.finish.finish_actions import (
    _check_active_agents,
    _validate_root_agent,
    finish_scan,
)


def test_validate_root_agent_not_root():
    """Test validation when agent has a parent_id."""
    agent_state = MagicMock()
    agent_state.parent_id = "some_parent"
    result = _validate_root_agent(agent_state)
    assert result is not None
    assert result["success"] is False
    assert result["error"] == "finish_scan_wrong_agent"


def test_validate_root_agent_is_root():
    """Test validation when agent has no parent_id."""
    agent_state = MagicMock()
    agent_state.parent_id = None
    result = _validate_root_agent(agent_state)
    assert result is None


def test_validate_root_agent_none():
    """Test validation when agent is None."""
    result = _validate_root_agent(None)
    assert result is None


def test_check_active_agents_no_state():
    """Test checking active agents with no agent state."""
    result = _check_active_agents(None)
    assert result is None


@patch("strix.tools.finish.finish_actions._agent_graph", {"nodes": {}}, create=True)
def test_check_active_agents_no_active():
    """Test checking active agents when none are active."""
    agent_state = MagicMock()
    agent_state.agent_id = "agent1"
    result = _check_active_agents(agent_state)
    assert result is None


@patch(
    "strix.tools.finish.finish_actions._agent_graph",
    {
        "nodes": {
            "agent1": {"status": "running"},  # self
            "agent2": {"name": "A2", "task": "task2", "status": "running"},
            "agent3": {"name": "A3", "task": "task3", "status": "stopping"},
            "agent4": {"status": "done"},
        }
    },
    create=True,
)
def test_check_active_agents_with_active():
    """Test checking active agents when some are active."""
    agent_state = MagicMock()
    agent_state.agent_id = "agent1"

    # We need to mock the import of strix.tools.agents_graph.agents_graph_actions
    mock_agent_graph = MagicMock(
        _agent_graph={
            "nodes": {
                "agent1": {"status": "running"},
                "agent2": {"name": "A2", "task": "task2", "status": "running"},
                "agent3": {"name": "A3", "task": "task3", "status": "stopping"},
                "agent4": {"status": "done"},
            }
        }
    )
    with patch.dict(
        "sys.modules", {"strix.tools.agents_graph.agents_graph_actions": mock_agent_graph}
    ):
        result = _check_active_agents(agent_state)
        assert result is not None
        assert result["success"] is False
        assert result["error"] == "agents_still_active"
        assert len(result["active_agents"]) == 1
        assert len(result["stopping_agents"]) == 1
        assert result["total_active"] == 2


def test_check_active_agents_import_error():
    """Test checking active agents when import fails."""
    agent_state = MagicMock()
    agent_state.agent_id = "agent1"

    # We can simulate import error by patching sys.modules with None or raising
    # wait, the simplest is not mocking and letting it fail if the import actually fails,
    # but the import won't fail since the module exists.
    # Let's mock builtins.__import__
    with patch("builtins.__import__", side_effect=ImportError):
        result = _check_active_agents(agent_state)
        assert result is None


def test_check_active_agents_exception():
    """Test checking active agents when an exception occurs."""
    agent_state = MagicMock()
    # If agent_id access raises exception
    type(agent_state).agent_id = property(lambda _self: (_ for _ in ()).throw(ValueError))

    result = _check_active_agents(agent_state)
    assert result is None


@patch("strix.tools.finish.finish_actions._validate_root_agent")
@patch("strix.tools.finish.finish_actions._check_active_agents")
def test_finish_scan_validation_errors(mock_check, mock_validate):
    """Test finish_scan with validation errors."""
    mock_validate.return_value = None
    mock_check.return_value = None

    result = finish_scan("", " ", "   ", "\n")
    assert result["success"] is False
    assert len(result["errors"]) == 4


@patch("strix.tools.finish.finish_actions._validate_root_agent")
@patch("strix.tools.finish.finish_actions._check_active_agents")
def test_finish_scan_root_agent_error(mock_check, mock_validate):
    """Test finish_scan when root agent validation fails."""
    mock_validate.return_value = {"error": "wrong"}
    result = finish_scan("a", "b", "c", "d")
    assert result == {"error": "wrong"}


@patch("strix.tools.finish.finish_actions._validate_root_agent")
@patch("strix.tools.finish.finish_actions._check_active_agents")
def test_finish_scan_active_agents_error(mock_check, mock_validate):
    """Test finish_scan when active agents validation fails."""
    mock_validate.return_value = None
    mock_check.return_value = {"error": "active"}
    result = finish_scan("a", "b", "c", "d")
    assert result == {"error": "active"}


@patch("strix.tools.finish.finish_actions._validate_root_agent")
@patch("strix.tools.finish.finish_actions._check_active_agents")
@patch("strix.tools.finish.finish_actions.get_global_tracer", create=True)
def test_finish_scan_success(mock_get_tracer, mock_check, mock_validate):
    """Test successful finish_scan."""
    mock_validate.return_value = None
    mock_check.return_value = None

    mock_tracer = MagicMock()
    mock_tracer.vulnerability_reports = [1, 2, 3]
    mock_get_tracer.return_value = mock_tracer

    with patch.dict(
        "sys.modules", {"strix.telemetry.tracer": MagicMock(get_global_tracer=mock_get_tracer)}
    ):
        result = finish_scan("exec", "meth", "tech", "rec")

        assert result["success"] is True
        assert result["vulnerabilities_found"] == 3
        mock_tracer.update_scan_final_fields.assert_called_once_with(
            executive_summary="exec",
            methodology="meth",
            technical_analysis="tech",
            recommendations="rec",
        )


@patch("strix.tools.finish.finish_actions._validate_root_agent")
@patch("strix.tools.finish.finish_actions._check_active_agents")
def test_finish_scan_no_tracer(mock_check, mock_validate):
    """Test successful finish_scan when tracer is None."""
    mock_validate.return_value = None
    mock_check.return_value = None

    with patch.dict(
        "sys.modules", {"strix.telemetry.tracer": MagicMock(get_global_tracer=lambda: None)}
    ):
        result = finish_scan("exec", "meth", "tech", "rec")

        assert result["success"] is True
        assert result["warning"] == "Results could not be persisted - tracer unavailable"


@patch("strix.tools.finish.finish_actions._validate_root_agent")
@patch("strix.tools.finish.finish_actions._check_active_agents")
def test_finish_scan_import_error(mock_check, mock_validate):
    """Test successful finish_scan when import fails."""
    mock_validate.return_value = None
    mock_check.return_value = None

    with patch("builtins.__import__", side_effect=ImportError("mocked import error")):
        result = finish_scan("exec", "meth", "tech", "rec")
        assert result["success"] is False
        assert "mocked import error" in result["message"]
