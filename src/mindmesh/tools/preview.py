"""preview_context MCP tool — context/policy preview without provider calls."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mindmesh.config import MindMeshConfig, load_config, resolve_alias
from mindmesh.context.collector import ContextCollector
from mindmesh.context.filters import ContextFilter
from mindmesh.context.git import GitContext
from mindmesh.context.redactor import SecretRedactor
from mindmesh.context.tokenizer import ContextSizer
from mindmesh.errors import MindMeshError
from mindmesh.policy.file_policy import FilePolicy
from mindmesh.policy.permission_policy import PermissionPolicy
from mindmesh.policy.provider_policy import ProviderPolicy
from mindmesh.providers.base import EndpointResolver

_config: MindMeshConfig | None = None


def init_tools(config: MindMeshConfig) -> None:
    global _config
    _config = config


async def _preview_context_impl(
    scope: str,
    endpoints: list[str] | None,
    config: MindMeshConfig,
) -> dict[str, Any]:
    endpoint_names = endpoints or config.review.default_endpoints

    # Steps 1-2: provider policy + permission check
    provider_policy = ProviderPolicy(config)
    permission_policy = PermissionPolicy(config.permissions)
    resolver = EndpointResolver(config)

    endpoints_valid: list[str] = []
    endpoints_blocked: list[dict[str, str]] = []
    permission_warnings: list[dict[str, str]] = []
    allowed_providers: list[str] = []

    for ep_name in endpoint_names:
        if ep_name not in config.endpoints:
            endpoints_blocked.append({
                "endpoint": ep_name,
                "reason": f"Endpoint '{ep_name}' not found in config",
                "error_code": "ENDPOINT_NOT_FOUND",
            })
            continue
        ep_cfg = config.endpoints[ep_name]
        provider_name = resolve_alias(ep_cfg.provider)
        try:
            provider_policy.validate(provider_name, requested_as=provider_name)
            resolver.resolve(ep_name)
        except MindMeshError as exc:
            endpoints_blocked.append({
                "endpoint": ep_name,
                "reason": exc.message,
                "error_code": exc.error_code,
            })
            continue
        endpoints_valid.append(ep_name)
        allowed_providers.append(provider_name)

    for provider_name in allowed_providers:
        warn = permission_policy.check_external_provider(provider_name)
        if warn is not None:
            permission_warnings.append({
                "warning": str(warn.get("warning", "")),
                "details": str(warn.get("provider", "")),
            })

    # Steps 3-7: context pipeline (no provider calls)
    git = GitContext()
    collector = ContextCollector(git, config)
    context_filter = ContextFilter(FilePolicy(config.privacy), config.limits)
    redactor = SecretRedactor()
    sizer = ContextSizer()

    try:
        raw_files = await collector.collect(scope)
    except Exception:
        raw_files = []

    filtered_files, filter_report = context_filter.filter(raw_files)
    redacted_files, redaction_findings = redactor.redact_files(filtered_files)
    context_size = sizer.measure_files(redacted_files)
    limit_warnings = sizer.check_limits(context_size, config.limits)

    large_ctx_warn = permission_policy.check_large_context(
        int(context_size.total_kb), config.limits.max_total_context_kb
    )
    if large_ctx_warn is not None:
        permission_warnings.append({
            "warning": str(large_ctx_warn.get("warning", "")),
            "details": (
                f"size_kb={large_ctx_warn.get('size_kb')},"
                f" limit_kb={large_ctx_warn.get('limit_kb')}"
            ),
        })

    lang_map = {fc.path: fc.language for fc in redacted_files}
    context_files = [
        {"path": path, "size_kb": round(kb, 2), "language": lang_map.get(path, "text")}
        for path, kb in context_size.file_sizes
    ]

    return {
        "scope": scope,
        "endpoints_requested": endpoint_names,
        "endpoints_valid": endpoints_valid,
        "endpoints_blocked": endpoints_blocked,
        "context_files": context_files,
        "files_filtered": {
            "by_policy": filter_report.blocked_by_policy,
            "by_binary": filter_report.blocked_by_binary,
            "by_size": filter_report.blocked_by_size,
            "by_generated": filter_report.blocked_by_generated,
            "by_total_limit": filter_report.blocked_by_total_limit,
        },
        "secrets_redacted": len(redaction_findings),
        "total_context_kb": context_size.total_kb,
        "limit_warnings": limit_warnings,
        "permission_warnings": permission_warnings,
    }


async def preview_context(
    scope: str = "git_diff",
    endpoints: list[str] | None = None,
) -> dict[str, Any]:
    cfg = _config or load_config()
    return await _preview_context_impl(scope, endpoints, cfg)


def register(mcp: FastMCP) -> None:
    mcp.tool()(preview_context)
