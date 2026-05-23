from __future__ import annotations

import json
import re
from typing import Any, cast

from mindmesh.schemas import Finding

_VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
_VALID_CATEGORIES = {
    "bug", "security", "performance", "architecture",
    "maintainability", "testing", "documentation", "style", "system",
}
_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


class ResponseNormalizer:
    def parse(
        self, raw: str, endpoint: str, provider: str, model: str
    ) -> list[Finding] | None:
        stripped = self.strip_code_fence(raw)
        try:
            data = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return None

        items: list[Any]
        if isinstance(data, list):
            items = cast(list[Any], data)
        elif isinstance(data, dict):
            raw_findings: Any = cast(dict[str, Any], data).get("findings", [])
            items = cast(list[Any], raw_findings) if isinstance(raw_findings, list) else []
        else:
            return None

        findings: list[Finding] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            finding = self._coerce_finding(cast(dict[str, Any], item), endpoint, provider, model)
            if finding is not None:
                findings.append(finding)
        return findings

    def strip_code_fence(self, raw: str) -> str:
        match = _FENCE_RE.search(raw)
        return match.group(1) if match else raw

    def make_parse_error_finding(
        self, endpoint: str, provider: str, model: str, error: str
    ) -> Finding:
        return Finding(
            endpoint=endpoint,
            provider=provider,
            model=model,
            severity="info",
            category="system",
            title="Parse error",
            explanation=error,
            confidence=1.0,
        )

    def _coerce_finding(
        self, item: dict[str, Any], endpoint: str, provider: str, model: str
    ) -> Finding | None:
        severity = item.get("severity", "info")
        if severity not in _VALID_SEVERITIES:
            severity = "info"

        category = item.get("category", "bug")
        if category not in _VALID_CATEGORIES:
            category = "bug"

        confidence = item.get("confidence", 0.5)
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.5

        title = item.get("title", "")
        explanation = item.get("explanation", "")
        if not title or not explanation:
            return None

        return Finding(
            endpoint=endpoint,
            provider=provider,
            model=model,
            severity=severity,
            category=category,
            file=item.get("file"),
            line=item.get("line"),
            title=title,
            explanation=explanation,
            recommendation=item.get("recommendation"),
            confidence=confidence,
        )
