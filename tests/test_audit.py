"""Tests for audit logging."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from mindmesh.audit import AuditEntry, AuditLogger


def _make_entry(**kwargs: object) -> AuditEntry:
    defaults: dict[str, object] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "tool": "review",
        "scope": "git_diff",
        "endpoints_called": ["ep1"],
        "endpoints_succeeded": ["ep1"],
        "endpoints_failed": [],
        "findings_count": 3,
        "context_size_kb": 10.5,
        "redacted_secrets": 0,
        "duration_ms": 150,
        "status": "success",
    }
    defaults.update(kwargs)
    return AuditEntry(**defaults)  # type: ignore[arg-type]


def test_audit_entry_created_correctly() -> None:
    entry = _make_entry()
    assert entry.tool == "review"
    assert entry.scope == "git_diff"
    assert entry.status == "success"
    assert entry.findings_count == 3
    assert entry.endpoints_called == ["ep1"]
    assert entry.endpoints_succeeded == ["ep1"]
    assert entry.endpoints_failed == []


def test_log_writes_jsonl(tmp_path: Path) -> None:
    logger = AuditLogger(log_dir=tmp_path)
    entry = _make_entry()
    logger.log(entry)

    date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    log_file = tmp_path / f"{date_str}.jsonl"
    assert log_file.exists()
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["tool"] == "review"
    assert data["status"] == "success"
    assert data["findings_count"] == 3


def test_get_recent_returns_last_n(tmp_path: Path) -> None:
    logger = AuditLogger(log_dir=tmp_path)
    for i in range(5):
        logger.log(_make_entry(findings_count=i))

    recent = logger.get_recent(3)
    assert len(recent) == 3
    assert recent[0].findings_count == 2
    assert recent[1].findings_count == 3
    assert recent[2].findings_count == 4


def test_log_dir_created_if_missing(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested" / "audit"
    assert not nested.exists()
    logger = AuditLogger(log_dir=nested)
    logger.log(_make_entry())
    assert nested.exists()
    assert any(nested.iterdir())


def test_get_recent_empty_if_no_file(tmp_path: Path) -> None:
    logger = AuditLogger(log_dir=tmp_path)
    result = logger.get_recent()
    assert result == []


def test_multiple_log_writes_and_reads(tmp_path: Path) -> None:
    logger = AuditLogger(log_dir=tmp_path)
    for i in range(4):
        logger.log(_make_entry(tool=f"tool_{i}", findings_count=i))

    recent = logger.get_recent(10)
    assert len(recent) == 4
    assert [e.tool for e in recent] == [f"tool_{i}" for i in range(4)]
    assert [e.findings_count for e in recent] == list(range(4))


def test_audit_failure_does_not_block_tool() -> None:
    from mindmesh.config import MindMeshConfig
    from mindmesh.tools.review import try_log_audit

    config = MindMeshConfig()
    assert config.audit.enabled is True

    start_time = time.monotonic()
    with patch("mindmesh.audit.AuditLogger.log", side_effect=OSError("disk full")):
        # Must not raise even though logger.log raises
        try_log_audit(
            config=config,
            tool="review",
            scope="git_diff",
            start_time=start_time,
            endpoints_called=["ep1"],
            endpoints_succeeded=["ep1"],
            endpoints_failed=[],
            findings_count=3,
            context_size_kb=10.5,
            redacted_secrets=0,
            status="success",
        )
    # Reaching here means no exception propagated


def test_audit_disabled_skips_logging(tmp_path: Path) -> None:
    from mindmesh.config import AuditConfig, MindMeshConfig
    from mindmesh.tools.review import try_log_audit

    config = MindMeshConfig(audit=AuditConfig(enabled=False, log_dir=str(tmp_path)))
    start_time = time.monotonic()
    try_log_audit(
        config=config,
        tool="review",
        scope="git_diff",
        start_time=start_time,
        endpoints_called=["ep1"],
        endpoints_succeeded=["ep1"],
        endpoints_failed=[],
        findings_count=1,
        context_size_kb=5.0,
        redacted_secrets=0,
        status="success",
    )
    # No file should have been written
    assert not any(tmp_path.iterdir())
