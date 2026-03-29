"""Tests for proxy actions."""

import sys
from unittest.mock import MagicMock

# Mock proxy_manager module before importing proxy_actions
mock_proxy_manager = MagicMock()
sys.modules["strix.tools.proxy.proxy_manager"] = mock_proxy_manager

from strix.tools.proxy.proxy_actions import (  # noqa: E402
    list_requests,
    list_sitemap,
    repeat_request,
    scope_rules,
    send_request,
    view_request,
    view_sitemap_entry,
)


def test_list_requests():
    """Test list_requests function."""
    mock_manager = MagicMock()
    mock_manager.list_requests.return_value = {"success": True, "data": []}
    mock_proxy_manager.get_proxy_manager.return_value = mock_manager

    result = list_requests(
        httpql_filter="test",
        start_page=1,
        end_page=2,
        page_size=10,
        sort_by="host",
        sort_order="asc",
        scope_id="123",
    )

    mock_manager.list_requests.assert_called_once_with("test", 1, 2, 10, "host", "asc", "123")
    assert result == {"success": True, "data": []}


def test_view_request():
    """Test view_request function."""
    mock_manager = MagicMock()
    mock_manager.view_request.return_value = {"success": True}
    mock_proxy_manager.get_proxy_manager.return_value = mock_manager

    result = view_request(
        request_id="req1",
        part="response",
        search_pattern="pattern",
        page=2,
        page_size=20,
    )

    mock_manager.view_request.assert_called_once_with("req1", "response", "pattern", 2, 20)
    assert result == {"success": True}


def test_send_request():
    """Test send_request function."""
    mock_manager = MagicMock()
    mock_manager.send_simple_request.return_value = {"success": True}
    mock_proxy_manager.get_proxy_manager.return_value = mock_manager

    # Test with default headers
    result1 = send_request(method="GET", url="http://test.com")
    mock_manager.send_simple_request.assert_called_once_with("GET", "http://test.com", {}, "", 30)
    assert result1 == {"success": True}

    mock_manager.send_simple_request.reset_mock()

    # Test with custom headers
    result2 = send_request(
        method="POST",
        url="http://test.com",
        headers={"Content-Type": "application/json"},
        body='{"a": 1}',
        timeout=10,
    )
    mock_manager.send_simple_request.assert_called_once_with(
        "POST", "http://test.com", {"Content-Type": "application/json"}, '{"a": 1}', 10
    )
    assert result2 == {"success": True}


def test_repeat_request():
    """Test repeat_request function."""
    mock_manager = MagicMock()
    mock_manager.repeat_request.return_value = {"success": True}
    mock_proxy_manager.get_proxy_manager.return_value = mock_manager

    # Test with default modifications
    result1 = repeat_request(request_id="req1")
    mock_manager.repeat_request.assert_called_once_with("req1", {})
    assert result1 == {"success": True}

    mock_manager.repeat_request.reset_mock()

    # Test with custom modifications
    result2 = repeat_request(request_id="req2", modifications={"body": "new"})
    mock_manager.repeat_request.assert_called_once_with("req2", {"body": "new"})
    assert result2 == {"success": True}


def test_scope_rules():
    """Test scope_rules function."""
    mock_manager = MagicMock()
    mock_manager.scope_rules.return_value = {"success": True}
    mock_proxy_manager.get_proxy_manager.return_value = mock_manager

    result = scope_rules(
        action="create",
        allowlist=["a"],
        denylist=["b"],
        scope_id="1",
        scope_name="test",
    )

    mock_manager.scope_rules.assert_called_once_with("create", ["a"], ["b"], "1", "test")
    assert result == {"success": True}


def test_list_sitemap():
    """Test list_sitemap function."""
    mock_manager = MagicMock()
    mock_manager.list_sitemap.return_value = {"success": True}
    mock_proxy_manager.get_proxy_manager.return_value = mock_manager

    result = list_sitemap(
        scope_id="1",
        parent_id="2",
        depth="ALL",
        page=3,
    )

    mock_manager.list_sitemap.assert_called_once_with("1", "2", "ALL", 3)
    assert result == {"success": True}


def test_view_sitemap_entry():
    """Test view_sitemap_entry function."""
    mock_manager = MagicMock()
    mock_manager.view_sitemap_entry.return_value = {"success": True}
    mock_proxy_manager.get_proxy_manager.return_value = mock_manager

    result = view_sitemap_entry(entry_id="entry1")

    mock_manager.view_sitemap_entry.assert_called_once_with("entry1")
    assert result == {"success": True}
