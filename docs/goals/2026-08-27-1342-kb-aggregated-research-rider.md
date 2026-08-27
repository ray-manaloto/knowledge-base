# Rider — Aggregated (2026-08-27, 13:42)

Serves `docs/goals/2026-08-27-1342-kb-aggregated-research-goal.md`. All paths absolute
from the repo root. It supersedes nothing in prior riders
(`2026-07-27-1702-kb-redaction-legibility-rider.md`,
`2026-07-31-1348-kb-fluent-stale-graph-rider.md`,
`2026-07-31-2056-kb-navigable-graph-rider.md`,
`2026-08-01-2116-kb-settled-claims-rider.md`) — their invariants still apply.

**This pair also breaks a 26-day silence.** No goal+rider has been authored since
2026-08-01. Every round from 2026-08-02 to 2026-08-27 ran without one, and in that
window the backlog went from 36 open issues to 294.

---

## Scope decision — is this one round?

Yes, and the headline word survives the test because the three deliverables are one
end state. A skill that has never run is a document, not an instrument; #509 is
only *proven* by artifacts it produced. So "the aggregated-research skill exists
**and has answered the two questions that prove it**" is a single state of the world.

The two questions are not arbitrary. The first (P3) is about the skill itself —
does it already exist, and what should be folded in — and its honest outcome may be
*adopt something else and delete most of what P2 built*. The second (P4) is the
team question. Running the self-referential one FIRST is deliberate: it is the only
ordering in which P4 gets the strongest available instrument rather than whatever
P2 happened to produce. (Ray, 2026-08-27, added after the first draft of this pair.)

**What was split out, and why:**

| Split out | Where it went | Why not here |
|---|---|---|
| The substrate (`.mcp.json` binding, ingesting our code + doctrine) | Its own round, after the team triage | Ray's Q14. A second headline word (`Reachable`) — `kb-goal-check` rejects two. |
| Triaging the 294 open issues | Its own round, run by the team this round designs | Ray's Q13: *"will have an optimized agent team triage the issues properly as its own round."* |
| Adopting the recommended team | Not a round — a Ray decision | The report is the deliverable. See Hand-back. |
| Federating the graph (#130) | Deferred, unscheduled | Depends on the substrate round's findings. |
| The 10 stranded worktrees | Deferred, unscheduled | Ten arbitrations, each a judgement call; unrelated to this round. |

## The evaluator constraint

`/goal`'s evaluator does not call tools. It sees only what Claude has already
written into the conversation. Every verification item is therefore a **string a
Haiku-class reader can find**, not a state of the repo. This is why item 2 quotes
`skill-lint`'s output verbatim rather than saying "the lint passes", and why
sentinels carry `@ <sha>` — a bare sentinel is satisfiable by the goal text itself.

## Preserve list, in full

| What | Where | Why |
|---|---|---|
| The six standing agents | `.claude/agents/*.md` | This round *researches* what should replace them. Editing them mid-research contaminates the question, and the 2026-08-06 roster synthesis is the baseline the new report must be compared against. |
| Every rule file | `.claude/rules/**` | They are the constraints the skill must encode, not material to edit. |
| The five Bash guards | `kb_setup.hook_guard`, `check_first`, `graph_first`, `absent_binary`, `secret_guard` | Each took a measured violation rate to earn. A research round has no business touching enforcement. |
| Tool pins | `mise.toml` `[tools]` | A pin move stales every line citation (#516). Not this round's job. |
| The corpus | `sources/**`, `graphify-out/**` except `memory/` | Ingestion is the substrate round. |
| This session's artifacts | `docs/artifacts/the-116-second-blackout.html`, `four-graphs-and-a-backlog.html`, `the-corpus-cannot-answer.html` | Published; people may have acted on them. Corrections go *on* the page, never over it. |
| Prior goal pairs | `docs/goals/*-goal.md`, `*-rider.md` | The record of what was tried. `*-goal.md` is excluded from hk's md builtins because its bytes ARE the payload. |

**Why the preserve list matters here specifically.** The cheapest way to satisfy
"the skill's research is high quality" is to narrow what counts as research until
the existing answer qualifies. The cheapest way to satisfy "the team is optimal"
is to declare the current six-agent roster optimal and stop. Both are Goodhart,
both are one lazy step away, and the preserve list is what makes them visible.

## Posture, expanded

- **No issue mutation.** Not a close, not a label, not a comment. The backlog is
  measured (`.agent/kb/reports/agents/backlog-audit.md`) and the next round acts
  on it. A round that starts closing issues will spend itself doing that.
- **No substrate work.** `.mcp.json` stays as it is even though it is wrong, and
  even though fixing it is one line. Ray sequenced it deliberately.
- **No graph rebuild.** `graphify-out/.build-failure.json` shows extract failing
  closed; #397 owns that. Attempting it here burns the round.
- **No new agent definitions.** The output is a *report* recommending a team.
- **`agy` budget: one call, maximum, and it must be named.** Ray, this session:
  *"the antigravity/gemini subscription for agy is very limited… so the agy
  subscription tokens deplete quickly."* Treat it as a scarce third opinion, not a
  routine reviewer — which is a change from how this round's predecessor used it
  (two antigravity cold reviews).
- **`grok` is not installed.** Any doctrine that routes to it is stale; do not
  follow it and do not fix it here.

## The question this round answers

**Ray restated it 2026-08-27, after the first draft, and the restatement is the
real question — the earlier "what roles" framing was the wrong one:**

> "one thing we are struggling w is the communication between claude and codex
> models which seems to be fragile and slow"
> "we are claude first (via its tui and claude desktop app) and will offload to
> codex models for code execution when it makes sense"
> "fable 5 tokens are limited but very powerful, we want to use it sparingly"
> "there are many articles and anthropic provides examples and best practices on
> how to use it properly and other articles on how to pair claude and codex
> models together"

So the question is **not** "which roles should exist". A roster is downstream of a
working interface, and this repo already has a roster (six agents, shipped
2026-08-06) built on top of an interface nobody has characterised. The question is:

**"How should a Claude-first session hand work to Codex and get it back, such that
the handoff is neither fragile nor slow — and where in that loop does a scarce
Fable 5 budget actually buy something?"**

Answered *by the skill*, from Anthropic's own published best practices and the
Claude+Codex pairing literature, not from this repo's accumulated folklore.

### The three constraints that shape any answer

| Constraint | Ray's words | What it rules out |
|---|---|---|
| **Fable 5 is scarce and powerful** | *"limited but very powerful, we want to use it sparingly"* | Any design where Fable is the default architect on every task. It must be spent at named decision points, and the report must say which. |
| **Claude-first** | *"claude first (via its tui and claude desktop app)"* | Any design where Codex holds the session or owns orchestration. Codex is offloaded-to, not handed the wheel. |
| **Codex for execution, conditionally** | *"offload to codex models for code execution when it makes sense"* | A fixed always-codex routing. The report owes a decision rule for *when it makes sense*, not a mode setting. |

### What "fragile and slow" must be decomposed into before it can be fixed

The report may not treat this as one problem. At minimum it separates:

- **Latency** — wall-clock from dispatch to usable result. Where does it actually
  go: CLI startup, model reasoning, the wrapper's preflight, the reap, or the
  architect re-reading the report?
- **Fragility of the transport** — the observed failure modes, which this repo has
  already recorded rather than guessed: lanes that time out at 900 s
  (`.agent/kb/reports/agents/handoff-verify.md` names one and its resume); lanes
  that complete but whose notification arrives after the session dies (this
  session, `docs/artifacts/the-116-second-blackout.html`); orphaned CLI processes
  surviving a "completed" task; a settled wrapper reused as a live writer.
- **Fragility of the CONTRACT** — the seven-part spec, the `PREMISES` block, the
  attestation gates. How much of the slowness is protocol overhead that is buying
  correctness, and how much is ceremony?
- **Context cost** — every lane report re-read at architect prices.

**The evidence is already on disk and must be used rather than re-derived.**
Counted 2026-08-27: **235** lane reports directly in `.agent/kb/reports/agents/`
(478 `.md` under `reports/` recursively), plus **159** cross-family review reports
under `.agent/kb/review/reports/`. That is the primary source on how this transport
actually behaves; the published literature is secondary. A report citing only the
literature has skipped the cheaper and more specific half.

**The 159 review reports are the sharpest slice and are easy to overlook.** They
are named `review-<sha>-<lane>.md` — every one is a cross-family handoff that
already happened, with its findings, its lane, and its commit. If the question is
"is the Claude↔Codex exchange fragile", 159 recorded instances of exactly that
exchange are better evidence than any article.

*(This paragraph carried "~260" until 2026-08-27, which was the agents/ directory's
hardlink count misread as a file count — corrected here rather than overwritten,
because the wrong figure UNDERSTATED the evidence base and the correction
strengthens the phase rather than weakening it.)*

### Banned answers

- **"The current six-agent roster is optimal."** It may be, but it cannot be the
  answer *by default*. It was designed 2026-08-06 against a three-lane world that
  included Gemini as a routine reviewer, which Ray has now scoped to one call.
  If the report concludes the roster stands, it must say what changed and why the
  conclusion survives it.
- **A roster with no interface.** A list of roles, models and efforts that does not
  say how a Claude session and a Codex lane exchange work, or what makes that
  exchange fail today, has not answered the question — it has answered the 2026-08-06
  one, which was already answered.
- **"Fable 5 orchestrates everything."** Ruled out by Ray's own budget constraint.
- **"Add the seven roles from the 2026-08-02 directive."** The 2026-08-06 synthesis
  explicitly argued against a large role list, citing 10x-Team: *"adopt 10x-Team's
  mechanics, not its role list"* — because CTO/PM/EM/DevOps/SRE/DBA "have no
  referent here". Re-proposing them needs new evidence, not a fresh assertion.
- **Anything routing to `grok`.** Not installed.

### What the report must reconcile

`.claude/agents/` diverged from its own research and nothing records why:
`kb-advisor` (fable/high) exists where the synthesis proposed `kb-fallback-reviewer`
(opus/high), and that synthesis said fable was *"deliberately ABSENT from the
standing roster"*. The new report must either explain the swap or flag it as
undocumented drift.

## Phases

### P1 — Read #509 and pin what "done" means for the skill

No depth test; this phase produces a decision, not code. Read `gh issue view 509`
in full. Extract its 5-step workflow, its 5 named traps, its "What good looks like"
list, and its 3 test prompts. Write them into the skill's eval fixtures **before**
writing the skill, so the skill is built against its acceptance criteria rather
than judged by them afterwards.

Commit: `docs(skills): pin #509's acceptance criteria as aggregated-research fixtures`.

### P2 — Build the skill via skill-creator's full loop

Ray's Q9: full spec, not minimum viable. `skill-creator` owns the loop;
`/mattpocock-skills:writing-for-agents` owns the docs style (both named in #509's
own decisions table).

The skill must encode, at minimum:

1. The **5-step cheapest-refutable-first** ordering: installed binary `--help` +
   throwaway probe → shipped source at a pinned ref via
   `gh api repos/OWNER/REPO/contents/PATH?ref=TAG` → both issue trackers via
   `gh api -X GET search/issues` → breadth via Firecrawl `developer-index` then web
   → synthesis by a strong Claude lane.
2. **A control arm on every null result.** This is #509's headline requirement and
   the one thing the skill exists to make automatic.
3. The **five traps**, each as a check the skill runs rather than prose it states:
   `gh search issues` returning `[]` instead of failing (#507); a channel with
   issues *disabled* reading as "zero reports" (jdx/hk); a cited reference
   contradicting what it annotates (#508); stale-PATH version skew; an agent's own
   claims needing a spot-check.
4. An explicit **"not measured"** section in its output template.
5. The **repos-touched enumeration** (`research-repo-enumeration.md`).

Gates green (`mise run kb-check -- .claude/skills/aggregated-research/ tests/`),
then one conventional commit.

**Depth test for this phase:** `mise run kb-skill-lint` must FAIL first on a
deliberately-bad draft that instructs a raw `graphify query` inside a bash fence,
then pass once corrected. Prove the FAIL direction — a gate verified only on clean
input is decoration (`probes-need-a-control-arm.md` rule 2).

### P3 — Point the skill at ITSELF (Ray, 2026-08-27, added after the first draft)

The skill's first run is the self-referential one, and it is not a warm-up — it is
the run that decides what P4 is even capable of. #509's own body already carries
this as a suggested eval prompt: *"What tools should we be using to research
questions like this?"*

Two questions, in this order:

1. **Does something like `aggregated-research` already exist?** A marketplace
   plugin, a published skill, an MCP server, a CLI, an SDK, an agent framework's
   research mode. If it does, the honest outcome may be *adopt it and delete most
   of P2's skill* — and that is a **success**, not a wasted phase. `use-tool-builtins.md`
   is explicit: homegrown code is the last resort, and custom code that survives
   the check must record in writing why the existing option was insufficient.
2. **What should be folded into it to make it stronger?** Candidates already
   present in this session or this repo, none of them yet evaluated against each
   other: the `firecrawl` family (`developer-index`, `research-index`, `search`,
   `crawl`, `map`), `exa`, `context7` / `ctx7`, `last30days`, `repowise`,
   `mcp2cli`, `Explore`, `gh api` search, `mattpocock-skills:research`, and
   graphify's own read-only verbs. Also: what is NOT installed that should be.

**This phase's own control arm.** "No prior art exists" is a negative, and a
negative from a search is worthless without an arm — `probes-need-a-control-arm.md`
rule 1. Before reporting zero prior art, run the same search shape against a
capability that certainly HAS prior art (e.g. "changelog summarizer skill") and
show it returns hits. State the arm in the report. This is also the phase's
dogfooding value: if the skill cannot arm its own negative, it does not satisfy

# 509's headline requirement and P2 is not done

**Do not install anything this phase discovers** without saying so first —
adding a marketplace plugin is `do-not.md` #11 territory (project scope only,
never a write to `~/.claude`) and it is a Ray decision. Recommend; hand back.

Output: `docs/research/reports/<date>-aggregated-research-prior-art.md`.

### P4 — Run it on the team question

Dispatch per Ray's Q6 instruction: *"run them as parallel
`/fable-orchestrator:orchestration` or subagents that we wait on for them to
complete, code review and `/verify` their results and then we move forward."*

So: parallel lanes, background, wait for structured reports, **cross-family review
the findings** (Claude-authored research → a codex reviewer), then verify.

Inputs the lanes must be given, because they cannot infer them:

- `docs/research/reports/2026-08-06-roster-synthesis.md` — the prior art.
- Issue #116 — the open ticket and its verbatim Ray directive.
- The lane constraint: Claude + Codex full, `agy` scarce, no `grok`, no API keys.
- The banned answers above.

Output lands at `docs/research/reports/<date>-claude-codex-handoff.md`.

### P5 — Verify and close the loop

Paste every sentinel. Run `mise run kb-gates`. Then, BEFORE `kb-ship`:

```
mise run kb-goal-outcome -- 2026-08-27-1342-kb-aggregated-research \
  --result achieved|cleared|stalled|blocked --turns <n> --note "<which clause failed and why>"
```

Its output is exempt from the review receipt (`review.EXEMPT_PATHS`), so it lands
on this round's own branch without costing a re-review (#66).

## Sentinel formats

Every sentinel ends `@ <sha>`, where `<sha>` is the first 12 characters of the
commit the claim is true at. **Sourced from the code that prints them**, not from
prose describing them:

| Sentinel | Literal | Source |
|---|---|---|
| skill exists | `AGG-SKILL: <n> file(s) under .claude/skills/aggregated-research/ @ <sha>` | authored here |
| lint clean | `skill-lint: <n> skill(s) checked; every instructed command is a mise task or allowed read-only` | `kb_setup/skill_lint.py`, the `else` branch of the findings report |
| score table | `[skill-score]` | `kb_setup/skill_eval.py`, stderr prefix |
| arms | `AGG-ARMED: <n> null result(s), <n> control arm(s) @ <sha>` | authored here |
| report | `AGG-REPORT: docs/research/reports/<filename> — <n> sources @ <sha>` | authored here |
| self / prior art | `AGG-SELF: <n> prior-art tool(s) evaluated, <n> adopted, <n> rejected @ <sha>` | authored here |
| team | `AGG-TEAM: <n> roles, lanes=<comma-separated> @ <sha>` | authored here |
| gates | `PASS  gate <name> rc=0` — **two spaces** | `kb_setup/pr.py` `run_gates` |

**Two traps this repo has already measured, restated so they are not re-hit:**
`mise run test` runs pytest under `-qq`, so `"N passed"` **never appears** — never
require it. And `kb-currency-check` prints **nothing** on success, so silence is
indistinguishable from never-ran.

## Verification — the literal lines

The goal's five items, with what produces each:

1. `ls -1 .claude/skills/aggregated-research/` output pasted, showing `SKILL.md`.
2. `mise run kb-skill-lint` and `mise run kb-skill-score -- aggregated-research`,
   both pasted, real exit codes (redirect to a file — never pipe to `tail`).
3. For each null result: the control-arm command and its **non-null** output. The
   zero-nulls escape hatch exists because a research run that happens to find
   everything owes no arm — but it must then prove the skill *would* emit one.
4. The committed report path, ending in `## GitHub repos touched`.
5. The team recommendation with model + effort per role.

## Out of scope — the overflow valve

Anything this round proves it should not do lands here rather than expanding scope:

- Fixing `mise.toml:911`'s stale *"Both open"* comment on #120 (measured wrong this
  session — #120 shipped 2026-08-05 and recovered 184 MB). **File it, do not fix
  it here.**
- The `graph_first` guard's marker dirtying pinned clones (#420).
- The 26 open issues referencing the deleted semantic-corpus layer.
- `.claude/skills/orchestrator-routing/SKILL.md`'s three-lane doctrine, now false
  on the grok lane and misleading on the agy budget. File it.

## Hand-back — Ray's calls, never reported as done

1. **Adopting the recommended team.** The report recommends; Ray adopts. A round
   that creates agent files from its own recommendation has skipped the decision.
2. **Whether `kb-advisor` (fable) stays** where the synthesis wanted
   `kb-fallback-reviewer`.
3. **The `agy` budget policy** beyond this round's one-call limit.
4. **Whether #109's destination gets amended** to the capability wording Ray chose
   this session (*"an agent in any repo can ask this corpus a question about a
   pinned dependency and get a source-cited answer, with no human in the loop"*)
   — settled in conversation, not yet written to the issue.
5. **Marking `2026-07-31-2056-kb-navigable-graph` superseded**, since Ray chose to
   write a new goal rather than resume it.

## Operator visibility

The goal is bounded at 35 turns and the operator must be able to see where it is
without asking. Not as completion clauses — a checkpoint the goal can be satisfied
by is a round announcing itself:

- One `SendUserMessage` at each phase boundary (P1→P2→P3→P4→P5), one or two lines.
- A warning before any command expected to exceed ~30 s.
- The turn count against the 35-turn bound in each phase-boundary message.
