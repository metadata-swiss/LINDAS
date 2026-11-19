# municipalities2lindas: design rationale

Why the package looks the way it does. Behaviour and config are in
`municipalities2lindas/README.md`; the triple contract is in
[municipalities2lindas-triple-contract.md](municipalities2lindas-triple-contract.md);
the next migration is in
[municipalities2lindas-ech0071-v1.2.0.md](municipalities2lindas-ech0071-v1.2.0.md).

## Why it exists

The historicised municipality directory (cantons, districts, municipalities,
their versions and mutation events) is reference data. ElCom, Zefix, SBB DiDok,
BLV, BAKOM, BAFU and BFS territorial data reference its IRIs, several million
triples in total. The legacy GitLab pipeline `fso-eCH_0071-ld` (operated by BAR)
depended on Sedex and a Node/Java toolchain (barnard59, CARML, Jena `arq`, EYE).
Requirements: read the BFS XML directly, model with version.link, keep every
identifier/class/property stable, run monthly plus manual trigger, operate from
this repo as GitHub Actions.

## Anti-goals (failure even if tests pass)

- An IRI that exists today disappears or changes.
- A broken or truncated download empties or shrinks the PROD graph.
- The pipeline silently republishes a frozen source forever (hence the
  13-month `validFrom` warning in `main.py`).

## Decisions and rejected alternatives

- **Plain-Python port, not a SPARQL/CARML re-run.** Each legacy rule is one
  named function in `mapper.py`; each quirk sits in one marked place. Rejected:
  running the legacy `.rq` through rdflib (slow on `MINUS`/aggregates over
  ~350k triples, typed-literal edge cases, logic split across two languages) and
  running CARML/EYE in containers (keeps the toolchain we retire).
- **Full-graph atomic replace behind a diff check, not incremental
  DELETE/INSERT.** One source file changing monthly; a single GraphDB `PUT`
  `?context=<graph>` is one transaction. Not the i14y frozen-manifest model:
  one download, passed between jobs as an artifact.
- **Literals use the raw XML text with `normalize=False`.** rdflib's default
  normalisation rewrites lexical forms and breaks byte parity. Records keep raw
  `.text` (no strip, no int conversion); an empty element counts as missing.
- **Mapper stage order matters.** Register/version triples (CARML equivalent),
  then identities/events from the *parsed records only* (the legacy CONSTRUCTs
  read only CARML output), then inference to a fixpoint over everything
  (`place` depends on typing from `identities`).
- **Output is sorted N-Triples.** Diffable, reproducible, and `rapper -i
  ntriples -c` validates it in CI.
- **Self-contained package.** `lindas.py` is its own client; do not import from
  `dataset2lindas`. GraphDB only (raises on a non-GraphDB update URL). The
  existing `upload_turtle` appends, so `replace_graph` is a separate method.
- **The diff compares RDF 1.1 terms, not strings.** An `xsd:string` literal
  equals the plain literal (`diff._canonical`), as RDF 1.1 defines them as the
  same term. An empty live graph is an initial import and bypasses the
  removed-ratio check.
- **Schedule is a repo variable, not a hard-coded cron.** GitHub only accepts a
  literal `schedule.cron`, so callers fire daily at 04:00 UTC and
  `schedule-gate` matches `MUNICIPALITIES_SCHEDULE_<ENV>` (`schedule.py`,
  stdlib only). Time of day stays fixed; hourly triggers are not worth the noise.
- **Own concurrency group per environment** (`municipalities-<env>`); the target
  graph is separate from `fso/i14y`.
- **Only new dependency is `pyshacl`** (Python 3.10, pinned).

## Non-goals (do not fold into unrelated changes)

Fixing legacy quirks (parity first; fixes are separate, reviewed changes);
portal VoID/DCAT descriptions; `owl:sameAs`; graph
`https://lindas.admin.ch/territorial` (also has `ld.admin.ch/municipality/*`
triples but is not owned here).

## SHACL validation

`checks.py` runs pyshacl (`inference="none"`, `advanced=True`) over the output
using shapes copied from the legacy repo, 2-7 s per file on the live graph.
The build fails on any violation not in `shapes/known_violations.json`.

| Shape | Handling |
| --- | --- |
| `VersionLink.ttl` | Unchanged. One known violation: `district/111` has two `vl:version` and two names (quirk B2). |
| `Specialized.ttl`, `identities.ttl` | Unchanged; conform. |
| `versions.ttl` | Updated from the legacy copy, which was stale: `district/changeevent/157` became a real merger on 2026-01-01 (6 predecessors, successor `district/version/10321`, `validFrom` allowed). The closed-shape check stays; it is the only guard that no eCH-0071 register triples land on district event IRIs (quirk B1). |
| legacy `sameAs.ttl` | Not copied; nothing produces `owl:sameAs`, it always failed. |
| legacy smoke ASK (no duplicate municipality name) | Rewritten as a shape in `Smoke.ttl` so all checks run in one engine. |

`known_violations.json` is the baseline for migrations: a new source version may
remove the B2 violation or add new ones, and each change must be decided
consciously, never added to the baseline just to go green.

## Test strategy

- Unit tests on a hand-made v1.1 fixture covering: one canton; two districts
  (current and abolished, mode 29); municipality admission modes 20-24, 26, 27
  and unmapped 25; abolition modes 26/27/29; entry modes 11/12/13; a merger (2
  predecessors → 1 successor, exercises the `version-chain` cross product); a
  district and a municipality sharing a mutation number (B1); a district id with
  both a current and a mode-29 version (B2); a municipality abolished only with
  a non-29 mode (B3); two mode-29 versions with the same max abolition date (B4).
- The expected `.nt` is written by hand from the triple contract, not generated
  by the code under test. Keep it that way: a regenerated expectation proves
  nothing.
- **Parity gate** for any mapper change meant to be output-neutral:
  `main diff` against the live PROD graph must report 0 added / 0 removed. If
  not, fix the port unless the live graph provably differs from what the legacy
  code produces (then escalate). The legacy pipeline can be run locally on the
  same XML as tiebreaker (`npm run to-file` with CARML service, Jena and EYE).
- Tests must not need network, Node or Java.

## Rollout state (step 1)

TEST and INT publish. PROD is dry-run only (`PUBLISH_ENABLED: false`, no
credentials passed) because the legacy GitLab pipeline stays the PROD writer
until the v1.2.0 switch. Write access of the repo's GraphDB users to
`fso/register` was never confirmed; the reusable workflow takes credentials as
caller secrets, so dedicated `MUNICIPALITIES_GRAPHDB_*` secrets only change the
callers. TEST and INT currently share the secrets `GRAPHDB_USER` / `GRAPHDB_PASSWORD_INT`,
the same pairing the i14y TEST workflows use. The package reads them as the
environment variables `GRAPHDB_USER` / `GRAPHDB_PASSWORD`; the i14y exporters still
use the legacy `STARDOG_*` names.
