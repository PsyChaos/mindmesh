"""Custom exception hierarchy for MindMesh."""

from mindmesh.schemas import ErrorFinding


class MindMeshError(Exception):
    """Base exception for MindMesh errors."""

    error_code: str = "UNKNOWN_ERROR"
    retryable: bool = False

    def __init__(self, message: str):
        """Initialize MindMeshError."""
        self.message = message
        super().__init__(self.message)

    def to_finding(
        self, endpoint: str, provider: str, model: str
    ) -> ErrorFinding:
        """Convert error to ErrorFinding."""
        return ErrorFinding(
            endpoint=endpoint,
            provider=provider,
            model=model,
            title=self.__class__.__name__,
            explanation=self.message,
            error_code=self.error_code,
            retryable=self.retryable,
        )


class ProviderTimeoutError(MindMeshError):
    """Raised when provider request times out."""

    error_code = "PROVIDER_TIMEOUT"
    retryable = True


class RateLimitError(MindMeshError):
    """Raised when rate limit is hit."""

    error_code = "RATE_LIMIT"
    retryable = True


class PolicyViolationError(MindMeshError):
    """Raised when policy is violated."""

    error_code = "POLICY_VIOLATION"
    retryable = False


class ProviderDisabledError(PolicyViolationError):
    """Raised when provider is explicitly disabled."""

    error_code = "PROVIDER_DISABLED"
    retryable = False

    def __init__(
        self,
        message: str,
        provider: str,
        requested_as: str,
        suggested_providers: list[str] | None = None,
    ):
        """Initialize ProviderDisabledError."""
        super().__init__(message)
        self.provider = provider
        self.requested_as = requested_as
        self.suggested_providers = suggested_providers or []


class DefaultProviderDisabledError(PolicyViolationError):
    """Raised when default provider is not available."""

    error_code = "DEFAULT_PROVIDER_DISABLED"
    retryable = False


class ParseError(MindMeshError):
    """Raised when parsing provider response fails."""

    error_code = "PARSE_ERROR"
    retryable = False


class ContextTooLargeError(MindMeshError):
    """Raised when context exceeds size limit."""

    error_code = "CONTEXT_TOO_LARGE"
    retryable = False


class SecretDetectedError(MindMeshError):
    """Raised when secret is detected in context."""

    error_code = "SECRET_DETECTED"
    retryable = False


class UnsupportedProviderError(MindMeshError):
    """Raised when provider is not supported."""

    error_code = "UNSUPPORTED_PROVIDER"
    retryable = False


class InvalidApiKeyError(MindMeshError):
    """Raised when API key is invalid."""

    error_code = "INVALID_API_KEY"
    retryable = False


class ModelUnavailableError(MindMeshError):
    """Raised when model is unavailable."""

    error_code = "MODEL_UNAVAILABLE"
    retryable = True


class PermissionDeniedError(PolicyViolationError):
    """Raised when operation is not permitted."""

    error_code = "PERMISSION_DENIED"
    retryable = False
