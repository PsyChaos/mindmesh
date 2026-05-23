"""local_scan MCP tool — run local security scanners without LLM calls."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from mindmesh.config import MindMeshConfig
from mindmesh.output.merger import FindingsMerger
from mindmesh.output.report import Reporter
from mindmesh.scanners.base import Scanner, get_available_scanners
from mindmesh.schemas import EndpointError, Finding, PolicyReport

_config: MindMeshConfig | None = None


def init_tools(config: MindMeshConfig) -> None:
    global _config
    _config = config


async def local_scan(
    target: str = ".",
    scanner: str | None = None,
    min_severity: str | None = None,
) -> dict[str, Any]:
    available = get_available_scanners()

    if not available:
        return {
            "error": "No scanners found. Install bandit or semgrep.",
            "available_scanners": [],
        }

    if scanner:
        matched = [s for s in available if s.name == scanner]
        if not matched:
            names = [s.name for s in available]
            return {
                "error": f"Scanner '{scanner}' not found. Available: {names}",
                "available_scanners": names,
            }
        scanners_to_run = matched
    else:
        scanners_to_run = available

    findings_by_scanner: dict[str, list[Finding]] = {}
    errors: list[EndpointError] = []

    async def _run_scanner(s: Scanner) -> None:
        try:
            results = await s.run(target)
            findings_by_scanner[f"local:{s.name}"] = results
        except Exception as exc:
            errors.append(EndpointError(
                endpoint=f"local:{s.name}",
                error_code="SCANNER_ERROR",
                message=str(exc),
                retryable=False,
            ))

    await asyncio.gather(*[_run_scanner(s) for s in scanners_to_run])

    merge_result = FindingsMerger().merge(findings_by_scanner)
    policy_report = PolicyReport(
        checked_providers=[],
        blocked_providers=[],
        allowed_providers=[],
        permission_warnings=[],
        file_policy_blocked=[],
        redacted_secret_count=0,
    )
    result = Reporter().build(
        merge_result, errors, [], 0.0, policy_report,
        min_severity=min_severity,
    )
    return result.model_dump()


def register(mcp: FastMCP) -> None:
    mcp.tool()(local_scan)
