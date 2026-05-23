"""review_code MCP tool — orchestrates the full review pipeline."""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from mindmesh.audit import AuditEntry, AuditLogger
from mindmesh.cache import ResponseCache
from mindmesh.config import MindMeshConfig, load_config, resolve_alias
from mindmesh.context.collector import ContextCollector, format_context
from mindmesh.context.filters import ContextFilter
from mindmesh.context.git import GitContext
from mindmesh.context.redactor import SecretRedactor
from mindmesh.context.tokenizer import ContextSizer
from mindmesh.errors import MindMeshError, RateLimitError
from mindmesh.history import HistoryStore
from mindmesh.output.merger import FindingsMerger
from mindmesh.output.normalizer import ResponseNormalizer
from mindmesh.output.report import Reporter
from mindmesh.policy.file_policy import FilePolicy
from mindmesh.policy.permission_policy import PermissionPolicy
from mindmesh.policy.provider_policy import ProviderPolicy
from mindmesh.prompts import PromptLoader
from mindmesh.providers.base import EndpointResolver, ProviderAdapter
from mindmesh.schemas import EndpointError, Finding, Message, PolicyReport, ToolResult

_DEFAULT_FOCUS = ["correctness", "bugs", "security", "performance", "maintainability"]


def try_log_audit(
    config: MindMeshConfig,
    tool: str,
    scope: str,
    start_time: float,
    endpoints_called: list[str],
    endpoints_succeeded: list[str],
    endpoints_failed: list[str],
    findings_count: int,
    context_size_kb: float,
    redacted_secrets: int,
    status: Literal["success", "partial", "error"],
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    if not config.audit.enabled:
        return
    log_dir = Path(config.audit.log_dir) if config.audit.log_dir else None
    logger = AuditLogger(log_dir)
    entry = AuditEntry(
        timestamp=datetime.now(tz=UTC).isoformat(),
        tool=tool,
        scope=scope,
        endpoints_called=endpoints_called,
        endpoints_succeeded=endpoints_succeeded,
        endpoints_failed=endpoints_failed,
        findings_count=findings_count,
        context_size_kb=context_size_kb,
        redacted_secrets=redacted_secrets,
        duration_ms=int((time.monotonic() - start_time) * 1000),
        status=status,
    )
    with contextlib.suppress(Exception):
        logger.log(entry)
    with contextlib.suppress(Exception):
        store = HistoryStore()
        store.record(
            timestamp=entry.timestamp, tool=tool, scope=scope,
            endpoints_called=endpoints_called,
            endpoints_succeeded=endpoints_succeeded,
            endpoints_failed=endpoints_failed,
            findings_count=findings_count,
            context_size_kb=context_size_kb,
            redacted_secrets=redacted_secrets,
            duration_ms=entry.duration_ms, status=status,
            input_tokens=input_tokens, output_tokens=output_tokens,
        )
        store.close()
_config: MindMeshConfig | None = None


def init_tools(config: MindMeshConfig) -> None:
    global _config
    _config = config


async def review_code(
    scope: str = "git_diff",
    endpoints: list[str] | None = None,
    focus: list[str] | None = None,
    dry_run: bool = False,
    min_severity: str | None = None,
    no_cache: bool = False,
) -> dict[str, Any]:
    cfg = _config or load_config()
    return await _run_review(
        cfg, scope, endpoints, focus,
        template_name="review", dry_run=dry_run,
        min_severity=min_severity, no_cache=no_cache,
    )


def register(mcp: FastMCP) -> None:
    mcp.tool()(review_code)


async def _run_review(
    config: MindMeshConfig,
    scope: str,
    endpoints: list[str] | None,
    focus: list[str] | None,
    template_name: str = "review",
    template_kwargs: dict[str, Any] | None = None,
    dry_run: bool = False,
    min_severity: str | None = None,
    no_cache: bool = False,
) -> dict[str, Any]:
    if dry_run:
        from mindmesh.tools.preview import (
            _preview_context_impl,  # pyright: ignore[reportPrivateUsage]
        )
        return await _preview_context_impl(scope, endpoints, config)
    focus_areas = focus or _DEFAULT_FOCUS
    endpoint_names = endpoints or config.review.default_endpoints
    start_time = time.monotonic()

    if not endpoint_names:
        try_log_audit(
            config, template_name, scope, start_time,
            endpoints_called=[], endpoints_succeeded=[], endpoints_failed=[],
            findings_count=0, context_size_kb=0.0, redacted_secrets=0,
            status="error",
        )
        return ToolResult(
            summary="No endpoints configured.",
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

    # Steps 1-2: alias resolve + provider policy validation
    provider_policy = ProviderPolicy(config)
    permission_policy = PermissionPolicy(config.permissions)
    resolver = EndpointResolver(config)
    endpoint_errors: list[EndpointError] = []
    valid: list[tuple[str, ProviderAdapter, str, dict[str, Any]]] = []

    checked_providers: list[str] = []
    blocked_providers: list[dict[str, str]] = []
    allowed_providers: list[str] = []

    for ep_name in endpoint_names:
        if ep_name not in config.endpoints:
            endpoint_errors.append(EndpointError(
                endpoint=ep_name,
                error_code="ENDPOINT_NOT_FOUND",
                message=f"Endpoint '{ep_name}' not found in config",
                retryable=False,
            ))
            continue
        ep_cfg = config.endpoints[ep_name]
        provider_name = resolve_alias(ep_cfg.provider)
        checked_providers.append(provider_name)
        try:
            provider_policy.validate(provider_name, requested_as=provider_name)
            adapter, model, ep_dict = resolver.resolve(ep_name)
        except MindMeshError as exc:
            blocked_providers.append({
                "provider": provider_name,
                "reason": exc.message,
                "error_code": exc.error_code,
            })
            endpoint_errors.append(EndpointError(
                endpoint=ep_name,
                error_code=exc.error_code,
                message=exc.message,
                retryable=exc.retryable,
            ))
            continue
        allowed_providers.append(provider_name)
        valid.append((ep_name, adapter, model, ep_dict))

    # Collect external-provider permission warnings for allowed providers
    permission_warnings: list[dict[str, str]] = []
    for provider_name in allowed_providers:
        warn = permission_policy.check_external_provider(provider_name)
        if warn is not None:
            permission_warnings.append({
                "warning": str(warn.get("warning", "")),
                "details": str(warn.get("provider", "")),
            })

    if not valid:
        policy_report = PolicyReport(
            checked_providers=checked_providers,
            blocked_providers=blocked_providers,
            allowed_providers=allowed_providers,
            permission_warnings=permission_warnings,
            file_policy_blocked=[],
            redacted_secret_count=0,
        )
        result = Reporter().build(
            FindingsMerger().merge({}), endpoint_errors, [], 0.0, policy_report
        )
        try_log_audit(
            config, template_name, scope, start_time,
            endpoints_called=list(endpoint_names),
            endpoints_succeeded=[],
            endpoints_failed=[err.endpoint for err in endpoint_errors],
            findings_count=0, context_size_kb=0.0, redacted_secrets=0,
            status="error",
        )
        return result.model_dump()

    # Steps 3-8: context pipeline
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

    if config.compression.enabled:
        from mindmesh.context.summarizer import summarize_files
        redacted_files = await summarize_files(redacted_files, config)

    context_size = sizer.measure_files(redacted_files)
    formatted = format_context(redacted_files)

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

    # Step 9: render prompt
    custom_dir = Path(config.prompts.custom_dir) if config.prompts.custom_dir else None
    loader = PromptLoader(custom_dir=custom_dir)
    base_kwargs: dict[str, Any] = {
        "focus_areas": focus_areas,
        "context": formatted,
        "scope_description": scope,
    }
    base_kwargs.update(template_kwargs or {})
    messages = loader.load(template_name, **base_kwargs)

    # Step 10: parallel calls with per-endpoint timeout + cache
    cache = ResponseCache(config.cache)
    use_cache = config.cache.enabled and not no_cache
    context_hash = ResponseCache.hash_content(formatted) if use_cache else ""
    normalizer = ResponseNormalizer()
    findings_by_endpoint: dict[str, list[Finding]] = {}

    async def _call(
        ep_name: str,
        adapter: ProviderAdapter,
        model: str,
        ep_dict: dict[str, Any],
    ) -> tuple[str, str | None, EndpointError | None]:
        cache_key = ""
        if use_cache:
            cache_key = ResponseCache.make_key(
                ep_name, template_name, context_hash,
            )
            cached = cache.get(cache_key)
            if cached is not None:
                return ep_name, cached, None

        timeout = float(ep_dict.get("timeout_seconds", 30))
        try:
            raw = await asyncio.wait_for(
                _send_with_retry(adapter, messages, model, ep_dict),
                timeout=timeout,
            )
            if use_cache:
                cache.put(cache_key, raw)
            return ep_name, raw, None
        except TimeoutError:
            return ep_name, None, EndpointError(
                endpoint=ep_name,
                error_code="PROVIDER_TIMEOUT",
                message=f"Timed out after {timeout}s",
                retryable=True,
            )
        except MindMeshError as exc:
            return ep_name, None, EndpointError(
                endpoint=ep_name,
                error_code=exc.error_code,
                message=exc.message,
                retryable=exc.retryable,
            )

    call_results = await asyncio.gather(*[
        _call(name, adapter, model, ep_dict) for name, adapter, model, ep_dict in valid
    ])

    # Step 11: normalize with parse retry + token tracking
    from mindmesh.providers.base import TokenUsage
    total_input_tokens = 0
    total_output_tokens = 0

    for ep_name, raw, call_error in call_results:
        if call_error is not None:
            endpoint_errors.append(call_error)
            continue
        assert raw is not None
        _, adapter, model, ep_dict = next(e for e in valid if e[0] == ep_name)
        usage = adapter.last_usage or TokenUsage()
        total_input_tokens += usage.input_tokens
        total_output_tokens += usage.output_tokens
        provider = resolve_alias(config.endpoints[ep_name].provider)
        findings_by_endpoint[ep_name] = await _parse_with_retry(
            normalizer, raw, ep_name, provider, model, adapter, messages, ep_dict
        )

    # Steps 12-14: merge → report → return
    merge_result = FindingsMerger().merge(findings_by_endpoint)
    policy_report = PolicyReport(
        checked_providers=checked_providers,
        blocked_providers=blocked_providers,
        allowed_providers=allowed_providers,
        permission_warnings=permission_warnings,
        file_policy_blocked=filter_report.blocked_by_policy,
        redacted_secret_count=len(redaction_findings),
    )
    result = Reporter().build(
        merge_result, endpoint_errors, redaction_findings,
        context_size.total_kb, policy_report, min_severity=min_severity,
    )
    _ep_succeeded = list(findings_by_endpoint.keys())
    _ep_failed = [err.endpoint for err in endpoint_errors]
    _audit_status: Literal["success", "partial", "error"]
    if not _ep_succeeded:
        _audit_status = "error"
    elif _ep_failed:
        _audit_status = "partial"
    else:
        _audit_status = "success"
    try_log_audit(
        config, template_name, scope, start_time,
        endpoints_called=list(endpoint_names),
        endpoints_succeeded=_ep_succeeded,
        endpoints_failed=_ep_failed,
        findings_count=sum(len(f) for f in findings_by_endpoint.values()),
        context_size_kb=context_size.total_kb,
        redacted_secrets=len(redaction_findings),
        status=_audit_status,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
    )
    return result.model_dump()


async def _send_with_retry(
    adapter: ProviderAdapter,
    messages: list[Message],
    model: str,
    config: dict[str, Any],
    max_retries: int = 2,
) -> str:
    last_exc: RateLimitError | None = None
    for attempt in range(max_retries + 1):
        try:
            return await adapter.send(messages, model, config)
        except RateLimitError as exc:
            last_exc = exc
            if attempt < max_retries:
                await asyncio.sleep(2**attempt)
    assert last_exc is not None
    raise last_exc


async def _parse_with_retry(
    normalizer: ResponseNormalizer,
    raw: str,
    endpoint: str,
    provider: str,
    model: str,
    adapter: ProviderAdapter,
    messages: list[Message],
    endpoint_cfg: dict[str, Any],
) -> list[Finding]:
    findings = normalizer.parse(raw, endpoint, provider, model)
    if findings is not None:
        return findings

    retry_msg = [
        *messages,
        Message(
            role="user",
            content="Your response was not valid JSON. Return only a JSON array of findings.",
        ),
    ]
    try:
        raw2 = await _send_with_retry(adapter, retry_msg, model, endpoint_cfg)
    except Exception:
        return [normalizer.make_parse_error_finding(
            endpoint, provider, model,
            f"Parse failed after retry. Raw response:\n{raw}",
        )]

    findings2 = normalizer.parse(raw2, endpoint, provider, model)
    if findings2 is not None:
        return findings2
    return [normalizer.make_parse_error_finding(
        endpoint, provider, model,
        f"Parse failed after retry. Raw response:\n{raw}",
    )]
