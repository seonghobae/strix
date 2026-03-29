import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from strix.tools.web_search.web_search_actions import SYSTEM_PROMPT, web_search


@pytest.fixture
def mock_env():
    """Mock the environment variable for testing."""
    with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-api-key"}):
        yield


def test_web_search_no_api_key():
    """Test web_search when PERPLEXITY_API_KEY is not set."""
    with patch.dict(os.environ, {}, clear=True):
        result = web_search("test query")
        assert result["success"] is False
        assert result["message"] == "PERPLEXITY_API_KEY environment variable not set"
        assert result["results"] == []


@patch("strix.tools.web_search.web_search_actions.requests.post")
def test_web_search_success(mock_post, mock_env):
    """Test web_search with a successful API response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Mocked search result."}}]
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = web_search("test query")

    assert result["success"] is True
    assert result["query"] == "test query"
    assert result["content"] == "Mocked search result."
    assert result["message"] == "Web search completed successfully"

    # Verify the API request payload and headers
    mock_post.assert_called_once_with(
        "https://api.perplexity.ai/chat/completions",
        headers={"Authorization": "Bearer test-api-key", "Content-Type": "application/json"},
        json={
            "model": "sonar-reasoning-pro",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "test query"},
            ],
        },
        timeout=300,
    )


@patch("strix.tools.web_search.web_search_actions.requests.post")
def test_web_search_timeout(mock_post, mock_env):
    """Test web_search handling a request timeout."""
    mock_post.side_effect = requests.exceptions.Timeout("Timeout error")

    result = web_search("test query")

    assert result["success"] is False
    assert result["message"] == "Request timed out"
    assert result["results"] == []


@patch("strix.tools.web_search.web_search_actions.requests.post")
def test_web_search_request_exception(mock_post, mock_env):
    """Test web_search handling a generic RequestException."""
    mock_post.side_effect = requests.exceptions.RequestException("Connection error")

    result = web_search("test query")

    assert result["success"] is False
    assert result["message"] == "API request failed: Connection error"
    assert result["results"] == []


@patch("strix.tools.web_search.web_search_actions.requests.post")
def test_web_search_key_error(mock_post, mock_env):
    """Test web_search handling unexpected JSON response format."""
    mock_response = MagicMock()
    # Missing 'choices' key
    mock_response.json.return_value = {"invalid": "format"}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = web_search("test query")

    assert result["success"] is False
    assert "Unexpected API response format: missing" in result["message"]
    assert result["results"] == []


@patch("strix.tools.web_search.web_search_actions.requests.post")
def test_web_search_generic_exception(mock_post, mock_env):
    """Test web_search handling an unexpected generic Exception."""
    mock_post.side_effect = ValueError("Some unexpected error")

    result = web_search("test query")

    assert result["success"] is False
    assert result["message"] == "Web search failed: Some unexpected error"
    assert result["results"] == []
