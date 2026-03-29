import sys
import types
from unittest.mock import Mock, sentinel

import pytest

import strix.runtime as runtime_module


@pytest.fixture(autouse=True)
def reset_global_runtime(monkeypatch):
    monkeypatch.setattr(runtime_module, "_global_runtime", None)
    yield
    monkeypatch.setattr(runtime_module, "_global_runtime", None)


def test_get_runtime_docker_is_singleton(monkeypatch):
    config_get = Mock(return_value="docker")
    docker_runtime_cls = Mock(return_value=sentinel.runtime)

    fake_docker_runtime_module = types.ModuleType("strix.runtime.docker_runtime")
    fake_docker_runtime_module.DockerRuntime = docker_runtime_cls

    monkeypatch.setattr(runtime_module.Config, "get", config_get)
    monkeypatch.setitem(sys.modules, "strix.runtime.docker_runtime", fake_docker_runtime_module)

    first_runtime = runtime_module.get_runtime()
    second_runtime = runtime_module.get_runtime()

    assert first_runtime is sentinel.runtime
    assert second_runtime is sentinel.runtime
    docker_runtime_cls.assert_called_once_with()
    assert config_get.call_count == 2


def test_get_runtime_raises_for_unsupported_backend(monkeypatch):
    config_get = Mock(return_value="unsupported")
    monkeypatch.setattr(runtime_module.Config, "get", config_get)

    with pytest.raises(ValueError, match="Unsupported runtime backend: unsupported"):
        runtime_module.get_runtime()

    config_get.assert_called_once_with("strix_runtime_backend")
    assert runtime_module._global_runtime is None


def test_cleanup_runtime_cleans_and_resets_global_runtime(monkeypatch):
    runtime_instance = Mock()
    monkeypatch.setattr(runtime_module, "_global_runtime", runtime_instance)

    runtime_module.cleanup_runtime()

    runtime_instance.cleanup.assert_called_once_with()
    assert runtime_module._global_runtime is None


def test_cleanup_runtime_noop_when_runtime_not_initialized():
    runtime_module.cleanup_runtime()

    assert runtime_module._global_runtime is None


def test_sandbox_initialization_error_stores_message_and_details():
    error = runtime_module.SandboxInitializationError("docker unavailable", details="daemon down")

    assert str(error) == "docker unavailable"
    assert error.message == "docker unavailable"
    assert error.details == "daemon down"
