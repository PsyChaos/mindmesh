"""Tests for ProviderPolicy fail-closed validation."""

from typing import Any

import pytest

from mindmesh.config import EndpointConfig, MindMeshConfig, ProviderConfig, ReviewConfig
from mindmesh.errors import (
    DefaultProviderDisabledError,
    PolicyViolationError,
    ProviderDisabledError,
    UnsupportedProviderError,
)
from mindmesh.policy.provider_policy import ProviderPolicy


def _make_config(
    providers: dict[str, Any] | None = None,
    disabled: list[str] | None = None,
    endpoints: dict[str, EndpointConfig] | None = None,
    default_endpoints: list[str] | None = None,
) -> MindMeshConfig:
    return MindMeshConfig(
        providers={k: ProviderConfig() for k in (providers or {})},
        disabled=disabled or [],
        endpoints=endpoints or {},
        review=ReviewConfig(default_endpoints=default_endpoints or []),
    )


# --- allowed list ---

def test_allowed_provider_passes() -> None:
    config = _make_config(providers={"openai": {}})
    ProviderPolicy(config).validate("openai")  # no raise


def test_provider_not_in_allowed_raises_policy_violation() -> None:
    config = _make_config(providers={"openai": {}})
    with pytest.raises(PolicyViolationError):
        ProviderPolicy(config).validate("gemini")


# --- disabled list ---

def test_disabled_provider_raises_provider_disabled_error() -> None:
    config = _make_config(providers={"openai": {}}, disabled=["openai"])
    with pytest.raises(ProviderDisabledError):
        ProviderPolicy(config).validate("openai")


def test_disabled_beats_allowed() -> None:
    """Provider in both disabled and allowed → still blocked."""
    config = _make_config(providers={"gemini": {}}, disabled=["gemini"])
    with pytest.raises(ProviderDisabledError):
        ProviderPolicy(config).validate("gemini")


# --- alias resolution ---

def test_alias_chatgpt_resolves_to_openai() -> None:
    config = _make_config(providers={"openai": {}})
    ProviderPolicy(config).validate("chatgpt")  # no raise


def test_alias_disabled_blocks_alias_request() -> None:
    """openai disabled → chatgpt (alias) also blocked."""
    config = _make_config(providers={"openai": {}}, disabled=["openai"])
    with pytest.raises(ProviderDisabledError):
        ProviderPolicy(config).validate("chatgpt", requested_as="chatgpt")


def test_requested_as_preserved_in_error() -> None:
    config = _make_config(providers={"openai": {}}, disabled=["openai"])
    with pytest.raises(ProviderDisabledError) as exc_info:
        ProviderPolicy(config).validate("chatgpt", requested_as="chatgpt")
    assert exc_info.value.requested_as == "chatgpt"


# --- suggested_providers ---

def test_suggested_providers_excludes_disabled() -> None:
    config = _make_config(
        providers={"openai": {}, "gemini": {}},
        disabled=["openai"],
    )
    with pytest.raises(ProviderDisabledError) as exc_info:
        ProviderPolicy(config).validate("openai")
    suggested = exc_info.value.suggested_providers
    assert "gemini" in suggested
    assert "openai" not in suggested


# --- unsupported provider ---

def test_unknown_provider_raises_unsupported() -> None:
    config = _make_config()  # empty allowed = all known
    with pytest.raises(UnsupportedProviderError):
        ProviderPolicy(config).validate("anthropic")


# --- empty allowed list ---

def test_empty_allowed_permits_known_providers() -> None:
    config = _make_config()  # no providers key = all known allowed
    ProviderPolicy(config).validate("gemini")  # no raise


def test_empty_allowed_still_respects_disabled() -> None:
    config = _make_config(disabled=["gemini"])
    with pytest.raises(ProviderDisabledError):
        ProviderPolicy(config).validate("gemini")


# --- default provider ---

def test_validate_default_raises_when_default_provider_disabled() -> None:
    config = _make_config(
        providers={"openai": {}},
        disabled=["openai"],
        endpoints={"ep1": EndpointConfig(provider="openai", model="gpt-4o")},
        default_endpoints=["ep1"],
    )
    with pytest.raises(DefaultProviderDisabledError):
        ProviderPolicy(config).validate_default()


def test_validate_default_passes_when_provider_ok() -> None:
    config = _make_config(
        providers={"openai": {}},
        endpoints={"ep1": EndpointConfig(provider="openai", model="gpt-4o")},
        default_endpoints=["ep1"],
    )
    ProviderPolicy(config).validate_default()  # no raise


# --- get_available_providers ---

def test_get_available_providers_excludes_disabled() -> None:
    config = _make_config(
        providers={"openai": {}, "gemini": {}},
        disabled=["openai"],
    )
    available = ProviderPolicy(config).get_available_providers()
    assert "gemini" in available
    assert "openai" not in available


def test_get_available_providers_empty_allowed_returns_all_known_minus_disabled() -> None:
    config = _make_config(disabled=["ollama"])
    available = ProviderPolicy(config).get_available_providers()
    assert "ollama" not in available
    assert "openai" in available


# --- partial validation (multiple endpoints) ---

def test_partial_validation_one_disabled_one_ok() -> None:
    """Validate two endpoints: disabled one raises, ok one passes."""
    config = _make_config(
        providers={"openai": {}, "gemini": {}},
        disabled=["openai"],
    )
    policy = ProviderPolicy(config)

    with pytest.raises(ProviderDisabledError):
        policy.validate("openai")

    policy.validate("gemini")  # no raise — others not blocked
