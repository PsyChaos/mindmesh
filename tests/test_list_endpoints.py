"""Tests for list_endpoints MCP tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindmesh.config import EndpointConfig, MindMeshConfig, ProviderConfig
from mindmesh.tools.list_endpoints import init_tools, list_endpoints


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


@pytest.mark.asyncio
async def test_list_endpoints_empty_config() -> None:
    init_tools(_config_with())
    result = await list_endpoints()
    assert result == {"endpoints": []}


@pytest.mark.asyncio
async def test_list_endpoints_ready_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"ep-openai": EndpointConfig(provider="openai", model="gpt-4o")},
    )
    init_tools(config)
    result = await list_endpoints()

    assert len(result["endpoints"]) == 1
    endpoint = result["endpoints"][0]
    assert endpoint["name"] == "ep-openai"
    assert endpoint["provider"] == "openai"
    assert endpoint["model"] == "gpt-4o"
    assert endpoint["status"] == "ready"


@pytest.mark.asyncio
async def test_list_endpoints_no_api_key_status() -> None:
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"ep-openai": EndpointConfig(provider="openai", model="gpt-4o")},
    )
    init_tools(config)
    result = await list_endpoints()

    assert len(result["endpoints"]) == 1
    endpoint = result["endpoints"][0]
    assert endpoint["status"] == "no_api_key"


@pytest.mark.asyncio
async def test_list_endpoints_disabled_status() -> None:
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"ep-openai": EndpointConfig(provider="openai", model="gpt-4o")},
        disabled=["openai"],
    )
    init_tools(config)
    result = await list_endpoints()

    assert len(result["endpoints"]) == 1
    endpoint = result["endpoints"][0]
    assert endpoint["status"] == "disabled"


@pytest.mark.asyncio
async def test_list_endpoints_with_base_url() -> None:
    config = _config_with(
        providers={"ollama": ProviderConfig(base_url="http://localhost:11434")},
        endpoints={"ep-ollama": EndpointConfig(provider="ollama", model="llama2")},
    )
    init_tools(config)
    result = await list_endpoints()

    assert len(result["endpoints"]) == 1
    endpoint = result["endpoints"][0]
    assert endpoint["status"] == "ready"


@pytest.mark.asyncio
async def test_list_endpoints_multiple_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config = _config_with(
        providers={
            "openai": ProviderConfig(api_key_env="OPENAI_API_KEY"),
            "gemini": ProviderConfig(api_key_env="GEMINI_API_KEY"),
            "ollama": ProviderConfig(base_url="http://localhost:11434"),
        },
        endpoints={
            "ep1": EndpointConfig(provider="openai", model="gpt-4o"),
            "ep2": EndpointConfig(provider="gemini", model="gemini-2.0-pro"),
            "ep3": EndpointConfig(provider="ollama", model="llama2"),
        },
        disabled=["gemini"],
    )
    init_tools(config)
    result = await list_endpoints()

    assert len(result["endpoints"]) == 3
    endpoints_by_name = {ep["name"]: ep for ep in result["endpoints"]}

    assert endpoints_by_name["ep1"]["status"] == "ready"
    assert endpoints_by_name["ep2"]["status"] == "disabled"
    assert endpoints_by_name["ep3"]["status"] == "ready"


@pytest.mark.asyncio
async def test_list_endpoints_provider_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={
            "ep-chatgpt": EndpointConfig(provider="chatgpt", model="gpt-4o"),
        },
    )
    init_tools(config)
    result = await list_endpoints()

    assert len(result["endpoints"]) == 1
    endpoint = result["endpoints"][0]
    assert endpoint["provider"] == "openai"
    assert endpoint["status"] == "ready"


# --- health check tests ---


@pytest.mark.asyncio
async def test_check_false_no_health_field() -> None:
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"ep1": EndpointConfig(provider="openai", model="gpt-4o")},
    )
    init_tools(config)
    result = await list_endpoints(check=False)

    assert "health" not in result["endpoints"][0]


@pytest.mark.asyncio
async def test_check_true_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"ep1": EndpointConfig(provider="openai", model="gpt-4o")},
    )
    init_tools(config)

    mock_adapter = MagicMock()
    mock_adapter.send = AsyncMock(return_value="ok")

    with patch(
        "mindmesh.tools.list_endpoints.EndpointResolver"
    ) as mock_resolver_cls:
        mock_resolver = MagicMock()
        mock_resolver.list_endpoints.return_value = [
            {"name": "ep1", "provider": "openai", "model": "gpt-4o", "status": "ready"},
        ]
        mock_resolver.resolve.return_value = (
            mock_adapter, "gpt-4o", {"timeout_seconds": 30},
        )
        mock_resolver_cls.return_value = mock_resolver

        result = await list_endpoints(check=True)

    assert result["endpoints"][0]["health"] == "healthy"


@pytest.mark.asyncio
async def test_check_true_blocked_by_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"ep1": EndpointConfig(provider="openai", model="gpt-4o")},
        disabled=["openai"],
    )
    init_tools(config)

    with patch(
        "mindmesh.tools.list_endpoints.EndpointResolver"
    ) as mock_resolver_cls:
        mock_resolver = MagicMock()
        mock_resolver.list_endpoints.return_value = [
            {"name": "ep1", "provider": "openai", "model": "gpt-4o", "status": "disabled"},
        ]
        mock_resolver_cls.return_value = mock_resolver

        result = await list_endpoints(check=True)

    assert result["endpoints"][0]["health"] == "blocked"


@pytest.mark.asyncio
async def test_check_true_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config = _config_with(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        endpoints={"ep1": EndpointConfig(provider="openai", model="gpt-4o")},
    )
    init_tools(config)

    mock_adapter = MagicMock()
    mock_adapter.send = AsyncMock(side_effect=TimeoutError)

    with patch(
        "mindmesh.tools.list_endpoints.EndpointResolver"
    ) as mock_resolver_cls:
        mock_resolver = MagicMock()
        mock_resolver.list_endpoints.return_value = [
            {"name": "ep1", "provider": "openai", "model": "gpt-4o", "status": "ready"},
        ]
        mock_resolver.resolve.return_value = (
            mock_adapter, "gpt-4o", {"timeout_seconds": 30},
        )
        mock_resolver_cls.return_value = mock_resolver

        result = await list_endpoints(check=True)

    assert result["endpoints"][0]["health"] == "timeout"
