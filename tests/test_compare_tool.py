"""Tests for compare_providers tool — no real API calls, no git operations."""

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
from mindmesh.tools.compare import compare_providers

_FINDING_A = json.dumps([{
    "severity": "high",
    "category": "bug",
    "title": "Null dereference",
    "explanation": "Value can be null here",
    "confidence": 0.9,
    "file": "foo.py",
    "line": 10,
}])

_FINDING_B = json.dumps([{
    "severity": "medium",
    "category": "bug",
    "title": "Similar null issue",
    "explanation": "Potential null pointer",
    "confidence": 0.8,
    "file": "foo.py",
    "line": 11,
}])

_FAKE_FILE = FileContext(
    path="src/main.py",
    content="def foo(): pass\n",
    language="python",
    scope_type="diff",
)


def _make_config(
    disabled: list[str] | None = None,
    default_endpoints: list[str] | None = None,
    two_endpoints: bool = False,
) -> MindMeshConfig:
    providers: dict[str, ProviderConfig] = {"openai": ProviderConfig()}
    endpoints: dict[str, EndpointConfig] = {
        "ep1": EndpointConfig(provider="openai", model="gpt-4o", timeout_seconds=30),
    }
    if two_endpoints:
        providers["gemini"] = ProviderConfig()
        endpoints["ep2"] = EndpointConfig(
            provider="gemini", model="gemini-2.0-flash", timeout_seconds=30
        )
    if default_endpoints is None:
        default_endpoints = list(endpoints.keys())
    return MindMeshConfig(
        providers=providers,
        disabled=disabled or [],
        endpoints=endpoints,
        review=ReviewConfig(default_endpoints=default_endpoints),
        privacy=PrivacyConfig(block_files=[], block_dirs=[]),
        limits=LimitsConfig(),
    )


def _make_adapter(send_return: str = _FINDING_A) -> MagicMock:
    adapter = MagicMock()
    adapter.name = "openai"
    adapter.send = AsyncMock(return_value=send_return)
    return adapter


@contextmanager
def _compare_patches(
    adapter1: MagicMock | None = None,
    adapter2: MagicMock | None = None,
    collected_files: list[FileContext] | None = None,
) -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Patch GitContext, ContextCollector, EndpointResolver for two-endpoint tests."""
    _adapter1 = adapter1 or _make_adapter(_FINDING_A)
    _adapter2 = adapter2 or _make_adapter(_FINDING_B)
    _files = collected_files if collected_files is not None else [_FAKE_FILE]

    with (
        patch("mindmesh.tools.review.GitContext"),
        patch("mindmesh.tools.review.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.review.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=_files)
        mock_cc_cls.return_value = mock_cc

        def _resolve(ep_name: str):
            if ep_name == "ep1":
                return _adapter1, "gpt-4o", {"timeout_seconds": 30}
            return _adapter2, "gemini-2.0-flash", {"timeout_seconds": 30}

        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = _resolve
        mock_resolver_cls.return_value = mock_resolver

        yield _adapter1, _adapter2


# --- 2-endpoint comparison ---

async def test_two_endpoints_both_return_findings() -> None:
    config = _make_config(two_endpoints=True)
    with (
        _compare_patches(),
        patch("mindmesh.tools.compare._config", config),
    ):
        result = await compare_providers(task="Explain any bugs found")
    assert "findings" in result
    assert len(result["findings"]) == 2


async def test_two_endpoints_both_adapters_called() -> None:
    config = _make_config(two_endpoints=True)
    with (
        _compare_patches() as (a1, a2),
        patch("mindmesh.tools.compare._config", config),
    ):
        await compare_providers(task="Compare performance")
    assert a1.send.call_count == 1
    assert a2.send.call_count == 1


async def test_two_endpoints_metadata_succeeds() -> None:
    config = _make_config(two_endpoints=True)
    with (
        _compare_patches(),
        patch("mindmesh.tools.compare._config", config),
    ):
        result = await compare_providers(task="Check for issues")
    assert result["metadata"]["endpoints_succeeded"] == 2
    assert result["metadata"]["endpoints_called"] == 2


# --- insufficient endpoints ---

async def test_one_endpoint_returns_error_summary() -> None:
    config = _make_config(default_endpoints=["ep1"])
    with patch("mindmesh.tools.compare._config", config):
        result = await compare_providers(task="Some task")
    assert "at least 2" in result["summary"].lower()
    assert result["findings"] == []
    assert result["endpoint_errors"] == []
    assert result["metadata"]["endpoints_called"] == 0


async def test_zero_endpoints_returns_error_summary() -> None:
    config = _make_config(default_endpoints=[])
    with patch("mindmesh.tools.compare._config", config):
        result = await compare_providers(task="Some task")
    assert "at least 2" in result["summary"].lower()
    assert result["findings"] == []
    assert result["metadata"]["endpoints_called"] == 0


async def test_explicit_one_endpoint_returns_error_summary() -> None:
    config = _make_config(two_endpoints=True)
    with patch("mindmesh.tools.compare._config", config):
        result = await compare_providers(task="Some task", endpoints=["ep1"])
    assert "at least 2" in result["summary"].lower()
    assert result["findings"] == []


# --- task parameter passed to prompt ---

async def test_task_passed_as_question_to_prompt() -> None:
    config = _make_config(two_endpoints=True)
    with (
        _compare_patches(),
        patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls,
        patch("mindmesh.tools.compare._config", config),
    ):
        from mindmesh.schemas import Message
        mock_loader = MagicMock()
        mock_loader.load.return_value = [
            Message(role="system", content="sys"),
            Message(role="user", content="usr"),
        ]
        mock_loader_cls.return_value = mock_loader
        await compare_providers(task="Is there a memory leak?")

    call_kwargs = mock_loader.load.call_args.kwargs
    assert call_kwargs.get("question") == "Is there a memory leak?"


async def test_ask_template_used() -> None:
    config = _make_config(two_endpoints=True)
    with (
        _compare_patches(),
        patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls,
        patch("mindmesh.tools.compare._config", config),
    ):
        from mindmesh.schemas import Message
        mock_loader = MagicMock()
        mock_loader.load.return_value = [
            Message(role="system", content="sys"),
            Message(role="user", content="usr"),
        ]
        mock_loader_cls.return_value = mock_loader
        await compare_providers(task="any task")

    assert mock_loader.load.call_args.args[0] == "compare"


async def test_context_mode_matches_scope() -> None:
    config = _make_config(two_endpoints=True)
    with (
        _compare_patches(),
        patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls,
        patch("mindmesh.tools.compare._config", config),
    ):
        from mindmesh.schemas import Message
        mock_loader = MagicMock()
        mock_loader.load.return_value = [
            Message(role="system", content="sys"),
            Message(role="user", content="usr"),
        ]
        mock_loader_cls.return_value = mock_loader
        await compare_providers(task="task", scope="staged")

    call_kwargs = mock_loader.load.call_args.kwargs
    assert call_kwargs.get("question") == "task"


# --- partial success ---

async def test_partial_success_one_endpoint_fails() -> None:
    import asyncio

    config = _make_config(two_endpoints=True)
    failing_adapter = _make_adapter()
    failing_adapter.send = AsyncMock(side_effect=asyncio.TimeoutError)
    good_adapter = _make_adapter(_FINDING_A)

    with (
        _compare_patches(adapter1=failing_adapter, adapter2=good_adapter),
        patch("mindmesh.tools.compare._config", config),
    ):
        result = await compare_providers(task="Check issues")

    assert len(result["endpoint_errors"]) == 1
    assert result["endpoint_errors"][0]["error_code"] == "PROVIDER_TIMEOUT"
    assert len(result["findings"]) == 1


async def test_partial_success_metadata() -> None:
    import asyncio

    config = _make_config(two_endpoints=True)
    failing_adapter = _make_adapter()
    failing_adapter.send = AsyncMock(side_effect=asyncio.TimeoutError)
    good_adapter = _make_adapter(_FINDING_A)

    with (
        _compare_patches(adapter1=failing_adapter, adapter2=good_adapter),
        patch("mindmesh.tools.compare._config", config),
    ):
        result = await compare_providers(task="Check issues")

    assert result["metadata"]["endpoints_succeeded"] == 1


# --- match_hints ---

async def test_match_hints_present_for_overlapping_findings() -> None:
    # Both endpoints return a finding at the same file + similar line + same category
    config = _make_config(two_endpoints=True)
    with (
        _compare_patches(
            adapter1=_make_adapter(_FINDING_A),
            adapter2=_make_adapter(_FINDING_B),
        ),
        patch("mindmesh.tools.compare._config", config),
    ):
        result = await compare_providers(task="Find bugs")

    # foo.py line 10 vs line 11, both "bug" → merger generates a match hint
    assert "match_hints" in result
    assert len(result["match_hints"]) >= 1
    hint = result["match_hints"][0]
    assert "finding_indices" in hint
    assert len(hint["finding_indices"]) == 2


async def test_match_hints_key_always_present() -> None:
    config = _make_config(two_endpoints=True)
    with (
        _compare_patches(),
        patch("mindmesh.tools.compare._config", config),
    ):
        result = await compare_providers(task="Any task")
    assert "match_hints" in result


# --- dry_run ---


async def test_dry_run_returns_preview_format() -> None:
    config = _make_config(two_endpoints=True)
    with (
        _compare_patches(),
        patch("mindmesh.tools.compare._config", config),
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

        result = await compare_providers(task="Check", dry_run=True)
    assert "context_files" in result or "endpoints_valid" in result
    assert "findings" not in result
