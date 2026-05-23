"""SARIF v2.1.0 output formatter for GitHub Code Scanning."""

from __future__ import annotations

from typing import Any

from mindmesh.schemas import Finding

_SARIF_VERSION = "2.1.0"
_SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec"
    "/main/sarif-2.1/schema/sarif-schema-2.1.0.json"
)

_SEVERITY_TO_LEVEL: dict[str, str] = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}


def findings_to_sarif(
    findings: list[Finding],
    tool_name: str = "mindmesh",
    tool_version: str = "0.1.0",
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    rules: dict[str, dict[str, Any]] = {}

    for finding in findings:
        rule_id = f"{finding.category}/{finding.severity}"
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": rule_id},
            }

        result: dict[str, Any] = {
            "ruleId": rule_id,
            "level": _SEVERITY_TO_LEVEL.get(finding.severity, "note"),
            "message": {"text": finding.title},
            "properties": {
                "explanation": finding.explanation,
                "endpoint": finding.endpoint,
                "provider": finding.provider,
                "model": finding.model,
                "confidence": finding.confidence,
            },
        }
        if finding.recommendation:
            result["fixes"] = [{
                "description": {"text": finding.recommendation},
            }]

        if finding.file:
            phys: dict[str, Any] = {
                "artifactLocation": {"uri": finding.file},
            }
            if finding.line is not None:
                phys["region"] = {"startLine": finding.line}
            location: dict[str, Any] = {"physicalLocation": phys}
            result["locations"] = [location]

        results.append(result)

    return {
        "$schema": _SARIF_SCHEMA,
        "version": _SARIF_VERSION,
        "runs": [{
            "tool": {
                "driver": {
                    "name": tool_name,
                    "version": tool_version,
                    "rules": list(rules.values()),
                },
            },
            "results": results,
        }],
    }
