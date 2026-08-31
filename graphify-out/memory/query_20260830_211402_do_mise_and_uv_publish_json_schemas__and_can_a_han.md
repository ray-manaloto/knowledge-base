---
type: "query"
date: "2026-08-30T21:14:02.940966+00:00"
question: "Do mise and uv publish JSON Schemas, and can a hand-written parser be trusted without a control arm?"
contributor: "graphify"
outcome: "corrected"
correction: "The belief was that `mise` and `uv` publish no JSON Schema, so anything read\nfrom them would have to be hand-parsed. **Both publish one** —\n`mise.jdx.dev/schema/mise.json` (170,707 B, draft-2020-12) and\n`astral-sh/uv/uv.schema.json` (137,527 B). Ray caught the claim and said,\nverbatim: *\"dont make claims without cited evidence.\"*\n\nThe claim had been asserted from plausibility. It was never probed. And it was\nload-bearing: it was the stated reason a design could not generate its readers.\n\nTwo things make this worth recording beyond the fact itself.\n\n**First, the correction has its own boundary, and overclaiming the other way is\nthe same error.** Both schemas describe the tools' CONFIG, not their command\nOUTPUT — the string `outdated` appears **0 times in each**. So `mise outdated -J`\nand `uv tree --format json` still have no published schema. Being wrong once is\nnot a licence to swing; the second claim needed its own probe, and got one.\n\n**Second, the same session shows what the unprobed habit costs when it reaches\ncode.** Four throwaway parsers were hand-written instead of using the repo's own\ncode generator, and TWO returned false answers: a `mise.lock` parser returned\n`0 → 0` because it assumed section names that do not exist, and a `uv tree`\nparser reported **\"0 outdated\" when 23 packages were behind**, because it\nassumed a list where the real shape is a keyed dict. Both were plausible zeros.\nBoth were caught only because the result was surprising enough to control-arm —\nand one control arm was itself broken (both terms returned 0, proving nothing),\nwhich nearly let the wrong answer through a second time.\n\nThe generalisable rule: **a zero is the most dangerous result a probe can\nreturn**, because it looks like an answer and reads like diligence. It is not an\nanswer until a control arm on the same probe has produced a NON-zero. And a\nparser written to read a shape you have not looked at is a probe with no control\narm at all — which is why the repo's standing directive is that the code\ngenerator owns every model type, and why hand-writing one is not a shortcut but\na wager.\n"
---

# Q: Do mise and uv publish JSON Schemas, and can a hand-written parser be trusted without a control arm?

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
different file.** ~~Nothing reads `mise.lock` at all.~~ **CORRECTED 2026-08-30
(cold review, re-derived): FALSE — `kb_setup.tool_sync._lock_converged` reads and
parses `mise.lock` at `tool_sync.py:287`, wired via `mise.toml:1157-1159`. What is
true is narrower: it compares VERSION STRINGS only, not checksums or per-platform
urls, so lock drift below the version level is still unchecked.** What is missing is not
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

Exactly **one of ~~75~~ 85 mise tasks names an LLM backend**, and it is not in this
pipeline. (**Count corrected 2026-08-30**: `grep -c '^\[tasks\.' mise.toml` → **85**.
The ratio claim is unaffected; only the denominator was stale.) Clone, AST extraction, cluster, label, derived views and
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

> **FLAGGED 2026-08-30 (cold review), unresolved and deliberately left so.** This
> paragraph sits against the directive quoted above it — *"Generate, never
> hand-write"*, and Ray's standing call that **the code generator owns every model
> type**. The two are reconcilable only if "generate" is read as scoped to types
> that HAVE a source schema, which is a reading nobody has confirmed. It is a real
> open question for the spec, not an editing slip, so it is annotated rather than
> silently rewritten in either direction. **Resolve it before any implementer lane
> is handed a spec that hand-authors a struct.**


## Outcome

- Signal: corrected
- Correction: The belief was that `mise` and `uv` publish no JSON Schema, so anything read
from them would have to be hand-parsed. **Both publish one** —
`mise.jdx.dev/schema/mise.json` (170,707 B, draft-2020-12) and
`astral-sh/uv/uv.schema.json` (137,527 B). Ray caught the claim and said,
verbatim: *"dont make claims without cited evidence."*

The claim had been asserted from plausibility. It was never probed. And it was
load-bearing: it was the stated reason a design could not generate its readers.

Two things make this worth recording beyond the fact itself.

**First, the correction has its own boundary, and overclaiming the other way is
the same error.** Both schemas describe the tools' CONFIG, not their command
OUTPUT — the string `outdated` appears **0 times in each**. So `mise outdated -J`
and `uv tree --format json` still have no published schema. Being wrong once is
not a licence to swing; the second claim needed its own probe, and got one.

**Second, the same session shows what the unprobed habit costs when it reaches
code.** Four throwaway parsers were hand-written instead of using the repo's own
code generator, and TWO returned false answers: a `mise.lock` parser returned
`0 → 0` because it assumed section names that do not exist, and a `uv tree`
parser reported **"0 outdated" when 23 packages were behind**, because it
assumed a list where the real shape is a keyed dict. Both were plausible zeros.
Both were caught only because the result was surprising enough to control-arm —
and one control arm was itself broken (both terms returned 0, proving nothing),
which nearly let the wrong answer through a second time.

The generalisable rule: **a zero is the most dangerous result a probe can
return**, because it looks like an answer and reads like diligence. It is not an
answer until a control arm on the same probe has produced a NON-zero. And a
parser written to read a shape you have not looked at is a probe with no control
arm at all — which is why the repo's standing directive is that the code
generator owns every model type, and why hand-writing one is not a shortcut but
a wager.
