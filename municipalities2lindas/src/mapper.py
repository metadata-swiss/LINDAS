"""Map eCH-0071 records to LINDAS triples, ported from the legacy CARML pipeline."""

from __future__ import annotations

from typing import Iterable, Set, Tuple, Union

from rdflib import XSD, Literal, Namespace, URIRef
from rdflib.namespace import RDF

from .config import MunicipalitiesConfig
from .source import Nomenclature, Record

SCHEMA = Namespace("http://schema.org/")
VL = Namespace("https://version.link/")
CH = Namespace("https://schema.ld.admin.ch/")
ECH = Namespace("https://ld.admin.ch/ech/71/")
PROV = Namespace("http://www.w3.org/ns/prov#")
GEO = Namespace("http://www.opengis.net/ont/geosparql#")
GN = Namespace("http://www.geonames.org/ontology#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

REG = URIRef("https://ld.admin.ch/fso/register")
CHE = URIRef("https://ld.admin.ch/country/CHE")

LD = "https://ld.admin.ch/"
AGVCH = "https://register.ld.admin.ch/agvch/"

Triple = Tuple[URIRef, URIRef, Union[URIRef, Literal]]


def lit_int(text: str) -> Literal:
    return Literal(text.strip(), datatype=XSD.integer, normalize=False)


def lit_date(text: str) -> Literal:
    return Literal(text.strip(), datatype=XSD.date, normalize=False)


def lit_str(text: str) -> Literal:
    return Literal(text, normalize=False)


def _int(rec: Record, key: str):
    return lit_int(rec[key]) if key in rec else None


def _date(rec: Record, key: str):
    return lit_date(rec[key]) if key in rec else None


def _str(rec: Record, key: str):
    return lit_str(rec[key]) if key in rec else None


def _emit(out: Set[Triple], s: URIRef, pairs: Iterable[tuple]) -> None:
    """Add (p, o) pairs for subject s, skipping those whose object is None."""
    for p, o in pairs:
        if o is not None:
            out.add((s, p, o))


def register_and_version_triples(
    n: Nomenclature, config: MunicipalitiesConfig
) -> Set[Triple]:
    """Everything the legacy CARML stage produced (Appendix A1)."""
    out: Set[Triple] = set()
    for canton in n.cantons:
        _canton_identity(out, canton, config)
        _register_canton(out, canton)
    for district in n.districts:
        _district_version(out, district)
        _register_district(out, district)
        _register_district_version(out, district)
        _register_district_event(out, district)
    for m in n.municipalities:
        _municipality_version(out, m)
        _register_municipality_version(out, m)
        _register_municipality(out, m)
        _register_municipality_event(out, m)
    return out


def _canton_identity(out: Set[Triple], c: Record, config: MunicipalitiesConfig) -> None:
    """mapping.xrm canton identity map."""
    cid = c["cantonId"]
    s = URIRef(f"{LD}canton/{cid}")
    for typ in (CH.Canton, SCHEMA.AdministrativeArea, SCHEMA.State, SCHEMA.DefinedTerm, VL.Identity):
        out.add((s, RDF.type, typ))
    _emit(
        out,
        s,
        [
            (SCHEMA.legalName, _str(c, "cantonLongName")),
            (SKOS.hiddenLabel, _str(c, "cantonLongName")),
            (SCHEMA.alternateName, _str(c, "cantonAbbreviation")),
            (SCHEMA.identifier, lit_int(cid)),
            (
                GEO.hasGeometry,
                URIRef(
                    "https://geo.ld.admin.ch/boundaries/canton/geometry-g1/"
                    f"{cid}:{config.canton_geometry_year}"
                ),
            ),
            (GN.featureCode, GN["A.ADM1"]),
            (SCHEMA.validFrom, _date(c, "cantonDateOfChange")),
            (SCHEMA.inDefinedTermSet, URIRef(f"{LD}dimension/canton")),
            (SCHEMA.containedInPlace, CHE),
            (SCHEMA.isPartOf, CHE),
            (PROV.hadPrimarySource, URIRef(f"https://geo.ld.admin.ch/boundaries/canton/{cid}")),
            (PROV.hadPrimarySource, URIRef(f"{AGVCH}canton/{cid}")),
        ],
    )
    out.add((CHE, SCHEMA.containsPlace, s))


def _district_version(out: Set[Triple], d: Record) -> None:
    """mapping.xrm district version map."""
    hist = d["districtHistId"]
    s = URIRef(f"{LD}district/version/{hist}")
    out.add((s, RDF.type, VL.Version))
    out.add((s, RDF.type, SCHEMA.DefinedTerm))
    canton = URIRef(f"{LD}canton/{d['cantonId']}") if "cantonId" in d else None
    did = d.get("districtId")
    _emit(
        out,
        s,
        [
            (SCHEMA.identifier, lit_int(hist)),
            (SCHEMA.isPartOf, canton),
            (SCHEMA.containedInPlace, canton),
            (VL.identity, URIRef(f"{LD}district/{did}") if did is not None else None),
            (VL.identityIdentifier, _int(d, "districtId")),
            (SCHEMA.name, _str(d, "districtShortName")),
            (SCHEMA.legalName, _str(d, "districtLongName")),
            (SCHEMA.validFrom, _date(d, "districtAdmissionDate")),
            (SCHEMA.validThrough, _date(d, "districtAbolitionDate")),
            (GN.featureCode, GN["A.ADM2"]),
            (PROV.hadPrimarySource, URIRef(f"{AGVCH}districtversion/{hist}")),
            (VL.inVersionedIdentitySet, REG),
        ],
    )


def _municipality_version(out: Set[Triple], m: Record) -> None:
    """mapping.xrm municipality version map."""
    hist = m["historyMunicipalityId"]
    s = URIRef(f"{LD}municipality/version/{hist}")
    out.add((s, RDF.type, VL.Version))
    out.add((s, RDF.type, SCHEMA.DefinedTerm))
    mid = m.get("municipalityId")
    dh = m.get("districtHistId")
    _emit(
        out,
        s,
        [
            (SCHEMA.identifier, lit_int(hist)),
            (PROV.hadPrimarySource, URIRef(f"{AGVCH}municipalityversion/{hist}")),
            (SCHEMA.legalName, _str(m, "municipalityLongName")),
            (SCHEMA.name, _str(m, "municipalityShortName")),
            (VL.identityIdentifier, _int(m, "municipalityId")),
            (VL.identity, URIRef(f"{LD}municipality/{mid}") if mid is not None else None),
            (SCHEMA.isPartOf, URIRef(f"{LD}district/version/{dh}") if dh is not None else None),
            (SCHEMA.validFrom, _date(m, "municipalityAdmissionDate")),
            (SCHEMA.validThrough, _date(m, "municipalityAbolitionDate")),
            (GN.featureCode, GN["A.ADM3"]),
            (VL.inVersionedIdentitySet, REG),
        ],
    )


def _register_canton(out: Set[Triple], c: Record) -> None:
    """mapping.xrm register canton map."""
    s = URIRef(f"{AGVCH}canton/{c['cantonId']}")
    out.add((s, RDF.type, ECH.Canton))
    name = _str(c, "cantonLongName")
    abbr = _str(c, "cantonAbbreviation")
    _emit(
        out,
        s,
        [
            (SCHEMA.name, name),
            (SCHEMA.legalName, name),
            (SCHEMA.identifier, lit_int(c["cantonId"])),
            (SCHEMA.alternateName, abbr),
            (ECH.cantonAbbreviation, abbr),
            (ECH.cantonId, lit_int(c["cantonId"])),
            (ECH.date, _date(c, "cantonDateOfChange")),
        ],
    )


def _register_district(out: Set[Triple], d: Record) -> None:
    """mapping.xrm register district map (one subject per distinct districtId)."""
    if "districtId" not in d:
        return
    s = URIRef(f"{AGVCH}district/{d['districtId']}")
    out.add((s, RDF.type, ECH.District))
    _emit(
        out,
        s,
        [
            (ECH.districtId, _int(d, "districtId")),
            (SCHEMA.identifier, _int(d, "districtId")),
            (ECH.districtEntryModeId, _int(d, "districtEntryMode")),
        ],
    )


def _register_district_version(out: Set[Triple], d: Record) -> None:
    """mapping.xrm register district version map."""
    hist = d["districtHistId"]
    s = URIRef(f"{AGVCH}districtversion/{hist}")
    out.add((s, RDF.type, ECH.DistrictVersion))
    did = d.get("districtId")
    _emit(
        out,
        s,
        [
            (ECH.districtHistId, lit_int(hist)),
            (SCHEMA.identifier, lit_int(hist)),
            (ECH.cantonId, _int(d, "cantonId")),
            (ECH.districtId, _int(d, "districtId")),
            (ECH.district, URIRef(f"{AGVCH}district/{did}") if did is not None else None),
            (SCHEMA.name, _str(d, "districtShortName")),
            (ECH.shortName, _str(d, "districtShortName")),
            (SCHEMA.legalName, _str(d, "districtLongName")),
            (ECH.longName, _str(d, "districtLongName")),
            (ECH.districtAdmissionNumber, _int(d, "districtAdmissionNumber")),
            (ECH.districtAdmissionModeId, _int(d, "districtAdmissionMode")),
            (ECH.districtAbolitionNumber, _int(d, "districtAbolitionNumber")),
            (ECH.districtAbolitionModeId, _int(d, "districtAbolitionMode")),
            (ECH.districtAdmissionDate, _date(d, "districtAdmissionDate")),
            (ECH.districtAbolitionDate, _date(d, "districtAbolitionDate")),
            (ECH.districtDateOfChange, _date(d, "districtDateOfChange")),
        ],
    )


def _register_municipality_version(out: Set[Triple], m: Record) -> None:
    """mapping.xrm register municipality version map."""
    hist = m["historyMunicipalityId"]
    s = URIRef(f"{AGVCH}municipalityversion/{hist}")
    out.add((s, RDF.type, ECH.MunicipalityVersion))
    mid = m.get("municipalityId")
    _emit(
        out,
        s,
        [
            (ECH.historyMunicipalityId, lit_int(hist)),
            (SCHEMA.identifier, lit_int(hist)),
            (ECH.longName, _str(m, "municipalityLongName")),
            (SCHEMA.legalName, _str(m, "municipalityLongName")),
            (ECH.shortName, _str(m, "municipalityShortName")),
            (SCHEMA.name, _str(m, "municipalityShortName")),
            (ECH.districtHistId, _int(m, "districtHistId")),
            (ECH.cantonAbbreviation, _str(m, "cantonAbbreviation")),
            (ECH.municipalityId, _int(m, "municipalityId")),
            (ECH.municipality, URIRef(f"{AGVCH}municipality/{mid}") if mid is not None else None),
            (ECH.municipalityStatusId, _int(m, "municipalityStatus")),
            (ECH.municipalityAdmissionNumber, _int(m, "municipalityAdmissionNumber")),
            (ECH.municipalityAdmissionModeId, _int(m, "municipalityAdmissionMode")),
            (ECH.municipalityAbolitionNumber, _int(m, "municipalityAbolitionNumber")),
            (ECH.municipalityAbolitionModeId, _int(m, "municipalityAbolitionMode")),
            (ECH.municipalityAdmissionDate, _date(m, "municipalityAdmissionDate")),
            (ECH.municipalityAbolitionDate, _date(m, "municipalityAbolitionDate")),
            (ECH.municipalityDateOfChange, _date(m, "municipalityDateOfChange")),
            (ECH.municipalityEntryModeId, _int(m, "municipalityEntryMode")),
        ],
    )


def _register_municipality(out: Set[Triple], m: Record) -> None:
    """mapping.xrm register municipality map (one subject per distinct municipalityId)."""
    if "municipalityId" not in m:
        return
    s = URIRef(f"{AGVCH}municipality/{m['municipalityId']}")
    out.add((s, RDF.type, ECH.Municipality))
    _emit(
        out,
        s,
        [
            (ECH.municipalityId, _int(m, "municipalityId")),
            (SCHEMA.identifier, _int(m, "municipalityId")),
            (ECH.municipalityEntryModeId, _int(m, "municipalityEntryMode")),
        ],
    )


def _register_municipality_event(out: Set[Triple], m: Record) -> None:
    """mapping.xrm register municipality event map, all admission modes."""
    num = m.get("municipalityAdmissionNumber")
    if num is None:
        return
    s = URIRef(f"{LD}municipality/changeevent/{num}")
    out.add((s, RDF.type, ECH.MunicipalityChangeEvent))
    _emit(
        out,
        s,
        [
            (ECH.date, _date(m, "municipalityAdmissionDate")),
            (ECH.municipalityAdmissionNumber, lit_int(num)),
            (SCHEMA.identifier, lit_int(num)),
        ],
    )


def _register_district_event(out: Set[Triple], d: Record) -> None:
    """mapping.xrm register district event map."""
    num = d.get("districtAdmissionNumber")
    if num is None:
        return
    # legacy-parity: B1
    s = URIRef(f"{LD}municipality/changeevent/{num}")
    out.add((s, RDF.type, ECH.DistrictChangeEvent))
    _emit(
        out,
        s,
        [
            (ECH.date, _date(d, "districtAdmissionDate")),
            (ECH.districtAdmissionNumber, lit_int(num)),
            (SCHEMA.identifier, lit_int(num)),
        ],
    )


MUNICIPALITY_TYPES = {
    "11": CH.PoliticalMunicipality,
    "12": CH.MunicipalityFreeArea,
    "13": CH.CantonalLakePortion,
}


def identity_triples(n: Nomenclature, config: MunicipalitiesConfig) -> Set[Triple]:
    """Identity construction (Appendix A2), computed from the records only."""
    out: Set[Triple] = set()
    district_ids = {
        d["districtHistId"]: d["districtId"]
        for d in n.districts
        if "districtHistId" in d and "districtId" in d
    }
    _current_municipalities(out, n.municipalities, district_ids, config)
    _deprecated_municipalities(out, n.municipalities, district_ids)
    _current_districts(out, n.districts)
    _deprecated_districts(out, n.districts)
    return out


def _is_current(rec: Record, prefix: str) -> bool:
    return f"{prefix}AbolitionNumber" not in rec


def _max_mode29_abolition(recs: Iterable[Record], prefix: str, require_entry_mode: bool) -> dict:
    """Max abolition date per id over mode-29 versions (ISO dates compare as strings)."""
    last: dict = {}
    for r in recs:
        if (
            f"{prefix}Id" in r
            and f"{prefix}AbolitionDate" in r
            and r.get(f"{prefix}AbolitionMode") == "29"
            and (not require_entry_mode or f"{prefix}EntryMode" in r)
        ):
            date = r[f"{prefix}AbolitionDate"]
            if r[f"{prefix}Id"] not in last or date > last[r[f"{prefix}Id"]]:
                last[r[f"{prefix}Id"]] = date
    return last


def _municipality_identity(
    out: Set[Triple], m: Record, district_ids: dict, typ: URIRef, deprecated: bool
) -> URIRef:
    mid = m["municipalityId"]
    s = URIRef(f"{LD}municipality/{mid}")
    types = [VL.Identity, typ] + ([VL.Deprecated] if deprecated else [SCHEMA.DefinedTerm])
    for t in types:
        out.add((s, RDF.type, t))
    pairs = [
        (VL.version, URIRef(f"{LD}municipality/version/{m['historyMunicipalityId']}")),
        (VL.inVersionedIdentitySet, REG),
        (SCHEMA.identifier, lit_int(mid)),
        (SCHEMA.name, lit_str(m["municipalityShortName"])),
        (SCHEMA.isPartOf, URIRef(f"{LD}district/{district_ids[m['districtHistId']]}")),
        (PROV.hadPrimarySource, URIRef(f"{AGVCH}municipalityversion/{m['historyMunicipalityId']}")),
        (PROV.hadPrimarySource, URIRef(f"https://geo.ld.admin.ch/boundaries/municipality/{mid}")),
    ]
    if not deprecated:
        pairs += [
            (GN.featureCode, GN["A.ADM3"]),
            (SCHEMA.inDefinedTermSet, URIRef(f"{LD}dimension/municipality")),
        ]
    _emit(out, s, pairs)
    return s


def _current_municipalities(
    out: Set[Triple], municipalities: Iterable[Record], district_ids: dict, config
) -> None:
    """Identity-Municipality.rq"""
    for m in municipalities:
        if (
            _is_current(m, "municipality")
            and m.get("municipalityEntryMode") in MUNICIPALITY_TYPES
            and all(
                k in m
                for k in (
                    "municipalityShortName",
                    "municipalityId",
                    "districtHistId",
                    "municipalityAdmissionDate",
                    "historyMunicipalityId",
                )
            )
            and m["districtHistId"] in district_ids
        ):
            typ = MUNICIPALITY_TYPES[m["municipalityEntryMode"]]
            s = _municipality_identity(out, m, district_ids, typ, deprecated=False)
            out.add(
                (
                    s,
                    GEO.hasGeometry,
                    URIRef(
                        "https://geo.ld.admin.ch/boundaries/municipality/geometry-g1/"
                        f"{m['municipalityId']}:{config.municipality_geometry_year}"
                    ),
                )
            )


def _deprecated_municipalities(
    out: Set[Triple], municipalities: Iterable[Record], district_ids: dict
) -> None:
    """Identity-Municipality-Deprecated.rq"""
    municipalities = list(municipalities)
    last = _max_mode29_abolition(municipalities, "municipality", require_entry_mode=True)
    # Anti-join on municipalityId only: the "still exists" check ignores the entry-mode VALUES.
    still_exists = {
        m["municipalityId"]
        for m in municipalities
        if _is_current(m, "municipality")
        and all(k in m for k in ("municipalityShortName", "municipalityId", "municipalityEntryMode"))
    }
    for m in municipalities:
        mid = m.get("municipalityId")
        if (
            mid in last
            and mid not in still_exists
            and m.get("municipalityEntryMode") in MUNICIPALITY_TYPES
            and m.get("municipalityAbolitionMode") == "29"
            and m.get("municipalityAbolitionDate") == last[mid]
            and all(
                k in m
                for k in (
                    "municipalityShortName",
                    "districtHistId",
                    "municipalityAbolitionNumber",
                    "historyMunicipalityId",
                )
            )
            and m["districtHistId"] in district_ids
        ):
            # legacy-parity: B3, B4
            typ = MUNICIPALITY_TYPES[m["municipalityEntryMode"]]
            _municipality_identity(out, m, district_ids, typ, deprecated=True)


def _district_identity(out: Set[Triple], d: Record, deprecated: bool) -> None:
    s = URIRef(f"{LD}district/{d['districtId']}")
    types = [VL.Identity, CH.District] + ([VL.Deprecated] if deprecated else [SCHEMA.DefinedTerm])
    for t in types:
        out.add((s, RDF.type, t))
    pairs = [
        (VL.version, URIRef(f"{LD}district/version/{d['districtHistId']}")),
        (VL.inVersionedIdentitySet, REG),
        (SCHEMA.identifier, lit_int(d["districtId"])),
        (SCHEMA.name, lit_str(d["districtShortName"])),
        (SCHEMA.isPartOf, URIRef(f"{LD}canton/{d['cantonId']}")),
        (PROV.hadPrimarySource, URIRef(f"{AGVCH}districtversion/{d['districtHistId']}")),
    ]
    if not deprecated:
        pairs.append((SCHEMA.inDefinedTermSet, URIRef(f"{LD}dimension/district")))
    _emit(out, s, pairs)


def _current_districts(out: Set[Triple], districts: Iterable[Record]) -> None:
    """Identity-District.rq"""
    for d in districts:
        if _is_current(d, "district") and all(
            k in d
            for k in ("districtShortName", "districtId", "cantonId", "districtAdmissionDate", "districtHistId")
        ):
            _district_identity(out, d, deprecated=False)


def _deprecated_districts(out: Set[Triple], districts: Iterable[Record]) -> None:
    """Identity-District-Deprecated.rq"""
    districts = list(districts)
    last = _max_mode29_abolition(districts, "district", require_entry_mode=False)
    for d in districts:
        did = d.get("districtId")
        if (
            did in last
            and d.get("districtAbolitionMode") == "29"
            and d.get("districtAbolitionDate") == last[did]
            and all(
                k in d
                for k in ("districtShortName", "cantonId", "districtAbolitionNumber", "districtHistId")
            )
        ):
            # legacy-parity: B2
            _district_identity(out, d, deprecated=True)


MUNICIPALITY_ADMISSION_TYPES = {
    "21": VL.ChangeEvent,
    "22": VL.ChangeEvent,  # legacy-parity: B5
    "23": VL.ChangeOfName,
    "24": VL.ChangeInHierarchy,
    "26": VL.ChangeEvent,
    "27": VL.ChangeEvent,
}

DISTRICT_ADMISSION_TYPES = {
    **MUNICIPALITY_ADMISSION_TYPES,
    "22": VL.ChangeOfName,  # legacy-parity: B5
}


def event_triples(n: Nomenclature) -> Set[Triple]:
    """Admission, initial-recording and abolition events (Appendix A2)."""
    out: Set[Triple] = set()
    for m in n.municipalities:
        _events(out, m, "municipality", "historyMunicipalityId",
                CH.MunicipalityChangeEvent, MUNICIPALITY_ADMISSION_TYPES)
    for d in n.districts:
        _events(out, d, "district", "districtHistId",
                CH.DistrictChangeEvent, DISTRICT_ADMISSION_TYPES)
    return out


def _events(out, rec, prefix, hist_key, event_class, types) -> None:
    if hist_key not in rec:
        return
    version = URIRef(f"{LD}{prefix}/version/{rec[hist_key]}")
    base = f"{LD}{prefix}/changeevent/"

    adm_number = rec.get(f"{prefix}AdmissionNumber")
    adm_mode = rec.get(f"{prefix}AdmissionMode")
    adm_date = rec.get(f"{prefix}AdmissionDate")
    if adm_number is not None and adm_mode is not None and adm_date is not None:
        if adm_mode == "20":
            event = URIRef(f"{base}{adm_number}_{rec[hist_key]}")
            classes = [VL.ChangeEvent, event_class, VL.InitialRecording]
        elif adm_mode in types:  # legacy-parity: B6 (mode 25 absent)
            event = URIRef(f"{base}{adm_number}")
            classes = [VL.ChangeEvent, event_class, types[adm_mode]]
        else:
            event = None
        if event is not None:
            for c in classes:
                out.add((event, RDF.type, c))
            out.add((event, SCHEMA.validFrom, lit_date(adm_date)))
            out.add((event, VL.successor, version))
            out.add((event, VL.inVersionedIdentitySet, REG))
            out.add((version, VL.startEvent, event))

    abo_number = rec.get(f"{prefix}AbolitionNumber")
    if (
        abo_number is not None
        and f"{prefix}AbolitionMode" in rec
        and f"{prefix}AbolitionDate" in rec
    ):
        event = URIRef(f"{base}{abo_number}")
        out.add((event, RDF.type, VL.ChangeEvent))  # legacy-parity: B6
        out.add((event, VL.predecessor, version))
        out.add((event, VL.inVersionedIdentitySet, REG))
        out.add((version, VL.endEvent, event))


def _index(triples: Iterable[Triple]):
    by_sp: dict = {}
    for s, p, o in triples:
        by_sp.setdefault((s, p), set()).add(o)
    return by_sp


def _version_chain(by_sp: dict, triples: Iterable[Triple]) -> Set[Triple]:
    out: Set[Triple] = set()
    for s, p, o in triples:
        if p == RDF.type and o == VL.ChangeEvent:
            for succ in by_sp.get((s, VL.successor), ()):
                for pred in by_sp.get((s, VL.predecessor), ()):
                    out.add((pred, VL.successor, succ))
                    out.add((succ, VL.predecessor, pred))
    return out


_VERSION_KINDS = (
    (ECH.MunicipalityVersion, CH.Municipality, LD + "dimension/municipality"),
    (ECH.DistrictVersion, CH.District, LD + "dimension/district"),
)


def _identity_typing(by_sp: dict, triples: Iterable[Triple]) -> Set[Triple]:
    out: Set[Triple] = set()
    for version, p, src in triples:
        if p != PROV.hadPrimarySource:
            continue
        for src_type, id_type, term_set in _VERSION_KINDS:
            if src_type in by_sp.get((src, RDF.type), ()):
                for ident in by_sp.get((version, VL.identity), ()):
                    out.add((ident, RDF.type, id_type))
                    out.add((ident, SCHEMA.inDefinedTermSet, URIRef(term_set)))
    return out


def _place(by_sp: dict, triples: Iterable[Triple]) -> Set[Triple]:
    out: Set[Triple] = set()
    for s, p, o in triples:
        if p != RDF.type:
            continue
        if o == CH.District:
            for canton in by_sp.get((s, SCHEMA.isPartOf), ()):
                out.add((s, SCHEMA.containedInPlace, canton))
                out.add((s, SCHEMA.containedInPlace, CHE))
                out.add((canton, SCHEMA.containsPlace, s))
                out.add((canton, SCHEMA.hasPart, s))
        elif o == CH.Municipality:
            for district in by_sp.get((s, SCHEMA.isPartOf), ()):
                if CH.District not in by_sp.get((district, RDF.type), ()):
                    continue
                for canton in by_sp.get((district, SCHEMA.isPartOf), ()):
                    out.add((s, SCHEMA.containedInPlace, district))
                    out.add((s, SCHEMA.containedInPlace, canton))
                    out.add((s, SCHEMA.containedInPlace, CHE))
                    out.add((canton, SCHEMA.containsPlace, s))
                    out.add((district, SCHEMA.containsPlace, s))
                    out.add((district, SCHEMA.hasPart, s))
    return out


def inferred_triples(triples: Set[Triple]) -> Set[Triple]:
    """Appendix A3 rules iterated to a fixpoint; returns only new triples."""
    known = set(triples)
    while True:
        by_sp = _index(known)
        found: Set[Triple] = set()
        for rule in (_version_chain, _identity_typing, _place):
            found |= rule(by_sp, known)
        found -= known
        if not found:
            return known - set(triples)
        known |= found


def build_graph(n: Nomenclature, config: MunicipalitiesConfig) -> Set[Triple]:
    base = (
        register_and_version_triples(n, config)
        | identity_triples(n, config)
        | event_triples(n)
    )
    return base | inferred_triples(base)
