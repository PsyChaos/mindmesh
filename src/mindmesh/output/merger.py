"""Finding grouping and match hint generation. Decision stays with Claude."""

from __future__ import annotations

from pydantic import BaseModel

from mindmesh.schemas import Finding, MatchHint

_LINE_RANGE = 5
_TITLE_SIM_THRESHOLD = 0.5


class MergeResult(BaseModel):
    all_findings: list[Finding]
    match_hints: list[MatchHint]
    endpoints_represented: list[str]
    findings_per_endpoint: dict[str, int]


def _title_similarity(a: str, b: str) -> float:
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _is_match(a: Finding, b: Finding) -> tuple[bool, str]:
    if a.endpoint == b.endpoint:
        return False, ""
    if a.file and b.file and a.file == b.file and a.category == b.category:
        if (
            a.line is not None
            and b.line is not None
            and abs(a.line - b.line) <= _LINE_RANGE
        ):
            return True, f"same file + line range + {a.category}"
        if _title_similarity(a.title, b.title) >= _TITLE_SIM_THRESHOLD:
            return True, "same file + category + similar title"
    if (
        a.file is None
        and b.file is None
        and a.category == b.category
        and _title_similarity(a.title, b.title) >= _TITLE_SIM_THRESHOLD
    ):
        return True, "same category + similar title"
    return False, ""


class FindingsMerger:
    def merge(
        self, findings_by_endpoint: dict[str, list[Finding]],
    ) -> MergeResult:
        all_findings: list[Finding] = [
            f for findings in findings_by_endpoint.values()
            for f in findings
        ]
        return MergeResult(
            all_findings=all_findings,
            match_hints=self._find_matches(all_findings),
            endpoints_represented=list(findings_by_endpoint.keys()),
            findings_per_endpoint={
                ep: len(fs) for ep, fs in findings_by_endpoint.items()
            },
        )

    def _find_matches(self, findings: list[Finding]) -> list[MatchHint]:
        n = len(findings)
        groups: dict[int, set[int]] = {}

        for i in range(n):
            for j in range(i + 1, n):
                matched, reason = _is_match(findings[i], findings[j])
                if not matched:
                    continue
                root_i = self._find_root(groups, i)
                root_j = self._find_root(groups, j)
                if root_i == root_j:
                    groups.setdefault(root_i, {root_i}).add(j)
                    continue
                merged = groups.pop(root_i, {root_i}) | groups.pop(
                    root_j, {root_j},
                )
                new_root = min(merged)
                groups[new_root] = merged

        hints: list[MatchHint] = []
        for _root, members in sorted(groups.items()):
            indices = sorted(members)
            if len(indices) < 2:
                continue
            a = findings[indices[0]]
            b = findings[indices[1]]
            _, reason = _is_match(a, b)
            hints.append(MatchHint(
                finding_indices=indices,
                reason=reason,
            ))
        return hints

    def _find_root(
        self, groups: dict[int, set[int]], idx: int,
    ) -> int:
        for root, members in groups.items():
            if idx in members:
                return root
        return idx
