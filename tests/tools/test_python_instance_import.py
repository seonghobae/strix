"""Regression tests for Python instance import behavior."""

import builtins
import importlib

import pytest


def test_python_instance_module_import_does_not_require_ipython(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure importing python_instance does not eagerly require IPython."""

    original_import = builtins.__import__

    def _import_blocker(name: str, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Raise ModuleNotFoundError for any IPython import attempt."""
        if name.startswith("IPython"):
            raise ModuleNotFoundError("No module named 'IPython'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import_blocker)

    module = importlib.import_module("strix.tools.python.python_instance")
    reloaded_module = importlib.reload(module)

    assert hasattr(reloaded_module, "PythonInstance")
