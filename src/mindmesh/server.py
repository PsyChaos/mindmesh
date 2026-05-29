"""MindMesh MCP server — FastMCP instance, tool registration, entry point."""

from pathlib import Path as _Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from mindmesh.config import load_config
from mindmesh.tools import (
    ask,
    bugfix,
    compare,
    delegate,
    list_endpoints,
    preview,
    review,
    scan,
    security,
    test_patch,
    validate,
)

_env = _Path.cwd() / ".env"
load_dotenv(_env if _env.exists() else None)

_TOOL_MODULES = (
    review, security, bugfix, ask, compare, delegate,
    list_endpoints, preview, validate, test_patch, scan,
)

mcp = FastMCP("mindmesh")
for _mod in _TOOL_MODULES:
    _mod.register(mcp)

config = load_config()
for _mod in _TOOL_MODULES:
    _mod.init_tools(config)


def main() -> None:
    mcp.run()
