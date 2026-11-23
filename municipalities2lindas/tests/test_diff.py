import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from municipalities2lindas.src.diff import decide, diff_graphs, render_markdown, summarize
from municipalities2lindas.src.lindas import LindasClient
from municipalities2lindas.src.main import main
from municipalities2lindas.src.mapper import lit_str
from municipalities2lindas.src.serializer import read_ntriples

FIXTURE_NT = Path(__file__).parent / "fixtures" / "ech0071_v1_1_sample_expected.nt"
P = URIRef("https://example.org/p")


def _triples(prefix, count):
    return {(URIRef(f"https://example.org/{prefix}{i}"), P, lit_str(str(i))) for i in range(count)}


class DiffTest(unittest.TestCase):
    def test_identical_graphs_skip(self):
        graph = _triples("s", 10)
        diff = diff_graphs(graph, set(graph))
        self.assertFalse(diff.has_changes)
        self.assertEqual(decide(diff, 0.05, False).action, "skip")

    def test_explicit_xsd_string_equals_plain_literal(self):
        subject = URIRef("https://example.org/s")
        generated = {(subject, P, Literal("x"))}
        live = {(subject, P, Literal("x", datatype=XSD.string))}
        self.assertFalse(diff_graphs(generated, live).has_changes)

    def test_small_change_uploads(self):
        live = _triples("s", 100)
        generated = (live - set(sorted(live)[:3])) | _triples("n", 5)
        diff = diff_graphs(generated, live)
        self.assertEqual((len(diff.removed), len(diff.added)), (3, 5))
        self.assertEqual(decide(diff, 0.05, False).action, "upload")

    def _large_removal(self):
        live = _triples("s", 100)
        return diff_graphs(live - set(sorted(live)[:6]), live)

    def test_large_removal_aborts(self):
        decision = decide(self._large_removal(), 0.05, False)
        self.assertEqual(decision.action, "abort")
        self.assertIn("6.0%", decision.reason)
        self.assertIn("ALLOW_LARGE_CHANGE", decision.reason)

    def test_large_removal_allowed(self):
        self.assertEqual(decide(self._large_removal(), 0.05, True).action, "upload")

    def test_ratio_equal_to_threshold_uploads(self):
        live = _triples("s", 100)
        diff = diff_graphs(live - set(sorted(live)[:5]), live)
        self.assertEqual(decide(diff, 0.05, False).action, "upload")

    def test_decide_uploads_when_live_graph_empty(self):
        diff = diff_graphs(_triples("s", 10), set())
        self.assertEqual(diff.removed_ratio, 0.0)
        self.assertEqual(decide(diff, 0.05, False).action, "upload")

    def test_summary_groups_by_predicate_and_limits_examples(self):
        diff = diff_graphs(_triples("n", 60), set())
        summary = summarize(diff, decide(diff, 0.05, False), None)
        self.assertEqual(summary["added_by_predicate"], {str(P): 60})
        self.assertEqual(len(summary["added_examples"]), 50)
        self.assertEqual(summary["added_examples"], sorted(summary["added_examples"]))
        self.assertIsNone(summary["source"])


class DiffCliTest(unittest.TestCase):
    def test_diff_cli_writes_report_and_output(self):
        generated = read_ntriples(FIXTURE_NT)
        live = set(sorted(generated)[1:])
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            report = tmp / "report.json"
            env = {
                "GITHUB_OUTPUT": str(tmp / "out.txt"),
                "GITHUB_STEP_SUMMARY": str(tmp / "summary.md"),
            }
            with mock.patch.dict(os.environ, env), mock.patch.object(
                LindasClient, "fetch_graph", return_value=live
            ), contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    ["diff", "--input", str(FIXTURE_NT), "--source-info",
                     str(tmp / "missing.json"), "--report", str(report)]
                )
            self.assertEqual(code, 0)
            self.assertIn("action=upload", (tmp / "out.txt").read_text())
            self.assertEqual(json.loads(report.read_text())["added_count"], 1)
            self.assertIn("upload", (tmp / "summary.md").read_text())

    def test_diff_cli_abort_path(self):
        generated = read_ntriples(FIXTURE_NT)
        live = generated | _triples("extra", len(generated) * 3)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            report = tmp / "report.json"
            env = {
                "GITHUB_OUTPUT": str(tmp / "out.txt"),
                "GITHUB_STEP_SUMMARY": str(tmp / "summary.md"),
            }
            with mock.patch.dict(os.environ, env), mock.patch.object(
                LindasClient, "fetch_graph", return_value=live
            ), contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    ["diff", "--input", str(FIXTURE_NT), "--source-info",
                     str(tmp / "missing.json"), "--report", str(report)]
                )
            self.assertEqual(code, 1)
            self.assertIn("action=abort", (tmp / "out.txt").read_text())
            self.assertEqual(json.loads(report.read_text())["action"], "abort")

    def test_markdown_shows_source_last_modified(self):
        diff = diff_graphs(_triples("n", 1), set())
        source = {"valid_from": "2026-01-01", "sha256": "ab", "last_modified": "Mon, 01 Jan 2026"}
        text = render_markdown(summarize(diff, decide(diff, 0.05, False), source))
        self.assertIn("Mon, 01 Jan 2026", text)


if __name__ == "__main__":
    unittest.main()
