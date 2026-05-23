"""Bandit scanner — Python security linter."""

from __future__ import annotations

import json
from typing import Any

from mindmesh.scanners.base import Scanner
from mindmesh.schemas import Finding

_SEVERITY_MAP: dict[str, str] = {
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
}

_CONFIDENCE_MAP: dict[str, float] = {
    "HIGH": 0.9,
    "MEDIUM": 0.7,
    "LOW": 0.4,
}


class BanditScanner(Scanner):
    name = "bandit"

    async def run(self, target: str) -> list[Finding]:
        _, stdout, _ = await self._exec(
            "bandit", "-r", target, "-f", "json", "-q",
        )
        if not stdout.strip():
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return []

        results: list[Any] = data.get("results", [])
        findings: list[Finding] = []
        for r in results:
            severity = _SEVERITY_MAP.get(
                r.get("issue_severity", ""), "info",
            )
            confidence = _CONFIDENCE_MAP.get(
                r.get("issue_confidence", ""), 0.5,
            )
            findings.append(Finding(
                endpoint="local:bandit",
                provider="bandit",
                model="bandit",
                severity=severity,  # type: ignore[arg-type]
                category="security",
                file=r.get("filename"),
                line=r.get("line_number"),
                title=f"[{r.get('test_id', '?')}] {r.get('test_name', '?')}",
                explanation=r.get("issue_text", ""),
                recommendation=r.get("more_info"),
                confidence=confidence,
            ))
        return findings
