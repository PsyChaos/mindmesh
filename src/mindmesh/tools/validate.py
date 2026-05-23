"""validate_policy MCP tool — check policy/config without provider calls."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mindmesh.config import MindMeshConfig, load_config, resolve_alias
from mindmesh.errors import MindMeshError
from mindmesh.policy.file_policy import FilePolicy
from mindmesh.policy.permission_policy import PermissionPolicy
from mindmesh.policy.provider_policy import ProviderPolicy
from mindmesh.providers.base import EndpointResolver

_config: MindMeshConfig | None = None


def init_tools(config: MindMeshConfig) -> None:
    global _config
    _config = config


async def validate_policy(
    endpoints: list[str] | None = None,
    paths: list[str] | None = None,
) -> dict[str, Any]:
    cfg = _config or load_config()
    endpoint_names = endpoints or cfg.review.default_endpoints

    provider_policy = ProviderPolicy(cfg)
    permission_policy = PermissionPolicy(cfg.permissions)
    file_policy = FilePolicy(cfg.privacy)
    resolver = EndpointResolver(cfg)

    endpoint_results: list[dict[str, Any]] = []
    for ep_name in endpoint_names:
        entry: dict[str, Any] = {"endpoint": ep_name, "status": "valid", "issues": []}
        if ep_name not in cfg.endpoints:
            entry["status"] = "error"
            entry["issues"].append(f"Endpoint '{ep_name}' not found in config")
            endpoint_results.append(entry)
            continue

        ep_cfg = cfg.endpoints[ep_name]
        provider_name = resolve_alias(ep_cfg.provider)
        try:
            provider_policy.validate(provider_name, requested_as=ep_cfg.provider)
        except MindMeshError as exc:
            entry["status"] = "blocked"
            entry["issues"].append(exc.message)

        try:
            resolver.resolve(ep_name)
        except MindMeshError as exc:
            entry["status"] = "error"
            entry["issues"].append(exc.message)

        warn = permission_policy.check_external_provider(provider_name)
        if warn is not None:
            entry["issues"].append(f"External provider confirmation required for '{provider_name}'")

        endpoint_results.append(entry)

    path_results: list[dict[str, Any]] = []
    for p in paths or []:
        blocked = file_policy.is_blocked(p)
        path_results.append({"path": p, "blocked": blocked})

    permissions_summary: dict[str, bool] = {
        "allow_full_codebase_context": cfg.permissions.allow_full_codebase_context,
        "allow_external_patch": cfg.permissions.allow_external_patch,
        "allow_auto_apply_patch": cfg.permissions.allow_auto_apply_patch,
        "require_confirmation_for_large_context": (
            cfg.permissions.require_confirmation_for_large_context
        ),
        "require_confirmation_for_external_provider": (
            cfg.permissions.require_confirmation_for_external_provider
        ),
    }

    return {
        "endpoints": endpoint_results,
        "paths": path_results,
        "permissions": permissions_summary,
        "disabled_providers": cfg.disabled,
        "privacy": {
            "redact_secrets": cfg.privacy.redact_secrets,
            "block_files_count": len(cfg.privacy.block_files),
            "block_dirs_count": len(cfg.privacy.block_dirs),
        },
        "limits": {
            "max_files": cfg.limits.max_files,
            "max_file_size_kb": cfg.limits.max_file_size_kb,
            "max_total_context_kb": cfg.limits.max_total_context_kb,
        },
    }


def register(mcp: FastMCP) -> None:
    mcp.tool()(validate_policy)
