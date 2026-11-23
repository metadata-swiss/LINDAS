"""Command line entry point for the municipalities pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .checks import (
    SHAPES_DIR,
    load_known_violations,
    stale_known_violations,
    unexpected_violations,
    validate_triples,
)
from .config import MunicipalitiesConfig
from .diff import decide, diff_graphs, render_markdown, summarize
from .lindas import LindasClient
from .mapper import build_graph
from .serializer import read_ntriples, write_ntriples
from .source import SourceError, check_counts, download_zip, is_stale, load_source


def _build(args: argparse.Namespace) -> int:
    config = MunicipalitiesConfig.from_env()
    try:
        if args.source_file:
            path, url, last_modified = Path(args.source_file), str(args.source_file), None
        else:
            download_dir = Path(args.download_dir)
            download_dir.mkdir(parents=True, exist_ok=True)
            path, last_modified = download_zip(config, download_dir / "source.zip")
            url = config.source_url
        nomenclature, info = load_source(path, config, url=url, last_modified=last_modified)
        if not args.skip_count_check:
            check_counts(nomenclature)
    except SourceError as error:
        print(f"ERROR: {error}")
        return 1

    try:
        triples = build_graph(nomenclature, config)
    except KeyError as error:
        print(f"ERROR: source record is missing required field {error}")
        return 1
    shapes_dir = Path(args.shapes_dir)
    violations, report = validate_triples(triples, shapes_dir)
    report.serialize(destination=args.shacl_report, format="turtle")
    known = load_known_violations(shapes_dir / "known_violations.json")
    unexpected = unexpected_violations(violations, known)
    for violation in violations:
        if violation in known:
            print(f"::notice::known SHACL violation {violation}")
    for violation in stale_known_violations(violations, known):
        print(f"::warning::stale known SHACL violation, remove from known_violations.json: {violation}")
    if unexpected:
        for violation in unexpected:
            print(f"ERROR: unexpected SHACL violation {violation}")
        return 1

    count = write_ntriples(triples, Path(args.output))
    Path(args.source_info).write_text(
        json.dumps(info.to_json(), indent=2), encoding="utf-8"
    )
    print(f"valid_from={info.valid_from} triples={count} sha256={info.sha256}")
    today = datetime.now(timezone.utc).date()
    try:
        stale = is_stale(info.valid_from, today)
    except ValueError:
        print(f"::warning::cannot parse eCH-0071 validFrom {info.valid_from!r}; skipping stale check")
    else:
        if stale:
            print(f"::warning::eCH-0071 source validFrom {info.valid_from} is older than 13 months")
    return 0


def _append(env_name: str, text: str) -> bool:
    path = os.environ.get(env_name)
    if not path:
        return False
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)
    return True


def _diff(args: argparse.Namespace) -> int:
    config = MunicipalitiesConfig.from_env()
    generated = read_ntriples(Path(args.input))
    live = LindasClient(config).fetch_graph()
    source_path = Path(args.source_info)
    source = (
        json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else None
    )
    diff = diff_graphs(generated, live)
    decision = decide(diff, config.max_removed_ratio, config.allow_large_change)
    summary = summarize(diff, decision, source)
    Path(args.report).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    markdown = render_markdown(summary)
    if not _append("GITHUB_STEP_SUMMARY", markdown + "\n"):
        print(markdown)
    _append("GITHUB_OUTPUT", f"action={decision.action}\n")
    print(f"action={decision.action}: {decision.reason}")
    return 1 if decision.action == "abort" else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="municipalities2lindas")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Generate sorted N-Triples from the eCH-0071 source")
    build.add_argument("--source-file")
    build.add_argument("--download-dir", default=".")
    build.add_argument("--output", default="municipalities.nt")
    build.add_argument("--source-info", default="source_info.json")
    build.add_argument("--shacl-report", default="shacl_report.ttl")
    build.add_argument("--shapes-dir", default=str(SHAPES_DIR))
    build.add_argument("--skip-count-check", action="store_true")
    build.set_defaults(func=_build)
    diff = sub.add_parser("diff", help="Compare generated N-Triples with the live LINDAS graph")
    diff.add_argument("--input", default="municipalities.nt")
    diff.add_argument("--source-info", default="source_info.json")
    diff.add_argument("--report", default="municipalities_diff.json")
    diff.set_defaults(func=_diff)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
