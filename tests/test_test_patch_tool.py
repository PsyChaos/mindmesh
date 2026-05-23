"""Tests for test_patch tool command validation."""

from __future__ import annotations

import pytest

from mindmesh.config import (
    EndpointConfig,
    MindMeshConfig,
    PermissionsConfig,
    PrivacyConfig,
    ProviderConfig,
    ReviewConfig,
)
from mindmesh.tools.test_patch import test_patch as run_test_patch
from mindmesh.tools.test_patch import validate_command


def _make_config(
    allow_external_patch: bool = True,
    allowed_test_commands: list[str] | None = None,
) -> MindMeshConfig:
    return MindMeshConfig(
        providers={"openai": ProviderConfig()},
        endpoints={
            "ep1": EndpointConfig(provider="openai", model="gpt-4o"),
        },
        review=ReviewConfig(default_endpoints=["ep1"]),
        privacy=PrivacyConfig(block_files=[], block_dirs=[]),
        permissions=PermissionsConfig(
            allow_external_patch=allow_external_patch,
            allowed_test_commands=allowed_test_commands or [],
        ),
    )


# --- validate_command ---


def test_validate_allowed_command() -> None:
    assert validate_command("uv run pytest", ["uv run pytest"]) is None


def test_validate_allowed_prefix() -> None:
    assert validate_command(
        "uv run pytest tests/ -x", ["uv run pytest"],
    ) is None


def test_validate_blocked_command() -> None:
    result = validate_command("rm -rf /", ["uv run pytest"])
    assert result is not None
    assert "not in allowed_test_commands" in result


def test_validate_empty_whitelist() -> None:
    result = validate_command("uv run pytest", [])
    assert result is not None
    assert "No allowed_test_commands" in result


def test_validate_empty_command() -> None:
    result = validate_command("", ["uv run pytest"])
    assert result is not None
    assert "Empty" in result


def test_validate_multiple_allowed() -> None:
    allowed = ["uv run pytest", "npm test", "make test"]
    assert validate_command("npm test", allowed) is None
    assert validate_command("make test", allowed) is None
    assert validate_command("cargo test", allowed) is not None


# --- test_patch tool ---


@pytest.mark.asyncio
async def test_patch_blocked_by_policy() -> None:
    import mindmesh.tools.test_patch as mod
    mod._config = _make_config(allow_external_patch=False)  # pyright: ignore[reportPrivateUsage]
    try:
        result = await run_test_patch(patch="diff", test_command="uv run pytest")
        assert result["error"] is not None
        assert "not allowed" in result["error"]
    finally:
        mod._config = None  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_command_blocked_by_whitelist() -> None:
    import mindmesh.tools.test_patch as mod
    mod._config = _make_config(  # pyright: ignore[reportPrivateUsage]
        allowed_test_commands=["uv run pytest"],
    )
    try:
        result = await run_test_patch(
            patch="diff", test_command="curl http://evil.com",
        )
        assert result["error"] is not None
        assert "not in allowed_test_commands" in result["error"]
        assert result["blocked_command"] == "curl http://evil.com"
    finally:
        mod._config = None  # pyright: ignore[reportPrivateUsage]


@pytest.mark.asyncio
async def test_no_command_skips_validation() -> None:
    import mindmesh.tools.test_patch as mod
    mod._config = _make_config(  # pyright: ignore[reportPrivateUsage]
        allowed_test_commands=[],
    )
    try:
        result = await run_test_patch(patch="not a real patch")
        assert "error" in result
        assert result.get("blocked_command") is None
    finally:
        mod._config = None  # pyright: ignore[reportPrivateUsage]
