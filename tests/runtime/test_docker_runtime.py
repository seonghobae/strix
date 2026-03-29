from unittest.mock import MagicMock, patch

import httpx
import pytest
from docker.errors import DockerException, ImageNotFound, NotFound

from strix.runtime.docker_runtime import DockerRuntime, SandboxInitializationError


@pytest.fixture
def mock_docker_client():
    with patch("docker.from_env") as mock_env:
        client = MagicMock()
        mock_env.return_value = client
        yield client


def test_docker_runtime_init_success(mock_docker_client):
    runtime = DockerRuntime()
    assert runtime._scan_container is None


def test_docker_runtime_init_failure():
    with patch("docker.from_env", side_effect=DockerException("Test error")):
        with pytest.raises(SandboxInitializationError) as exc_info:
            DockerRuntime()
        assert "Docker is not available" in str(exc_info.value)


def test_find_available_port(mock_docker_client):
    runtime = DockerRuntime()
    port = runtime._find_available_port()
    assert isinstance(port, int)
    assert port > 0


@patch("strix.telemetry.tracer.get_global_tracer")
def test_get_scan_id_with_tracer(mock_get_tracer, mock_docker_client):
    tracer = MagicMock()
    tracer.scan_config = {"scan_id": "test-scan-123"}
    mock_get_tracer.return_value = tracer
    runtime = DockerRuntime()
    assert runtime._get_scan_id("agent-id") == "test-scan-123"


def test_get_scan_id_without_tracer(mock_docker_client):
    runtime = DockerRuntime()
    assert runtime._get_scan_id("agent-123-abc") == "scan-agent"


def test_verify_image_available_success(mock_docker_client):
    mock_docker_client.images.get.return_value = MagicMock(id="123", attrs={"some": "attr"})
    runtime = DockerRuntime()
    runtime._verify_image_available("test-image")


def test_verify_image_available_not_found(mock_docker_client):
    mock_docker_client.images.get.side_effect = ImageNotFound("Not found")
    runtime = DockerRuntime()
    with patch("time.sleep"), pytest.raises(ImageNotFound):
        runtime._verify_image_available("test-image", max_retries=2)


def test_verify_image_available_incomplete(mock_docker_client):
    mock_docker_client.images.get.return_value = MagicMock(id=None)
    runtime = DockerRuntime()
    with patch("time.sleep"), pytest.raises(ImageNotFound):
        runtime._verify_image_available("test-image", max_retries=2)


def test_recover_container_state(mock_docker_client):
    container = MagicMock()
    container.attrs = {
        "Config": {"Env": ["SOME_VAR=1", "TOOL_SERVER_TOKEN=secret_val"]},
        "NetworkSettings": {
            "Ports": {"48081/tcp": [{"HostPort": "12345"}], "48080/tcp": [{"HostPort": "12346"}]}
        },
    }
    runtime = DockerRuntime()
    runtime._recover_container_state(container)
    assert runtime._tool_server_token == "secret_val"  # noqa: S105
    assert runtime._tool_server_port == 12345
    assert runtime._caido_port == 12346


def test_recover_container_state_missing(mock_docker_client):
    container = MagicMock()
    container.attrs = {"Config": {"Env": ["SOME_VAR=1"]}, "NetworkSettings": {"Ports": {}}}
    runtime = DockerRuntime()
    runtime._recover_container_state(container)
    assert runtime._tool_server_token is None
    assert runtime._tool_server_port is None
    assert runtime._caido_port is None


@patch("httpx.Client")
@patch("strix.runtime.docker_runtime.time.sleep")
def test_wait_for_tool_server_success(mock_sleep, mock_httpx_client, mock_docker_client):
    mock_client_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "healthy"}
    mock_client_instance.get.return_value = mock_response
    mock_httpx_client.return_value.__enter__.return_value = mock_client_instance

    runtime = DockerRuntime()
    runtime._tool_server_port = 12345
    runtime._wait_for_tool_server()


@patch("httpx.Client")
@patch("strix.runtime.docker_runtime.time.sleep")
def test_wait_for_tool_server_timeout(mock_sleep, mock_httpx_client, mock_docker_client):
    mock_client_instance = MagicMock()
    mock_client_instance.get.side_effect = httpx.ConnectError("Test error")
    mock_httpx_client.return_value.__enter__.return_value = mock_client_instance

    runtime = DockerRuntime()
    runtime._tool_server_port = 12345
    with pytest.raises(SandboxInitializationError):
        runtime._wait_for_tool_server(max_retries=2)


@patch("strix.config.Config.get")
@patch("strix.runtime.docker_runtime.DockerRuntime._verify_image_available")
@patch("strix.runtime.docker_runtime.DockerRuntime._wait_for_tool_server")
def test_create_container_success(mock_wait, mock_verify, mock_config, mock_docker_client):
    mock_config.side_effect = lambda k: "test-image" if k == "strix_image" else None

    mock_container = MagicMock()
    mock_docker_client.containers.run.return_value = mock_container
    mock_docker_client.containers.get.side_effect = NotFound("Not found")

    runtime = DockerRuntime()
    container = runtime._create_container("test-scan")

    assert container == mock_container
    assert runtime._scan_container == mock_container
    assert runtime._tool_server_port is not None
    assert runtime._caido_port is not None
    assert runtime._tool_server_token is not None
    mock_wait.assert_called_once()


@patch("strix.config.Config.get")
def test_create_container_no_image(mock_config, mock_docker_client):
    mock_config.return_value = None
    runtime = DockerRuntime()
    with pytest.raises(ValueError, match="STRIX_IMAGE must be configured"):
        runtime._create_container("test-scan")


@patch("strix.config.Config.get")
@patch("strix.runtime.docker_runtime.DockerRuntime._verify_image_available")
@patch("strix.runtime.docker_runtime.DockerRuntime._wait_for_tool_server")
@patch("strix.runtime.docker_runtime.time.sleep")
def test_create_container_failure_retry(
    mock_sleep, mock_wait, mock_verify, mock_config, mock_docker_client
):
    mock_config.side_effect = lambda k: "test-image" if k == "strix_image" else None
    mock_docker_client.containers.run.side_effect = DockerException("Test error")
    mock_docker_client.containers.get.side_effect = NotFound("Not found")

    runtime = DockerRuntime()
    with pytest.raises(SandboxInitializationError):
        runtime._create_container("test-scan", max_retries=1)


def test_get_scan_id_import_error(mock_docker_client):
    runtime = DockerRuntime()
    with patch.dict("sys.modules", {"strix.telemetry.tracer": None}):
        assert runtime._get_scan_id("agent-123") == "scan-agent"


@patch("strix.config.Config.get")
@patch("strix.runtime.docker_runtime.DockerRuntime._verify_image_available")
@patch("strix.runtime.docker_runtime.DockerRuntime._wait_for_tool_server")
def test_create_container_stops_existing(mock_wait, mock_verify, mock_config, mock_docker_client):
    mock_config.side_effect = lambda k: "test-image" if k == "strix_image" else None
    existing_container = MagicMock()
    mock_docker_client.containers.get.return_value = existing_container

    mock_new_container = MagicMock()
    mock_docker_client.containers.run.return_value = mock_new_container

    runtime = DockerRuntime()
    runtime._create_container("test-scan")
    existing_container.stop.assert_called_once()
    existing_container.remove.assert_called_once_with(force=True)


def test_get_or_create_container_existing_running(mock_docker_client):
    runtime = DockerRuntime()
    container = MagicMock()
    container.status = "running"
    runtime._scan_container = container
    assert runtime._get_or_create_container("test") == container


def test_get_or_create_container_existing_not_found(mock_docker_client):
    runtime = DockerRuntime()
    container = MagicMock()
    container.reload.side_effect = NotFound("Not found")
    runtime._scan_container = container
    runtime._tool_server_port = 1234

    mock_docker_client.containers.get.side_effect = NotFound("Not found")
    mock_docker_client.containers.list.return_value = []

    with patch.object(runtime, "_create_container") as mock_create:
        mock_create.return_value = MagicMock()
        runtime._get_or_create_container("test")

        assert runtime._scan_container is None
        assert runtime._tool_server_port is None
        mock_create.assert_called_once()


def test_get_or_create_container_by_name(mock_docker_client):
    runtime = DockerRuntime()
    container = MagicMock()
    container.status = "exited"
    mock_docker_client.containers.get.return_value = container

    with patch.object(runtime, "_recover_container_state") as mock_recover:
        assert runtime._get_or_create_container("test") == container
        container.start.assert_called_once()
        mock_recover.assert_called_once_with(container)


def test_get_or_create_container_by_label(mock_docker_client):
    runtime = DockerRuntime()
    mock_docker_client.containers.get.side_effect = NotFound("Not found")

    container = MagicMock()
    container.status = "exited"
    mock_docker_client.containers.list.return_value = [container]

    with patch.object(runtime, "_recover_container_state") as mock_recover:
        assert runtime._get_or_create_container("test") == container
        container.start.assert_called_once()
        mock_recover.assert_called_once_with(container)


@patch("pathlib.Path.exists")
@patch("pathlib.Path.is_dir")
@patch("pathlib.Path.rglob")
def test_copy_local_directory_to_container(
    mock_rglob, mock_is_dir, mock_exists, mock_docker_client
):
    mock_exists.return_value = True
    mock_is_dir.return_value = True

    mock_file = MagicMock()
    mock_file.is_file.return_value = True
    mock_file.relative_to.return_value = "test.txt"
    mock_rglob.return_value = [mock_file]

    runtime = DockerRuntime()
    container = MagicMock()

    with patch("tarfile.open"):
        runtime._copy_local_directory_to_container(container, "/dummy/path")
        container.put_archive.assert_called_once()
        container.exec_run.assert_called_once()


@pytest.mark.asyncio
@patch("strix.runtime.docker_runtime.DockerRuntime._register_agent")
async def test_create_sandbox_success(mock_register, mock_docker_client):
    runtime = DockerRuntime()
    container = MagicMock()
    container.id = "container123"

    runtime._tool_server_port = 12345
    runtime._caido_port = 12346
    runtime._tool_server_token = "val123"  # noqa: S105

    with (
        patch.object(runtime, "_get_scan_id", return_value="scan-123"),
        patch.object(runtime, "_get_or_create_container", return_value=container),
        patch.object(runtime, "_resolve_docker_host", return_value="localhost"),
    ):
        sandbox = await runtime.create_sandbox("agent-123")
        assert sandbox["workspace_id"] == "container123"
        assert sandbox["api_url"] == "http://localhost:12345"
        mock_register.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_sandbox_missing_token(mock_docker_client):
    runtime = DockerRuntime()
    container = MagicMock()
    container.id = "container123"

    with (
        patch.object(runtime, "_get_scan_id", return_value="scan-123"),
        patch.object(runtime, "_get_or_create_container", return_value=container),
        pytest.raises(RuntimeError, match="Tool server not initialized"),
    ):
        await runtime.create_sandbox("agent-123")


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_register_agent(mock_async_client, mock_docker_client):
    mock_client_instance = MagicMock()
    mock_response = MagicMock()
    from unittest.mock import AsyncMock

    mock_client_instance.post = AsyncMock(return_value=mock_response)
    mock_async_client.return_value.__aenter__.return_value = mock_client_instance

    runtime = DockerRuntime()
    await runtime._register_agent("http://localhost:1234", "agent-123", "token")
    mock_client_instance.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_sandbox_url(mock_docker_client):
    runtime = DockerRuntime()
    mock_docker_client.containers.get.return_value = MagicMock()
    with patch.object(runtime, "_resolve_docker_host", return_value="localhost"):
        url = await runtime.get_sandbox_url("container123", 8080)
        assert url == "http://localhost:8080"


@pytest.mark.asyncio
async def test_get_sandbox_url_not_found(mock_docker_client):
    runtime = DockerRuntime()
    mock_docker_client.containers.get.side_effect = NotFound("Not found")
    with pytest.raises(ValueError, match="Container container123 not found."):
        await runtime.get_sandbox_url("container123", 8080)


def test_resolve_docker_host(mock_docker_client):
    runtime = DockerRuntime()
    with patch.dict("os.environ", {"DOCKER_HOST": "tcp://192.168.1.100:2375"}):
        assert runtime._resolve_docker_host() == "192.168.1.100"
    with patch.dict("os.environ", {"DOCKER_HOST": ""}):
        assert runtime._resolve_docker_host() == "127.0.0.1"


@pytest.mark.asyncio
async def test_destroy_sandbox(mock_docker_client):
    runtime = DockerRuntime()
    container = MagicMock()
    mock_docker_client.containers.get.return_value = container

    runtime._scan_container = container
    runtime._tool_server_port = 1234

    await runtime.destroy_sandbox("container123")
    container.stop.assert_called_once()
    container.remove.assert_called_once()
    assert runtime._scan_container is None
    assert runtime._tool_server_port is None


@patch("subprocess.Popen")
def test_cleanup(mock_popen, mock_docker_client):
    runtime = DockerRuntime()
    container = MagicMock()
    container.name = "test-container"
    runtime._scan_container = container
    runtime._tool_server_port = 1234

    runtime.cleanup()

    assert runtime._scan_container is None
    assert runtime._tool_server_port is None
    mock_popen.assert_called_once()


def test_get_or_create_container_docker_exception(mock_docker_client):
    runtime = DockerRuntime()
    mock_docker_client.containers.get.side_effect = NotFound("Not found")
    mock_docker_client.containers.list.side_effect = DockerException("Test error")
    with patch.object(runtime, "_create_container") as mock_create:
        mock_create.return_value = MagicMock()
        runtime._get_or_create_container("test")
        mock_create.assert_called_once()


@patch("pathlib.Path.exists")
def test_copy_local_directory_not_exists(mock_exists, mock_docker_client):
    mock_exists.return_value = False
    runtime = DockerRuntime()
    container = MagicMock()
    runtime._copy_local_directory_to_container(container, "/dummy/path")
    container.put_archive.assert_not_called()


@patch("pathlib.Path.exists")
@patch("pathlib.Path.is_dir")
@patch("pathlib.Path.rglob")
def test_copy_local_directory_exception(mock_rglob, mock_is_dir, mock_exists, mock_docker_client):
    mock_exists.return_value = True
    mock_is_dir.return_value = True
    mock_rglob.return_value = [MagicMock()]

    runtime = DockerRuntime()
    container = MagicMock()
    container.put_archive.side_effect = DockerException("Test error")

    with patch("tarfile.open"):
        # Should not raise
        runtime._copy_local_directory_to_container(container, "/dummy/path")


@pytest.mark.asyncio
@patch("strix.runtime.docker_runtime.DockerRuntime._register_agent")
async def test_create_sandbox_with_local_sources(mock_register, mock_docker_client):
    runtime = DockerRuntime()
    container = MagicMock()
    container.id = "container123"

    runtime._tool_server_port = 12345
    runtime._caido_port = 12346
    runtime._tool_server_token = "val123"  # noqa: S105

    local_sources = [
        {"source_path": "/dummy/path", "workspace_subdir": "target_1"},
        {"source_path": "/dummy/path2"},
    ]

    with (
        patch.object(runtime, "_get_scan_id", return_value="scan-123"),
        patch.object(runtime, "_get_or_create_container", return_value=container),
        patch.object(runtime, "_copy_local_directory_to_container") as mock_copy,
        patch.object(runtime, "_resolve_docker_host", return_value="localhost"),
    ):
        await runtime.create_sandbox("agent-123", local_sources=local_sources)
        assert mock_copy.call_count == 2


@pytest.mark.asyncio
async def test_create_sandbox_container_id_none(mock_docker_client):
    runtime = DockerRuntime()
    container = MagicMock()
    container.id = None

    with (
        patch.object(runtime, "_get_scan_id", return_value="scan-123"),
        patch.object(runtime, "_get_or_create_container", return_value=container),
        pytest.raises(RuntimeError, match="Docker container ID is unexpectedly None"),
    ):
        await runtime.create_sandbox("agent-123")


@pytest.mark.asyncio
@patch("httpx.AsyncClient")
async def test_register_agent_request_error(mock_async_client, mock_docker_client):
    from unittest.mock import AsyncMock

    mock_client_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.RequestError("Test error")
    mock_client_instance.post = AsyncMock(return_value=mock_response)
    mock_async_client.return_value.__aenter__.return_value = mock_client_instance

    runtime = DockerRuntime()
    # Should catch exception and not raise
    await runtime._register_agent("http://localhost:1234", "agent-123", "token")


@pytest.mark.asyncio
async def test_destroy_sandbox_exception(mock_docker_client):
    runtime = DockerRuntime()
    mock_docker_client.containers.get.side_effect = NotFound("Not found")
    # Should catch exception
    await runtime.destroy_sandbox("container123")


@patch("subprocess.Popen")
def test_cleanup_no_container_name(mock_popen, mock_docker_client):
    runtime = DockerRuntime()
    container = MagicMock()
    container.name = None
    runtime._scan_container = container

    runtime.cleanup()
    mock_popen.assert_not_called()


@pytest.mark.asyncio
@patch("strix.runtime.docker_runtime.DockerRuntime._register_agent")
async def test_create_sandbox_with_local_sources_missing_path(mock_register, mock_docker_client):
    runtime = DockerRuntime()
    container = MagicMock()
    container.id = "container123"

    runtime._tool_server_port = 12345
    runtime._caido_port = 12346
    runtime._tool_server_token = "val123"  # noqa: S105

    local_sources = [
        {"workspace_subdir": "target_1"}  # Missing source_path
    ]

    with (
        patch.object(runtime, "_get_scan_id", return_value="scan-123"),
        patch.object(runtime, "_get_or_create_container", return_value=container),
        patch.object(runtime, "_copy_local_directory_to_container") as mock_copy,
        patch.object(runtime, "_resolve_docker_host", return_value="localhost"),
    ):
        await runtime.create_sandbox("agent-123", local_sources=local_sources)
        mock_copy.assert_not_called()
