# Ray's directives — 2026-08-21 (VERBATIM)

Written the same day, at `/clear-prep`. Session `11db65d3`.

## The round's opening choice

> C4

Chosen from a `kb-resume` reconciliation that offered settling the plan-authority
blockers first versus reviewing/shipping first. **Settled** in `aa590ac5`:
`verify` → `execution_authorized: true`, suite rc=0.

## On the PR

> Wait for bots

**Honoured**, and it paid for itself: CodeRabbit found a live break in
`_runtime_reasons` that the cold cross-family lane and the author had both
missed. Fixed in `9dfc1255`, armed 5/5.

## The clear-prep instruction — VERBATIM

> Run the session-review workflow on all the sessions and addendums we havent done so far
> The synthesizer needs to focus on making sure we have all pending issues/missing requirements ready before the full deep extraction and reflection and generated artifacts on the graphify cloned repo pinned to the latest graphify version
> Especially the requests i made regarding tracking model/effort on each file extracted so we have a history of it when we have to rerun it on newer graphify releases and automating the process

### The decisions taken under it, so the next round does not re-ask

- **Run it NOW**, in-session, rather than handing it to a fresh context — because
  the handoff should be shaped by its findings.
- **Window:** deep from the first session born after the previous review was
  written (`2026-08-17T21:24Z`) to now — 14 non-trivial sessions, 51.9 MB.
  Ray asked for a *researched* boundary rather than a guessed one; the measured
  boundary is that review's own mtime, not a calendar date.
- **Caps:** per-lane, not global. The previous run's global cap was consumed by
  two lanes and left two entire lanes unverified while reading as if they had
  passed. A completeness critic reports what was not covered.
- **Output:** report **and file issues** now; **implement after `/clear`.**

### The requirement this is aimed at

Ray's model/effort tracking request is already designed as **#411** — one row per
`(source, content sha256)` recording model, effort, `deep_mode`, `max_turns`,
graphify version and adapter hash, plus the SKIPPED files with their reason.
Keyed on **content hash rather than path**, so a future graphify release is a
**delta** rather than a full re-run, which is the "automating the process" half.

Ray's own ruling on it, 2026-08-20: **design + issue now, build as its own
reviewed change**, with the immediate graphify run carrying a minimal inline
record. That fork — build it first, or run with an inline record — is the
question the synthesist was pointed at.

## Two further directives, same session, after the workflow launched

### On the session-review workflow itself — VERBATIM

> i think the session review workflow is missing a lane on how to actually self-improve/self-heal/self-optimize the workflow itself and the subagents and the each subagent's settings/tools/etc

Filed as **#423**. Ray's decisions when asked: run it as a **focused follow-up**
after a session-review completes, not as a lane inside one — so it reads that
run's real telemetry rather than reasoning about the design in the abstract — and
its authority is to **propose AND build the measurement harness**.

He is right that the gap is real. Every lane of the 2026-08-21 run pointed at the
REPO; none pointed at the INSTRUMENT. The three defects this project has already
paid for in its own fan-outs — a GLOBAL verification cap that starved two whole
lanes, a per-item `const` output schema that gave N agents N prompt-cache
prefixes, and a run that died at 78 agents before tiering to 23 — were every one
of them found by accident, after the fact.

### On what happens after the extraction — VERBATIM

> and after we finally complete the deep extraction/reflection/aftifacts of the graphify cloned repo we need to do the following:
> - research how to add the session review outputs into graphify
> - enforce the session review subagents use the specialized graphify subagent
> - what graphify tooling should the other subagents use
>
> if we can use graphify as an ai agent memory layer and/or what other ai agent memory tools/services/sdks/libraries/etc we should be using

Filed as **#424**, with the sequencing Ray states: this is AFTER the deep
extraction, and is not a reason to delay it.

Two items were measured while filing and are already answered:

- The 2026-08-21 lanes ran as the DEFAULT `workflow-subagent` — no `agentType`
  was passed, so `.claude/agents/` was never consulted at all.
- All six roster agents mention `graphify` between 3 and 25 times, and **zero**
  name any `mcp__graphify__*` tool, `ingest_turns` or `recall`.

⚠️ The memory-layer question has an INHERITED prior answer (graphify's
`ingest_turns`/`recall` unused, 0 against a control of 19 for `save-result`,
rated above ten external candidates). It must be re-derived or labelled
unverified, never restated as a finding.
