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

## Addendum, same day (session `kb-20260821.03`, at the round-2 review bound) — VERBATIM

Asked (AskUserQuestion) whether to run a bounded round 3 for the confirmed
cold-review residuals, ship-and-file, or fix truths only:

> /clear-prep
>
> option 1 on new session after /clear
>
> context is getting full. But, run session-review workflow:
> - to find all issues/repeated mistakes and manual commands that should be wrapped in a modular skill -> mise task -> python library module/function
> - find all occurrences of a skill not triggering
> - should have triggered or requested a /clear-prep to have been run since we went over the 20% context of current model
> - make sure we the goal is to complete the graphify full deep extraction/reflection/generated artifacts

**Decisions recorded:** round 3 (option 1 = one bounded codex lane for the
truth/correctness residuals plus the two cheap design fixes — lowercase proxy
names in the refusal/exemption sets, a typed CLI refusal instead of a traceback
— then one cold pass, then re-plan / authority (k) / sweeps / gates / kb-review /
kb-ship) runs in the NEXT session after `/clear`. `/clear-prep` is
user-invocable only, so the session prepared the handoff inputs and asked Ray to
run it. The session-review workflow is to be run with the four foci above, and
**a /clear-prep should have been requested when context passed 20% of the
model's window** — recorded as a standing expectation.

Also decided this session (AskUserQuestion, all "Recommended"): re-run the slice
at 0.9.48 (G2); #426 = derive the runtime and refuse at verify AND execute; the
cap follows the ONE-FULL-RESTART rule (first ≈$140 at 58 chunks, re-derived to
$63 at the measured 26 post-dedupe chunks); #414 dedupe IN the bundle; NO new
lint suppression — refactor instead.

## Second addendum, same day (session `kb-20260821.03`, at `/clear-prep` step 0) — VERBATIM

Asked "what should I record before /clear?" (AskUserQuestion). Ray:

> 1. the /clear-prep skill should be refactored to call the session-review workflow
>    - so every step it does should become a step/lane in the session-review workflow
>    - steps that i think are still missing:
>      - finding the cause of what is writing to .codex/config.toml and adding claude telemetry lines
>      - finding manaul commands being run that are not wrapped in modular skill(s) -> mise task(s) -> python library module(s)/function(s)
>      - finding cases where a skill isn't being triggered and manual commands are being done and/or not following a predefined skill's steps
>        - all skills should be creeated via /skill-creator and use /mattpocock-skills:writing-for-agents
>      - identify issues/repeated mistakes that need to be escalated as critical and need to be fixed immediately either in the current session if there is enough headroom in the current context or most likely as the immediate next tasks in the next session after running /clear
>      - identify code that should have been generated using datamodel-code-generator or some other code generation tool
>        - especially cases where an enum should have been used instead of a string literal
>    - it should also be able to be triggered by an agent so that it runs when context hits over 20%
>      - so toggle this flag: 'disable-model-invocation: true' in .claude/skills/clear-prep/SKILL.md
>    - there are a lot more requests that i've made that are still either being lost and/or have not been run through the aggregation/triage step of the session-review workflow
>    - use graphify as ai agent memory with regards to the results the session-review workflow
>      - should we do a deep extraction and reflection and generate artifacts from its final output or on its intermediate steps
>    - but self-reflection/self-correction/self-healing/self-optimizing the /clear-prep skill needs to be automated
> 2. all the workflows in this project should have graphify ingested/deep extracted/reflected/generated artifacts
>    - workflows:
>      - .claude/workflows/kb-extract.js
>      - .claude/workflows/kb-tool-review.js
>      - .claude/workflows/session-review.js
>    - should be using this for analysis:
>      - AST tree sitter from graphify
>      - LSP
>   - generate visual document(s) explaining the workflow
>     - show components and their relationships/dependencies
>     - show architecture/workflow/sequence diagrams
>       - use appropriate diagramming tool(s) like mermaid/tldr/excalidraw/etc
>     - must update/say in synce when the code changes
>       - research and find tools that can automate this step
>         - provide cited resources on what the tools are with pros/cons and which one should be chosen
>   - same synced visual documents should be done for this project's python code also

**Decisions recorded at the same step (AskUserQuestion):** after round 3 lands, the
session STOPS and asks go/no-go before the first provider call; the /clear-prep
DENY guard + #428/#429/#430 ship as a SMALL PR BEFORE round 3. The
`disable-model-invocation` flag on clear-prep was flipped in this session per the
directive above (the banner in the skill updated); the rest is filed as two epics
(see the handoff) for the session-review aggregation/triage step.
