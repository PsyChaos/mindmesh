"""Final JSON report production from merged findings."""

from mindmesh.output.merger import MergeResult
from mindmesh.schemas import EndpointError, PolicyReport, RedactionFinding, ToolResult

_SEVERITY_RANK: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


class Reporter:
    def build(
        self,
        merge_result: MergeResult,
        endpoint_errors: list[EndpointError],
        redaction_findings: list[RedactionFinding],
        context_size_kb: float,
        policy_report: PolicyReport | None = None,
        min_severity: str | None = None,
    ) -> ToolResult:
        findings = merge_result.all_findings
        if min_severity and min_severity in _SEVERITY_RANK:
            threshold = _SEVERITY_RANK[min_severity]
            findings = [f for f in findings if self._severity_order(f.severity) <= threshold]
        sorted_findings = sorted(
            findings,
            key=lambda f: self._severity_order(f.severity),
        )
        endpoints_called = len(merge_result.endpoints_represented) + len(endpoint_errors)
        endpoints_succeeded = len(merge_result.endpoints_represented)
        redacted = len(redaction_findings)

        summary_parts = [
            f"{endpoints_called} endpoint çağrıldı, {len(sorted_findings)} finding bulundu."
        ]
        if endpoint_errors:
            summary_parts.append(f"{len(endpoint_errors)} endpoint hata döndürdü.")
        if redacted:
            summary_parts.append(f"{redacted} secret redacted edildi.")

        return ToolResult(
            summary=" ".join(summary_parts),
            findings=sorted_findings,
            endpoint_errors=endpoint_errors,
            match_hints=merge_result.match_hints,
            metadata={
                "endpoints_called": endpoints_called,
                "endpoints_succeeded": endpoints_succeeded,
                "total_findings": len(sorted_findings),
                "context_size_kb": context_size_kb,
                "redacted_secrets": redacted,
            },
            policy_report=policy_report.model_dump() if policy_report is not None else None,
        )

    def _severity_order(self, severity: str) -> int:
        return _SEVERITY_RANK.get(severity, 99)
