"""Tests for OpenAIAdapter — no real API calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest

from mindmesh.config import ProviderConfig
from mindmesh.errors import (
    InvalidApiKeyError,
    ModelUnavailableError,
    ProviderTimeoutError,
    RateLimitError,
)
from mindmesh.providers.openai import OpenAIAdapter
from mindmesh.schemas import Message

_FAKE_REQUEST = httpx.Request("GET", "https://api.openai.com")


def _fake_response(status: int) -> httpx.Response:
    return httpx.Response(status, request=_FAKE_REQUEST)


def _make_adapter(monkeypatch: pytest.MonkeyPatch) -> tuple[OpenAIAdapter, MagicMock]:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    with patch("mindmesh.providers.openai.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        config = ProviderConfig(api_key_env="OPENAI_API_KEY")
        adapter = OpenAIAdapter(config)
    return adapter, mock_client


def _mock_completion(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


# --- message format ---

@pytest.mark.asyncio
async def test_messages_converted_to_openai_format(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion("ok"))

    messages = [
        Message(role="system", content="You are a reviewer."),
        Message(role="user", content="Check this diff."),
    ]
    await adapter.send(messages, "gpt-4o", {})

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["messages"] == [
        {"role": "system", "content": "You are a reviewer."},
        {"role": "user", "content": "Check this diff."},
    ]


@pytest.mark.asyncio
async def test_message_order_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion("ok"))

    messages = [
        Message(role="system", content="system msg"),
        Message(role="user", content="user msg"),
    ]
    await adapter.send(messages, "gpt-4o", {})

    sent = mock_client.chat.completions.create.call_args.kwargs["messages"]
    assert sent[0]["role"] == "system"
    assert sent[1]["role"] == "user"


@pytest.mark.asyncio
async def test_model_passed_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion("ok"))

    await adapter.send([Message(role="user", content="hi")], "gpt-4o-mini", {})

    assert mock_client.chat.completions.create.call_args.kwargs["model"] == "gpt-4o-mini"


# --- response content ---

@pytest.mark.asyncio
async def test_response_content_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion("findings here"))

    result = await adapter.send([Message(role="user", content="hi")], "gpt-4o", {})
    assert result == "findings here"


@pytest.mark.asyncio
async def test_empty_response_returns_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion(""))

    result = await adapter.send([Message(role="user", content="hi")], "gpt-4o", {})
    assert result == ""


@pytest.mark.asyncio
async def test_none_content_returns_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion(None))  # type: ignore[arg-type]

    result = await adapter.send([Message(role="user", content="hi")], "gpt-4o", {})
    assert result == ""


# --- config passthrough ---

@pytest.mark.asyncio
async def test_temperature_passed_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion("ok"))

    await adapter.send([Message(role="user", content="hi")], "gpt-4o", {"temperature": 0.2})

    assert mock_client.chat.completions.create.call_args.kwargs["temperature"] == 0.2


@pytest.mark.asyncio
async def test_temperature_absent_when_not_in_config(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(return_value=_mock_completion("ok"))

    await adapter.send([Message(role="user", content="hi")], "gpt-4o", {})

    assert "temperature" not in mock_client.chat.completions.create.call_args.kwargs


# --- error mapping ---

@pytest.mark.asyncio
async def test_timeout_error_raises_provider_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(
        side_effect=openai.APITimeoutError(request=_FAKE_REQUEST)
    )

    with pytest.raises(ProviderTimeoutError):
        await adapter.send([Message(role="user", content="hi")], "gpt-4o", {})


@pytest.mark.asyncio
async def test_rate_limit_error_raises_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(
        side_effect=openai.RateLimitError(
            message="rate limited", response=_fake_response(429), body=None
        )
    )

    with pytest.raises(RateLimitError):
        await adapter.send([Message(role="user", content="hi")], "gpt-4o", {})


@pytest.mark.asyncio
async def test_auth_error_raises_invalid_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(
        side_effect=openai.AuthenticationError(
            message="invalid key", response=_fake_response(401), body=None
        )
    )

    with pytest.raises(InvalidApiKeyError):
        await adapter.send([Message(role="user", content="hi")], "gpt-4o", {})


@pytest.mark.asyncio
async def test_not_found_error_raises_model_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.chat.completions.create = AsyncMock(
        side_effect=openai.NotFoundError(
            message="model not found", response=_fake_response(404), body=None
        )
    )

    with pytest.raises(ModelUnavailableError):
        await adapter.send([Message(role="user", content="hi")], "gpt-4o", {})
