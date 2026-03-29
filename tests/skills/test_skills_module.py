"""Unit tests for ``strix.skills`` module behavior."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

import strix.skills as skills_module


@pytest.fixture
def skills_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Patch resource lookup so tests use a tmp directory."""
    resource_root = tmp_path / "resources"
    resource_root.mkdir()

    def _resource_path(*parts: str) -> Path:
        return resource_root.joinpath(*parts)

    monkeypatch.setattr(
        skills_module,
        "get_strix_resource_path",
        _resource_path,
    )
    return resource_root / "skills"


def _write_markdown(path: Path, content: str = "# skill\n") -> None:
    """Create a markdown file with UTF-8 content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_get_available_skills_returns_empty_dict_when_skills_dir_missing(
    skills_resources: Path,
) -> None:
    """Missing skills directory should return an empty map."""
    assert not skills_resources.exists()

    assert skills_module.get_available_skills() == {}


def test_get_available_skills_filters_excluded_and_sorts_stems(
    skills_resources: Path,
) -> None:
    """Only non-excluded categories with sorted markdown stems should be returned."""
    skills_resources.mkdir(parents=True)

    _write_markdown(skills_resources / "__internal" / "secret.md")
    _write_markdown(skills_resources / "scan_modes" / "scan.md")
    _write_markdown(skills_resources / "coordination" / "coord.md")
    _write_markdown(skills_resources / "net" / "zeta.md")
    _write_markdown(skills_resources / "net" / "alpha.md")
    _write_markdown(skills_resources / "data" / "beta.md")
    (skills_resources / "net" / "ignore.txt").write_text("nope", encoding="utf-8")
    (skills_resources / "empty").mkdir(parents=True)

    assert skills_module.get_available_skills() == {
        "data": ["beta"],
        "net": ["alpha", "zeta"],
    }


def test_skill_list_parsing_and_validation_paths(skills_resources: Path) -> None:
    """Cover parse/validate helpers across valid, invalid, and boundary paths."""
    skills_resources.mkdir(parents=True)
    _write_markdown(skills_resources / "alpha_cat" / "alpha.md")
    _write_markdown(skills_resources / "alpha_cat" / "beta.md")
    _write_markdown(skills_resources / "beta_cat" / "gamma.md")

    assert skills_module.get_all_skill_names() == {"alpha", "beta", "gamma"}

    validation = skills_module.validate_skill_names(["alpha", "ghost", "beta"])
    assert validation == {"valid": ["alpha", "beta"], "invalid": ["ghost"]}

    assert skills_module.parse_skill_list(None) == []
    assert skills_module.parse_skill_list("") == []
    assert skills_module.parse_skill_list(" alpha, , beta , gamma ") == ["alpha", "beta", "gamma"]

    too_many_message = skills_module.validate_requested_skills(["a", "b", "c", "d", "e", "f"])
    assert too_many_message is not None
    assert "Cannot specify more than 5 skills" in too_many_message

    assert skills_module.validate_requested_skills([]) is None

    invalid_message = skills_module.validate_requested_skills(["alpha", "ghost"])
    assert invalid_message is not None
    assert "Invalid skills: ['ghost']." in invalid_message
    assert "Available skills:" in invalid_message
    for available_name in ("alpha", "beta", "gamma"):
        assert available_name in invalid_message

    assert skills_module.validate_requested_skills(["alpha", "beta"]) is None


def test_generate_skills_description_when_no_skills_available(skills_resources: Path) -> None:
    """Description should report no skills when inventory is empty."""
    assert not skills_resources.exists()

    assert skills_module.generate_skills_description() == "No skills available"


def test_generate_skills_description_when_available_map_exists_but_names_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the defensive branch where flattened skill names are empty."""

    def _available_skills() -> dict[str, list[str]]:
        return {"net": ["alpha"]}

    def _empty_skill_names() -> set[str]:
        return set()

    monkeypatch.setattr(skills_module, "get_available_skills", _available_skills)
    monkeypatch.setattr(skills_module, "get_all_skill_names", _empty_skill_names)

    assert skills_module.generate_skills_description() == "No skills available"


def test_generate_skills_description_includes_sorted_list_and_example(
    skills_resources: Path,
) -> None:
    """Description should reflect discovered skills and include sorted examples."""
    skills_resources.mkdir(parents=True)

    _write_markdown(skills_resources / "net" / "zeta.md")
    _write_markdown(skills_resources / "net" / "alpha.md")
    _write_markdown(skills_resources / "net" / "beta.md")
    _write_markdown(skills_resources / "scan_modes" / "ignored.md")

    description = skills_module.generate_skills_description()

    assert "Available skills: alpha, beta, zeta." in description
    assert "Example: alpha, beta for specialized agent" in description


def test_get_all_categories_includes_internal_categories_and_sorted_stems(
    skills_resources: Path,
) -> None:
    """Internal categories should be included by _get_all_categories."""
    skills_resources.mkdir(parents=True)

    _write_markdown(skills_resources / "scan_modes" / "z.md")
    _write_markdown(skills_resources / "scan_modes" / "a.md")
    _write_markdown(skills_resources / "coordination" / "sync.md")
    _write_markdown(skills_resources / "regular" / "beta.md")
    _write_markdown(skills_resources / "regular" / "alpha.md")
    _write_markdown(skills_resources / "__internal" / "hidden.md")

    assert skills_module._get_all_categories() == {
        "coordination": ["sync"],
        "regular": ["alpha", "beta"],
        "scan_modes": ["a", "z"],
    }


def test_get_all_categories_returns_empty_when_skills_dir_missing(
    skills_resources: Path,
) -> None:
    """Missing skills directory should return empty categories map."""
    assert not skills_resources.exists()

    assert skills_module._get_all_categories() == {}


def test_load_skills_resolves_slash_path_and_strips_frontmatter(skills_resources: Path) -> None:
    """Slash-qualified name should resolve directly and strip YAML frontmatter."""
    skills_resources.mkdir(parents=True)

    _write_markdown(
        skills_resources / "cat" / "skill.md",
        "---\ntitle: Skill\nowner: team\n---\n\n## Skill Body\nDetails\n",
    )

    assert skills_module.load_skills(["cat/skill"]) == {
        "skill": "## Skill Body\nDetails\n",
    }


def test_load_skills_resolves_category_name_and_root_fallback_and_warns_missing(
    caplog: pytest.LogCaptureFixture,
    skills_resources: Path,
) -> None:
    """Bare name resolution should check category first, then root-level fallback."""
    skills_resources.mkdir(parents=True)

    _write_markdown(skills_resources / "web" / "httpx.md", "category content\n")
    _write_markdown(skills_resources / "root_only.md", "root content\n")

    caplog.set_level(logging.WARNING, logger="strix.skills")
    loaded = skills_module.load_skills(["httpx", "root_only", "missing"])

    assert loaded == {
        "httpx": "category content\n",
        "root_only": "root content\n",
    }
    assert "Skill not found: missing" in caplog.messages


def test_load_skills_handles_expected_read_exceptions(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    skills_resources: Path,
) -> None:
    """FileNotFoundError/OSError/ValueError should be caught and warned."""
    skills_resources.mkdir(parents=True)

    _write_markdown(skills_resources / "errors" / "file_not_found.md")
    (skills_resources / "errors" / "os_error.md").mkdir(parents=True)
    (skills_resources / "errors" / "value_error.md").write_bytes(b"\x80")

    original_read_text = Path.read_text

    def _raise_for_selected_files(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == "file_not_found.md":
            raise FileNotFoundError("missing file")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _raise_for_selected_files)

    caplog.set_level(logging.WARNING, logger="strix.skills")
    loaded = skills_module.load_skills(["file_not_found", "os_error", "value_error"])

    assert loaded == {}
    assert "Failed to load skill file_not_found: missing file" in caplog.messages
    assert any("Failed to load skill os_error:" in message for message in caplog.messages)
    assert any("Failed to load skill value_error:" in message for message in caplog.messages)
