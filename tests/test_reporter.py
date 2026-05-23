"""Tests for Reporter."""

import pytest

from mindmesh.output.merger import MergeResult
from mindmesh.output.report import Reporter
from mindmesh.schemas import EndpointError, Finding, MatchHint, RedactionFinding


def make_finding(severity: str = "medium", endpoint: str = "ep1") -> Finding:
    return Finding(
        endpoint=endpoint,
        provider="openai",
        model="gpt-4o",
        severity=severity,  # type: ignore[arg-type]
        category="bug",
        file="src/main.py",
        line=10,
        title="Issue",
        explanation="Something is wrong.",
        confidence=0.9,
    )


def make_merge_result(
    findings: list[Finding] | None = None,
    match_hints: list[MatchHint] | None = None,
    endpoints: list[str] | None = None,
) -> MergeResult:
    findings = findings or []
    endpoints = endpoints or (["ep1"] if findings else [])
    per_ep: dict[str, int] = {}
    for ep in endpoints:
        per_ep[ep] = sum(1 for f in findings if f.endpoint == ep)
    return MergeResult(
        all_findings=findings,
        match_hints=match_hints or [],
        endpoints_represented=endpoints,
        findings_per_endpoint=per_ep,
    )


def make_error(endpoint: str = "ep_err") -> EndpointError:
    return EndpointError(
        endpoint=endpoint,
        error_code="timeout",
        message="Request timed out.",
        retryable=True,
    )


def make_redaction(file: str = "src/main.py", line: int = 5) -> RedactionFinding:
    return RedactionFinding(file=file, line=line, pattern="api_key")


@pytest.fixture
def reporter() -> Reporter:
    return Reporter()


# --- Empty inputs ---

def test_empty_findings_and_errors(reporter: Reporter) -> None:
    result = reporter.build(make_merge_result(), [], [], 10.0)
    assert result.findings == []
    assert result.endpoint_errors == []
    assert result.match_hints == []
    assert result.summary


def test_empty_metadata_counts(reporter: Reporter) -> None:
    result = reporter.build(make_merge_result(endpoints=[]), [], [], 0.0)
    assert result.metadata["endpoints_called"] == 0
    assert result.metadata["endpoints_succeeded"] == 0
    assert result.metadata["total_findings"] == 0
    assert result.metadata["redacted_secrets"] == 0


# --- Severity sorting ---

def test_findings_sorted_by_severity(reporter: Reporter) -> None:
    findings = [
        make_finding("info"),
        make_finding("low"),
        make_finding("critical"),
        make_finding("high"),
        make_finding("medium"),
    ]
    result = reporter.build(make_merge_result(findings, endpoints=["ep1"]), [], [], 0.0)
    severities = [f.severity for f in result.findings]
    assert severities == ["critical", "high", "medium", "low", "info"]


def test_critical_first_info_last(reporter: Reporter) -> None:
    findings = [make_finding("info"), make_finding("critical")]
    result = reporter.build(make_merge_result(findings, endpoints=["ep1"]), [], [], 0.0)
    assert result.findings[0].severity == "critical"
    assert result.findings[-1].severity == "info"


def test_mixed_severity_stable_order(reporter: Reporter) -> None:
    findings = [make_finding("high"), make_finding("medium"), make_finding("high")]
    result = reporter.build(make_merge_result(findings, endpoints=["ep1"]), [], [], 0.0)
    severities = [f.severity for f in result.findings]
    assert severities == ["high", "high", "medium"]


# --- Endpoint errors ---

def test_endpoint_errors_passed_through(reporter: Reporter) -> None:
    errors = [make_error("ep_bad")]
    result = reporter.build(make_merge_result(), errors, [], 0.0)
    assert len(result.endpoint_errors) == 1
    assert result.endpoint_errors[0].endpoint == "ep_bad"


def test_only_errors_no_findings(reporter: Reporter) -> None:
    errors = [make_error()]
    result = reporter.build(make_merge_result(endpoints=[]), errors, [], 5.0)
    assert result.findings == []
    assert len(result.endpoint_errors) == 1


# --- Metadata ---

def test_endpoints_called_includes_errors(reporter: Reporter) -> None:
    findings = [make_finding(endpoint="ep1")]
    merge = make_merge_result(findings, endpoints=["ep1"])
    errors = [make_error("ep2"), make_error("ep3")]
    result = reporter.build(merge, errors, [], 0.0)
    assert result.metadata["endpoints_called"] == 3
    assert result.metadata["endpoints_succeeded"] == 1


def test_total_findings_count(reporter: Reporter) -> None:
    findings = [make_finding(), make_finding(), make_finding()]
    result = reporter.build(make_merge_result(findings, endpoints=["ep1"]), [], [], 0.0)
    assert result.metadata["total_findings"] == 3


def test_context_size_kb_in_metadata(reporter: Reporter) -> None:
    result = reporter.build(make_merge_result(), [], [], 42.5)
    assert result.metadata["context_size_kb"] == 42.5


def test_redacted_secrets_count(reporter: Reporter) -> None:
    redactions = [make_redaction(), make_redaction(line=20)]
    result = reporter.build(make_merge_result(), [], redactions, 0.0)
    assert result.metadata["redacted_secrets"] == 2


# --- Summary text ---

def test_summary_contains_endpoint_and_finding_counts(reporter: Reporter) -> None:
    findings = [make_finding()]
    merge = make_merge_result(findings, endpoints=["ep1"])
    result = reporter.build(merge, [], [], 0.0)
    assert "1" in result.summary
    assert "finding" in result.summary.lower() or "endpoint" in result.summary.lower()


def test_summary_mentions_errors_when_present(reporter: Reporter) -> None:
    errors = [make_error()]
    result = reporter.build(make_merge_result(endpoints=[]), errors, [], 0.0)
    assert "hata" in result.summary.lower() or "error" in result.summary.lower()


def test_summary_mentions_redaction_when_present(reporter: Reporter) -> None:
    result = reporter.build(make_merge_result(), [], [make_redaction()], 0.0)
    assert "redact" in result.summary.lower() or "secret" in result.summary.lower()


def test_summary_no_error_mention_when_no_errors(reporter: Reporter) -> None:
    result = reporter.build(make_merge_result(endpoints=["ep1"]), [], [], 0.0)
    assert "hata" not in result.summary.lower() or "0 endpoint" not in result.summary


# --- Match hints passthrough ---

def test_match_hints_passed_through(reporter: Reporter) -> None:
    hint = MatchHint(finding_indices=[0, 1], reason="same file + line range + bug")
    merge = make_merge_result(match_hints=[hint])
    result = reporter.build(merge, [], [], 0.0)
    assert len(result.match_hints) == 1
    assert result.match_hints[0].finding_indices == [0, 1]


# --- min_severity filter ---

def test_min_severity_high_filters_medium_low_info(reporter: Reporter) -> None:
    findings = [
        make_finding("critical"),
        make_finding("high"),
        make_finding("medium"),
        make_finding("low"),
        make_finding("info"),
    ]
    merge = make_merge_result(findings, endpoints=["ep1"])
    result = reporter.build(merge, [], [], 0.0, min_severity="high")
    severities = [f.severity for f in result.findings]
    assert severities == ["critical", "high"]


def test_min_severity_medium_keeps_critical_high_medium(reporter: Reporter) -> None:
    findings = [
        make_finding("critical"),
        make_finding("high"),
        make_finding("medium"),
        make_finding("low"),
    ]
    merge = make_merge_result(findings, endpoints=["ep1"])
    result = reporter.build(merge, [], [], 0.0, min_severity="medium")
    severities = [f.severity for f in result.findings]
    assert severities == ["critical", "high", "medium"]


def test_min_severity_critical_only(reporter: Reporter) -> None:
    findings = [make_finding("critical"), make_finding("high"), make_finding("info")]
    merge = make_merge_result(findings, endpoints=["ep1"])
    result = reporter.build(merge, [], [], 0.0, min_severity="critical")
    assert len(result.findings) == 1
    assert result.findings[0].severity == "critical"


def test_min_severity_none_keeps_all(reporter: Reporter) -> None:
    findings = [make_finding("critical"), make_finding("info")]
    merge = make_merge_result(findings, endpoints=["ep1"])
    result = reporter.build(merge, [], [], 0.0, min_severity=None)
    assert len(result.findings) == 2


def test_min_severity_invalid_keeps_all(reporter: Reporter) -> None:
    findings = [make_finding("critical"), make_finding("info")]
    merge = make_merge_result(findings, endpoints=["ep1"])
    result = reporter.build(merge, [], [], 0.0, min_severity="bogus")
    assert len(result.findings) == 2


def test_min_severity_updates_metadata_count(reporter: Reporter) -> None:
    findings = [make_finding("critical"), make_finding("low"), make_finding("info")]
    merge = make_merge_result(findings, endpoints=["ep1"])
    result = reporter.build(merge, [], [], 0.0, min_severity="high")
    assert result.metadata["total_findings"] == 1
