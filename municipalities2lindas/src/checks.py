"""SHACL validation of the generated triples against the legacy shapes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

import rdflib
from pyshacl import validate
from rdflib import Graph, URIRef
from rdflib.namespace import SH

from .mapper import Triple

SHAPES_DIR = Path(__file__).resolve().parent.parent / "shapes"


@dataclass(frozen=True)
class Violation:
    shape_file: str
    focus_node: str
    path: Optional[str]
    component: str


def _local_name(iri: str) -> str:
    return iri.rsplit("#", 1)[-1]


def validate_triples(
    triples: Set[Triple], shapes_dir: Path = SHAPES_DIR
) -> Tuple[List[Violation], Graph]:
    shape_paths = sorted(Path(shapes_dir).glob("*.ttl"))
    if not shape_paths:
        raise ValueError(f"no SHACL shape files (*.ttl) found in {shapes_dir}")
    data = Graph()
    for triple in triples:
        data.add(triple)
    violations: List[Violation] = []
    merged = Graph()
    for shape_path in shape_paths:
        shapes = Graph().parse(str(shape_path), format="turtle")
        _, report, _ = validate(
            data, shacl_graph=shapes, inference="none", advanced=True, do_owl_imports=False
        )
        merged += report
        for result in report.subjects(rdflib.RDF.type, SH.ValidationResult):
            path = report.value(result, SH.resultPath)
            violations.append(
                Violation(
                    shape_file=shape_path.name,
                    focus_node=str(report.value(result, SH.focusNode)),
                    path=str(path) if isinstance(path, URIRef) else None,
                    component=_local_name(str(report.value(result, SH.sourceConstraintComponent))),
                )
            )
    violations.sort(key=lambda v: (v.shape_file, v.focus_node, v.path or "", v.component))
    return violations, merged


def load_known_violations(path: Path) -> Set[Violation]:
    if not Path(path).exists():
        return set()
    entries = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        Violation(e["shape_file"], e["focus_node"], e.get("path"), e["component"])
        for e in entries
    }


def unexpected_violations(found: List[Violation], known: Set[Violation]) -> List[Violation]:
    return [violation for violation in found if violation not in known]


def stale_known_violations(found: List[Violation], known: Set[Violation]) -> List[Violation]:
    """Known entries that no longer occur and should be removed from the file."""
    return sorted(known - set(found), key=lambda v: (v.shape_file, v.focus_node, v.path or "", v.component))
