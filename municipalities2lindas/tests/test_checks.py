import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from municipalities2lindas.src.checks import (
    SHAPES_DIR,
    Violation,
    load_known_violations,
    stale_known_violations,
    unexpected_violations,
    validate_triples,
)
from municipalities2lindas.tests.helpers import make_test_config
from municipalities2lindas.src.main import main
from municipalities2lindas.src.mapper import build_graph
from municipalities2lindas.src.source import load_source

FIXTURE = Path(__file__).parent / "fixtures" / "ech0071_v1_1_sample.xml"
NAME = "http://schema.org/name"
MAX_COUNT = "MaxCountConstraintComponent"


class ChecksTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.shapes = self.tmp / "shapes"
        self.shapes.mkdir()
        (self.shapes / "Smoke.ttl").write_bytes((SHAPES_DIR / "Smoke.ttl").read_bytes())
        config = make_test_config()
        nomenclature, _ = load_source(FIXTURE, config)
        self.triples = build_graph(nomenclature, config)

    def test_smoke_shape_flags_duplicate_names(self):
        violations, _ = validate_triples(self.triples, self.shapes)
        self.assertEqual(
            violations,
            [Violation("Smoke.ttl", "https://ld.admin.ch/municipality/5", NAME, MAX_COUNT)],
        )

    def test_known_violation_is_filtered(self):
        known_file = self.tmp / "known.json"
        known_file.write_text(json.dumps([{
            "shape_file": "Smoke.ttl", "focus_node": "https://ld.admin.ch/municipality/5",
            "path": NAME, "component": MAX_COUNT, "reason": "test",
        }]), encoding="utf-8")
        violations, _ = validate_triples(self.triples, self.shapes)
        known = load_known_violations(known_file)
        self.assertEqual(unexpected_violations(violations, known), [])

    def test_known_entry_without_match_is_stale(self):
        entry = Violation("Smoke.ttl", "https://ld.admin.ch/municipality/9", NAME, MAX_COUNT)
        violations, _ = validate_triples(self.triples, self.shapes)
        self.assertEqual(stale_known_violations(violations, {entry}), [entry])
        self.assertEqual(stale_known_violations(violations, set(violations)), [])

    def test_missing_known_file_means_empty_set(self):
        self.assertEqual(load_known_violations(self.tmp / "absent.json"), set())

    def test_empty_shapes_dir_is_rejected(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        with self.assertRaises(ValueError):
            validate_triples(self.triples, empty)

    def test_shapes_dir_contents_are_tracked(self):
        self.assertEqual(
            sorted(p.name for p in SHAPES_DIR.iterdir()),
            ["Smoke.ttl", "Specialized.ttl", "VersionLink.ttl",
             "identities.ttl", "known_violations.json", "versions.ttl"],
        )

    def test_build_fails_on_unexpected_violation(self):
        out = self.tmp / "m.nt"
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main([
                "build", "--source-file", str(FIXTURE), "--output", str(out),
                "--source-info", str(self.tmp / "i.json"), "--skip-count-check",
                "--shapes-dir", str(self.shapes),
                "--shacl-report", str(self.tmp / "report.ttl"),
            ])
        self.assertEqual(code, 1)
        self.assertIn("municipality/5", buffer.getvalue())
        self.assertFalse(out.exists())
        self.assertTrue((self.tmp / "report.ttl").exists())

    def test_build_passes_with_known_violation_as_notice(self):
        (self.shapes / "known_violations.json").write_text(json.dumps([{
            "shape_file": "Smoke.ttl", "focus_node": "https://ld.admin.ch/municipality/5",
            "path": NAME, "component": MAX_COUNT, "reason": "test",
        }]), encoding="utf-8")
        out = self.tmp / "m.nt"
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main([
                "build", "--source-file", str(FIXTURE), "--output", str(out),
                "--source-info", str(self.tmp / "i.json"), "--skip-count-check",
                "--shapes-dir", str(self.shapes),
                "--shacl-report", str(self.tmp / "report.ttl"),
            ])
        self.assertEqual(code, 0)
        self.assertIn("::notice::", buffer.getvalue())
        self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
