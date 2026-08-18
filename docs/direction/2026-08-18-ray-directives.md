# Directives — 2026-08-18 (Ray, verbatim)

**Stored verbatim**, following `docs/direction/2026-08-17-ray-directives.md`, because
this directive's own first complaint is that requirements get lost between sessions.
Do not paraphrase, summarise, or "clean up" the text below — it is the artifact.
Analysis, status and open questions go in the sections *after* the verbatim block,
never inside it.

**This file must stay under `docs/direction/**`** — that path is formatter-exempt in
`hk.pkl` precisely because a spell-checker "fixing" a verbatim record edits what
someone said.

---

## VERBATIM

> /clear-prep
> option 1 but then we have to do the following:
>
> you are still not following instructions and losing requirements/instructions between sessions that /clear-prep is having issues w the handoff files
>
> we cannot do any graphify work on old stale versions as this will cause us to run on versions that could have outdated functionality or bugs
> - we need to enforce this can never happen again
> - right now the latest version is 0.9.46
> - our python library needs to handle and take into account that the graphify version will keep getting new versions as we keep working
>
> we need a full session review workflow sweep to aggregate all the issues and requirements missed and anything vague an agent can miss and fix all of these so we stop compounding mistakes and making it hard to get back to moving forward
> the list of issues need to be durably stored as github issues and/or remapped to a wayfinder map
>
> and we need to enforce reviewing all pr reivews from bots instead of ignoring them
>
> and we need to start getting ready to run /clear-prep once the context is at 20% (which right now is 200K tokens)
> - so that the handoff doesnt have to handle too much
> - and we need to enforce smaller tasks that can fit into this token budget
>
> and we ensure we dont lose any pending work on git worktrees and/or branches of from the backup directory
>
> and we need to ensure that all documentation and code is in a state that if a subscription plan gets depleted a humand and/or another ai llm agent can take over understanding current state, pending issues/tasks, gotchas, etc
>
> we need to prioritize what issues to fix right away that will prevent mistakes for us to move forward
> if possible fixing the issues in parallel if the chance of conflict is zero or can be pre-planned
>
> we need to enforce a zero tolerance on repeating mistakes
>
> we need to enforce not doing any work until all critical currency dependencies are up to date

The `option 1` above is Ray's answer to a question about **scope drift** in the corpus
run: *"Run it and let the gate refuse + retry"* — the staging gate already catches every
drifted chunk, so nothing wrong can merge; run the 58 chunks, let refused chunks fail,
then re-run just those.

---

## The ordering this directive imposes

The last line is a **gate on everything else**, and it is stated as one: *"not doing any
work until all critical currency dependencies are up to date."* So the sequence is not a
preference:

1. **Currency first.** `mise run kb-currency-check`, run 2026-08-18, reports **eight**
   pins behind upstream, not one: graphify `0.9.45 -> 0.9.46`, mise `2026.8.3 -> 2026.8.6`,
   hk `1.54.1 -> 1.55.0`, uv `0.12.3 -> 0.12.5`, ruff `0.16.2 -> 0.16.3`,
   ty `0.0.69 -> 0.0.72`, doppler `3.76.1 -> 3.76.5`, fnox `1.32.0 -> 1.33.0`. A ninth,
   `skillopt`, is pinned to a VCS revision and reports **NOT CHECKED** — unknown, not
   fine. Nothing else starts until these are resolved.
2. Then the session-review sweep, whose output is **durable GitHub issues** (and/or a
   wayfinder map), not a report.
3. Then the prioritised fixes, in parallel where conflict is provably zero.

## What each item is asking for, and what already exists

| # | Directive | Status here |
|---|---|---|
| 1 | `/clear-prep` loses requirements between sessions | The handoff is `.agent/plans/session-*.md`, which is **gitignored** — it does not survive a clone. That is a candidate root cause and is not yet fixed. |
| 2 | Never run graphify work on a stale version; the library must expect new versions continuously | `currency.toml` tracks graphify and `kb-currency-check` is offline+fast and DID report the drift — but nothing BLOCKS work on a stale pin, which is the gap this directive names. `kb_setup.currency.apply` is [recorded as unreachable for graphify](../../graphify-out/memory) — bump by hand. |
| 3 | Full session-review sweep → durable issues / wayfinder map | The workflow was rebuilt and committed this session (`.claude/workflows/session-review.js` + `kb-session-review` skill). It has **not been run** yet. |
| 4 | Review ALL PR bot reviews instead of ignoring them | Today CodeRabbit is **advisory and non-blocking** (`kb_setup.pr._ADVISORY_CHECKS`), and `Repowise / code health` was made advisory on #336. Reported, but routinely not acted on. |
| 5 | Prepare `/clear-prep` at 20% context (~200K of a 1M window); enforce smaller tasks | Nothing measures remaining context or bounds task size today. |
| 6 | Lose no pending work on worktrees / branches / the backup directory | Three worktrees exist under `../worktrees/`, plus ~20 local branches. Not audited this session. |
| 7 | Docs + code must let a human or another agent take over cold | Partly true (rules, skills, `docs/`), but the handoff being gitignored (item 1) directly undermines it. |
| 8 | Prioritise the issues that prevent further mistakes; parallelise where conflict is zero | Depends on item 3's output. |
| 9 | Zero tolerance on repeating mistakes | This session repeated two known classes: a wait condition satisfied by pre-existing state, and `git add -A` sweeping derived output into a commit. Both are already written down. |
| 10 | No work until critical currency deps are current | Blocks items 2–8. **Start here.** |

## Rulings, given by Ray 2026-08-18 in the same exchange

These were asked as `AskUserQuestion` and answered; they are recorded here rather than
left in a transcript, which is the whole subject of item 1.

- **Item 5 — the `/clear-prep` trigger is BOTH, whichever fires first.** The session
  token budget (exactly readable from inside a turn) AND an estimate of the 1M context
  window. Ray chose both over either, so a threshold that one measure misses is still
  caught by the other. Neither may be silently dropped for being harder to measure.
- **Item 3 — the sweep's output is GITHUB ISSUES.** Filed with `gh`, labelled and
  prioritised, so they survive any session and any clone. A wayfinder map may be layered
  on later; it is not a substitute, and `/mattpocock-skills:wayfinder` cannot be
  model-invoked so only Ray can produce one.
- **Item 10 — currency means ALL EIGHT pins, in one sweep**, not graphify alone. Ray
  chose the widest option explicitly, over "graphify first" and over "graphify plus the
  gate toolchain". So the gate does not lift until every pin above is resolved, and
  `skillopt`'s NOT-CHECKED state is part of that resolution rather than an exception.

---

## ADDENDUM — VERBATIM (Ray, same day, after PR #339 landed)

> option 1
>
> add this to what needs to be handled in the next session after running /clear
>
> these need to be added as critical currency dependencies if they have not been added already and must always be on the latest version:
> - uv
> - hk
> - github:agent-sh/agnix
> - fnox
> - doppler
> - antigravity-cli
> - codex
> - from pyproject.toml:
>   - anthropic
>   - graphifyy
>   - msgspec
>   - skillopt
>   - datamodel-code-generator
>   - ruff
>   - ty
>   - structlog
>   - trafilatura
>   - pytest
>   - pytest-xdist
> - provide/suggest other dependencies that are at the core of what this project is working on that needs expert knowledge
>
> review if we use rumdl right now and/or if we should
> - if not needed, just remove from mise.toml for now and any other references to it
>
> - we should replace gitleask with betterleaks
>   - we can start w adding it as another hk builtin and run it in parallel with gitleaks until we are 100% confident we are losing features
>
> add this as another hk builtin checker for the project:
> - https://github.com/mongodb/kingfisher
>
> - create a workflow that revieews every hk builtins (do not skip)
>   - asses which ones we are missing for this project
>   - if multiple exist that provide the samw functionality it should pick the native/system one (rust/c++/etc)
>     - for example we should replace gitleaks with betterleaks
>   - each hk builtin we use becomes a critical currency depenency
>
> the output of these commands should never show anything stale at the top level:
> - mise outdated -b -J
> - uv tree --outdated --show-sizes --all-groups --format json
>
>
> can kb-arms be run in parallel?

### The answer to the question, measured

**Not today, and one of the two reasons is fundamental rather than a missing flag.**

`kb_setup.arms` runs a strictly serial `for arm in ordered:` loop
(`arms.py:466`), and each arm **edits the working tree in place**, runs the
suite, then restores. Two arms in flight would be mutating the same files at the
same time, so their verdicts would describe a tree neither of them wrote. That is
not a concurrency setting; it is the design.

Two directions that WOULD work and are worth pricing next round:

1. **Parallelise INSIDE each arm.** `_PYTEST_FLAGS` is
   `("-q", "--no-header", "-rf", "-p", "no:cacheprovider")` — no `-n auto`, while
   `mise run test` uses it. On a 5-arm spec over two large corpus suites this
   session, each arm took minutes; xdist would cut the wall clock per arm without
   touching the serial invariant. The caution is real though: this repo has
   already been bitten by a wall-clock assertion that passed alone and failed
   under `-n auto`, so a suite with timing-sensitive tests must be measured, not
   assumed.
2. **Parallelise ACROSS arms in isolated worktrees.** One git worktree per arm
   removes the shared-tree problem entirely, at ~200-500 ms and a disk copy each.
   That is the honest way to get across-arm parallelism, and it is exactly what
   `Agent`'s `isolation: "worktree"` does for subagents.

Neither is a one-line change, so both are recorded here rather than attempted at
the end of a long session.

### What this addendum adds to the next round's list

- **A named currency roster**, 18 entries, that must be tracked and current.
  Re-derived from `currency.toml` 2026-08-18 rather than repeated from a prior
  note: it defines **12** `[tool.*]` sections (graphify, ffmpeg, mise,
  claude-code, hk, fnox, doppler, skillopt, uv, ruff, ty, codex), and **9 of the
  18** in Ray's roster are ALREADY tracked (uv, hk, fnox, doppler, codex,
  graphify, skillopt, ruff, ty). The **9 missing** are: agnix, antigravity-cli,
  anthropic, msgspec, datamodel-code-generator, structlog, trafilatura, pytest,
  pytest-xdist. An earlier draft of this line said "tracks 4 of ~14 pins",
  inherited from a work-memory note and never re-derived — the cold lane caught
  it, and it is the inherited-number failure `probes-need-a-control-arm.md`
  rule 6 names.
- **Two new top-level staleness gates**: `mise outdated -b -J` and
  `uv tree --outdated --show-sizes --all-groups --format json` must both come
  back clean at the top level.
- **`rumdl`: decide use-or-remove.** It runs today as two hk steps
  (`rumdl`, `rumdl_format`) over 188 files.
- **`gitleaks` -> `betterleaks`**, added in PARALLEL first and only swapped once
  no feature loss is confirmed. Note this repo's gitleaks scope is load-bearing:
  `.gitleaks.toml` and `hk.pkl`'s `proseExclude` are what keep the
  review-exempt paths scanner-visible, and two tests pin that.
- **`mongodb/kingfisher`** as an additional hk builtin.
- **A workflow that reviews EVERY hk builtin** — no skipping — proposing the ones
  this project lacks, preferring the native/system implementation where several
  overlap, and promoting every adopted builtin to a tracked currency dependency.

---

## Rulings at clear-prep, 2026-08-18 (asked and answered)

- **NEXT SESSION'S FIRST TASK, in Ray's words:** *"improving the session review
  workflow and running it to aggregate the list of issues we need to handle to
  stop making mistakes and applying it to the project"*.

  **This takes precedence over the currency gate for the FIRST task**, and the
  precedence is recorded rather than reconciled, because the directive above says
  *"not doing any work until all critical currency dependencies are up to date"*.
  Both are Ray's; the later one is the operative instruction for what to start
  with. Do not re-litigate the ordering — improve the workflow, run it, file the
  issues, apply them. Currency follows, and its own ordering is unchanged.

- **THE CORPUS RUN IS RE-SCOPED, NOT SCHEDULED.** Ray chose *"the 5-file chunking
  may be wrong"* over running it. Chunk 1's drift came from `ARCHITECTURE.md` and
  `CHANGELOG.md` DESCRIBING 26 other modules, so before spending the projected
  ~77 USD (measured 1.32 USD/chunk x 58) the chunk boundaries themselves are the
  question — not whether to accept a refuse-and-retry loop. The earlier ruling
  *"run it and let the gate refuse + retry"* is therefore SUPERSEDED for the run
  itself; what survives from it is that the staging gate is trusted to catch
  drift, which is what makes re-scoping safe to do deliberately rather than
  urgently.

---

## SECOND ADDENDUM — VERBATIM (Ray, same day, as comments on the design artifact)

Four comments left on the published design artifact
`https://claude.ai/code/artifact/59a537df-bb8e-4970-a96d-5dcd102d5a1e`. Recorded
here rather than only in the artifact's comment thread because an artifact is not
something a session loads, and this file is — which is item 1 of the directive
above, applied to itself.

> and once we do complete the sources/graphify deep extraction/reflections/generated artifacts
> and have expert level understanding of graphify and a graphify expert agent
> we need to really enforce that all agents use graphify skills and the graphify query/explain tools as the first place to research and/or navigate the project's code and documentation

> make sure we are not creating hand written models and/or code that can be generated from the latest datamodel-code-generator tool and/or some other code generation tool

> can we enable timestamps in the telemetry to know when exactly messages/commands were being run?

> can we use these sdks instead?
> - https://github.com/anthropics/anthropic-sdk-python
> - https://github.com/anthropics/claude-agent-sdk-python

And, in the same exchange, on whether to build the proposed selector:

> option 1
> but pending review of my artifacts comments

---

## What the second addendum is asking for

- **graphify-first, enforced for AGENTS — not just for this session.** The
  existing `kb_setup.graph_first` deny is scoped to the Bash and Grep calls of
  the session that runs it; it says nothing about what a spawned subagent does,
  and the roster's six agents are instructed to query the graph first only in
  PROSE, which this repo has measured at 0-of-19 compliance. The directive is
  explicitly SEQUENCED — it lands *after* the deep extraction, the reflections,
  the generated artifacts and a graphify expert agent exist. It is not a task for
  today; it is the acceptance criterion that campaign is aimed at, and it is
  recorded now so that finishing the campaign does not look like finishing the
  work.
- **Codegen before hand-authoring.** Any new data contract — the session-selector
  JSON among them — goes through this repo's existing codegen path rather than a
  hand-written model. What that path is, and where hand-written contracts still
  sit, is being measured rather than assumed.
- **Telemetry as a clock.** Raised against the finding that file `mtime` mis-dates
  a resumed session (20 of 238 transcripts, worst 119.6 h). Whether telemetry
  already answers it, and at what retention cost, is being measured.
- **The SDKs are a challenge to a PREMISE, and are treated as one.** The claim
  *"only the model can spawn Claude agents"* (`.claude/workflows/session-review.js:27-31`)
  is what puts the fan-out in a workflow instead of a `kb_setup` module. If an SDK
  refutes it, the seam moves and `zero-bash-logic.md`'s reach grows. It is being
  settled against the installed SDKs and this repo's auth and billing model
  before anything is built on either answer.
