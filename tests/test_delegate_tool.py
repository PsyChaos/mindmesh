"""Tests for delegate_task tool."""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
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
from mindmesh.tools.delegate import delegate_task

_VALID_JSON = json.dumps([{
    "severity": "high",
    "category": "architecture",
    "title": "Phase 1: Setup",
    "explanation": "Initial setup step",
    "confidence": 0.9,
    "file": None,
    "line": None,
}])

_FAKE_FILE = FileContext(
    path="src/main.py",
    content="def foo(): pass\n",
    language="python",
    scope_type="diff",
)


def _make_config(
    default_endpoints: list[str] | None = None,
    two_endpoints: bool = False,
    allow_external_patch: bool = False,
) -> MindMeshConfig:
    providers: dict[str, ProviderConfig] = {"openai": ProviderConfig()}
    endpoints: dict[str, EndpointConfig] = {
        "ep1": EndpointConfig(
            provider="openai", model="gpt-4o", timeout_seconds=30,
        ),
    }
    if two_endpoints:
        providers["gemini"] = ProviderConfig()
        endpoints["ep2"] = EndpointConfig(
            provider="gemini", model="gemini-2.0-flash", timeout_seconds=30,
        )
    if default_endpoints is None:
        default_endpoints = list(endpoints.keys())
    return MindMeshConfig(
        providers=providers,
        disabled=[],
        endpoints=endpoints,
        review=ReviewConfig(default_endpoints=default_endpoints),
        privacy=PrivacyConfig(block_files=[], block_dirs=[]),
        limits=LimitsConfig(),
        permissions=PermissionsConfig(
            allow_external_patch=allow_external_patch,
        ),
    )


def _make_adapter(send_return: str = _VALID_JSON) -> MagicMock:
    adapter = MagicMock()
    adapter.name = "openai"
    adapter.send = AsyncMock(return_value=send_return)
    return adapter


@contextmanager
def _delegate_patches(
    adapter: MagicMock | None = None,
) -> Generator[MagicMock, None, None]:
    _adapter = adapter or _make_adapter()
    with (
        patch("mindmesh.tools.review.GitContext"),
        patch("mindmesh.tools.review.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.review.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[_FAKE_FILE])
        mock_cc_cls.return_value = mock_cc

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (
            _adapter, "gpt-4o", {"timeout_seconds": 30},
        )
        mock_resolver_cls.return_value = mock_resolver

        yield _adapter


def _set_config(config: MindMeshConfig | None) -> None:
    import mindmesh.tools.delegate as mod
    mod._config = config  # pyright: ignore[reportPrivateUsage]


# --- invalid mode ---


@pytest.mark.asyncio
async def test_invalid_mode_returns_error() -> None:
    _set_config(_make_config())
    try:
        result = await delegate_task(task="plan", mode="invalid_mode")
        assert "Invalid mode" in result["summary"]
        assert result["metadata"]["endpoints_called"] == 0
    finally:
        _set_config(None)


# --- patch policy ---


@pytest.mark.asyncio
async def test_allow_patch_blocked_by_policy() -> None:
    _set_config(_make_config(allow_external_patch=False))
    try:
        result = await delegate_task(
            task="fix this", mode="patch_suggestion", allow_patch=True,
        )
        assert "not allowed" in result["summary"]
    finally:
        _set_config(None)


@pytest.mark.asyncio
async def test_allow_patch_permitted() -> None:
    _set_config(_make_config(allow_external_patch=True))
    try:
        with _delegate_patches():
            result = await delegate_task(
                task="fix this", mode="patch_suggestion", allow_patch=True,
            )
        assert result["metadata"]["endpoints_called"] >= 1
    finally:
        _set_config(None)


# --- planning mode uses all endpoints ---


@pytest.mark.asyncio
async def test_planning_mode_uses_all_default_endpoints() -> None:
    config = _make_config(two_endpoints=True)
    _set_config(config)
    try:
        with _delegate_patches() as adapter:
            await delegate_task(task="plan auth", mode="planning")
        assert adapter.send.call_count == 2
    finally:
        _set_config(None)


# --- advisory mode uses single endpoint ---


@pytest.mark.asyncio
async def test_advisory_mode_uses_single_endpoint() -> None:
    config = _make_config(two_endpoints=True)
    _set_config(config)
    try:
        with _delegate_patches() as adapter:
            await delegate_task(task="analyze", mode="advisory")
        assert adapter.send.call_count == 1
    finally:
        _set_config(None)


# --- dry_run ---


@pytest.mark.asyncio
async def test_dry_run_returns_preview() -> None:
    _set_config(_make_config())
    try:
        with (
            _delegate_patches(),
            patch("mindmesh.tools.preview.EndpointResolver") as mock_prev_resolver,
            patch("mindmesh.tools.preview.GitContext"),
            patch("mindmesh.tools.preview.ContextCollector") as mock_prev_cc,
        ):
            mock_prev_cc_inst = MagicMock()
            mock_prev_cc_inst.collect = AsyncMock(return_value=[_FAKE_FILE])
            mock_prev_cc.return_value = mock_prev_cc_inst

            mock_resolver = MagicMock()
            mock_resolver.resolve.return_value = (
                _make_adapter(), "gpt-4o", {"timeout_seconds": 30},
            )
            mock_prev_resolver.return_value = mock_resolver

            result = await delegate_task(task="plan", dry_run=True)
        assert "findings" not in result
        assert "context_files" in result or "endpoints_valid" in result
    finally:
        _set_config(None)


# --- explicit endpoint override ---


@pytest.mark.asyncio
async def test_explicit_endpoint_overrides_default() -> None:
    config = _make_config(two_endpoints=True)
    _set_config(config)
    try:
        resolved: list[str] = []

        with (
            patch("mindmesh.tools.review.GitContext"),
            patch("mindmesh.tools.review.ContextCollector") as mock_cc_cls,
            patch("mindmesh.tools.review.EndpointResolver") as mock_resolver_cls,
        ):
            mock_cc = MagicMock()
            mock_cc.collect = AsyncMock(return_value=[_FAKE_FILE])
            mock_cc_cls.return_value = mock_cc

            adapter = _make_adapter()
            mock_resolver = MagicMock()

            def _resolve(ep_name: str):
                resolved.append(ep_name)
                return adapter, "gpt-4o", {"timeout_seconds": 30}

            mock_resolver.resolve.side_effect = _resolve
            mock_resolver_cls.return_value = mock_resolver

            await delegate_task(task="analyze", endpoint="ep2")

        assert resolved == ["ep2"]
    finally:
        _set_config(None)
