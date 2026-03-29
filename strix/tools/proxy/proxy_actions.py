"""Proxy tool actions.

This module provides tools for interacting with HTTP proxy capabilities,
such as listing requests, viewing details, and sending or repeating requests.
"""

from typing import Any, Literal

from strix.tools.registry import register_tool


RequestPart = Literal["request", "response"]


@register_tool
def list_requests(
    httpql_filter: str | None = None,
    start_page: int = 1,
    end_page: int = 1,
    page_size: int = 50,
    sort_by: Literal[
        "timestamp",
        "host",
        "method",
        "path",
        "status_code",
        "response_time",
        "response_size",
        "source",
    ] = "timestamp",
    sort_order: Literal["asc", "desc"] = "desc",
    scope_id: str | None = None,
) -> dict[str, Any]:
    """List proxy requests.

    Args:
        httpql_filter: Optional filter string using HTTPQL syntax.
        start_page: The starting page number (1-based).
        end_page: The ending page number.
        page_size: The number of items per page.
        sort_by: The field to sort the results by.
        sort_order: The order of sorting ("asc" or "desc").
        scope_id: Optional scope ID to filter the requests.

    Returns:
        A dictionary containing the list of requests and pagination info.
    """
    from .proxy_manager import get_proxy_manager

    manager = get_proxy_manager()
    return manager.list_requests(
        httpql_filter, start_page, end_page, page_size, sort_by, sort_order, scope_id
    )


@register_tool
def view_request(
    request_id: str,
    part: RequestPart = "request",
    search_pattern: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """View details of a specific proxy request.

    Args:
        request_id: The ID of the request to view.
        part: The part of the request to view ("request" or "response").
        search_pattern: Optional search pattern to filter the content.
        page: The page number for paginated content.
        page_size: The size of each page.

    Returns:
        A dictionary containing the request details.
    """
    from .proxy_manager import get_proxy_manager

    manager = get_proxy_manager()
    return manager.view_request(request_id, part, search_pattern, page, page_size)


@register_tool
def send_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: str = "",
    timeout: int = 30,
) -> dict[str, Any]:
    """Send a new HTTP request.

    Args:
        method: The HTTP method (e.g., "GET", "POST").
        url: The destination URL.
        headers: Optional dictionary of HTTP headers.
        body: The request body string.
        timeout: Timeout in seconds for the request.

    Returns:
        A dictionary containing the result of the sent request.
    """
    from .proxy_manager import get_proxy_manager

    if headers is None:
        headers = {}
    manager = get_proxy_manager()
    return manager.send_simple_request(method, url, headers, body, timeout)


@register_tool
def repeat_request(
    request_id: str,
    modifications: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Repeat an existing proxy request with optional modifications.

    Args:
        request_id: The ID of the request to repeat.
        modifications: Optional dictionary of modifications to apply.

    Returns:
        A dictionary containing the result of the repeated request.
    """
    from .proxy_manager import get_proxy_manager

    if modifications is None:
        modifications = {}
    manager = get_proxy_manager()
    return manager.repeat_request(request_id, modifications)


@register_tool
def scope_rules(
    action: Literal["get", "list", "create", "update", "delete"],
    allowlist: list[str] | None = None,
    denylist: list[str] | None = None,
    scope_id: str | None = None,
    scope_name: str | None = None,
) -> dict[str, Any]:
    """Manage scope rules for the proxy.

    Args:
        action: The action to perform ("get", "list", "create", "update", "delete").
        allowlist: Optional list of allowed patterns.
        denylist: Optional list of denied patterns.
        scope_id: Optional ID of the scope to manage.
        scope_name: Optional name for a new scope.

    Returns:
        A dictionary containing the result of the scope rules operation.
    """
    from .proxy_manager import get_proxy_manager

    manager = get_proxy_manager()
    return manager.scope_rules(action, allowlist, denylist, scope_id, scope_name)


@register_tool
def list_sitemap(
    scope_id: str | None = None,
    parent_id: str | None = None,
    depth: Literal["DIRECT", "ALL"] = "DIRECT",
    page: int = 1,
) -> dict[str, Any]:
    """List the sitemap entries for the proxy.

    Args:
        scope_id: Optional scope ID to filter sitemap entries.
        parent_id: Optional parent ID to retrieve sub-entries.
        depth: The depth of the retrieval ("DIRECT" or "ALL").
        page: The page number to retrieve.

    Returns:
        A dictionary containing the sitemap entries.
    """
    from .proxy_manager import get_proxy_manager

    manager = get_proxy_manager()
    return manager.list_sitemap(scope_id, parent_id, depth, page)


@register_tool
def view_sitemap_entry(
    entry_id: str,
) -> dict[str, Any]:
    """View details of a specific sitemap entry.

    Args:
        entry_id: The ID of the sitemap entry.

    Returns:
        A dictionary containing the details of the sitemap entry.
    """
    from .proxy_manager import get_proxy_manager

    manager = get_proxy_manager()
    return manager.view_sitemap_entry(entry_id)
