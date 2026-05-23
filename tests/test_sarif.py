"""Tests for SARIF output formatter."""

from __future__ import annotations

from mindmesh.output.sarif import findings_to_sarif
from mindmesh.schemas import Finding


def _finding(
    severity: str = "high",
    category: str = "bug",
    file: str | None = "src/main.py",
    line: int | None = 10,
    title: str = "Issue found",
    recommendation: str | None = "Fix it",
) -> Finding:
    return Finding(
        endpoint="ep1",
        provider="openai",
        model="gpt-4o",
        severity=severity,  # type: ignore[arg-type]
        category=category,  # type: ignore[arg-type]
        file=file,
        line=line,
        title=title,
        explanation="Something is wrong.",
        recommendation=recommendation,
        confidence=0.9,
    )


def test_empty_findings() -> None:
    sarif = findings_to_sarif([])
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"]) == 1
    assert sarif["runs"][0]["results"] == []


def test_single_finding_structure() -> None:
    sarif = findings_to_sarif([_finding()])
    run = sarif["runs"][0]
    assert len(run["results"]) == 1
    result = run["results"][0]
    assert result["ruleId"] == "bug/high"
    assert result["level"] == "error"
    assert result["message"]["text"] == "Issue found"


def test_severity_to_level_mapping() -> None:
    for sev, expected in [
        ("critical", "error"),
        ("high", "error"),
        ("medium", "warning"),
        ("low", "note"),
        ("info", "note"),
    ]:
        sarif = findings_to_sarif([_finding(severity=sev)])
        assert sarif["runs"][0]["results"][0]["level"] == expected


def test_location_with_file_and_line() -> None:
    sarif = findings_to_sarif([_finding(file="a.py", line=42)])
    loc = sarif["runs"][0]["results"][0]["locations"][0]
    assert loc["physicalLocation"]["artifactLocation"]["uri"] == "a.py"
    assert loc["physicalLocation"]["region"]["startLine"] == 42


def test_location_file_only_no_line() -> None:
    sarif = findings_to_sarif([_finding(file="a.py", line=None)])
    loc = sarif["runs"][0]["results"][0]["locations"][0]
    assert loc["physicalLocation"]["artifactLocation"]["uri"] == "a.py"
    assert "region" not in loc["physicalLocation"]


def test_no_file_no_locations() -> None:
    sarif = findings_to_sarif([_finding(file=None, line=None)])
    assert "locations" not in sarif["runs"][0]["results"][0]


def test_recommendation_as_fix() -> None:
    sarif = findings_to_sarif([_finding(recommendation="Use parameterized queries")])
    fixes = sarif["runs"][0]["results"][0]["fixes"]
    assert len(fixes) == 1
    assert fixes[0]["description"]["text"] == "Use parameterized queries"


def test_no_recommendation_no_fixes() -> None:
    sarif = findings_to_sarif([_finding(recommendation=None)])
    assert "fixes" not in sarif["runs"][0]["results"][0]


def test_rules_deduplicated() -> None:
    findings = [_finding(severity="high", category="bug") for _ in range(3)]
    sarif = findings_to_sarif(findings)
    rules = sarif["runs"][0]["tool"]["driver"]["rules"]
    assert len(rules) == 1
    assert rules[0]["id"] == "bug/high"


def test_multiple_rules() -> None:
    findings = [
        _finding(severity="high", category="bug"),
        _finding(severity="medium", category="security"),
    ]
    sarif = findings_to_sarif(findings)
    rules = sarif["runs"][0]["tool"]["driver"]["rules"]
    assert len(rules) == 2


def test_properties_contain_metadata() -> None:
    sarif = findings_to_sarif([_finding()])
    props = sarif["runs"][0]["results"][0]["properties"]
    assert props["endpoint"] == "ep1"
    assert props["provider"] == "openai"
    assert props["confidence"] == 0.9
