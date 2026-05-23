from __future__ import annotations

from pathlib import Path

import pathspec

from mindmesh.config import PrivacyConfig


class FilePolicy:
    def __init__(self, config: PrivacyConfig) -> None:
        self._block_spec = pathspec.PathSpec.from_lines("gitignore", config.block_files)
        self._block_dirs: frozenset[str] = frozenset(config.block_dirs)

    def is_blocked(self, path: str | Path) -> bool:
        normalized = Path(path)
        if self._block_spec.match_file(str(normalized)):
            return True
        parts = normalized.parts
        return bool(parts and parts[0] in self._block_dirs)

    def filter_paths(self, paths: list[str]) -> tuple[list[str], list[str]]:
        allowed: list[str] = []
        blocked: list[str] = []
        for p in paths:
            (blocked if self.is_blocked(p) else allowed).append(p)
        return allowed, blocked
