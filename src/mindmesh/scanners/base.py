"""Scanner base class for local security tools."""

from __future__ import annotations

import asyncio
import shutil
from abc import ABC, abstractmethod

from mindmesh.schemas import Finding


class Scanner(ABC):
    name: str

    def is_available(self) -> bool:
        return shutil.which(self.name) is not None

    @abstractmethod
    async def run(self, target: str) -> list[Finding]: ...

    async def _exec(
        self, *args: str, cwd: str | None = None,
    ) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode(),
            stderr.decode(),
        )


def get_available_scanners() -> list[Scanner]:
    from mindmesh.scanners.bandit import BanditScanner
    from mindmesh.scanners.semgrep import SemgrepScanner

    all_scanners: list[Scanner] = [BanditScanner(), SemgrepScanner()]
    return [s for s in all_scanners if s.is_available()]
