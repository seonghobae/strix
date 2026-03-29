"""Tests for web search actions."""

from unittest.mock import MagicMock, patch

import requests

from strix.tools.web_search.web_search_actions import SYSTEM_PROMPT, web_search


def test_web_search_success():
    """Test successful web search."""
    with (
        patch("os.getenv", return_value="test_key"),
        patch("requests.post") as mock_post,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test result content"}}]
        }
        mock_post.return_value = mock_response

        result = web_search("test query")

        assert result["success"] is True
        assert result["content"] == "Test result content"
        assert result["query"] == "test query"
        assert result["message"] == "Web search completed successfully"

        mock_post.assert_called_once_with(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": "Bearer test_key", "Content-Type": "application/json"},
            json={
                "model": "sonar-reasoning-pro",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "test query"},
                ],
            },
            timeout=300,
        )


def test_web_search_no_api_key():
    """Test web search without API key."""
    with patch("os.getenv", return_value=None):
        result = web_search("test query")

        assert result["success"] is False
        assert result["message"] == "PERPLEXITY_API_KEY environment variable not set"
        assert result["results"] == []


def test_web_search_timeout():
    """Test web search timeout."""
    with (
        patch("os.getenv", return_value="test_key"),
        patch("requests.post", side_effect=requests.exceptions.Timeout),
    ):
        result = web_search("test query")

        assert result["success"] is False
        assert result["message"] == "Request timed out"


def test_web_search_request_exception():
    """Test web search request exception."""
    with (
        patch("os.getenv", return_value="test_key"),
        patch(
            "requests.post",
            side_effect=requests.exceptions.RequestException("Connection error"),
        ),
    ):
        result = web_search("test query")

        assert result["success"] is False
        assert "API request failed" in result["message"]


def test_web_search_key_error():
    """Test web search unexpected response format."""
    with (
        patch("os.getenv", return_value="test_key"),
        patch("requests.post") as mock_post,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {"wrong_format": True}
        mock_post.return_value = mock_response

        result = web_search("test query")

        assert result["success"] is False
        assert "Unexpected API response format" in result["message"]


def test_web_search_general_exception():
    """Test web search general exception."""
    with patch("os.getenv", side_effect=Exception("Unexpected error")):
        result = web_search("test query")

        assert result["success"] is False
        assert "Web search failed" in result["message"]
