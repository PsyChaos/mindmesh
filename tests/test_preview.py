"""Tests for preview_context tool and dry_run mode."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindmesh.config import (
    EndpointConfig,
    LimitsConfig,
    MindMeshConfig,
    PermissionsConfig,
    PrivacyConfig,
    ProviderConfig,
    ReviewConfig,
)
from mindmesh.context.collector import FileContext
from mindmesh.tools.preview import _preview_context_impl  # pyright: ignore[reportPrivateUsage]
from mindmesh.tools.review import _run_review  # pyright: ignore[reportPrivateUsage]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    disabled: list[str] | None = None,
    permissions: PermissionsConfig | None = None,
    block_files: list[str] | None = None,
) -> MindMeshConfig:
    return MindMeshConfig(
        providers={"openai": ProviderConfig()},
        disabled=disabled or [],
        endpoints={
            "ep1": EndpointConfig(provider="openai", model="gpt-4o", timeout_seconds=30),
        },
        review=ReviewConfig(default_endpoints=["ep1"]),
        privacy=PrivacyConfig(block_files=block_files or [], block_dirs=[]),
        limits=LimitsConfig(),
        permissions=permissions or PermissionsConfig(),
    )


def _make_file(
    path: str = "src/main.py",
    content: str = "def foo(): pass\n",
    language: str = "python",
) -> FileContext:
    return FileContext(path=path, content=content, language=language, scope_type="diff")


def _make_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.name = "openai"
    return adapter


# ---------------------------------------------------------------------------
# preview_context returns correct structure
# ---------------------------------------------------------------------------


async def test_preview_returns_required_keys() -> None:
    config = _make_config()
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[_make_file()])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _preview_context_impl("git_diff", ["ep1"], config)

    assert result["scope"] == "git_diff"
    assert "endpoints_requested" in result
    assert "endpoints_valid" in result
    assert "endpoints_blocked" in result
    assert "context_files" in result
    assert "files_filtered" in result
    assert "secrets_redacted" in result
    assert "total_context_kb" in result
    assert "limit_warnings" in result
    assert "permission_warnings" in result


async def test_preview_valid_endpoint_in_endpoints_valid() -> None:
    config = _make_config()
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _preview_context_impl("git_diff", ["ep1"], config)

    assert "ep1" in result["endpoints_valid"]
    assert result["endpoints_blocked"] == []


# ---------------------------------------------------------------------------
# Blocked endpoint in report
# ---------------------------------------------------------------------------


async def test_preview_disabled_provider_in_endpoints_blocked() -> None:
    config = _make_config(disabled=["openai"])
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _preview_context_impl("git_diff", ["ep1"], config)

    assert result["endpoints_valid"] == []
    assert len(result["endpoints_blocked"]) == 1
    blocked = result["endpoints_blocked"][0]
    assert blocked["endpoint"] == "ep1"
    assert "error_code" in blocked
    assert "reason" in blocked


async def test_preview_missing_endpoint_in_endpoints_blocked() -> None:
    config = _make_config()

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[])
        mock_cc_cls.return_value = mock_cc
        mock_resolver_cls.return_value = MagicMock()

        result = await _preview_context_impl("git_diff", ["nonexistent"], config)

    assert len(result["endpoints_blocked"]) == 1
    assert result["endpoints_blocked"][0]["endpoint"] == "nonexistent"
    assert result["endpoints_blocked"][0]["error_code"] == "ENDPOINT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Filtered files in report
# ---------------------------------------------------------------------------


async def test_preview_policy_blocked_files_in_files_filtered() -> None:
    config = _make_config(block_files=[".env"])
    adapter = _make_adapter()

    env_file = FileContext(
        path=".env", content="SECRET=abc\n", language="text", scope_type="file"
    )
    normal_file = _make_file()

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[env_file, normal_file])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _preview_context_impl("git_diff", ["ep1"], config)

    assert ".env" in result["files_filtered"]["by_policy"]
    assert "src/main.py" not in result["files_filtered"]["by_policy"]


async def test_preview_files_filtered_has_all_categories() -> None:
    config = _make_config()
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _preview_context_impl("git_diff", ["ep1"], config)

    ff = result["files_filtered"]
    assert "by_policy" in ff
    assert "by_binary" in ff
    assert "by_size" in ff
    assert "by_generated" in ff
    assert "by_total_limit" in ff


# ---------------------------------------------------------------------------
# Secret count in report
# ---------------------------------------------------------------------------


async def test_preview_secrets_redacted_count() -> None:
    config = _make_config()
    adapter = _make_adapter()

    secret_file = _make_file(
        content='password = "hunter2"\ntoken = "sk-' + "a" * 25 + '"'
    )

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[secret_file])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _preview_context_impl("git_diff", ["ep1"], config)

    assert result["secrets_redacted"] >= 2


async def test_preview_no_secrets_returns_zero() -> None:
    config = _make_config()
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[_make_file()])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _preview_context_impl("git_diff", ["ep1"], config)

    assert result["secrets_redacted"] == 0


# ---------------------------------------------------------------------------
# KB size in report
# ---------------------------------------------------------------------------


async def test_preview_kb_size_correct() -> None:
    config = _make_config()
    adapter = _make_adapter()

    # 10 lines of 99 chars each = 1000 bytes ≈ 0.977 KB; avg line len 99 avoids minified check
    content = ("x" * 99 + "\n") * 10
    file1 = _make_file(content=content)

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[file1])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _preview_context_impl("git_diff", ["ep1"], config)

    assert result["total_context_kb"] == pytest.approx(0.977, abs=0.05)  # pyright: ignore[reportUnknownMemberType]


async def test_preview_context_files_have_required_fields() -> None:
    config = _make_config()
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[_make_file()])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _preview_context_impl("git_diff", ["ep1"], config)

    assert len(result["context_files"]) == 1
    cf = result["context_files"][0]
    assert cf["path"] == "src/main.py"
    assert cf["language"] == "python"
    assert "size_kb" in cf


# ---------------------------------------------------------------------------
# dry_run=True in review_code returns preview format
# ---------------------------------------------------------------------------


async def test_dry_run_true_returns_preview_format() -> None:
    config = _make_config()
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[_make_file()])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _run_review(config, "git_diff", ["ep1"], None, dry_run=True)

    assert "scope" in result
    assert "endpoints_valid" in result
    assert "endpoints_blocked" in result
    assert "context_files" in result
    assert "files_filtered" in result
    assert "secrets_redacted" in result
    assert "total_context_kb" in result
    # Review-specific keys must NOT be present
    assert "findings" not in result
    assert "summary" not in result


async def test_dry_run_false_returns_review_format() -> None:
    config = _make_config()
    adapter = _make_adapter()
    adapter.send = AsyncMock(return_value="[]")

    with (
        patch("mindmesh.tools.review.GitContext"),
        patch("mindmesh.tools.review.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.review.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[_make_file()])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _run_review(config, "git_diff", ["ep1"], None, dry_run=False)

    assert "summary" in result
    assert "findings" in result
    assert "scope" not in result


async def test_dry_run_uses_default_endpoints_when_none_given() -> None:
    config = _make_config()
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.preview.GitContext"),
        patch("mindmesh.tools.preview.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.preview.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        # endpoints=None — should fall back to config.review.default_endpoints = ["ep1"]
        result = await _run_review(config, "git_diff", None, None, dry_run=True)

    assert result["endpoints_requested"] == ["ep1"]
