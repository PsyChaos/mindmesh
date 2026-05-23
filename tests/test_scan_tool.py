"""Tests for local_scan tool and scanner infrastructure."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindmesh.scanners.bandit import BanditScanner
from mindmesh.scanners.base import Scanner, get_available_scanners
from mindmesh.scanners.semgrep import SemgrepScanner
from mindmesh.schemas import Finding
from mindmesh.tools.scan import local_scan

_BANDIT_OUTPUT = json.dumps({
    "results": [
        {
            "test_id": "B101",
            "test_name": "assert_used",
            "issue_severity": "LOW",
            "issue_confidence": "HIGH",
            "issue_text": "Use of assert detected.",
            "filename": "src/main.py",
            "line_number": 10,
            "more_info": "https://bandit.readthedocs.io",
        },
        {
            "test_id": "B105",
            "test_name": "hardcoded_password_string",
            "issue_severity": "HIGH",
            "issue_confidence": "MEDIUM",
            "issue_text": "Possible hardcoded password.",
            "filename": "src/auth.py",
            "line_number": 42,
            "more_info": "https://bandit.readthedocs.io",
        },
    ],
})

_SEMGREP_OUTPUT = json.dumps({
    "results": [
        {
            "check_id": "python.lang.security.audit.exec-used",
            "path": "src/util.py",
            "start": {"line": 15},
            "extra": {
                "severity": "ERROR",
                "message": "Use of exec() detected.",
                "fix": "Avoid exec; use safer alternatives.",
            },
        },
    ],
})


# --- Scanner detection ---


def test_scanner_is_available_true() -> None:
    s = BanditScanner()
    with patch("shutil.which", return_value="/usr/bin/bandit"):
        assert s.is_available() is True


def test_scanner_is_available_false() -> None:
    s = BanditScanner()
    with patch("shutil.which", return_value=None):
        assert s.is_available() is False


def test_get_available_scanners_filters() -> None:
    with patch("shutil.which", return_value=None):
        assert get_available_scanners() == []


# --- BanditScanner ---


@pytest.mark.asyncio
async def test_bandit_parse_findings() -> None:
    scanner = BanditScanner()
    with patch.object(
        scanner, "_exec",
        new=AsyncMock(return_value=(1, _BANDIT_OUTPUT, "")),
    ):
        findings = await scanner.run("src/")

    assert len(findings) == 2
    assert findings[0].severity == "low"
    assert findings[0].file == "src/main.py"
    assert findings[0].line == 10
    assert "B101" in findings[0].title
    assert findings[1].severity == "high"
    assert findings[1].confidence == 0.7


@pytest.mark.asyncio
async def test_bandit_empty_output() -> None:
    scanner = BanditScanner()
    with patch.object(
        scanner, "_exec",
        new=AsyncMock(return_value=(0, "", "")),
    ):
        findings = await scanner.run("src/")
    assert findings == []


@pytest.mark.asyncio
async def test_bandit_invalid_json() -> None:
    scanner = BanditScanner()
    with patch.object(
        scanner, "_exec",
        new=AsyncMock(return_value=(1, "not json", "")),
    ):
        findings = await scanner.run("src/")
    assert findings == []


# --- SemgrepScanner ---


@pytest.mark.asyncio
async def test_semgrep_parse_findings() -> None:
    scanner = SemgrepScanner()
    with patch.object(
        scanner, "_exec",
        new=AsyncMock(return_value=(0, _SEMGREP_OUTPUT, "")),
    ):
        findings = await scanner.run("src/")

    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].file == "src/util.py"
    assert findings[0].line == 15
    assert "exec-used" in findings[0].title


@pytest.mark.asyncio
async def test_semgrep_empty_output() -> None:
    scanner = SemgrepScanner()
    with patch.object(
        scanner, "_exec",
        new=AsyncMock(return_value=(0, "", "")),
    ):
        findings = await scanner.run("src/")
    assert findings == []


# --- local_scan tool ---


@pytest.mark.asyncio
async def test_local_scan_no_scanners() -> None:
    with patch(
        "mindmesh.tools.scan.get_available_scanners",
        return_value=[],
    ):
        result = await local_scan()
    assert "error" in result
    assert "No scanners" in result["error"]


@pytest.mark.asyncio
async def test_local_scan_unknown_scanner() -> None:
    fake = MagicMock(spec=Scanner)
    fake.name = "bandit"
    with patch(
        "mindmesh.tools.scan.get_available_scanners",
        return_value=[fake],
    ):
        result = await local_scan(scanner="nonexistent")
    assert "error" in result
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_local_scan_runs_and_returns_findings() -> None:
    fake = MagicMock(spec=Scanner)
    fake.name = "bandit"
    fake.run = AsyncMock(return_value=[
        Finding(
            endpoint="local:bandit",
            provider="bandit",
            model="bandit",
            severity="high",
            category="security",
            file="src/auth.py",
            line=42,
            title="[B105] hardcoded_password",
            explanation="Possible hardcoded password.",
            confidence=0.9,
        ),
    ])
    with patch(
        "mindmesh.tools.scan.get_available_scanners",
        return_value=[fake],
    ):
        result = await local_scan(target="src/")

    assert result["metadata"]["total_findings"] == 1
    assert result["findings"][0]["severity"] == "high"


@pytest.mark.asyncio
async def test_local_scan_min_severity_filters() -> None:
    fake = MagicMock(spec=Scanner)
    fake.name = "bandit"
    fake.run = AsyncMock(return_value=[
        Finding(
            endpoint="local:bandit", provider="bandit",
            model="bandit", severity="high", category="security",
            title="High issue", explanation="desc", confidence=0.9,
        ),
        Finding(
            endpoint="local:bandit", provider="bandit",
            model="bandit", severity="low", category="security",
            title="Low issue", explanation="desc", confidence=0.5,
        ),
    ])
    with patch(
        "mindmesh.tools.scan.get_available_scanners",
        return_value=[fake],
    ):
        result = await local_scan(min_severity="high")

    assert result["metadata"]["total_findings"] == 1
    assert result["findings"][0]["severity"] == "high"


@pytest.mark.asyncio
async def test_local_scan_scanner_error_handled() -> None:
    fake = MagicMock(spec=Scanner)
    fake.name = "bandit"
    fake.run = AsyncMock(
        side_effect=RuntimeError("scanner crashed"),
    )
    with patch(
        "mindmesh.tools.scan.get_available_scanners",
        return_value=[fake],
    ):
        result = await local_scan()

    assert len(result["endpoint_errors"]) == 1
    err = result["endpoint_errors"][0]
    assert err["error_code"] == "SCANNER_ERROR"
