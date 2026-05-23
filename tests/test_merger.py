"""Tests for FindingsMerger."""

import pytest

from mindmesh.output.merger import FindingsMerger
from mindmesh.schemas import Finding


def make_finding(
    endpoint: str = "ep1",
    provider: str = "openai",
    model: str = "gpt-4o",
    severity: str = "medium",
    category: str = "bug",
    file: str | None = "src/main.py",
    line: int | None = 10,
    title: str = "Issue",
) -> Finding:
    return Finding(
        endpoint=endpoint,
        provider=provider,
        model=model,
        severity=severity,  # type: ignore[arg-type]
        category=category,  # type: ignore[arg-type]
        file=file,
        line=line,
        title=title,
        explanation="An issue was found.",
        recommendation="Fix it.",
        confidence=0.9,
    )


@pytest.fixture
def merger() -> FindingsMerger:
    return FindingsMerger()


# --- Flattening ---

def test_single_endpoint_flattened(merger: FindingsMerger) -> None:
    findings = [make_finding(title="A"), make_finding(title="B")]
    result = merger.merge({"ep1": findings})
    assert len(result.all_findings) == 2


def test_multiple_endpoints_flattened(merger: FindingsMerger) -> None:
    result = merger.merge({
        "ep1": [make_finding(endpoint="ep1", title="A")],
        "ep2": [make_finding(endpoint="ep2", title="B"), make_finding(endpoint="ep2", title="C")],
    })
    assert len(result.all_findings) == 3


def test_empty_input_returns_empty_result(merger: FindingsMerger) -> None:
    result = merger.merge({})
    assert result.all_findings == []
    assert result.match_hints == []
    assert result.endpoints_represented == []
    assert result.findings_per_endpoint == {}


# --- Match hints ---

def test_same_file_line_category_matches(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [make_finding(endpoint="ep1", file="a.py", line=10, category="bug")],
        "ep2": [make_finding(endpoint="ep2", file="a.py", line=10, category="bug")],
    }
    result = merger.merge(findings_by_ep)
    assert len(result.match_hints) == 1
    assert result.match_hints[0].finding_indices == [0, 1]


def test_same_file_line_within_5_matches(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [make_finding(endpoint="ep1", file="a.py", line=10, category="security")],
        "ep2": [make_finding(endpoint="ep2", file="a.py", line=15, category="security")],
    }
    result = merger.merge(findings_by_ep)
    assert len(result.match_hints) == 1


def test_same_file_line_diff_greater_than_5_no_match(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [make_finding(
            endpoint="ep1", file="a.py", line=10, category="bug", title="Null ref",
        )],
        "ep2": [make_finding(
            endpoint="ep2", file="a.py", line=16, category="bug", title="Memory leak",
        )],
    }
    result = merger.merge(findings_by_ep)
    assert result.match_hints == []


def test_different_category_no_match(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [make_finding(endpoint="ep1", file="a.py", line=10, category="bug")],
        "ep2": [make_finding(endpoint="ep2", file="a.py", line=10, category="security")],
    }
    result = merger.merge(findings_by_ep)
    assert result.match_hints == []


def test_different_file_no_match(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [make_finding(endpoint="ep1", file="a.py", line=10, category="bug")],
        "ep2": [make_finding(endpoint="ep2", file="b.py", line=10, category="bug")],
    }
    result = merger.merge(findings_by_ep)
    assert result.match_hints == []


def test_file_none_different_title_no_match(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [make_finding(
            endpoint="ep1", file=None, line=10, category="bug", title="Null ref",
        )],
        "ep2": [make_finding(
            endpoint="ep2", file=None, line=10, category="bug", title="Memory leak",
        )],
    }
    result = merger.merge(findings_by_ep)
    assert result.match_hints == []


def test_line_none_different_title_no_match(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [make_finding(
            endpoint="ep1", file="a.py", line=None, category="bug", title="Null ref",
        )],
        "ep2": [make_finding(
            endpoint="ep2", file="a.py", line=None, category="bug", title="Memory leak",
        )],
    }
    result = merger.merge(findings_by_ep)
    assert result.match_hints == []


# --- Counts and endpoints ---

def test_findings_per_endpoint_correct(merger: FindingsMerger) -> None:
    result = merger.merge({
        "ep1": [make_finding(), make_finding()],
        "ep2": [make_finding()],
    })
    assert result.findings_per_endpoint == {"ep1": 2, "ep2": 1}


def test_endpoints_represented_correct(merger: FindingsMerger) -> None:
    result = merger.merge({"ep1": [], "ep2": []})
    assert set(result.endpoints_represented) == {"ep1", "ep2"}


# --- Three endpoint, two match groups scenario ---

def test_three_endpoints_two_match_groups(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [
            make_finding(endpoint="ep1", file="a.py", line=10, category="bug", title="Bug A"),
            make_finding(endpoint="ep1", file="b.py", line=50, category="security", title="Sec A"),
        ],
        "ep2": [
            make_finding(endpoint="ep2", file="a.py", line=12, category="bug", title="Bug B"),
            make_finding(endpoint="ep2", file="c.py", line=1, category="bug", title="Unrelated"),
        ],
        "ep3": [
            make_finding(endpoint="ep3", file="b.py", line=52, category="security", title="Sec B"),
        ],
    }
    result = merger.merge(findings_by_ep)
    assert len(result.all_findings) == 5
    # ep1[0] (idx=0, a.py:10 bug) matches ep2[0] (idx=2, a.py:12 bug) → diff=2 ≤ 5
    # ep1[1] (idx=1, b.py:50 security) matches ep3[0] (idx=4, b.py:52 security) → diff=2 ≤ 5
    assert len(result.match_hints) == 2
    matched_pairs = {tuple(h.finding_indices) for h in result.match_hints}
    assert (0, 2) in matched_pairs
    assert (1, 4) in matched_pairs


# --- Title similarity matching ---


def test_title_similarity_match_same_file_category(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [make_finding(
            endpoint="ep1", file="a.py", line=10, category="bug",
            title="Null pointer dereference in auth",
        )],
        "ep2": [make_finding(
            endpoint="ep2", file="a.py", line=50, category="bug",
            title="Null pointer dereference in authentication",
        )],
    }
    result = merger.merge(findings_by_ep)
    assert len(result.match_hints) == 1
    assert "similar title" in result.match_hints[0].reason


def test_title_dissimilar_no_match(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [make_finding(
            endpoint="ep1", file="a.py", line=10, category="bug",
            title="Null pointer",
        )],
        "ep2": [make_finding(
            endpoint="ep2", file="a.py", line=50, category="bug",
            title="Memory leak overflow",
        )],
    }
    result = merger.merge(findings_by_ep)
    assert result.match_hints == []


def test_no_file_title_similarity_match(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [make_finding(
            endpoint="ep1", file=None, line=None, category="architecture",
            title="Missing error handling in pipeline",
        )],
        "ep2": [make_finding(
            endpoint="ep2", file=None, line=None, category="architecture",
            title="Missing error handling in data pipeline",
        )],
    }
    result = merger.merge(findings_by_ep)
    assert len(result.match_hints) == 1
    assert "similar title" in result.match_hints[0].reason


# --- Group merging (3+ endpoints) ---


def test_three_endpoints_grouped_into_single_hint(
    merger: FindingsMerger,
) -> None:
    findings_by_ep = {
        "ep1": [make_finding(
            endpoint="ep1", file="a.py", line=10, category="bug",
        )],
        "ep2": [make_finding(
            endpoint="ep2", file="a.py", line=11, category="bug",
        )],
        "ep3": [make_finding(
            endpoint="ep3", file="a.py", line=12, category="bug",
        )],
    }
    result = merger.merge(findings_by_ep)
    assert len(result.match_hints) == 1
    assert len(result.match_hints[0].finding_indices) == 3


# --- Same endpoint no match ---


def test_same_endpoint_findings_not_matched(merger: FindingsMerger) -> None:
    findings_by_ep = {
        "ep1": [
            make_finding(endpoint="ep1", file="a.py", line=10, category="bug"),
            make_finding(endpoint="ep1", file="a.py", line=11, category="bug"),
        ],
    }
    result = merger.merge(findings_by_ep)
    assert result.match_hints == []
