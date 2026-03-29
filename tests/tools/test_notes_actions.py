from unittest.mock import patch

import pytest

from strix.tools.notes.notes_actions import (
    _notes_storage,
    create_note,
    delete_note,
    list_notes,
    update_note,
)


@pytest.fixture(autouse=True)
def clean_storage():
    """Clear the notes storage before each test."""
    _notes_storage.clear()
    yield
    _notes_storage.clear()


def test_create_note_success():
    result = create_note(
        title="Test Note",
        content="This is a test note.",
        category="general",
        tags=["test"],
    )
    assert result["success"] is True
    assert "note_id" in result
    assert result["note_id"] is not None
    assert result["message"] == "Note 'Test Note' created successfully"

    note_id = result["note_id"]
    assert note_id in _notes_storage
    stored_note = _notes_storage[note_id]
    assert stored_note["title"] == "Test Note"
    assert stored_note["content"] == "This is a test note."
    assert stored_note["category"] == "general"
    assert stored_note["tags"] == ["test"]


def test_create_note_empty_title():
    result = create_note(title="", content="content")
    assert result["success"] is False
    assert result["error"] == "Title cannot be empty"


def test_create_note_empty_content():
    result = create_note(title="title", content="   ")
    assert result["success"] is False
    assert result["error"] == "Content cannot be empty"


def test_create_note_invalid_category():
    result = create_note(title="title", content="content", category="invalid_cat")
    assert result["success"] is False
    assert "Invalid category" in result["error"]


@patch("strix.tools.notes.notes_actions.uuid.uuid4", side_effect=ValueError("UUID error"))
def test_create_note_exception(mock_uuid):
    result = create_note(title="title", content="content")
    assert result["success"] is False
    assert "Failed to create note: UUID error" in result["error"]


def test_list_notes_success():
    create_note("Note 1", "Content 1", tags=["t1"])
    create_note("Note 2", "Content 2", category="findings", tags=["t2"])

    # List all
    result = list_notes()
    assert result["success"] is True
    assert result["total_count"] == 2

    # Filter by category
    result = list_notes(category="findings")
    assert result["total_count"] == 1
    assert result["notes"][0]["title"] == "Note 2"

    # Filter by tags
    result = list_notes(tags=["t1"])
    assert result["total_count"] == 1
    assert result["notes"][0]["title"] == "Note 1"

    # Filter by search
    result = list_notes(search="Content 2")
    assert result["total_count"] == 1
    assert result["notes"][0]["title"] == "Note 2"


@patch("strix.tools.notes.notes_actions._filter_notes", side_effect=TypeError("Filter error"))
def test_list_notes_exception(mock_filter):
    result = list_notes()
    assert result["success"] is False
    assert "Failed to list notes: Filter error" in result["error"]
    assert result["notes"] == []
    assert result["total_count"] == 0


def test_update_note_success():
    res = create_note("Old Title", "Old Content")
    note_id = res["note_id"]

    update_res = update_note(
        note_id,
        title="New Title",
        content="New Content",
        tags=["new_tag"],
    )
    assert update_res["success"] is True
    assert update_res["message"] == "Note 'New Title' updated successfully"

    stored_note = _notes_storage[note_id]
    assert stored_note["title"] == "New Title"
    assert stored_note["content"] == "New Content"
    assert stored_note["tags"] == ["new_tag"]


def test_update_note_not_found():
    result = update_note("invalid_id", title="New Title")
    assert result["success"] is False
    assert "not found" in result["error"]


def test_update_note_empty_title():
    res = create_note("Old Title", "Old Content")
    note_id = res["note_id"]

    result = update_note(note_id, title="   ")
    assert result["success"] is False
    assert result["error"] == "Title cannot be empty"


def test_update_note_empty_content():
    res = create_note("Old Title", "Old Content")
    note_id = res["note_id"]

    result = update_note(note_id, content="")
    assert result["success"] is False
    assert result["error"] == "Content cannot be empty"


def test_update_note_exception():
    res = create_note("Title", "Content")
    note_id = res["note_id"]

    with patch("strix.tools.notes.notes_actions.datetime") as mock_datetime:
        mock_datetime.now.side_effect = TypeError("Datetime error")
        result = update_note(note_id, title="New")

    assert result["success"] is False
    assert "Failed to update note: Datetime error" in result["error"]


def test_delete_note_success():
    res = create_note("To Delete", "Content")
    note_id = res["note_id"]

    del_res = delete_note(note_id)
    assert del_res["success"] is True
    assert del_res["message"] == "Note 'To Delete' deleted successfully"
    assert note_id not in _notes_storage


def test_delete_note_not_found():
    result = delete_note("invalid_id")
    assert result["success"] is False
    assert "not found" in result["error"]


@patch("strix.tools.notes.notes_actions._notes_storage")
def test_delete_note_exception(mock_storage):
    # Setup mock to raise error on del
    class MockStorage(dict):
        def __delitem__(self, key):
            raise ValueError("Delete error")

    mock_dict = MockStorage()
    mock_dict["test_id"] = {"title": "Test"}

    with patch("strix.tools.notes.notes_actions._notes_storage", mock_dict):
        result = delete_note("test_id")
        assert result["success"] is False
        assert "Failed to delete note: Delete error" in result["error"]
