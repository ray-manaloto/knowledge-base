# Rider — `Fluent`: stale-graph detection + the release-notes review

Serves `docs/goals/2026-07-31-1348-kb-fluent-stale-graph-goal.md`. Paste that
file's contents after `/goal `; this file is what it points at.

Produced by the `Fluent` wayfinder map
([#85](https://github.com/ray-manaloto/knowledge-base/issues/85)), whose five
child tickets are all resolved. **Every decision below is already settled — this
round executes, it does not re-litigate.** Where a decision has a ticket, the
ticket carries the evidence.

## Scope decision — is this one round?

Yes, and the headline word is the test: **`Fluent`** names the state of the world
after the round — this repo can tell you, without being asked, whether the graph
still matches its committed inputs and whether the tools that built it have moved.
The detector and the notes review are two halves of the same fluency; neither
alone produces it. A repo that notices a stale graph but runs a year-old graphify
is not fluent, and neither is the reverse.

**Split out deliberately** (do not pull back in): #82 (codex/cursor/opencode/pi
docs, ~27M subagent tokens), #81 (toolchain docs), #93 (`kb-extract.js` prompt)
and #94 (`sources/**` scanner scope), and the dotfiles port carrying
`kb-setup`'s pin, `[tool.mise]`, `min_version`, and the `hk.pkl` scanner fix.

## The evaluator constraint — everything below follows from it

> It does not call tools, so it can only judge what Claude has already surfaced
> in the conversation. — `code.claude.com/docs/en/goal.md`

No file reads, no commands, no git. So every clause in the goal is settleable by
**string match over the transcript**. "The detector works" is unjudgeable; "the
transcript contains `STALE-ARM+ @ <sha>` followed by pasted output" is judgeable.

Write for the weakest evaluator you could get. `ANTHROPIC_DEFAULT_HAIKU_MODEL`
rebinds the evaluator globally, so Haiku-class is a **floor**, not a description
of what will actually judge this round. Record which model judged it in the
outcome — a `stalled` under one evaluator is not evidence about another.

## Preserve list — change anything except these

The list exists because the cheapest way to satisfy almost any metric is to
delete the thing the metric was protecting. Each row names what a plausible
"consistency pass" would remove, and why removing it is the failure.

| Preserve | Where | Why deleting it is the cheapest wrong move |
|---|---|---|
| `size:mtime_ns` for **OUTPUTS** | `kb_setup.currency.sync.artifact_fingerprint` | This round introduces a sha256 fingerprint for INPUTS. "Unifying" the two looks like tidying and is measured wrong: outputs are **341 MB** and inputs **2.4 MB** — 142x — and the stat exists precisely because a digest over 341 MB cannot run in a per-session hook (#89). |
| DRIFT / SKIP / OK as three distinct states | `kb_setup.currency`, and `CLAUDE.md`'s currency section | Collapsing to a boolean makes every code path shorter. It also makes "could not check" render as green, which is the single defect this engine's whole design refuses. |
| `kb-currency-check` staying **silent when clean** and **always exiting 0** | `kb_setup.currency`, the SessionStart hook | A detector that prints on every session gets ignored; one that exits non-zero blocks sessions over a version pin. |
| The `no depends` ban | `hk.pkl:12` (`fail_fast = false`), `hk.pkl:152`, `long-running-command-hangs.md` rule 5 | hk **1.53.0 (#1099) fixed** the deadlock behind it, so a currency-minded agent will read the ban as dead weight. Ray decided 2026-07-31 to keep it: `exclusive` works and the doctrine spans both repos. Retiring it here alone splits their rules. |
| The `kb-review` receipt gate | `kb_setup.review`, the receipt checks in `pr.py`'s `ship_main` / `land_main` | Deleting it is the CHEAPEST way to make the `PASS  gate …` lines below appear, and it must not be the way. |
| Every existing `[tool.*]` block and its `watch` items | `currency.toml` | The watch notes carry conditions (version floors, "this is inert here", the fnox skew) that read as verbose. They are the falsifiable half. |
| The fnox pin/skew note | `mise.toml` `fnox = "1.31.1"` + `[[tool.fnox.watch]]` | The skew (repo pin vs the user's global `latest`) is deliberate and accepted (#86). "Fixing" it means editing `~`, which `do-not.md` #11 forbids outright. |
| Verbatim reports | `docs/research/reports/**` | Never reformatted, renamed, or trimmed — including `2026-07-31-size-mtime-false-drift.md`, which is what #89's decision rests on. |
| Committed work-memory | `graphify-out/memory/**` | Append via `kb-remember`; never rewrite an existing entry. |

## Posture — expanded

- **knowledge-base only.** No dotfiles edits, no port. dotfiles has unrelated
  in-flight work on `docs/takeover-research-20260730`.
- **The detector never rebuilds and never blocks, and always exits 0** (locked map
  Note + #88). It is a signal. `graphify-out/` is gitignored and DERIVED, so a
  stale local graph is not part of what ships and cannot be a shipping defect.
- **No `.sh`, no inline shell logic** — `kb_setup` module + a mise task.
- **No `noqa` / `type: ignore` / `ty: ignore`** — suppressions live in the root
  `pyproject.toml` or not at all.
- **No bare `graphify`** — `kb-*` tasks only; the PreToolUse guard denies it.
- **Branch first.** Never commit on `main`.
- **Do NOT re-propose `size:mtime_ns` for INPUTS.** Falsified by #89 with a
  measured eight-row table; three ordinary git operations move it on identical
  bytes. Re-proposing it requires a NEW measurement pasted into the conversation
  first, not an argument.
- **Do NOT retire the `no depends` ban** (above).
- **Do NOT bump a pin the notes review has not read.** An unread bump is the
  thing this round exists to stop.

## The question this round answers

*Can this repo tell, unprompted, that its graph no longer matches its committed
inputs — and are the tools that built it current?*

Banned answers, because they have already been tried and refuted:

- **`graphify check-update` cannot do this job.** `watch.py:1499` tests only for
  `graphify-out/needs_update`, which is written solely by `graphify watch` — and
  `do-not.md` #2 forbids `--watch`. It is a probe that can only say "clean", and
  it is guard-denied besides.
- **`built_at_commit` cannot do this job.** It is the git HEAD at build time, so
  every rebuild at one commit writes the identical value — and rebuilding
  repeatedly at one commit is the normal rhythm.

## Phases

Each phase: **depth test first → implement → gates green → one conventional
commit.** A phase whose product is a finding has no failing test to write first;
that is fine, and it is said rather than faked.

### P1 — the input fingerprint

Add a sha256 content fingerprint over `sources/*.manifest` +
`sources/extractions/*.json` — the two globs `kb_setup.graph.build()` actually
reads — recorded into `graphify-out/.currency-stamp.json` alongside the existing
output fingerprints. Written by `kb-build`, at the same point the build stamp is.

**Depth test first**, both arms: a real content change moves it; the three git
operations #89 measured (revert via `git checkout --`, round-trip through a
branch that touches `sources/`, stash+pop of a `sources/` edit) do **not**.

Cost is settled: 1.8 ms over 43 files, best of 5. `git hash-object` was measured
as the tool built-in and is **~480x slower** here — subprocess start-up dominates
a 2.4 MB hash — so this is in-process `hashlib`, and that is recorded so nobody
re-runs the check.

### P2 — the detector, and its own output section

Compare recorded inputs against live ones and report **under its own header**,
not folded into the version-drift block (#88). The existing header says *"run the
tool-currency skill"*, which is the wrong remedy: the fix for a stale graph is
`mise run kb-build`, and folding it in would print an instruction that does not
fix what it is reporting.

It **names what moved**, per path — `kb-update`'s changed-page worklist is the
precedent: a fingerprint proves THAT something changed, never WHAT.

```text
[graph] corpus inputs changed since the graph was built — run `mise run kb-build`:
[graph]   sources/agent-harness-docs.manifest  (content changed)
[graph]   sources/extractions/claude-docs-docs.json  (content changed)
```

### P3 — the not-verifiable state, and its ordering

**Absent stamp or absent graph short-circuits to *never built* BEFORE any input
is compared** (#89). A fresh clone has neither artifact, so comparing first would
tell the very first session in a new clone that its whole corpus had gone stale.

The 43-of-43 figure from #89 belongs to THIS phase and not to P1, and the
distinction matters: a fresh clone has **no recording to compare against at all**,
which defeats every fingerprint scheme equally — sha256 included. It is not
evidence against `size:mtime_ns` and must not be read as qualifying P1's claim
that sha256 survives content-preserving git operations. It is the reason for the
ordering rule above, and nothing else. (Cold lane, round 1.)

An unreadable stamp reports *not verifiable*, never a false green. Test both
directions.

### P4 — wire it in

Into the same SessionStart path `kb-currency-check` already runs on. Silent when
clean. Always exit 0.

### P5 — the release-notes review

Four tools; two still need reading:

| Tool | State entering this round |
|---|---|
| **graphify** | pinned **0.9.30**, upstream **0.9.31** — NOT read |
| **mise** | `expected` **2026.7.16**, PATH **2026.7.18** — NOT read; nags every SessionStart |
| **hk** | pinned **1.52.0**, upstream **1.54.0** — **notes already read** (#87); 1.53/1.54 recorded in `currency.toml`'s watch items. The remaining question is only whether to bump. |
| **fnox** | pinned **1.31.1** = upstream **1.31.1** — in sync, both arms probed (#86) |

Read graphify's and mise's notes and say, per release, whether it reaches this
repo's actual usage. "Reaches" means naming the code path, not the feature.

### P6 — act on what P5 found

Bump what the notes justify; record what they do not. A bump that is not
justified by a note that was read is out of scope by posture.

**hk's bump is a three-places change**: `mise.toml`'s pin, plus `hk.pkl`'s
`amends` and `import` URLs (#87). A `mise.toml`-only bump runs a new binary
against old schemas, and the mismatch surfaces as a pkl error with nothing
pointing at the pin.

### P7 — review, ship, THEN record the outcome

Order, and every step of it is load-bearing:

1. `kb-remember` + `kb-reflect` — the lessons, which are knowable now.
2. The `kb-review` skill, then `mise run kb-review-receipt`.
3. `mise run kb-ship`.
4. **`mise run kb-goal-outcome` — only now**, and only with the result that
   actually happened.
5. Commit what step 4 wrote, and push it to the open PR.

**Step 4 comes after step 3 because `ship: OK` is verification item 7** — the
round's success is not knowable until ship has succeeded. Recording `achieved`
before shipping means a later ship failure leaves a false `achieved` in
`docs/goals/README.md` and in work-memory, where the next session reads it as
settled. (Cold lane, round 1.)

**Step 5 does not need a second review**, and this is exactly what
`review.EXEMPT_PATHS` was built for (#66): `kb-goal-outcome` writes only
`graphify-out/memory/**` and `docs/goals/README.md`, so `kb-land` accepts the
ancestor receipt from step 2 for a HEAD whose entire delta is those paths. One
reviewed path in that delta and it refuses, naming the file.

**Do not invert 1 and 2 to `land` first.** `kb-land` squash-merges, so the
reviewed SHA is not an ancestor of the new `main` afterwards and the exempt-path
fallback has nothing to fall back to. Measured the hard way this session: a
19-line work-memory file then needed a cold lane of its own.

## Sentinel formats

Every sentinel ends `@ <sha>`, where `<sha>` is the current
`git rev-parse --short HEAD`. The `@ <sha>` is what stops the goal's own text
counting as evidence — the condition names each string, so all of them are in the
transcript at turn 0, and only a real run can attach a real SHA to one.

| Sentinel | Means |
|---|---|
| `STALE-ARM+ @ <sha>` | the detector FIRED on a real input change; command and output pasted |
| `STALE-ARM- @ <sha>` | the same detector stayed SILENT after a git op that left the bytes unchanged; command and output pasted |
| `STALE-NEVER-BUILT @ <sha>` | an **absent** stamp reported *never built*, NOT drift; output pasted |
| `NOTES-REVIEWED: <tool> <from>-><to> — <one sentence> @ <sha>` | one per tool read in P5 |
| `GOAL-BLOCKED: <blocker> — tried: <probe1>; <probe2> @ <sha>` | the honest exit, naming two probes already pasted |

`STALE-ARM+` without `STALE-ARM-` is not evidence — it is a check that has only
ever passed (`probes-need-a-control-arm.md` rule 2). Both, or neither counts.

**`STALE-NEVER-BUILT` means one outcome, not two.** It covers the ABSENT-artifact
case only. P3 also tests the *unreadable*-stamp branch, which must report *not
verifiable* — that is a test rather than a goal clause. Naming both under one
sentinel would let a probe that only ever reached one branch satisfy a condition
written about the other. (Cold lane, round 1.)

## Verification — the literal strings, and what prints them

Sourced from the code that PRINTS them, anchored to symbols rather than line
numbers (a line number is invalidated by any edit above it, including one that
never touches the string):

| Literal | Printed by |
|---|---|
| `==> review: <n> lane(s): …` | `pr.py` `ship_main`, before any gate runs |
| `PASS  gate <name> rc=0` — **two spaces** | `pr.py` `run_gates` |
| `ship: OK — PR open, gates green` (em dash) | `pr.py` `_open_or_update_pr` |
| `OK eval: N passed, N skipped, 0 failed, 0 unarmed` | `evals.py` `render` |
| `review-receipt: OK` | `kb-setup review-receipt` |
| `Saved to graphify-out/memory/<file>.md` | graphify `cli.py` |
| `Reflected N memories (…) -> …LESSONS.md` | graphify `cli.py` |

**Three traps, all measured, all invisible from reading a goal:**

1. `mise run test` runs pytest under `-qq`, so **`"N passed"` never appears**. A
   condition requiring it is unsatisfiable. (Control arm: bare
   `uv run pytest tests/` prints it.)
2. `kb-currency-check` prints **nothing** on success, so silence is
   indistinguishable from never-ran. Require an echoed, file-recorded `rc`.
3. **`kb-ship` REFUSES before it runs a single gate** without a `kb-review`
   receipt for the current HEAD. So a condition asking for `PASS  gate lint rc=0`
   with no instruction to review first is unsatisfiable — ship stops at the
   receipt check and none of those strings appear.

## Out of scope — the overflow valve

Anything this round discovers it should not do goes here, not into scope: the
four split-out tickets (#82, #81, #93, #94), the dotfiles port, retiring the
`no depends` ban, and any change to the OUTPUT fingerprint.

## Hand-back — never report these as done

- **Merging the PR is Ray's call.** The round ends at `ship: OK`.
- **Secret rotation is Ray's**, deferred to project end by his explicit decision.
  Raise it once, unprompted, when the project completes — not each session.
- **Any decision the map locked** is Ray's to reopen, not this round's.
