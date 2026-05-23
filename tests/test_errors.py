"""Tests for MindMesh exception hierarchy."""


from mindmesh.errors import (
    ContextTooLargeError,
    DefaultProviderDisabledError,
    InvalidApiKeyError,
    MindMeshError,
    ModelUnavailableError,
    ParseError,
    PermissionDeniedError,
    PolicyViolationError,
    ProviderDisabledError,
    ProviderTimeoutError,
    RateLimitError,
    SecretDetectedError,
    UnsupportedProviderError,
)
from mindmesh.schemas import ErrorFinding


class TestMindMeshError:
    """Tests for base MindMeshError class."""

    def test_error_message(self):
        """Test error message initialization."""
        error = MindMeshError("Test error message")
        assert error.message == "Test error message"
        assert str(error) == "Test error message"

    def test_error_code_default(self):
        """Test default error_code."""
        error = MindMeshError("Test")
        assert error.error_code == "UNKNOWN_ERROR"

    def test_retryable_default(self):
        """Test default retryable flag."""
        error = MindMeshError("Test")
        assert error.retryable is False

    def test_to_finding(self):
        """Test to_finding conversion."""
        error = MindMeshError("Test error")
        finding = error.to_finding(
            endpoint="test:endpoint",
            provider="test",
            model="test-model",
        )
        assert isinstance(finding, ErrorFinding)
        assert finding.endpoint == "test:endpoint"
        assert finding.provider == "test"
        assert finding.model == "test-model"
        assert finding.explanation == "Test error"
        assert finding.error_code == "UNKNOWN_ERROR"
        assert finding.retryable is False

    def test_is_exception(self):
        """Test MindMeshError is an Exception."""
        error = MindMeshError("Test")
        assert isinstance(error, Exception)


class TestProviderTimeoutError:
    """Tests for ProviderTimeoutError."""

    def test_error_code(self):
        """Test ProviderTimeoutError error_code."""
        error = ProviderTimeoutError("Request timeout")
        assert error.error_code == "PROVIDER_TIMEOUT"

    def test_retryable(self):
        """Test ProviderTimeoutError is retryable."""
        error = ProviderTimeoutError("Request timeout")
        assert error.retryable is True

    def test_to_finding(self):
        """Test to_finding returns correct finding."""
        error = ProviderTimeoutError("Request timeout after 30s")
        finding = error.to_finding("openai:gpt-4", "openai", "gpt-4")
        assert finding.error_code == "PROVIDER_TIMEOUT"
        assert finding.retryable is True
        assert finding.explanation == "Request timeout after 30s"


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_error_code(self):
        """Test RateLimitError error_code."""
        error = RateLimitError("Rate limit exceeded")
        assert error.error_code == "RATE_LIMIT"

    def test_retryable(self):
        """Test RateLimitError is retryable."""
        error = RateLimitError("Rate limit exceeded")
        assert error.retryable is True


class TestPolicyViolationError:
    """Tests for PolicyViolationError."""

    def test_error_code(self):
        """Test PolicyViolationError error_code."""
        error = PolicyViolationError("Policy violated")
        assert error.error_code == "POLICY_VIOLATION"

    def test_retryable(self):
        """Test PolicyViolationError is not retryable."""
        error = PolicyViolationError("Policy violated")
        assert error.retryable is False

    def test_is_mindmesh_error(self):
        """Test PolicyViolationError is MindMeshError."""
        error = PolicyViolationError("Policy violated")
        assert isinstance(error, MindMeshError)


class TestProviderDisabledError:
    """Tests for ProviderDisabledError."""

    def test_error_code(self):
        """Test ProviderDisabledError error_code."""
        error = ProviderDisabledError(
            "Provider disabled",
            provider="openai",
            requested_as="chatgpt",
        )
        assert error.error_code == "PROVIDER_DISABLED"

    def test_retryable(self):
        """Test ProviderDisabledError is not retryable."""
        error = ProviderDisabledError(
            "Provider disabled",
            provider="openai",
            requested_as="chatgpt",
        )
        assert error.retryable is False

    def test_provider_field(self):
        """Test provider field."""
        error = ProviderDisabledError(
            "Provider disabled",
            provider="openai",
            requested_as="chatgpt",
        )
        assert error.provider == "openai"

    def test_requested_as_field(self):
        """Test requested_as field."""
        error = ProviderDisabledError(
            "Provider disabled",
            provider="openai",
            requested_as="chatgpt",
        )
        assert error.requested_as == "chatgpt"

    def test_suggested_providers_default(self):
        """Test suggested_providers defaults to empty list."""
        error = ProviderDisabledError(
            "Provider disabled",
            provider="openai",
            requested_as="chatgpt",
        )
        assert error.suggested_providers == []

    def test_suggested_providers_provided(self):
        """Test suggested_providers when provided."""
        error = ProviderDisabledError(
            "Provider disabled",
            provider="openai",
            requested_as="chatgpt",
            suggested_providers=["gemini", "zai"],
        )
        assert error.suggested_providers == ["gemini", "zai"]

    def test_is_policy_violation_error(self):
        """Test ProviderDisabledError is PolicyViolationError."""
        error = ProviderDisabledError(
            "Provider disabled",
            provider="openai",
            requested_as="chatgpt",
        )
        assert isinstance(error, PolicyViolationError)

    def test_inheritance_chain(self):
        """Test inheritance chain."""
        error = ProviderDisabledError(
            "Provider disabled",
            provider="openai",
            requested_as="chatgpt",
        )
        assert isinstance(error, ProviderDisabledError)
        assert isinstance(error, PolicyViolationError)
        assert isinstance(error, MindMeshError)
        assert isinstance(error, Exception)


class TestDefaultProviderDisabledError:
    """Tests for DefaultProviderDisabledError."""

    def test_error_code(self):
        """Test DefaultProviderDisabledError error_code."""
        error = DefaultProviderDisabledError("Default provider disabled")
        assert error.error_code == "DEFAULT_PROVIDER_DISABLED"

    def test_retryable(self):
        """Test DefaultProviderDisabledError is not retryable."""
        error = DefaultProviderDisabledError("Default provider disabled")
        assert error.retryable is False

    def test_is_policy_violation_error(self):
        """Test DefaultProviderDisabledError is PolicyViolationError."""
        error = DefaultProviderDisabledError("Default provider disabled")
        assert isinstance(error, PolicyViolationError)


class TestParseError:
    """Tests for ParseError."""

    def test_error_code(self):
        """Test ParseError error_code."""
        error = ParseError("Invalid JSON response")
        assert error.error_code == "PARSE_ERROR"

    def test_retryable(self):
        """Test ParseError is not retryable."""
        error = ParseError("Invalid JSON response")
        assert error.retryable is False


class TestContextTooLargeError:
    """Tests for ContextTooLargeError."""

    def test_error_code(self):
        """Test ContextTooLargeError error_code."""
        error = ContextTooLargeError("Context exceeds 100KB")
        assert error.error_code == "CONTEXT_TOO_LARGE"

    def test_retryable(self):
        """Test ContextTooLargeError is not retryable."""
        error = ContextTooLargeError("Context exceeds 100KB")
        assert error.retryable is False


class TestSecretDetectedError:
    """Tests for SecretDetectedError."""

    def test_error_code(self):
        """Test SecretDetectedError error_code."""
        error = SecretDetectedError("API key found at line 42")
        assert error.error_code == "SECRET_DETECTED"

    def test_retryable(self):
        """Test SecretDetectedError is not retryable."""
        error = SecretDetectedError("API key found at line 42")
        assert error.retryable is False


class TestUnsupportedProviderError:
    """Tests for UnsupportedProviderError."""

    def test_error_code(self):
        """Test UnsupportedProviderError error_code."""
        error = UnsupportedProviderError("Provider 'custom' is not supported")
        assert error.error_code == "UNSUPPORTED_PROVIDER"

    def test_retryable(self):
        """Test UnsupportedProviderError is not retryable."""
        error = UnsupportedProviderError("Provider 'custom' is not supported")
        assert error.retryable is False


class TestInvalidApiKeyError:
    """Tests for InvalidApiKeyError."""

    def test_error_code(self):
        """Test InvalidApiKeyError error_code."""
        error = InvalidApiKeyError("API key is invalid")
        assert error.error_code == "INVALID_API_KEY"

    def test_retryable(self):
        """Test InvalidApiKeyError is not retryable."""
        error = InvalidApiKeyError("API key is invalid")
        assert error.retryable is False


class TestModelUnavailableError:
    """Tests for ModelUnavailableError."""

    def test_error_code(self):
        """Test ModelUnavailableError error_code."""
        error = ModelUnavailableError("Model gpt-5 is not available")
        assert error.error_code == "MODEL_UNAVAILABLE"

    def test_retryable(self):
        """Test ModelUnavailableError is retryable."""
        error = ModelUnavailableError("Model gpt-5 is not available")
        assert error.retryable is True


class TestPermissionDeniedError:
    """Tests for PermissionDeniedError."""

    def test_error_code(self):
        """Test PermissionDeniedError error_code."""
        error = PermissionDeniedError("Operation not permitted")
        assert error.error_code == "PERMISSION_DENIED"

    def test_retryable(self):
        """Test PermissionDeniedError is not retryable."""
        error = PermissionDeniedError("Operation not permitted")
        assert error.retryable is False

    def test_is_policy_violation_error(self):
        """Test PermissionDeniedError is PolicyViolationError."""
        error = PermissionDeniedError("Operation not permitted")
        assert isinstance(error, PolicyViolationError)


class TestAllRetryableFlagsClear:
    """Test retryable flags for all error types."""

    def test_retryable_true_errors(self):
        """Test errors that should be retryable."""
        retryable_errors = [
            ProviderTimeoutError("timeout"),
            RateLimitError("rate limit"),
            ModelUnavailableError("unavailable"),
        ]
        for error in retryable_errors:
            assert error.retryable is True

    def test_retryable_false_errors(self):
        """Test errors that should not be retryable."""
        non_retryable_errors = [
            PolicyViolationError("policy"),
            ProviderDisabledError("disabled", "test", "test"),
            DefaultProviderDisabledError("default disabled"),
            ParseError("parse"),
            ContextTooLargeError("context"),
            SecretDetectedError("secret"),
            UnsupportedProviderError("unsupported"),
            InvalidApiKeyError("key"),
            PermissionDeniedError("permission"),
        ]
        for error in non_retryable_errors:
            assert error.retryable is False


class TestAllPolicyViolationChildren:
    """Test PolicyViolationError children are not retryable."""

    def test_policy_violation_subclasses(self):
        """Test all PolicyViolationError subclasses are not retryable."""
        policy_errors = [
            ProviderDisabledError("disabled", "test", "test"),
            DefaultProviderDisabledError("default disabled"),
            PermissionDeniedError("permission"),
        ]
        for error in policy_errors:
            assert isinstance(error, PolicyViolationError)
            assert error.retryable is False


class TestErrorFindingConversion:
    """Test conversion of errors to ErrorFinding."""

    def test_all_errors_convert_to_finding(self):
        """Test all error types convert to ErrorFinding."""
        errors = [
            MindMeshError("test"),
            ProviderTimeoutError("timeout"),
            RateLimitError("rate limit"),
            PolicyViolationError("policy"),
            ProviderDisabledError("disabled", "openai", "chatgpt"),
            DefaultProviderDisabledError("default"),
            ParseError("parse"),
            ContextTooLargeError("context"),
            SecretDetectedError("secret"),
            UnsupportedProviderError("unsupported"),
            InvalidApiKeyError("key"),
            ModelUnavailableError("unavailable"),
            PermissionDeniedError("permission"),
        ]
        for error in errors:
            finding = error.to_finding("test", "test", "test")
            assert isinstance(finding, ErrorFinding)
            assert finding.endpoint == "test"
            assert finding.error_code == error.error_code
            assert finding.retryable == error.retryable

    def test_error_finding_maintains_retryable(self):
        """Test ErrorFinding maintains retryable flag from error."""
        timeout_error = ProviderTimeoutError("timeout")
        timeout_finding = timeout_error.to_finding("test", "test", "test")
        assert timeout_finding.retryable is True

        parse_error = ParseError("parse")
        parse_finding = parse_error.to_finding("test", "test", "test")
        assert parse_finding.retryable is False

    def test_provider_disabled_error_to_finding(self):
        """Test ProviderDisabledError to_finding."""
        error = ProviderDisabledError(
            "Provider disabled",
            provider="openai",
            requested_as="chatgpt",
            suggested_providers=["gemini", "zai"],
        )
        finding = error.to_finding("openai:gpt-4", "openai", "gpt-4")
        assert finding.error_code == "PROVIDER_DISABLED"
        assert finding.provider == "openai"


class TestInheritanceChain:
    """Test exception inheritance chains."""

    def test_mindmesh_error_is_exception(self):
        """Test MindMeshError extends Exception."""
        error = MindMeshError("test")
        assert isinstance(error, Exception)

    def test_policy_violation_error_chain(self):
        """Test PolicyViolationError inheritance."""
        error = PolicyViolationError("test")
        assert isinstance(error, MindMeshError)
        assert isinstance(error, Exception)

    def test_provider_disabled_error_chain(self):
        """Test ProviderDisabledError full chain."""
        error = ProviderDisabledError("test", "openai", "chatgpt")
        assert isinstance(error, ProviderDisabledError)
        assert isinstance(error, PolicyViolationError)
        assert isinstance(error, MindMeshError)
        assert isinstance(error, Exception)

    def test_permission_denied_error_chain(self):
        """Test PermissionDeniedError full chain."""
        error = PermissionDeniedError("test")
        assert isinstance(error, PermissionDeniedError)
        assert isinstance(error, PolicyViolationError)
        assert isinstance(error, MindMeshError)
        assert isinstance(error, Exception)
