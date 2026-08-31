---
type: "query"
date: "2026-08-30T21:14:02.593420+00:00"
question: "What does the dependency-upgrade protocol need to be, and where does agent-token work actually enter it?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does the dependency-upgrade protocol need to be, and where does agent-token work actually enter it?

## Answer

# The dependency-upgrade protocol: what three grilling rounds settled

Session `kb-20260830.001`, 2026-08-30. Full record: issue #638.

## The reframe that matters

Upgrading a dependency is a ~13-stage pipeline, and **11 of 13 stages are
already machine work with a command that exists**. The gap is not capability —
nothing SEQUENCES them, so an agent is the sequencer, and an agent forgets a
stage. Today's proof: a bump moved the pin, the manifests and the installed
binary, and went 7/7 green over a `mise.lock` still holding old checksums.

The deeper diagnosis: **each stage has a checker, and each checker reads a
different file.** Nothing reads `mise.lock` at all. What is missing is not
another checker but ONE OBJECT that knows a dependency has a set of artifacts
which must all agree. Every previous fix added a checker to the pile.

## Settled by Ray

- Durable execution: **DBOS on SQLite** (verified: its sqlite/tursodb PR is
  merged, `sqlite` is in core source not just tests).
- Upgrade **blindly**; gates catch failures; on red, **auto-revert that one
  dependency and continue the batch**.
- **One dependency = one commit; the batch = one PR.**
- Scope: mise `[tools]` + pyproject first-level ONLY. Rule for transitives:
  *"if we want a transitive dependency to be a currency, then just make it a
  first level dependency."*
- **Generate, never hand-write.**
- **Reduce the number of config files.** Mandatory: `mise.toml`,
  `pyproject.toml`. Everything else is a deletion candidate.
- The primitive: one table mapping **dependency → the sources it syncs to →
  per-stage status** (outdated / sources synced / deep extraction / reflection /
  artifacts). `currency.toml` becomes a generated projection of it.
- MVP: **full upgrade automation with the ability to skip agent tokens.**

## The token answer, which is the constraint that dominates

Exactly **one of 75 mise tasks names an LLM backend**, and it is not in this
pipeline. Clone, AST extraction, cluster, label, derived views and
`graphify reflect` are all deterministic. **So a full zero-token upgrade of
every dependency is achievable today** — skip semantic extraction and record
`skipped_tokens` rather than blocking. Zero-token is the DEFAULT PATH, not a
mode; agent work is opt-in per flag and resumable from the status record.

## The advisor's correction to Ray's own answers

Rewriting `currency.toml` contradicts DB-as-truth plus fewer-config-files: a
rewritten file is a THIRD copy of the same facts. **Delete it, do not rewrite
it** — its judgment becomes DB columns, and a read-only export can regenerate a
TOML view. On DBOS: over-specified for ~130 rows, but cheap to hold wrong if
every step is a plain function DBOS merely decorates.

And: do NOT codegen models from the published 170KB/137KB vendor schemas —
hundreds of types to read `[tools]`. Use them for VALIDATION; author two small
structs for the command outputs, which have no published schema.


## Outcome

- Signal: useful