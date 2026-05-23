"""list_endpoints MCP tool — lists configured endpoints with status."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from mindmesh.config import MindMeshConfig, load_config, resolve_alias
from mindmesh.errors import MindMeshError
from mindmesh.policy.provider_policy import ProviderPolicy
from mindmesh.providers.base import EndpointResolver
from mindmesh.schemas import Message

_config: MindMeshConfig | None = None

_PING_PROMPT = [
    Message(role="system", content="Respond with exactly: ok"),
    Message(role="user", content="ping"),
]
_PING_TIMEOUT = 5.0


def init_tools(config: MindMeshConfig) -> None:
    global _config
    _config = config


async def list_endpoints(check: bool = False) -> dict[str, Any]:
    cfg = _config or load_config()
    resolver = EndpointResolver(cfg)
    entries = resolver.list_endpoints()

    if not check:
        return {"endpoints": entries}

    provider_policy = ProviderPolicy(cfg)
    results = await asyncio.gather(*[
        _check_endpoint(name=e["name"], cfg=cfg, resolver=resolver,
                        provider_policy=provider_policy)
        for e in entries
    ])
    health_map = dict(results)

    for entry in entries:
        entry["health"] = health_map.get(entry["name"], "unknown")

    return {"endpoints": entries}


async def _check_endpoint(
    name: str,
    cfg: MindMeshConfig,
    resolver: EndpointResolver,
    provider_policy: ProviderPolicy,
) -> tuple[str, str]:
    if name not in cfg.endpoints:
        return name, "not_found"

    ep_cfg = cfg.endpoints[name]
    provider_name = resolve_alias(ep_cfg.provider)

    try:
        provider_policy.validate(provider_name)
    except MindMeshError:
        return name, "blocked"

    try:
        adapter, model, ep_dict = resolver.resolve(name)
    except (MindMeshError, KeyError, ValueError):
        return name, "error"

    try:
        await asyncio.wait_for(
            adapter.send(_PING_PROMPT, model, ep_dict),
            timeout=_PING_TIMEOUT,
        )
        return name, "healthy"
    except TimeoutError:
        return name, "timeout"
    except Exception:
        return name, "unreachable"


def register(mcp: FastMCP) -> None:
    mcp.tool()(list_endpoints)
