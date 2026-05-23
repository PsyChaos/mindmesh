from __future__ import annotations

from typing import Any

import pytest

from mindmesh.config import EndpointConfig, MindMeshConfig, ProviderConfig
from mindmesh.providers.base import EndpointResolver, ProviderAdapter
from mindmesh.schemas import Message


class FakeAdapter(ProviderAdapter):
    name = "fake"

    async def send(self, messages: list[Message], model: str, config: dict[str, Any]) -> str:
        return '{"findings": []}'


class NoSendAdapter(ProviderAdapter):
    name = "nosend"
    # deliberately omits send() → should be abstract


def _config_with(
    providers: dict[str, ProviderConfig] | None = None,
    endpoints: dict[str, EndpointConfig] | None = None,
    disabled: list[str] | None = None,
) -> MindMeshConfig:
    return MindMeshConfig(
        providers=providers or {},
        endpoints=endpoints or {},
        disabled=disabled or [],
    )


# ── ProviderAdapter abstract contract ──────────────────────────────────────


def test_provider_adapter_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        ProviderAdapter()  # type: ignore[abstract]


def test_send_is_abstract_missing_raises() -> None:
    with pytest.raises(TypeError):
        NoSendAdapter()  # type: ignore[abstract]


def test_concrete_subclass_instantiates() -> None:
    adapter = FakeAdapter()
    assert adapter.name == "fake"


@pytest.mark.asyncio
async def test_concrete_subclass_send_works() -> None:
    adapter = FakeAdapter()
    result = await adapter.send(
        [Message(role="user", content="hello")], model="fake-model", config={}
    )
    assert isinstance(result, str)


# ── EndpointResolver.resolve ────────────────────────────────────────────────


def test_endpoint_resolver_resolves_adapter_model_config() -> None:
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"ep1": EndpointConfig(provider="openai", model="gpt-4o", timeout_seconds=45)},
    )
    resolver = EndpointResolver(config)
    resolver._adapters["openai"] = FakeAdapter()  # pyright: ignore[reportPrivateUsage]

    adapter, model, ep_cfg = resolver.resolve("ep1")

    assert adapter is resolver._adapters["openai"]  # pyright: ignore[reportPrivateUsage]
    assert model == "gpt-4o"
    assert ep_cfg["timeout_seconds"] == 45
    assert ep_cfg["provider"] == "openai"


def test_endpoint_resolver_unknown_endpoint_raises_key_error() -> None:
    config = _config_with()
    resolver = EndpointResolver(config)

    with pytest.raises(KeyError, match="missing-ep"):
        resolver.resolve("missing-ep")


def test_endpoint_resolver_unsupported_provider_raises() -> None:
    config = _config_with(
        providers={"ghost": ProviderConfig()},
        endpoints={"ep1": EndpointConfig(provider="ghost", model="x")},
    )
    resolver = EndpointResolver(config)

    with pytest.raises(ValueError, match="Unsupported provider"):
        resolver.resolve("ep1")


# ── Lazy init / caching ─────────────────────────────────────────────────────


def test_lazy_init_same_provider_reuses_adapter_instance() -> None:
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={
            "ep1": EndpointConfig(provider="openai", model="gpt-4o"),
            "ep2": EndpointConfig(provider="openai", model="gpt-3.5-turbo"),
        },
    )
    resolver = EndpointResolver(config)
    pre_built = FakeAdapter()
    resolver._adapters["openai"] = pre_built  # pyright: ignore[reportPrivateUsage]

    adapter1, model1, _ = resolver.resolve("ep1")
    adapter2, model2, _ = resolver.resolve("ep2")

    assert adapter1 is pre_built
    assert adapter2 is pre_built  # same cached instance
    assert model1 == "gpt-4o"
    assert model2 == "gpt-3.5-turbo"


def test_get_adapter_caches_on_second_call() -> None:
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"ep1": EndpointConfig(provider="openai", model="gpt-4o")},
    )
    resolver = EndpointResolver(config)
    fake = FakeAdapter()
    resolver._adapters["openai"] = fake  # pyright: ignore[reportPrivateUsage]

    first = resolver._get_adapter("openai")  # pyright: ignore[reportPrivateUsage]
    second = resolver._get_adapter("openai")  # pyright: ignore[reportPrivateUsage]

    assert first is second is fake


# ── list_endpoints status ────────────────────────────────────────────────────


def test_list_endpoints_ready_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"openai-default": EndpointConfig(provider="openai", model="gpt-4o")},
    )
    resolver = EndpointResolver(config)

    results = resolver.list_endpoints()

    assert len(results) == 1
    assert results[0]["name"] == "openai-default"
    assert results[0]["status"] == "ready"


def test_list_endpoints_no_api_key_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config = _config_with(
        providers={"gemini": ProviderConfig(api_key_env="GEMINI_API_KEY")},
        endpoints={"gemini-default": EndpointConfig(provider="gemini", model="gemini-2.0-flash")},
    )
    resolver = EndpointResolver(config)

    results = resolver.list_endpoints()

    assert results[0]["status"] == "no_api_key"


def test_list_endpoints_disabled_status() -> None:
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"openai-default": EndpointConfig(provider="openai", model="gpt-4o")},
        disabled=["openai"],
    )
    resolver = EndpointResolver(config)

    results = resolver.list_endpoints()

    assert results[0]["status"] == "disabled"


def test_list_endpoints_base_url_provider_is_ready() -> None:
    config = _config_with(
        providers={"ollama": ProviderConfig(base_url="http://localhost:11434")},
        endpoints={"ollama-local": EndpointConfig(provider="ollama", model="qwen2.5-coder")},
    )
    resolver = EndpointResolver(config)

    results = resolver.list_endpoints()

    assert results[0]["status"] == "ready"


def test_list_endpoints_alias_resolved_for_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"chatgpt-ep": EndpointConfig(provider="chatgpt", model="gpt-4o")},
    )
    resolver = EndpointResolver(config)

    results = resolver.list_endpoints()

    assert results[0]["provider"] == "openai"  # alias resolved
    assert results[0]["status"] == "ready"
