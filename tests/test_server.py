"""Tests for server.py — MCP server wiring."""

from __future__ import annotations

import asyncio
import importlib


def test_mcp_instance_exists() -> None:
    from mindmesh.server import mcp
    assert mcp is not None


def test_mcp_name_is_mindmesh() -> None:
    from mindmesh.server import mcp
    assert mcp.name == "mindmesh"


def test_review_code_tool_registered() -> None:
    from mindmesh.server import mcp
    tools = asyncio.run(mcp.list_tools())
    names = [t.name for t in tools]
    assert "review_code" in names


def test_main_is_importable() -> None:
    from mindmesh.server import main
    assert callable(main)


def test_server_module_importable() -> None:
    mod = importlib.import_module("mindmesh.server")
    assert hasattr(mod, "mcp")
    assert hasattr(mod, "main")
