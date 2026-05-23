"""Fail-closed provider validation policy."""

from mindmesh.config import MindMeshConfig, resolve_alias
from mindmesh.errors import (
    DefaultProviderDisabledError,
    PolicyViolationError,
    ProviderDisabledError,
    UnsupportedProviderError,
)
from mindmesh.registry import get_registry


class ProviderPolicy:
    """Fail-closed validation for provider access."""

    def __init__(self, config: MindMeshConfig) -> None:
        self._config = config

    def validate(self, provider_name: str, requested_as: str | None = None) -> None:
        """Validate provider in 5 steps. Raises on any violation.

        Steps:
        1. Resolve alias
        2. Check disabled list → ProviderDisabledError
        3. Check allowed list (empty = all permitted) → PolicyViolationError
        4. Check adapter known → UnsupportedProviderError
        5. Pass
        """
        # Step 1: alias resolve
        resolved = resolve_alias(provider_name)
        label = requested_as if requested_as is not None else provider_name

        # Step 2: disabled check (disabled > allowed, always)
        disabled = {resolve_alias(p) for p in self._config.disabled}
        if resolved in disabled:
            suggested = self._get_available_providers()
            raise ProviderDisabledError(
                message=f"Provider '{resolved}' is disabled. No fallback.",
                provider=resolved,
                requested_as=label,
                suggested_providers=suggested,
            )

        # Step 3: allowed check (empty = all providers allowed)
        allowed = self._config.providers
        if allowed and resolved not in allowed:
            raise PolicyViolationError(
                f"Provider '{resolved}' is not in the allowed providers list."
            )

        # Step 4: adapter known
        if resolved not in get_registry().known_names():
            raise UnsupportedProviderError(
                f"Provider '{resolved}' is not supported. "
                f"Known providers: {sorted(get_registry().known_names())}"
            )

    def validate_default(self) -> None:
        """Raise DefaultProviderDisabledError if the default provider is disabled."""
        default_endpoints = self._config.review.default_endpoints
        if not default_endpoints:
            return

        disabled = {resolve_alias(p) for p in self._config.disabled}

        for endpoint_name in default_endpoints:
            endpoint = self._config.endpoints.get(endpoint_name)
            if endpoint is None:
                continue
            resolved = resolve_alias(endpoint.provider)
            if resolved in disabled:
                raise DefaultProviderDisabledError(
                    f"Default provider '{resolved}' (endpoint '{endpoint_name}') "
                    "is disabled. Fix the configuration — no automatic fallback."
                )

    def get_available_providers(self) -> list[str]:
        """Return allowed providers minus disabled ones."""
        return self._get_available_providers()

    def _get_available_providers(self) -> list[str]:
        disabled = {resolve_alias(p) for p in self._config.disabled}
        allowed = self._config.providers

        candidates = (
            {resolve_alias(p) for p in allowed} if allowed else set(get_registry().known_names())
        )

        return sorted(candidates - disabled)
