"""Z.ai provider adapter (OpenAI-compatible API via httpx)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from mindmesh.config import ProviderConfig
from mindmesh.errors import (
    InvalidApiKeyError,
    ModelUnavailableError,
    ProviderTimeoutError,
    RateLimitError,
)
from mindmesh.providers.base import ProviderAdapter
from mindmesh.schemas import Message

_DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


class ZaiAdapter(ProviderAdapter):
    name = "zai"

    def __init__(self, provider_config: ProviderConfig) -> None:
        api_key = ""
        if provider_config.api_key_env:
            api_key = os.environ.get(provider_config.api_key_env, "")

        base_url = provider_config.base_url or _DEFAULT_BASE_URL
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def send(self, messages: list[Message], model: str, config: dict[str, Any]) -> str:
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if "temperature" in config:
            body["temperature"] = config["temperature"]
        if "max_tokens" in config:
            body["max_tokens"] = config["max_tokens"]

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=body,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError(f"Z.ai request timed out: {exc}") from exc

            if resp.status_code == 401:
                raise InvalidApiKeyError("Z.ai authentication failed")
            if resp.status_code == 429:
                raise RateLimitError("Z.ai rate limit exceeded")
            if resp.status_code == 404:
                raise ModelUnavailableError(f"Z.ai model '{model}' not found")

            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {})
        if usage:
            from mindmesh.providers.base import TokenUsage
            self._last_usage = TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0) or 0,
                output_tokens=usage.get("completion_tokens", 0) or 0,
            )
        choices = data.get("choices", [])
        if not choices:
            return ""
        content: str | None = choices[0].get("message", {}).get("content")
        return content or ""
