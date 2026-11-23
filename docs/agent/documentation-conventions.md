# Documentation Conventions

Where documentation goes in this repository, and how agent-facing instruction files are
written and maintained. Read it before creating a new documentation file, before adding
anything to a `CLAUDE.md`, or when deciding where a piece of knowledge belongs.

## The three layers

Documentation in this repo lives in exactly one of three places. Pick by asking two
questions: is this always true, and how detailed is it?

### 1. Root `CLAUDE.md` (always loaded)

Loaded into every session regardless of the task, so every line costs tokens on every
prompt. It is a map, not the territory.

Contains only:

- One or two sentences describing what this repository is.
- Tech stack: languages, frameworks, versions, database. Facts that cannot be guessed.
- The exact build, test, lint and run commands as actually invoked in this repo, not
  the conventional ones for the stack.
- The top level directory layout, three to six entries, one line each.
- Conventions that apply across the whole repo and that a linter cannot enforce.
- Boundaries: generated output, vendored code, legacy areas that must not be edited.
- Pointers to deeper documents, written conditionally (see "Writing pointers").

Does not contain: anything discoverable by reading a single file, gotcha lists,
area-specific rules, code snippets, task or migration status, or notes about how to
maintain this file.

Target: under 100 lines. Treat 200 as a hard ceiling that triggers a cleanup.

### 2. Nested `CLAUDE.md` (loaded by location)

A `CLAUDE.md` placed inside a directory is picked up automatically when work touches
files in that subtree. No pointer is needed for discovery. This is the preferred
mechanism for scoping in this monorepo, because the scope is enforced by location
rather than described in prose.

Use one per meaningful area, for example `municipalities2lindas/CLAUDE.md`,
`dataset2lindas/CLAUDE.md`.

Contains only conventions that are true inside that directory and are not already
stated at the root. Never restate root content. If a rule is true everywhere, it
belongs at the root; if it is true in two sibling directories, it probably belongs at
the root too.

Same length discipline as the root: orientation level, not reference level.

### 3. `docs/` (loaded on demand)

Depth lives here, split by audience:

- `docs/agent/` — reference material written for an agent: terse, rule-shaped, and reached
  by a conditional pointer from a `CLAUDE.md`. Architecture decisions, domain background,
  detailed reference, anything long.

These files are only read when a pointer sends an agent to them, so length is much less
costly, though still not free.

One topic per file. Name files after the topic, not after the layer. The `agent/`
directory is the one exception: it names the audience, because that boundary is what a
human browsing `docs/` needs to see.

## Writing pointers

A pointer is a single line in a `CLAUDE.md` that states a condition and a path. The
condition matters as much as the path, because it is what stops the file being read on
unrelated work.

    When working on the municipalities pipeline, read `docs/agent/municipalities2lindas-design.md`.

Rules for pointers:

- Always state when the document applies, not just that it exists.
- Put the pointer in the `CLAUDE.md` closest to the topic.
- A pointer is an instruction, not a mechanism. An agent usually follows it but may
  not. Anything genuinely non-negotiable stays inline in the `CLAUDE.md` itself rather
  than behind a pointer.
- One line per pointer. If a pointer needs a paragraph of explanation, the target
  document is probably badly scoped.

## Referring to code

Never paste code snippets into documentation. They go stale silently and there is no
signal when they do.

Never cite line numbers either. A line range looks precise and rots on the next
refactor, with no signal that it has. A stale line number is worse than no reference at all, because it
sends a reader somewhere wrong while reading as authoritative.

Refer to code by path and by the name of the thing.
A path and a symbol name both survive refactoring far better than a line number, and
when they do break, a reader can grep for the name. A reference says where to find more
detail — it is never a substitute for explaining the point. Anything a reader needs in
order to follow the document has to be in the document's own prose, understandable
without opening the code.

One exception: a single identifier or configuration value may be quoted inline — a
property key, a role name, a schema name, a task name. That is the fact being stated,
not an excerpt of code.

## Where a gotcha goes

Gotchas are the main source of bloat. Sort each one:

- It changed an agent's behaviour after a real mistake, and applies broadly: keep it in
  the relevant `CLAUDE.md`, phrased as a rule.
- It is about one specific file or function: it is a code comment next to that code,
  not documentation.
- It is background, historical, or occasionally useful: it goes in `docs/agent/`, reachable
  by a pointer.

If a gotcha does not fit any of these, it is probably not worth recording.

## Status versus decisions

Living status, what is done, what is next, what is blocked, goes stale within days and
should not sit in a markdown file that agents read. Keep it in the issue tracker.

Stable decisions, patterns, and rationale belong in `docs/agent/`. When a document mixes
the two, split it.

One thing that looks like status but is not: a subsystem that exists and runs but is
not production-ready — unlicensed, stubbed, or interim. That is a boundary, not a
progress report, and an agent that does not know it will present broken output as
finished. State it in one sentence where the subsystem is documented, saying what makes
it not ready, and delete the sentence when it stops being true.

## Maintaining these files

Agents must not edit any `CLAUDE.md` directly. Propose the change, with the reason, and
leave the edit to a human. These files are loaded into every future session, so a
change is closer to a code change than to a note.

One exception: when a document a `CLAUDE.md` points at is moved or renamed, an agent
updates the pointer path in the same commit as the move. That is mechanical rather than a
content change, and leaving it to a human guarantees a window where the pointer is broken.

The content here should be stable for weeks or months. Frequent edits are a signal that
task-specific detail is leaking in, not a sign of healthy upkeep.

Review roughly monthly, or whenever a file feels heavy. For each line, ask whether it
changed a decision recently. If not, delete it. Deleting is the normal outcome of a
review.

## Adding a new document

1. Check whether an existing file already covers the topic. Prefer extending it.
2. Decide the layer using the questions at the top of this file.
3. If it lands in `docs/agent/`, add a conditional pointer from the nearest `CLAUDE.md`.
4. Keep the document to one topic and state its scope in the first two lines.
5. Nothing to configure: everything under `docs/` is tracked. Working notes for a
   single change go in `docs/scratch/`, which is ignored.
