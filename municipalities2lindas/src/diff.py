"""Compare the generated graph with the live LINDAS graph and decide what to do."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Literal as LiteralType, Optional

from rdflib import Literal
from rdflib.namespace import XSD

from .mapper import Triple
from .serializer import term


@dataclass(frozen=True)
class GraphDiff:
    added: frozenset
    removed: frozenset
    generated_count: int
    live_count: int

    @property
    def removed_ratio(self) -> float:
        if self.live_count == 0:
            return 0.0
        return len(self.removed) / self.live_count

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed)


def _canonical(triple: Triple) -> Triple:
    """Treat an explicit xsd:string datatype as equal to a plain literal (RDF 1.1)."""
    s, p, o = triple
    if isinstance(o, Literal) and o.datatype == XSD.string:
        o = Literal(str(o), lang=None, datatype=None, normalize=False)
    return (s, p, o)


def diff_graphs(generated: set[Triple], live: set[Triple]) -> GraphDiff:
    generated_keys = {_canonical(t) for t in generated}
    live_keys = {_canonical(t) for t in live}
    return GraphDiff(
        added=frozenset(t for t in generated if _canonical(t) not in live_keys),
        removed=frozenset(t for t in live if _canonical(t) not in generated_keys),
        generated_count=len(generated),
        live_count=len(live),
    )


@dataclass(frozen=True)
class Decision:
    action: LiteralType["skip", "upload", "abort"]
    reason: str


def decide(diff: GraphDiff, max_removed_ratio: float, allow_large_change: bool) -> Decision:
    if not diff.has_changes:
        return Decision("skip", "Generated graph is identical to the live graph")
    if diff.live_count == 0:
        return Decision("upload", "Live graph is empty; initial import")
    if diff.removed_ratio > max_removed_ratio and not allow_large_change:
        return Decision(
            "abort",
            f"{diff.removed_ratio * 100:.1f}% of live triples would be removed "
            f"(limit {max_removed_ratio * 100:.1f}%); "
            "set ALLOW_LARGE_CHANGE=true to proceed",
        )
    return Decision(
        "upload", f"{len(diff.added)} added, {len(diff.removed)} removed"
    )


def _by_predicate(triples: Iterable[Triple]) -> dict:
    counts = Counter(str(p) for _, p, _ in triples)
    return dict(sorted(counts.items()))


def _examples(triples: Iterable[Triple], limit: int) -> list:
    lines = sorted(f"{term(s)} {term(p)} {term(o)} ." for s, p, o in triples)
    return lines[:limit]


def summarize(
    diff: GraphDiff, decision: Decision, source_info: Optional[dict], examples: int = 50
) -> dict:
    return {
        "action": decision.action,
        "reason": decision.reason,
        "generated_count": diff.generated_count,
        "live_count": diff.live_count,
        "added_count": len(diff.added),
        "removed_count": len(diff.removed),
        "removed_ratio": diff.removed_ratio,
        "added_by_predicate": _by_predicate(diff.added),
        "removed_by_predicate": _by_predicate(diff.removed),
        "added_examples": _examples(diff.added, examples),
        "removed_examples": _examples(diff.removed, examples),
        "source": source_info,
    }


def render_markdown(summary: dict) -> str:
    lines = ["## Municipalities diff", ""]
    source = summary.get("source")
    if source:
        lines.append(f"- Source validFrom: `{source.get('valid_from')}`")
        lines.append(f"- Source sha256: `{source.get('sha256')}`")
        if source.get("last_modified"):
            lines.append(f"- Source last modified: `{source['last_modified']}`")
    lines += [
        f"- Generated triples: {summary['generated_count']}",
        f"- Live triples: {summary['live_count']}",
        f"- Added: {summary['added_count']}",
        f"- Removed: {summary['removed_count']} ({summary['removed_ratio'] * 100:.1f}% of live)",
        f"- Decision: **{summary['action']}** - {summary['reason']}",
        "",
    ]
    added, removed = summary["added_by_predicate"], summary["removed_by_predicate"]
    if added or removed:
        lines += ["| Predicate | Added | Removed |", "| --- | ---: | ---: |"]
        for predicate in sorted(set(added) | set(removed)):
            lines.append(f"| `{predicate}` | {added.get(predicate, 0)} | {removed.get(predicate, 0)} |")
        lines.append("")
    return "\n".join(lines)
