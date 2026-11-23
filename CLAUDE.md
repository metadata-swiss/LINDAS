# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Synchronizes public [i14y](https://www.i14y.admin.ch/) metadata (graph `https://lindas.admin.ch/fso/i14y`) and the BFS historicised municipality list (graph `https://lindas.admin.ch/fso/register`) to the LINDAS triple store, as three independent Python packages run by GitHub Actions. Python 3.10 in CI; dependencies in `requirements.txt` (`pyshacl` pinned). Each package has its own README with the detailed RDF model and config variables; read it before changing behavior.

## Layout

- `concept2sharedDimension/` — i14y CodeList concepts → LINDAS (`src/main.py`, `src/versioning/{config,core,processor,utils}.py`).
- `dataset2lindas/` — i14y DCAT datasets (+ SHACL structures) → LINDAS (`src/{api,config,mapper,synchronizer,turtle_writer,main}.py`).
- `municipalities2lindas/` — BFS eCH-0071 municipality list → `fso/register`, full replace (`src/`, `shapes/`, `tests/`).
- `.github/workflows/` — reusable and per-environment (TEST/INT/PROD) sync workflows. `prod_*` workflows (no `graphdb` in the name) target the legacy Stardog PROD.
- `docs/agent/` — agent reference docs (conventions, municipalities design and contract).
- `CPSV_mapping/`, `DCAT_mapping/` — legacy standalone scripts, not part of the automated sync.

## Commands

```bash
python -m pip install -r requirements.txt

# Tests (unittest, no pytest; run from repo root). tests/ dirs have no __init__.py,
# so `discover -t .` fails — name modules instead:
python -m unittest dataset2lindas.tests.test_api dataset2lindas.tests.test_mapper dataset2lindas.tests.test_synchronizer
python -m unittest concept2sharedDimension.tests.test_catalog_metadata concept2sharedDimension.tests.test_vocabulary_protection
python -m unittest municipalities2lindas.tests.test_config municipalities2lindas.tests.test_source municipalities2lindas.tests.test_mapper municipalities2lindas.tests.test_serializer municipalities2lindas.tests.test_lindas municipalities2lindas.tests.test_diff municipalities2lindas.tests.test_checks municipalities2lindas.tests.test_schedule
python -m unittest dataset2lindas.tests.test_synchronizer.<TestClass>.<test_name>   # single test

# Generate a Turtle batch locally (uploads nothing; keep LINDAS_UPDATE_URL unset — with it set, a concept batch deletes changed concepts from LINDAS)
BATCH_CONCEPT_IDS=<concept-uuid> python -m concept2sharedDimension.src.main --batch-index 0   # -> batch_0_output.ttl
python -m dataset2lindas.src.main --dataset-ids <dataset-uuid> --batch-index 0                # -> batch_0_datasets.ttl
```

Uploading/deleting requires `LINDAS_UPDATE_URL` (plus `STARDOG_USER`/`STARDOG_PASSWORD` for protected environments). Turtle is validated in CI with `rapper`.

## Architecture (big picture)

Both i14y exporters share one **frozen-manifest incremental model**, orchestrated by the reusable workflows `.github/workflows/reusable_workflow.yml` (concepts) and `dataset_reusable_workflow.yml` (datasets), called by thin per-environment (TEST/INT/PROD) caller workflows:

1. Scan the full i14y inventory once and persist it as a run-specific manifest (`*_source_manifest.json`) plus a sync plan. Every later step (batches, deletions, metrics) reloads the manifest, so i14y changes mid-run can't cause inconsistency.
2. Compare with LINDAS (via SPARQL) to decide per identifier: export, delete, or skip. Changed = absent, version set differs, or `system.modifiedAt` within `I14Y_MODIFIED_LOOKBACK_HOURS` (24h; 96h on Monday); missing/invalid `modifiedAt` → re-export (datasets) or deep compare (concepts).
3. Build Turtle in parallel batch jobs, validate, then upload **sequentially**. LINDAS updates must not overlap, but only the TEST i14y workflows and the municipalities workflows have concurrency groups; the INT and PROD i14y callers rely on cron spacing.
4. Delete orphans, upload that exporter's portal VoID/DCAT description (`i14y-concepts` or `i14y-datasets`), then verify source vs LINDAS metrics — any mismatch fails the run.

Key design points that span files:
- **Deterministic IRIs**: datasets/concepts live under `https://register.ld.admin.ch/i14y/{dataset|concept}/{id}`; blank nodes are skolemized under `.../.well-known/genid/` so deletion by URI prefix/closure is reliable.
- **Dataset identity** is the first entry of `identifiers`, not the i14y UUID; missing or duplicate primary identifiers abort the run.
- **Shared publisher agents** (`.../i14y/agent/{id}`) are used by both concepts and datasets and are deleted only when no concept or dataset still references them.
- **Replace = delete then re-export**; deletion must not remove externally owned resources (themes, standards, shared structure parts indexed via `dct:hasPart`). Dataset-structure `dct:conformsTo` links to concepts are intentionally preserved on concept deletion.
- Datasets: `404` on the structure TTL endpoint means "no structure"; any other failure aborts the batch. `dcat:accessService` is emitted only for public i14y data services, and no DataService triples are generated. The dataset catalog is opt-in (`CREATE_DATASET_CATALOG`).
- Turtle is streamed per dataset (`DatasetStreamingTurtleWriter`) — never hold the full batch graph in memory.
- TEST has extra full-lifecycle workflows (clear → import all → delete all → assert empty graph) that share a concurrency group with the TEST incremental workflow.

`municipalities2lindas` does not use that model. Per run (`municipalities_reusable_workflow.yml`, TEST/INT/PROD callers): a schedule gate (repo variables `MUNICIPALITIES_SCHEDULE_<ENV>`) → build from the BFS zip + SHACL check against `shapes/` and `known_violations.json` → diff against the live graph, aborting if more than `MAX_REMOVED_RATIO` would be removed → one atomic GraphDB `PUT` of the whole `fso/register` graph, then a count check. Output must stay triple-identical to the legacy pipeline (quirks B1-B6 are marked `# legacy-parity: B<n>`; see the spec in `docs/agent/municipalities2lindas-triple-contract.md`). In step 1, PROD is dry-run only and gets no credentials.

`SPARQL_EXAMPLES.md` and `stardog_queries_examples.ipynb` hold queries for inspecting the graph.

## Conventions

- **Comments earn their place.** Be sparing and deliberate. Explain intent and non-obvious reasoning only, never restate the code, and keep them short enough that a human reviewer can skim past them. A long comment is usually reference material in the wrong place — put that in `docs/agent/` and leave a one-line pointer to it. Prefer a clearer name or a smaller method over a paragraph explaining a murky one.
- **Commits.** Conventional Commits with the Jira ticket as the scope:
  `<type>(<TICKET>): <subject>`. The body gives the what and the why, wrapped at ~80 columns. Tooling, dependency and codegen work is `build`, not `feat`.
- **Branches.** `<type>/<TICKET>-<short-kebab-description>`.
- **Agents must not edit any `CLAUDE.md`.** Propose the change with its reason and leave the edit to a human.
- **RDF files and `.gitignore`.** The root `.gitignore` ignores `*.ttl` and `*.nt` (generated outputs). Any RDF file that must be committed (shapes, test fixtures) needs a `!` exception, e.g. `!municipalities2lindas/shapes/*.ttl`. Check with `git check-ignore -v <file>` — an ignored shape or fixture silently disappears in CI.
- **Superpowers docs.** Specs and plans generated by the superpowers skills (docs/superpowers/) are working files and must not be committed. Anything a future change needs goes in docs/agent/.

## Pointers

- Before creating a documentation file or adding to a `CLAUDE.md`, read `docs/agent/documentation-conventions.md`.
- When working on the municipalities pipeline, read `docs/agent/municipalities2lindas-design.md`.
- When switching the municipalities source to eCH-0071 v1.2.0, read `docs/agent/municipalities2lindas-ech0071-v1.2.0.md`.
- When changing CANTON_GEOMETRY_YEAR or MUNICIPALITY_GEOMETRY_YEAR, read `docs/agent/municipalities2lindas-geometry-years.md`.
- When changing how a package decides to write to LINDAS, or before running an exporter against a real endpoint, read `docs/agent/lindas-update-url.md`.
