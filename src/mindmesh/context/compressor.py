"""Context compression — extract signatures, drop bodies."""

from __future__ import annotations

import ast
import re
from typing import Any

from mindmesh.context.collector import FileContext

_FUNC_RE = re.compile(
    r"^(\s*(?:export\s+)?(?:async\s+)?(?:function|def|fn|func)\s+\w+\s*\([^)]*\)[^{;]*)",
    re.MULTILINE,
)
_CLASS_RE = re.compile(
    r"^(\s*(?:export\s+)?(?:class|struct|interface|trait|enum)\s+\w+[^{;]*)",
    re.MULTILINE,
)
_METHOD_RE = re.compile(
    r"^(\s+(?:public|private|protected|static|async|override)?\s*\w+\s*\([^)]*\)[^{;]*)",
    re.MULTILINE,
)


def compress_file(fc: FileContext) -> FileContext:
    if fc.language == "python":
        skeleton = _compress_python(fc.content)
    else:
        skeleton = _compress_generic(fc.content)
    return fc.model_copy(update={"content": skeleton})


def compress_files(files: list[FileContext]) -> list[FileContext]:
    return [compress_file(fc) for fc in files]


def _compress_python(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _compress_generic(source)

    lines: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            decorators = _format_decorators(node.decorator_list, source)
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            base_str = f"({bases})" if bases else ""
            lines.append(f"{decorators}class {node.name}{base_str}:")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = _format_decorators(node.decorator_list, source)
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            args = ast.unparse(node.args)
            ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            indent = "    " if _is_method(node, tree) else ""
            lines.append(f"{indent}{decorators}{prefix} {node.name}({args}){ret}: ...")
    return "\n".join(lines) if lines else _compress_generic(source)


def _format_decorators(
    decorators: list[Any], source: str,
) -> str:
    parts: list[str] = []
    for d in decorators:
        seg = ast.get_source_segment(source, d)
        if seg:
            parts.append(f"@{seg}\n")
    return "".join(parts)


def _is_method(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    tree: ast.Module,
) -> bool:
    for cls in ast.walk(tree):
        if isinstance(cls, ast.ClassDef):
            for child in ast.iter_child_nodes(cls):
                if child is node:
                    return True
    return False


def _compress_generic(source: str) -> str:
    signatures: list[str] = []
    for pattern in (_CLASS_RE, _FUNC_RE, _METHOD_RE):
        for match in pattern.finditer(source):
            sig = match.group(1).rstrip()
            if sig not in signatures:
                signatures.append(sig)
    return "\n".join(signatures) if signatures else source[:500]
