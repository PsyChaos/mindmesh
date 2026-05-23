"""Tests for security_audit tool — no real API calls, no git operations."""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from mindmesh.config import (
    EndpointConfig,
    LimitsConfig,
    MindMeshConfig,
    PrivacyConfig,
    ProviderConfig,
    ReviewConfig,
)
from mindmesh.context.collector import FileContext
from mindmesh.tools.security import security_audit

_VALID_JSON = json.dumps([{
    "severity": "high",
    "category": "security",
    "title": "Hardcoded secret",
    "explanation": "API key exposed in source code",
    "confidence": 0.95,
    "file": "config.py",
    "line": 5,
}])

_FAKE_FILE = FileContext(
    path="src/main.py",
    content="api_key = 'sk-12345678'\n",
    language="python",
    scope_type="diff",
)


def _make_config(
    disabled: list[str] | None = None,
    default_endpoints: list[str] | None = None,
) -> MindMeshConfig:
    return MindMeshConfig(
        providers={"openai": ProviderConfig()},
        disabled=disabled or [],
        endpoints={"ep1": EndpointConfig(provider="openai", model="gpt-4o", timeout_seconds=30)},
        review=ReviewConfig(
            default_endpoints=default_endpoints if default_endpoints is not None else ["ep1"],
        ),
        privacy=PrivacyConfig(block_files=[], block_dirs=[]),
        limits=LimitsConfig(),
    )


def _make_adapter(send_return: str = _VALID_JSON) -> MagicMock:
    adapter = MagicMock()
    adapter.name = "openai"
    adapter.send = AsyncMock(return_value=send_return)
    return adapter


@contextmanager
def _security_patches(
    adapter: MagicMock | None = None,
    collected_files: list[FileContext] | None = None,
) -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Patch GitContext, ContextCollector, EndpointResolver for tests."""
    _adapter = adapter or _make_adapter()
    _files = collected_files if collected_files is not None else [_FAKE_FILE]

    with (
        patch("mindmesh.tools.review.GitContext"),
        patch("mindmesh.tools.review.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.review.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=_files)
        mock_cc_cls.return_value = mock_cc

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (_adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        yield _adapter, mock_cc


# --- successful security audit ---

async def test_security_audit_returns_findings() -> None:
    config = _make_config()
    with (
        _security_patches(),
        patch("mindmesh.tools.security._config", config),
    ):
        result = await security_audit()
    assert "findings" in result
    assert len(result["findings"]) == 1
    assert result["findings"][0]["title"] == "Hardcoded secret"


async def test_security_audit_endpoint_succeeds_metadata() -> None:
    config = _make_config()
    with (
        _security_patches(),
        patch("mindmesh.tools.security._config", config),
    ):
        result = await security_audit()
    assert result["metadata"]["endpoints_succeeded"] == 1


# --- template name verification ---

async def test_security_uses_security_template() -> None:
    config = _make_config()
    with (
        _security_patches(),
        patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls,
        patch("mindmesh.tools.security._config", config),
    ):
        mock_loader = MagicMock()
        from mindmesh.schemas import Message
        mock_loader.load.return_value = [
            Message(role="system", content="sys"),
            Message(role="user", content="usr"),
        ]
        mock_loader_cls.return_value = mock_loader
        await security_audit()

    # Verify that PromptLoader.load was called with template_name="security"
    call_args = mock_loader.load.call_args
    assert call_args.args[0] == "security"


# --- default focus areas ---

async def test_default_security_focus_areas() -> None:
    config = _make_config()
    with (
        _security_patches(),
        patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls,
        patch("mindmesh.tools.security._config", config),
    ):
        mock_loader = MagicMock()
        from mindmesh.schemas import Message
        mock_loader.load.return_value = [
            Message(role="system", content="sys"),
            Message(role="user", content="usr"),
        ]
        mock_loader_cls.return_value = mock_loader
        await security_audit()

    call_kwargs = mock_loader.load.call_args.kwargs
    focus_areas = call_kwargs["focus_areas"]
    assert "authentication" in focus_areas
    assert "authorization" in focus_areas
    assert "injection" in focus_areas
    assert "secrets" in focus_areas
    assert "ssrf" in focus_areas
    assert "path_traversal" in focus_areas


async def test_custom_focus_overrides_default() -> None:
    config = _make_config()
    with (
        _security_patches(),
        patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls,
        patch("mindmesh.tools.security._config", config),
    ):
        mock_loader = MagicMock()
        from mindmesh.schemas import Message
        mock_loader.load.return_value = [
            Message(role="system", content="sys"),
            Message(role="user", content="usr"),
        ]
        mock_loader_cls.return_value = mock_loader
        await security_audit(focus=["custom_focus"])

    call_kwargs = mock_loader.load.call_args.kwargs
    assert call_kwargs["focus_areas"] == ["custom_focus"]


# --- disabled endpoint ---

async def test_disabled_endpoint_goes_to_endpoint_errors() -> None:
    config = _make_config(disabled=["openai"])
    with (
        _security_patches(),
        patch("mindmesh.tools.security._config", config),
    ):
        result = await security_audit()
    assert len(result["endpoint_errors"]) == 1
    assert result["endpoint_errors"][0]["error_code"] == "PROVIDER_DISABLED"


# --- empty content ---

async def test_empty_diff_returns_empty_findings() -> None:
    adapter = _make_adapter(send_return="[]")
    config = _make_config()
    with (
        _security_patches(adapter=adapter, collected_files=[]),
        patch("mindmesh.tools.security._config", config),
    ):
        result = await security_audit()
    assert result["findings"] == []
    assert result["endpoint_errors"] == []
