"""Tests for git helper CLI commands (commit, pr) — no real API or git calls."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindmesh.config import (
    EndpointConfig,
    LimitsConfig,
    MindMeshConfig,
    PrivacyConfig,
    ProviderConfig,
    ReviewConfig,
)
from mindmesh.context.git import GitContext


def _make_config() -> MindMeshConfig:
    return MindMeshConfig(
        providers={"openai": ProviderConfig()},
        endpoints={
            "ep1": EndpointConfig(
                provider="openai", model="gpt-4o-mini", timeout_seconds=30,
            ),
        },
        review=ReviewConfig(default_endpoints=["ep1"]),
        privacy=PrivacyConfig(block_files=[], block_dirs=[]),
        limits=LimitsConfig(),
    )


# --- GitContext new methods ---


@pytest.mark.asyncio
async def test_log_oneline() -> None:
    git = GitContext()
    with patch.object(
        git, "_run",
        new=AsyncMock(return_value="abc123 first\ndef456 second\n"),
    ):
        result = await git.log_oneline(2)
    assert "abc123" in result
    assert "second" in result


@pytest.mark.asyncio
async def test_current_branch() -> None:
    git = GitContext()
    with patch.object(
        git, "_run", new=AsyncMock(return_value="feature/foo\n"),
    ):
        result = await git.current_branch()
    assert result == "feature/foo"


@pytest.mark.asyncio
async def test_branch_log_with_base() -> None:
    git = GitContext()
    with patch.object(
        git, "_run", new=AsyncMock(return_value="abc feat: add X\n"),
    ):
        result = await git.branch_log("main")
    assert "abc" in result


# --- commit generation ---


@pytest.mark.asyncio
async def test_commit_calls_adapter() -> None:
    from mindmesh.cli import _generate_commit

    cfg = _make_config()
    mock_git = MagicMock()
    mock_git.smart_diff = AsyncMock(return_value="diff --git a/x.py")

    adapter = MagicMock()
    adapter.send = AsyncMock(return_value="feat: add user auth")

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = (
        adapter, "gpt-4o-mini", {"timeout_seconds": 30},
    )

    with (
        patch("mindmesh.cli.load_config", return_value=cfg),
        patch("mindmesh.context.git.GitContext", return_value=mock_git),
        patch(
            "mindmesh.providers.base.EndpointResolver",
            return_value=mock_resolver,
        ),contextlib.suppress(SystemExit)
    ):
        await _generate_commit(None, as_json=False)

    adapter.send.assert_called_once()


# --- pr generation ---


@pytest.mark.asyncio
async def test_pr_calls_adapter() -> None:
    from mindmesh.cli import _generate_pr

    cfg = _make_config()
    mock_git = MagicMock()
    mock_git.current_branch = AsyncMock(return_value="feature/auth")
    mock_git.branch_log = AsyncMock(return_value="abc feat: add auth")
    mock_git.smart_diff = AsyncMock(return_value="diff --git a/x.py")

    adapter = MagicMock()
    adapter.send = AsyncMock(
        return_value="TITLE: Add auth\n\nBODY:\n## Summary",
    )

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = (
        adapter, "gpt-4o-mini", {"timeout_seconds": 30},
    )

    with (
        patch("mindmesh.cli.load_config", return_value=cfg),
        patch("mindmesh.context.git.GitContext", return_value=mock_git),
        patch(
            "mindmesh.providers.base.EndpointResolver",
            return_value=mock_resolver,
        ),contextlib.suppress(SystemExit)
    ):
        await _generate_pr(None, as_json=False)

    adapter.send.assert_called_once()
