# LINDAS_UPDATE_URL

What `LINDAS_UPDATE_URL` controls, why it has no default, and who sets it where. Read it
before changing how a package decides whether to write to a triple store, or before
running an exporter against a real endpoint.

## What it is

The endpoint the exporters write to: uploads, deletions and graph replacement. It is the
only switch between "build Turtle" and "modify a live store". Reading is separate and uses
`LINDAS_QUERY_URL`, which defaults to TEST, so a local run can compare against LINDAS
without being able to change it.

## Why it is empty by default

- No environment is a safe default. TEST is shared, and PROD must never be hit by accident.
- Generation and writing are deliberately separate. With the variable unset, the exporters
  only produce files and write nothing to the store.
- A missing value fails loudly rather than guessing. The dataset and municipalities
  packages raise an error when asked to write without it. Municipalities additionally
  requires a GraphDB statements endpoint (the URL must contain `graphdb`).
- Concepts are the trap. `LindasAPIHelper` reads the variable straight from the
  environment, and a concept run with `CLEAR_GRAPH` unset deletes changed concepts from
  LINDAS before regenerating them whenever the variable is set. Unset is what makes a local
  concept run side-effect-free.

## Who sets it, where and when

CI sets it; people normally do not. Each per-environment caller workflow in
`.github/workflows/` passes a hardcoded value as the `LINDAS_UPDATE_URL` input of the
matching reusable workflow (`reusable_workflow.yml`, `dataset_reusable_workflow.yml`,
`municipalities_reusable_workflow.yml`), which exports it as a job-level environment
variable. The URL is not a secret, so it is committed.

| Environment | Value |
|---|---|
| TEST | `https://test.graphdb.lindas.admin.ch/repositories/lindas/statements` |
| INT | `https://int.graphdb.lindas.admin.ch/repositories/lindas/statements` |
| PROD (GraphDB) | `https://graphdb.lindas.admin.ch/repositories/lindas/statements` |
| PROD (legacy Stardog, `prod_*` workflows) | `https://stardog.cluster.ldbar.ch/lindas` |

It is in effect on every scheduled run and on every `workflow_dispatch` run, including the
manual-clear and TEST full-lifecycle workflows.

Credentials are separate. The i14y exporters read `STARDOG_USER` and `STARDOG_PASSWORD`
(a legacy name, kept until their cleanup), passed in the caller's `secrets:` block.
Municipalities reads `GRAPHDB_USER` and `GRAPHDB_PASSWORD` instead. TEST reuses the INT
GraphDB credentials. Municipalities PROD sets the URL but disables publishing and passes
no credentials, so it is dry-run only.

## Local use

Leave it unset. If a local run must write, point it at TEST, never PROD, and set
`CLEAR_GRAPH` deliberately for concepts. Local generation commands are in the root
`CLAUDE.md`.
