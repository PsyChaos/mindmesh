"""Tests for PermissionPolicy."""

import pytest

from mindmesh.config import PermissionsConfig
from mindmesh.errors import PermissionDeniedError
from mindmesh.policy.permission_policy import PermissionPolicy


class TestCheckFullCodebase:
    """Tests for check_full_codebase method."""

    def test_full_codebase_allowed(self):
        """Test no error when full codebase is allowed."""
        config = PermissionsConfig(allow_full_codebase_context=True)
        policy = PermissionPolicy(config)
        policy.check_full_codebase()  # Should not raise

    def test_full_codebase_denied(self):
        """Test PermissionDeniedError when full codebase is not allowed."""
        config = PermissionsConfig(allow_full_codebase_context=False)
        policy = PermissionPolicy(config)
        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_full_codebase()
        assert "full codebase context" in str(exc_info.value).lower()

    def test_full_codebase_default_denied(self):
        """Test default value is False (deny)."""
        config = PermissionsConfig()
        policy = PermissionPolicy(config)
        with pytest.raises(PermissionDeniedError):
            policy.check_full_codebase()


class TestCheckExternalPatch:
    """Tests for check_external_patch method."""

    def test_external_patch_allowed(self):
        """Test no error when external patch is allowed."""
        config = PermissionsConfig(allow_external_patch=True)
        policy = PermissionPolicy(config)
        policy.check_external_patch()  # Should not raise

    def test_external_patch_denied(self):
        """Test PermissionDeniedError when external patch is not allowed."""
        config = PermissionsConfig(allow_external_patch=False)
        policy = PermissionPolicy(config)
        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_external_patch()
        assert "external patch" in str(exc_info.value).lower()

    def test_external_patch_default_denied(self):
        """Test default value is False (deny)."""
        config = PermissionsConfig()
        policy = PermissionPolicy(config)
        with pytest.raises(PermissionDeniedError):
            policy.check_external_patch()


class TestCheckAutoApplyPatch:
    """Tests for check_auto_apply_patch method."""

    def test_auto_apply_patch_allowed(self):
        """Test no error when auto-apply patch is allowed."""
        config = PermissionsConfig(allow_auto_apply_patch=True)
        policy = PermissionPolicy(config)
        policy.check_auto_apply_patch()  # Should not raise

    def test_auto_apply_patch_denied(self):
        """Test PermissionDeniedError when auto-apply patch is not allowed."""
        config = PermissionsConfig(allow_auto_apply_patch=False)
        policy = PermissionPolicy(config)
        with pytest.raises(PermissionDeniedError) as exc_info:
            policy.check_auto_apply_patch()
        assert "auto-apply patch" in str(exc_info.value).lower()

    def test_auto_apply_patch_default_denied(self):
        """Test default value is False (deny)."""
        config = PermissionsConfig()
        policy = PermissionPolicy(config)
        with pytest.raises(PermissionDeniedError):
            policy.check_auto_apply_patch()


class TestCheckLargeContext:
    """Tests for check_large_context method."""

    def test_large_context_within_limit(self):
        """Test no warning when context is within limit."""
        config = PermissionsConfig(require_confirmation_for_large_context=True)
        policy = PermissionPolicy(config)
        result = policy.check_large_context(context_size_kb=100, limit_kb=200)
        assert result is None

    def test_large_context_exceeds_limit_confirmation_required(self):
        """Test warning dict when context exceeds limit with confirmation required."""
        config = PermissionsConfig(require_confirmation_for_large_context=True)
        policy = PermissionPolicy(config)
        result = policy.check_large_context(context_size_kb=300, limit_kb=200)
        assert result is not None
        assert result["warning"] == "LARGE_CONTEXT"
        assert result["size_kb"] == 300
        assert result["limit_kb"] == 200

    def test_large_context_exceeds_limit_no_confirmation(self):
        """Test no warning when confirmation not required."""
        config = PermissionsConfig(require_confirmation_for_large_context=False)
        policy = PermissionPolicy(config)
        result = policy.check_large_context(context_size_kb=300, limit_kb=200)
        assert result is None

    def test_large_context_at_limit(self):
        """Test no warning when context equals limit."""
        config = PermissionsConfig(require_confirmation_for_large_context=True)
        policy = PermissionPolicy(config)
        result = policy.check_large_context(context_size_kb=200, limit_kb=200)
        assert result is None

    def test_large_context_default_requires_confirmation(self):
        """Test default value requires confirmation."""
        config = PermissionsConfig()
        policy = PermissionPolicy(config)
        assert config.require_confirmation_for_large_context is True
        result = policy.check_large_context(context_size_kb=2000, limit_kb=1024)
        assert result is not None

    def test_large_context_zero_limit(self):
        """Test with zero limit."""
        config = PermissionsConfig(require_confirmation_for_large_context=True)
        policy = PermissionPolicy(config)
        result = policy.check_large_context(context_size_kb=1, limit_kb=0)
        assert result is not None

    def test_large_context_large_values(self):
        """Test with large KB values."""
        config = PermissionsConfig(require_confirmation_for_large_context=True)
        policy = PermissionPolicy(config)
        result = policy.check_large_context(context_size_kb=10000, limit_kb=5000)
        assert result is not None
        assert result["size_kb"] == 10000
        assert result["limit_kb"] == 5000


class TestCheckExternalProvider:
    """Tests for check_external_provider method."""

    def test_external_provider_confirmation_required(self):
        """Test warning for external provider with confirmation required."""
        config = PermissionsConfig(require_confirmation_for_external_provider=True)
        policy = PermissionPolicy(config)
        result = policy.check_external_provider("openai")
        assert result is not None
        assert result["warning"] == "EXTERNAL_PROVIDER"
        assert result["provider"] == "openai"

    def test_external_provider_no_confirmation(self):
        """Test no warning when confirmation not required."""
        config = PermissionsConfig(require_confirmation_for_external_provider=False)
        policy = PermissionPolicy(config)
        result = policy.check_external_provider("openai")
        assert result is None

    def test_ollama_provider_no_warning(self):
        """Test ollama provider doesn't require confirmation."""
        config = PermissionsConfig(require_confirmation_for_external_provider=True)
        policy = PermissionPolicy(config)
        result = policy.check_external_provider("ollama")
        assert result is None

    def test_local_provider_no_warning(self):
        """Test local provider doesn't require confirmation."""
        config = PermissionsConfig(require_confirmation_for_external_provider=True)
        policy = PermissionPolicy(config)
        result = policy.check_external_provider("local")
        assert result is None

    def test_provider_case_insensitive(self):
        """Test provider name comparison is case-insensitive."""
        config = PermissionsConfig(require_confirmation_for_external_provider=True)
        policy = PermissionPolicy(config)
        result_upper = policy.check_external_provider("OLLAMA")
        result_mixed = policy.check_external_provider("Ollama")
        assert result_upper is None
        assert result_mixed is None

    def test_external_providers_require_warning(self):
        """Test various external providers require warning."""
        config = PermissionsConfig(require_confirmation_for_external_provider=True)
        policy = PermissionPolicy(config)
        external_providers = ["openai", "gemini", "zai", "custom"]
        for provider in external_providers:
            result = policy.check_external_provider(provider)
            assert result is not None
            assert result["provider"] == provider

    def test_default_external_provider_no_confirmation(self):
        """Test default is no confirmation required for external providers."""
        config = PermissionsConfig()
        policy = PermissionPolicy(config)
        assert config.require_confirmation_for_external_provider is False
        result = policy.check_external_provider("openai")
        assert result is None


class TestDefaultPermissions:
    """Tests for default permission values."""

    def test_default_permissions_config(self):
        """Test default PermissionsConfig values."""
        config = PermissionsConfig()
        assert config.allow_full_codebase_context is False
        assert config.allow_external_patch is False
        assert config.allow_auto_apply_patch is False
        assert config.require_confirmation_for_large_context is True
        assert config.require_confirmation_for_external_provider is False

    def test_all_defaults_with_permission_policy(self):
        """Test PermissionPolicy with all default permissions."""
        config = PermissionsConfig()
        policy = PermissionPolicy(config)

        # Should raise for all check methods that check allow_* flags
        with pytest.raises(PermissionDeniedError):
            policy.check_full_codebase()
        with pytest.raises(PermissionDeniedError):
            policy.check_external_patch()
        with pytest.raises(PermissionDeniedError):
            policy.check_auto_apply_patch()

        # Should require confirmation for large context
        result = policy.check_large_context(1500, 1024)
        assert result is not None

        # Should not require confirmation for external providers
        result = policy.check_external_provider("openai")
        assert result is None


class TestPermissionPolicyIntegration:
    """Integration tests for PermissionPolicy."""

    def test_permissive_configuration(self):
        """Test fully permissive configuration."""
        config = PermissionsConfig(
            allow_full_codebase_context=True,
            allow_external_patch=True,
            allow_auto_apply_patch=True,
            require_confirmation_for_large_context=False,
            require_confirmation_for_external_provider=False,
        )
        policy = PermissionPolicy(config)

        # All checks should pass without errors or warnings
        policy.check_full_codebase()
        policy.check_external_patch()
        policy.check_auto_apply_patch()
        assert policy.check_large_context(5000, 1024) is None
        assert policy.check_external_provider("openai") is None

    def test_restrictive_configuration(self):
        """Test fully restrictive configuration."""
        config = PermissionsConfig(
            allow_full_codebase_context=False,
            allow_external_patch=False,
            allow_auto_apply_patch=False,
            require_confirmation_for_large_context=True,
            require_confirmation_for_external_provider=True,
        )
        policy = PermissionPolicy(config)

        # All allow_* checks should raise
        with pytest.raises(PermissionDeniedError):
            policy.check_full_codebase()
        with pytest.raises(PermissionDeniedError):
            policy.check_external_patch()
        with pytest.raises(PermissionDeniedError):
            policy.check_auto_apply_patch()

        # All confirmation checks should return warnings
        assert policy.check_large_context(1500, 1024) is not None
        assert policy.check_external_provider("openai") is not None
        # Local providers still exempt
        assert policy.check_external_provider("ollama") is None
