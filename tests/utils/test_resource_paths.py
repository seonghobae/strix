import sys
from pathlib import Path

from strix.utils.resource_paths import get_strix_resource_path


def test_get_strix_resource_path_standard() -> None:
    """Test standard execution path without PyInstaller _MEIPASS."""
    # Temporarily remove _MEIPASS if it exists
    original_meipass = getattr(sys, "_MEIPASS", None)
    if hasattr(sys, "_MEIPASS"):
        del sys._MEIPASS

    try:
        result = get_strix_resource_path("config", "default.json")

        # We just verify it returns a Path and ends with the expected parts
        assert isinstance(result, Path)
        assert result.parts[-2:] == ("config", "default.json")
    finally:
        if original_meipass is not None:
            sys._MEIPASS = original_meipass  # type: ignore[attr-defined]


def test_get_strix_resource_path_frozen_exists(tmp_path: Path) -> None:
    """Test frozen execution where the _MEIPASS directory contains a 'strix' folder."""
    frozen_base = tmp_path
    strix_dir = frozen_base / "strix"
    strix_dir.mkdir()

    original_meipass = getattr(sys, "_MEIPASS", None)
    sys._MEIPASS = str(frozen_base)  # type: ignore[attr-defined]
    try:
        result = get_strix_resource_path("assets", "logo.png")
        assert result == strix_dir / "assets" / "logo.png"
    finally:
        if original_meipass is not None:
            sys._MEIPASS = original_meipass  # type: ignore[attr-defined]
        else:
            del sys._MEIPASS


def test_get_strix_resource_path_frozen_not_exists(tmp_path: Path) -> None:
    """Test frozen execution where the 'strix' folder does not exist."""
    frozen_base = tmp_path
    # strix_dir is NOT created

    original_meipass = getattr(sys, "_MEIPASS", None)
    sys._MEIPASS = str(frozen_base)  # type: ignore[attr-defined]
    try:
        result = get_strix_resource_path("assets", "logo.png")
        # Should fallback to the regular __file__ path
        assert isinstance(result, Path)
        assert result.parts[-2:] == ("assets", "logo.png")
        assert str(frozen_base) not in str(result)
    finally:
        if original_meipass is not None:
            sys._MEIPASS = original_meipass  # type: ignore[attr-defined]
        else:
            del sys._MEIPASS
