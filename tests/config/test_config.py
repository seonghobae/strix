import json
from pathlib import Path
from unittest.mock import patch

import pytest

from strix.config.config import (
    STRIX_API_BASE,
    Config,
    apply_saved_config,
    resolve_llm_config,
    save_current_config,
)


@pytest.fixture
def clean_config(monkeypatch, tmp_path):
    config_dir = tmp_path / ".strix"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Ensure config override is removed
    monkeypatch.setattr(Config, "_config_file_override", None)

    # clear env vars
    for name in Config.tracked_vars():
        monkeypatch.delenv(name, raising=False)

    return config_dir


def test_get_returns_env_over_default(clean_config, monkeypatch):
    monkeypatch.setenv("STRIX_LLM", "my-model")
    assert Config.get("strix_llm") == "my-model"


def test_get_returns_default(clean_config):
    assert Config.get("strix_reasoning_effort") == "high"


def test_config_dir(clean_config, tmp_path):
    assert Config.config_dir() == tmp_path / ".strix"


def test_config_file_no_override(clean_config, tmp_path):
    assert Config.config_file() == tmp_path / ".strix" / "cli-config.json"


def test_load_no_file(clean_config):
    assert Config.load() == {}


def test_load_invalid_json(clean_config):
    Config.config_dir().mkdir(parents=True, exist_ok=True)
    Config.config_file().write_text("{invalid")
    assert Config.load() == {}


def test_load_os_error(clean_config):
    Config.config_dir().mkdir(parents=True, exist_ok=True)
    Config.config_file().write_text('{"env": {}}')

    # Simulate an OSError when reading
    with patch("pathlib.Path.open", side_effect=OSError):
        assert Config.load() == {}


def test_save_success(clean_config):
    data = {"env": {"STRIX_LLM": "test-model"}}
    assert Config.save(data) is True
    assert json.loads(Config.config_file().read_text()) == data


def test_save_os_error(clean_config):
    data = {"env": {"STRIX_LLM": "test-model"}}
    with patch("pathlib.Path.open", side_effect=OSError):
        assert Config.save(data) is False


def test_apply_saved_env_not_dict(clean_config):
    Config.config_dir().mkdir(parents=True, exist_ok=True)
    Config.config_file().write_text('{"env": "not a dict"}')
    applied = Config.apply_saved()
    assert applied == {}


def test_apply_saved_cleared_vars(clean_config, monkeypatch):
    # Setup saved config with a var
    Config.save({"env": {"STRIX_LLM": "saved-model", "STRIX_IMAGE": "test-image"}})

    # User clears STRIX_LLM via env var
    monkeypatch.setenv("STRIX_LLM", "")

    applied = Config.apply_saved()
    assert applied == {"STRIX_IMAGE": "test-image"}

    # Check that STRIX_LLM was cleared from file
    loaded = Config.load()
    assert "STRIX_LLM" not in loaded.get("env", {})


def test_apply_saved_llm_env_changed(clean_config, monkeypatch):
    # Setup saved config
    Config.save({"env": {"STRIX_LLM": "saved-model", "STRIX_REASONING_EFFORT": "low"}})

    # User changes STRIX_LLM via env var
    monkeypatch.setenv("STRIX_LLM", "new-model")

    Config.apply_saved()

    # LLM config should be popped from saved file
    loaded = Config.load()
    assert "STRIX_LLM" not in loaded.get("env", {})
    assert "STRIX_REASONING_EFFORT" not in loaded.get("env", {})


def test_llm_env_changed_false(clean_config, monkeypatch):
    assert Config._llm_env_changed({"STRIX_LLM": "saved-model"}) is False


def test_capture_current(clean_config, monkeypatch):
    monkeypatch.setenv("STRIX_LLM", "current-model")
    monkeypatch.setenv("LLM_TIMEOUT", "200")

    captured = Config.capture_current()
    assert captured == {"env": {"STRIX_LLM": "current-model", "LLM_TIMEOUT": "200"}}


def test_save_current(clean_config, monkeypatch):
    Config.save({"env": {"STRIX_LLM": "old-model", "LLM_TIMEOUT": "100"}})

    monkeypatch.setenv("STRIX_LLM", "new-model")
    monkeypatch.setenv("LLM_TIMEOUT", "")  # should remove

    assert Config.save_current() is True

    loaded = Config.load()
    assert loaded["env"]["STRIX_LLM"] == "new-model"
    assert "LLM_TIMEOUT" not in loaded["env"]


def test_save_current_with_empty_and_no_change(clean_config, monkeypatch):
    # Just run save_current without setting env
    assert Config.save_current() is True


def test_apply_saved_config_wrapper(clean_config):
    Config.save({"env": {"LLM_TIMEOUT": "500"}})
    assert apply_saved_config() == {"LLM_TIMEOUT": "500"}


def test_save_current_config_wrapper(clean_config, monkeypatch):
    monkeypatch.setenv("STRIX_REASONING_EFFORT", "low")
    assert save_current_config() is True
    assert Config.load()["env"]["STRIX_REASONING_EFFORT"] == "low"


def test_resolve_llm_config_no_model(clean_config):
    assert resolve_llm_config() == (None, None, None)


def test_resolve_llm_config_strix_model(clean_config, monkeypatch):
    monkeypatch.setenv("STRIX_LLM", "strix/my-model")
    monkeypatch.setenv("LLM_API_KEY", "my-key")

    model, api_key, api_base = resolve_llm_config()
    assert model == "strix/my-model"
    assert api_key == "my-key"
    assert api_base == STRIX_API_BASE


def test_resolve_llm_config_other_model_with_base(clean_config, monkeypatch):
    monkeypatch.setenv("STRIX_LLM", "openai/gpt-4")
    monkeypatch.setenv("LLM_API_KEY", "openai-key")
    monkeypatch.setenv("LLM_API_BASE", "https://api.openai.com")

    model, api_key, api_base = resolve_llm_config()
    assert model == "openai/gpt-4"
    assert api_key == "openai-key"
    assert api_base == "https://api.openai.com"


def test_resolve_llm_config_other_model_with_openai_api_base(clean_config, monkeypatch):
    monkeypatch.setenv("STRIX_LLM", "openai/gpt-4")
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.openai.com")

    model, _, api_base = resolve_llm_config()
    assert model == "openai/gpt-4"
    assert api_base == "https://api.openai.com"
