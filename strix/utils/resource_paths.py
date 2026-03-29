"""Utility for resolving paths to bundled Strix resources.

This module provides a helper function to resolve resource paths whether
running in a standard Python environment or from a PyInstaller bundle.
"""

import sys
from pathlib import Path


def get_strix_resource_path(*parts: str) -> Path:
    """Get the absolute path to a Strix resource.

    This function handles both standard Python execution where the resource
    is relative to this file, and PyInstaller execution where the resource
    is located in sys._MEIPASS.

    Args:
        *parts: Path components to join (e.g., 'templates', 'agent.json').

    Returns:
        Path: The resolved absolute path to the resource.
    """
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        base = Path(frozen_base) / "strix"
        if base.exists():
            return base.joinpath(*parts)

    base = Path(__file__).resolve().parent.parent
    return base.joinpath(*parts)
