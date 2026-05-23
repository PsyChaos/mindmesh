"""Ollama provider adapter (local HTTP API via httpx)."""

from __future__ import annotations

import json as json_mod
from collections.abc import AsyncIterator
from typing import Any

import httpx

from mindmesh.config import ProviderConfig
from mindmesh.errors import ModelUnavailableError, ProviderTimeoutError
from mindmesh.providers.base import ProviderAdapter
from mindmesh.schemas import Message

_DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaAdapter(ProviderAdapter):
    name = "ollama"

    def __init__(self, provider_config: ProviderConfig) -> None:
        base_url = provider_config.base_url or _DEFAULT_BASE_URL
        self._base_url = base_url.rstrip("/")

    def _build_body(
        self, messages: list[Message], model: str, config: dict[str, Any],
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages
            ],
        }
        if "temperature" in config:
            options = body.setdefault("options", {})
            options["temperature"] = config["temperature"]
        return body

    async def send(
        self, messages: list[Message], model: str, config: dict[str, Any],
    ) -> str:
        body = self._build_body(messages, model, config)
        body["stream"] = False

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/api/chat", json=body,
                )
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError(
                    f"Ollama request timed out: {exc}",
                ) from exc
            except httpx.ConnectError as exc:
                raise ProviderTimeoutError(
                    f"Cannot connect to Ollama at {self._base_url}: {exc}",
                ) from exc

            if resp.status_code == 404:
                raise ModelUnavailableError(
                    f"Ollama model '{model}' not found",
                )
            resp.raise_for_status()
            data = resp.json()

        from mindmesh.providers.base import TokenUsage
        self._last_usage = TokenUsage(
            input_tokens=data.get("prompt_eval_count", 0) or 0,
            output_tokens=data.get("eval_count", 0) or 0,
        )
        content: str | None = data.get("message", {}).get("content")
        return content or ""

    async def send_stream(
        self, messages: list[Message], model: str, config: dict[str, Any],
    ) -> AsyncIterator[str]:
        body = self._build_body(messages, model, config)
        body["stream"] = True

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream(
                    "POST", f"{self._base_url}/api/chat", json=body,
                ) as resp:
                    if resp.status_code == 404:
                        raise ModelUnavailableError(
                            f"Ollama model '{body['model']}' not found",
                        )
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        chunk = json_mod.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError(
                    f"Ollama request timed out: {exc}",
                ) from exc
            except httpx.ConnectError as exc:
                raise ProviderTimeoutError(
                    f"Cannot connect to Ollama at {self._base_url}: {exc}",
                ) from exc
