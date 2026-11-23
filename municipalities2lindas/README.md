# Swiss municipalities to LINDAS

`municipalities2lindas` publishes the BFS historicised municipality register (eCH-0071 XML) to:

`https://lindas.admin.ch/fso/register`

It is a Python port of the legacy GitLab `main-graphdb` pipeline (CARML + SPARQL CONSTRUCTs + N3 rules) and produces the same triples. Against the live PROD graph the output is identical: 347070 generated = 347070 live, 0 added, 0 removed.

## Source to graph

1. Download the zip (`MUNICIPALITIES_SOURCE_URL`) and select the eCH-0071 member of the configured version. A non-zip download, a missing version folder or a wrong namespace fails the run before any LINDAS call.
2. Parse cantons, districts and municipalities, keeping every value as raw XML text.
3. Build the triples, serialise sorted N-Triples (`municipalities.nt`) and validate them with pyshacl against the legacy shapes in `shapes/`. Only the baseline in `shapes/known_violations.json` is tolerated (`https://ld.admin.ch/district/111`, legacy quirk B2).
4. Diff against the live graph. Identical: skip. Otherwise, after the safety check, replace the whole graph and verify the triple count. An empty live graph is an initial import and bypasses the safety check. The diff treats an `xsd:string` literal as equal to the plain literal (RDF 1.1).

## RDF model

Resources live under `https://ld.admin.ch/` (cantons, districts, municipalities, their versions, change events and identities). The complete triple contract and the legacy quirks kept on purpose for parity (B1-B8) are in [docs/agent/municipalities2lindas-triple-contract.md](../docs/agent/municipalities2lindas-triple-contract.md); design rationale is in [docs/agent/municipalities2lindas-design.md](../docs/agent/municipalities2lindas-design.md). Quirks in the code are marked `# legacy-parity: B<n>`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `MUNICIPALITIES_SOURCE_URL` | `https://www.agvchapp.bfs.admin.ch/file/xml/dz-b-00.04-hgv-02.zip` | Source zip. |
| `ECH0071_VERSION` | `1.1` | `1.1` expects namespace `http://www.ech.ch/xmlns/eCH-0071/1`; `1.2.0` expects `.../eCH-0071/2`. |
| `CANTON_GEOMETRY_YEAR` | `2023` | Year in canton geometry IRIs. |
| `MUNICIPALITY_GEOMETRY_YEAR` | `2026` | Year in municipality geometry IRIs. |
| `TARGET_GRAPH` | `https://lindas.admin.ch/fso/register` | Graph that is replaced. |
| `LINDAS_QUERY_URL` | `https://lindas.admin.ch/query` | SPARQL endpoint for the diff. |
| `LINDAS_UPDATE_URL` | empty | GraphDB statements endpoint (the URL must contain `graphdb`); needed only to publish. |
| `GRAPHDB_USER` / `GRAPHDB_PASSWORD` | unset | Credentials, needed only to publish. |
| `MAX_REMOVED_RATIO` | `0.05` | Share of live triples a run may remove before it aborts. |
| `ALLOW_LARGE_CHANGE` | `false` | Overrides the safety check. |
| `DEBUG_LOCAL_TEST` | `false` | Disables TLS verification, for local or proxy setups. |

### Schedule

The workflows fire daily at 04:00 UTC (`0 4 * * *`); a gate job decides whether the scheduled run proceeds. The repository variables `MUNICIPALITIES_SCHEDULE_TEST`, `MUNICIPALITIES_SCHEDULE_INT` and `MUNICIPALITIES_SCHEDULE_PROD` hold the date-field expression `<day-of-month> <month> <day-of-week>`:

| Value | Runs |
| --- | --- |
| unset | `2 * *`, the 2nd of each month |
| `2 * *` | 2nd of each month |
| `1,15 * *` | 1st and 15th |
| `* * 1` | every Monday |
| `off` | scheduled runs never proceed; manual runs still do |

If both day-of-month and day-of-week are restricted, a day matching either runs, as in standard cron. Ranges and steps (`1-7`, `*/2`) work as in cron. Manual (`workflow_dispatch`) runs always proceed. An invalid expression fails the gate job; it does not silently skip. Test an expression with `python -m municipalities2lindas.src.schedule --expression "1,15 * *" --date 2026-12-15`.

## Local usage

```bash
python -m pip install -r requirements.txt

python -m municipalities2lindas.src.main build --download-dir /tmp/m2l \
  --output /tmp/m2l/municipalities.nt --source-info /tmp/m2l/source_info.json \
  --shacl-report /tmp/m2l/shacl_report.ttl
LINDAS_QUERY_URL=https://lindas.admin.ch/query python -m municipalities2lindas.src.main diff \
  --input /tmp/m2l/municipalities.nt --source-info /tmp/m2l/source_info.json \
  --report /tmp/m2l/municipalities_diff.json
```

Run from the repo root. Without the path flags, `build` writes `municipalities.nt`, `source_info.json` and `shacl_report.ttl` (and `--download-dir` defaults to `.`, so `source.zip` too) to the current directory, and `diff` reads and writes there. `--shapes-dir` overrides `shapes/`.

`build --source-file <zip-or-xml>` uses a local zip or a bare eCH-0071 `.xml` instead of downloading. `build --skip-count-check` disables the `MIN_COUNTS` plausibility floor in `source.py`, for small fixtures only.

Neither command writes to LINDAS. Publishing is `python -m municipalities2lindas.src.lindas municipalities.nt`, which the publish job runs (needs `LINDAS_UPDATE_URL` and credentials).

Tests (from the repo root):

```bash
python -m unittest municipalities2lindas.tests.test_config municipalities2lindas.tests.test_source municipalities2lindas.tests.test_mapper municipalities2lindas.tests.test_serializer municipalities2lindas.tests.test_lindas municipalities2lindas.tests.test_diff municipalities2lindas.tests.test_checks municipalities2lindas.tests.test_schedule
```

## GitHub Actions

`municipalities_reusable_workflow.yml` is called by `municipalities_graphdb_{test,int,prod}.yml`. Jobs:

1. `schedule-gate`: applies the schedule above. When it says no, every later job is skipped.
2. `build`: download, map, SHACL check, validate the N-Triples with `rapper`, archive.
3. `diff`: compare with the live graph and decide `skip`, `upload` or `abort`. It warns (`::warning::`) when the result is `upload` but publishing is disabled, so a PROD run with pending changes always shows the warning.
4. `publish`: replace the graph and verify the count. Runs only when the diff says `upload`, `PUBLISH_ENABLED` is true, `DRY_RUN` is false and the environment is not `PROD`.

Each caller sets the environment's update and query URLs, the schedule variable and `PUBLISH_ENABLED`; the reusable workflow's target graph is fixed to `https://lindas.admin.ch/fso/register`.

Jobs share data only through artifacts, so `publish` uploads exactly the file that `diff` compared. `municipalities-<run_id>` holds `municipalities.nt`, `source_info.json`, `shacl_report.ttl` and the source zip, and is kept even when `build` fails. `municipalities-diff-<run_id>` holds `municipalities_diff.json`.

PROD receives no credentials in step 1: its caller passes no secrets, `PUBLISH_ENABLED` is false, and the publish job is additionally excluded for `PROD`. TEST and INT both use the `GRAPHDB_USER` / `GRAPHDB_PASSWORD_INT` secrets (exposed to the job as `GRAPHDB_USER` / `GRAPHDB_PASSWORD`), as the i14y TEST workflows do. Each environment has its own concurrency group with no cancellation, so a run queues behind a running one and graph writes never overlap. Manual runs accept `DRY_RUN` and `ALLOW_LARGE_CHANGE`.

`ECH0071_VERSION` and the geometry years are not set in any workflow, so the `config.py` defaults apply.

**Step 1 rollout.** TEST and INT publish. PROD is dry-run only (`PUBLISH_ENABLED: false`): it builds and diffs, and never writes. The legacy GitLab pipeline remains the PROD writer until step 2 (eCH-0071 v1.2.0, see docs/agent/municipalities2lindas-ech0071-v1.2.0.md), which must ship before the BFS 2027-01-01 release.

## Operations

All checks (build, SHACL, diff) run before the single graph replacement (one PUT).

- **SHACL unexpected violation.** The build fails with a violation that is not in `shapes/known_violations.json`. Read `shacl_report.ttl` from the build artifact. A new violation means the source data or the mapper changed; fix the cause. Add a baseline entry only for a documented legacy quirk, with a reason.
- **Safety-check abort.** The diff would remove more than `MAX_REMOVED_RATIO` of the live triples. Inspect `municipalities_diff.json` (`removed_by_predicate`, examples). Re-run manually with `ALLOW_LARGE_CHANGE=true` only when the change is expected, such as the one-off step 2 switch, and reviewed.
- **Stale-source warning.** `eCH-0071 source validFrom ... is older than 13 months` means BFS has not published a newer file as expected. Step 2 (v1.2.0) is due; check the BFS release.
- **Count mismatch after publish.** The count check retries because the query endpoint lags behind the update. If it still fails, compare the live count with `generated_count` in the diff report and re-run the whole workflow, not the failed job (re-running `publish` alone reuses an old artifact and decision). A re-run republishes only when the diff is non-empty; otherwise it ends in `skip`, which is also correct after a false mismatch.
