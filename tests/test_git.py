from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mindmesh.context.git import GitContext, GitError


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(path: Path) -> None:
    git("init", cwd=path)
    git("config", "user.email", "test@example.com", cwd=path)
    git("config", "user.name", "Test", cwd=path)


def initial_commit(path: Path, filename: str = "file.txt", content: str = "hello\n") -> None:
    (path / filename).write_text(content)
    git("add", filename, cwd=path)
    git("commit", "-m", "init", cwd=path)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    make_repo(tmp_path)
    initial_commit(tmp_path)
    return tmp_path


async def test_diff_head_with_changes(repo: Path) -> None:
    (repo / "file.txt").write_text("changed\n")
    ctx = GitContext(cwd=repo)
    result = await ctx.diff_head()
    assert "changed" in result


async def test_diff_head_no_changes(repo: Path) -> None:
    ctx = GitContext(cwd=repo)
    result = await ctx.diff_head()
    assert result == ""


async def test_diff_staged(repo: Path) -> None:
    (repo / "file.txt").write_text("staged change\n")
    git("add", "file.txt", cwd=repo)
    ctx = GitContext(cwd=repo)
    result = await ctx.diff_staged()
    assert "staged change" in result


async def test_diff_branch(repo: Path) -> None:
    git("checkout", "-b", "feature", cwd=repo)
    (repo / "new.txt").write_text("feature content\n")
    git("add", "new.txt", cwd=repo)
    git("commit", "-m", "feature", cwd=repo)
    ctx = GitContext(cwd=repo)
    # The initial branch name may be 'master' or 'main' depending on git config
    branches_out = subprocess.run(
        ["git", "branch", "--list"], cwd=repo, capture_output=True, text=True
    ).stdout
    base = "master" if "master" in branches_out else "main"
    result = await ctx.diff_branch(base)
    assert "feature content" in result


async def test_smart_diff_uses_head_first(repo: Path) -> None:
    (repo / "file.txt").write_text("smart diff content\n")
    ctx = GitContext(cwd=repo)
    result = await ctx.smart_diff()
    assert "smart diff content" in result


async def test_smart_diff_falls_back_to_branch(repo: Path) -> None:
    # No working tree changes; create a new commit on a feature branch
    git("checkout", "-b", "feat", cwd=repo)
    (repo / "extra.txt").write_text("branch only\n")
    git("add", "extra.txt", cwd=repo)
    git("commit", "-m", "feat commit", cwd=repo)
    ctx = GitContext(cwd=repo)
    branches_out = subprocess.run(
        ["git", "branch", "--list"], cwd=repo, capture_output=True, text=True
    ).stdout
    base = "master" if "master" in branches_out else "main"
    result = await ctx.smart_diff(base_branch=base)
    assert "branch only" in result


async def test_detect_base_branch_configured(repo: Path) -> None:
    ctx = GitContext(cwd=repo)
    result = await ctx.detect_base_branch(configured="develop")
    assert result == "develop"


async def test_detect_base_branch_detects_main(repo: Path) -> None:
    # Rename the branch to 'main'
    git("branch", "-m", "main", cwd=repo)
    ctx = GitContext(cwd=repo)
    result = await ctx.detect_base_branch()
    assert result == "main"


async def test_detect_base_branch_detects_master(repo: Path) -> None:
    git("branch", "-m", "master", cwd=repo)
    ctx = GitContext(cwd=repo)
    result = await ctx.detect_base_branch()
    assert result == "master"


async def test_list_files(repo: Path) -> None:
    ctx = GitContext(cwd=repo)
    files = await ctx.list_files(".")
    assert "file.txt" in files


async def test_git_error_outside_repo(tmp_path: Path) -> None:
    ctx = GitContext(cwd=tmp_path)
    with pytest.raises(GitError):
        await ctx.diff_head()
