"""Sorted N-Triples output and lexical-form-preserving input."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Set

import rdflib
from rdflib import Graph, Literal

from .mapper import Triple


def term(value) -> str:
    if not isinstance(value, Literal):
        return value.n3()
    lexical = (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    text = f'"{lexical}"'
    if value.language:
        return f"{text}@{value.language}"
    if value.datatype:
        return f"{text}^^<{value.datatype}>"
    return text


def write_ntriples(triples: Iterable[Triple], path: Path) -> int:
    lines = sorted(f"{term(s)} {term(p)} {term(o)} .\n" for s, p, o in triples)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.writelines(lines)
    return len(lines)


def parse_ntriples(text: str) -> Set[Triple]:
    # rdflib has no per-call switch; this global is not thread-safe.
    previous = rdflib.NORMALIZE_LITERALS
    rdflib.NORMALIZE_LITERALS = False
    try:
        graph = Graph()
        graph.parse(data=text, format="nt")
        return set(graph)
    finally:
        rdflib.NORMALIZE_LITERALS = previous


def read_ntriples(path: Path) -> Set[Triple]:
    return parse_ntriples(Path(path).read_text(encoding="utf-8"))
