"""Tests for ProviderRegistry."""

from __future__ import annotations

from mindmesh.registry import ProviderInfo, ProviderRegistry, get_registry


def _fresh_registry() -> ProviderRegistry:
    reg = ProviderRegistry()
    reg.register(ProviderInfo(
        name="test-provider",
        module_path="mindmesh.providers.test",
        class_name="TestAdapter",
        default_model="test-model",
        api_key_env="TEST_API_KEY",
        aliases=("tp", "tprov"),
    ))
    return reg


def test_register_and_get() -> None:
    reg = _fresh_registry()
    info = reg.get("test-provider")
    assert info is not None
    assert info.name == "test-provider"
    assert info.class_name == "TestAdapter"


def test_get_unknown_returns_none() -> None:
    reg = _fresh_registry()
    assert reg.get("nonexistent") is None


def test_alias_resolution() -> None:
    reg = _fresh_registry()
    assert reg.resolve_alias("tp") == "test-provider"
    assert reg.resolve_alias("tprov") == "test-provider"
    assert reg.resolve_alias("unknown") == "unknown"


def test_get_by_alias() -> None:
    reg = _fresh_registry()
    info = reg.get("tp")
    assert info is not None
    assert info.name == "test-provider"


def test_is_known() -> None:
    reg = _fresh_registry()
    assert reg.is_known("test-provider") is True
    assert reg.is_known("tp") is True
    assert reg.is_known("nonexistent") is False


def test_known_names() -> None:
    reg = _fresh_registry()
    assert "test-provider" in reg.known_names()


def test_aliases_dict() -> None:
    reg = _fresh_registry()
    aliases = reg.aliases()
    assert aliases["tp"] == "test-provider"
    assert aliases["tprov"] == "test-provider"


def test_auto_env_map() -> None:
    reg = _fresh_registry()
    env_map = reg.auto_env_map()
    assert "TEST_API_KEY" in env_map
    name, endpoint, model = env_map["TEST_API_KEY"]
    assert name == "test-provider"
    assert endpoint == "test-provider-default"
    assert model == "test-model"


def test_auto_env_map_no_key() -> None:
    reg = ProviderRegistry()
    reg.register(ProviderInfo(
        name="local-only",
        module_path="mindmesh.providers.local",
        class_name="LocalAdapter",
        default_model="local-m",
    ))
    assert reg.auto_env_map() == {}


def test_adapter_map() -> None:
    reg = _fresh_registry()
    amap = reg.adapter_map()
    assert amap["test-provider"] == (
        "mindmesh.providers.test", "TestAdapter",
    )


def test_all_providers() -> None:
    reg = _fresh_registry()
    assert len(reg.all_providers()) == 1


def test_global_registry_has_builtin_providers() -> None:
    reg = get_registry()
    assert reg.is_known("openai")
    assert reg.is_known("gemini")
    assert reg.is_known("zai")
    assert reg.is_known("ollama")
    assert reg.is_known("chatgpt")
    assert reg.is_known("local")


def test_global_registry_alias_chatgpt() -> None:
    reg = get_registry()
    assert reg.resolve_alias("chatgpt") == "openai"


def test_global_registry_alias_local() -> None:
    reg = get_registry()
    assert reg.resolve_alias("local") == "ollama"
