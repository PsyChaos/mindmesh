from __future__ import annotations

import asyncio
from pathlib import Path


class GitError(Exception):
    pass


class GitContext:
    def __init__(self, cwd: str | Path | None = None) -> None:
        self._cwd = str(cwd) if cwd else None

    @property
    def cwd(self) -> str | None:
        return self._cwd

    async def _run(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._cwd,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise GitError(stderr.decode().strip() or f"git {' '.join(args)} failed")
        return stdout.decode()

    async def diff_head(self) -> str:
        return (await self._run("diff", "HEAD")).strip()

    async def diff_staged(self) -> str:
        return (await self._run("diff", "--staged")).strip()

    async def diff_branch(self, base_branch: str) -> str:
        return (await self._run("diff", f"{base_branch}...HEAD")).strip()

    async def smart_diff(self, base_branch: str | None = None) -> str:
        result = await self.diff_head()
        if result:
            return result
        branch = await self.detect_base_branch(base_branch)
        try:
            result = await self.diff_branch(branch)
        except GitError:
            return ""
        return result

    async def detect_base_branch(self, configured: str | None = None) -> str:
        if configured:
            return configured
        try:
            output = await self._run("remote", "show", "origin")
            for line in output.splitlines():
                stripped = line.strip()
                if stripped.startswith("HEAD branch:"):
                    return stripped.split(":", 1)[1].strip()
        except GitError:
            pass
        try:
            branches_output = await self._run("branch", "--list")
            branches = [b.strip().lstrip("* ") for b in branches_output.splitlines()]
            if "main" in branches:
                return "main"
            if "master" in branches:
                return "master"
        except GitError:
            pass
        return "main"

    async def list_files(self, path: str) -> list[str]:
        output = await self._run("ls-files", "--", path)
        return [line for line in output.splitlines() if line]

    async def log_oneline(self, count: int = 10) -> str:
        return (await self._run(
            "log", "--oneline", f"-{count}",
        )).strip()

    async def branch_log(self, base_branch: str | None = None) -> str:
        branch = await self.detect_base_branch(base_branch)
        try:
            return (await self._run(
                "log", "--oneline", f"{branch}..HEAD",
            )).strip()
        except GitError:
            return await self.log_oneline(20)

    async def current_branch(self) -> str:
        return (await self._run(
            "rev-parse", "--abbrev-ref", "HEAD",
        )).strip()
