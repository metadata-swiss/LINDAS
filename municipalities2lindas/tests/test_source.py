import hashlib
import io
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from municipalities2lindas.tests.helpers import make_test_config
from municipalities2lindas.src.source import (
    SourceError,
    check_counts,
    is_stale,
    load_source,
    parse_nomenclature,
    select_member,
)

FIXTURE = Path(__file__).parent / "fixtures" / "ech0071_v1_1_sample.xml"
NS1 = "http://www.ech.ch/xmlns/eCH-0071/1"
NS2 = "http://www.ech.ch/xmlns/eCH-0071/2"


def make_zip(*names: str) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name in names:
            zf.writestr(name, b"<x/>")
    return zipfile.ZipFile(io.BytesIO(buffer.getvalue()))


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.xml = FIXTURE.read_bytes()

    def test_parse_fixture_counts(self):
        n = parse_nomenclature(self.xml, NS1)
        self.assertEqual(n.valid_from, "2026-01-01")
        self.assertEqual(len(n.cantons), 2)
        self.assertEqual(len(n.districts), 4)
        self.assertEqual(len(n.municipalities), 12)

    def test_parse_keeps_raw_text_and_omits_absent(self):
        n = parse_nomenclature(self.xml, NS1)
        record = next(m for m in n.municipalities if m["historyMunicipalityId"] == "11003")
        self.assertNotIn("municipalityAbolitionNumber", record)
        self.assertEqual(record["municipalityId"], "1")

    def test_empty_element_treated_as_missing(self):
        xml = (
            f'<eCH-0071:nomenclature xmlns:eCH-0071="{NS1}"><validFrom>2026-01-01</validFrom>'
            "<cantons/><districts><district><districtHistId>1</districtHistId>"
            "<districtAbolitionDate/></district></districts><municipalities/>"
            "</eCH-0071:nomenclature>"
        ).encode()
        with self.assertLogs("municipalities2lindas.src.source", level="WARNING"):
            n = parse_nomenclature(xml, NS1)
        self.assertNotIn("districtAbolitionDate", n.districts[0])

    def test_parse_rejects_wrong_namespace(self):
        wrong = self.xml.replace(b"eCH-0071/1", b"eCH-0071/2")
        with self.assertRaises(SourceError) as ctx:
            parse_nomenclature(wrong, NS1)
        self.assertIn(NS1, str(ctx.exception))
        self.assertIn(NS2, str(ctx.exception))


class SelectMemberTests(unittest.TestCase):
    A = "x.20260101/1.1  (last update)/eCH0071_260101.xml"
    B = "x.20260101/1.2.0/eCH0071_260101.xml"

    def test_select_member_picks_version_folder(self):
        zf = make_zip(self.A, self.B)
        self.assertEqual(select_member(zf, "1.1"), self.A)
        self.assertEqual(select_member(zf, "1.2.0"), self.B)

    def test_select_member_missing_version_folder(self):
        with self.assertRaises(SourceError) as ctx:
            select_member(make_zip(self.B), "1.1")
        self.assertIn("ECH0071_VERSION", str(ctx.exception))
        self.assertIn("1.2.0", str(ctx.exception))

    def test_select_member_ambiguous(self):
        zf = make_zip(self.A, "y.20250101/1.1/eCH0071_250101.xml")
        with self.assertRaises(SourceError):
            select_member(zf, "1.1")


class LoadSourceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.config = make_test_config()

    def test_load_source_rejects_non_zip(self):
        path = self.dir / "bad.zip"
        path.write_bytes(b"<html>error</html>")
        with self.assertRaises(SourceError):
            load_source(path, self.config)

    def test_load_source_info(self):
        path = self.dir / "src.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("x.20260101/1.1  (last update)/eCH0071_260101.xml", FIXTURE.read_bytes())
        nomenclature, info = load_source(path, self.config, url="u", last_modified="lm")
        self.assertEqual(info.sha256, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(info.size, path.stat().st_size)
        self.assertEqual(info.valid_from, "2026-01-01")
        self.assertEqual(info.last_modified, "lm")
        self.assertEqual(info.to_json()["member"], info.member)
        self.assertEqual(len(nomenclature.municipalities), 12)

    def test_load_source_accepts_xml(self):
        nomenclature, info = load_source(FIXTURE, self.config)
        self.assertEqual(info.member, FIXTURE.name)
        self.assertEqual(len(nomenclature.cantons), 2)


class CountsAndStalenessTests(unittest.TestCase):
    def test_check_counts_fixture_fails_real_minimums(self):
        n = parse_nomenclature(FIXTURE.read_bytes(), NS1)
        with self.assertRaises(SourceError) as ctx:
            check_counts(n)
        self.assertIn("cantons", str(ctx.exception))
        check_counts(n, minimums={"cantons": 2, "districts": 4, "municipalities": 12})

    def test_is_stale(self):
        self.assertTrue(is_stale("2026-01-01", date(2027, 2, 2)))
        self.assertFalse(is_stale("2026-01-01", date(2027, 1, 31)))

    def test_is_stale_tolerates_timezone_suffix(self):
        self.assertTrue(is_stale("2026-01-01+01:00", date(2027, 2, 2)))
        self.assertFalse(is_stale("2026-01-01Z", date(2027, 1, 31)))


if __name__ == "__main__":
    unittest.main()
