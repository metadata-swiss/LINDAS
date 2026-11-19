# municipalities2lindas geometry years

What `CANTON_GEOMETRY_YEAR` and `MUNICIPALITY_GEOMETRY_YEAR` do, when to change
them, and how they moved in the legacy pipeline. Read before changing either
value or the `geo:hasGeometry` mapping. Quirk B7 in
[municipalities2lindas-triple-contract.md](municipalities2lindas-triple-contract.md).

## Meaning

Each current or deprecated canton/municipality identity gets one
`geo:hasGeometry` link into the boundary dataset on `geo.ld.admin.ch`, which
holds one geometry per boundary and year:

- canton: `https://geo.ld.admin.ch/boundaries/canton/geometry-g1/{cantonId}:{year}`
- municipality: `https://geo.ld.admin.ch/boundaries/municipality/geometry-g1/{municipalityId}:{year}`

The years are plain config (defaults 2023 and 2026), not derived from the
source data. The pipeline does not check that the target IRIs exist. A spot
check (2026-11) resolved canton 1 for 2023/2024 and municipality 261 for
2025/2026; a year that does not exist returns 404. Not checked: every emitted
id, in particular abolished municipalities against a recent year.

## When and who

Nothing triggers a change and no workflow sets the variables, so the
`config.py` defaults apply. The pipeline owners decide, with the consumers of
these IRIs. Change a year when:

- `geo.ld.admin.ch` publishes a newer boundary set and the register should link
  to it (municipalities change with mergers, roughly every one or two years).
- Moving to eCH-0071 v1.2.0 (step 2), where the years must be decided
  deliberately.
- Emitted geometry IRIs start returning 404.

Rules:

- A change rewrites every `geo:hasGeometry` triple. Roll it out on TEST/INT
  first and review the diff.
- Keep it out of the v1.2.0 switch commit, like any other quirk fix.
- Until step 2 the legacy pipeline is the PROD writer. Changing a year only in
  this port makes the two writers disagree.
- Canton and municipality years are independent. Check both whenever one moves.

## History in the legacy pipeline

The legacy GitLab `main-graphdb` pipeline is the source of the defaults.

Municipality year, set in the BIND of the Identity-Municipality SPARQL
CONSTRUCT:

| Date | Commit | Author | Change |
| --- | --- | --- | --- |
| 2023-08-22 | 5595505 | Adrian Gschwend | Introduced at 2023 |
| 2025-06-10 | 29e8dfc | Michael Luggen | 2023 to 2025 |
| 2025-06-16 | 3b9024f | Michael Luggen | 2025 to 2024, because the 2025 geometries were not ready |
| 2026-03-10 | 8173fb7 | Benedikt Hitz | 2024 to 2026 |

The year stayed at 2023 for almost two years, and 2026 skips 2025. A
commented-out `:2022` municipality line in the XRM mapping was never active.

Canton year, set in the XRM mapping and the CARML file generated from it:

| Date | Commit | Author | Change |
| --- | --- | --- | --- |
| 2022-12-07 | 254b661 | Michael Luggen | Introduced at 2022 (first register version) |
| 2023-08-22 | 5595505 | Adrian Gschwend | 2022 to 2023, same commit that added the municipality geo links |

The canton year has not moved since. It lives in a different file than the
municipality year, so the later municipality bumps (SPARQL only) may simply
have missed it. The two were last in step in August 2023. Whether 2023 is
still the right canton year is open.
