"""Tests for ask_provider tool — no real API calls, no git operations."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
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
from mindmesh.context.collector import FileContext
from mindmesh.schemas import Message
from mindmesh.tools.ask import ask_provider

_FAKE_ANSWER = "This function handles user authentication."

_FAKE_FILE = FileContext(
    path="src/main.py",
    content="def foo(): pass\n",
    language="python",
    scope_type="diff",
)


def _make_config(
    default_endpoints: list[str] | None = None,
) -> MindMeshConfig:
    return MindMeshConfig(
        providers={"openai": ProviderConfig()},
        disabled=[],
        endpoints={
            "ep1": EndpointConfig(
                provider="openai", model="gpt-4o", timeout_seconds=30,
            ),
        },
        review=ReviewConfig(
            default_endpoints=(
                default_endpoints if default_endpoints is not None else ["ep1"]
            ),
        ),
        privacy=PrivacyConfig(block_files=[], block_dirs=[]),
        limits=LimitsConfig(),
    )


def _make_adapter(send_return: str = _FAKE_ANSWER) -> MagicMock:
    adapter = MagicMock()
    adapter.name = "openai"
    adapter.send = AsyncMock(return_value=send_return)
    return adapter


@contextmanager
def _ask_patches(
    adapter: MagicMock | None = None,
    collected_files: list[FileContext] | None = None,
) -> Generator[tuple[MagicMock, MagicMock], None, None]:
    _adapter = adapter or _make_adapter()
    _files = collected_files if collected_files is not None else [_FAKE_FILE]

    with (
        patch("mindmesh.tools.ask.GitContext"),
        patch("mindmesh.tools.ask.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.ask.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=_files)
        mock_cc_cls.return_value = mock_cc

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (
            _adapter, "gpt-4o", {"timeout_seconds": 30},
        )
        mock_resolver_cls.return_value = mock_resolver

        yield _adapter, mock_cc


def _set_config(config: MindMeshConfig | None) -> None:
    import mindmesh.tools.ask as ask_mod
    ask_mod._config = config  # pyright: ignore[reportPrivateUsage]


# --- basic success ---


@pytest.mark.asyncio
async def test_ask_provider_returns_answer() -> None:
    _set_config(_make_config())
    try:
        with _ask_patches():
            result = await ask_provider(question="What does this code do?")
        assert result["answer"] == _FAKE_ANSWER
        assert result["endpoint"] == "ep1"
        assert result["provider"] == "openai"
    finally:
        _set_config(None)


@pytest.mark.asyncio
async def test_ask_uses_ask_template() -> None:
    _set_config(_make_config())
    try:
        with (
            _ask_patches(),
            patch("mindmesh.tools.ask.PromptLoader") as mock_loader_cls,
        ):
            mock_loader = MagicMock()
            mock_loader.load.return_value = [
                Message(role="system", content="sys"),
                Message(role="user", content="usr"),
            ]
            mock_loader_cls.return_value = mock_loader
            await ask_provider(question="Explain this function.")

        assert mock_loader.load.call_args.args[0] == "ask"
    finally:
        _set_config(None)


@pytest.mark.asyncio
async def test_question_passed_to_template() -> None:
    _set_config(_make_config())
    try:
        with (
            _ask_patches(),
            patch("mindmesh.tools.ask.PromptLoader") as mock_loader_cls,
        ):
            mock_loader = MagicMock()
            mock_loader.load.return_value = [
                Message(role="system", content="sys"),
                Message(role="user", content="usr"),
            ]
            mock_loader_cls.return_value = mock_loader
            await ask_provider(question="How does auth work?")

        kwargs = mock_loader.load.call_args.kwargs
        assert kwargs["question"] == "How does auth work?"
    finally:
        _set_config(None)


@pytest.mark.asyncio
async def test_context_mode_none_passes_empty_context() -> None:
    _set_config(_make_config())
    try:
        with (
            _ask_patches(),
            patch("mindmesh.tools.ask.PromptLoader") as mock_loader_cls,
        ):
            mock_loader = MagicMock()
            mock_loader.load.return_value = [
                Message(role="system", content="sys"),
                Message(role="user", content="usr"),
            ]
            mock_loader_cls.return_value = mock_loader
            await ask_provider(question="Hello?", context_mode="none")

        kwargs = mock_loader.load.call_args.kwargs
        assert kwargs["context"] == ""
    finally:
        _set_config(None)


@pytest.mark.asyncio
async def test_context_mode_passed_to_template() -> None:
    _set_config(_make_config())
    try:
        with (
            _ask_patches(),
            patch("mindmesh.tools.ask.PromptLoader") as mock_loader_cls,
        ):
            mock_loader = MagicMock()
            mock_loader.load.return_value = [
                Message(role="system", content="sys"),
                Message(role="user", content="usr"),
            ]
            mock_loader_cls.return_value = mock_loader
            await ask_provider(question="Q?", context_mode="git_diff")

        kwargs = mock_loader.load.call_args.kwargs
        assert kwargs["context_mode"] == "git_diff"
    finally:
        _set_config(None)


@pytest.mark.asyncio
async def test_default_endpoint_from_config_when_none_given() -> None:
    _set_config(_make_config(default_endpoints=["ep1"]))
    try:
        with _ask_patches() as (adapter, _):
            await ask_provider(question="What is this?")
        assert adapter.send.call_count == 1
    finally:
        _set_config(None)


@pytest.mark.asyncio
async def test_explicit_endpoint_overrides_default() -> None:
    config = MindMeshConfig(
        providers={"openai": ProviderConfig()},
        disabled=[],
        endpoints={
            "ep1": EndpointConfig(
                provider="openai", model="gpt-4o", timeout_seconds=30,
            ),
            "ep2": EndpointConfig(
                provider="openai", model="gpt-4o-mini", timeout_seconds=30,
            ),
        },
        review=ReviewConfig(default_endpoints=["ep1"]),
        privacy=PrivacyConfig(block_files=[], block_dirs=[]),
        limits=LimitsConfig(),
    )
    _set_config(config)
    try:
        with (
            patch("mindmesh.tools.ask.GitContext"),
            patch("mindmesh.tools.ask.ContextCollector") as mock_cc_cls,
            patch("mindmesh.tools.ask.EndpointResolver") as mock_resolver_cls,
        ):
            mock_cc = MagicMock()
            mock_cc.collect = AsyncMock(return_value=[])
            mock_cc_cls.return_value = mock_cc

            adapter = _make_adapter()
            mock_resolver = MagicMock()

            resolved: list[str] = []

            def _resolve(ep_name: str):
                resolved.append(ep_name)
                return adapter, "gpt-4o-mini", {"timeout_seconds": 30}

            mock_resolver.resolve.side_effect = _resolve
            mock_resolver_cls.return_value = mock_resolver

            await ask_provider(question="Q?", endpoint="ep2")

        assert resolved == ["ep2"]
    finally:
        _set_config(None)


@pytest.mark.asyncio
async def test_no_endpoint_configured_returns_error() -> None:
    _set_config(_make_config(default_endpoints=[]))
    try:
        result = await ask_provider(question="Hello?")
        assert result["error"] is not None
        assert result["answer"] is None
    finally:
        _set_config(None)


@pytest.mark.asyncio
async def test_unknown_endpoint_returns_error() -> None:
    _set_config(_make_config())
    try:
        result = await ask_provider(question="Hello?", endpoint="nonexistent")
        assert result["error"] is not None
        assert result["answer"] is None
    finally:
        _set_config(None)
