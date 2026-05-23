"""compare_providers MCP tool — sends the same task to multiple endpoints for comparison."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mindmesh.config import MindMeshConfig, load_config
from mindmesh.schemas import ToolResult
from mindmesh.tools.review import _run_review  # pyright: ignore[reportPrivateUsage]

_config: MindMeshConfig | None = None


def init_tools(config: MindMeshConfig) -> None:
    global _config
    _config = config


async def compare_providers(
    task: str,
    scope: str = "git_diff",
    endpoints: list[str] | None = None,
    min_severity: str | None = None,
    dry_run: bool = False,
    no_cache: bool = False,
) -> dict[str, Any]:
    cfg = _config or load_config()
    ep_list = endpoints or cfg.review.default_endpoints
    if len(ep_list) < 2:
        return ToolResult(
            summary="Compare requires at least 2 endpoints.",
            findings=[],
            endpoint_errors=[],
            match_hints=[],
            metadata={
                "endpoints_called": 0,
                "endpoints_succeeded": 0,
                "total_findings": 0,
                "context_size_kb": 0.0,
                "redacted_secrets": 0,
            },
        ).model_dump()
    return await _run_review(
        cfg,
        scope,
        ep_list,
        focus=None,
        template_name="compare",
        template_kwargs={"question": task},
        dry_run=dry_run,
        min_severity=min_severity,
        no_cache=no_cache,
    )


def register(mcp: FastMCP) -> None:
    mcp.tool()(compare_providers)
