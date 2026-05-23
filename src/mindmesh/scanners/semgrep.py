"""Semgrep scanner — multi-language static analysis."""

from __future__ import annotations

import json
from typing import Any

from mindmesh.scanners.base import Scanner
from mindmesh.schemas import Finding

_SEVERITY_MAP: dict[str, str] = {
    "ERROR": "high",
    "WARNING": "medium",
    "INFO": "low",
}


class SemgrepScanner(Scanner):
    name = "semgrep"

    async def run(self, target: str) -> list[Finding]:
        _, stdout, _ = await self._exec(
            "semgrep", "scan", "--json", "--quiet", target,
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
            extra: dict[str, Any] = r.get("extra", {})
            severity = _SEVERITY_MAP.get(
                extra.get("severity", ""), "info",
            )
            findings.append(Finding(
                endpoint="local:semgrep",
                provider="semgrep",
                model="semgrep",
                severity=severity,  # type: ignore[arg-type]
                category="security",
                file=r.get("path"),
                line=r.get("start", {}).get("line"),
                title=r.get("check_id", "unknown"),
                explanation=extra.get("message", ""),
                recommendation=extra.get("fix"),
                confidence=0.85,
            ))
        return findings
