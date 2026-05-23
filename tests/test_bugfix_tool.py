"""Tests for bug_investigate tool — no real API calls, no git operations."""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
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
from mindmesh.schemas import Message
from mindmesh.tools.bugfix import bug_investigate

_VALID_JSON = json.dumps([{
    "severity": "high",
    "category": "bug",
    "title": "Null dereference in handler",
    "explanation": "obj can be None before access",
    "confidence": 0.9,
    "file": "handler.py",
    "line": 17,
}])

_FAKE_FILE = FileContext(
    path="src/handler.py",
    content="def handle(obj): return obj.value\n",
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
def _bugfix_patches(
    adapter: MagicMock | None = None,
    collected_files: list[FileContext] | None = None,
) -> Generator[tuple[MagicMock, MagicMock], None, None]:
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


# --- full pipeline flow ---

async def test_bug_investigate_returns_result_shape() -> None:
    config = _make_config()
    with (
        _bugfix_patches(),
        patch("mindmesh.tools.bugfix._config", config),
    ):
        result = await bug_investigate(issue="App crashes on startup")
    assert "findings" in result
    assert "endpoint_errors" in result
    assert "metadata" in result


async def test_bug_investigate_context_pipeline_runs() -> None:
    config = _make_config()
    adapter = _make_adapter()
    with (
        _bugfix_patches(adapter=adapter),
        patch("mindmesh.tools.bugfix._config", config),
    ):
        await bug_investigate(issue="NullPointerException in session handler")
    assert adapter.send.call_count == 1


# --- template name ---

async def test_bug_investigate_template_used() -> None:
    config = _make_config()
    with (
        _bugfix_patches(),
        patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls,
        patch("mindmesh.tools.bugfix._config", config),
    ):
        mock_loader = MagicMock()
        from mindmesh.schemas import Message
        mock_loader.load.return_value = [
            Message(role="system", content="sys"),
            Message(role="user", content="usr"),
        ]
        mock_loader_cls.return_value = mock_loader
        await bug_investigate(issue="App crash")

    call_args = mock_loader.load.call_args
    assert call_args.args[0] == "bug_investigate"


# --- issue parameter ---

async def test_issue_parameter_passed_to_prompt() -> None:
    config = _make_config()
    with (
        _bugfix_patches(),
        patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls,
        patch("mindmesh.tools.bugfix._config", config),
    ):
        mock_loader = MagicMock()
        from mindmesh.schemas import Message
        mock_loader.load.return_value = [
            Message(role="system", content="sys"),
            Message(role="user", content="usr"),
        ]
        mock_loader_cls.return_value = mock_loader
        await bug_investigate(issue="Database connection timeout")

    call_kwargs = mock_loader.load.call_args.kwargs
    assert call_kwargs["issue"] == "Database connection timeout"


# --- logs parameter ---

async def test_logs_passed_to_prompt_when_provided() -> None:
    config = _make_config()
    sample_logs = "ERROR: connection refused at line 42"
    with (
        _bugfix_patches(),
        patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls,
        patch("mindmesh.tools.bugfix._config", config),
    ):
        mock_loader = MagicMock()
        from mindmesh.schemas import Message
        mock_loader.load.return_value = [
            Message(role="system", content="sys"),
            Message(role="user", content="usr"),
        ]
        mock_loader_cls.return_value = mock_loader
        await bug_investigate(issue="Connection refused", logs=sample_logs)

    call_kwargs = mock_loader.load.call_args.kwargs
    assert call_kwargs["logs"] == sample_logs


async def test_logs_is_none_when_not_provided() -> None:
    config = _make_config()
    with (
        _bugfix_patches(),
        patch("mindmesh.tools.review.PromptLoader") as mock_loader_cls,
        patch("mindmesh.tools.bugfix._config", config),
    ):
        mock_loader = MagicMock()
        from mindmesh.schemas import Message
        mock_loader.load.return_value = [
            Message(role="system", content="sys"),
            Message(role="user", content="usr"),
        ]
        mock_loader_cls.return_value = mock_loader
        await bug_investigate(issue="App crash")

    call_kwargs = mock_loader.load.call_args.kwargs
    assert call_kwargs["logs"] is None


async def test_logs_absent_from_rendered_prompt_when_not_provided() -> None:
    """Real PromptLoader renders template — 'Logs:' section must be absent."""
    config = _make_config()
    captured_messages: list[Message] = []

    adapter = _make_adapter()
    original_send = adapter.send

    async def capture_send(messages: list[Message], model: str, cfg: dict[str, Any]) -> str:
        captured_messages.extend(messages)
        return await original_send(messages, model, cfg)

    adapter.send = capture_send

    with (
        _bugfix_patches(adapter=adapter),
        patch("mindmesh.tools.bugfix._config", config),
    ):
        await bug_investigate(issue="Memory leak in worker thread")

    user_content = next(m.content for m in captured_messages if m.role == "user")
    assert "Logs:" not in user_content


async def test_logs_present_in_rendered_prompt_when_provided() -> None:
    """Real PromptLoader renders template — 'Logs:' section must appear."""
    config = _make_config()
    captured_messages: list[Message] = []
    sample_logs = "WARN: heap size exceeded"

    adapter = _make_adapter()
    original_send = adapter.send

    async def capture_send(messages: list[Message], model: str, cfg: dict[str, Any]) -> str:
        captured_messages.extend(messages)
        return await original_send(messages, model, cfg)

    adapter.send = capture_send

    with (
        _bugfix_patches(adapter=adapter),
        patch("mindmesh.tools.bugfix._config", config),
    ):
        await bug_investigate(issue="Memory leak", logs=sample_logs)

    user_content = next(m.content for m in captured_messages if m.role == "user")
    assert "Logs:" in user_content
    assert sample_logs in user_content


# --- disabled endpoint ---

async def test_disabled_endpoint_goes_to_endpoint_errors() -> None:
    config = _make_config(disabled=["openai"])
    with (
        _bugfix_patches(),
        patch("mindmesh.tools.bugfix._config", config),
    ):
        result = await bug_investigate(issue="Crash on init")
    assert len(result["endpoint_errors"]) == 1
    assert result["endpoint_errors"][0]["error_code"] == "PROVIDER_DISABLED"
