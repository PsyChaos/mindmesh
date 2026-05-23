"""delegate_task MCP tool — delegate a task to one or more endpoints."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mindmesh.config import MindMeshConfig, load_config
from mindmesh.tools.review import _run_review  # pyright: ignore[reportPrivateUsage]

_VALID_MODES = {"advisory", "analysis", "review", "planning", "patch_suggestion"}

_config: MindMeshConfig | None = None


def init_tools(config: MindMeshConfig) -> None:
    global _config
    _config = config


def _empty_result(summary: str) -> dict[str, Any]:
    from mindmesh.schemas import ToolResult

    return ToolResult(
        summary=summary,
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


def _resolve_endpoints(
    cfg: MindMeshConfig,
    endpoint: str | None,
    endpoints: list[str] | None,
    multi: bool,
) -> list[str]:
    if endpoints:
        return endpoints
    if endpoint:
        return [endpoint]
    if multi:
        return cfg.review.default_endpoints
    return cfg.review.default_endpoints[:1]


_TEMPLATE_FOR_MODE: dict[str, str] = {
    "planning": "plan",
}


async def delegate_task(
    task: str,
    endpoint: str | None = None,
    endpoints: list[str] | None = None,
    scope: str = "git_diff",
    mode: str = "advisory",
    allow_patch: bool = False,
    min_severity: str | None = None,
    dry_run: bool = False,
    no_cache: bool = False,
) -> dict[str, Any]:
    cfg = _config or load_config()

    if mode not in _VALID_MODES:
        return _empty_result(
            f"Invalid mode '{mode}'. Valid: {sorted(_VALID_MODES)}"
        )

    if allow_patch and not cfg.permissions.allow_external_patch:
        return _empty_result(
            "External patches not allowed by policy. "
            "Set allow_external_patch=true."
        )

    ep_list = _resolve_endpoints(
        cfg, endpoint, endpoints, multi=(mode == "planning"),
    )
    template = _TEMPLATE_FOR_MODE.get(mode, "delegate")

    return await _run_review(
        cfg,
        scope,
        ep_list,
        focus=None,
        template_name=template,
        template_kwargs={
            "task": task,
            "mode": mode,
            "allow_patch": allow_patch,
        },
        dry_run=dry_run,
        min_severity=min_severity,
        no_cache=no_cache,
    )


def register(mcp: FastMCP) -> None:
    mcp.tool()(delegate_task)
