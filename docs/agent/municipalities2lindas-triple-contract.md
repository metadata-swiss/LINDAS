# municipalities2lindas: triple contract and legacy quirks

Reference for changing `municipalities2lindas/src/mapper.py`. This is the
specification the mapper implements; the checked-in fixture
`municipalities2lindas/tests/fixtures/ech0071_v1_1_sample_expected.nt` is the
executable form of it. Origin: the legacy GitLab pipeline `fso-ech_0071-ld`,
branch `main-graphdb`, HEAD 8173fb7 (CARML mapping, 10 SPARQL CONSTRUCTs, 3 N3
rule files). Live PROD parity was proven: 347,070 triples, 0 added, 0 removed.

Quirks B1-B6 are marked `# legacy-parity: B<n>` in `mapper.py`; `grep -rn
legacy-parity municipalities2lindas/src` lists them. B7 is the two geometry-year
defaults in `config.py`; B8 is a consequence of the identity rules in A2, not a
single code site.

Prefixes:

| Prefix | IRI |
| --- | --- |
| `schema:` | `http://schema.org/` (http) |
| `vl:` | `https://version.link/` |
| `ch:` / `admin:` | `https://schema.ld.admin.ch/` |
| `ech:` | `https://ld.admin.ch/ech/71/` |
| `prov:` | `http://www.w3.org/ns/prov#` |
| `geo:` | `http://www.opengis.net/ont/geosparql#` |
| `gn:` | `http://www.geonames.org/ontology#` |
| `skos:` | `http://www.w3.org/2004/02/skos/core#` |

Conventions:

- `{x}` is raw XML text.
- `int(x)` is `"{x}"^^xsd:integer`, with the lexical form unchanged.
- `date(x)` is `"{x}"^^xsd:date`.
- A missing source field means no triple.
- `REG` is `<https://ld.admin.ch/fso/register>`.
- `CHE` is `<https://ld.admin.ch/country/CHE>`.

## A1. Mapping (`mappings/mapping.xrm` → `src-gen/mapping.carml.ttl`)

**Canton identity**, per `canton`: `<https://ld.admin.ch/canton/{cantonId}>`

- `a` `ch:Canton`, `schema:AdministrativeArea`, `schema:State`,
  `schema:DefinedTerm`, `vl:Identity`
- `schema:legalName {cantonLongName}`
- `skos:hiddenLabel {cantonLongName}`
- `schema:alternateName {cantonAbbreviation}`
- `schema:identifier int(cantonId)`
- `geo:hasGeometry <https://geo.ld.admin.ch/boundaries/canton/geometry-g1/{cantonId}:{CANTON_GEOMETRY_YEAR}>`
- `gn:featureCode gn:A.ADM1`
- `schema:validFrom date(cantonDateOfChange)`
- `schema:inDefinedTermSet <https://ld.admin.ch/dimension/canton>`
- `schema:containedInPlace CHE`
- `schema:isPartOf CHE`
- `prov:hadPrimarySource <https://geo.ld.admin.ch/boundaries/canton/{cantonId}>`
- `prov:hadPrimarySource <https://register.ld.admin.ch/agvch/canton/{cantonId}>`

Also `CHE schema:containsPlace <…/canton/{cantonId}>`. No `schema:name` on the
canton identity.

**District version**, per `district`: `<https://ld.admin.ch/district/version/{districtHistId}>`

- `a` `vl:Version`, `schema:DefinedTerm`
- `schema:identifier int(districtHistId)`
- `schema:isPartOf` and `schema:containedInPlace <https://ld.admin.ch/canton/{cantonId}>`
- `vl:identity <https://ld.admin.ch/district/{districtId}>`
- `vl:identityIdentifier int(districtId)`
- `schema:name {districtShortName}`
- `schema:legalName {districtLongName}`
- `schema:validFrom date(districtAdmissionDate)`
- `schema:validThrough date(districtAbolitionDate)`
- `gn:featureCode gn:A.ADM2`
- `prov:hadPrimarySource <https://register.ld.admin.ch/agvch/districtversion/{districtHistId}>`
- `vl:inVersionedIdentitySet REG`

**Municipality version**, per `municipality`: `<https://ld.admin.ch/municipality/version/{historyMunicipalityId}>`

- `a` `vl:Version`, `schema:DefinedTerm`
- `schema:identifier int(historyMunicipalityId)`
- `prov:hadPrimarySource <https://register.ld.admin.ch/agvch/municipalityversion/{historyMunicipalityId}>`
- `schema:legalName {municipalityLongName}`
- `schema:name {municipalityShortName}`
- `vl:identityIdentifier int(municipalityId)`
- `vl:identity <https://ld.admin.ch/municipality/{municipalityId}>`
- `schema:isPartOf <https://ld.admin.ch/district/version/{districtHistId}>` (the
  district **version**)
- `schema:validFrom date(municipalityAdmissionDate)`
- `schema:validThrough date(municipalityAbolitionDate)`
- `gn:featureCode gn:A.ADM3`
- `vl:inVersionedIdentitySet REG`

**Register canton**: `<https://register.ld.admin.ch/agvch/canton/{cantonId}>`

- `a ech:Canton`
- `schema:name` and `schema:legalName {cantonLongName}`
- `schema:identifier int(cantonId)`
- `schema:alternateName {cantonAbbreviation}`
- `ech:cantonAbbreviation {cantonAbbreviation}`
- `ech:cantonId int(cantonId)`
- `ech:date date(cantonDateOfChange)`

**Register district**, one per distinct `districtId`: `<https://register.ld.admin.ch/agvch/district/{districtId}>`

- `a ech:District`
- `ech:districtId` and `schema:identifier int(districtId)`
- `ech:districtEntryModeId int(districtEntryMode)`. This can have several
  values, one per distinct value across versions.

**Register district version**: `<https://register.ld.admin.ch/agvch/districtversion/{districtHistId}>`

- `a ech:DistrictVersion`
- `ech:districtHistId` and `schema:identifier int(districtHistId)`
- `ech:cantonId int(cantonId)`
- `ech:districtId int(districtId)`
- `ech:district <https://register.ld.admin.ch/agvch/district/{districtId}>`
- `schema:name` and `ech:shortName {districtShortName}`
- `schema:legalName` and `ech:longName {districtLongName}`
- `ech:districtAdmissionNumber int(districtAdmissionNumber)`
- `ech:districtAdmissionModeId int(districtAdmissionMode)`
- `ech:districtAbolitionNumber int(districtAbolitionNumber)`
- `ech:districtAbolitionModeId int(districtAbolitionMode)`
- `ech:districtAdmissionDate`, `ech:districtAbolitionDate` and
  `ech:districtDateOfChange` as `date(...)`

**Register municipality version**: `<https://register.ld.admin.ch/agvch/municipalityversion/{historyMunicipalityId}>`

- `a ech:MunicipalityVersion`
- `ech:historyMunicipalityId` and `schema:identifier int(historyMunicipalityId)`
- `ech:longName` and `schema:legalName {municipalityLongName}`
- `ech:shortName` and `schema:name {municipalityShortName}`
- `ech:districtHistId int(districtHistId)`
- `ech:cantonAbbreviation {cantonAbbreviation}`
- `ech:municipalityId int(municipalityId)`
- `ech:municipality <https://register.ld.admin.ch/agvch/municipality/{municipalityId}>`
- `ech:municipalityStatusId int(municipalityStatus)`
- `ech:municipalityAdmissionNumber`, `ech:municipalityAdmissionModeId`,
  `ech:municipalityAbolitionNumber` and `ech:municipalityAbolitionModeId` as
  `int(...)`
- `ech:municipalityAdmissionDate`, `ech:municipalityAbolitionDate` and
  `ech:municipalityDateOfChange` as `date(...)`
- `ech:municipalityEntryModeId int(municipalityEntryMode)`

**Register municipality**: `<https://register.ld.admin.ch/agvch/municipality/{municipalityId}>`

- `a ech:Municipality`
- `ech:municipalityId` and `schema:identifier int(municipalityId)`
- `ech:municipalityEntryModeId int(municipalityEntryMode)`, possibly
  multi-valued

**Register municipality event**, per `municipality`: `<https://ld.admin.ch/municipality/changeevent/{municipalityAdmissionNumber}>`

- `a ech:MunicipalityChangeEvent`
- `ech:date date(municipalityAdmissionDate)`
- `ech:municipalityAdmissionNumber` and `schema:identifier int(municipalityAdmissionNumber)`

This applies to all admission modes, including 20.

**Register district event**, per `district`: **`<https://ld.admin.ch/municipality/changeevent/{districtAdmissionNumber}>`** (quirk B1)

- `a ech:DistrictChangeEvent`
- `ech:date date(districtAdmissionDate)`
- `ech:districtAdmissionNumber` and `schema:identifier int(districtAdmissionNumber)`

## A2. Identity and event construction (`sparql/*.rq`, computed from source records only)

Definitions:

- *current* means the version has no `AbolitionNumber`.
- `munType` is entry mode 11 → `ch:PoliticalMunicipality`, 12 →
  `ch:MunicipalityFreeArea`, 13 → `ch:CantonalLakePortion`. Any other entry
  mode: no identity.
- `districtIdOf(districtHistId)` joins through the district versions.

**Current municipality identity** (`Identity-Municipality.rq`). For each current
municipality version `v` whose entry mode maps to `munType` and whose
`districtHistId` resolves:

`<…/municipality/{municipalityId}>`

- `a vl:Identity, munType, schema:DefinedTerm`
- `gn:featureCode gn:A.ADM3`
- `vl:version v`
- `vl:inVersionedIdentitySet REG`
- `schema:inDefinedTermSet <https://ld.admin.ch/dimension/municipality>`
- `schema:identifier int(municipalityId)`
- `schema:name {municipalityShortName}`
- `schema:isPartOf <https://ld.admin.ch/district/{districtIdOf}>`
- `geo:hasGeometry <https://geo.ld.admin.ch/boundaries/municipality/geometry-g1/{municipalityId}:{MUNICIPALITY_GEOMETRY_YEAR}>`
- `prov:hadPrimarySource <register municipalityversion of v>`
- `prov:hadPrimarySource <https://geo.ld.admin.ch/boundaries/municipality/{municipalityId}>`

**Deprecated municipality identity** (`Identity-Municipality-Deprecated.rq`).

- Applies to `municipalityId`s that have no current version and at least one
  version with abolition mode 29.
- Take the version(s) with abolition mode 29 whose abolition date equals the
  maximum mode-29 abolition date for that id, with entry mode in 11/12/13 and
  a `districtHistId` that resolves.
- The subquery's max is grouped only by id, so compute it the same way: across
  all mode-29 versions of the id that have an entry mode.

For each such version: `a vl:Identity, vl:Deprecated, munType`; `vl:version v`;
`vl:inVersionedIdentitySet REG`; `schema:identifier`; `schema:name`;
`schema:isPartOf` district identity; both `prov:hadPrimarySource` values as in
the current identity. **No** `schema:DefinedTerm`, featureCode,
`inDefinedTermSet` or geometry.

**Current district identity** (`Identity-District.rq`). For each current
district version `v`: `<…/district/{districtId}>`

- `a vl:Identity, ch:District, schema:DefinedTerm`
- `vl:version v`
- `vl:inVersionedIdentitySet REG`
- `schema:inDefinedTermSet <https://ld.admin.ch/dimension/district>`
- `schema:identifier int(districtId)`
- `schema:name {districtShortName}`
- `schema:isPartOf <…/canton/{cantonId}>`
- `prov:hadPrimarySource <register districtversion of v>`

**Deprecated district identity** (`Identity-District-Deprecated.rq`). For the
district version(s) with abolition mode 29 at the max mode-29 abolition date of
the `districtId`, **without** excluding ids that still have a current version
(quirk B2):

- `a vl:Identity, vl:Deprecated, ch:District`
- `vl:version v`
- `vl:inVersionedIdentitySet REG`
- `schema:identifier`
- `schema:name`
- `schema:isPartOf` canton
- `prov:hadPrimarySource` register version

**Admission events** (`*ChangeEvent-Admission.rq`). For each version with
admission mode in the table and an admission date:
`E = <…/{municipality|district}/changeevent/{admissionNumber}>`.

- `E a vl:ChangeEvent, ch:{Municipality|District}ChangeEvent, <type>`
- `schema:validFrom date(admissionDate)`
- `vl:successor v`
- `vl:inVersionedIdentitySet REG`
- `v vl:startEvent E`

| mode | municipality type | district type |
| --- | --- | --- |
| 21 | vl:ChangeEvent | vl:ChangeEvent |
| 22 | vl:ChangeEvent | **vl:ChangeOfName** |
| 23 | vl:ChangeOfName | vl:ChangeOfName |
| 24 | vl:ChangeInHierarchy | vl:ChangeInHierarchy |
| 26 | vl:ChangeEvent | vl:ChangeEvent |
| 27 | vl:ChangeEvent | vl:ChangeEvent |

Other modes (25, unknown): no admission event and no `startEvent`.

**Initial recording** (`*InitialRecording.rq`), admission mode 20:
`E = <…/{municipality|district}/changeevent/{admissionNumber}_{histId}>`.

- `a vl:ChangeEvent, ch:{Municipality|District}ChangeEvent, vl:InitialRecording`
- `schema:validFrom date(admissionDate)`
- `vl:successor v`
- `vl:inVersionedIdentitySet REG`
- `v vl:startEvent E`

**Abolition events** (`*ChangeEvent-Abolision.rq`). For each version with an
abolition number, an abolition mode and an abolition date (any mode):
`E = <…/{municipality|district}/changeevent/{abolitionNumber}>`.

- `E a vl:ChangeEvent`
- `vl:predecessor v`
- `vl:inVersionedIdentitySet REG`
- `v vl:endEvent E`

No date. These merge with admission events of the same number.

## A3. Inferred triples (`rules/*.n3`, computed to a fixpoint over all of A1 + A2)

- `version-chain.n3`: for every `E a vl:ChangeEvent` with `vl:successor s` and
  `vl:predecessor p`, emit `p vl:successor s` and `s vl:predecessor p` (full
  cross product).
- `identities.n3`: for every `version prov:hadPrimarySource src ; vl:identity id`:
  - if `src a ech:MunicipalityVersion`: `id a ch:Municipality ;
    schema:inDefinedTermSet <https://ld.admin.ch/dimension/municipality>`;
  - if `src a ech:DistrictVersion`: `id a ch:District ;
    schema:inDefinedTermSet <https://ld.admin.ch/dimension/district>`.
- `place.n3`:
  - `m a ch:Municipality ; schema:isPartOf d . d a ch:District ; schema:isPartOf c`
    ⇒ `m schema:containedInPlace d, c, CHE . c schema:containsPlace m .
    d schema:containsPlace m . d schema:hasPart m`
  - `d a ch:District ; schema:isPartOf c`
    ⇒ `d schema:containedInPlace c, CHE . c schema:containsPlace d .
    c schema:hasPart d`

## B. Legacy quirks kept for parity

Each quirk is a legacy bug reproduced on purpose so output stays triple-identical.
Examples are from the v1.1 source (validFrom 2026-01-01) where one exists;
otherwise the case is built in the unit-test fixture.

- **B1.** District register events are minted on
  `https://ld.admin.ch/municipality/changeevent/{districtAdmissionNumber}`
  (legacy `mapping.xrm`, RegisterDistrictEvent uses `municipalityEventIri`).
  - *Effect:* a district event shares its IRI space with municipality events. If
    a district and a municipality ever have the same admission number, both
    land on one subject with two types and two dates.
  - *Example:* district Gäu (`districtAdmissionNumber` 125) gets the register
    event `…/municipality/changeevent/125`, while its A2 admission event is
    `…/district/changeevent/125`. The v1.1 file has no number used by both a
    district and a municipality, so no collision occurs today.
- **B2.** The deprecated-district query does not exclude district ids that still
  have a current version.
  - *Effect:* such an id is both current and deprecated, with two names and two
    `vl:version` values on one IRI.
  - *Example:* `districtId` 111 has the current version 10229 (Dietikon, admitted
    1990-01-01) and the mode-29 version 10119 (Zürich, abolished 1989-12-31).
    `…/district/111` gets `vl:Deprecated` next to `schema:DefinedTerm`, plus both
    names. It is the only such id in v1.1.
- **B3.** Ids abolished only with modes other than 29, and without a current
  version, get no identity triples. They still get `ch:Municipality`/`ch:District`
  and `inDefinedTermSet` from `identities.n3`.
  - *Effect:* the id is typed and in the term set, but has no `vl:Identity`,
    name or version link.
  - *Example:* `municipalityId` 4954 (Wigoltingen) has one version, 10281,
    abolished 1994-12-31 with mode 26 (merger). 157 municipality ids and 4
    district ids (for example 230 Wangen, mode 27) are affected.
- **B4.** Ties on the max mode-29 abolition date produce several
  `vl:version`/`schema:name`/`isPartOf` on one identity.
  - *Effect:* the identity gets one value per tied version instead of a single
    pick.
  - *Example:* no tie in v1.1. If versions A ("Foo") and B ("Foo-Bar") of id 9
    are both abolished with mode 29 on 2010-12-31, `…/municipality/9` gets
    both versions and both names.
- **B5.** Admission mode 22 maps to `vl:ChangeOfName` for districts but to
  `vl:ChangeEvent` for municipalities.
  - *Example:* district Gäu (hist id 10230, number 125, 1991-01-01) gets
    `vl:ChangeOfName`; municipality Egerkingen (hist id 13703, number 1513,
    1991-01-01) gets plain `vl:ChangeEvent`. Mode 22 occurs 6 times for
    districts and 47 times for municipalities.
- **B6.** Admission mode 25 gets no start event; abolition-only events have no
  date and no `ch:*ChangeEvent` type.
  - *Effect:* no `vl:startEvent` for a mode-25 version. An abolition number
    that matches no admission number yields an event with only `vl:ChangeEvent`,
    `vl:predecessor` and `vl:inVersionedIdentitySet`.
  - *Example:* neither case occurs in v1.1: there is no mode 25, and every
    abolition number also appears as an admission number. Normally the two sides
    merge, so the abolition event inherits the date and the class from the
    successor's admission.
- **B7.** Canton geometry year is fixed at 2023; municipality geometry year is 2026.
  - *Example:* canton 1 links to `…/canton/geometry-g1/1:2023`; municipality 261
    links to `…/municipality/geometry-g1/261:2026`. The years are changed
    through `CANTON_GEOMETRY_YEAR` and `MUNICIPALITY_GEOMETRY_YEAR`.
- **B8.** `vl:version` from an identity links only the current version (or the
  deprecated pick), not the history.
  - *Example:* `municipalityId` 3514 (Schmitten (GR)) has versions 10007, 14153
    and the current 15964. `…/municipality/3514` has `vl:version` only for 15964;
    the older versions point to the identity through `vl:identity` but not the
    other way round.
