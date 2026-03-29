"""Tests for proxy tool actions."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from strix.tools.proxy.proxy_actions import (
    list_requests,
    list_sitemap,
    repeat_request,
    scope_rules,
    send_request,
    view_request,
    view_sitemap_entry,
)


@pytest.fixture
def mock_proxy_manager(monkeypatch: pytest.MonkeyPatch):
    """Provide a mocked proxy manager without importing optional dependencies."""
    mock_manager = MagicMock()
    fake_proxy_module = SimpleNamespace(get_proxy_manager=lambda: mock_manager)
    monkeypatch.setitem(sys.modules, "strix.tools.proxy.proxy_manager", fake_proxy_module)
    return mock_manager


def test_list_requests(mock_proxy_manager):
    """Verify list_requests forwards filters and pagination to manager."""
    mock_proxy_manager.list_requests.return_value = {"status": "ok"}
    result = list_requests(
        httpql_filter="status_code:200",
        start_page=1,
        end_page=2,
        page_size=10,
        sort_by="status_code",
        sort_order="asc",
        scope_id="scope-123",
    )
    assert result == {"status": "ok"}
    mock_proxy_manager.list_requests.assert_called_once_with(
        "status_code:200", 1, 2, 10, "status_code", "asc", "scope-123"
    )


def test_view_request(mock_proxy_manager):
    """Verify view_request forwards request lookup parameters."""
    mock_proxy_manager.view_request.return_value = {"data": "test"}
    result = view_request(
        request_id="req-1", part="response", search_pattern="test", page=2, page_size=20
    )
    assert result == {"data": "test"}
    mock_proxy_manager.view_request.assert_called_once_with("req-1", "response", "test", 2, 20)


def test_send_request(mock_proxy_manager):
    """Verify send_request forwards method/url/headers/body arguments."""
    mock_proxy_manager.send_simple_request.return_value = {"sent": True}

    # Without headers
    result = send_request(method="GET", url="http://example.com", timeout=10)
    assert result == {"sent": True}
    mock_proxy_manager.send_simple_request.assert_called_with(
        "GET", "http://example.com", {}, "", 10
    )

    mock_proxy_manager.send_simple_request.reset_mock()

    # With headers and body
    result = send_request(
        method="POST",
        url="http://example.com",
        headers={"Content-Type": "application/json"},
        body='{"foo":"bar"}',
        timeout=5,
    )
    assert result == {"sent": True}
    mock_proxy_manager.send_simple_request.assert_called_with(
        "POST", "http://example.com", {"Content-Type": "application/json"}, '{"foo":"bar"}', 5
    )


def test_repeat_request(mock_proxy_manager):
    """Verify repeat_request uses empty/default and explicit modifications."""
    mock_proxy_manager.repeat_request.return_value = {"repeated": True}

    # Without modifications
    result = repeat_request(request_id="req-1")
    assert result == {"repeated": True}
    mock_proxy_manager.repeat_request.assert_called_with("req-1", {})

    mock_proxy_manager.repeat_request.reset_mock()

    # With modifications
    mods = {"headers": {"X-Test": "1"}}
    result = repeat_request(request_id="req-2", modifications=mods)
    assert result == {"repeated": True}
    mock_proxy_manager.repeat_request.assert_called_with("req-2", mods)


def test_scope_rules(mock_proxy_manager):
    """Verify scope_rules forwards scope policy arguments."""
    mock_proxy_manager.scope_rules.return_value = {"rules": "updated"}
    result = scope_rules(
        action="update",
        allowlist=["*.com"],
        denylist=["*.org"],
        scope_id="scope-1",
        scope_name="Test Scope",
    )
    assert result == {"rules": "updated"}
    mock_proxy_manager.scope_rules.assert_called_once_with(
        "update", ["*.com"], ["*.org"], "scope-1", "Test Scope"
    )


def test_list_sitemap(mock_proxy_manager):
    """Verify list_sitemap forwards scope and traversal parameters."""
    mock_proxy_manager.list_sitemap.return_value = {"sitemap": []}
    result = list_sitemap(scope_id="scope-1", parent_id="parent-2", depth="ALL", page=3)
    assert result == {"sitemap": []}
    mock_proxy_manager.list_sitemap.assert_called_once_with("scope-1", "parent-2", "ALL", 3)


def test_view_sitemap_entry(mock_proxy_manager):
    """Verify view_sitemap_entry forwards entry identifier."""
    mock_proxy_manager.view_sitemap_entry.return_value = {"entry": {}}
    result = view_sitemap_entry(entry_id="entry-1")
    assert result == {"entry": {}}
    mock_proxy_manager.view_sitemap_entry.assert_called_once_with("entry-1")
