"""LLM-based context summarizer with fallback chain."""

from __future__ import annotations

from mindmesh.config import MindMeshConfig
from mindmesh.context.collector import FileContext
from mindmesh.context.compressor import compress_files
from mindmesh.providers.base import EndpointResolver
from mindmesh.schemas import Message


async def summarize_files(
    files: list[FileContext],
    config: MindMeshConfig,
) -> list[FileContext]:
    if not config.compression.enabled:
        return files

    endpoint_name = _resolve_endpoint(config)
    if endpoint_name:
        try:
            return await _llm_summarize(files, endpoint_name, config)
        except Exception:
            pass

    return compress_files(files)


def _resolve_endpoint(config: MindMeshConfig) -> str | None:
    if config.compression.endpoint and config.compression.endpoint in config.endpoints:
            return config.compression.endpoint
    defaults = config.review.default_endpoints
    return defaults[0] if defaults else None


async def _llm_summarize(
    files: list[FileContext],
    endpoint_name: str,
    config: MindMeshConfig,
) -> list[FileContext]:
    resolver = EndpointResolver(config)
    adapter, model, ep_dict = resolver.resolve(endpoint_name)

    result: list[FileContext] = []
    for fc in files:
        if len(fc.content) < 500:
            result.append(fc)
            continue
        messages = [
            Message(
                role="system",
                content=(
                    "Summarize this code file. Keep function/class signatures, "
                    "key logic, imports, and public API. Remove implementation "
                    "details. Output only the summary, no explanation."
                ),
            ),
            Message(
                role="user",
                content=f"File: {fc.path}\nLanguage: {fc.language}\n\n{fc.content}",
            ),
        ]
        summary = await adapter.send(messages, model, ep_dict)
        result.append(fc.model_copy(update={"content": summary}))
    return result
