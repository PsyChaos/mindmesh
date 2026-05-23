"""security_audit MCP tool — orchestrates security analysis pipeline."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mindmesh.config import MindMeshConfig, load_config
from mindmesh.tools.review import _run_review  # pyright: ignore[reportPrivateUsage]

_DEFAULT_SECURITY_FOCUS = [
    "authentication",
    "authorization",
    "injection",
    "secrets",
    "ssrf",
    "path_traversal",
]
_config: MindMeshConfig | None = None


def init_tools(config: MindMeshConfig) -> None:
    global _config
    _config = config


async def security_audit(
    scope: str = "git_diff",
    endpoints: list[str] | None = None,
    focus: list[str] | None = None,
    dry_run: bool = False,
    min_severity: str | None = None,
    no_cache: bool = False,
) -> dict[str, Any]:
    cfg = _config or load_config()
    return await _run_review(
        cfg,
        scope,
        endpoints,
        focus or _DEFAULT_SECURITY_FOCUS,
        template_name="security",
        dry_run=dry_run,
        min_severity=min_severity,
        no_cache=no_cache,
    )


def register(mcp: FastMCP) -> None:
    mcp.tool()(security_audit)
