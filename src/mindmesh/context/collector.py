from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from mindmesh.config import MindMeshConfig
from mindmesh.context.git import GitContext

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".js": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
}


def detect_language(path: str) -> str:
    ext = Path(path).suffix.lower()
    return LANGUAGE_MAP.get(ext, "text")


class FileContext(BaseModel):
    path: str
    content: str
    language: str
    scope_type: Literal["diff", "file"]
    start_line: int | None = None
    end_line: int | None = None


def _parse_diff(diff_output: str) -> list[FileContext]:
    if not diff_output.strip():
        return []

    results: list[FileContext] = []
    for section in diff_output.split("diff --git ")[1:]:
        lines = section.splitlines()
        path: str | None = None
        content_lines: list[str] = []
        start_line: int | None = None
        end_line: int | None = None

        for line in lines:
            if line.startswith("+++ b/"):
                path = line[6:]
            elif line.startswith("@@ "):
                try:
                    new_info = line.split("+")[1].split()[0]
                    parts = new_info.split(",")
                    new_start = int(parts[0])
                    new_count = int(parts[1]) if len(parts) > 1 else 1
                    if start_line is None:
                        start_line = new_start
                    end_line = new_start + max(0, new_count - 1)
                except (IndexError, ValueError):
                    pass
                content_lines.append(line)
            elif not line.startswith((
                "--- ", "index ", "new file", "deleted file",
                "old mode", "new mode", "Binary files",
                "similarity", "rename",
            )):
                content_lines.append(line)

        if path is not None:
            results.append(
                FileContext(
                    path=path,
                    content="\n".join(content_lines),
                    language=detect_language(path),
                    scope_type="diff",
                    start_line=start_line,
                    end_line=end_line,
                )
            )

    return results


class ContextCollector:
    def __init__(self, git: GitContext, config: MindMeshConfig) -> None:
        self._git = git
        self._config = config

    async def collect(self, scope: str) -> list[FileContext]:
        if scope == "git_diff":
            diff = await self._git.smart_diff(self._config.project.base_branch)
            return _parse_diff(diff)
        if scope == "staged":
            diff = await self._git.diff_staged()
            return _parse_diff(diff)
        if scope == "branch":
            base = self._config.project.base_branch or await self._git.detect_base_branch()
            diff = await self._git.diff_branch(base)
            return _parse_diff(diff)
        if scope.startswith("skeleton:"):
            path = scope[len("skeleton:"):]
            from mindmesh.context.compressor import compress_files
            files = await self._collect_path(path)
            return compress_files(files)
        return await self._collect_path(scope)

    async def _collect_path(self, path: str) -> list[FileContext]:
        base = (Path(self._git.cwd) if self._git.cwd else Path.cwd()).resolve()
        target = (base / path).resolve()

        if not target.is_relative_to(base):
            raise PermissionError(f"Access outside workspace is not allowed: {path}")

        if not target.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        if target.is_file():
            content = await asyncio.to_thread(target.read_text, errors="replace")
            return [FileContext(
                path=path, content=content,
                language=detect_language(path), scope_type="file",
            )]

        file_paths = await self._git.list_files(path)

        async def _read(fp: str) -> FileContext:
            content = await asyncio.to_thread((base / fp).read_text, errors="replace")
            return FileContext(
                path=fp, content=content,
                language=detect_language(fp), scope_type="file",
            )

        return list(await asyncio.gather(*[_read(fp) for fp in file_paths]))


def format_context(files: list[FileContext]) -> str:
    parts: list[str] = []
    for fc in files:
        label = "modified" if fc.scope_type == "diff" else "file"
        header = f"## File: {fc.path} ({label})\nLanguage: {fc.language}"
        if fc.start_line is not None and fc.end_line is not None:
            header += f"\nLines: {fc.start_line}-{fc.end_line}"
        parts.append(f"{header}\n\n{fc.content}")
    return "\n\n".join(parts)
