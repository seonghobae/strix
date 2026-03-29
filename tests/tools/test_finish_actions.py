"""Tests for finish_actions.py."""

from unittest.mock import MagicMock, patch

from strix.tools.finish.finish_actions import (
    _check_active_agents,
    _validate_root_agent,
    finish_scan,
)


class MockAgentState:
    """Mock agent state for testing."""

    def __init__(self, parent_id=None, agent_id=None):
        self.parent_id = parent_id
        self.agent_id = agent_id


def test_validate_root_agent_with_no_parent():
    """Test _validate_root_agent when the agent is the root agent."""
    state = MockAgentState(parent_id=None)
    result = _validate_root_agent(state)
    assert result is None


def test_validate_root_agent_with_parent():
    """Test _validate_root_agent when the agent is a subagent."""
    state = MockAgentState(parent_id="parent_1")
    result = _validate_root_agent(state)
    assert result is not None
    assert result["success"] is False
    assert result["error"] == "finish_scan_wrong_agent"


def test_validate_root_agent_without_parent_attr():
    """Test _validate_root_agent when agent state lacks parent_id."""
    state = MagicMock(spec=[])
    result = _validate_root_agent(state)
    assert result is None


def test_check_active_agents_no_agent_id():
    """Test _check_active_agents when agent state lacks agent_id."""
    state = MockAgentState(agent_id=None)
    result = _check_active_agents(state)
    assert result is None


@patch("strix.tools.finish.finish_actions._agent_graph", {"nodes": {}}, create=True)
def test_check_active_agents_empty_graph():
    """Test _check_active_agents with an empty agent graph."""
    state = MockAgentState(agent_id="current_agent")
    mock_module = MagicMock(_agent_graph={"nodes": {}})
    with patch.dict("sys.modules", {"strix.tools.agents_graph.agents_graph_actions": mock_module}):
        result = _check_active_agents(state)
        assert result is None


def test_check_active_agents_with_active_agents():
    """Test _check_active_agents when there are running or stopping agents."""
    state = MockAgentState(agent_id="agent1")
    mock_graph = {
        "nodes": {
            "agent1": {"status": "running"},
            "agent2": {"status": "running", "name": "Agent 2", "task": "Task 2"},
            "agent3": {"status": "stopping", "name": "Agent 3", "task": "Task 3"},
        }
    }

    mock_module = MagicMock()
    mock_module._agent_graph = mock_graph

    with patch.dict("sys.modules", {"strix.tools.agents_graph.agents_graph_actions": mock_module}):
        result = _check_active_agents(state)
        assert result is not None
        assert result["success"] is False
        assert result["error"] == "agents_still_active"
        assert len(result["active_agents"]) == 1
        assert len(result["stopping_agents"]) == 1
        assert result["total_active"] == 2


def test_check_active_agents_import_error():
    """Test _check_active_agents when strix.tools.agents_graph cannot be imported."""
    state = MockAgentState(agent_id="agent1")
    with patch.dict("sys.modules", {"strix.tools.agents_graph.agents_graph_actions": None}):
        result = _check_active_agents(state)
        assert result is None


def test_check_active_agents_exception(caplog):
    """Test _check_active_agents when an unexpected exception occurs."""
    state = MockAgentState(agent_id="agent1")

    mock_module = MagicMock()
    # Trigger an exception when accessing _agent_graph
    type(mock_module)._agent_graph = property(
        lambda _self: (_ for _ in ()).throw(Exception("Mock Exception"))
    )

    with patch.dict("sys.modules", {"strix.tools.agents_graph.agents_graph_actions": mock_module}):
        result = _check_active_agents(state)
        assert result is None
        assert "Error checking active agents" in caplog.text


def test_finish_scan_validation_failures():
    """Test finish_scan missing required fields."""
    result = finish_scan("", "method", "analysis", "recommend")
    assert result["success"] is False
    assert "Executive summary cannot be empty" in result["errors"]

    result = finish_scan("summary", "", "analysis", "recommend")
    assert result["success"] is False
    assert "Methodology cannot be empty" in result["errors"]

    result = finish_scan("summary", "method", "", "recommend")
    assert result["success"] is False
    assert "Technical analysis cannot be empty" in result["errors"]

    result = finish_scan("summary", "method", "analysis", "")
    assert result["success"] is False
    assert "Recommendations cannot be empty" in result["errors"]


def test_finish_scan_with_validation_error():
    """Test finish_scan when _validate_root_agent fails."""
    state = MockAgentState(parent_id="parent")
    result = finish_scan("summary", "method", "analysis", "recommend", agent_state=state)
    assert result["success"] is False
    assert result["error"] == "finish_scan_wrong_agent"


@patch("strix.tools.finish.finish_actions._check_active_agents")
def test_finish_scan_with_active_agents_error(mock_check_active):
    """Test finish_scan when _check_active_agents fails."""
    mock_check_active.return_value = {"success": False, "error": "agents_still_active"}
    result = finish_scan("summary", "method", "analysis", "recommend", agent_state=MockAgentState())
    assert result["success"] is False
    assert result["error"] == "agents_still_active"


@patch("strix.tools.finish.finish_actions._check_active_agents", return_value=None)
@patch("strix.tools.finish.finish_actions._validate_root_agent", return_value=None)
def test_finish_scan_success(mock_validate, mock_check, monkeypatch):
    """Test successful finish_scan."""
    mock_tracer = MagicMock()
    mock_tracer.vulnerability_reports = ["vuln1"]

    mock_get_tracer = MagicMock(return_value=mock_tracer)
    mock_telemetry_tracer = MagicMock(get_global_tracer=mock_get_tracer)

    with patch.dict("sys.modules", {"strix.telemetry.tracer": mock_telemetry_tracer}):
        result = finish_scan(" summary ", " method ", " analysis ", " recommend ", agent_state=None)
        assert result["success"] is True
        assert result["scan_completed"] is True
        assert result["vulnerabilities_found"] == 1

        mock_tracer.update_scan_final_fields.assert_called_once_with(
            executive_summary="summary",
            methodology="method",
            technical_analysis="analysis",
            recommendations="recommend",
        )


@patch("strix.tools.finish.finish_actions._check_active_agents", return_value=None)
@patch("strix.tools.finish.finish_actions._validate_root_agent", return_value=None)
def test_finish_scan_no_tracer(mock_validate, mock_check, caplog):
    """Test finish_scan when tracer is None."""
    mock_get_tracer = MagicMock(return_value=None)
    mock_telemetry_tracer = MagicMock(get_global_tracer=mock_get_tracer)

    with patch.dict("sys.modules", {"strix.telemetry.tracer": mock_telemetry_tracer}):
        result = finish_scan("summary", "method", "analysis", "recommend", agent_state=None)
        assert result["success"] is True
        assert result["message"] == "Scan completed (not persisted)"
        assert "Current tracer not available" in caplog.text


@patch("strix.tools.finish.finish_actions._check_active_agents", return_value=None)
@patch("strix.tools.finish.finish_actions._validate_root_agent", return_value=None)
def test_finish_scan_import_error(mock_validate, mock_check):
    """Test finish_scan when importing tracer fails."""
    with patch.dict("sys.modules", {"strix.telemetry.tracer": None}):
        result = finish_scan("summary", "method", "analysis", "recommend", agent_state=None)
        assert result["success"] is False
        assert "Failed to complete scan" in result["message"]


@patch("strix.tools.finish.finish_actions._check_active_agents", return_value=None)
@patch("strix.tools.finish.finish_actions._validate_root_agent", return_value=None)
def test_finish_scan_attribute_error(mock_validate, mock_check):
    """Test finish_scan when tracer module misses get_global_tracer."""
    with patch.dict("sys.modules", {"strix.telemetry.tracer": MagicMock(spec=[])}):
        result = finish_scan("summary", "method", "analysis", "recommend", agent_state=None)
        assert result["success"] is False
        assert "Failed to complete scan" in result["message"]
