# Lane: contradicted — iteration 1 self-audit

Scope: the session that just shipped `f772f5eb` (session-review workflow rewrite)
on branch `docs-directive-addendum`, plus the standing rule/skill/CLAUDE.md corpus
those changes touch.

---

## FINDING 1 (HIGH) — the roster table says `kb-synthesist` runs on opus; the new code runs it primarily on `fable`

**Both sides of the contradiction:**

- `CLAUDE.md:180` (unchanged by this session's `f772f5eb`, which touched the same
  line only to bump the graphify version string):
  > "`agents/` is the standing roster — 6 subagents, each declaring `model` +
  > `effort`: `kb-advisor` (fable) consulted only at commitment boundaries;
  > **`kb-adversarial-verifier` and `kb-synthesist` (opus) for judgment**;
  > `kb-corpus-curator`, `kb-tool-researcher` and `kb-extraction-worker`
  > (sonnet) for execution."
- `.claude/agents/kb-synthesist.md:1-4` (frontmatter, unchanged this session):
  `model: opus`, `effort: high`.
- `.claude/workflows/session-review.js:505-514` (NEW this session, `f772f5eb`):
  ```js
  async function judge(prompt, opts) {
    const first = await agent(prompt, { ...opts, model: 'fable', effort: 'high' })
    if (first) return { value: first, ranOn: 'fable/high' }
    log('FABLE UNAVAILABLE — re-dispatching to opus at xhigh. THIS RUN FELL BACK.')
    ...
  ```
  called at `session-review.js:561`: `agent(prompt, { label: 'synthesise',
  phase: 'Synthesise', agentType: 'kb-synthesist' })` — i.e. the agent-type
  identity is `kb-synthesist`, but the model actually dispatched is `fable`
  first, `opus` only as fallback.

**The contradiction is not merely stale prose vs. new code — it is self-aware
and still left standing.** The same commit's own comment at
`session-review.js:508-509` states the deviation explicitly: *"Fable for
judgment, Opus if Fable is gone... `xhigh` on the fallback is deliberately
ABOVE doctrine's same-effort rule"* — but the "doctrine" it cites
(`.claude/agents/kb-advisor.md:79-82`, *"the caller re-dispatches this same
brief to an Opus subagent at the **same effort**"*) is written for the
`kb-advisor` agent specifically, not `kb-synthesist`, so the new code is
inventing a second, undocumented fallback policy (fable→opus at a **raised**
effort) for an agent CLAUDE.md still describes as running on opus outright.

**Where this was at least partially caught, and where it wasn't:** this
session's own `.claude/skills/kb-session-review/SKILL.md` update (same commit)
correctly documents the new behaviour — "Synthesise | `kb-synthesist` on
**`fable`**, falling back to `opus`/`xhigh`" — so the skill and the code agree
with each other. **`CLAUDE.md:180` and `kb-synthesist.md`'s own frontmatter
were not updated to match**, so a reader following the roster table (root
CLAUDE.md, the single most-loaded file in the project) is told a materially
wrong fact about the one agent this exact self-audit run's synthesis step
depends on.

**Why this matters for THIS iteration specifically:** the synthesis phase of
the very workflow reviewing this session is not running the model CLAUDE.md
says it runs on. If `fable` silently degrades output quality relative to
`opus`, nothing in the roster description would lead a reader to suspect it.

**Remedy:** either (a) update `CLAUDE.md:180` to say `kb-synthesist` runs on
`fable` (falling back to opus/xhigh) for the session-review workflow
specifically — noting the per-invocation override — or (b) if `fable`-first was
not an intentional roster change (only a workflow-local optimization), rename
the dispatch's `agentType` away from `kb-synthesist` so the roster claim stays
true for the *agent*, and let the workflow's own model choice be workflow-local
and undocumented-at-roster-level on purpose. Either way, `CLAUDE.md:180`
currently states something the shipped code does not do.

**Control arm:** confirmed by reading the actual frontmatter (`model: opus`)
and the actual dispatch call (`model: 'fable'`) side by side — not an inference
from prose on either side.

---

## FINDING 2 (HIGH) — a load-bearing design-decision comment cites `workflows.md:316` and `:318` for a caching mechanism the cited source does not contain, anywhere

**The claim**, `.claude/workflows/session-review.js` (NEW this session,
`f772f5eb`, in the comment block explaining why `const: lane.key` was dropped
from the sweep schema — lines land around 315-330 in the current file, quoting
verbatim):

> "`workflows.md:316` makes the OUTPUT SCHEMA part of the cache key: agents
> share a prefix only when model, effort, agent type, tools, output schema and
> cwd all match. Pinning the key per lane gave eight lanes eight schemas, so the
> native fan-out prefix hold (`:318` — hold all but the first, release together
> once the first response begins) could never engage..."

**What the cited source actually says.** This repo's only ingested copy of
`workflows.md` is `sources/agent-harness-docs/docs/claude-code/workflows.md`
(pinned via `sources/agent-harness-docs.manifest`,
`commit = 33aef930acb2e56154a056dd7e1dfd08b9a3cf3e`). At the cited lines:

```
$ sed -n '316p;318p' sources/agent-harness-docs/docs/claude-code/workflows.md
The runtime applies the following constraints:
| Constraint  | Why  |
```

— the table header for the "Behavior and limits" section (16-concurrent-agent
cap, 1,000-agent total cap, no mid-run input, etc.). Nothing about caching,
prompt-cache keys, model/effort/agent-type/tools/schema/cwd matching, or a
"prefix hold" mechanism appears at either line.

**Grepped the whole 404-line file for every term the comment uses** —
`cache key`, `hold all`, `prefix hold`, `output schema`, `release together` —
all **zero hits**. `grep -c -i "cache"` over the whole file returns 3 hits, all
in the "Resume after a pause" section (`workflows.md:332,337,339`), which
describes something different: agents that finished return cached RESULTS on
resume, and replay stops at the first agent that didn't finish — nothing about
a schema-keyed prefix that "holds" a fan-out.

**Control arm.** `grep -c -i resume` over the same file returns 9 (so the grep
tool and file are both fine — the file just does not contain the cited
mechanism). `grep -rln "maxdepth 4"` over the whole repo correctly finds the
one place that string is genuinely documented
(`.claude/rules/probes-need-a-control-arm.md`), confirming the same grep
methodology surfaces a real citation when one exists; it surfaces nothing for
this one.

**Why this is a "contradicted instructions" finding, not just an error.** The
comment is not decorative — it is the stated reason the schema was changed
from `const: lane.key` to a plain string, i.e. it is offered as the
justification for a currently-shipped behavior change. `docs/direction`'s
sibling rule `probes-need-a-control-arm.md` names exactly this failure shape
("a stated condition... is also what makes a fact falsifiable later") and this
comment is unfalsifiable-until-checked in exactly the way that rule warns
about: prose defending a choice, citing a line number as if it had been read,
where the line number does not support the claim.

**What is NOT being claimed here:** the underlying mechanism (schema affects
whether Claude Code's live workflow runtime can share a prompt-cache prefix
across parallel agents) may well be true of the *current* product — this repo's
vendored doc could be stale relative to the live harness, and staleness of a
vendored doc is a known, tracked category (`tool-currency-and-native-first.md`).
But that is a *different* justification than "workflows.md:316/:318 says so",
and the comment as written asserts the citation, not "I believe this is true of
the current product but our vendored copy predates it."

**Remedy:** either re-derive the claim from the CURRENT product docs (fetch
`workflows.md` fresh per `research-doc-sources.md`'s chain and re-ingest if it
now documents this) and fix the citation, or drop the specific line numbers and
state the mechanism as an unverified belief per
`probes-need-a-control-arm.md` rule 6 ("mark it explicitly as unverified").

---

## FINDING 3 (MEDIUM) — `.agent/telemetry/` is written by config, at 1.8 GB / ~4,300 files, and is absent from the rule that enumerates every legal `.agent/` path

`.claude/rules/agent-artifact-conventions.md` "The local tree (gitignored)"
table lists exactly seven paths as everything that may exist under `.agent/`:
`state/`, `notepad.md`, `plans/`, `logs/`, `brain-audit.md`,
`kb/review/receipt-<sha>.json`, `kb/review/reports/review-<sha>-<lane>.md`.
Rule 1 of the same file: *"No ad-hoc directories... Map your artifact to the
closest one [in the table]."*

`.agent/telemetry/` is not in that table, yet it is real, large, and actively
written by declared config, not by an agent going off-script:

```
$ du -sh .agent/telemetry && find .agent/telemetry -type f | wc -l
1.8G	.agent/telemetry
4299 (dirs+files listed by `ls`; see raw find count for files only)
```

`.claude/settings.json`'s `env` block sets
`"OTEL_LOG_RAW_API_BODIES": "file:.agent/telemetry/"` (plus
`OTEL_LOG_USER_PROMPTS`/`_ASSISTANT_RESPONSES`/`_TOOL_DETAILS`/`_TOOL_CONTENT`,
all `"1"`), and `.claude/settings.json` also wires a `PreToolUse`(?) — actually
a scheduled — task `mise run kb-telemetry-prune` (`.claude/settings.json:56`),
confirming this is deliberate, maintained infrastructure, not an accident. The
working tree also currently carries an uncommitted `.codex/config.toml` edit
(not part of `f772f5eb`) adding the identical six `OTEL_*` keys to bring Codex
into parity with Claude's settings — further evidence this is intentional,
ongoing work, not a one-off.

**The contradiction:** a rule stating "no ad-hoc directories... any path not
listed above [is forbidden]" is being violated, continuously, by declared
project config — 1.8 GB of it — while the rule's own table has not been
updated to acknowledge the path exists. Either the rule is wrong (telemetry
should be added to the table, with its own retention/prune note, mirroring how
the table already documents `kb/gates/` and `kb/review/`), or the telemetry
mechanism itself is the thing that should not exist in its current undocumented
form. Right now neither has happened — the rule and the config simply disagree,
and a reader trusting the rule's table as exhaustive (which rule 1 tells them
to do) would not know this 1.8 GB path exists at all.

This is not new to this session (`kb-telemetry-prune` and the OTEL keys predate
`f772f5eb`, per prior work-memory: "raw-body telemetry is live and costs ~1.17
MB/request", already flagged in `MEMORY.md`), but it remains live and
unresolved as of this iteration, and it is exactly the shape this lane is
asked to find: a rule that says the repo does not do something the repo
continuously does.

**Remedy:** add a `.agent/telemetry/` row to `agent-artifact-conventions.md`'s
table (owner: telemetry OTEL config; retention: pruned by
`mise run kb-telemetry-prune`), or decide the mechanism should be re-scoped
and update the config instead. Either fixes the contradiction; leaving both as
they are does not.

---

## COVERAGE

**Reached and analysed:**
- The full diff of `f772f5eb` (`.claude/workflows/session-review.js`,
  `.claude/skills/kb-session-review/SKILL.md`, the `.agents/` mirror of that
  skill, `CLAUDE.md`).
- Cross-referenced every model/effort claim in the new code against
  `.claude/agents/kb-synthesist.md`, `.claude/agents/kb-adversarial-verifier.md`,
  `.claude/agents/kb-advisor.md`, and `CLAUDE.md`'s roster line.
- Verified the `workflows.md:316`/`:318` citation against the actual vendored
  source file, with a grep control arm proving the grep methodology itself is
  sound.
- Verified `pyproject.toml`'s graphify pin (0.9.45) now matches CLAUDE.md's
  corrected claim (was 0.9.44, now 0.9.45) — consistent, not a finding.
- Confirmed the lane count is genuinely 8 (`grep -c "key: '"` in
  `session-review.js`), matching both the commit message's "six lanes ->
  eight" fix and the SKILL.md text.
- Checked `.agent/telemetry/`'s size/config wiring against
  `agent-artifact-conventions.md`'s enumerated table.
- Checked whether the `-maxdepth 6`/depth-7 claim in the new `REFUTE_CONTRACT`
  text is fabricated the same way Finding 2 is: **it is not** — `grep -c
  "maxdepth 6"` against this session's own transcript returns 22 hits (vs. 0
  for "maxdepth 4", the *other*, older documented incident), so this specific
  claim is real to this session even though it has not yet been persisted to a
  review report anywhere on disk. Not reported as a contradiction; flagged here
  only so the next lane does not have to re-derive it. (This gap — an
  in-session finding not yet persisted per `agent-report-persistence.md` — is
  arguably a "forgotten"/"pending-work" lane finding, not "contradicted"; left
  for those lanes.)

**Opened but not finished analysing:**
- Whether `.agents/skills/**` (the hand-mirrored copy of `.claude/skills/**`,
  9 of 10 dirs still without a generator per the 2026-08-17 report) drifted
  again in THIS session's edit to `kb-session-review/SKILL.md` — I confirmed
  both copies changed by the same +30 lines in `f772f5eb`'s stat output but did
  not byte-diff them against each other to confirm they are now identical.
- The full text of `.claude/rules/*.md` beyond the ones cited above — I did not
  sweep every rule file against every workflow/skill file pairwise; I followed
  the highest-signal leads from the actual diff first (per the task's stated
  priority: findings that would cause a WRONG or STALLED execution of the
  session-review plan specifically).
- `.claude/agents/kb-corpus-curator.md`, `kb-tool-researcher.md`,
  `kb-extraction-worker.md` frontmatter were not individually checked against
  CLAUDE.md's "(sonnet) for execution" claim — plausible but unverified.

**Never reached:**
- `python/src/kb_setup/**` for contradictions between code and its own
  docstrings/comments (out of scope for this pass — focused on the freshly
  shipped workflow/skill/CLAUDE.md surface per the task's stated priority).
- The other 8 review-report files listed in the handoff
  (`.agent/kb/review/reports/review-*-cold.md` for #337/#338/#339) — not
  cross-read against current rule text for staleness.
- `docs/goals/`, `docs/currency/`, and the currency roster items themselves —
  those are explicitly the "already found" / other-lane territory per the task
  prompt (currency gate, roster) and were left to whichever lane owns that.

## GitHub repos touched

_None._ (No external repo source or docs were fetched during this pass — all
evidence came from files already vendored/committed in this repository.)
