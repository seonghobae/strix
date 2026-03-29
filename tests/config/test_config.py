import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from strix.config.config import Config, apply_saved_config, resolve_llm_config, save_current_config


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch):
    """Reset config state and environment before and after each test."""
    Config._config_file_override = None

    # Clear all tracked env vars so host environment doesn't interfere
    for var_name in Config.tracked_vars():
        monkeypatch.delenv(var_name, raising=False)

    yield
    Config._config_file_override = None


def test_tracked_vars():
    vars_list = Config.tracked_vars()
    assert "STRIX_LLM" in vars_list
    assert "LLM_API_KEY" in vars_list
    assert "STRIX_TELEMETRY" in vars_list


def test_get_returns_env_over_default(monkeypatch):
    monkeypatch.setenv("STRIX_TELEMETRY", "0")
    assert Config.get("strix_telemetry") == "0"


def test_get_returns_default_if_no_env(monkeypatch):
    monkeypatch.delenv("STRIX_TELEMETRY", raising=False)
    assert Config.get("strix_telemetry") == "1"


def test_config_file_override(tmp_path):
    custom_path = tmp_path / "custom.json"
    Config._config_file_override = custom_path
    assert Config.config_file() == custom_path


def test_load_no_file(tmp_path):
    Config._config_file_override = tmp_path / "missing.json"
    assert Config.load() == {}


def test_load_invalid_json(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text("{invalid")
    Config._config_file_override = path
    assert Config.load() == {}


def test_load_os_error():
    Config._config_file_override = Path("/nonexistent/dir/file.json")
    with patch("pathlib.Path.open", side_effect=OSError):
        assert Config.load() == {}


def test_load_valid_json(tmp_path):
    path = tmp_path / "valid.json"
    path.write_text('{"env": {"STRIX_LLM": "test-model"}}')
    Config._config_file_override = path
    assert Config.load() == {"env": {"STRIX_LLM": "test-model"}}


def test_save_success(tmp_path):
    dir_path = tmp_path / ".strix"
    Config._config_file_override = dir_path / "cli-config.json"

    with patch("strix.config.config.Config.config_dir", return_value=dir_path):
        assert Config.save({"test": "data"}) is True
        assert (dir_path / "cli-config.json").exists()

        with (dir_path / "cli-config.json").open() as f:
            data = json.load(f)
            assert data == {"test": "data"}


def test_save_os_error():
    with patch("pathlib.Path.mkdir", side_effect=OSError):
        assert Config.save({"test": "data"}) is False


def test_apply_saved_empty(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("{}")
    Config._config_file_override = path

    applied = apply_saved_config()
    assert applied == {}


def test_apply_saved_with_env(tmp_path):
    path = tmp_path / "valid.json"
    path.write_text('{"env": {"STRIX_TELEMETRY": "0"}}')
    Config._config_file_override = path

    applied = apply_saved_config()
    assert applied == {"STRIX_TELEMETRY": "0"}
    assert os.getenv("STRIX_TELEMETRY") == "0"


def test_apply_saved_clears_empty_vars(tmp_path, monkeypatch):
    path = tmp_path / "cli-config.json"
    path.write_text('{"env": {"STRIX_TELEMETRY": "1"}}')
    Config._config_file_override = None
    monkeypatch.setenv("STRIX_TELEMETRY", "")

    with (
        patch("strix.config.config.Config.config_file", return_value=path),
        patch("strix.config.config.Config.config_dir", return_value=tmp_path),
    ):
        # Should pop STRIX_TELEMETRY from env_vars because os.environ has it empty
        applied = apply_saved_config()
        # It won't apply STRIX_TELEMETRY since it was popped
        assert applied == {}


def test_apply_saved_force(tmp_path, monkeypatch):
    path = tmp_path / "valid.json"
    path.write_text('{"env": {"STRIX_TELEMETRY": "1"}}')
    Config._config_file_override = path
    monkeypatch.setenv("STRIX_TELEMETRY", "0")

    # Without force, it won't overwrite
    applied = apply_saved_config(force=False)
    assert applied == {}
    assert os.getenv("STRIX_TELEMETRY") == "0"

    # With force, it overwrites
    applied = apply_saved_config(force=True)
    assert applied == {"STRIX_TELEMETRY": "1"}
    assert os.getenv("STRIX_TELEMETRY") == "1"


def test_llm_env_changed(monkeypatch):
    saved_env = {"STRIX_LLM": "model-a"}
    # Changed
    monkeypatch.setenv("STRIX_LLM", "model-b")
    assert Config._llm_env_changed(saved_env) is True

    # Not changed
    monkeypatch.setenv("STRIX_LLM", "model-a")
    assert Config._llm_env_changed(saved_env) is False

    # None is ignored
    monkeypatch.delenv("STRIX_LLM", raising=False)
    assert Config._llm_env_changed(saved_env) is False


def test_apply_saved_llm_changed_pops_vars(tmp_path, monkeypatch):
    path = tmp_path / "cli-config.json"
    path.write_text('{"env": {"STRIX_LLM": "model-a", "LLM_API_KEY": "key1"}}')
    Config._config_file_override = None
    with (
        patch("strix.config.config.Config.config_file", return_value=path),
        patch("strix.config.config.Config.config_dir", return_value=tmp_path),
    ):
        monkeypatch.setenv("STRIX_LLM", "model-b")
        applied = apply_saved_config()
        assert applied == {}
        with path.open() as f:
            data = json.load(f)
            assert data == {"env": {}}


def test_save_current_config(tmp_path, monkeypatch):
    path = tmp_path / "cli-config.json"
    path.write_text('{"env": {"STRIX_LLM": "model-a"}}')
    Config._config_file_override = None

    monkeypatch.setenv("STRIX_LLM", "model-b")
    monkeypatch.setenv("STRIX_TELEMETRY", "")

    with (
        patch("strix.config.config.Config.config_file", return_value=path),
        patch("strix.config.config.Config.config_dir", return_value=tmp_path),
    ):
        assert save_current_config() is True
        with path.open() as f:
            data = json.load(f)
            assert data["env"].get("STRIX_LLM") == "model-b"
            assert "STRIX_TELEMETRY" not in data["env"]
            assert "LLM_API_KEY" not in data["env"]


def test_capture_current(monkeypatch):
    monkeypatch.setenv("STRIX_LLM", "model-test")
    captured = Config.capture_current()
    assert "env" in captured
    assert captured["env"]["STRIX_LLM"] == "model-test"
    assert "LLM_API_KEY" not in captured["env"]


def test_resolve_llm_config_none(monkeypatch):
    assert resolve_llm_config() == (None, None, None)


def test_resolve_llm_config_strix_model(monkeypatch):
    monkeypatch.setenv("STRIX_LLM", "strix/fast")
    monkeypatch.setenv("LLM_API_KEY", "strix-key")
    model, key, base = resolve_llm_config()
    assert model == "strix/fast"
    assert key == "strix-key"
    assert base == "https://models.strix.ai/api/v1"


def test_resolve_llm_config_custom_model(monkeypatch):
    monkeypatch.setenv("STRIX_LLM", "openai/gpt-4")
    monkeypatch.setenv("LLM_API_KEY", "custom-key")
    monkeypatch.setenv("LLM_API_BASE", "custom-base")
    model, key, base = resolve_llm_config()
    assert model == "openai/gpt-4"
    assert key == "custom-key"
    assert base == "custom-base"


def test_resolve_llm_config_custom_model_fallback_base(monkeypatch):
    monkeypatch.setenv("STRIX_LLM", "openai/gpt-4")
    monkeypatch.setenv("LLM_API_KEY", "custom-key")
    monkeypatch.setenv("OPENAI_API_BASE", "openai-base")
    model, key, base = resolve_llm_config()
    assert base == "openai-base"


def test_config_file_default(tmp_path):
    Config._config_file_override = None
    with patch("strix.config.config.Config.config_dir", return_value=tmp_path):
        assert Config.config_file() == tmp_path / "cli-config.json"


def test_apply_saved_invalid_env_type(tmp_path):
    path = tmp_path / "valid.json"
    path.write_text('{"env": "not_a_dict"}')
    Config._config_file_override = path

    applied = apply_saved_config()
    assert applied == {}
