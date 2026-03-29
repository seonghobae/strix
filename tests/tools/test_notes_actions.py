from unittest.mock import patch

import pytest

from strix.tools.notes.notes_actions import (
    _filter_notes,
    _notes_storage,
    create_note,
    delete_note,
    list_notes,
    update_note,
)


@pytest.fixture(autouse=True)
def clear_notes_storage():
    """Clear the notes storage before each test."""
    _notes_storage.clear()
    yield
    _notes_storage.clear()


def test_filter_notes_empty():
    """Test filtering when storage is empty."""
    assert _filter_notes() == []


def test_filter_notes_by_category():
    """Test filtering notes by category."""
    _notes_storage["1"] = {
        "category": "general",
        "title": "t1",
        "content": "c1",
        "created_at": "2023-01-01",
    }
    _notes_storage["2"] = {
        "category": "findings",
        "title": "t2",
        "content": "c2",
        "created_at": "2023-01-02",
    }

    results = _filter_notes(category="general")
    assert len(results) == 1
    assert results[0]["note_id"] == "1"


def test_filter_notes_by_tags():
    """Test filtering notes by tags."""
    _notes_storage["1"] = {
        "tags": ["tag1", "tag2"],
        "title": "t1",
        "content": "c1",
        "created_at": "2023-01-01",
    }
    _notes_storage["2"] = {
        "tags": ["tag3"],
        "title": "t2",
        "content": "c2",
        "created_at": "2023-01-02",
    }

    results = _filter_notes(tags=["tag2"])
    assert len(results) == 1
    assert results[0]["note_id"] == "1"


def test_filter_notes_by_search_query():
    """Test filtering notes by search query."""
    _notes_storage["1"] = {
        "title": "Hello World",
        "content": "Just a test",
        "created_at": "2023-01-01",
    }
    _notes_storage["2"] = {
        "title": "Something else",
        "content": "World is big",
        "created_at": "2023-01-02",
    }
    _notes_storage["3"] = {
        "title": "Nothing here",
        "content": "No match",
        "created_at": "2023-01-03",
    }

    results = _filter_notes(search_query="world")
    assert len(results) == 2
    # Sorts by created_at descending
    assert results[0]["note_id"] == "2"
    assert results[1]["note_id"] == "1"


def test_create_note_success():
    """Test successful creation of a note."""
    res = create_note(title="Test", content="This is a test", category="findings", tags=["test"])
    assert res["success"] is True
    assert "note_id" in res

    note_id = res["note_id"]
    assert note_id in _notes_storage
    note = _notes_storage[note_id]
    assert note["title"] == "Test"
    assert note["content"] == "This is a test"
    assert note["category"] == "findings"
    assert note["tags"] == ["test"]


def test_create_note_empty_title():
    """Test creation fails with empty title."""
    res = create_note(title="   ", content="content")
    assert res["success"] is False
    assert "Title cannot be empty" in res["error"]


def test_create_note_empty_content():
    """Test creation fails with empty content."""
    res = create_note(title="title", content="")
    assert res["success"] is False
    assert "Content cannot be empty" in res["error"]


def test_create_note_invalid_category():
    """Test creation fails with invalid category."""
    res = create_note(title="title", content="content", category="invalid_cat")
    assert res["success"] is False
    assert "Invalid category" in res["error"]


def test_create_note_exception():
    """Test creation handles exceptions."""
    with patch("strix.tools.notes.notes_actions.uuid.uuid4", side_effect=ValueError("UUID error")):
        res = create_note(title="title", content="content")
        assert res["success"] is False
        assert "UUID error" in res["error"]


def test_list_notes_success():
    """Test listing notes successfully."""
    create_note(title="Test 1", content="Content 1")
    create_note(title="Test 2", content="Content 2")

    res = list_notes()
    assert res["success"] is True
    assert res["total_count"] == 2
    assert len(res["notes"]) == 2


def test_list_notes_exception():
    """Test listing notes handles exceptions."""
    with patch(
        "strix.tools.notes.notes_actions._filter_notes", side_effect=TypeError("Filter error")
    ):
        res = list_notes()
        assert res["success"] is False
        assert "Filter error" in res["error"]


def test_update_note_success():
    """Test updating a note successfully."""
    res1 = create_note(title="Old Title", content="Old Content")
    note_id = res1["note_id"]

    res2 = update_note(note_id, title="New Title", content="New Content", tags=["new"])
    assert res2["success"] is True

    note = _notes_storage[note_id]
    assert note["title"] == "New Title"
    assert note["content"] == "New Content"
    assert note["tags"] == ["new"]


def test_update_note_not_found():
    """Test updating a non-existent note."""
    res = update_note("nonexistent", title="title")
    assert res["success"] is False
    assert "not found" in res["error"]


def test_update_note_empty_title():
    """Test updating note fails with empty title."""
    res1 = create_note(title="Title", content="Content")
    res2 = update_note(res1["note_id"], title="   ")
    assert res2["success"] is False
    assert "Title cannot be empty" in res2["error"]


def test_update_note_empty_content():
    """Test updating note fails with empty content."""
    res1 = create_note(title="Title", content="Content")
    res2 = update_note(res1["note_id"], content="   ")
    assert res2["success"] is False
    assert "Content cannot be empty" in res2["error"]


def test_update_note_exception():
    """Test updating note handles exceptions."""
    res1 = create_note(title="Title", content="Content")
    with patch("strix.tools.notes.notes_actions.datetime") as mock_dt:
        mock_dt.now.side_effect = TypeError("Datetime error")
        res2 = update_note(res1["note_id"], title="New")
        assert res2["success"] is False
        assert "Datetime error" in res2["error"]


def test_delete_note_success():
    """Test deleting a note successfully."""
    res1 = create_note(title="Title", content="Content")
    note_id = res1["note_id"]

    assert note_id in _notes_storage
    res2 = delete_note(note_id)
    assert res2["success"] is True
    assert note_id not in _notes_storage


def test_delete_note_not_found():
    """Test deleting a non-existent note."""
    res = delete_note("nonexistent")
    assert res["success"] is False
    assert "not found" in res["error"]


def test_delete_note_exception():
    """Test deleting note handles exceptions."""
    res1 = create_note(title="Title", content="Content")

    # Trigger TypeError on delete
    bad_dict = {res1["note_id"]: None}
    with patch("strix.tools.notes.notes_actions._notes_storage", bad_dict):
        res2 = delete_note(res1["note_id"])
        assert res2["success"] is False
        assert "Failed to delete note:" in res2["error"]
