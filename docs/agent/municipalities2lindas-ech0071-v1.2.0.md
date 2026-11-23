# municipalities2lindas: moving to eCH-0071 v1.2.0 (step 2)

Step 1 reproduces the legacy output from the eCH-0071 **v1.1** file. Step 2
makes v1.2.0 the source and the new pipeline the PROD writer.

**Deadline:** v1.2.0 must be the source before the BFS release of 2027-01-01.
That zip may drop the `1.1` folder (the folder is named `1.1  (last update)`),
and the 2027 mutations must reach LINDAS. If `1.1` is still present, the
deadline is soft. A missing `1.1` folder fails the run with a message pointing
here (`source.select_member`).

The deadline is about the source version, not about which pipeline writes PROD.
The PROD cutover (checklist item 8) does not depend on `ECH0071_VERSION` and may
happen earlier on v1.1: step 1 output is triple-identical to legacy, so that
cutover is a no-op diff. Doing it first separates the writer switch from the
large v1.2.0 data change. Whatever the order, never run both writers, and the
legacy pipeline breaks the same way if BFS drops `1.1`.

## What is already in place

- `ECH0071_VERSION=1.2.0` is accepted (`config.ECH0071_NAMESPACES`), expecting
  namespace `http://www.ech.ch/xmlns/eCH-0071/2` (v1.1: `.../eCH-0071/1`).
- `source.select_member` takes the zip folder equal to the version or starting
  with `<version> ` (the v1.1 folder is literally `1.1  (last update)`, two
  spaces). Check the real v1.2.0 folder name in the zip before relying on it.
- `main diff` + safety check + `ALLOW_LARGE_CHANGE` exist for exactly this
  one-off large change. An empty live graph skips the safety check
  (`diff.decide`), so a fresh TEST import needs no override.

## What is not in place

No workflow sets `ECH0071_VERSION`; every run uses the `config.py` default
`1.1`. The switch is not done until the version is set, either as an `env`
entry in `municipalities_reusable_workflow.yml` (or a caller input) or by
changing the default.

## Known difference v1.1 → v1.2.0 (both files valid from 2026-01-01)

Measured on the 2026-01-01 files; re-measure on the file you actually use.

- v1.2.0 data starts in 1848 (v1.1: 1960).
- All existing canton, district-version and municipality-version ids are kept.
- 468 municipality versions are added (1848-1959).
- 3,145 municipality and 197 district admission dates change; 25 canton dates
  change.
- 337 municipality versions change admission number and mode. This **renames
  change-event IRIs**: the synthetic 1960 initial recordings
  `…/changeevent/{n}_{histId}` (admission mode 20) become real events
  `…/changeevent/{n}`. Consumers referencing those event IRIs are affected.

## Do not assume

- The v1.2.0 XML element names/structure equal v1.1. Diff the XSDs first and
  extend `source._records` / `mapper.py` only where they differ. The parser
  keeps every child as raw text keyed by tag, so new fields are carried but
  unmapped until the mapper uses them.
- Quirks B1-B8 still apply. They are legacy bugs kept for IRI/triple stability.
  v1.2.0 data may make some moot (e.g. B2 on `district/111`) or newly visible.
  Do not "fix" any of them in the same change as the version switch; each fix
  alters IRIs that consumers reference (see
  [municipalities2lindas-triple-contract.md](municipalities2lindas-triple-contract.md)).
- The geometry years are config, not derived from the data
  (`CANTON_GEOMETRY_YEAR` 2023, `MUNICIPALITY_GEOMETRY_YEAR` 2026, quirk B7).
  Decide them deliberately; changing them rewrites every `geo:hasGeometry` IRI.
- `MIN_COUNTS` in `source.py` (26 / 300 / 5000) were set for v1.1. With history
  from 1848 the real counts are higher; keep the bounds a plausibility floor,
  not a mirror of the data.

## Checklist

1. Obtain the v1.2.0 zip folder/XML and its XSD; diff against v1.1.
2. Add a v1.2.0 fixture (small, hand-made, same shape as the v1.1 sample) and a
   hand-written expected `.nt`; keep the v1.1 fixture and tests green so both
   versions stay supported.
3. Run `build` with `ECH0071_VERSION=1.2.0`, then `diff` against the live PROD
   graph. Read `municipalities_diff.json` (`removed_by_predicate`, examples)
   and classify every difference against the list above. Anything unexplained
   is a bug, not data.
4. Re-run SHACL. Decide each new violation consciously; update
   `shapes/known_violations.json` (with a reason) or fix the cause. If B2 goes
   away, remove its baseline entry. Revisit the closed shape in `versions.ttl`
   if event IRIs change.
5. Get sign-off from BFS and the consumers on the reviewed diff
   (ElCom, Zefix, SBB DiDok, BLV, BAKOM, BAFU, BFS territorial).
6. Set `ECH0071_VERSION=1.2.0` for the workflows (see "What is not in place").
   Without it the runs below still read v1.1.
7. TEST: fresh import into an empty graph; INT: dry run, then real run. Use
   `ALLOW_LARGE_CHANGE=true` for the one-off run only.
8. PROD cutover: set `PUBLISH_ENABLED: true` and pass credentials in
   `municipalities_graphdb_prod.yml`, remove the "excluded for PROD" condition
   in the `publish` job of `municipalities_reusable_workflow.yml`, confirm
   write access to `fso/register`, then have BAR switch the legacy GitLab
   pipeline off. Never run both writers.
9. Update `municipalities2lindas/README.md` (default version, rollout text) and
   propose the matching `CLAUDE.md` edit to a human.
