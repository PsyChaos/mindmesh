"""Tests for GeminiAdapter — no real API calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindmesh.config import ProviderConfig
from mindmesh.errors import InvalidApiKeyError, ProviderTimeoutError, RateLimitError
from mindmesh.providers.gemini import GeminiAdapter
from mindmesh.schemas import Message


def _make_adapter(monkeypatch: pytest.MonkeyPatch) -> tuple[GeminiAdapter, MagicMock]:
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    with patch("mindmesh.providers.gemini.genai.Client") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        config = ProviderConfig(api_key_env="GEMINI_API_KEY")
        adapter = GeminiAdapter(config)
    return adapter, mock_client


def _mock_response(text: str | None) -> MagicMock:
    response = MagicMock()
    response.text = text
    return response


def _client_error(code: int) -> object:
    from google.genai import errors as genai_errors

    return genai_errors.ClientError(code, {"error": {"message": f"HTTP {code}"}})


# --- message format ---


@pytest.mark.asyncio
async def test_system_message_becomes_system_instruction(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(return_value=_mock_response("ok"))

    messages = [
        Message(role="system", content="You are a code reviewer."),
        Message(role="user", content="Review this diff."),
    ]
    await adapter.send(messages, "gemini-2.0-flash", {})

    call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
    assert call_kwargs["contents"] == "Review this diff."
    assert call_kwargs["config"].system_instruction == "You are a code reviewer."


@pytest.mark.asyncio
async def test_multiple_user_messages_joined(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(return_value=_mock_response("ok"))

    messages = [
        Message(role="user", content="First part."),
        Message(role="user", content="Second part."),
    ]
    await adapter.send(messages, "gemini-2.0-flash", {})

    call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
    assert call_kwargs["contents"] == "First part.\nSecond part."


@pytest.mark.asyncio
async def test_no_system_message_passes_none_config(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(return_value=_mock_response("ok"))

    messages = [Message(role="user", content="Hello")]
    await adapter.send(messages, "gemini-2.0-flash", {})

    call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
    assert call_kwargs["config"] is None


@pytest.mark.asyncio
async def test_model_passed_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(return_value=_mock_response("ok"))

    await adapter.send([Message(role="user", content="hi")], "gemini-2.5-pro", {})

    assert mock_client.aio.models.generate_content.call_args.kwargs["model"] == "gemini-2.5-pro"


# --- response content ---


@pytest.mark.asyncio
async def test_response_text_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(
        return_value=_mock_response("findings here")
    )

    result = await adapter.send([Message(role="user", content="hi")], "gemini-2.0-flash", {})
    assert result == "findings here"


@pytest.mark.asyncio
async def test_none_response_text_returns_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(return_value=_mock_response(None))

    result = await adapter.send([Message(role="user", content="hi")], "gemini-2.0-flash", {})
    assert result == ""


# --- config passthrough ---


@pytest.mark.asyncio
async def test_temperature_passed_to_generation_config(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(return_value=_mock_response("ok"))

    await adapter.send(
        [Message(role="user", content="hi")], "gemini-2.0-flash", {"temperature": 0.4},
    )

    call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
    assert call_kwargs["config"].temperature == 0.4


@pytest.mark.asyncio
async def test_temperature_absent_when_not_in_config(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(return_value=_mock_response("ok"))

    await adapter.send([Message(role="user", content="hi")], "gemini-2.0-flash", {})

    call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
    assert call_kwargs["config"] is None


# --- error mapping ---


@pytest.mark.asyncio
async def test_timeout_raises_provider_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(side_effect=TimeoutError())

    with pytest.raises(ProviderTimeoutError, match="timed out"):
        await adapter.send([Message(role="user", content="hi")], "gemini-2.0-flash", {})


@pytest.mark.asyncio
async def test_401_raises_invalid_api_key_error(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(side_effect=_client_error(401))

    with pytest.raises(InvalidApiKeyError):
        await adapter.send([Message(role="user", content="hi")], "gemini-2.0-flash", {})


@pytest.mark.asyncio
async def test_403_raises_invalid_api_key_error(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(side_effect=_client_error(403))

    with pytest.raises(InvalidApiKeyError):
        await adapter.send([Message(role="user", content="hi")], "gemini-2.0-flash", {})


@pytest.mark.asyncio
async def test_429_raises_rate_limit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(side_effect=_client_error(429))

    with pytest.raises(RateLimitError):
        await adapter.send([Message(role="user", content="hi")], "gemini-2.0-flash", {})


@pytest.mark.asyncio
async def test_other_client_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    from google.genai import errors as genai_errors

    adapter, mock_client = _make_adapter(monkeypatch)
    mock_client.aio.models.generate_content = AsyncMock(side_effect=_client_error(400))

    with pytest.raises(genai_errors.ClientError):
        await adapter.send([Message(role="user", content="hi")], "gemini-2.0-flash", {})
