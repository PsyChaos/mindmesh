"""Shared Pydantic models for inter-layer communication."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Message for provider communication."""

    role: Literal["system", "user"]
    content: str


class Finding(BaseModel):
    """Analysis finding from a provider."""

    endpoint: str
    provider: str
    model: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: Literal[
        "bug",
        "security",
        "performance",
        "architecture",
        "maintainability",
        "testing",
        "documentation",
        "style",
        "system",
    ]
    file: str | None = None
    line: int | None = None
    title: str
    explanation: str
    recommendation: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)


class ErrorFinding(Finding):
    """Error finding from a provider."""

    error_code: str
    retryable: bool = False
    severity: Literal["critical", "high", "medium", "low", "info"] = "info"
    category: Literal[
        "bug",
        "security",
        "performance",
        "architecture",
        "maintainability",
        "testing",
        "documentation",
        "style",
        "system",
    ] = "system"
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class MatchHint(BaseModel):
    """Hint for merging findings."""

    finding_indices: list[int]
    reason: str


class EndpointError(BaseModel):
    """Error from an endpoint."""

    endpoint: str
    error_code: str
    message: str
    retryable: bool


class PolicyReport(BaseModel):
    """Structured policy check results for a tool run."""

    checked_providers: list[str]
    blocked_providers: list[dict[str, str]]  # {provider, reason, error_code}
    allowed_providers: list[str]
    permission_warnings: list[dict[str, str]]  # {warning, details}
    file_policy_blocked: list[str]
    redacted_secret_count: int


class ToolResult(BaseModel):
    """Result from a tool."""

    summary: str
    findings: list[Finding] = []
    endpoint_errors: list[EndpointError] = []
    match_hints: list[MatchHint] = []
    metadata: dict[str, Any] = Field(default_factory=dict)
    policy_report: dict[str, Any] | None = None


class RedactionFinding(BaseModel):
    """Finding for redacted secret."""

    file: str
    line: int
    pattern: str
    category: str = ""
    action: Literal["redacted"] = "redacted"
