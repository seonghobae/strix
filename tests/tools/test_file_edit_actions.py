"""Tests for the file_edit tools actions."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Mock openhands_aci modules before importing
mock_openhands_aci = MagicMock()
mock_shell = MagicMock()
mock_openhands_aci.utils = MagicMock()
mock_openhands_aci.utils.shell = mock_shell

sys.modules["openhands_aci"] = mock_openhands_aci
sys.modules["openhands_aci.utils"] = mock_openhands_aci.utils
sys.modules["openhands_aci.utils.shell"] = mock_shell

from strix.tools.file_edit.file_edit_actions import (  # noqa: E402
    _parse_file_editor_output,
    list_files,
    search_files,
    str_replace_editor,
)


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset the mock objects before each test."""
    mock_openhands_aci.reset_mock()
    mock_shell.reset_mock()
    mock_openhands_aci.file_editor.reset_mock()
    mock_shell.run_shell_cmd.reset_mock()


def test_parse_file_editor_output_valid_json() -> None:
    """Test parsing valid JSON inside ACI output tags."""
    json_data = {"output": "success", "error": None}
    output = f"<oh_aci_output_123>\n{json.dumps(json_data)}\n</oh_aci_output_123>"
    result = _parse_file_editor_output(output)
    assert result == json_data


def test_parse_file_editor_output_no_match() -> None:
    """Test parsing when no ACI output tags are found."""
    output = "Just some random text"
    result = _parse_file_editor_output(output)
    assert result == {"output": output, "error": None}


def test_parse_file_editor_output_invalid_json() -> None:
    """Test parsing when tags are present but JSON is invalid."""
    output = "<oh_aci_output_123>\nInvalid JSON\n</oh_aci_output_123>"
    result = _parse_file_editor_output(output)
    assert result == {"output": output, "error": None}


def test_str_replace_editor_success() -> None:
    """Test successful string replacement using the file editor."""
    json_data = {"output": "File updated", "error": None}
    mock_openhands_aci.file_editor.return_value = (
        f"<oh_aci_output_1>\n{json.dumps(json_data)}\n</oh_aci_output_1>"
    )

    result = str_replace_editor(command="replace", path="/tmp/test.txt", old_str="a", new_str="b")
    assert result == {"content": "File updated"}
    mock_openhands_aci.file_editor.assert_called_once_with(
        command="replace",
        path="/tmp/test.txt",
        file_text=None,
        view_range=None,
        old_str="a",
        new_str="b",
        insert_line=None,
    )


def test_str_replace_editor_relative_path() -> None:
    """Test string replacement with a relative path resolving to /workspace."""
    json_data = {"output": "File updated", "error": None}
    mock_openhands_aci.file_editor.return_value = (
        f"<oh_aci_output_1>\n{json.dumps(json_data)}\n</oh_aci_output_1>"
    )

    str_replace_editor(command="replace", path="test.txt", old_str="a", new_str="b")
    mock_openhands_aci.file_editor.assert_called_once()
    assert mock_openhands_aci.file_editor.call_args[1]["path"] == str(Path("/workspace/test.txt"))


def test_str_replace_editor_with_error_in_output() -> None:
    """Test string replacement when output contains an error."""
    json_data = {"output": "", "error": "File not found"}
    mock_openhands_aci.file_editor.return_value = (
        f"<oh_aci_output_1>\n{json.dumps(json_data)}\n</oh_aci_output_1>"
    )

    result = str_replace_editor(command="view", path="/tmp/test.txt")
    assert result == {"error": "File not found"}


def test_str_replace_editor_exception() -> None:
    """Test string replacement when an exception is raised."""
    mock_openhands_aci.file_editor.side_effect = ValueError("Mocked error")

    result = str_replace_editor(command="view", path="/tmp/test.txt")
    assert result == {"error": "Error in view operation: Mocked error"}


@patch("pathlib.Path.exists")
@patch("pathlib.Path.is_dir")
def test_list_files_success(mock_is_dir: MagicMock, mock_exists: MagicMock) -> None:
    """Test successful listing of files and directories."""
    mock_exists.return_value = True
    mock_is_dir.return_value = True
    mock_shell.run_shell_cmd.return_value = (0, "file1.txt\nfile2.txt\ndir1", "")

    with (
        patch("pathlib.Path.is_file") as mock_is_file,
        patch("pathlib.Path.is_dir", side_effect=[True, True]),
    ):
        mock_is_file.side_effect = [True, True, False]
        result = list_files(path="/tmp/dir")

    assert result["files"] == ["file1.txt", "file2.txt"]
    assert result["directories"] == ["dir1"]
    assert result["total_files"] == 2
    assert result["total_dirs"] == 1
    assert result["path"] == "/tmp/dir"
    assert result["recursive"] is False
    mock_shell.run_shell_cmd.assert_called_once_with("ls -1a '/tmp/dir'")


@patch("pathlib.Path.exists")
@patch("pathlib.Path.is_dir")
def test_list_files_recursive(mock_is_dir: MagicMock, mock_exists: MagicMock) -> None:
    """Test successful recursive listing of files and directories."""
    mock_exists.return_value = True
    mock_is_dir.return_value = True
    mock_shell.run_shell_cmd.return_value = (0, "/tmp/dir/file1.txt\n/tmp/dir/dir1", "")

    with (
        patch("pathlib.Path.is_file") as mock_is_file,
        patch("pathlib.Path.is_dir", side_effect=[True, True]),
    ):
        mock_is_file.side_effect = [True, False]
        result = list_files(path="/tmp/dir", recursive=True)

    assert result["files"] == ["/tmp/dir/file1.txt"]
    assert result["directories"] == ["/tmp/dir/dir1"]
    mock_shell.run_shell_cmd.assert_called_once_with(
        "find '/tmp/dir' -type f -o -type d | head -500"
    )


@patch("pathlib.Path.exists")
def test_list_files_not_found(mock_exists: MagicMock) -> None:
    """Test listing a directory that does not exist."""
    mock_exists.return_value = False
    result = list_files(path="/tmp/nonexistent")
    assert result == {"error": "Directory not found: /tmp/nonexistent"}


@patch("pathlib.Path.exists")
@patch("pathlib.Path.is_dir")
def test_list_files_not_a_dir(mock_is_dir: MagicMock, mock_exists: MagicMock) -> None:
    """Test listing a path that is not a directory."""
    mock_exists.return_value = True
    mock_is_dir.return_value = False
    result = list_files(path="/tmp/file.txt")
    assert result == {"error": "Path is not a directory: /tmp/file.txt"}


@patch("pathlib.Path.exists")
@patch("pathlib.Path.is_dir")
def test_list_files_shell_error(mock_is_dir: MagicMock, mock_exists: MagicMock) -> None:
    """Test listing files when the shell command fails."""
    mock_exists.return_value = True
    mock_is_dir.return_value = True
    mock_shell.run_shell_cmd.return_value = (1, "", "Permission denied")

    result = list_files(path="/tmp/dir")
    assert result == {"error": "Error listing directory: Permission denied"}


@patch("pathlib.Path.exists")
def test_list_files_exception(mock_exists: MagicMock) -> None:
    """Test listing files when an exception is raised."""
    mock_exists.side_effect = OSError("Mocked error")
    result = list_files(path="/tmp/dir")
    assert result == {"error": "Error listing directory: Mocked error"}


def test_list_files_relative_path() -> None:
    """Test list_files with a relative path resolving to /workspace."""
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False
        result = list_files(path="dir")

        expected_path = str(Path("/workspace/dir"))
        assert result == {"error": f"Directory not found: {expected_path}"}


@patch("pathlib.Path.exists")
def test_search_files_success(mock_exists: MagicMock) -> None:
    """Test successful file search."""
    mock_exists.return_value = True
    mock_shell.run_shell_cmd.return_value = (0, "match found", "")

    result = search_files(path="/tmp/dir", regex="pattern")
    assert result == {"output": "match found"}
    mock_shell.run_shell_cmd.assert_called_once_with(
        "rg --line-number --glob '*' 'pattern' '/tmp/dir'"
    )


@patch("pathlib.Path.exists")
def test_search_files_no_matches(mock_exists: MagicMock) -> None:
    """Test file search with no matches (exit code 1)."""
    mock_exists.return_value = True
    mock_shell.run_shell_cmd.return_value = (1, "", "")

    result = search_files(path="/tmp/dir", regex="pattern")
    assert result == {"output": "No matches found"}


@patch("pathlib.Path.exists")
def test_search_files_shell_error(mock_exists: MagicMock) -> None:
    """Test file search when the shell command fails (exit code > 1)."""
    mock_exists.return_value = True
    mock_shell.run_shell_cmd.return_value = (2, "", "Invalid regex")

    result = search_files(path="/tmp/dir", regex="pattern")
    assert result == {"error": "Error searching files: Invalid regex"}


@patch("pathlib.Path.exists")
def test_search_files_not_found(mock_exists: MagicMock) -> None:
    """Test search files in a directory that does not exist."""
    mock_exists.return_value = False
    result = search_files(path="/tmp/nonexistent", regex="pattern")
    assert result == {"error": "Directory not found: /tmp/nonexistent"}


@patch("pathlib.Path.exists")
def test_search_files_exception(mock_exists: MagicMock) -> None:
    """Test search files when an exception is raised."""
    mock_exists.side_effect = ValueError("Mocked error")
    result = search_files(path="/tmp/dir", regex="pattern")
    assert result == {"error": "Error searching files: Mocked error"}


def test_search_files_relative_path() -> None:
    """Test search_files with a relative path resolving to /workspace."""
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False
        result = search_files(path="dir", regex="pattern")

        expected_path = str(Path("/workspace/dir"))
        assert result == {"error": f"Directory not found: {expected_path}"}
