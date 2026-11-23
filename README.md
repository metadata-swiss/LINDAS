# I14Y to LINDAS

This repository synchronizes public [i14y](https://www.i14y.admin.ch/) metadata to the LINDAS graph `https://lindas.admin.ch/fso/i14y`, and Swiss municipality data to `https://lindas.admin.ch/fso/register`.

The maintained exporters are independent Python packages:

- `concept2sharedDimension`: public i14y `CodeList` concepts to LINDAS.
- `dataset2lindas`: public i14y DCAT datasets to LINDAS.
- `municipalities2lindas`: BFS eCH-0071 municipality register to the graph `https://lindas.admin.ch/fso/register`; see [municipalities2lindas/README.md](municipalities2lindas/README.md).

`CPSV_mapping` and `DCAT_mapping` are legacy, standalone mappings and are not part of the automated synchronization.

## Synchronization model

The two i14y exporters follow the same safe incremental model (`municipalities2lindas` instead replaces its whole graph in one transaction behind a diff check):

1. Scan the complete i14y source inventory.
2. Persist that inventory as a run-specific manifest before creating batches.
3. Build and validate Turtle files locally in the workflow.
4. Upload batches sequentially to LINDAS.
5. Delete resources no longer present in the frozen source inventory.
6. Check source/LINDAS metrics after publication and fail the workflow if they differ.

The manifest means that every batch, reconciliation step and final metric uses the same source snapshot, even if i14y changes while the workflow is running.

## Concepts

`concept2sharedDimension` exports public `CodeList` versions for the configured registration statuses. A CodeList for which every selected version has no entries is excluded. Concepts are incrementally re-imported when their version inventory differs from LINDAS, when `system.modifiedAt` is recent, or when a conservative deep comparison detects a drift.

Concept resources use the following URI family:

```text
https://register.ld.admin.ch/i14y/concept/{identifier}
https://register.ld.admin.ch/i14y/concept/{identifier}/version/{version}
```

The exporter produces the CodeList hierarchy, deterministic skolem IRIs for internal nodes and shared publisher agents below:

```text
https://register.ld.admin.ch/i14y/agent/{publisher-identifier}
```

The daily workflow compares the number of exported concept _versions_ per registration status between i14y and LINDAS.

See [concept2sharedDimension/README.md](concept2sharedDimension/README.md) for details.

## Datasets

`dataset2lindas` scans every page of `GET /api/datasets`, obtains details from `GET /api/datasets/{datasetId}` and exports new or changed datasets. The change window is controlled by `I14Y_MODIFIED_LOOKBACK_HOURS` (24 hours by default, 96 hours on Monday).

Dataset URIs are:

```text
https://register.ld.admin.ch/i14y/dataset/{identifier}
```

For each dataset, the exporter also requests `GET /api/datasets/{datasetId}/structures/exports/TTL`. A `404` simply means that no structure exists. Structures are linked through `dct:conformsTo`, indexed with `dct:hasPart`, and their internal blank nodes are deterministically skolemized under the dataset URI. This permits reliable deletion of a dataset and its owned structure graph.

No `dcat:Catalog` is created by default. `CREATE_DATASET_CATALOG=true` is an independent opt-in switch that creates or updates `https://register.ld.admin.ch/i14y/catalog/datasets`; it is unrelated to `CLEAR_GRAPH`.

The daily workflow verifies both the dataset count and the number of datasets with a structure.

See [dataset2lindas/README.md](dataset2lindas/README.md) for configuration and local batch usage.

## GitHub Actions

The reusable workflows are:

- `.github/workflows/reusable_workflow.yml` for concepts.
- `.github/workflows/dataset_reusable_workflow.yml` for datasets.
- `.github/workflows/municipalities_reusable_workflow.yml` for municipalities (see its README).

Caller workflows target GraphDB TEST, INT and PROD; `prod_incremental_update.yml` and `prod_manual_clear.yml` target the legacy Stardog PROD for concepts. They validate RDF with `rapper` and keep artifacts only for generated batches or failures. LINDAS update requests must not overlap, but only the TEST i14y callers and the municipalities callers have concurrency groups; the INT and PROD i14y callers rely on their cron spacing.

After each run, each i14y reusable workflow also uploads its own stable VoID/DCAT dataset description for the LINDAS portal: `i14y-concepts` from the concept workflow, `i14y-datasets` from the dataset workflow.

Two additional TEST-only lifecycle workflows clear the graph, import the complete inventory, delete every imported resource and verify that the graph is empty. If triples remain, they export the remaining graph as an artifact for diagnosis.

## SPARQL examples

Ready-to-run queries for inspecting the concepts and datasets in LINDAS are available in [SPARQL_EXAMPLES.md](SPARQL_EXAMPLES.md).

## Local usage

Install the dependencies once:

```bash
python -m pip install -r requirements.txt
```

Generate a concept batch:

```bash
BATCH_CONCEPT_IDS=<i14y-concept-id> python -m concept2sharedDimension.src.main --batch-index 0
```

Generate a dataset batch:

```bash
python -m dataset2lindas.src.main --dataset-ids <i14y-dataset-id> --batch-index 0
```

Generation does not upload Turtle. Uploading or deleting resources requires `LINDAS_UPDATE_URL` and, for protected environments, `STARDOG_USER` and `STARDOG_PASSWORD`. Leave `LINDAS_UPDATE_URL` unset locally: with it set, a concept batch deletes changed concepts from LINDAS before regenerating them (see the concept README). The target graph defaults to `https://lindas.admin.ch/fso/i14y`.

`stardog_queries_examples.ipynb` contains HTTP/SPARQL examples for inspecting the graph.
