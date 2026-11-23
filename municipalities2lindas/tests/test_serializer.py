import contextlib
import dataclasses
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import rdflib
from rdflib import URIRef

from municipalities2lindas.tests.helpers import make_test_config
from municipalities2lindas.src.main import main
from municipalities2lindas.src.mapper import build_graph, lit_int, lit_str
from municipalities2lindas.src.serializer import read_ntriples, write_ntriples
from municipalities2lindas.src.source import load_source

FIXTURE = Path(__file__).parent / "fixtures" / "ech0071_v1_1_sample.xml"
S = URIRef("https://example.org/s")
P = URIRef("https://example.org/p")


class SerializerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_round_trip_preserves_lexical_forms(self):
        triples = {(S, P, lit_int("01"))}
        path = self.tmp / "out.nt"
        self.assertEqual(write_ntriples(triples, path), 1)
        back = read_ntriples(path)
        self.assertEqual(back, triples)
        self.assertEqual(str(next(iter(back))[2]), "01")

    def test_output_sorted_and_utf8(self):
        triples = {(S, P, lit_str("Zürich")), (S, P, lit_str("Aarau"))}
        path = self.tmp / "out.nt"
        write_ntriples(triples, path)
        text = path.read_bytes().decode("utf-8")
        self.assertIn("Zürich", text)
        self.assertNotIn("\\u", text)
        lines = text.splitlines()
        self.assertEqual(lines, sorted(lines))

    def test_special_characters_stay_on_one_line(self):
        triples = {(S, P, lit_str('a\nb "q" back\\slash\r'))}
        path = self.tmp / "out.nt"
        write_ntriples(triples, path)
        self.assertEqual(len(path.read_bytes().splitlines()), 1)
        self.assertEqual(read_ntriples(path), triples)

    def test_normalize_literals_restored_after_parse_error(self):
        path = self.tmp / "bad.nt"
        path.write_text("not n-triples\n", encoding="utf-8")
        before = rdflib.NORMALIZE_LITERALS
        with self.assertRaises(Exception):
            read_ntriples(path)
        self.assertEqual(rdflib.NORMALIZE_LITERALS, before)

    def test_build_cli_on_fixture(self):
        out = self.tmp / "m.nt"
        info = self.tmp / "info.json"
        trivial_shapes = self.tmp / "trivial_shapes"
        trivial_shapes.mkdir()
        (trivial_shapes / "Absent.ttl").write_text(
            "PREFIX sh: <http://www.w3.org/ns/shacl#>\n"
            "[] sh:targetNode <https://example.org/absent> ; sh:property [ sh:path <https://example.org/p> ; sh:maxCount 0 ] .\n",
            encoding="utf-8",
        )
        code = main([
            "build", "--source-file", str(FIXTURE), "--output", str(out),
            "--source-info", str(info), "--skip-count-check",
            "--shapes-dir", str(trivial_shapes), "--shacl-report", str(self.tmp / "r.ttl"),
        ])
        self.assertEqual(code, 0)
        nomenclature, _ = load_source(FIXTURE, make_test_config())
        self.assertEqual(read_ntriples(out), build_graph(nomenclature, make_test_config()))
        self.assertEqual(json.loads(info.read_text(encoding="utf-8"))["valid_from"], "2026-01-01")

    def test_build_cli_tolerates_unparseable_valid_from(self):
        out = self.tmp / "m.nt"
        trivial_shapes = self.tmp / "shapes"
        trivial_shapes.mkdir()
        (trivial_shapes / "Absent.ttl").write_text(
            "PREFIX sh: <http://www.w3.org/ns/shacl#>\n"
            "[] sh:targetNode <https://example.org/absent> ; sh:property [ sh:path <https://example.org/p> ; sh:maxCount 0 ] .\n",
            encoding="utf-8",
        )
        with mock.patch("municipalities2lindas.src.main.is_stale", side_effect=ValueError("bad")):
            code = main([
                "build", "--source-file", str(FIXTURE), "--output", str(out),
                "--source-info", str(self.tmp / "i.json"), "--skip-count-check",
                "--shapes-dir", str(trivial_shapes), "--shacl-report", str(self.tmp / "r.ttl"),
            ])
        self.assertEqual(code, 0)

    def test_build_cli_reports_record_missing_field(self):
        nomenclature, _ = load_source(FIXTURE, make_test_config())
        broken = dataclasses.replace(
            nomenclature,
            cantons=[{k: v for k, v in c.items() if k != "cantonId"} for c in nomenclature.cantons],
        )
        buffer = io.StringIO()
        with mock.patch("municipalities2lindas.src.main.load_source", return_value=(broken, None)), \
                contextlib.redirect_stdout(buffer):
            code = main([
                "build", "--source-file", str(FIXTURE), "--output", str(self.tmp / "m.nt"),
                "--skip-count-check",
            ])
        self.assertEqual(code, 1)
        self.assertIn("cantonId", buffer.getvalue())

    def test_build_cli_reports_source_error(self):
        bad = self.tmp / "bad.zip"
        bad.write_bytes(b"<html>nope</html>")
        code = main(["build", "--source-file", str(bad), "--output", str(self.tmp / "o.nt"),
                     "--source-info", str(self.tmp / "i.json")])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
