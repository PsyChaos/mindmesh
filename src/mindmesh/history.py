"""SQLite-backed run history for CLI dashboard."""

from __future__ import annotations

import contextlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_DB = Path.home() / ".mindmesh" / "history.db"

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    tool TEXT NOT NULL,
    scope TEXT NOT NULL,
    endpoints_called TEXT NOT NULL,
    endpoints_succeeded TEXT NOT NULL,
    endpoints_failed TEXT NOT NULL,
    findings_count INTEGER NOT NULL,
    context_size_kb REAL NOT NULL,
    redacted_secrets INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    status TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0
);
"""

_MIGRATE_SQL = [
    "ALTER TABLE runs ADD COLUMN input_tokens INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE runs ADD COLUMN output_tokens INTEGER NOT NULL DEFAULT 0",
]


@dataclass
class RunRecord:
    id: int
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
    status: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ProviderStats:
    provider: str
    total_calls: int
    successes: int
    failures: int
    success_rate: float
    avg_duration_ms: float
    total_findings: int
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class HistoryStore:
    def __init__(self, db_path: Path | None = None) -> None:
        path = db_path or _DEFAULT_DB
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute(_INIT_SQL)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        for sql in _MIGRATE_SQL:
            with contextlib.suppress(sqlite3.OperationalError):
                self._conn.execute(sql)

    def record(
        self,
        timestamp: str,
        tool: str,
        scope: str,
        endpoints_called: list[str],
        endpoints_succeeded: list[str],
        endpoints_failed: list[str],
        findings_count: int,
        context_size_kb: float,
        redacted_secrets: int,
        duration_ms: int,
        status: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO runs "
            "(timestamp, tool, scope, endpoints_called, endpoints_succeeded, "
            "endpoints_failed, findings_count, context_size_kb, "
            "redacted_secrets, duration_ms, status, "
            "input_tokens, output_tokens) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                timestamp, tool, scope,
                json.dumps(endpoints_called),
                json.dumps(endpoints_succeeded),
                json.dumps(endpoints_failed),
                findings_count, context_size_kb,
                redacted_secrets, duration_ms, status,
                input_tokens, output_tokens,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid or 0

    def recent(self, count: int = 20) -> list[RunRecord]:
        rows = self._conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (count,),
        ).fetchall()
        return [self._to_record(row) for row in rows]

    def get(self, run_id: int) -> RunRecord | None:
        row = self._conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,),
        ).fetchone()
        return self._to_record(row) if row else None

    def stats(self) -> list[ProviderStats]:
        rows = self._conn.execute(
            "SELECT endpoints_called, endpoints_succeeded, "
            "endpoints_failed, findings_count, duration_ms, "
            "input_tokens, output_tokens "
            "FROM runs",
        ).fetchall()

        per_provider: dict[str, dict[str, float]] = {}
        for row in rows:
            called_json, succ_json, fail_json = row[0], row[1], row[2]
            findings, duration = row[3], row[4]
            in_tok, out_tok = row[5], row[6]
            called: list[str] = json.loads(called_json)
            succeeded: list[str] = json.loads(succ_json)
            failed: list[str] = json.loads(fail_json)

            for ep in called:
                p = per_provider.setdefault(ep, {
                    "calls": 0, "successes": 0, "failures": 0,
                    "findings": 0, "duration_sum": 0,
                    "input_tokens": 0, "output_tokens": 0,
                })
                p["calls"] += 1
                p["duration_sum"] += duration
                p["findings"] += findings
                p["input_tokens"] += in_tok
                p["output_tokens"] += out_tok
                if ep in succeeded:
                    p["successes"] += 1
                if ep in failed:
                    p["failures"] += 1

        result: list[ProviderStats] = []
        for provider, s in sorted(per_provider.items()):
            calls = int(s["calls"])
            result.append(ProviderStats(
                provider=provider,
                total_calls=calls,
                successes=int(s["successes"]),
                failures=int(s["failures"]),
                success_rate=s["successes"] / calls if calls else 0,
                avg_duration_ms=s["duration_sum"] / calls if calls else 0,
                total_findings=int(s["findings"]),
                total_input_tokens=int(s["input_tokens"]),
                total_output_tokens=int(s["output_tokens"]),
            ))
        return result

    def clear(self) -> int:
        cursor = self._conn.execute("DELETE FROM runs")
        self._conn.commit()
        return cursor.rowcount

    def _to_record(self, row: tuple[object, ...]) -> RunRecord:
        return RunRecord(
            id=int(row[0]),  # type: ignore[arg-type]
            timestamp=str(row[1]),
            tool=str(row[2]),
            scope=str(row[3]),
            endpoints_called=json.loads(str(row[4])),
            endpoints_succeeded=json.loads(str(row[5])),
            endpoints_failed=json.loads(str(row[6])),
            findings_count=int(row[7]),  # type: ignore[arg-type]
            context_size_kb=float(row[8]),  # type: ignore[arg-type]
            redacted_secrets=int(row[9]),  # type: ignore[arg-type]
            duration_ms=int(row[10]),  # type: ignore[arg-type]
            status=str(row[11]),
            input_tokens=int(row[12]) if len(row) > 12 else 0,  # type: ignore[arg-type]
            output_tokens=int(row[13]) if len(row) > 13 else 0,  # type: ignore[arg-type]
        )

    def close(self) -> None:
        self._conn.close()
