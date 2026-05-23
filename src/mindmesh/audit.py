"""Audit logging for MindMesh tool invocations."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

_DEFAULT_LOG_DIR = Path.home() / ".mindmesh" / "audit"


class AuditEntry(BaseModel):
    timestamp: str
    tool: str
    scope: str
    endpoints_called: list[str]
    endpoints_succeeded: list[str]
    endpoints_failed: list[str]
    findings_count: int
    context_size_kb: float
    redacted_secrets: int
    duration_ms: int
    status: Literal["success", "partial", "error"]


class AuditLogger:
    def __init__(self, log_dir: Path | None = None) -> None:
        self._log_dir = log_dir or _DEFAULT_LOG_DIR

    def _today_file(self) -> Path:
        date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        return self._log_dir / f"{date_str}.jsonl"

    def log(self, entry: AuditEntry) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        with open(self._today_file(), "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

    def get_recent(self, count: int = 20) -> list[AuditEntry]:
        log_file = self._today_file()
        if not log_file.exists():
            return []
        with open(log_file, encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
        return [AuditEntry.model_validate_json(line) for line in lines[-count:]]
