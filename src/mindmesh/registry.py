"""Centralized provider registry — single source of truth."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    module_path: str
    class_name: str
    default_model: str
    api_key_env: str | None = None
    aliases: tuple[str, ...] = ()


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ProviderInfo] = {}
        self._aliases: dict[str, str] = {}

    def register(self, info: ProviderInfo) -> None:
        self._providers[info.name] = info
        for alias in info.aliases:
            self._aliases[alias] = info.name

    def get(self, name: str) -> ProviderInfo | None:
        resolved = self.resolve_alias(name)
        return self._providers.get(resolved)

    def resolve_alias(self, name: str) -> str:
        return self._aliases.get(name, name)

    def is_known(self, name: str) -> bool:
        resolved = self.resolve_alias(name)
        return resolved in self._providers

    def known_names(self) -> frozenset[str]:
        return frozenset(self._providers.keys())

    def aliases(self) -> dict[str, str]:
        return dict(self._aliases)

    def auto_env_map(self) -> dict[str, tuple[str, str, str]]:
        result: dict[str, tuple[str, str, str]] = {}
        for info in self._providers.values():
            if info.api_key_env:
                endpoint_name = f"{info.name}-default"
                result[info.api_key_env] = (
                    info.name, endpoint_name, info.default_model,
                )
        return result

    def adapter_map(self) -> dict[str, tuple[str, str]]:
        return {
            info.name: (info.module_path, info.class_name)
            for info in self._providers.values()
        }

    def all_providers(self) -> list[ProviderInfo]:
        return list(self._providers.values())


_registry = ProviderRegistry()

_registry.register(ProviderInfo(
    name="openai",
    module_path="mindmesh.providers.openai",
    class_name="OpenAIAdapter",
    default_model="gpt-4o",
    api_key_env="OPENAI_API_KEY",
    aliases=("chatgpt",),
))
_registry.register(ProviderInfo(
    name="gemini",
    module_path="mindmesh.providers.gemini",
    class_name="GeminiAdapter",
    default_model="gemini-2.0-flash",
    api_key_env="GEMINI_API_KEY",
))
_registry.register(ProviderInfo(
    name="zai",
    module_path="mindmesh.providers.zai",
    class_name="ZaiAdapter",
    default_model="glm-4.6",
    api_key_env="ZAI_API_KEY",
))
_registry.register(ProviderInfo(
    name="ollama",
    module_path="mindmesh.providers.ollama",
    class_name="OllamaAdapter",
    default_model="qwen2.5-coder",
    aliases=("local",),
))


def get_registry() -> ProviderRegistry:
    return _registry
