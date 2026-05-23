from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from mindmesh.registry import get_registry as _get_registry

DEFAULT_BLOCK_FILES: list[str] = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "secrets/**",
    "config/production.*",
]

DEFAULT_BLOCK_DIRS: list[str] = [
    "node_modules",
    "vendor",
    "dist",
    "build",
    ".git",
    ".next",
    "coverage",
    ".cache",
    ".idea",
    ".vscode",
]



class ProviderConfig(BaseModel):
    api_key_env: str | None = None
    base_url: str | None = None


class EndpointConfig(BaseModel):
    provider: str
    model: str
    timeout_seconds: int = 30


class PrivacyConfig(BaseModel):
    redact_secrets: bool = True
    block_files: list[str] = Field(default_factory=lambda: list(DEFAULT_BLOCK_FILES))
    block_dirs: list[str] = Field(default_factory=lambda: list(DEFAULT_BLOCK_DIRS))
    custom_secret_patterns: list[str] = Field(default_factory=list)


class LimitsConfig(BaseModel):
    max_files: int = 50
    max_file_size_kb: int = 120
    max_total_context_kb: int = 1024
    prefer_git_diff: bool = True


class SandboxConfig(BaseModel):
    enabled: bool = True
    image: str = "python:3.12-slim"
    network: bool = False
    memory_limit: str = "512m"
    cpu_limit: float = 1.0


class PermissionsConfig(BaseModel):
    allow_full_codebase_context: bool = False
    allow_external_patch: bool = False
    allow_auto_apply_patch: bool = False
    require_confirmation_for_large_context: bool = True
    require_confirmation_for_external_provider: bool = False
    allowed_test_commands: list[str] = Field(default_factory=list)


class PromptsConfig(BaseModel):
    custom_dir: str | None = None


class ReviewConfig(BaseModel):
    default_endpoints: list[str] = Field(default_factory=list)
    output_format: str = "structured_findings"


class ProjectConfig(BaseModel):
    name: str = ""
    default_scope: str = "git_diff"
    base_branch: str | None = None


class CompressionConfig(BaseModel):
    enabled: bool = False
    endpoint: str | None = None


class CacheConfig(BaseModel):
    enabled: bool = False
    ttl_seconds: int = 3600
    db_path: str | None = None


class AuditConfig(BaseModel):
    enabled: bool = True
    log_dir: str | None = None


class MindMeshConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    disabled: list[str] = Field(default_factory=list)
    endpoints: dict[str, EndpointConfig] = Field(default_factory=dict)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    compression: CompressionConfig = Field(default_factory=CompressionConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)


def resolve_alias(name: str) -> str:
    return _get_registry().resolve_alias(name)


def _build_auto_providers_and_endpoints() -> (
    tuple[dict[str, ProviderConfig], dict[str, EndpointConfig]]
):
    providers: dict[str, ProviderConfig] = {}
    endpoints: dict[str, EndpointConfig] = {}
    env_map = _get_registry().auto_env_map()
    for env_var, (provider_name, endpoint_name, model) in env_map.items():
        if os.environ.get(env_var):
            providers[provider_name] = ProviderConfig(api_key_env=env_var)
            endpoints[endpoint_name] = EndpointConfig(provider=provider_name, model=model)
    return providers, endpoints


def _load_yaml(config_path: Path) -> dict[str, Any]:
    try:
        with open(config_path) as f:
            loaded = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in config file '{config_path}': {exc}") from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(
            f"Config file '{config_path}' must be a YAML mapping, got {type(loaded).__name__}"
        )
    return cast(dict[str, Any], loaded)


def load_config(path: Path | None = None) -> MindMeshConfig:
    load_dotenv(override=False)

    raw: dict[str, Any] = {}

    if path is not None:
        raw = _load_yaml(path)
    else:
        candidate = Path.cwd() / ".mindmesh.yml"
        if candidate.exists():
            raw = _load_yaml(candidate)

    config = MindMeshConfig.model_validate(raw)

    if not config.providers and not config.endpoints:
        auto_providers, auto_endpoints = _build_auto_providers_and_endpoints()
        config.providers = auto_providers
        config.endpoints = auto_endpoints

    if not config.providers and not config.endpoints:
        raise ValueError(
            "No providers configured and no API keys found in environment. "
            "Set at least one of: OPENAI_API_KEY, GEMINI_API_KEY, ZAI_API_KEY, "
            "or configure providers in .mindmesh.yml"
        )

    return config
