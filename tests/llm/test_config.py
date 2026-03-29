"""Tests for the LLM configuration module."""

from unittest.mock import patch

import pytest

from strix.llm.config import LLMConfig


def test_llm_config_empty_model_name():
    """Test that creating LLMConfig without a model name raises ValueError."""
    with (
        patch("strix.llm.config.resolve_llm_config", return_value=(None, None, None)),
        pytest.raises(ValueError, match="STRIX_LLM environment variable must be set and not empty"),
    ):
        LLMConfig(model_name=None)


def test_llm_config_success():
    """Test successful initialization of LLMConfig."""
    with (
        patch(
            "strix.llm.config.resolve_llm_config",
            return_value=("test-model", "test-key", "test-base"),
        ),
        patch(
            "strix.llm.config.resolve_strix_model",
            return_value=("api-test-model", "canonical-test-model"),
        ),
    ):
        config = LLMConfig(
            model_name=None,
            scan_mode="quick",
            skills=["test_skill"],
            timeout=100,
            reasoning_effort="high",
            system_prompt_context={"test": "context"},
            interactive=True,
        )
        assert config.model_name == "test-model"
        assert config.api_key == "test-key"
        assert config.api_base == "test-base"
        assert config.litellm_model == "api-test-model"
        assert config.canonical_model == "canonical-test-model"
        assert config.scan_mode == "quick"
        assert config.skills == ["test_skill"]
        assert config.timeout == 100
        assert config.reasoning_effort == "high"
        assert config.system_prompt_context == {"test": "context"}
        assert config.interactive is True


def test_llm_config_fallback_values():
    """Test fallback values for LLMConfig when some configs are not provided."""
    with (
        patch("strix.llm.config.resolve_llm_config", return_value=("test-model", None, None)),
        patch("strix.llm.config.resolve_strix_model", return_value=(None, None)),
        patch("strix.llm.config.Config.get", return_value="400"),
    ):
        config = LLMConfig(model_name="explicit-model", scan_mode="invalid_mode")
        assert config.model_name == "explicit-model"
        assert config.litellm_model == "explicit-model"
        assert config.canonical_model == "explicit-model"
        assert config.scan_mode == "deep"
        assert config.timeout == 400
        assert config.skills == []
        assert config.system_prompt_context == {}
