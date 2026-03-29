"""Tests for executor."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from strix.tools.executor import (
    _check_error_result,
    _execute_single_tool,
    _execute_tool_in_sandbox,
    _execute_tool_locally,
    _format_tool_result,
    _get_tracer_and_agent_id,
    _update_tracer_with_result,
    _validate_tool_arguments,
    execute_tool,
    execute_tool_invocation,
    execute_tool_with_validation,
    extract_screenshot_from_result,
    process_tool_invocations,
    remove_screenshot_from_result,
    validate_tool_availability,
)


@pytest.fixture
def mock_agent_state():
    """Test function/class."""
    state = MagicMock()
    state.sandbox_id = "test-sandbox-id"
    state.sandbox_token = "test-token"  # noqa: S105
    state.sandbox_info = {"tool_server_port": 8080}
    state.agent_id = "test-agent-id"
    return state


@pytest.mark.asyncio
async def test_execute_tool_local(monkeypatch):
    """Test function/class."""
    with (
        patch("strix.tools.executor.should_execute_in_sandbox", return_value=False),
        patch("strix.tools.executor._execute_tool_locally", new_callable=AsyncMock) as mock_local,
    ):
        mock_local.return_value = "local_result"
        result = await execute_tool("my_tool", kwargs={"a": 1})
        assert result == "local_result"
        mock_local.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_tool_sandbox(monkeypatch, mock_agent_state):
    """Test function/class."""
    monkeypatch.setenv("STRIX_SANDBOX_MODE", "false")
    with (
        patch("strix.tools.executor.should_execute_in_sandbox", return_value=True),
        patch(
            "strix.tools.executor._execute_tool_in_sandbox", new_callable=AsyncMock
        ) as mock_sandbox,
    ):
        mock_sandbox.return_value = "sandbox_result"
        result = await execute_tool("my_tool", agent_state=mock_agent_state, kwargs={"a": 1})
        assert result == "sandbox_result"
        mock_sandbox.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_tool_sandbox_mode_override(monkeypatch):
    """Test function/class."""
    monkeypatch.setenv("STRIX_SANDBOX_MODE", "true")
    with (
        patch("strix.tools.executor.should_execute_in_sandbox", return_value=True),
        patch("strix.tools.executor._execute_tool_locally", new_callable=AsyncMock) as mock_local,
    ):
        mock_local.return_value = "local_result_override"
        result = await execute_tool("my_tool", kwargs={"a": 1})
        assert result == "local_result_override"
        mock_local.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_tool_in_sandbox_missing_id():
    """Test function/class."""
    state = MagicMock()
    state.sandbox_id = None
    with pytest.raises(ValueError, match="valid sandbox_id is required"):
        await _execute_tool_in_sandbox("my_tool", state)


@pytest.mark.asyncio
async def test_execute_tool_in_sandbox_missing_token():
    """Test function/class."""
    state = MagicMock()
    state.sandbox_id = "test"
    state.sandbox_token = None
    with pytest.raises(ValueError, match="valid sandbox_token is required"):
        await _execute_tool_in_sandbox("my_tool", state)


@pytest.mark.asyncio
async def test_execute_tool_in_sandbox_missing_info():
    """Test function/class."""
    state = MagicMock()
    state.sandbox_id = "test"
    state.sandbox_token = "token"  # noqa: S105
    state.sandbox_info = {}
    with pytest.raises(ValueError, match="valid sandbox_info containing tool_server_port"):
        await _execute_tool_in_sandbox("my_tool", state)


@pytest.mark.asyncio
async def test_execute_tool_in_sandbox_success(mock_agent_state):
    """Test function/class."""
    mock_runtime = MagicMock()
    mock_runtime.get_sandbox_url = AsyncMock(return_value="http://localhost:8080")

    with (
        patch("strix.tools.executor.get_runtime", return_value=mock_runtime),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_post.return_value = mock_response

        result = await _execute_tool_in_sandbox("my_tool", mock_agent_state, a=1)
        assert result == "success"
        mock_post.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_tool_in_sandbox_server_error(mock_agent_state):
    """Test function/class."""
    mock_runtime = MagicMock()
    mock_runtime.get_sandbox_url = AsyncMock(return_value="http://localhost:8080")

    with (
        patch("strix.tools.executor.get_runtime", return_value=mock_runtime),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "some_error"}
        mock_post.return_value = mock_response

        with pytest.raises(RuntimeError, match="Sandbox execution error: some_error"):
            await _execute_tool_in_sandbox("my_tool", mock_agent_state, a=1)


@pytest.mark.asyncio
async def test_execute_tool_in_sandbox_http_error(mock_agent_state):
    """Test function/class."""
    mock_runtime = MagicMock()
    mock_runtime.get_sandbox_url = AsyncMock(return_value="http://localhost:8080")

    with (
        patch("strix.tools.executor.get_runtime", return_value=mock_runtime),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_post.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )

        with pytest.raises(
            RuntimeError, match="Authentication failed: Invalid or missing sandbox token"
        ):
            await _execute_tool_in_sandbox("my_tool", mock_agent_state, a=1)


@pytest.mark.asyncio
async def test_execute_tool_in_sandbox_http_error_other(mock_agent_state):
    """Test function/class."""
    mock_runtime = MagicMock()
    mock_runtime.get_sandbox_url = AsyncMock(return_value="http://localhost:8080")

    with (
        patch("strix.tools.executor.get_runtime", return_value=mock_runtime),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_post.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_response
        )

        with pytest.raises(RuntimeError, match="HTTP error calling tool server: 500"):
            await _execute_tool_in_sandbox("my_tool", mock_agent_state, a=1)


@pytest.mark.asyncio
async def test_execute_tool_in_sandbox_request_error(mock_agent_state):
    """Test function/class."""
    mock_runtime = MagicMock()
    mock_runtime.get_sandbox_url = AsyncMock(return_value="http://localhost:8080")

    with (
        patch("strix.tools.executor.get_runtime", return_value=mock_runtime),
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
    ):
        mock_post.side_effect = httpx.RequestError("timeout")

        with pytest.raises(RuntimeError, match="Request error calling tool server: RequestError"):
            await _execute_tool_in_sandbox("my_tool", mock_agent_state, a=1)


@pytest.mark.asyncio
async def test_execute_tool_locally_not_found():
    """Test function/class."""
    with (
        patch("strix.tools.executor.get_tool_by_name", return_value=None),
        pytest.raises(ValueError, match="Tool 'my_tool' not found"),
    ):
        await _execute_tool_locally("my_tool", None)


@pytest.mark.asyncio
async def test_execute_tool_locally_sync():
    """Test function/class."""
    mock_tool = MagicMock(return_value="sync_res")
    with (
        patch("strix.tools.executor.get_tool_by_name", return_value=mock_tool),
        patch("strix.tools.executor.convert_arguments", return_value={"a": 1}),
        patch("strix.tools.executor.needs_agent_state", return_value=False),
    ):
        result = await _execute_tool_locally("my_tool", None, a=1)
        assert result == "sync_res"
        mock_tool.assert_called_once_with(a=1)


@pytest.mark.asyncio
async def test_execute_tool_locally_async():
    """Test function/class."""
    mock_tool = AsyncMock(return_value="async_res")
    with (
        patch("strix.tools.executor.get_tool_by_name", return_value=mock_tool),
        patch("strix.tools.executor.convert_arguments", return_value={"a": 1}),
        patch("strix.tools.executor.needs_agent_state", return_value=False),
    ):
        result = await _execute_tool_locally("my_tool", None, a=1)
        assert result == "async_res"
        mock_tool.assert_awaited_once_with(a=1)


@pytest.mark.asyncio
async def test_execute_tool_locally_needs_agent_state():
    """Test function/class."""
    mock_tool = MagicMock(return_value="res")
    with (
        patch("strix.tools.executor.get_tool_by_name", return_value=mock_tool),
        patch("strix.tools.executor.convert_arguments", return_value={"a": 1}),
        patch("strix.tools.executor.needs_agent_state", return_value=True),
    ):
        with pytest.raises(ValueError, match="requires agent_state"):
            await _execute_tool_locally("my_tool", None, a=1)

        state = MagicMock()
        result = await _execute_tool_locally("my_tool", state, a=1)
        assert result == "res"
        mock_tool.assert_called_once_with(agent_state=state, a=1)


def test_validate_tool_availability():
    """Test function/class."""
    with patch("strix.tools.executor.get_tool_names", return_value=["tool1", "tool2"]):
        is_valid, msg = validate_tool_availability(None)
        assert not is_valid
        assert "missing" in msg

        is_valid, msg = validate_tool_availability("tool3")
        assert not is_valid
        assert "not available" in msg

        is_valid, msg = validate_tool_availability("tool1")
        assert is_valid
        assert msg == ""


def test_validate_tool_arguments():
    """Test function/class."""
    with patch("strix.tools.executor.get_tool_param_schema", return_value=None):
        assert _validate_tool_arguments("tool1", {}) is None

    schema = {"has_params": True, "params": {"a", "b"}, "required": {"a"}}
    with patch("strix.tools.executor.get_tool_param_schema", return_value=schema):
        assert "unknown parameter" in _validate_tool_arguments("tool1", {"a": 1, "c": 2})
        assert "missing required parameter" in _validate_tool_arguments("tool1", {"b": 2})
        assert _validate_tool_arguments("tool1", {"a": 1}) is None


@pytest.mark.asyncio
async def test_execute_tool_with_validation():
    """Test function/class."""
    with patch("strix.tools.executor.validate_tool_availability", return_value=(False, "error1")):
        assert await execute_tool_with_validation("tool1") == "Error: error1"

    with (
        patch("strix.tools.executor.validate_tool_availability", return_value=(True, "")),
        patch("strix.tools.executor._validate_tool_arguments", return_value="error2"),
    ):
        assert await execute_tool_with_validation("tool1") == "Error: error2"

    with (
        patch("strix.tools.executor.validate_tool_availability", return_value=(True, "")),
        patch("strix.tools.executor._validate_tool_arguments", return_value=None),
        patch("strix.tools.executor.execute_tool", new_callable=AsyncMock) as mock_exec,
    ):
        mock_exec.return_value = "success"
        assert await execute_tool_with_validation("tool1") == "success"

        mock_exec.side_effect = Exception("test error" + "x" * 600)
        err = await execute_tool_with_validation("tool1")
        assert "Error executing tool1:" in err
        assert "truncated" in err


@pytest.mark.asyncio
async def test_execute_tool_invocation():
    """Test function/class."""
    with patch(
        "strix.tools.executor.execute_tool_with_validation", new_callable=AsyncMock
    ) as mock_val:
        mock_val.return_value = "ok"
        res = await execute_tool_invocation({"toolName": "tool1", "args": {"a": 1}}, None)
        assert res == "ok"
        mock_val.assert_awaited_once_with("tool1", None, a=1)


def test_check_error_result():
    """Test function/class."""
    assert _check_error_result({"error": "test"}) == (True, {"error": "test"})
    assert _check_error_result("Error: test") == (True, "Error: test")
    assert _check_error_result("ERROR: test") == (True, "ERROR: test")
    assert _check_error_result("success") == (False, None)
    assert _check_error_result({"result": "test"}) == (False, None)


def test_update_tracer_with_result():
    """Test function/class."""
    tracer = MagicMock()
    _update_tracer_with_result(tracer, "id1", is_error=True, result=None, error_payload="err")
    tracer.update_tool_execution.assert_called_with("id1", "error", "err")

    tracer.reset_mock()
    _update_tracer_with_result(tracer, "id1", is_error=False, result="res", error_payload=None)
    tracer.update_tool_execution.assert_called_with("id1", "completed", "res")

    tracer.update_tool_execution.side_effect = ConnectionError("conn_err")
    with pytest.raises(ConnectionError):
        _update_tracer_with_result(tracer, "id1", is_error=False, result="res", error_payload=None)

    # no tracer or execution_id
    _update_tracer_with_result(None, "id1", is_error=False, result="res", error_payload=None)
    _update_tracer_with_result(tracer, None, is_error=False, result="res", error_payload=None)


def test_format_tool_result():
    """Test function/class."""
    xml, imgs = _format_tool_result("tool1", None)
    assert "Tool tool1 executed successfully" in xml
    assert not imgs

    xml, imgs = _format_tool_result("tool1", {"screenshot": "b64data", "result": "ok"})
    assert imgs[0]["image_url"]["url"].split(",")[-1] == "b64data"
    assert "Image data extracted" in xml

    long_str = "A" * 15000
    xml, imgs = _format_tool_result("tool1", long_str)
    assert "middle content truncated" in xml


@pytest.mark.asyncio
async def test_execute_single_tool():
    """Test function/class."""
    tool_inv = {"toolName": "tool1", "args": {"a": 1}}
    tracer = MagicMock()
    tracer.log_tool_execution_start.return_value = "exec_id"

    with (
        patch("strix.tools.executor.execute_tool_invocation", new_callable=AsyncMock) as mock_exec,
        patch("strix.tools.executor._check_error_result", return_value=(False, None)),
        patch("strix.tools.executor._update_tracer_with_result") as mock_update,
        patch("strix.tools.executor._format_tool_result", return_value=("<xml>", [])),
    ):
        mock_exec.return_value = "res"

        xml, imgs, finish = await _execute_single_tool(tool_inv, None, tracer, "agent1")
        assert xml == "<xml>"
        assert not imgs
        assert not finish

        tracer.log_tool_execution_start.assert_called_once()
        mock_update.assert_called_once()

        # Test agent finish scan
        mock_exec.return_value = {"scan_completed": True}
        tool_inv["toolName"] = "finish_scan"
        xml, imgs, finish = await _execute_single_tool(tool_inv, None, None, "agent1")
        assert finish

        # Test agent finish agent_finish
        mock_exec.return_value = {"agent_completed": True}
        tool_inv["toolName"] = "agent_finish"
        xml, imgs, finish = await _execute_single_tool(tool_inv, None, None, "agent1")
        assert finish

        # Test error handling
        mock_exec.side_effect = RuntimeError("err")
        with pytest.raises(RuntimeError):
            await _execute_single_tool(tool_inv, None, tracer, "agent1")

        tracer.update_tool_execution.assert_called_with("exec_id", "error", "err")


def test_get_tracer_and_agent_id():
    """Test function/class."""
    state = MagicMock()
    state.agent_id = "agent1"

    with patch("strix.telemetry.tracer.get_global_tracer", return_value="tracer"):
        tracer, aid = _get_tracer_and_agent_id(state)
        assert tracer == "tracer"
        assert aid == "agent1"

    with patch.dict("sys.modules", {"strix.telemetry.tracer": None}):
        tracer, aid = _get_tracer_and_agent_id(state)
        assert tracer is None
        assert aid == "unknown_agent"


@pytest.mark.asyncio
async def test_process_tool_invocations():
    """Test function/class."""
    invs = [{"toolName": "tool1"}, {"toolName": "finish_scan"}]
    hist = []

    with (
        patch("strix.tools.executor._get_tracer_and_agent_id", return_value=(None, "agent1")),
        patch("strix.tools.executor._execute_single_tool", new_callable=AsyncMock) as mock_single,
    ):
        mock_single.side_effect = [("<xml1>", [{"type": "image_url"}], False), ("<xml2>", [], True)]

        finish = await process_tool_invocations(invs, hist, None)
        assert finish
        assert len(hist) == 1
        assert "xml1" in hist[0]["content"][0]["text"]

    # test without images
    hist = []
    with (
        patch("strix.tools.executor._get_tracer_and_agent_id", return_value=(None, "agent1")),
        patch("strix.tools.executor._execute_single_tool", new_callable=AsyncMock) as mock_single,
    ):
        mock_single.side_effect = [("<xml1>", [], False)]

        finish = await process_tool_invocations([{"toolName": "tool1"}], hist, None)
        assert not finish
        assert len(hist) == 1
        assert isinstance(hist[0]["content"], str)


def test_extract_screenshot_from_result():
    """Test function/class."""
    assert extract_screenshot_from_result("str") is None
    assert extract_screenshot_from_result({"a": 1}) is None
    assert extract_screenshot_from_result({"screenshot": "b64"}) == "b64"
    assert extract_screenshot_from_result({"screenshot": ""}) is None


def test_remove_screenshot_from_result():
    """Test function/class."""
    assert remove_screenshot_from_result("str") == "str"
    assert remove_screenshot_from_result({"a": 1}) == {"a": 1}

    res = {"screenshot": "b64", "other": 1}
    new_res = remove_screenshot_from_result(res)
    assert new_res["screenshot"] == "[Image data extracted - see attached image]"
    assert res["screenshot"] == "b64"  # Original should not be mutated


def test_update_tracer_with_result_connection_error():
    """Test function/class."""
    from unittest.mock import MagicMock

    import pytest

    from strix.tools.executor import _update_tracer_with_result

    tracer_mock = MagicMock()
    tracer_mock.update_tool_execution.side_effect = [ConnectionError("Network failure"), None]

    with pytest.raises(ConnectionError, match="Network failure"):
        _update_tracer_with_result(
            tracer_mock, "123", is_error=False, result="ok", error_payload=None
        )

    assert tracer_mock.update_tool_execution.call_count == 2
    tracer_mock.update_tool_execution.assert_called_with("123", "error", "Network failure")


def test_update_tracer_with_result_runtime_error_no_tracer():
    """Test function/class."""
    from unittest.mock import MagicMock

    import pytest

    from strix.tools.executor import _update_tracer_with_result

    # Actually if there's no tracer, it returns early.
    # To test the except block without tracer or execution_id isn't possible normally
    # because it early returns.
    # Let's test just a standard RuntimeError.
    tracer_mock = MagicMock()
    tracer_mock.update_tool_execution.side_effect = [RuntimeError("Failed"), None]

    with pytest.raises(RuntimeError, match="Failed"):
        _update_tracer_with_result(
            tracer_mock, "123", is_error=True, result=None, error_payload="error payload"
        )
