import unittest
from pathlib import Path

import rdflib
from rdflib import XSD, Literal, URIRef
from rdflib.namespace import RDF

from municipalities2lindas.tests.helpers import make_test_config
from municipalities2lindas.src.mapper import (
    CHE,
    ECH,
    CH,
    GEO,
    GN,
    PROV,
    REG,
    SCHEMA,
    VL,
    Nomenclature,
    build_graph,
    event_triples,
    identity_triples,
    inferred_triples,
    lit_date,
    lit_int,
    lit_str,
    register_and_version_triples,
)
from municipalities2lindas.src.source import parse_nomenclature

FIXTURE = Path(__file__).parent / "fixtures" / "ech0071_v1_1_sample.xml"
LD = "https://ld.admin.ch/"
AGVCH = "https://register.ld.admin.ch/agvch/"


def t(s, p, o):
    return (URIRef(s), URIRef(p), o if isinstance(o, Literal) else URIRef(o))


class RegisterAndVersionTriplesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = make_test_config()
        n = parse_nomenclature(FIXTURE.read_bytes(), config.expected_namespace)
        cls.triples = register_and_version_triples(n, config)

    def objects(self, s, p):
        return {o for (s2, p2, o) in self.triples if s2 == URIRef(s) and p2 == URIRef(p)}

    def test_canton_identity(self):
        canton = LD + "canton/1"
        types = self.objects(canton, str(RDF.type))
        self.assertEqual(
            types,
            {
                URIRef("https://schema.ld.admin.ch/Canton"),
                URIRef("http://schema.org/AdministrativeArea"),
                URIRef("http://schema.org/State"),
                URIRef("http://schema.org/DefinedTerm"),
                URIRef("https://version.link/Identity"),
            },
        )
        self.assertIn(
            t(
                canton,
                "http://www.opengis.net/ont/geosparql#hasGeometry",
                "https://geo.ld.admin.ch/boundaries/canton/geometry-g1/1:2023",
            ),
            self.triples,
        )
        self.assertIn(
            t(canton, "http://schema.org/validFrom", Literal("1960-01-01", datatype=XSD.date, normalize=False)),
            self.triples,
        )
        self.assertEqual(
            self.objects(canton, "http://www.w3.org/ns/prov#hadPrimarySource"),
            {
                URIRef("https://geo.ld.admin.ch/boundaries/canton/1"),
                URIRef(AGVCH + "canton/1"),
            },
        )
        self.assertIn(
            t(canton, "http://www.w3.org/2004/02/skos/core#hiddenLabel", lit_str("Zürich")),
            self.triples,
        )
        self.assertEqual(self.objects(canton, "http://schema.org/name"), set())
        self.assertIn(t(str(CHE), "http://schema.org/containsPlace", canton), self.triples)

    def test_district_version(self):
        v = LD + "district/version/10104"
        self.assertEqual(self.objects(v, "http://schema.org/isPartOf"), {URIRef(LD + "canton/2")})
        self.assertEqual(
            self.objects(v, "http://schema.org/containedInPlace"), {URIRef(LD + "canton/2")}
        )
        self.assertEqual(self.objects(v, "https://version.link/identity"), {URIRef(LD + "district/201")})
        self.assertEqual(self.objects(v, "https://version.link/identityIdentifier"), {lit_int("201")})
        self.assertEqual(self.objects(v, "http://schema.org/validThrough"), set())

    def test_municipality_version_points_to_district_version(self):
        self.assertEqual(
            self.objects(LD + "municipality/version/11006", "http://schema.org/isPartOf"),
            {URIRef(LD + "district/version/10104")},
        )

    def test_register_district_multi_entry_mode(self):
        p = str(ECH.districtEntryModeId)
        self.assertEqual(self.objects(AGVCH + "district/101", p), {lit_int("15")})
        self.assertEqual(self.objects(AGVCH + "district/201", p), {lit_int("16")})

    def test_register_municipality_version_fields(self):
        v = AGVCH + "municipalityversion/11005"
        self.assertEqual(
            self.objects(v, str(ECH.municipalityAbolitionModeId)), {lit_int("24")}
        )
        self.assertEqual(self.objects(v, str(ECH.cantonAbbreviation)), {lit_str("ZH")})
        self.assertEqual(
            self.objects(v, str(ECH.municipality)), {URIRef(AGVCH + "municipality/3")}
        )
        preds = {p for (s, p, o) in self.triples if s == URIRef(v)}
        self.assertFalse([p for p in preds if str(p).startswith(str(ECH) + "districtEntryMode")])

    def test_b1_district_event_on_municipality_iri(self):
        e = LD + "municipality/changeevent/157"
        self.assertEqual(
            self.objects(e, str(RDF.type)),
            {ECH.DistrictChangeEvent, ECH.MunicipalityChangeEvent},
        )
        self.assertIn(lit_int("157"), self.objects(e, str(ECH.districtAdmissionNumber)))
        self.assertIn(lit_int("157"), self.objects(e, str(ECH.municipalityAdmissionNumber)))
        self.assertFalse(
            [s for (s, p, o) in self.triples if str(s).startswith(LD + "district/changeevent/")]
        )

    def test_literals_not_normalised(self):
        config = make_test_config()
        n = Nomenclature(
            valid_from="2026-01-01",
            cantons=[{"cantonId": "01", "cantonAbbreviation": "ZH"}],
            districts=[],
            municipalities=[],
        )
        triples = register_and_version_triples(n, config)
        ids = {o for (s, p, o) in triples if p == SCHEMA.identifier}
        self.assertIn(lit_int("01"), ids)
        self.assertEqual({str(o) for o in ids}, {"01"})


class IdentityTriplesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = make_test_config()
        n = parse_nomenclature(FIXTURE.read_bytes(), config.expected_namespace)
        cls.triples = identity_triples(n, config)

    def objects(self, s, p):
        return {o for (s2, p2, o) in self.triples if s2 == URIRef(s) and p2 == URIRef(p)}

    def uris(self, *values):
        return {URIRef(v) for v in values}

    def test_current_municipality_identity(self):
        s = LD + "municipality/1"
        self.assertEqual(
            self.objects(s, RDF.type),
            {VL.Identity, CH.PoliticalMunicipality, SCHEMA.DefinedTerm},
        )
        self.assertEqual(self.objects(s, VL.version), self.uris(LD + "municipality/version/11003"))
        self.assertEqual(self.objects(s, SCHEMA.name), {lit_str("Aach-Bbach")})
        self.assertEqual(self.objects(s, SCHEMA.identifier), {lit_int("1")})
        self.assertEqual(self.objects(s, SCHEMA.isPartOf), self.uris(LD + "district/101"))
        self.assertEqual(
            self.objects(s, GEO.hasGeometry),
            self.uris("https://geo.ld.admin.ch/boundaries/municipality/geometry-g1/1:2026"),
        )
        self.assertEqual(
            self.objects(s, PROV.hadPrimarySource),
            self.uris(
                AGVCH + "municipalityversion/11003",
                "https://geo.ld.admin.ch/boundaries/municipality/1",
            ),
        )
        self.assertEqual(self.objects(s, GN.featureCode), {GN["A.ADM3"]})
        self.assertEqual(
            self.objects(s, SCHEMA.inDefinedTermSet), self.uris(LD + "dimension/municipality")
        )
        self.assertEqual(
            self.objects(s, VL.inVersionedIdentitySet), self.uris(LD + "fso/register")
        )

    def test_entry_mode_types(self):
        s3 = LD + "municipality/3"
        self.assertIn(CH.MunicipalityFreeArea, self.objects(s3, RDF.type))
        self.assertEqual(self.objects(s3, SCHEMA.isPartOf), self.uris(LD + "district/201"))
        self.assertIn(CH.CantonalLakePortion, self.objects(LD + "municipality/4", RDF.type))

    def test_deprecated_municipality(self):
        s = LD + "municipality/4"
        self.assertIn(VL.Deprecated, self.objects(s, RDF.type))
        self.assertEqual(self.objects(s, VL.version), self.uris(LD + "municipality/version/11007"))
        self.assertEqual(self.objects(s, SCHEMA.isPartOf), self.uris(LD + "district/102"))
        self.assertNotIn(SCHEMA.DefinedTerm, self.objects(s, RDF.type))
        for p in (GN.featureCode, SCHEMA.inDefinedTermSet, GEO.hasGeometry):
            self.assertEqual(self.objects(s, p), set())

    def test_b4_tie_gives_two_versions(self):
        s = LD + "municipality/5"
        self.assertEqual(
            self.objects(s, VL.version),
            self.uris(LD + "municipality/version/11008", LD + "municipality/version/11009"),
        )
        self.assertEqual(self.objects(s, SCHEMA.name), {lit_str("Edorf"), lit_str("Edorf-Neu")})

    def test_b3_non29_abolished_has_no_identity(self):
        subjects = {s for (s, _, _) in self.triples}
        self.assertNotIn(URIRef(LD + "municipality/2"), subjects)
        self.assertNotIn(URIRef(LD + "municipality/6"), subjects)

    def test_current_district_identity(self):
        s = LD + "district/201"
        self.assertEqual(
            self.objects(s, RDF.type), {VL.Identity, CH.District, SCHEMA.DefinedTerm}
        )
        self.assertEqual(self.objects(s, VL.version), self.uris(LD + "district/version/10104"))
        self.assertEqual(self.objects(s, SCHEMA.name), {lit_str("Gamma")})
        self.assertEqual(self.objects(s, SCHEMA.isPartOf), self.uris(LD + "canton/2"))
        self.assertEqual(
            self.objects(s, SCHEMA.inDefinedTermSet), self.uris(LD + "dimension/district")
        )
        self.assertEqual(
            self.objects(s, PROV.hadPrimarySource), self.uris(AGVCH + "districtversion/10104")
        )

    def test_b2_district_current_and_deprecated(self):
        s = LD + "district/101"
        self.assertIn(VL.Deprecated, self.objects(s, RDF.type))
        self.assertEqual(
            self.objects(s, VL.version),
            self.uris(LD + "district/version/10100", LD + "district/version/10101"),
        )
        self.assertEqual(self.objects(s, SCHEMA.name), {lit_str("Alt-Alpha"), lit_str("Alpha")})

    def test_deprecated_district_without_current(self):
        s = LD + "district/102"
        self.assertIn(VL.Deprecated, self.objects(s, RDF.type))
        self.assertEqual(self.objects(s, VL.version), self.uris(LD + "district/version/10102"))


class IdentityEdgeCasesTest(unittest.TestCase):
    DISTRICT = {"districtHistId": "1", "districtId": "10", "cantonId": "1"}

    def identity(self, *municipalities, mid="7"):
        n = Nomenclature("2026-01-01", [], [self.DISTRICT], list(municipalities))
        triples = identity_triples(n, make_test_config())
        return {(p, o) for (s, p, o) in triples if s == URIRef(LD + "municipality/" + mid)}

    @staticmethod
    def muni(hist, **over):
        rec = {
            "historyMunicipalityId": hist,
            "municipalityId": "7",
            "districtHistId": "1",
            "municipalityShortName": "X",
            "municipalityEntryMode": "11",
            "municipalityAdmissionDate": "2000-01-01",
        }
        rec.update(over)
        return rec

    def test_abolished_with_current_version_is_not_deprecated(self):
        old = self.muni(
            "1",
            municipalityAbolitionNumber="5",
            municipalityAbolitionMode="29",
            municipalityAbolitionDate="2010-01-01",
        )
        got = self.identity(old, self.muni("2"))
        self.assertNotIn((RDF.type, VL.Deprecated), got)
        self.assertEqual(
            {o for (p, o) in got if p == VL.version},
            {URIRef(LD + "municipality/version/2")},
        )
        self.assertIn((RDF.type, SCHEMA.DefinedTerm), got)

    def test_missing_admission_date_gives_no_identity(self):
        rec = self.muni("1")
        del rec["municipalityAdmissionDate"]
        self.assertEqual(self.identity(rec), set())

    def test_unresolved_district_gives_no_identity(self):
        self.assertEqual(self.identity(self.muni("1", districtHistId="99")), set())

    def test_entry_mode_outside_11_12_13_gives_no_identity(self):
        self.assertEqual(self.identity(self.muni("1", municipalityEntryMode="14")), set())


class EventTriplesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = make_test_config()
        n = parse_nomenclature(FIXTURE.read_bytes(), config.expected_namespace)
        cls.triples = event_triples(n)

    def has(self, s, p, o):
        self.assertIn(t(s, p, o), self.triples)

    def about(self, s):
        return {x for x in self.triples if x[0] == URIRef(s)}

    def objects(self, s, p):
        return {x[2] for x in self.triples if x[0] == URIRef(s) and x[1] == URIRef(p)}

    def test_merger_event(self):
        e = LD + "municipality/changeevent/2001"
        v = LD + "municipality/version/"
        self.has(e, RDF.type, VL.ChangeEvent)
        self.has(e, RDF.type, CH.MunicipalityChangeEvent)
        self.has(e, SCHEMA.validFrom, Literal("2005-01-01", datatype=XSD.date))
        self.assertEqual(self.objects(e, VL.successor), {URIRef(v + "11003")})
        self.assertEqual(
            self.objects(e, VL.predecessor), {URIRef(v + "11001"), URIRef(v + "11002")}
        )
        self.has(e, VL.inVersionedIdentitySet, REG)
        self.has(v + "11001", VL.endEvent, e)
        self.has(v + "11003", VL.startEvent, e)

    def test_rename_and_hierarchy_types(self):
        self.has(LD + "municipality/changeevent/2002", RDF.type, VL.ChangeOfName)
        self.has(LD + "municipality/changeevent/157", RDF.type, VL.ChangeInHierarchy)

    def test_b5_mode22(self):
        # legacy-parity: B5
        m = LD + "municipality/changeevent/2008"
        self.assertNotIn(t(m, RDF.type, VL.ChangeOfName), self.triples)
        d = LD + "district/changeevent/150"
        self.has(d, RDF.type, VL.ChangeOfName)
        self.assertEqual(
            self.objects(d, VL.predecessor), {URIRef(LD + "district/version/10100")}
        )
        self.assertEqual(
            self.objects(d, VL.successor), {URIRef(LD + "district/version/10101")}
        )

    def test_initial_recording(self):
        e = LD + "municipality/changeevent/1000_11001"
        for c in (VL.ChangeEvent, CH.MunicipalityChangeEvent, VL.InitialRecording):
            self.has(e, RDF.type, c)
        self.has(e, SCHEMA.validFrom, Literal("1960-01-01", datatype=XSD.date))
        self.has(e, VL.successor, LD + "municipality/version/11001")
        self.has(LD + "district/changeevent/1000_10100", RDF.type, CH.DistrictChangeEvent)

    def test_b6_mode25_no_start_event(self):
        # legacy-parity: B6
        self.assertEqual(self.objects(LD + "municipality/version/11008", VL.startEvent), set())
        self.assertEqual(self.about(LD + "municipality/changeevent/2004"), set())

    def test_b6_abolition_only_event(self):
        # legacy-parity: B6
        e = LD + "municipality/changeevent/2005"
        v = LD + "municipality/version/"
        self.assertEqual(
            self.about(e),
            {
                t(e, RDF.type, VL.ChangeEvent),
                t(e, VL.predecessor, v + "11008"),
                t(e, VL.predecessor, v + "11009"),
                t(e, VL.inVersionedIdentitySet, REG),
            },
        )

    def test_district_merge_event(self):
        e = LD + "district/changeevent/157"
        v = LD + "district/version/"
        self.has(e, RDF.type, VL.ChangeEvent)
        self.has(e, RDF.type, CH.DistrictChangeEvent)
        self.assertEqual(self.objects(e, VL.predecessor), {URIRef(v + "10102")})
        self.assertEqual(self.objects(e, VL.successor), {URIRef(v + "10104")})

    def nom(self, muni=(), dist=()):
        return Nomenclature("2026-01-01", [], list(dist), list(muni))

    def muni(self, **kw):
        base = {"historyMunicipalityId": "5"}
        base.update(kw)
        return base

    def test_required_fields(self):
        adm = dict(municipalityAdmissionNumber="9", municipalityAdmissionMode="21")
        self.assertEqual(event_triples(self.nom([self.muni(**adm)])), set())
        with_date = self.muni(municipalityAdmissionDate="2000-01-01", **adm)
        self.assertTrue(event_triples(self.nom([with_date])))
        for k in adm:
            rec = dict(with_date)
            del rec[k]
            self.assertEqual(event_triples(self.nom([rec])), set())
        ab = self.muni(
            municipalityAbolitionNumber="9",
            municipalityAbolitionMode="29",
            municipalityAbolitionDate="2000-01-01",
        )
        self.assertTrue(event_triples(self.nom([ab])))
        del ab["municipalityAbolitionMode"]
        self.assertEqual(event_triples(self.nom([ab])), set())

    def test_unknown_admission_mode_gives_nothing(self):
        rec = self.muni(
            municipalityAdmissionNumber="9",
            municipalityAdmissionMode="28",
            municipalityAdmissionDate="2000-01-01",
        )
        self.assertEqual(event_triples(self.nom([rec])), set())


class InferenceAndGraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = make_test_config()
        cls.nom = parse_nomenclature(FIXTURE.read_bytes(), cls.config.expected_namespace)
        cls.graph = build_graph(cls.nom, cls.config)

    def test_version_chain_cross_product(self):
        mv = LD + "municipality/version/"
        for s, p, o in [
            (mv + "11001", VL.successor, mv + "11003"),
            (mv + "11002", VL.successor, mv + "11003"),
            (mv + "11003", VL.predecessor, mv + "11001"),
            (mv + "11003", VL.predecessor, mv + "11002"),
        ]:
            self.assertIn(t(s, p, o), self.graph)

    def test_b3_identity_typed_by_rule_only(self):
        s = URIRef(LD + "municipality/2")
        own = {(p, o) for (x, p, o) in self.graph if x == s}
        self.assertEqual(
            own,
            {
                (RDF.type, CH.Municipality),
                (SCHEMA.inDefinedTermSet, URIRef(LD + "dimension/municipality")),
            },
        )

    def test_place_hierarchy(self):
        m1, d101 = LD + "municipality/1", LD + "district/101"
        c1, c2, d201 = LD + "canton/1", LD + "canton/2", LD + "district/201"
        for s, p, o in [
            (m1, SCHEMA.containedInPlace, d101),
            (m1, SCHEMA.containedInPlace, c1),
            (m1, SCHEMA.containedInPlace, CHE),
            (c1, SCHEMA.containsPlace, m1),
            (d101, SCHEMA.hasPart, m1),
            (c2, SCHEMA.hasPart, d201),
        ]:
            self.assertIn(t(s, p, o), self.graph)
        self.assertNotIn(t(c1, SCHEMA.hasPart, m1), self.graph)

    def test_inferred_returns_only_new(self):
        base = (
            register_and_version_triples(self.nom, self.config)
            | identity_triples(self.nom, self.config)
            | event_triples(self.nom)
        )
        new = inferred_triples(base)
        self.assertTrue(new)
        self.assertEqual(new & base, set())
        self.assertEqual(base | new, self.graph)

    def test_build_graph_matches_golden(self):
        golden_path = FIXTURE.with_name("ech0071_v1_1_sample_expected.nt")
        old = rdflib.NORMALIZE_LITERALS
        rdflib.NORMALIZE_LITERALS = False
        try:
            g = rdflib.Graph()
            g.parse(golden_path, format="nt")
            expected = set(g)
        finally:
            rdflib.NORMALIZE_LITERALS = old
        if self.graph != expected:
            diff = sorted(
                [("only-code",) + x for x in self.graph - expected]
                + [("only-golden",) + x for x in expected - self.graph],
                key=str,
            )
            print("\n".join(" ".join(str(p) for p in d) for d in diff))
        self.assertEqual(self.graph, expected)


if __name__ == "__main__":
    unittest.main()


class LiteralWhitespaceTest(unittest.TestCase):
    def test_numeric_and_date_literals_are_stripped(self):
        self.assertEqual(lit_int("\n 2 ").toPython(), 2)
        self.assertEqual(str(lit_int(" 2 ")), "2")
        self.assertEqual(str(lit_date(" 2026-01-01\n")), "2026-01-01")
