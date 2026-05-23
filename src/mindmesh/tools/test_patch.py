"""test_patch MCP tool — apply a patch in isolated worktree and run tests."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mindmesh.config import MindMeshConfig, load_config
from mindmesh.worktree import WorktreeManager

_config: MindMeshConfig | None = None


def init_tools(config: MindMeshConfig) -> None:
    global _config
    _config = config


def validate_command(
    test_command: str, allowed: list[str],
) -> str | None:
    executable = test_command.split()[0] if test_command.split() else ""
    if not executable:
        return "Empty test command."

    if not allowed:
        return (
            "No allowed_test_commands configured. "
            "Add commands to permissions.allowed_test_commands in .mindmesh.yml "
            "or remove test_command to skip tests."
        )

    for pattern in allowed:
        if executable == pattern or test_command.startswith(pattern):
            return None

    return (
        f"Command '{executable}' is not in allowed_test_commands. "
        f"Allowed: {allowed}"
    )


async def test_patch(
    patch: str,
    test_command: str | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    cfg = _config or load_config()

    if not cfg.permissions.allow_external_patch:
        return {
            "error": "External patches not allowed by policy. "
            "Set allow_external_patch=true.",
            "patch_applied": False,
        }

    if test_command:
        violation = validate_command(
            test_command, cfg.permissions.allowed_test_commands,
        )
        if violation:
            return {
                "error": violation,
                "patch_applied": False,
                "blocked_command": test_command,
            }

    manager = WorktreeManager(sandbox=cfg.sandbox)
    cmd = test_command.split() if test_command else None
    result = await manager.test_patch(
        patch_content=patch,
        test_command=cmd,
        timeout=timeout,
    )
    return {
        "worktree_path": result.worktree_path,
        "branch_name": result.branch_name,
        "patch_applied": result.patch_applied,
        "sandboxed": result.sandboxed,
        "test_exit_code": result.test_exit_code,
        "test_output": result.test_output,
        "error": result.error,
    }


def register(mcp: FastMCP) -> None:
    mcp.tool()(test_patch)
