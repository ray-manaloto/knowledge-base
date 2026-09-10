# Advisor verdict — making `kb-codex --review --model <X>` verifiable

**Lane:** kb-codex-astra-advisor (Claude-side grounding + `gpt-6-astra` consult).
**Status:** IN PROGRESS — written incrementally as facts are established.
**Date:** 2026-09-10.

## Established facts (each with its probe)

_(appended below as they land)_
### F1 — `review_model` IS the only channel, and it IS read (source, 0.154.0)

Pinned clone verified at the manifest commit:
`sources/codex/` HEAD = `6b9826e3aa83b1a5947db50f4332cb9c65f1b340` = `rust-v0.154.0`,
matching `sources/codex.manifest` and the installed `codex-cli 0.154.0`.

`sources/codex/codex-rs/core/src/tasks/review.rs:123-127`:

```rust
let model = config
    .review_model
    .clone()
    .unwrap_or_else(|| ctx.model_info().slug.clone());
sub_agent_config.model = Some(model);
```

Resolution order upstream of that: `config/mod.rs:3966`
`let review_model = override_review_model.or(cfg.review_model);` — the CLI
override wins over the TOML value; `override_review_model` is destructured from
`ConfigOverrides` at `config/mod.rs:3240`. Field declared `config/mod.rs:625`.

Upstream's OWN control arms exist and are the strongest cheap evidence the
mechanism is live:
- `core/tests/suite/review.rs:937` `review_uses_custom_review_model_from_config`
- `core/tests/suite/review.rs:1018` `review_uses_session_model_when_review_model_unset`

### F2 — the candidate OBSERVABLE: `TurnContextItem.model`

`sources/codex/codex-rs/protocol/src/protocol.rs:3202-3255` defines
`TurnContextItem`, persisted (doc comment at `:3197-3201`) "once per real user
turn". Two fields decide this consult:

- `:3232` `pub model: String` — **non-optional**, so it is always written.
- `:3206-3208` `pub root_turn_id: Option<String>` — "Root turn that owns this
  subagent turn's attribution. **Only set for subagent turns**".

If review sub-agent turns are persisted with their own `TurnContextItem`, the
rollout file names the reviewer model directly, and `root_turn_id` is the flag
that distinguishes the sub-agent turn from the parent session turn.

`core/src/session/mod.rs:4353` carries the persist comment.

### F3 — 🔴 THE OBSERVABLE EXISTS, AND TODAY'S RUN IS ALREADY RECORDED

The review sub-agent gets **its own rollout file** under
`~/.codex/sessions/<Y>/<M>/<D>/`, whose `session_meta.source` is the JSON object
`{"subagent": "review"}` — not the string `"exec"` a normal lane writes.

For the exact run the team lead flagged (base `6b3ab427…`, `--model gpt-5.6-sol`):

```
rollout-2026-09-10T13-16-15-01a08c88-d548-7c03-827a-6927049aa77d.jsonl
  session_meta.source     = {'subagent': 'review'}
  session_meta.cli_version= 0.154.0
  turn_context.model      = 'gpt-5.6-sol'      <-- the model that was REQUESTED
  turn_context.effort     = 'xhigh'
  turn_context.root_turn_id = '01a08c88-ca77-7ac2-8361-d2c549dec59d'
```

Its parent is `rollout-2026-09-10T13-16-09-01a08c88-c768-…jsonl`
(`session_meta.source = 'exec'`), started 6 seconds earlier.

**So the review DID run on `gpt-5.6-sol`.** The banner said `gpt-6-astra` and was
wrong; the selection path was live the whole time. The defect is that the ONLY
observable a reader was looking at is the one that cannot answer the question —
not that the model was substituted.

### F4 — the JOIN KEY is already in the artifact `kb-codex` tees

The banner of today's review output (`.agent/kb/review/reports/review-7b28f460…-cold.md`,
lines 1-10) prints:

```
model:      gpt-6-astra          <-- the PARENT thread's model
session id: 01a08c88-c768-7c23-8a0a-d4a3598715e1
```

and the review sub-agent's rollout `session_meta.payload` carries:

```
parent_thread_id = 01a08c88-c768-7c23-8a0a-d4a3598715e1   <-- exact match
id               = 01a08c88-d548-7c03-827a-6927049aa77d
source           = {"subagent": "review"}
thread_source    = "subagent"
cwd              = /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base
```

So the chain is deterministic with no new codex feature and no guessing:
banner `session id` -> the child rollout whose `parent_thread_id` equals it and
whose `source` is `{"subagent":"review"}` -> its `turn_context.model`.

### F5 — for `codex review`, the banner's model NEVER RUNS A TURN

The parent exec rollout for that run
(`rollout-2026-09-10T13-16-09-01a08c88-c768-….jsonl`) contains
`{'session_meta': 1, 'event_msg': 158, 'response_item': 2}` and **zero
`turn_context` items**. The child contains the only one. The parent thread
delegates the whole review and never takes a model turn, so the banner's
`model:` line for `codex review` is not merely "the session model" — it names a
model that performed no work at all. That is why glancing at it can never
answer the question, in either direction.

### F6 — `codex review` has no `--json` and no `--model` (0.154.0, live)

`codex review --help` on the installed 0.154.0 lists only:
`-c/--config`, `--strict-config`, `--enable`, `--uncommitted`, `--base`,
`--disable`, `--commit`, `--title`, `-h`. No `--model`, no `-s/--sandbox`,
no `--json`/event-stream flag. This confirms `codex_run.py:518`
(`-c review_model=<toml string>`) is the only channel, and rules out a
machine-readable stream as the observable.

`CODEX_HOME` is unset on this host, so the session root is `~/.codex/sessions`.
An implementer MUST honour `$CODEX_HOME` rather than hardcoding `~/.codex`.

### F7 — CONTROL ARM: the field discriminates, from data, on this CLI build

Scanned every rollout under `~/.codex/sessions` for `session_meta.source` being
a dict, and read the first `turn_context.model`. Four `{"subagent":"review"}`
rollouts exist, all on `cli_version 0.154.0`, all within one day:

| when | turn_context.model |
|---|---|
| 2026-09-10 13:30 | `gpt-5.6-sol` |
| 2026-09-10 02:52 | `gpt-5.6-sol` |
| 2026-09-10 02:12 | `gpt-6-astra` |
| 2026-09-10 01:24 | `gpt-6-astra` |

**Both answers occur.** The observable is therefore not a constant, which is
exactly what the banner failed. (The banner returned `gpt-6-astra` for all
three arms of the 2026-09-09 measurement, including a bogus slug.)

Bonus, unasked: `spawn_agent` sub-agents record `source.subagent.thread_spawn.agent_role`
— e.g. `kb-codex-astra-advisor` -> `gpt-6-astra`, `kb-codex-advisor` -> `gpt-5.6-sol`.
So the SAME observable also makes every Claude-dispatched codex advisor/reviewer
lane's model auditable, not just `codex review`.

### F8 — 🔴 LIVE THREE-ARM MEASUREMENT (2026-09-10, this host, codex-cli 0.154.0)

Same command shape, same repo, same day, ONE variable. Run through the repo's own
task (`mise run kb-codex -- --review --base HEAD~1 --sandbox read-only …`):

| arm | `--model` passed | banner `model:` | rollout `turn_context.model` |
|---|---|---|---|
| the run Ray flagged (13:16) | `gpt-5.6-sol` | `gpt-6-astra` | **`gpt-5.6-sol`** |
| bogus-slug canary (13:53) | `definitely-not-a-real-model-xyz` | `gpt-6-astra` | **`definitely-not-a-real-model-xyz`** |
| control, flag OMITTED (13:53) | *(none)* | `gpt-6-astra` | **`gpt-6-astra`** |

The banner returned ONE answer across all three. The rollout returned THREE
DIFFERENT answers, each equal to what was requested. The observable therefore
discriminates in every direction, including the negative one.

The bogus arm additionally reproduced the API-level canary:

```
ERROR: {"type":"error","status":400,"error":{"type":"invalid_request_error",
"message":"The 'definitely-not-a-real-model-xyz' model is not supported when
using Codex with a ChatGPT account."}}
```

…and, notably, the rollout recorded the invalid slug too — so the field reports
**what was actually requested of the API**, not a post-hoc validation.

Resolver used (this is also the implementation sketch): for a parent session id,
scan `$CODEX_HOME/sessions/**/rollout-*.jsonl`, keep the file whose FIRST line is
a `session_meta` with `payload.parent_thread_id == <parent>` and
`payload.source == {"subagent":"review"}`, then read the first `turn_context`
record's `model`/`effort`. **Exactly 1 hit for each of the three parents** — no
ambiguity, no tie-break needed.

### Verdict on the ground truth

**`-c review_model=<X>` WORKS on 0.154.0. No model was ever substituted.** The
receipt's lane field has been telling the truth; what was missing was any way to
*check* it. The bug Ray asked to be fixed is real but is a **provenance bug, not a
routing bug**: the only observable anyone was reading is structurally incapable of
answering the question, and for `codex review` it names a thread that takes no
model turn at all (F5).

This CORRECTS the standing note in
`.claude/skills/kb-review/references/lanes.md` in one direction only: its claim
that the banner is not a valid observable is CONFIRMED and its 3-arm table
reproduces. Its implicit corollary — that nothing else can answer — is REFUTED.

### F9 — UNRELATED HAZARD found while verifying tree cleanliness (NOT mine)

`git status` was clean at session start and is not now. `.codex/config.toml` has
been rewritten from **265 lines to 43** — 222 lines removed, including the
"TWO SERVERS, TWO NAMES" block that `CLAUDE.md` invariant #4 rests on and the
`[agents] default_subagent_model` rationale — and six env vars added to
`[shell_environment_policy.set]`, among them:

```toml
OTEL_LOG_USER_PROMPTS = "1"
OTEL_LOG_ASSISTANT_RESPONSES = "1"
OTEL_LOG_RAW_API_BODIES = "file:.agent/telemetry/"
```

**Not caused by this consult.** mtime is `13:46:20`; my first probe started
`13:53:06`. Exonerated by timestamp, not by assertion. Flagged because (a) it is
the #399 class (a tracked config rewritten by an unidentified writer) and
`mise run kb-attribute-write -- .codex/config.toml` is the task for it, and
(b) `OTEL_LOG_RAW_API_BODIES` writing raw API bodies to disk is a credential
surface that `docs/secrets.md` would want a look at.

---

## THE VERDICT

**Fail closed.** The remedy is a run-bound evidence record, not a better-worded
claim; and a receipt that cannot produce that evidence must refuse `kb-ship` and
`kb-land` rather than degrade.

Produced by `gpt-6-astra` / `xhigh` / `sandbox: read-only` via
`mise run kb-codex`. **The lane's own model was verified with the observable
this consult is about**: parent session `01a08cae-d643-76c3-a32c-815a6f91ac49`,
rollout `turn_context.model = 'gpt-6-astra'`, `effort = 'xhigh'`. So this verdict
is not a claim about which model ruled, either.

### The risk that decides it

**Mistaking inability to verify for successful verification.** The measurement
settles model *selection*; it does not turn an unavailable observer into a
successful one.

And the sharpest catch, which came out of my own bogus arm and I had not drawn:
**a recorded `turn_context.model` does NOT prove the review completed.** The
bogus arm wrote a perfectly good `turn_context.model` and then died at the API
with the review interrupted. Model-observed and review-happened are two facts,
and a receipt must require both. `sources/codex/codex-rs/core/src/tasks/review.rs:145-149`
(`process_review_events -> Option<ReviewOutputEvent>`) is where codex itself
distinguishes `TurnComplete` from `TurnAborted` — verified, not inherited.

### Ranked remedy

1. **Fail closed — ADOPT.** Preserve the diagnostic artifacts, refuse a
   qualifying receipt, print the exact recovery command.
2. **Degrade to `model-unverified` — diagnostic only.** Honest to *record*; it
   cannot *satisfy* the requirement. Shipping on it is waiving the requirement.
3. **Advisory — REJECT.** Silence on failure recreates the exact ambiguity.

On the outage doctrine (`mise-tasks-only.md`): it forbids redirecting someone to
a command that cannot perform their action. Here the remedy makes certification
reliable and recoverable rather than certifying without evidence. Schema
breakage causing a certification outage is an accepted, explicit availability
trade — not the same failure.

### The design move that defuses the schema risk (Q2)

**Snapshot the evidence into THIS repo's own versioned format during the run.**
Then `kb-ship`/`kb-land` validate our stable record and never touch codex's
internal rollout schema, and never depend on `$CODEX_HOME` sessions still
existing. A single versioned adapter is the only code that reads
`turn_context`/`session_meta`; qualify it against the measured CLI release and
re-exercise it before any codex upgrade. That keeps the internal-schema
dependency at review time, where a failure is cheap and recoverable, instead of
at ship time, where it would be an outage.

The bogus-slug canary belongs in **adapter qualification**, not in every review:
it proves the selection PATH is live, never that this particular review ran on
the requested model.

### Q3 — does the measurement retire option (e)?

**Yes, as the final remedy.** `model-unverified` stays the honest label for
historical runs and for a genuinely unresolved one. Choosing it permanently now
would discard stronger evidence that is demonstrably available — 3 of 3 arms
resolved to exactly one unambiguous hit.

### Q4 — spec handed to an implementer

- **Collection** — extend `python/src/kb_setup/codex_run.py:526` (`_run_review`);
  add `python/src/kb_setup/codex_review_evidence.py` + a versioned schema.
  Capture: attempt id, effective `$CODEX_HOME`, CLI + adapter versions,
  requested model, reviewed SHA/base, subprocess result, immutable output path.
- **Resolution** — take the ONE parent UUID from *that invocation's* banner; join
  on BOTH `source == {"subagent":"review"}` AND `parent_thread_id`. Require
  exactly one child; inspect **every** model-bearing turn context, not just the
  first. Never pick the newest file; never substitute the requested or banner
  model. Bounded retries for persistence lag; incomplete discovery, malformed
  required records, unsupported version and exhausted retries are all explicit
  failures.
- **Result contract** — a tagged union
  `Resolved(evidence) | Unavailable(reason, diagnostics) | Error(kind, diagnostics)`.
  No `None`, no empty list, no default-success. Model *matching* is a separate
  explicit decision on top of `Resolved`.
- **Completion binding** — require successful process completion AND a terminal
  review result, independently of model resolution.
- **Enforcement** — put the requirement in the ONE shared validator,
  `python/src/kb_setup/review.py:413` (`_all_reasons`), which writer and both
  shipping consumers already call — that is exactly the "one composition" this
  module exists to keep. `python/src/kb_setup/cli.py:854` accepts an evidence
  REFERENCE, never a caller-supplied "verified model". Legacy receipts must not
  silently qualify.
- **Recovery** — a python-backed `kb-*` mise task that re-resolves a preserved
  attempt without re-running inference. Publish evidence atomically; a failed
  attempt can never inherit another attempt's success. Update BOTH `kb-review`
  skill copies (`.claude/` and `.agents/`) and their lane references.

### The FAIL-direction arms (each needs a matching valid control)

| check | real isolated failure input | realistic production mutation it must catch |
|---|---|---|
| home + parent binding | custom `CODEX_HOME`; missing/changed banner UUID; an unrelated successful review nearby | hardcode `~/.codex`, drop the parent equality, or pick newest |
| complete, unique discovery | zero children; two matching children; delayed child; incomplete scan | accept first hit, or read an exhausted/incomplete search as success |
| required schema + turns | missing `model`; zero turns; truncated JSON; unsupported version | skip invalid records, or default a missing model to the requested one |
| lane/model agreement | Sol lane with an Astra observation; a later turn changes model | read only the first turn, or drop the exact comparison |
| review completion | the bogus-slug failure; cancel after one turn; banner-only output | ignore exit/terminal outcome because a model was observed |
| resolver failure | raise an I/O error; kill the resolver mid-run with a prior success on disk | catch-and-return-success, or reuse stale evidence |
| receipt binding | swap report/run ids; remove evidence; supply a legacy/unknown variant | remove the digest/identity check, or make evidence optional |

Exercise the failures through receipt creation, ship AND land, asserting nonzero
/ refusal and **no push or merge side effect**. Extend `tests/test_codex_lane.py`,
`tests/test_review.py`, `tests/test_review_cli.py`, `tests/test_pr.py`; add
resolver tests and a `kb-arms` spec. Use real temp files and subprocesses for the
absence/crash arms — **renaming a definition proves nothing here.**

### One consequence not in the spec, worth stating

`--ephemeral` becomes load-bearing rather than merely discouraged. An ephemeral
lane persists no session file, so it can never produce this evidence. Repo policy
already forbids it (`ai-cli-invocation.md`); after this change, breaking that
policy would silently make every review unshippable.

## What I could NOT verify

- **The Astra lane's own graph access failed.** It reported: *"Graph query and
  recall tasks both failed before execution because mise could not create
  temporary files"* — the read-only sandbox. Its ruling therefore rests on the
  evidence I supplied plus its own source inspection, not on the KB graph. I ran
  the graph reads myself (see F1-F8); the verdict's reasoning did not.
- **`--ephemeral` behaviour was not re-armed this session.** It is inherited from
  a 2026-09-01 measurement recorded in the agent spec; label it unverified.
- **Rollout-schema stability across future codex releases** is unknowable by
  probe. That is precisely why the adapter is versioned and qualified per release.
- I did NOT run a full successful Astra-vs-Sol *paired review to completion*; the
  control arm was the flag-omitted run plus the four historical review rollouts.

## GitHub repos touched

- [openai/codex](https://github.com/openai/codex) — the pinned `rust-v0.154.0`
  source: `core/src/tasks/review.rs`, `core/src/config/mod.rs`,
  `protocol/src/protocol.rs`, `core/tests/suite/review.rs`.
