"""bug_investigate MCP tool — orchestrates bug investigation pipeline."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mindmesh.config import MindMeshConfig, load_config
from mindmesh.tools.review import _run_review  # pyright: ignore[reportPrivateUsage]

_config: MindMeshConfig | None = None


def init_tools(config: MindMeshConfig) -> None:
    global _config
    _config = config


async def bug_investigate(
    issue: str,
    scope: str = "git_diff",
    endpoints: list[str] | None = None,
    logs: str | None = None,
    dry_run: bool = False,
    min_severity: str | None = None,
    no_cache: bool = False,
) -> dict[str, Any]:
    cfg = _config or load_config()
    return await _run_review(
        cfg,
        scope,
        endpoints,
        focus=None,
        template_name="bug_investigate",
        template_kwargs={"issue": issue, "logs": logs},
        dry_run=dry_run,
        min_severity=min_severity,
        no_cache=no_cache,
    )


def register(mcp: FastMCP) -> None:
    mcp.tool()(bug_investigate)
