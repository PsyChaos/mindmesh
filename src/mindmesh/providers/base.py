from __future__ import annotations

import importlib
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from mindmesh.config import MindMeshConfig, ProviderConfig, resolve_alias
from mindmesh.registry import get_registry
from mindmesh.schemas import Message


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0


class ProviderAdapter(ABC):
    name: str
    _last_usage: TokenUsage | None = None

    @property
    def last_usage(self) -> TokenUsage | None:
        return self._last_usage

    @abstractmethod
    async def send(
        self, messages: list[Message], model: str, config: dict[str, Any],
    ) -> str: ...

    async def send_stream(
        self, messages: list[Message], model: str, config: dict[str, Any],
    ) -> AsyncIterator[str]:
        result = await self.send(messages, model, config)
        yield result


class EndpointResolver:
    def __init__(self, config: MindMeshConfig) -> None:
        self._config = config
        self._adapters: dict[str, ProviderAdapter] = {}

    def resolve(self, endpoint_name: str) -> tuple[ProviderAdapter, str, dict[str, Any]]:
        if endpoint_name not in self._config.endpoints:
            raise KeyError(f"Endpoint '{endpoint_name}' not found in config")
        endpoint = self._config.endpoints[endpoint_name]
        provider_name = resolve_alias(endpoint.provider)
        adapter = self._get_adapter(provider_name)
        return adapter, endpoint.model, endpoint.model_dump()

    def _get_adapter(self, provider_name: str) -> ProviderAdapter:
        if provider_name in self._adapters:
            return self._adapters[provider_name]

        adapter_map = get_registry().adapter_map()
        if provider_name not in adapter_map:
            raise ValueError(f"Unsupported provider: '{provider_name}'")

        module_path, class_name = adapter_map[provider_name]
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ValueError(
                f"Adapter module for provider '{provider_name}' is not available: {exc}"
            ) from exc

        adapter_cls = getattr(module, class_name)
        provider_config = self._config.providers.get(provider_name, ProviderConfig())
        adapter: ProviderAdapter = adapter_cls(provider_config)
        self._adapters[provider_name] = adapter
        return adapter

    def list_endpoints(self) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        for name, endpoint in self._config.endpoints.items():
            provider_name = resolve_alias(endpoint.provider)
            status = self._endpoint_status(provider_name)
            results.append(
                {"name": name, "provider": provider_name, "model": endpoint.model, "status": status}
            )
        return results

    def _endpoint_status(self, provider_name: str) -> str:
        if provider_name in self._config.disabled:
            return "disabled"
        provider = self._config.providers.get(provider_name)
        if provider is None:
            return "no_api_key"
        if provider.api_key_env:
            return "ready" if os.environ.get(provider.api_key_env) else "no_api_key"
        if provider.base_url:
            return "ready"
        return "no_api_key"
