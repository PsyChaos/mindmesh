"""Git worktree isolation for safe patch testing."""

from __future__ import annotations

import asyncio
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from mindmesh.config import SandboxConfig


@dataclass
class WorktreeResult:
    worktree_path: str
    branch_name: str
    patch_applied: bool
    test_exit_code: int | None = None
    test_output: str = ""
    error: str | None = None
    sandboxed: bool = False


@dataclass
class WorktreeManager:
    repo_path: Path = field(default_factory=Path.cwd)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)

    async def _git(
        self, *args: str, cwd: Path | None = None,
    ) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd or self.repo_path),
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode(),
            stderr.decode(),
        )

    async def create(
        self, prefix: str = "mindmesh-wt",
    ) -> tuple[Path, str]:
        branch = f"{prefix}-{uuid.uuid4().hex[:8]}"
        wt_path = self.repo_path / ".worktrees" / branch
        wt_path.parent.mkdir(parents=True, exist_ok=True)

        code, _, err = await self._git(
            "worktree", "add", "-b", branch, str(wt_path),
        )
        if code != 0:
            raise RuntimeError(
                f"Failed to create worktree: {err.strip()}",
            )
        return wt_path, branch

    async def apply_patch(
        self, wt_path: Path, patch_content: str,
    ) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "git", "apply", "--check", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(wt_path),
        )
        _, _ = await proc.communicate(patch_content.encode())
        if proc.returncode != 0:
            return False

        proc2 = await asyncio.create_subprocess_exec(
            "git", "apply", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(wt_path),
        )
        await proc2.communicate(patch_content.encode())
        return proc2.returncode == 0

    async def run_command(
        self, wt_path: Path, command: list[str], timeout: float = 120.0,
    ) -> tuple[int, str, bool]:
        if self.sandbox.enabled:
            if await self._docker_available():
                return await self._run_in_docker(wt_path, command, timeout)
            raise RuntimeError(
                "Sandbox enabled but Docker is not available. "
                "Install Docker or set sandbox.enabled=false in .mindmesh.yml"
            )
        return *await self._run_local(wt_path, command, timeout), False

    async def _run_local(
        self, wt_path: Path, command: list[str], timeout: float,
    ) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(wt_path),
        )
        try:
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
            return proc.returncode or 0, stdout.decode()
        except TimeoutError:
            proc.kill()
            return -1, f"Command timed out after {timeout}s"

    async def _run_in_docker(
        self, wt_path: Path, command: list[str], timeout: float,
    ) -> tuple[int, str, bool]:
        docker_args = [
            "docker", "run", "--rm",
            "--volume", f"{wt_path}:/workspace:ro",
            "--workdir", "/workspace",
            "--memory", self.sandbox.memory_limit,
            f"--cpus={self.sandbox.cpu_limit}",
            "--user", "nobody",
            "--read-only",
            "--tmpfs", "/tmp:rw,size=64m",
        ]
        if not self.sandbox.network:
            docker_args.append("--network=none")

        docker_args.append(self.sandbox.image)
        docker_args.extend(command)

        proc = await asyncio.create_subprocess_exec(
            *docker_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
            return proc.returncode or 0, stdout.decode(), True
        except TimeoutError:
            proc.kill()
            return -1, f"Docker command timed out after {timeout}s", True

    async def _docker_available(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def cleanup(self, wt_path: Path, branch: str) -> None:
        await self._git("worktree", "remove", str(wt_path), "--force")
        await self._git("branch", "-D", branch)
        if wt_path.exists():
            shutil.rmtree(wt_path, ignore_errors=True)

    async def test_patch(
        self,
        patch_content: str,
        test_command: list[str] | None = None,
        timeout: float = 120.0,
    ) -> WorktreeResult:
        wt_path, branch = await self.create()
        try:
            applied = await self.apply_patch(wt_path, patch_content)
            if not applied:
                return WorktreeResult(
                    worktree_path=str(wt_path),
                    branch_name=branch,
                    patch_applied=False,
                    error="Patch does not apply cleanly",
                )

            if test_command:
                exit_code, output, sandboxed = await self.run_command(
                    wt_path, test_command, timeout,
                )
                return WorktreeResult(
                    worktree_path=str(wt_path),
                    branch_name=branch,
                    patch_applied=True,
                    test_exit_code=exit_code,
                    test_output=output,
                    sandboxed=sandboxed,
                )

            return WorktreeResult(
                worktree_path=str(wt_path),
                branch_name=branch,
                patch_applied=True,
            )
        finally:
            await self.cleanup(wt_path, branch)
