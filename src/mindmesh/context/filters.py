"""Context filter: applies policy and size limits to candidate files."""

from __future__ import annotations

import re

from pydantic import BaseModel

from mindmesh.config import LimitsConfig
from mindmesh.context.collector import FileContext
from mindmesh.policy.file_policy import FilePolicy

_GENERATED_PATH_PATTERNS: tuple[str, ...] = ("generated", "min.", ".min.")
_GENERATED_HEADER_RE = re.compile(
    r"(auto[-\s]?generated|do not edit|this file is generated|code generated)",
    re.IGNORECASE,
)
_NON_ASCII_THRESHOLD = 0.30
_AVG_LINE_LENGTH_THRESHOLD = 500


class FilterReport(BaseModel):
    total_candidates: int
    passed: int
    blocked_by_policy: list[str] = []
    blocked_by_binary: list[str] = []
    blocked_by_size: list[str] = []
    blocked_by_total_limit: list[str] = []
    blocked_by_generated: list[str] = []


def is_binary(content: str) -> bool:
    return "\x00" in content


def is_generated_or_minified(path: str, content: str) -> bool:
    path_lower = path.lower()
    if any(pat in path_lower for pat in _GENERATED_PATH_PATTERNS):
        return True

    lines = content.splitlines()
    if lines and _GENERATED_HEADER_RE.search(lines[0]):
        return True

    if lines:
        avg_length = sum(len(ln) for ln in lines) / len(lines)
        if avg_length > _AVG_LINE_LENGTH_THRESHOLD:
            return True

    return False


class ContextFilter:
    def __init__(self, file_policy: FilePolicy, limits: LimitsConfig) -> None:
        self._policy = file_policy
        self._limits = limits

    def filter(self, files: list[FileContext]) -> tuple[list[FileContext], FilterReport]:
        passed: list[FileContext] = []
        blocked_policy: list[str] = []
        blocked_binary: list[str] = []
        blocked_size: list[str] = []
        blocked_total: list[str] = []
        blocked_generated: list[str] = []

        total_kb = 0.0
        total_limit_hit = False

        for fc in files:
            if total_limit_hit:
                blocked_total.append(fc.path)
                continue

            if self._policy.is_blocked(fc.path):
                blocked_policy.append(fc.path)
                continue

            if is_binary(fc.content):
                blocked_binary.append(fc.path)
                continue

            if is_generated_or_minified(fc.path, fc.content):
                blocked_generated.append(fc.path)
                continue

            file_kb = len(fc.content.encode("utf-8")) / 1024
            if file_kb > self._limits.max_file_size_kb:
                blocked_size.append(fc.path)
                continue

            if total_kb + file_kb > self._limits.max_total_context_kb:
                total_limit_hit = True
                blocked_total.append(fc.path)
                continue

            total_kb += file_kb
            passed.append(fc)

        report = FilterReport(
            total_candidates=len(files),
            passed=len(passed),
            blocked_by_policy=blocked_policy,
            blocked_by_binary=blocked_binary,
            blocked_by_size=blocked_size,
            blocked_by_total_limit=blocked_total,
            blocked_by_generated=blocked_generated,
        )
        return passed, report
