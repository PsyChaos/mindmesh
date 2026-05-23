from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindmesh.config import MindMeshConfig
from mindmesh.context.collector import (
    ContextCollector,
    FileContext,
    detect_language,
    format_context,
)
from mindmesh.context.git import GitContext

SAMPLE_DIFF = """\
diff --git a/src/auth.py b/src/auth.py
index 1234567..abcdefg 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,6 +10,10 @@ def login(user):
     pass
+
+def logout(user):
+    pass
"""


def _make_git(cwd: str | None = None) -> GitContext:
    git = MagicMock(spec=GitContext)
    git.cwd = cwd
    return git


def _make_config(**project_kwargs: object) -> MindMeshConfig:
    # provide a dummy provider so load_config validation passes
    return MindMeshConfig.model_validate(
        {
            "project": project_kwargs,
            "providers": {"openai": {"api_key_env": "OPENAI_API_KEY"}},
            "endpoints": {"default": {"provider": "openai", "model": "gpt-4o"}},
        }
    )


# ---------------------------------------------------------------------------
# Diff scopes
# ---------------------------------------------------------------------------


async def test_collect_git_diff_returns_file_contexts() -> None:
    git = _make_git()
    git.smart_diff = AsyncMock(return_value=SAMPLE_DIFF)
    collector = ContextCollector(git, _make_config())

    result = await collector.collect("git_diff")

    assert len(result) == 1
    fc = result[0]
    assert fc.path == "src/auth.py"
    assert fc.scope_type == "diff"
    assert fc.language == "python"
    assert fc.start_line == 10


async def test_collect_git_diff_empty_returns_empty_list() -> None:
    git = _make_git()
    git.smart_diff = AsyncMock(return_value="")
    collector = ContextCollector(git, _make_config())

    result = await collector.collect("git_diff")

    assert result == []


async def test_collect_staged_parses_diff() -> None:
    git = _make_git()
    git.diff_staged = AsyncMock(return_value=SAMPLE_DIFF)
    collector = ContextCollector(git, _make_config())

    result = await collector.collect("staged")

    assert len(result) == 1
    assert result[0].scope_type == "diff"
    assert result[0].path == "src/auth.py"


async def test_collect_branch_uses_configured_base() -> None:
    git = _make_git()
    git.diff_branch = AsyncMock(return_value=SAMPLE_DIFF)
    collector = ContextCollector(git, _make_config(base_branch="main"))

    result = await collector.collect("branch")

    git.diff_branch.assert_called_once_with("main")
    assert len(result) == 1


async def test_collect_branch_detects_base_when_not_configured() -> None:
    git = _make_git()
    git.diff_branch = AsyncMock(return_value=SAMPLE_DIFF)
    git.detect_base_branch = AsyncMock(return_value="master")
    collector = ContextCollector(git, _make_config())

    await collector.collect("branch")

    git.detect_base_branch.assert_called_once()
    git.diff_branch.assert_called_once_with("master")


# ---------------------------------------------------------------------------
# Path scope — file
# ---------------------------------------------------------------------------


async def test_collect_file_path_returns_content(tmp_path: Path) -> None:
    file = tmp_path / "hello.py"
    file.write_text("print('hello')")

    git = _make_git(cwd=str(tmp_path))
    collector = ContextCollector(git, _make_config())

    result = await collector.collect("hello.py")

    assert len(result) == 1
    fc = result[0]
    assert fc.path == "hello.py"
    assert fc.content == "print('hello')"
    assert fc.scope_type == "file"
    assert fc.language == "python"
    assert fc.start_line is None
    assert fc.end_line is None


# ---------------------------------------------------------------------------
# Path scope — directory
# ---------------------------------------------------------------------------


async def test_collect_directory_gathers_all_files(tmp_path: Path) -> None:
    subdir = tmp_path / "src"
    subdir.mkdir()
    (subdir / "a.py").write_text("x = 1")
    (subdir / "b.ts").write_text("const y = 2")

    git = _make_git(cwd=str(tmp_path))
    git.list_files = AsyncMock(return_value=["src/a.py", "src/b.ts"])
    collector = ContextCollector(git, _make_config())

    result = await collector.collect("src")

    assert len(result) == 2
    paths = {fc.path for fc in result}
    assert paths == {"src/a.py", "src/b.ts"}
    langs = {fc.language for fc in result}
    assert langs == {"python", "typescript"}
    for fc in result:
        assert fc.scope_type == "file"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


async def test_collect_nonexistent_path_raises(tmp_path: Path) -> None:
    git = _make_git(cwd=str(tmp_path))
    collector = ContextCollector(git, _make_config())

    with pytest.raises(FileNotFoundError, match="does not exist"):
        await collector.collect("nonexistent_file.py")


# ---------------------------------------------------------------------------
# format_context
# ---------------------------------------------------------------------------


def test_format_context_diff_scope_shows_modified() -> None:
    files = [
        FileContext(
            path="src/foo.py",
            content="def foo(): pass",
            language="python",
            scope_type="diff",
            start_line=5,
            end_line=10,
        )
    ]
    result = format_context(files)

    assert "## File: src/foo.py (modified)" in result
    assert "Language: python" in result
    assert "Lines: 5-10" in result
    assert "def foo(): pass" in result


def test_format_context_file_scope_shows_file_label() -> None:
    files = [
        FileContext(path="README.md", content="# Hello", language="markdown", scope_type="file")
    ]
    result = format_context(files)

    assert "## File: README.md (file)" in result
    assert "Language: markdown" in result
    assert "Lines:" not in result


def test_format_context_no_lines_when_none() -> None:
    files = [
        FileContext(path="a.py", content="pass", language="python", scope_type="diff")
    ]
    result = format_context(files)

    assert "Lines:" not in result


def test_format_context_multiple_files_joined() -> None:
    files = [
        FileContext(path="a.py", content="x=1", language="python", scope_type="file"),
        FileContext(path="b.ts", content="y=2", language="typescript", scope_type="file"),
    ]
    result = format_context(files)

    assert "## File: a.py" in result
    assert "## File: b.ts" in result


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


def test_detect_language_known_extensions() -> None:
    cases = {
        "foo.py": "python",
        "bar.ts": "typescript",
        "baz.js": "javascript",
        "main.go": "go",
        "lib.rs": "rust",
        "App.java": "java",
        "script.rb": "ruby",
        "index.php": "php",
        "config.yml": "yaml",
        "config.yaml": "yaml",
        "data.json": "json",
        "README.md": "markdown",
        "page.html": "html",
        "style.css": "css",
    }
    for path, expected in cases.items():
        assert detect_language(path) == expected, f"{path} → expected {expected}"


def test_detect_language_unknown_returns_text() -> None:
    assert detect_language("file.xyz") == "text"
    assert detect_language("Makefile") == "text"
    assert detect_language("noextension") == "text"
