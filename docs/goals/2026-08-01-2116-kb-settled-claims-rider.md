# Rider — `2026-08-01-2116-kb-settled-claims`

Serves `docs/goals/2026-08-01-2116-kb-settled-claims-goal.md`. Read both.

## Scope decision — is this one round?

Yes, and the headline word is the test. **Settled** names one state of the
world: *no claim this repo makes about its own currency, its own graph, or its
peer tools is still resting on a measurement someone else took, or on a probe
that was deferred.* Every phase below moves exactly one such claim from
inherited/deferred to re-derived-in-round.

It is a bigger round than it looks, and that is deliberate — Ray's clear-prep
decisions (2026-08-02, `AskUserQuestion`) chose the bundling on cost grounds:

1. **The currency tail AND #101 in ONE round.** They share a `kb-build`. #101's
   verification needs one, and so does re-probing
   `data-only-json-produces-zero-nodes` by counting build warnings. Splitting
   them pays for two ~30-minute builds to learn two things one build answers.
2. **Both cross-report disagreements fold in.** Both are cheap probes, and the
   prose-node-count one is the same inherited-number shape as the 382-vs-119 MB
   error the Navigable round already had to fix in `CLAUDE.md`.
3. **`kb-tool-review.js` gets exercised end-to-end on a NEW, fourth tool.** It
   has never been executed. Its agents were run individually during the
   Navigable round and it has been patched twice since, so *committed* is not
   *proven*.
4. **The round PROPOSES the fourth tool and waits.** Ray picks. See
   "Hand-back".

What is NOT in this round: any dotfiles commit, any upstream issue closure, any
raise of the graph size cap, any second peer-tool fan-out beyond the one
approved tool. Those are in "Out of scope".

## The evaluator constraint

`/goal`'s evaluator does not call tools. It judges only text already in this
conversation. So every clause below is *an action that produces text, plus a
property of that text* — never a state of a file. A probe run inside a
subagent, a `Workflow`, or a background task is **invisible** to it: its output
must be restated in the main conversation to count (T11).

## Progress checkpoints — the operator is a reader too

The section above makes every clause legible to the *evaluator*. Nothing else
in this pair makes the round legible to **Ray**, and on 2026-08-02 that cost a
real misread: the goal was armed, no phase had started, and the silence was
indistinguishable from a long-running agent — so the round was reported as
*"done and agents completed"* when nothing had run at all. `TaskList` and
`CronList` were both empty.

`/goal`'s own documentation already assumes the opposite. With a turn or time
clause in the condition, *"Claude reports progress against that clause each
turn and the evaluator judges it from the conversation."* This round has one
(70 turns, SOFT), so progress narration is not an extra — it is the documented
behaviour of the bound this goal already carries.

Binding for this round:

- **A `SendUserMessage` at every phase boundary** — one starting a phase, one
  closing it naming the sentinel that landed. Silence between phases is a
  defect, not efficiency.
- **A message BEFORE any command expected to exceed ~2 minutes**, saying what
  is running and roughly how long. The P4 build is ~30 minutes and would
  otherwise be half an hour of nothing.
- **The turn count in each boundary message** (`turn n/70`). That is what the
  documented per-turn progress report actually is.
- **A hand-back is announced, not merely awaited.** P3 ends by waiting for
  Ray; the wait must arrive as a question, never as a pause.

These are *reporting* obligations, not completion ones. None is a sentinel and
none gates the goal — a checkpoint message must never be offered as evidence
for items 1–8, which the EVIDENCE RULE already forbids.

## The amendment budget is deliberate

The goal measures **3,820 of 4,000 characters**, leaving ~180 spare. That is not
slack, it is a reserve, and it is there because of #65: the Legible round's goal
sat at **3,941** and *could not be amended* when reality diverged — editing a
round's own completion condition mid-round to make the round satisfiable is the
Goodhart move a preserve list exists to name, so the round correctly refused,
and the consequence was an evaluator reading two arms with neither satisfied.

The first draft of this goal sat at 3,974 — **tighter than the one that already
failed**. It was cut back rather than shipped. If this round needs an amendment,
there is room for one; spend it on a LANDINGS arm, not on deleting a clause.

## Preserve list — change anything except these

| What | Where | Why it is here |
|---|---|---|
| the `kb-review` receipt gate | `kb_setup/review.py`, `pr.py` | deleting it is the single cheapest route to the `PASS  gate` lines. Not the way. |
| `docs/research/**` exclusion from the reviewed diff | `.claude/skills/kb-review/SKILL.md` | an empty scoped diff is a *state*, not a bug; "fixing" it by deleting the exclusion re-imports 56% self-exhaust |
| DRIFT / SKIP / OK as three distinct states; "could not check" never rendered green | `kb_setup/currency/**` | seeding a baseline is cheapest by deleting the *NOT CHECKED* reporting. That would make the round's own evidence unfalsifiable. |
| `kb-currency-check` silent when clean; always exits 0 | `kb_setup/currency/run.py` | a SessionStart hook must never block a session over a pin |
| `size:mtime_ns` for OUTPUTS / sha256 for INPUTS | #89 | re-litigated once already |
| every `[tool.*]` block and every `watch` item in `currency.toml` | `currency.toml` | this round ADDS baselines and re-probes; it never prunes. Deleting a tracked issue is the cheapest way to "re-check" it. |
| `.base-graph.json` + `.base-graph.sha256` and `kb-watch` idempotence | `kb_setup/graph.py` | landed last round with a content guard; a one-root change must not quietly drop it |
| `scope = study` as a second axis from `kind`, and the three peer tools already pinned | `sources/*.manifest` | the cheapest way to make a rebuild fast is to drop sources |
| the `no depends` ban | `hk.pkl` | `depends` + `fail_fast = false` deadlocks hk |
| verbatim reports | `docs/research/reports/**`, `.agent/kb/**` | `agent-report-persistence.md` |
| existing work-memory | `graphify-out/memory/**` | append only |

## Posture — expanded

- **knowledge-base only.** The dotfiles gap is a *measurement*. No dotfiles
  commit, no dotfiles branch, no `mise run` in that repo that writes anything.
- **Do not pick the fourth tool.** Propose, then stop. Running the fan-out
  before Ray answers is the one irreversible spend in this round.
- **One `kb-build`, not three.** The whole bundling argument is that #101's fix
  and the fourth tool's ingestion ride the same build. If a second build turns
  out to be unavoidable, say why in the message that starts it.
- **No inherited numbers.** Every figure this round reports is re-derived in
  this conversation or explicitly labelled inherited-and-unverified
  (`probes-need-a-control-arm.md` rule 6).
- **Do not claim the #101 capability without both arms.** A depth test that has
  only ever passed is decoration; it must FAIL at HEAD first.
- No `.sh`, no inline shell logic, no `noqa` / `type: ignore`, no bare
  `graphify` at a command position, no non-Claude LLM backend anywhere near the
  corpus.
- Branch first. Do NOT raise `GRAPHIFY_MAX_GRAPH_BYTES` — if growth exceeds the
  remaining headroom, stop and report rather than widening the cap.
- Turn bound **70, SOFT**: flag the overrun in a message, finish the phase in
  flight, do not abandon mid-phase.

## The question this round answers

*Which of this repo's standing claims survive a fresh measurement?*

**Banned answers** — already refuted, do not re-propose without a NEW pasted
measurement:

| Claim | Why it is banned |
|---|---|
| "`affected` cannot link tests to source — it is a graphify limitation" | refuted by an adversarial verifier: `affected "_state"` → 9 test functions; a `conftest.py` fixture reaches 17 across two modules. The cause is OUR merge namespacing, not the tool. |
| "cognee proves one-root works, so our fix works" | cognee is the **indirect** arm only. The direct arm is a `kb_setup.graph` change plus a build plus a depth test. |
| "an issue is open upstream, therefore the gap exists" | issues stay open after fixes ship. Read the **installed 0.9.31 source**. |
| "`mise run test` prints `N passed`" | it runs pytest under `-qq`; that string never appears |

## Phases

Each phase: depth test first where it changes code → implement → gates green →
one conventional commit. P1, P6 produce *findings* rather than code, so they
have no failing test to write first; that is stated rather than faked.

### P1 — settle the two cross-report disagreements (cheap, no build)

Both were flagged by the Navigable round's synthesist and left unresolved.

**(a) Does graphify report its own truncation?** One report quotes
`TRUNCATED: showing 70 of 487 nodes`; the other says `kb-query`'s budget
truncation is silent. The hypothesis is tool-vs-wrapper. Settle it by running
BOTH surfaces on one question large enough to truncate, and pasting both
outputs — the graphify-level call and `mise run kb-query`. Report which layer
prints what. If the wrapper is the silent one, say whether a fix is a
one-liner; do not build it this round.

**(b) The prose graph node count.** Both retrieval reports say **2,553**;
`CLAUDE.md` says **2,105**. Re-derive it live — `mise run kb-query -- "…"
--prose --idf` prints an `indexed node(s) from graph-prose.json` line — and
correct whichever document is stale, in the same commit. Note the count moves
when the graph is rebuilt, so run this AFTER P4 if the pre-build number and the
post-build number disagree; report both rather than picking one.

### P2 — #101: one extraction root (the depth test comes first)

`python/` and the root `tests/` are indexed as two extraction runs, so
`merge-graphs` re-namespaces ids per merge and leaves disjoint namespaces
(`knowledge-base::python::…` vs `tests::…`) that no edge can span.

Measured last round:

| measurement | value |
|---|---|
| tests-touching edges | 3,368 |
| **crossing into `python::`** | **0** |
| control: within `python/` | 2,194 |
| cognee (ONE extraction run), same graph file | **10,099** test↔src edges |

**Write the depth test first and watch it FAIL at HEAD**: `affected` on a real
`kb_setup` symbol must return at least one node whose path is under `tests/`.
Paste the failing run. Then change `kb_setup.graph`'s self-extraction to cover
both trees as ONE extraction root. Do not rebuild yet — P4 owns the build.

The candidate fix is **UNVERIFIED**. If the depth test still fails after P4,
that is `AFFECTED-TESTS=REFUTED @ <sha>` — a landing, with both arms pasted,
not a failure and not `GOAL-BLOCKED`. Do not claim the capability, and do not
keep re-cutting the fix to force a pass; a refuted hypothesis with a clean
measurement is worth more to the next round than a green arm nobody trusts.

### P3 — propose the fourth peer tool, then STOP

Bring **2–3 candidates** to `AskUserQuestion`, each with:

- repo size measured live (files, or LOC — say which), not recalled;
- licence, read from the repo;
- one line on why it is a peer worth a gap analysis, and which `lens` it would
  get (`retrieval` / `observability` / something new).

Starting points to **re-check live, not to trust**: `getzep/graphiti`
(temporal agent-memory graph), `oraios/serena` (LSP-backed semantic code
toolkit), `blarApp/blarify` (codebase → graph), `Aider-AI/aider` (repo-map via
PageRank over a tree-sitter graph). Any of these may be archived, renamed or
already covered — verify before proposing. Do not propose a tool already under
`sources/` (`cognee`, `basic-memory`, `pensyve`, and the three existing
`scope = study` tools are all taken).

**This phase ends by waiting.** Do not register a manifest, do not ingest, do
not launch the fan-out before Ray's answer is in this conversation.

If Ray rejects every candidate, that is `TOOL-APPROVED=DECLINED @ <sha>` and
P4's and P5's items land `=DECLINED` with it. Do NOT substitute a tool he did
not pick, and do NOT re-ask with the same list reworded — a second round of
candidates needs genuinely different ones.

### P4 — ONE `kb-build`

After approval: add `sources/<key>.manifest` (url + ref + commit,
`scope = study`), then run **one** `mise run kb-build` that carries both
the #101 one-root change and the new source.

Three things come out of this single build:

1. the #101 depth test's PASS arm (or its refutation);
2. `INGESTED: <key> <n> nodes`, `<n>` non-zero;
3. the `data-only-json-produces-zero-nodes` re-probe — **count the build's
   warnings**; that is the recorded method in `currency.toml`, not a new one.

Check headroom before starting. If the graph would exceed the cap, stop and
report; do not raise it.

⚠️ **`mise run lint` is BLIND to the new manifest.** `sources/**` sits outside
every hk builtin (#94), so a commit adding only a source file passes a gate that
examined zero files. `PASS  gate lint rc=0` is therefore green *about nothing*
here. The real arm is the build itself: a manifest whose pin is wrong fails at
clone time, and `INGESTED: <key> <n> nodes` with `<n>` non-zero is what proves
the source actually reached the graph. Do not read the green gate as validation
of the manifest — this is `verify-before-advancing.md`'s "a green gate is not a
green artifact", with a named issue behind it.

### P5 — exercise `kb-tool-review.js` end-to-end

Invoke the saved workflow, not its agents individually — and **by `scriptPath`,
never by `name`**:

```text
Workflow({ scriptPath: '.claude/workflows/kb-tool-review.js',
  args: { reportDir: 'docs/research/reports',
    tools: [{ key: '<key>', source: 'sources/<key>', lens: '<lens>', note: '<note>' }] } })
```

⚠️ **`name:` resolution runs a STALE CACHED COPY — this would silently defeat
the whole phase.** Measured in #13: `.claude/workflows/kb-extract.js` was
edited, re-invoked by name, and returned **the old error text verbatim**; an
explicit `scriptPath` to the repo file worked first try. `kb-tool-review.js`
has been patched twice since it was written, so a by-name run would exercise a
pre-patch script and report `HARNESS-RAN` as evidence about the committed file
— reproducing, inside this round's own verification, exactly the
committed-is-not-proven error the round exists to correct.

The `Workflow` tool result carries the path the script was persisted from.
**Paste that path, the returned object, and the report paths into the main
conversation** — a Workflow result the evaluator never sees does not exist
(T11), and a path nobody pasted is not proof of which script ran.

It returns `{ tools, verified, refuted, unverified, reports }`.

**Zero refuted means the verifier did not run.** That was true of the three
Navigable gap analyses and it is true here. If the run surfaces a defect in the
workflow itself, fixing it IS the deliverable of this phase — proving the
harness is the point, and a harness that fails on first real use has just paid
for itself.

### P6 — the currency tail

Follow the methods recorded in `currency.toml`; do not reinvent them.

- **`label-communities-schema-gap`** — last probed on 0.9.30. Diff `llm.py`
  between the probed version and the installed 0.9.31; **grep the diff for
  `label` BEFORE assuming anything**; run the 42-batch probe **only if** a
  label-touching line moved. "No label line moved, so the prior verdict
  stands" is a legitimate, cheap outcome — say so with the diff pasted.
- **#2101, #2086, #1653, #1824** — re-check each against the **installed
  0.9.31 source**, never the tracker.
- **hk and fnox upstream baselines** — both print *"no upstream version has
  ever been recorded — NOT CHECKED against upstream (this is not a pass)"*
  every session today; confirmed still true at `43a6b46`. Seed them with a
  networked `mise run kb-currency`. If upstream is unreadable, that lands as
  `BASELINE-SEEDED=UNREACHABLE @ <sha>` with the failed command pasted — never
  as a seeded baseline, and never as silence. An unreachable upstream is the
  *latest UNKNOWN* state the engine already models; do not collapse it to OK.
- **What a graphify bump actually costs** — pin + manifest + re-clone + a full
  rebuild. Now measurable: the Navigable round ran three full `kb-build`s and
  this round runs one. Write the sentence with a real minute count.
- **The dotfiles gap, as a MEASUREMENT.** Its `currency.toml` carries only
  `[tool.graphify]`, and its `kb-setup` pin is behind main. Re-derive how far
  behind — do not repeat the inherited "26 commits / 4,907 insertions" figure
  without re-running it. `#34`: the SessionStart nudge never fires cross-repo
  because `CLAUDE_PROJECT_DIR` is the other repo. **No dotfiles commit.**

### P7 — close

`kb-remember` + `kb-reflect` → the **`kb-review` skill** (ONE cold cross-family
lane, bounded at 2 rounds) → `mise run kb-review-receipt` →
`mise run kb-goal-outcome` → commit what it wrote → `mise run kb-ship` →
`mise run kb-land`.

**The round ends at `kb-land`, not at `ship: OK`** (Ray, 2026-07-31: *"why is
merging mine, we are working on a long-running multi-agent harness"*). Run
`kb-goal-outcome` BEFORE `kb-ship` and commit its output —
`review.EXEMPT_PATHS` covers `graphify-out/memory/**` and
`docs/goals/README.md`, so closing the loop costs no re-review (#66).

**Freeze HEAD for the duration of the review.** Nothing enforces it; the
receipt catches the consequence at ship time, long after the cheap moment.

## Sentinel formats

Every sentinel ends `@ <sha>`, where `<sha>` is `git rev-parse --short HEAD` at
the time of writing. The `@ <sha>` rule exists because a value that did not
exist when the goal was written is the only thing separating fresh evidence
from the condition quoting itself (T12).

```text
TRUNCATION: <tool|wrapper|neither> — <literal printed, or the word silent> @ <sha>
PROSE-COUNT: <n> — <path corrected, or already-correct> @ <sha>
AFFECTED-TESTS- @ <sha>          # at HEAD, before the fix: no node under tests/
AFFECTED-TESTS+ @ <sha>          # after the P4 build: >=1 node under tests/
TOOL-APPROVED: <key> @ <sha>     # quoting Ray's answer; never self-approved
INGESTED: <key> <n> nodes @ <sha>
HARNESS-RAN: <key> — <v> verified, <r> refuted, <u> unverified @ <sha>
REPROBE: <item> — <verdict> @ <sha>
ISSUES-RECHECKED: 2101/2086/1653/1824 @ <sha>
BASELINE-SEEDED: hk <v>, fnox <v> @ <sha>
BUMP-COST: <sentence with a measured minute count> @ <sha>
DOTFILES-GAP: <sentence with a re-derived number> @ <sha>
GOAL-BLOCKED: <blocker> — tried: <probe1>; <probe2> @ <sha>
```

`AFFECTED-TESTS-` and `AFFECTED-TESTS+` are a **pair**. One arm alone is not
reportable — that is `probes-need-a-control-arm.md`, and it is the rule this
repo has paid for most often.

### The landing arms (the goal's LANDINGS clause)

Every item may also land as a **negative that is still a result**:

```text
AFFECTED-TESTS=REFUTED @ <sha>     # one-root fix built, depth test STILL fails
TOOL-APPROVED=DECLINED @ <sha>     # Ray rejects every candidate
INGESTED=DECLINED @ <sha>          # cascades from TOOL-APPROVED=DECLINED
HARNESS-RAN=DECLINED @ <sha>       # same
BASELINE-SEEDED=UNREACHABLE @ <sha> # upstream unreadable; paste the failed cmd
```

**This exists because a pair offering only success and blocked pushes the agent
toward *claiming* success** — #65, found by the Spec lane on the Legible round,
where the round established its cause, could satisfy neither of its two arms,
and had to invent a third mid-round. A refutation with both arms pasted is a
landing, not a failure, and it is emphatically not `GOAL-BLOCKED`. Reserve that
sentinel for *"I cannot find out"*, never for *"I found out, and the answer was
no"*.

The arm inherits the same evidence discipline as the positive: it names the
probe, and the probe's output is pasted. `=REFUTED` asserted without a run is
worse than no landing at all.

## Verification — the literal lines, and the code that prints them

Sourced from the code that PRINTS each string, anchored to symbols rather than
line numbers (a line number is invalidated by any edit above it):

| Signal | Literal | Source |
|---|---|---|
| review receipt, before any gate | `==> review: <n> lane(s): …` | `pr.py` `ship_main` |
| any gate under `kb-ship` | `PASS  gate <name> rc=0` — **two spaces** | `pr.py` `run_gates` |
| gates `kb-ship` runs | lint, test, brain-audit, eval | `pr.py` `GATES` |
| new PR | `ship: OK — PR open, gates green` | `pr.py` `_open_or_update_pr` |
| merged | `land: OK — PR #N merged, main synced` | `pr.py` `land_main` |
| memory | `Saved to graphify-out/memory/<file>.md` | graphify `cli.py` |
| reflect | `Reflected N memories (...) -> ...LESSONS.md` | graphify `cli.py` |

Three traps, all measured here, all of which look completely reasonable in a
goal and are unsatisfiable:

1. **`mise run test` runs pytest under `-qq`, so `"N passed"` never appears.**
   Control arm: bare `uv run pytest tests/` prints `578 passed`.
2. **`kb-currency-check` prints NOTHING on success**, so silence is
   indistinguishable from never-ran. Require an echoed, file-recorded `rc`.
3. **`kb-ship` REFUSES before it runs a single gate** without a `kb-review`
   receipt for HEAD. A condition asking for `PASS  gate lint rc=0` with no
   instruction to review first is unsatisfiable.

And the one the Navigable round actually tripped on, which is why it recorded
`stalled` rather than `achieved`: its condition named a **`[graph]` line** from
`kb-currency-check` as the bypassed-restamp discriminator. That prefix reports
graph-vs-INPUTS state. The bypassed-restamp arm really surfaces through
`run.py`'s drift branch as:

```text
[currency]   graphify: build-stamp — generated outputs out of sync with the stamp …
```

Both arms fired (0 lines vs 1), so the *mechanism* worked; the condition named
the wrong literal. Same class as the `"N passed"` trap. **If this round needs a
currency discriminator, use `build-stamp`, not `[graph]`.**

## Out of scope

The overflow valve. Anything this round proves it should not do goes here
rather than quietly expanding scope.

- Any dotfiles commit. The gap is measured, then written down here.
- A second or third peer tool. One approved tool, one fan-out.
- Closing any upstream tracked issue.
- Raising `GRAPHIFY_MAX_GRAPH_BYTES`.
- Building the truncation-reporting fix, if P1(a) shows one is needed. Report
  the finding and the estimated size; let the next round decide.
- **The three issues this round deliberately WORKS AROUND rather than fixes.**
  Each is named where it bites, and naming it is the whole obligation:
  **#103** (`kb-ship` refuses an empty-scoped-diff branch — worked around by
  this branch being forked off `206e6f5`), **#94** (`sources/**` outside every
  hk builtin — P4), **#13** (`Workflow` name resolution runs a stale cache —
  P5). Fixing any of them is a different round; each would need its own
  FAIL-direction proof, and #103's fix in particular touches the receipt gate
  this round's Preserve list protects.
- The rest of the standing backlog: **#93** `kb-extract.js` edge direction ·
  **#82** (deferred by Ray) · **#81** toolchain docs · **#67**, **#68**,
  **#62**–**#66**, **#34**.

## Hand-back — never report these as done

| Decision | Who | When |
|---|---|---|
| **which fourth peer tool** | Ray | P3, via `AskUserQuestion`, before any ingestion |
| secret rotation | Ray | raise ONCE, unprompted, at PROJECT completion — not at a round boundary |
| raising the graph size cap | Ray | if headroom runs out, stop and report |
| closing an upstream tracked issue | Ray | never unilaterally |

## Standing traps this repo has already paid for

Do not re-learn these:

- A **stubbed `_run`** means no fixture has a second writer, so no test can
  exhibit a bug about *other* writers. That blind spot hid two real defects in
  one round.
- **The guard can survive inside its own fix** — a TOCTOU where the check ran
  once and the destructive swap happened minutes later. Verify at the point of
  USE.
- Unquoted `--include=*.py` → zsh eats it → **all counts false zeros**.
- `grep … | head; echo $?` reads *head's* rc.
- A bare `graphify` on PATH may resolve a different version than the pinned
  **0.9.31**. Use `graphify_exe`.
- `rumdl fmt` will **split a long markdown table row**, silently un-tabling it.
- The hook guard scans **heredoc bodies** — prose containing `graphify <word>`
  gets denied. Use the Edit tool for file edits.
- Receipt report filenames need the **full** SHA; the body needs **≥12** chars.
- Ray is on **iOS**: `pbcopy` is useless. Hand him goal text **in a message**,
  and `diff` your reproduction against the committed file first.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo this round runs in.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the pinned tool whose 0.9.31 source P6 re-checks four issues against.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — the currency gap P6 measures; read only, never committed to.
- [topoteretes/cognee](https://github.com/topoteretes/cognee) — the indirect arm for #101's one-root hypothesis.
- [getzep/graphiti](https://github.com/getzep/graphiti) — fourth-tool candidate, to be re-verified live in P3.
- [oraios/serena](https://github.com/oraios/serena) — fourth-tool candidate, to be re-verified live in P3.
- [blarApp/blarify](https://github.com/blarApp/blarify) — fourth-tool candidate, to be re-verified live in P3.
- [Aider-AI/aider](https://github.com/Aider-AI/aider) — fourth-tool candidate, to be re-verified live in P3.
