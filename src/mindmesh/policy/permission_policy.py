"""Permission policy enforcement for MindMesh operations."""

from typing import Any

from mindmesh.config import PermissionsConfig
from mindmesh.errors import PermissionDeniedError

# Local providers that don't require confirmation
LOCAL_PROVIDERS = {"ollama", "local"}


class PermissionPolicy:
    """Enforces permission checks for MindMesh operations."""

    def __init__(self, config: PermissionsConfig):
        """Initialize PermissionPolicy."""
        self.config = config

    def check_full_codebase(self) -> None:
        """Check if full codebase context is allowed.

        Raises:
            PermissionDeniedError: If allow_full_codebase_context is False.
        """
        if not self.config.allow_full_codebase_context:
            raise PermissionDeniedError(
                "Full codebase context is not allowed. "
                "Set allow_full_codebase_context=true in .mindmesh.yml"
            )

    def check_external_patch(self) -> None:
        """Check if external patch is allowed.

        Raises:
            PermissionDeniedError: If allow_external_patch is False.
        """
        if not self.config.allow_external_patch:
            raise PermissionDeniedError(
                "External patch is not allowed. "
                "Set allow_external_patch=true in .mindmesh.yml"
            )

    def check_auto_apply_patch(self) -> None:
        """Check if auto-apply patch is allowed.

        Raises:
            PermissionDeniedError: If allow_auto_apply_patch is False.
        """
        if not self.config.allow_auto_apply_patch:
            raise PermissionDeniedError(
                "Auto-apply patch is not allowed. "
                "Set allow_auto_apply_patch=true in .mindmesh.yml"
            )

    def check_large_context(
        self, context_size_kb: int, limit_kb: int
    ) -> dict[str, Any] | None:
        """Check if context size requires confirmation.

        Args:
            context_size_kb: Current context size in KB.
            limit_kb: Maximum allowed size in KB.

        Returns:
            Warning dict if confirmation required and limit exceeded, None otherwise.
            Claude will present this warning to the user.
        """
        if (
            self.config.require_confirmation_for_large_context
            and context_size_kb > limit_kb
        ):
            return {
                "warning": "LARGE_CONTEXT",
                "size_kb": context_size_kb,
                "limit_kb": limit_kb,
            }
        return None

    def check_external_provider(self, provider_name: str) -> dict[str, Any] | None:
        """Check if external provider requires confirmation.

        Args:
            provider_name: Name of the provider.

        Returns:
            Warning dict if confirmation required, None otherwise.
            Local providers (ollama, local) don't require confirmation.
        """
        if provider_name.lower() in LOCAL_PROVIDERS:
            return None

        if self.config.require_confirmation_for_external_provider:
            return {
                "warning": "EXTERNAL_PROVIDER",
                "provider": provider_name,
            }
        return None
