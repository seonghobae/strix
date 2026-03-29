"""Tests for todo action helpers and tool functions."""

from datetime import UTC
from datetime import datetime as real_datetime
from types import SimpleNamespace

import pytest

from strix.tools.todo import todo_actions


@pytest.fixture(autouse=True)
def clear_todo_storage() -> None:
    """Reset in-memory todo storage for each test."""
    todo_actions._todos_storage.clear()
    yield
    todo_actions._todos_storage.clear()


@pytest.fixture
def agent_state() -> SimpleNamespace:
    """Create a minimal agent state with agent_id."""
    return SimpleNamespace(agent_id="agent-A")


def test_get_agent_todos_initializes_and_reuses_bucket() -> None:
    """Get-agent helper initializes once and reuses same mapping."""
    first = todo_actions._get_agent_todos("agent-A")
    second = todo_actions._get_agent_todos("agent-A")
    third = todo_actions._get_agent_todos("agent-B")

    assert first is second
    assert first == {}
    assert third == {}
    assert first is not third


def test_normalize_priority_valid_and_invalid() -> None:
    """Priority normalizes case and rejects unsupported values."""
    assert todo_actions._normalize_priority("HIGH") == "high"
    assert todo_actions._normalize_priority(None) == "normal"
    assert todo_actions._normalize_priority(None, default="LOW") == "low"

    with pytest.raises(ValueError, match="Invalid priority"):
        todo_actions._normalize_priority("urgent")


@pytest.mark.parametrize(
    ("raw_ids", "expected"),
    [
        (None, []),
        ("", []),
        ("   ", []),
        ("a", ["a"]),
        ("a,b", ["a", "b"]),
        ('["x", "", " y "]', ["x", "y"]),
        ('"solo"', ["solo"]),
        (["x", "", " y "], ["x", "y"]),
        (123, ["123"]),
    ],
)
def test_normalize_todo_ids_inputs(raw_ids: object, expected: list[str]) -> None:
    """Todo ID normalizer handles scalar/list/string inputs."""
    assert todo_actions._normalize_todo_ids(raw_ids) == expected


def test_normalize_bulk_updates_variants_and_errors() -> None:
    """Bulk update normalizer supports valid structures and rejects invalid ones."""
    assert todo_actions._normalize_bulk_updates(None) == []
    assert todo_actions._normalize_bulk_updates("  ") == []

    assert todo_actions._normalize_bulk_updates('{"id":"a1","title":"T"}') == [
        {
            "todo_id": "a1",
            "title": "T",
            "description": None,
            "priority": None,
            "status": None,
        }
    ]

    assert todo_actions._normalize_bulk_updates(
        [{"todo_id": "a2", "description": "D", "priority": "high", "status": "done"}]
    ) == [
        {
            "todo_id": "a2",
            "title": None,
            "description": "D",
            "priority": "high",
            "status": "done",
        }
    ]

    with pytest.raises(ValueError, match="Updates must be valid JSON"):
        todo_actions._normalize_bulk_updates("{bad")

    with pytest.raises(TypeError, match="list of update objects"):
        todo_actions._normalize_bulk_updates(5)

    with pytest.raises(TypeError, match="Each update must be an object"):
        todo_actions._normalize_bulk_updates(["bad"])

    with pytest.raises(ValueError, match="must include 'todo_id'"):
        todo_actions._normalize_bulk_updates([{"title": "missing id"}])


def test_normalize_bulk_todos_variants_and_errors() -> None:
    """Bulk todo normalizer handles JSON, line fallback, and validation errors."""
    assert todo_actions._normalize_bulk_todos(None) == []
    assert todo_actions._normalize_bulk_todos(" ") == []

    assert todo_actions._normalize_bulk_todos("- first\n* second\n\tthird") == [
        {"title": "first"},
        {"title": "second"},
        {"title": "third"},
    ]

    assert todo_actions._normalize_bulk_todos(
        '{"title":"  Task  ","description":"   ","priority":"critical"}'
    ) == [{"title": "Task", "description": None, "priority": "critical"}]

    assert todo_actions._normalize_bulk_todos(
        ["  Alpha  ", "", {"title": " Beta ", "description": " Desc ", "priority": "low"}]
    ) == [
        {"title": "Alpha"},
        {"title": "Beta", "description": "Desc", "priority": "low"},
    ]

    with pytest.raises(TypeError, match="list, dict, or JSON string"):
        todo_actions._normalize_bulk_todos(123)

    with pytest.raises(TypeError, match="string or object with a title"):
        todo_actions._normalize_bulk_todos([True])

    with pytest.raises(ValueError, match="non-empty 'title'"):
        todo_actions._normalize_bulk_todos([{"title": "   "}])


def test_sorted_todos_order_includes_unknown_status_priority() -> None:
    """Sorting helper orders known statuses/priorities before unknown ones."""
    todos = todo_actions._get_agent_todos("agent-A")
    todos.update(
        {
            "a": {
                "title": "done-low",
                "status": "done",
                "priority": "low",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            "b": {
                "title": "pending-critical",
                "status": "pending",
                "priority": "critical",
                "created_at": "2026-01-01T00:00:01+00:00",
            },
            "c": {
                "title": "weird",
                "status": "custom",
                "priority": "urgent",
                "created_at": "2026-01-01T00:00:02+00:00",
            },
            "d": {
                "title": "in-progress-high",
                "status": "in_progress",
                "priority": "high",
                "created_at": "2026-01-01T00:00:03+00:00",
            },
        }
    )

    ordered = todo_actions._sorted_todos("agent-A")
    assert [item["todo_id"] for item in ordered] == ["a", "d", "b", "c"]


def test_create_todo_requires_title_or_todos(agent_state: SimpleNamespace) -> None:
    """Create returns a validation error when no task payload is provided."""
    result = todo_actions.create_todo(agent_state)
    assert result == {
        "success": False,
        "error": "Provide a title or 'todos' list to create.",
        "todo_id": None,
    }


def test_create_todo_success_with_title_and_bulk(
    monkeypatch: pytest.MonkeyPatch, agent_state: SimpleNamespace
) -> None:
    """Create supports title and bulk todos with deterministic IDs/timestamps."""

    class _FixedDateTime:
        @classmethod
        def now(cls, tz):
            assert tz is UTC
            return real_datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    uuids = iter(["abcdef12-0000", "ghijkl34-0000", "mnopqr56-0000"])

    monkeypatch.setattr(todo_actions, "datetime", _FixedDateTime)
    monkeypatch.setattr(todo_actions.uuid, "uuid4", lambda: next(uuids))

    result = todo_actions.create_todo(
        agent_state,
        title="  Inline  ",
        description="  Inline description ",
        priority="HIGH",
        todos=[{"title": "Bulk", "priority": "low"}, "Bulk 2"],
    )

    assert result["success"] is True
    assert result["count"] == 3
    assert [item["todo_id"] for item in result["created"]] == ["abcdef", "ghijkl", "mnopqr"]

    todos = result["todos"]
    assert len(todos) == 3
    assert {todo["status"] for todo in todos} == {"pending"}
    assert {todo["created_at"] for todo in todos} == {"2026-01-01T12:00:00+00:00"}
    assert {todo["updated_at"] for todo in todos} == {"2026-01-01T12:00:00+00:00"}
    inline = next(todo for todo in todos if todo["title"] == "Inline")
    assert inline["description"] == "Inline description"
    assert inline["priority"] == "high"
    assert inline["completed_at"] is None


def test_create_todo_error_wrapper(agent_state: SimpleNamespace) -> None:
    """Create wraps validation/type errors into a failure response."""
    result_priority = todo_actions.create_todo(agent_state, title="X", priority="urgent")
    assert result_priority["success"] is False
    assert "Failed to create todo" in result_priority["error"]

    result_type = todo_actions.create_todo(agent_state, todos=[{"title": "ok"}, 1])
    assert result_type["success"] is False
    assert "Failed to create todo" in result_type["error"]


def test_list_todos_filters_sorts_and_summary(agent_state: SimpleNamespace) -> None:
    """List applies filters/sorting and counts statuses, including unknown ones."""
    todos = todo_actions._get_agent_todos(agent_state.agent_id)
    todos.update(
        {
            "x1": {
                "title": "done",
                "description": None,
                "priority": "low",
                "status": "done",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "completed_at": "2026-01-01T00:00:00+00:00",
            },
            "x2": {
                "title": "pending",
                "description": None,
                "priority": "critical",
                "status": "pending",
                "created_at": "2026-01-01T00:00:01+00:00",
                "updated_at": "2026-01-01T00:00:01+00:00",
                "completed_at": None,
            },
            "x3": {
                "title": "custom",
                "description": None,
                "priority": "normal",
                "status": "blocked",
                "created_at": "2026-01-01T00:00:02+00:00",
                "updated_at": "2026-01-01T00:00:02+00:00",
                "completed_at": None,
            },
        }
    )

    listed = todo_actions.list_todos(agent_state)
    assert listed["success"] is True
    assert [item["todo_id"] for item in listed["todos"]] == ["x1", "x2", "x3"]
    assert listed["summary"]["pending"] == 1
    assert listed["summary"]["done"] == 1
    assert listed["summary"]["in_progress"] == 0
    assert listed["summary"]["blocked"] == 1

    filtered = todo_actions.list_todos(agent_state, status="PENDING", priority="CRITICAL")
    assert filtered["total_count"] == 1
    assert filtered["todos"][0]["todo_id"] == "x2"

    filtered_priority_only = todo_actions.list_todos(agent_state, priority="LOW")
    assert filtered_priority_only["total_count"] == 1
    assert filtered_priority_only["todos"][0]["todo_id"] == "x1"


def test_list_todos_exception_branch(
    monkeypatch: pytest.MonkeyPatch, agent_state: SimpleNamespace
) -> None:
    """List returns safe fallback payload when helper raises."""
    monkeypatch.setattr(
        todo_actions, "_get_agent_todos", lambda _aid: (_ for _ in ()).throw(TypeError("boom"))
    )

    result = todo_actions.list_todos(agent_state)
    assert result["success"] is False
    assert "Failed to list todos" in result["error"]
    assert result["todos"] == []
    assert result["total_count"] == 0
    assert result["summary"] == {"pending": 0, "in_progress": 0, "done": 0}


def test_apply_single_update_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Single update helper handles validation, status transitions, and timestamps."""

    class _FixedDateTime:
        @classmethod
        def now(cls, tz):
            assert tz is UTC
            return real_datetime(2026, 2, 2, 11, 0, 0, tzinfo=UTC)

    monkeypatch.setattr(todo_actions, "datetime", _FixedDateTime)

    agent_todos = {
        "t1": {
            "title": "A",
            "description": "D",
            "priority": "normal",
            "status": "pending",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "completed_at": None,
        }
    }

    assert todo_actions._apply_single_update(agent_todos, "missing") == {
        "todo_id": "missing",
        "error": "Todo with ID 'missing' not found",
    }

    assert todo_actions._apply_single_update(agent_todos, "t1", title="  ") == {
        "todo_id": "t1",
        "error": "Title cannot be empty",
    }

    assert todo_actions._apply_single_update(agent_todos, "t1", priority="urgent") == {
        "todo_id": "t1",
        "error": "Invalid priority. Must be one of: low, normal, high, critical",
    }

    assert todo_actions._apply_single_update(agent_todos, "t1", status="blocked") == {
        "todo_id": "t1",
        "error": "Invalid status. Must be one of: pending, in_progress, done",
    }

    assert (
        todo_actions._apply_single_update(
            agent_todos,
            "t1",
            title="  B  ",
            description="",
            priority="HIGH",
            status="done",
        )
        is None
    )
    assert agent_todos["t1"]["title"] == "B"
    assert agent_todos["t1"]["description"] is None
    assert agent_todos["t1"]["priority"] == "high"
    assert agent_todos["t1"]["status"] == "done"
    assert agent_todos["t1"]["completed_at"] == "2026-02-02T11:00:00+00:00"
    assert agent_todos["t1"]["updated_at"] == "2026-02-02T11:00:00+00:00"

    assert todo_actions._apply_single_update(agent_todos, "t1", status="in_progress") is None
    assert agent_todos["t1"]["completed_at"] is None


def test_apply_single_update_without_status_still_updates_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single update updates timestamp even when status is omitted."""

    class _FixedDateTime:
        @classmethod
        def now(cls, tz):
            assert tz is UTC
            return real_datetime(2026, 3, 3, 10, 0, 0, tzinfo=UTC)

    monkeypatch.setattr(todo_actions, "datetime", _FixedDateTime)
    agent_todos = {
        "t1": {
            "title": "A",
            "description": "D",
            "priority": "normal",
            "status": "pending",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "completed_at": None,
        }
    }

    assert todo_actions._apply_single_update(agent_todos, "t1", title="B") is None
    assert agent_todos["t1"]["status"] == "pending"
    assert agent_todos["t1"]["updated_at"] == "2026-03-03T10:00:00+00:00"


def test_update_todo_no_payload(agent_state: SimpleNamespace) -> None:
    """Update requires todo_id or updates payload."""
    assert todo_actions.update_todo(agent_state) == {
        "success": False,
        "error": "Provide todo_id or 'updates' list to update.",
    }


def test_update_todo_bulk_and_single_partial_errors(agent_state: SimpleNamespace) -> None:
    """Update handles mixed success/error results and optional errors field."""
    created = todo_actions.create_todo(agent_state, todos=["A", "B"])
    todo_ids = [item["todo_id"] for item in created["created"]]

    partial = todo_actions.update_todo(
        agent_state,
        updates=[
            {"todo_id": todo_ids[0], "status": "done"},
            {"todo_id": "missing", "status": "done"},
        ],
    )
    assert partial["success"] is False
    assert partial["updated"] == [todo_ids[0]]
    assert partial["updated_count"] == 1
    assert partial["errors"] == [
        {"todo_id": "missing", "error": "Todo with ID 'missing' not found"}
    ]

    single = todo_actions.update_todo(
        agent_state,
        todo_id=todo_ids[1],
        title="  Renamed  ",
        description=" text ",
        priority="low",
        status="in_progress",
    )
    assert single["success"] is True
    assert single["updated"] == [todo_ids[1]]
    assert "errors" not in single
    updated_todo = next(todo for todo in single["todos"] if todo["todo_id"] == todo_ids[1])
    assert updated_todo["title"] == "Renamed"
    assert updated_todo["description"] == "text"
    assert updated_todo["priority"] == "low"
    assert updated_todo["status"] == "in_progress"


def test_update_todo_exception_branch(agent_state: SimpleNamespace) -> None:
    """Update catches normalization errors and returns failure payload."""
    result = todo_actions.update_todo(agent_state, updates="{bad")
    assert result["success"] is False
    assert "Updates must be valid JSON" in result["error"]


@pytest.mark.parametrize(
    ("func", "ids_key", "success_key", "missing_msg"),
    [
        (
            todo_actions.mark_todo_done,
            "todo_ids",
            "marked_done",
            "Provide todo_id or todo_ids to mark as done.",
        ),
        (
            todo_actions.mark_todo_pending,
            "todo_ids",
            "marked_pending",
            "Provide todo_id or todo_ids to mark as pending.",
        ),
        (
            todo_actions.delete_todo,
            "todo_ids",
            "deleted",
            "Provide todo_id or todo_ids to delete.",
        ),
    ],
)
def test_mark_pending_delete_success_and_partial_errors(
    func,
    ids_key: str,
    success_key: str,
    missing_msg: str,
    agent_state: SimpleNamespace,
) -> None:
    """Mark/delete actions handle required IDs, success path, and partial errors."""
    no_ids = func(agent_state)
    assert no_ids == {"success": False, "error": missing_msg}

    created = todo_actions.create_todo(agent_state, todos=["A", "B"])
    todo_ids = [item["todo_id"] for item in created["created"]]

    success = func(agent_state, **{ids_key: todo_ids})
    assert success["success"] is True
    assert success[success_key] == todo_ids
    assert success["marked_count" if success_key.startswith("marked") else "deleted_count"] == 2
    assert "errors" not in success

    partial = func(agent_state, **{ids_key: [todo_ids[0], "missing"]})
    assert partial["success"] is False
    if success_key == "deleted":
        assert partial[success_key] == []
        assert partial["errors"] == [
            {"todo_id": todo_ids[0], "error": f"Todo with ID '{todo_ids[0]}' not found"},
            {"todo_id": "missing", "error": "Todo with ID 'missing' not found"},
        ]
    else:
        assert partial[success_key] == [todo_ids[0]]
        assert partial["errors"] == [
            {"todo_id": "missing", "error": "Todo with ID 'missing' not found"}
        ]


@pytest.mark.parametrize(
    "func", [todo_actions.mark_todo_done, todo_actions.mark_todo_pending, todo_actions.delete_todo]
)
def test_mark_pending_delete_exception_branch(
    func,
    monkeypatch: pytest.MonkeyPatch,
    agent_state: SimpleNamespace,
) -> None:
    """Mark/delete actions catch normalization errors."""
    monkeypatch.setattr(
        todo_actions,
        "_normalize_todo_ids",
        lambda _raw: (_ for _ in ()).throw(TypeError("bad ids")),
    )
    result = func(agent_state, todo_ids=["x"])
    assert result == {"success": False, "error": "bad ids"}


@pytest.mark.parametrize(
    ("func", "result_key"),
    [
        (todo_actions.mark_todo_done, "marked_done"),
        (todo_actions.mark_todo_pending, "marked_pending"),
        (todo_actions.delete_todo, "deleted"),
    ],
)
def test_mark_pending_delete_accept_single_todo_id(
    func,
    result_key: str,
    agent_state: SimpleNamespace,
) -> None:
    """Mark/delete actions support single todo_id argument paths."""
    created = todo_actions.create_todo(agent_state, title="only")
    todo_id = created["created"][0]["todo_id"]

    result = func(agent_state, todo_id=todo_id)
    assert result["success"] is True
    assert result[result_key] == [todo_id]
