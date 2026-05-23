"""Tests for review_code tool — no real API calls, no git operations."""

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
from mindmesh.tools.review import _run_review  # pyright: ignore[reportPrivateUsage]

_VALID_JSON = json.dumps([{
    "severity": "high",
    "category": "bug",
    "title": "Null dereference",
    "explanation": "Can be null here",
    "confidence": 0.9,
    "file": "foo.py",
    "line": 10,
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
    providers: list[str] | None = None,
    extra_endpoints: dict[str, EndpointConfig] | None = None,
) -> MindMeshConfig:
    prov_list = providers or ["openai"]
    eps = {"ep1": EndpointConfig(provider="openai", model="gpt-4o", timeout_seconds=30)}
    if extra_endpoints:
        eps.update(extra_endpoints)
    return MindMeshConfig(
        providers={p: ProviderConfig() for p in prov_list},
        disabled=disabled or [],
        endpoints=eps,
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
def _review_patches(
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


# --- successful review ---

async def test_successful_review_returns_findings() -> None:
    config = _make_config()
    with _review_patches():
        result = await _run_review(config, "git_diff", None, None)
    assert "findings" in result
    assert len(result["findings"]) == 1
    assert result["findings"][0]["title"] == "Null dereference"


async def test_single_endpoint_succeeds_metadata() -> None:
    config = _make_config()
    with _review_patches():
        result = await _run_review(config, "git_diff", None, None)
    assert result["metadata"]["endpoints_succeeded"] == 1
    assert result["metadata"]["endpoints_called"] == 1


# --- disabled endpoint ---

async def test_disabled_endpoint_goes_to_endpoint_errors() -> None:
    config = _make_config(disabled=["openai"])
    with _review_patches():
        result = await _run_review(config, "git_diff", None, None)
    assert len(result["endpoint_errors"]) == 1
    assert result["endpoint_errors"][0]["error_code"] == "PROVIDER_DISABLED"


async def test_all_endpoints_disabled_returns_only_errors() -> None:
    config = _make_config(disabled=["openai"])
    with _review_patches():
        result = await _run_review(config, "git_diff", None, None)
    assert result["findings"] == []
    assert len(result["endpoint_errors"]) >= 1


# --- timeout ---

async def test_timeout_produces_endpoint_error() -> None:
    import asyncio

    adapter = _make_adapter()
    adapter.send = AsyncMock(side_effect=asyncio.TimeoutError)

    config = _make_config()
    with _review_patches(adapter=adapter):
        result = await _run_review(config, "git_diff", None, None)

    assert len(result["endpoint_errors"]) == 1
    assert result["endpoint_errors"][0]["error_code"] == "PROVIDER_TIMEOUT"
    assert result["findings"] == []


# --- JSON parse retry ---

async def test_parse_retry_on_bad_json_then_success() -> None:
    good_json = _VALID_JSON
    # First call: bad JSON; second call (retry): good JSON
    adapter = _make_adapter()
    adapter.send = AsyncMock(side_effect=["not json at all", good_json])

    config = _make_config()
    with _review_patches(adapter=adapter):
        result = await _run_review(config, "git_diff", None, None)

    assert len(result["findings"]) == 1
    assert result["findings"][0]["title"] == "Null dereference"


async def test_parse_retry_both_fail_produces_parse_error_finding() -> None:
    adapter = _make_adapter()
    adapter.send = AsyncMock(return_value="still not json")

    config = _make_config()
    with _review_patches(adapter=adapter):
        result = await _run_review(config, "git_diff", None, None)

    assert len(result["findings"]) == 1
    assert result["findings"][0]["title"] == "Parse error"
    assert result["findings"][0]["category"] == "system"


# --- empty diff ---

async def test_empty_diff_returns_empty_findings() -> None:
    adapter = _make_adapter(send_return="[]")
    config = _make_config()
    with _review_patches(adapter=adapter, collected_files=[]):
        result = await _run_review(config, "git_diff", None, None)
    assert result["findings"] == []
    assert result["endpoint_errors"] == []


# --- default endpoints from config ---

async def test_default_endpoints_from_config_when_none_passed() -> None:
    config = _make_config(default_endpoints=["ep1"])
    with _review_patches():
        result = await _run_review(config, "git_diff", None, None)
    assert result["metadata"]["endpoints_called"] >= 1


async def test_no_endpoints_configured_returns_empty_summary() -> None:
    config = _make_config(default_endpoints=[])
    with _review_patches():
        result = await _run_review(config, "git_diff", None, None)
    assert result["findings"] == []
    assert result["metadata"]["endpoints_called"] == 0


# --- focus areas ---

async def test_focus_areas_passed_to_prompt() -> None:
    config = _make_config()
    with (
        _review_patches(),
        patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls,
    ):
            mock_loader = MagicMock()
            from mindmesh.schemas import Message
            mock_loader.load.return_value = [
                Message(role="system", content="sys"),
                Message(role="user", content="usr"),
            ]
            mock_loader_cls.return_value = mock_loader
            await _run_review(config, "git_diff", None, ["security", "performance"])

    call_kwargs = mock_loader.load.call_args.kwargs
    assert call_kwargs["focus_areas"] == ["security", "performance"]


async def test_default_focus_areas_when_none() -> None:
    config = _make_config()
    with _review_patches(), patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls:
        mock_loader = MagicMock()
        from mindmesh.schemas import Message
        mock_loader.load.return_value = [
            Message(role="system", content="sys"),
            Message(role="user", content="usr"),
        ]
        mock_loader_cls.return_value = mock_loader
        await _run_review(config, "git_diff", None, None)

    call_kwargs = mock_loader.load.call_args.kwargs
    assert "bugs" in call_kwargs["focus_areas"]
    assert "security" in call_kwargs["focus_areas"]


# --- parallel calls ---

async def test_two_endpoints_called_in_parallel() -> None:
    config = MindMeshConfig(
        providers={"openai": ProviderConfig(), "gemini": ProviderConfig()},
        disabled=[],
        endpoints={
            "ep1": EndpointConfig(provider="openai", model="gpt-4o", timeout_seconds=30),
            "ep2": EndpointConfig(provider="gemini", model="gemini-2.0-flash", timeout_seconds=30),
        },
        review=ReviewConfig(default_endpoints=["ep1", "ep2"]),
        privacy=PrivacyConfig(block_files=[], block_dirs=[]),
        limits=LimitsConfig(),
    )

    with (
        patch("mindmesh.tools.review.GitContext"),
        patch("mindmesh.tools.review.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.review.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[_FAKE_FILE])
        mock_cc_cls.return_value = mock_cc

        adapter1 = _make_adapter()
        adapter2 = _make_adapter()

        def _resolve(ep_name: str):
            if ep_name == "ep1":
                return adapter1, "gpt-4o", {"timeout_seconds": 30}
            return adapter2, "gemini-2.0-flash", {"timeout_seconds": 30}

        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = _resolve
        mock_resolver_cls.return_value = mock_resolver

        result = await _run_review(config, "git_diff", None, None)

    assert adapter1.send.call_count == 1
    assert adapter2.send.call_count == 1
    assert result["metadata"]["endpoints_succeeded"] == 2


# --- secret redaction metadata ---

async def test_redacted_secrets_count_in_metadata() -> None:
    file_with_secret = FileContext(
        path="config.py",
        content="api_key = 'sk-abcdefghijklmnopqrst1234'\n",
        language="python",
        scope_type="file",
    )
    config = _make_config()
    with _review_patches(collected_files=[file_with_secret]):
        result = await _run_review(config, "git_diff", None, None)
    assert result["metadata"]["redacted_secrets"] >= 1
