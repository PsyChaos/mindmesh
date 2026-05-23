"""Gemini provider adapter (google-genai SDK)."""

from __future__ import annotations

import os
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from mindmesh.config import ProviderConfig
from mindmesh.errors import InvalidApiKeyError, ProviderTimeoutError, RateLimitError
from mindmesh.providers.base import ProviderAdapter
from mindmesh.schemas import Message


class GeminiAdapter(ProviderAdapter):
    name = "gemini"

    def __init__(self, provider_config: ProviderConfig) -> None:
        api_key = ""
        if provider_config.api_key_env:
            api_key = os.environ.get(provider_config.api_key_env, "")
        self._client = genai.Client(api_key=api_key)

    async def send(self, messages: list[Message], model: str, config: dict[str, Any]) -> str:
        system_parts = [m.content for m in messages if m.role == "system"]
        user_parts = [m.content for m in messages if m.role == "user"]

        system_instruction = "\n".join(system_parts) if system_parts else None
        contents = "\n".join(user_parts)

        gen_config_kwargs: dict[str, Any] = {}
        if system_instruction is not None:
            gen_config_kwargs["system_instruction"] = system_instruction
        if "temperature" in config:
            gen_config_kwargs["temperature"] = config["temperature"]

        gen_config = types.GenerateContentConfig(**gen_config_kwargs) if gen_config_kwargs else None

        try:
            response = await self._client.aio.models.generate_content(  # type: ignore[reportUnknownMemberType]
                model=model,
                contents=contents,
                config=gen_config,
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(f"Gemini request timed out: {exc}") from exc
        except genai_errors.ClientError as exc:
            if exc.code in (401, 403):
                raise InvalidApiKeyError(f"Gemini authentication failed: {exc}") from exc
            if exc.code == 429:
                raise RateLimitError(f"Gemini rate limit exceeded: {exc}") from exc
            raise

        usage_meta = getattr(response, "usage_metadata", None)
        if usage_meta:
            from mindmesh.providers.base import TokenUsage
            self._last_usage = TokenUsage(
                input_tokens=getattr(usage_meta, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage_meta, "candidates_token_count", 0) or 0,
            )
        return response.text or ""
