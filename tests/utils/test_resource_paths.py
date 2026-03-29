import sys
from pathlib import Path

from strix.utils.resource_paths import get_strix_resource_path


def test_get_resource_path_standard():
    """Test path resolution in standard Python environment."""
    path = get_strix_resource_path("test", "file.txt")
    expected = Path(__file__).resolve().parent.parent.parent / "strix" / "test" / "file.txt"
    assert path == expected


def test_get_resource_path_frozen_exists(tmp_path, monkeypatch):
    """Test path resolution in PyInstaller with existing resource dir."""
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    strix_dir = tmp_path / "strix"
    strix_dir.mkdir()

    path = get_strix_resource_path("test", "file.txt")
    assert path == strix_dir / "test" / "file.txt"


def test_get_resource_path_frozen_not_exists(tmp_path, monkeypatch):
    """Test path resolution in PyInstaller when resource dir is missing."""
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    # Do not create tmp_path / "strix"

    path = get_strix_resource_path("test", "file.txt")
    expected = Path(__file__).resolve().parent.parent.parent / "strix" / "test" / "file.txt"
    assert path == expected
