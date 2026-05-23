from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from mindmesh.config import (
    DEFAULT_BLOCK_DIRS,
    DEFAULT_BLOCK_FILES,
    EndpointConfig,
    MindMeshConfig,
    PrivacyConfig,
    load_config,
    resolve_alias,
)


def test_default_config_sensible_defaults() -> None:
    config = MindMeshConfig()

    assert config.privacy.redact_secrets is True
    assert config.limits.max_files == 50
    assert config.limits.max_file_size_kb == 120
    assert config.limits.max_total_context_kb == 1024
    assert config.limits.prefer_git_diff is True
    assert config.permissions.allow_full_codebase_context is False
    assert config.permissions.allow_external_patch is False
    assert config.permissions.allow_auto_apply_patch is False
    assert config.permissions.require_confirmation_for_large_context is True
    assert config.permissions.require_confirmation_for_external_provider is False
    assert config.project.default_scope == "git_diff"
    assert config.project.name == ""
    assert config.project.base_branch is None
    assert config.review.output_format == "structured_findings"
    assert config.review.default_endpoints == []
    assert config.disabled == []


def test_load_config_from_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    config_data = {
        "project": {"name": "test-project", "default_scope": "staged"},
        "providers": {"openai": {"api_key_env": "OPENAI_API_KEY"}},
        "endpoints": {
            "openai-review": {"provider": "openai", "model": "gpt-4o", "timeout_seconds": 45}
        },
        "privacy": {"redact_secrets": True, "block_files": [".env", "*.pem"]},
        "limits": {"max_files": 30},
    }
    config_file = tmp_path / ".mindmesh.yml"
    config_file.write_text(yaml.dump(config_data))

    config = load_config(config_file)

    assert config.project.name == "test-project"
    assert config.project.default_scope == "staged"
    assert "openai" in config.providers
    assert config.providers["openai"].api_key_env == "OPENAI_API_KEY"
    assert "openai-review" in config.endpoints
    assert config.endpoints["openai-review"].provider == "openai"
    assert config.endpoints["openai-review"].model == "gpt-4o"
    assert config.endpoints["openai-review"].timeout_seconds == 45
    assert config.limits.max_files == 30
    assert config.limits.max_file_size_kb == 120  # default preserved


def test_yaml_not_found_uses_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)

    config = load_config()

    assert config.privacy.redact_secrets is True
    assert config.limits.max_total_context_kb == 1024
    assert config.permissions.allow_auto_apply_patch is False
    assert config.project.default_scope == "git_diff"


def test_auto_endpoint_from_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)

    config = load_config()

    assert "openai" in config.providers
    assert config.providers["openai"].api_key_env == "OPENAI_API_KEY"
    assert "openai-default" in config.endpoints
    assert config.endpoints["openai-default"].provider == "openai"
    assert config.endpoints["openai-default"].model == "gpt-4o"


def test_no_api_key_raises_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    # prevent any .env file higher in the tree from loading
    def _noop(**_: Any) -> bool:
        return False
    monkeypatch.setattr("mindmesh.config.load_dotenv", _noop)

    with pytest.raises(ValueError, match="No providers configured"):
        load_config()


def test_resolve_alias_chatgpt() -> None:
    assert resolve_alias("chatgpt") == "openai"


def test_resolve_alias_local() -> None:
    assert resolve_alias("local") == "ollama"


def test_resolve_alias_unknown_passthrough() -> None:
    assert resolve_alias("gemini") == "gemini"
    assert resolve_alias("zai") == "zai"
    assert resolve_alias("unknown-provider") == "unknown-provider"


def test_privacy_config_default_block_files() -> None:
    privacy = PrivacyConfig()

    for expected in DEFAULT_BLOCK_FILES:
        assert expected in privacy.block_files, f"Expected '{expected}' in default block_files"

    assert ".env" in privacy.block_files
    assert ".env.*" in privacy.block_files
    assert "*.pem" in privacy.block_files
    assert "*.key" in privacy.block_files
    assert "id_rsa" in privacy.block_files
    assert "id_ed25519" in privacy.block_files
    assert "secrets/**" in privacy.block_files
    assert "config/production.*" in privacy.block_files


def test_privacy_config_default_block_dirs() -> None:
    privacy = PrivacyConfig()

    for expected in DEFAULT_BLOCK_DIRS:
        assert expected in privacy.block_dirs, f"Expected '{expected}' in default block_dirs"

    assert "node_modules" in privacy.block_dirs
    assert ".git" in privacy.block_dirs
    assert "dist" in privacy.block_dirs
    assert ".vscode" in privacy.block_dirs
    assert ".idea" in privacy.block_dirs


def test_endpoint_config_timeout_default() -> None:
    endpoint = EndpointConfig(provider="openai", model="gpt-4o")
    assert endpoint.timeout_seconds == 30


def test_config_merge_yaml_overrides_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    config_data = {
        "providers": {"openai": {"api_key_env": "OPENAI_API_KEY"}},
        "endpoints": {"openai-default": {"provider": "openai", "model": "gpt-4o"}},
        "privacy": {"redact_secrets": False},
        "limits": {"max_files": 100},
        "permissions": {"allow_full_codebase_context": True},
    }
    config_file = tmp_path / "custom.yml"
    config_file.write_text(yaml.dump(config_data))

    config = load_config(config_file)

    # YAML values override defaults
    assert config.privacy.redact_secrets is False
    assert config.limits.max_files == 100
    assert config.permissions.allow_full_codebase_context is True

    # Unspecified values keep defaults
    assert config.limits.max_file_size_kb == 120
    assert config.limits.max_total_context_kb == 1024
    assert config.permissions.allow_auto_apply_patch is False
    assert config.review.output_format == "structured_findings"


def test_invalid_yaml_raises_meaningful_error(tmp_path: Path) -> None:
    config_file = tmp_path / "bad.yml"
    config_file.write_text("key: [\nunclosed bracket")

    with pytest.raises(ValueError, match="Invalid YAML"):
        load_config(config_file)
