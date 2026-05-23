"""Tests for PromptLoader — custom_dir fallback behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from mindmesh.prompts import PromptLoader


@pytest.fixture
def custom_dir(tmp_path: Path) -> Path:
    d = tmp_path / "custom_prompts"
    d.mkdir()
    return d


# --- built-in templates ---


def test_load_builtin_review() -> None:
    loader = PromptLoader()
    messages = loader.load(
        "review", focus_areas=["bugs"], context="x", scope_description="git_diff",
    )
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[1].role == "user"


def test_load_missing_template_raises() -> None:
    loader = PromptLoader()
    with pytest.raises(FileNotFoundError, match="nonexistent.md"):
        loader.load("nonexistent")


# --- custom_dir override ---


def test_custom_dir_overrides_builtin(custom_dir: Path) -> None:
    (custom_dir / "review.md").write_text(
        "---SYSTEM---\nCustom system\n---USER---\nCustom user"
    )
    loader = PromptLoader(custom_dir=custom_dir)
    messages = loader.load("review")
    assert "Custom system" in messages[0].content
    assert "Custom user" in messages[1].content


def test_custom_dir_fallback_to_builtin(custom_dir: Path) -> None:
    loader = PromptLoader(custom_dir=custom_dir)
    messages = loader.load(
        "review", focus_areas=["bugs"], context="x", scope_description="git_diff",
    )
    assert len(messages) == 2
    assert "Custom" not in messages[0].content


def test_custom_dir_new_template(custom_dir: Path) -> None:
    (custom_dir / "my_custom.md").write_text(
        "---SYSTEM---\nYou are custom.\n---USER---\n{{ question }}"
    )
    loader = PromptLoader(custom_dir=custom_dir)
    messages = loader.load("my_custom", question="Hello?")
    assert "custom" in messages[0].content
    assert "Hello?" in messages[1].content


def test_custom_dir_none_uses_builtin() -> None:
    loader = PromptLoader(custom_dir=None)
    messages = loader.load(
        "ask", question="test", context_mode="none", context="",
    )
    assert len(messages) == 2


# --- jinja2 rendering ---


def test_template_variables_rendered(custom_dir: Path) -> None:
    (custom_dir / "test_tpl.md").write_text(
        "---SYSTEM---\nHello {{ name }}\n---USER---\n{{ query }}"
    )
    loader = PromptLoader(custom_dir=custom_dir)
    messages = loader.load("test_tpl", name="World", query="Q?")
    assert "World" in messages[0].content
    assert "Q?" in messages[1].content


def test_no_user_section_returns_empty_user() -> None:
    custom = Path(__file__).parent / "_test_no_user"
    custom.mkdir(exist_ok=True)
    try:
        (custom / "sys_only.md").write_text("---SYSTEM---\nSystem only content")
        ldr = PromptLoader(custom_dir=custom)
        messages = ldr.load("sys_only")
        assert messages[0].content == "System only content"
        assert messages[1].content == ""
    finally:
        (custom / "sys_only.md").unlink()
        custom.rmdir()
