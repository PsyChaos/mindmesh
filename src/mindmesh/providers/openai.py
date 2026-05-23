"""OpenAI provider adapter (AsyncOpenAI SDK)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any, cast

import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from mindmesh.config import ProviderConfig
from mindmesh.errors import (
    InvalidApiKeyError,
    ModelUnavailableError,
    ProviderTimeoutError,
    RateLimitError,
)
from mindmesh.providers.base import ProviderAdapter
from mindmesh.schemas import Message


class OpenAIAdapter(ProviderAdapter):
    name = "openai"

    def __init__(self, provider_config: ProviderConfig) -> None:
        api_key = ""
        if provider_config.api_key_env:
            api_key = os.environ.get(provider_config.api_key_env, "")

        kwargs: dict[str, Any] = {"api_key": api_key}
        if provider_config.base_url:
            kwargs["base_url"] = provider_config.base_url

        self._client = AsyncOpenAI(**kwargs)

    def _build_kwargs(
        self, messages: list[Message], model: str, config: dict[str, Any],
    ) -> dict[str, Any]:
        oai_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]
        call_kwargs: dict[str, Any] = {
            "model": model, "messages": oai_messages,
        }
        if "temperature" in config:
            call_kwargs["temperature"] = config["temperature"]
        if "max_tokens" in config:
            call_kwargs["max_tokens"] = config["max_tokens"]
        return call_kwargs

    async def send(
        self, messages: list[Message], model: str, config: dict[str, Any],
    ) -> str:
        call_kwargs = self._build_kwargs(messages, model, config)
        try:
            response = cast(
                ChatCompletion,
                await self._client.chat.completions.create(**call_kwargs),
            )
        except openai.APITimeoutError as exc:
            raise ProviderTimeoutError(f"OpenAI request timed out: {exc}") from exc
        except openai.RateLimitError as exc:
            raise RateLimitError(f"OpenAI rate limit exceeded: {exc}") from exc
        except openai.AuthenticationError as exc:
            raise InvalidApiKeyError(f"OpenAI authentication failed: {exc}") from exc
        except openai.NotFoundError as exc:
            raise ModelUnavailableError(f"OpenAI model not found: {exc}") from exc

        if response.usage:
            from mindmesh.providers.base import TokenUsage
            self._last_usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )
        content: str | None = response.choices[0].message.content
        return content or ""

    async def send_stream(
        self, messages: list[Message], model: str, config: dict[str, Any],
    ) -> AsyncIterator[str]:
        call_kwargs = self._build_kwargs(messages, model, config)
        call_kwargs["stream"] = True
        try:
            stream = await self._client.chat.completions.create(**call_kwargs)  # pyright: ignore[reportUnknownVariableType]
            async for chunk in stream:  # type: ignore[union-attr]
                delta = chunk.choices[0].delta if chunk.choices else None  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
                if delta and delta.content:  # pyright: ignore[reportUnknownMemberType]
                    yield delta.content  # pyright: ignore[reportUnknownMemberType]
        except openai.APITimeoutError as exc:
            raise ProviderTimeoutError(f"OpenAI request timed out: {exc}") from exc
        except openai.RateLimitError as exc:
            raise RateLimitError(f"OpenAI rate limit exceeded: {exc}") from exc
        except openai.AuthenticationError as exc:
            raise InvalidApiKeyError(f"OpenAI authentication failed: {exc}") from exc
        except openai.NotFoundError as exc:
            raise ModelUnavailableError(f"OpenAI model not found: {exc}") from exc
