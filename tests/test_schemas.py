"""Tests for MindMesh schemas."""

from typing import Any, cast

import pytest
from pydantic import ValidationError

from mindmesh.schemas import (
    EndpointError,
    ErrorFinding,
    Finding,
    MatchHint,
    Message,
    RedactionFinding,
    ToolResult,
)


class TestMessage:
    """Tests for Message model."""

    def test_create_system_message(self):
        """Test creating system message."""
        msg = Message(role="system", content="You are a code reviewer")
        assert msg.role == "system"
        assert msg.content == "You are a code reviewer"

    def test_create_user_message(self):
        """Test creating user message."""
        msg = Message(role="user", content="Review this code")
        assert msg.role == "user"
        assert msg.content == "Review this code"

    def test_invalid_role(self):
        """Test that invalid role raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Message(role=cast(Any, "assistant"), content="Hello")
        assert "role" in str(exc_info.value)

    def test_message_json_serialization(self):
        """Test JSON serialization/deserialization."""
        msg = Message(role="user", content="Test")
        json_str = msg.model_dump_json()
        loaded = Message.model_validate_json(json_str)
        assert loaded.role == msg.role
        assert loaded.content == msg.content


class TestFinding:
    """Tests for Finding model."""

    def test_create_finding_minimal(self):
        """Test creating Finding with required fields."""
        finding = Finding(
            endpoint="openai:gpt-4",
            provider="openai",
            model="gpt-4",
            severity="high",
            category="bug",
            title="Test bug",
            explanation="This is a test bug",
        )
        assert finding.endpoint == "openai:gpt-4"
        assert finding.severity == "high"
        assert finding.confidence == 0.8  # default value

    def test_create_finding_with_location(self):
        """Test creating Finding with file and line."""
        finding = Finding(
            endpoint="openai:gpt-4",
            provider="openai",
            model="gpt-4",
            severity="medium",
            category="maintainability",
            file="src/auth.py",
            line=42,
            title="Long function",
            explanation="Function is too long",
            recommendation="Split into smaller functions",
        )
        assert finding.file == "src/auth.py"
        assert finding.line == 42
        assert finding.recommendation is not None

    def test_all_severities(self):
        """Test all valid severity levels."""
        for severity in ["critical", "high", "medium", "low", "info"]:
            finding = Finding(
                endpoint="test",
                provider="test",
                model="test",
                severity=cast(Any, severity),
                category="bug",
                title="Test",
                explanation="Test",
            )
            assert finding.severity == severity

    def test_all_categories(self):
        """Test all valid categories."""
        categories = [
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
        for category in categories:
            finding = Finding(
                endpoint="test",
                provider="test",
                model="test",
                severity="low",
                category=cast(Any, category),
                title="Test",
                explanation="Test",
            )
            assert finding.category == category

    def test_invalid_severity(self):
        """Test that invalid severity raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Finding(
                endpoint="test",
                provider="test",
                model="test",
                severity=cast(Any, "critical_error"),
                category="bug",
                title="Test",
                explanation="Test",
            )
        assert "severity" in str(exc_info.value)

    def test_invalid_category(self):
        """Test that invalid category raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Finding(
                endpoint="test",
                provider="test",
                model="test",
                severity="high",
                category=cast(Any, "invalid"),
                title="Test",
                explanation="Test",
            )
        assert "category" in str(exc_info.value)

    def test_confidence_zero(self):
        """Test confidence at lower bound."""
        finding = Finding(
            endpoint="test",
            provider="test",
            model="test",
            severity="low",
            category="bug",
            title="Test",
            explanation="Test",
            confidence=0.0,
        )
        assert finding.confidence == 0.0

    def test_confidence_one(self):
        """Test confidence at upper bound."""
        finding = Finding(
            endpoint="test",
            provider="test",
            model="test",
            severity="low",
            category="bug",
            title="Test",
            explanation="Test",
            confidence=1.0,
        )
        assert finding.confidence == 1.0

    def test_confidence_mid_range(self):
        """Test confidence in mid-range."""
        finding = Finding(
            endpoint="test",
            provider="test",
            model="test",
            severity="low",
            category="bug",
            title="Test",
            explanation="Test",
            confidence=0.5,
        )
        assert finding.confidence == 0.5

    def test_confidence_below_zero(self):
        """Test that confidence below 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            Finding(
                endpoint="test",
                provider="test",
                model="test",
                severity="low",
                category="bug",
                title="Test",
                explanation="Test",
                confidence=-0.1,
            )

    def test_confidence_above_one(self):
        """Test that confidence above 1 raises ValidationError."""
        with pytest.raises(ValidationError):
            Finding(
                endpoint="test",
                provider="test",
                model="test",
                severity="low",
                category="bug",
                title="Test",
                explanation="Test",
                confidence=1.1,
            )

    def test_finding_json_serialization(self):
        """Test JSON serialization/deserialization."""
        finding = Finding(
            endpoint="openai:gpt-4",
            provider="openai",
            model="gpt-4",
            severity="high",
            category="security",
            file="src/auth.py",
            line=10,
            title="SQL Injection",
            explanation="User input not escaped",
            recommendation="Use parameterized queries",
            confidence=0.95,
        )
        json_str = finding.model_dump_json()
        loaded = Finding.model_validate_json(json_str)
        assert loaded.endpoint == finding.endpoint
        assert loaded.severity == finding.severity
        assert loaded.file == finding.file
        assert loaded.confidence == finding.confidence


class TestErrorFinding:
    """Tests for ErrorFinding model."""

    def test_create_error_finding(self):
        """Test creating ErrorFinding."""
        error = ErrorFinding(
            endpoint="openai:gpt-4",
            provider="openai",
            model="gpt-4",
            title="Provider timeout",
            explanation="Request timed out",
            error_code="TIMEOUT",
        )
        assert error.error_code == "TIMEOUT"
        assert error.severity == "info"
        assert error.category == "system"
        assert error.confidence == 1.0

    def test_error_finding_retryable(self):
        """Test ErrorFinding with retryable flag."""
        error = ErrorFinding(
            endpoint="openai:gpt-4",
            provider="openai",
            model="gpt-4",
            title="Rate limited",
            explanation="Hit rate limit",
            error_code="RATE_LIMIT",
            retryable=True,
        )
        assert error.retryable is True

    def test_error_finding_non_retryable(self):
        """Test ErrorFinding non-retryable."""
        error = ErrorFinding(
            endpoint="openai:gpt-4",
            provider="openai",
            model="gpt-4",
            title="Invalid API key",
            explanation="API key not valid",
            error_code="INVALID_KEY",
            retryable=False,
        )
        assert error.retryable is False

    def test_error_finding_inherits_from_finding(self):
        """Test that ErrorFinding is a Finding."""
        error = ErrorFinding(
            endpoint="test",
            provider="test",
            model="test",
            title="Error",
            explanation="Test error",
            error_code="TEST",
        )
        assert isinstance(error, Finding)

    def test_error_finding_json_serialization(self):
        """Test JSON serialization/deserialization."""
        error = ErrorFinding(
            endpoint="openai:gpt-4",
            provider="openai",
            model="gpt-4",
            title="Provider error",
            explanation="Something went wrong",
            error_code="ERROR",
            retryable=True,
        )
        json_str = error.model_dump_json()
        loaded = ErrorFinding.model_validate_json(json_str)
        assert loaded.error_code == error.error_code
        assert loaded.retryable == error.retryable


class TestMatchHint:
    """Tests for MatchHint model."""

    def test_create_match_hint(self):
        """Test creating MatchHint."""
        hint = MatchHint(finding_indices=[0, 3, 5], reason="Same file and line range")
        assert hint.finding_indices == [0, 3, 5]
        assert hint.reason == "Same file and line range"

    def test_match_hint_empty_list(self):
        """Test MatchHint with empty finding_indices."""
        hint = MatchHint(finding_indices=[], reason="No matches")
        assert hint.finding_indices == []

    def test_match_hint_single_index(self):
        """Test MatchHint with single index."""
        hint = MatchHint(finding_indices=[0], reason="Single match")
        assert hint.finding_indices == [0]


class TestEndpointError:
    """Tests for EndpointError model."""

    def test_create_endpoint_error(self):
        """Test creating EndpointError."""
        error = EndpointError(
            endpoint="openai:gpt-4",
            error_code="TIMEOUT",
            message="Request timed out after 30s",
            retryable=True,
        )
        assert error.endpoint == "openai:gpt-4"
        assert error.error_code == "TIMEOUT"
        assert error.retryable is True

    def test_endpoint_error_non_retryable(self):
        """Test non-retryable endpoint error."""
        error = EndpointError(
            endpoint="gemini:2.5",
            error_code="INVALID_KEY",
            message="API key is invalid",
            retryable=False,
        )
        assert error.retryable is False


class TestToolResult:
    """Tests for ToolResult model."""

    def test_create_tool_result_empty(self):
        """Test creating ToolResult with no findings."""
        result = ToolResult(summary="No issues found")
        assert result.summary == "No issues found"
        assert result.findings == []
        assert result.endpoint_errors == []
        assert result.match_hints == []
        assert result.metadata == {}

    def test_tool_result_with_findings(self):
        """Test ToolResult with findings."""
        finding = Finding(
            endpoint="openai:gpt-4",
            provider="openai",
            model="gpt-4",
            severity="high",
            category="bug",
            title="Test bug",
            explanation="Test explanation",
        )
        result = ToolResult(
            summary="Found 1 issue",
            findings=[finding],
        )
        assert len(result.findings) == 1
        assert result.findings[0].title == "Test bug"

    def test_tool_result_with_errors(self):
        """Test ToolResult with endpoint errors."""
        error = EndpointError(
            endpoint="openai:gpt-4",
            error_code="TIMEOUT",
            message="Request timed out",
            retryable=True,
        )
        result = ToolResult(
            summary="Partial failure",
            endpoint_errors=[error],
        )
        assert len(result.endpoint_errors) == 1

    def test_tool_result_with_match_hints(self):
        """Test ToolResult with match hints."""
        hint = MatchHint(finding_indices=[0, 2], reason="Same category")
        result = ToolResult(
            summary="With hints",
            match_hints=[hint],
        )
        assert len(result.match_hints) == 1

    def test_tool_result_with_metadata(self):
        """Test ToolResult with metadata."""
        metadata = {"endpoints_called": 3, "endpoints_succeeded": 2}
        result = ToolResult(
            summary="Summary",
            metadata=metadata,
        )
        assert result.metadata["endpoints_called"] == 3

    def test_tool_result_json_serialization(self):
        """Test JSON serialization/deserialization."""
        finding = Finding(
            endpoint="test",
            provider="test",
            model="test",
            severity="low",
            category="bug",
            title="Test",
            explanation="Test",
        )
        result = ToolResult(
            summary="Test",
            findings=[finding],
            metadata={"key": "value"},
        )
        json_str = result.model_dump_json()
        loaded = ToolResult.model_validate_json(json_str)
        assert loaded.summary == result.summary
        assert len(loaded.findings) == 1
        assert loaded.metadata["key"] == "value"


class TestRedactionFinding:
    """Tests for RedactionFinding model."""

    def test_create_redaction_finding(self):
        """Test creating RedactionFinding."""
        redaction = RedactionFinding(
            file="src/config.py",
            line=15,
            pattern="api_key",
        )
        assert redaction.file == "src/config.py"
        assert redaction.line == 15
        assert redaction.pattern == "api_key"
        assert redaction.action == "redacted"

    def test_redaction_finding_default_action(self):
        """Test RedactionFinding action defaults to redacted."""
        redaction = RedactionFinding(
            file="src/secret.py",
            line=20,
            pattern="password",
        )
        assert redaction.action == "redacted"

    def test_redaction_finding_json_serialization(self):
        """Test JSON serialization/deserialization."""
        redaction = RedactionFinding(
            file="src/env.py",
            line=5,
            pattern="token",
        )
        json_str = redaction.model_dump_json()
        loaded = RedactionFinding.model_validate_json(json_str)
        assert loaded.file == redaction.file
        assert loaded.line == redaction.line
        assert loaded.pattern == redaction.pattern


class TestIntegration:
    """Integration tests combining multiple models."""

    def test_finding_list_serialization(self):
        """Test serializing list of findings."""
        findings = [
            Finding(
                endpoint="openai:gpt-4",
                provider="openai",
                model="gpt-4",
                severity="high",
                category="security",
                title="SQL Injection",
                explanation="User input not escaped",
            ),
            Finding(
                endpoint="gemini:2.5",
                provider="gemini",
                model="gemini-2.5",
                severity="medium",
                category="performance",
                title="Slow query",
                explanation="N+1 query detected",
            ),
        ]
        result = ToolResult(
            summary="Found 2 issues",
            findings=findings,
        )
        json_str = result.model_dump_json()
        loaded = ToolResult.model_validate_json(json_str)
        assert len(loaded.findings) == 2
        assert loaded.findings[0].severity == "high"
        assert loaded.findings[1].severity == "medium"

    def test_complex_tool_result(self):
        """Test ToolResult with all fields populated."""
        findings = [
            Finding(
                endpoint="openai:gpt-4",
                provider="openai",
                model="gpt-4",
                severity="critical",
                category="security",
                file="auth.py",
                line=10,
                title="Hardcoded secret",
                explanation="API key hardcoded",
                recommendation="Use environment variables",
                confidence=0.99,
            ),
        ]
        errors = [
            EndpointError(
                endpoint="gemini:2.5",
                error_code="TIMEOUT",
                message="Request timed out",
                retryable=True,
            ),
        ]
        hints = [
            MatchHint(finding_indices=[0], reason="Same file"),
        ]
        result = ToolResult(
            summary="Review complete",
            findings=findings,
            endpoint_errors=errors,
            match_hints=hints,
            metadata={
                "endpoints_called": 2,
                "endpoints_succeeded": 1,
                "context_size_kb": 50,
            },
        )
        json_str = result.model_dump_json()
        loaded = ToolResult.model_validate_json(json_str)
        assert len(loaded.findings) == 1
        assert len(loaded.endpoint_errors) == 1
        assert len(loaded.match_hints) == 1
        assert loaded.metadata["endpoints_called"] == 2
