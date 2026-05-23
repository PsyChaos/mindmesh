"""ask_provider MCP tool — ask a single endpoint a free-form question."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from mindmesh.config import MindMeshConfig, load_config, resolve_alias
from mindmesh.context.collector import ContextCollector, format_context
from mindmesh.context.filters import ContextFilter
from mindmesh.context.git import GitContext
from mindmesh.context.redactor import SecretRedactor
from mindmesh.context.tokenizer import ContextSizer
from mindmesh.errors import MindMeshError, RateLimitError
from mindmesh.policy.file_policy import FilePolicy
from mindmesh.policy.provider_policy import ProviderPolicy
from mindmesh.prompts import PromptLoader
from mindmesh.providers.base import EndpointResolver, ProviderAdapter
from mindmesh.schemas import Message

_config: MindMeshConfig | None = None


def init_tools(config: MindMeshConfig) -> None:
    global _config
    _config = config


async def ask_provider(
    question: str,
    endpoint: str | None = None,
    context_mode: str = "none",
) -> dict[str, Any]:
    cfg = _config or load_config()
    defaults = cfg.review.default_endpoints
    ep_name = endpoint or (defaults[0] if defaults else None)

    if not ep_name:
        return {"error": "No endpoint configured.", "answer": None}

    if ep_name not in cfg.endpoints:
        return {"error": f"Endpoint '{ep_name}' not found.", "answer": None}

    ep_cfg = cfg.endpoints[ep_name]
    provider_name = resolve_alias(ep_cfg.provider)
    provider_policy = ProviderPolicy(cfg)
    try:
        provider_policy.validate(provider_name, requested_as=ep_cfg.provider)
    except MindMeshError as exc:
        return {"error": exc.message, "answer": None}

    resolver = EndpointResolver(cfg)
    try:
        adapter, model, ep_dict = resolver.resolve(ep_name)
    except MindMeshError as exc:
        return {"error": exc.message, "answer": None}

    context_text = ""
    context_size_kb = 0.0
    redacted_count = 0

    if context_mode != "none":
        git = GitContext()
        collector = ContextCollector(git, cfg)
        context_filter = ContextFilter(FilePolicy(cfg.privacy), cfg.limits)
        redactor = SecretRedactor()
        sizer = ContextSizer()

        try:
            raw_files = await collector.collect(context_mode)
        except Exception:
            raw_files = []

        filtered_files, _ = context_filter.filter(raw_files)
        redacted_files, redaction_findings = redactor.redact_files(filtered_files)
        size_info = sizer.measure_files(redacted_files)
        context_text = format_context(redacted_files)
        context_size_kb = size_info.total_kb
        redacted_count = len(redaction_findings)

    from pathlib import Path
    custom_dir = Path(cfg.prompts.custom_dir) if cfg.prompts.custom_dir else None
    loader = PromptLoader(custom_dir=custom_dir)
    messages = loader.load(
        "ask",
        question=question,
        context_mode=context_mode,
        context=context_text,
    )

    timeout = float(ep_dict.get("timeout_seconds", 30))
    try:
        raw = await asyncio.wait_for(
            _send_with_retry(adapter, messages, model, ep_dict),
            timeout=timeout,
        )
    except TimeoutError:
        return {"error": f"Timed out after {timeout}s", "answer": None}
    except MindMeshError as exc:
        return {"error": exc.message, "answer": None}

    return {
        "endpoint": ep_name,
        "provider": provider_name,
        "model": model,
        "answer": raw,
        "metadata": {
            "context_size_kb": context_size_kb,
            "redacted_secrets": redacted_count,
        },
    }


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


def register(mcp: FastMCP) -> None:
    mcp.tool()(ask_provider)
