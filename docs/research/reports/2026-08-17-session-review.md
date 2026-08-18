# Session review — 14 Claude Code sessions, 2026-08-15 .. 2026-08-17

Synthesis of five parallel investigations against Ray's 2026-08-17 directive
(`docs/direction/2026-08-17-ray-directives.md`, read in full before writing).
Source reports, all under `.agent/kb/reports/agents/`:
`deterministic-reviewers-2026-08-17.md`, `unpinned-tools-2026-08-17.md`,
`forgotten-requirements-2026-08-17.md`, `contradicted-instructions-2026-08-17.md`,
`forgotten-cap-hunt.md`, `forgotten-cap-hunt-b.md`,
`context-heavy-work-2026-08-17.md`.

Scope armed identically by four independent agents: `ls -lt *.jsonl` in the
project transcript dir gives exactly **14** files with mtime ≥ 2026-08-15; the
15th (`497d5dcb`) is Aug 14 18:19. Two of them independently counted **2,422**
Bash tool calls — the same figure `kb-session-reflect` prints, which is the
cross-check that scope and parsers agree.

**Ray's stated problem is "going in circles not accomplishing anything." This
report is ranked so that the top three items are the circles.** Everything below
item 9 is bookkeeping.

---

## 1. THE FORGOTTEN CAP

### The two hunts disagree. That disagreement is itself the finding.

Two independent routes were run — Hunt A over all 229 transcripts, Hunt B over
git history and repo artifacts with **no transcript consulted**, deliberately
kept independent so they could cross-check. They returned **different caps**.

| | Hunt A (transcripts) | Hunt B (artifacts) |
|---|---|---|
| The cap | `_MAX_COST_USD = 0.25` | `GRAPHIFY_MAX_GRAPH_BYTES` 512 MiB |
| How lost | meaning changed: a per-call cap recorded as "25 cents **total**", then shipped as `25.0` per chunk × 58 chunks | raised to 1 GiB on 2026-08-03 as a self-declared "BRIDGE, NOT A GROWTH STRATEGY", never retired |
| Date lost | 2026-08-14 → 2026-08-17 | 2026-08-03 |
| Still live? | yes — no cumulative cap exists | yes — 735.6 MiB / 1 GiB = **72% consumed** |

### Which I believe: Hunt A's $0.25 — with one stated dependency

**Ray clarified in this very session that the cap is a `$` SPEND cap.** That
clarification is recorded in Hunt A's finding 6, which rules out the two
non-dollar readings on exactly that ground, and traces to the AskUserQuestion at
`fb633adf` L137 headed *"The lost cap"*. If that clarification is real — and it
is the only reason to prefer one hunt over the other — then Hunt B's 512 MiB
graph cap is a **byte** cap and cannot be the answer, however live it is.

**I did not re-probe the clarification myself.** It is the single load-bearing
premise of this section and it is inherited (`probes-need-a-control-arm.md`
rule 6). One AskUserQuestion settles it. If Ray says the cap was not about
dollars, the answer flips to Hunt B and the ranking below flips with it.

### The evidence for $0.25, and how it was lost

`.agent/plans/session-2026-08-16-b.md:35`, verbatim:

> `| max_cost_usd | 0.25 | 25 cents total, for 1.37M words |`

Three days later, `graphify_semantic_slice.py:406-416` ships
`CORPUS_PROFILE(max_budget_usd="25.00", max_cost_usd=25.0)`, and
`.agent/plans/session-2026-08-16-c.md:81` re-describes it as
`($25 cap)` — no longer "total". Enforcement is per chunk only
(`graphify_semantic_corpus.py:2036-2039`, `0.0 <= metadata.total_cost_usd <=
config.max_cost_usd`). This session measured the consequence itself, `49e2cc30`
L1840, 2026-08-17T17:41:37Z, verbatim:

> "The successful call cost **$1.12**. Checking how `max_cost_usd = 25.0` is
> enforced — 58 × $1.12 is well past it."

**So: the cap was $0.25, described as a whole-run total, and is now $25.00 per
chunk across 58 chunks with nothing summing spend.** Expected run cost ~$65;
theoretical ceiling ~$1,450; cumulative cap: none. That is a 100× raise plus the
silent loss of the concept "total".

### Two things that are NOT the cap, and why saying so matters

- **Ray never stated a dollar figure as a cap in any of the 229 transcripts.**
  Control-armed: the identical probe over the identical corpus *does* return
  `max_cost_usd = 25.0`, the $25 Managed-Agents prose, and Ray's own
  `a86bf6ac` L2603 CodeRabbit spend directive — so it finds Ray's cost talk. Its
  silence on "Ray set $N" is a real absence. The cap Ray remembers is one **we**
  wrote down and then re-described, not one he issued.
- **The `$0.25` constant was authored on 2026-08-14 by codex, while Ray's Claude
  subscription tokens were depleted** (`8df3dace` L203, Ray verbatim: *"codex was
  working on this repo while the claude subscription plan's tokens were
  depleted"*). **There is no Claude transcript for that decision.** Any
  session-review workflow built from transcripts alone is structurally blind to
  codex-authored rounds — this must be a documented limit of the tool Ray is
  commissioning, not a surprise found later.

### Hunt B is not wrong — it found a SECOND forgotten cap, and it is nearly full

`mise.toml:188-195`, verbatim: *"THIS IS A BRIDGE, NOT A GROWTH STRATEGY … A cap
raised once per ingestion is not a guard, it is a ratchet."* Its two written exit
conditions — issues **#120** and **#130** — are both still OPEN. Its trajectory,
from this repo's own artifacts: 345 MB (2026-07-31) → 499 MB (CLAUDE.md, 2026-08-05)
→ **771,357,561 bytes = 735.6 MiB, re-measured independently by me just now**.
72% of the bridge consumed, and `kb_setup/insights.py:435-445` only *reports* it —
`hk.pkl` has an `md_size_budget` step and no graph-size step.

Ray reserved this raise to himself **by name, four times** (both 2026-07-31 and
2026-08-01 goal files, both riders, and `.claude/agents/kb-corpus-curator.md:42`
*"Never raise `GRAPHIFY_MAX_GRAPH_BYTES` to make a build fit"*). Control-armed
absence: `kb-curator/SKILL.md` — **the skill that adds sources and therefore grows
the graph** — contains zero hits for the cap, while `clear-prep` mentions
`graphify-out` 3 times. The fence exists in files that do not load during the
activity it fences.

**Report both to Ray. One is the answer; the other will become the next
"forgotten cap" in about six weeks of ingestion.**

---

## 2. WHAT THIS ROUND DID WRONG — ranked by cost, not by count

### RANK 1 — Context. 10 of 10 working sessions blew the 200K target; median 2.9×, worst 4.2×

This is the largest measured failure in the window and it is the mechanism behind
"going in circles". Peak context, `usage`-derived (true token counts):

| session | peak ctx | vs 200K |
|---|---|---|
| 49e2cc30 | 843,865 | **4.2×** |
| 15f7b35a | 793,862 | 4.0× |
| eb35109b | 729,762 | 3.6× |
| e8682e1d | 712,390 | 3.6× |
| 8df3dace | 705,977 | 3.5× |
| fd97f19d | 583,137 | 2.9× |
| de3c5d58 | 543,987 | 2.7× |

Peak == final in every session: context grew monotonically and was **never**
reclaimed. **Compaction events: 0**, control-armed against three out-of-window
files that do contain compact boundaries — so the zero is real, and it is bad
news: every session ran on `claude-opus-5[1m]`, so the symptom was suppressed by
the model, not by decomposition. Any move to a 200K-class model turns all ten
into compaction storms.

**Assistant prose is 1% of any session.** The cause is where machine bytes land.

### RANK 2 — No cumulative spend cap on the extraction run

~$65 expected, ~$1,450 theoretical, nothing summing. Independently confirmed by
both cap hunts and by this session's own $1.12 measurement. It is a live
exposure, not a historical one — the 58-chunk run is the next thing queued.

### RANK 3 — Delegation at 0.55% of tool calls, which is why rank 1 has no absorber

**20 `Agent` delegations across 3,622 tool calls.** The three sessions that
delegated *nothing* include the largest-context session in the window
(`49e2cc30`, 843,865). Every probe byte, build log and file read landed in the
main context and stayed there for the rest of a 4–13 hour round.

### RANK 4 — A Codex agent was committed to main against the Claude-only-LLM invariant

`.codex/agents/kb-extraction-worker.toml` (commit `98b116fd`, PR #325, in-window),
verbatim: *"You are the **executor** unit of this repo's only LLM path."* Against
`do-not.md` #4, `CLAUDE.md:66`, and `ai-cli-invocation.md` (*"never an extraction
backend"*). No gate fired because `clean_env()` strips backends from graphify
**subprocesses**, and host-agent extraction is not a subprocess — the agent *is*
the LLM. Ranked 4 not 1 only because it has not run; it is the highest-severity
*correctness* item in the window.

### RANK 5 — `github-cli` unpinned, and repo code calls it

See §4. It is the only unpinned binary that can break a repo **task**.

### Now the numbers the existing tools reported — which matter and which are noise

| reported | verdict | why |
|---|---|---|
| `piped-rc` ×126 | **MATTERS, mid** | This is the mechanism by which a red gate reads green. `mise run kb-check` already exists as the fix; 126 is a habit that has outlived its excuse. |
| `bounded-search` ×22 | **MATTERS, mid** | Each is a potential false negative, the failure class this repo has burned the most hours on. |
| `mutation-harness` ×72 | **NOISE as reported** | The rule is a bare token match (`read_text\|.replace(\|write_text`) with an **order-free** second search for `pytest\|subprocess.run\|rc=`. All 72 excerpts are three tokens with no command context. Worse, the remedy string printed alongside all 72 carries a frozen inherited number — "149 hand-written harnesses across 21 sessions" — that `kb-distill`, run minutes later, contradicts (largest group is `json`, 126 scripts / 24 sessions; no harness group at all). **The most-repeated wrong number in the report is printed 72× per run.** |
| `relative-cd` ×12 | **NOISE at this volume** | 12 across 2,422 commands = 0.5%. |
| `bare-interpreter` ×9 | **NOISE at this volume** | 0.4%. |
| graph-first **45 : 110** | **MISLEADING** | `session_reflect.py:543` scans **only Bash tool calls**, so every `mcp__graphify__*` call — and this repo has the hosted graphify MCP registered — contributes **0 to the numerator** while `Read`/`Grep` still increment the denominator. The ratio is biased by construction. The *real* signal underneath it is `eb35109b`: **319 of its 610 Bash calls were `grep`**, and `de3c5d58` had `cd=191`. |

**And the structural caveat on all of it:** `session_reflect` has **8 rules
total**, 3 of which fired zero times. ~20 rule files in `.claude/rules/` have no
detector at all. **An empty section means "no rule matched", never "the round was
clean."** A quiet `kb-session-reflect` is not a passing round.

---

## 3. FORGOTTEN REQUIREMENTS AND CONTRADICTED INSTRUCTIONS

### 3a. Forgotten — ranked

**F1 — graphify issue #2787 follow-up landed nowhere.** Ray, `eb35109b`
2026-08-17T02:24:19Z, verbatim:

> "NOTE: comment https://github.com/Graphify-Labs/graphify/issues/2787 stating it
> might have been fixed in https://github.com/Graphify-Labs/graphify/pull/2794"

It is an issue **this repo filed**. `currency.toml` watches exactly 8 graphify
issues (2484, 2485, 2551, 2308, 2101, 2086, 1653, 1824) — 2787 absent. Control
arm: `2787` → 0 hits across `currency.toml`/`docs/currency/`/`.claude/`, while
`2076` → 18, `1392` → 11, `959` → 5. Cross-checked against the 0.9.46 currency
run happening in this very session: still absent, while control `2551` → 1 in
`graphify-watch-state.json`. **Status: not tracked anywhere. Cheapest possible
moment to fix is now, mid-resync.**

**F2 — `docs/direction/**` is a WRITE-ONLY tree.** Ray's directive is captured
verbatim and captured *well*. Nothing reads it. `git grep -n docs/direction` over
tracked files returns exactly two live hits, both in `hk.pkl` — the formatter
exclusion and the comment explaining it. Zero hits in `CLAUDE.md`, in
`.claude/CLAUDE.md`, in `clear-prep/SKILL.md`; not a row in the Layout table.
Control arm: the sibling `docs/goals` is referenced from 10+ tracked files
including four rules and two skills. **The only live pointer to Ray's directive is
a line in `~/.claude/…/MEMORY.md` — outside the repo, dies on a fresh clone, and
is precisely the mechanism Ray opened the /grilling by naming as broken.**
Capture without a reader is the disease this whole exercise diagnoses, in its
purest form.

**F3 — zero of the 10 standing mandates and 5 open questions has an issue**, in a
repo with 203 issues and a working convention that a work item becomes an issue.
Control-armed title sweep over all 203: `telemetry` 0, `worktree` 0,
`state machine` 0, `mermaid` 0, `centraliz` 0, `max token` 0 — against controls
`currency` 11, `graphify` 30, `kb-review` 7. The two most exposed:
- **worktrees** — the directive itself says *"NOT ESTABLISHED … Probe before
  answering"*; `grep -rl worktree` over rules/skills/CLAUDE.md/currency.toml → 0
  files. `graphify-out/` is gitignored and repo-local, so an `isolation:
  "worktree"` Agent run gets an absent graph, silently. **This one has a live
  failure mode and should get an issue plus a probe before the next worktree run.**
- **"what is the cap we had previously?"** — §1 above answers it, pending Ray's
  confirmation of the `$`-spend reading.

**F4 — Ray stated the same plan-mode preference TWICE, two days apart, and it is
written nowhere.** `8df3dace` 2026-08-15T20:17:15Z: *"i enabled plan mode / show
checkboxes and optional text field w pros/cons"*. `fb633adf` 2026-08-17T20:18:17Z:
*"i changed to plan mode, send me the interactive forms for the questions"*.
Control-armed over `.claude/` + `docs/` + `CLAUDE.md`: `checkbox` → no files,
`pros/cons` → no files, `interactive form` → no files; control `AskUserQuestion`
→ 5 files. **Having to repeat it IS the symptom Ray is describing.** Two lines in
the existing eager rule `clarify-before-acting.md` fix it permanently.

**F5 — Ray named six detector classes; `kb-session-reflect` implements none of the
five specific ones**, and pre-dates the directive by nine days (first commit
`eb88a57b` 2026-08-08). Absent: forgotten requirements, contradicted instructions,
unpinned tools, when-to-update-CLAUDE.md/hooks/rules, context-heavy decomposition.
**This report was produced by hand, by five agents, because no tool can produce
it.** Ray's own open question 3 anticipates the risk: the re-map *"should say what
is extended versus what is new, or this becomes a parallel implementation of the
tooling it is meant to unify."*

**F6 — "we should not rely on tools existing or managed by `~/.config/mise/mise.toml`"
has no rule, no hk step, no ticket.** Control-armed: `git grep -l "config/mise"`
returns research prose and the directive itself — no enforcement; control
`git grep -l mise.toml` over `.claude/` hits 5+ rule files. Nearest live ticket is
**#227** ("the pin is decorative for the whole Python surface") — the same disease
in a different organ, still open.

### 3b. Contradicted — ranked

**C1 — the Codex extraction agent (rank 4 above).** Its Claude twin declares
`model: sonnet` and a tool allowlist; the `.codex` twin declares only
`model_reasoning_effort = "medium"` — no model, no allowlist, and `grep -in claude`
over it returns exactly one line, a path reference. **The named precedent
`0367588e` ("All LLM work is **Codex**") WAS corrected in `.claude/` and
`.agents/`; `.codex/` was not.**

**C2 — `CLAUDE.md:9` asserts the opposite of the repo's shape.** Verbatim:
*"Claude-only by design — one self-contained `CLAUDE.md`, no `AGENTS.md` stub."*
`AGENTS.md` exists (51 lines, `c70f0f81`), and `98b116fd` added `.agents/skills/**`
— 16 files, ~2,700 lines. `grep -n '\.agents/\|\.codex' CLAUDE.md .claude/CLAUDE.md`
→ **rc=1, zero hits**; control `grep -c '\.claude/' CLAUDE.md` → 6. Drift is already
real: `diff .claude/skills/clear-prep/SKILL.md .agents/skills/clear-prep/SKILL.md`
→ line 171 differs. **The always-loaded doctrine file is lying about the repo.**

**C3 — the second config surface is unmirrored, unlinted, unbudgeted and
undocumented.** Only **1 of 10** `.agents/skills/*` dirs has a generator
(`skill_refresh.py:53`, graphify only). Both authoring gates are hard-scoped:
`skill_lint.py:57 DEFAULT_SKILL_GLOB = ".claude/skills/*/SKILL.md"`,
`md_budget.py:121 _SKILL_RE = "^\.claude/skills/.*/SKILL\.md$"`. **This is the
mechanism that let C1 land against a hard invariant with every gate green.**

**C4 — `.mcp.json` registers the hosted graphify MCP**, against Ray's 2026-08-02
directive *"we should be integrating the graphify python library instead of the
graphify cli/mcp"*. It carries its own written exit condition
(`docs/graphify-reference.md:136`) and the blocking defect it worked around
(#289) closed two commits later in `5308c69c`. **Nobody re-tested the exit
condition.** Simultaneously a contradicted instruction and a forgotten requirement.

**C5 — a failing `typos` step was silenced by gitignoring its input**
(`graphify-out/.vocab.txt`, `98b116fd`) with an excellent control-armed
justification but **no recorded approval and no upstream issue**, which
`zero-skip-policy.md` #1/#4 and Ray's mandate 3 both require. Defensible on the
merits; the process gap is real, and `typos` exiting 2 with zero bytes on both
streams will recur.

### 3c. The invariants that HELD — all control-armed, all machine-gated

Zero `.sh` files added; zero inline lint suppressions; zero authored commits on
`main`'s first parent (4 PR merges); zero writes outside the project; zero
`gh pr create`/`gh pr merge` across 14 transcripts (control: `kb-ship`/`kb-land`
in 10 of 14). **Every invariant that held has a machine gate. Every contradiction
found (C1, C2, C4) is meaning-level and lives on a surface no gate reads.** That
is the reportable pattern, and it reproduces the named precedent exactly.

---

## 4. UNPINNED TOOLS — ranked, with disposition

Method: all 2,422 Bash calls parsed twice (heredoc-stripped head extraction, then
a per-call anchored regex), survivors resolved with `command -v` and their
declaring config read straight off `mise ls --current`'s source column. Control
arm on the "not in repo mise.toml" grep: the same shape on
`(hk|taplo|gitleaks|typos)` returned lines 35/37/42/44, so it discriminates.

| rank | tool | calls / sessions | provenance | disposition |
|---|---|---|---|---|
| **1** | `gh` | 122 / 10 | **user config only** (`~/.config/mise/config.toml`, 2.97.0) | **PIN in repo `mise.toml`.** 19 `"gh"` literals in `kb_setup`; it backs `kb-ship` (`pr.py:372`) and `kb-land` (`pr.py:233`). On a fresh clone without Ray's global config, **`kb-ship` fails**. The only unpinned binary that breaks a repo task. |
| **2** | `git` | 316 / 10 | **nothing** — a dead mise shim falling through to Apple Git 2.50.1 | **Pin, or at minimum add a `[tool.git]` currency row.** `mise which git` errors ("not currently active") while `git --version` returns rc=0 from `/Library/Developer/CommandLineTools`. **68 `"git"` literals in `kb_setup` ride an OS binary with no floor anywhere.** |
| **3** | `rg` | 6 / 1 | user config only (15.2.0) | **Pin — on behavioural grounds only.** Correction to the obvious reading: repo code does **not** call it. Its 6 `kb_setup` hits are `graph_first.py:73 _TREE_SEARCHERS` (the guard that *detects* agents using rg) and a filename allowlist. Control-armed: `grep -rn '"npm"'` → nothing while `grep -rn '"gh",'` → 8 lines. |
| **4** | `jq` | 28 / 3 | user config only (1.8.2) | **Replace at the call site, don't pin.** All 28 uses are `\| jq` over a `gh --json` or PyPI response; `gh --jq` (already used in this window) or `uv run python` covers every one with zero new pins. |
| **5** | `curl` | 21 / 5 | nothing (OS 8.7.1) | **Leave.** 21 read-only probes, none load-bearing. |
| **6** | `yq` (2), `npm` (1) | 1 session each | user config only | **Leave.** Genuine one-offs; `npm` has zero literals in `kb_setup`. |
| **7** | `claude` | 17 / 4 | native installer, `~/.local/bin/claude` | **Unpinnable — record the fact** so a future session does not spend a probe rediscovering it. Absent from all 135 `mise ls --current` rows. All 17 uses are `--help` probes. |

**Adjacent, flagged not acted on:** the user config carries **`pipx:graphifyy
0.9.46`** against `pyproject.toml`'s `graphifyy[all]==0.9.45`. The repo `.venv`
currently wins on PATH so nothing is broken today — this is the known stale-PATH
skew with a one-release gap. Next currency round.

**False-positive discipline, stated because the number is dramatic:** a naive
argv[0] extractor reports **`import` at 165 calls resolving to
`/opt/homebrew/bin/import` (ImageMagick)**. It is `import json` inside quoted
`-c` strings. Every row under 30 calls was individually opened before being
reported; that is how `tree`, `fd`, `watch`, `delta`, `time` and `usage` were
caught as prose or python. **Any unpinned-tool survey of this corpus that skips
the per-hit read will report ImageMagick as a top-5 dependency.**

---

## 5. CONTEXT BUDGET — what blew past 200K and how it should have been decomposed

Budget is exhausted in the **first 14–20 minutes** of every long session
(`eb35109b` crossed 200K at msg 104/1,165 = 14 min). **80–91% of each long
session runs in deficit.** Four drivers, ranked by measured tokens recoverable:

**D1 — one skill load = 175K tokens, 88% of the entire budget, and it happened
twice.** `claude-api` at ~700,700 chars ≈ **175,178 tokens**, injected as one
user-role message by one `Skill` call. Both invocations were **fact lookups whose
answers are a few hundred tokens**:
- `15f7b35a` at 11% into the session: `"current model pricing for Haiku 4.5, Sonnet 5, Opus 5 input/output per MTok"` — then sat in context for the remaining 89%, re-read on ~1,740 turns.
- `49e2cc30`: `"definitively retrieve a model's maximum output tokens"`.

These are the #1 and #2 peak-context sessions in the window, and this one block is
21–22% of each peak. The skill's own trigger fires *"whenever the prompt names
Claude/Anthropic in any form"* — in a repo whose subject **is** Claude Code.
**Fix: `Agent(general-purpose)` loads it, returns the table, dies. ~350K recovered.**

**D2 — the same plan re-pasted 13 times.** `8df3dace` made 14 `ExitPlanMode` calls
carrying 497,501 chars, monotonically growing 13,433 → 58,016. Only the last is
live: **439,485 chars (~110K tokens) is pure restatement — 55% of Ray's whole
budget spent re-sending a document already in context.** Fix: a plan is a FILE
(`agent-artifact-conventions.md` already says so). `Write` once, `Edit` per
revision (a hunk, not a document), `ExitPlanMode` with a pointer. **~110K recovered.**

**D3 — GUI exploration at ~100K tokens per screenful.** 19
`mcp__claude-in-chrome__browser_batch` calls returned **677,391 chars (~169K
tokens)**; the six largest alone are ~142K. It was clicking around
`app.graphify.com`'s sidebar looking for an MCP link. `research-doc-sources.md`
prescribes `llms.txt` and the documented API **before** driving a GUI, and the
product of all that clicking is now one tracked report. **~165K recoverable.**

**D4 — the structural cause: the ROUND is the atomic unit of context, and a round
is 4–13 hours.** Seven of nine working sessions open with the identical single
instruction, *"Read and follow `.agent/plans/session-*.md`"*. `fd97f19d` executed
**13h14m on 2 human turns**; `de3c5d58` **8h46m on 1**. There is no decomposition
boundary anywhere inside a round because **the handoff format makes the round the
atom.**

**The decomposition already visible in these transcripts** — six phases, each
closing on an artifact that is a clean seam:

| phase | closes with | why it is a seam |
|---|---|---|
| P1 Orient | a plan file | reads MEMORY/handoff/issues; touches no code |
| P2 Implement | a commit | the only phase needing module sources in context |
| P3 Arm | `kb-arms` spec + rc table | needs the spec, not the implementation history |
| P4 Review | the `kb-review` receipt | cold by design — already a subagent |
| P5 Ship | `kb-ship`/`kb-land` | needs branch, gates, PR number |
| P6 Close | `kb-remember`/`kb-reflect`/next handoff | needs the outcome, not the transcript |

`e8682e1d` ran P1–P6 in one 6h27m / 712K context. Split six ways: ~90–120K each,
none over budget, **and each restartable after a crash instead of losing 6 hours.**

**The enabling change is small and it is the highest-leverage item in this whole
report:** `/clear-prep` already writes a handoff. It should write a handoff **per
phase** and end the session at each phase boundary. `kb-session-state` already
produces the block. What is missing is only the *norm* that a phase boundary is a
session boundary.

**Not the headline, reported so it is not chased:** whole-file re-reads cost
186,524 chars (~47K tokens) across the window — a habit, an order of magnitude
below D1–D3.

---

## 6. PROPOSED AUTOMATION — skill → mise task → python module, and which layers are EARNED

Ray's mandate is that every layer exists and takes optional arguments. The
counter-pressure is real and measured in this repo: **every skill spends the
skill-listing budget on every turn**, and 9 plugins are already enabled. So each
proposal states which layers it *earns*.

Note for every detector below: `kb_setup.session_reflect`'s `OWNED` (:212),
`DIRECTIVES` (:299) and `UNARMED` (:432) tables are **Rule tuples — data, not
branches**. A new detector is *a table row plus a test*, not a new module.

### A1 — Cumulative spend accumulator (RANK 1, blocks the 58-chunk run)
- **module**: `kb_setup.graphify_semantic_corpus_run` — accumulate
  `metadata.total_cost_usd` across staged chunks in `on_chunk_done`, abort on
  `max_total_cost_usd`. Every chunk already records the figure; nothing sums them.
  `--max-budget-usd` **cannot** express this (it is per provider invocation).
- **task**: none new — `kb-corpus-run` owns it.
- **skill**: **NOT EARNED.**
- Ask Ray the ceiling first (measured expectation ~$65).

### A2 — Graph-size gate (RANK 2, 72% of a bridge cap consumed)
- **module**: `kb_setup.insights.SizeCheck` **already computes it** and only prints.
- **task**: an `hk.pkl` step / `kb-gates` row reading it, with the ceiling and its
  owner named in code (what #218 asks for).
- **skill**: **NOT EARNED** — but move the *fence* into
  `.claude/skills/kb-curator/SKILL.md`, which currently has zero mentions of it and
  is the skill that grows the graph.

### A3 — Context-budget detector (RANK 3, the 200K mandate)
- **module**: a new Rule row is *not* enough here — this needs `usage`-derived peak
  context, which `session_reflect` does not compute. Add a
  `peak_context_tokens(path)` helper beside `_scan` and a report section: peak,
  the message index where 200K was crossed, and the top-3 largest single tool
  results / skill bodies.
- **task**: `kb-session-reflect` — **exists**, extend it.
- **skill**: **NOT EARNED** — `kb-session-reflect` is already a `/clear-prep` step.
- Second half, cheap and high-value: a **skill-body-size warning** — any `Skill`
  load over ~20K tokens should be a subagent. That is a `.claude/rules/` entry
  (eager, behaviour-triggered), not code.

### A4 — Unpinned-tool detector (RANK 4, Ray named it explicitly)
- **module**: new `kb_setup.tool_provenance` — for each command head seen in a
  transcript, resolve `command -v` and read `mise ls --current`'s source column;
  report anything whose declaring config is not the repo's. **Must carry the
  false-positive discipline from §4 or it reports ImageMagick.**
- **task**: extend `kb-currency-check` (it is already the offline drift check) —
  do **not** add a new task.
- **skill**: **NOT EARNED.**

### A5 — Forgotten-requirement detector (RANK 5, the hardest and most valuable)
- **module**: `kb_setup.session_reflect` gains a **Ray-turn extractor**, which is
  purely deterministic and was got wrong twice by hand this round: it must read
  **both** `type=="user"` **and** `type=="last-prompt"` (slash commands live only
  in the latter, 4 prompts were dropped without it) and exclude the two non-Ray
  prefixes (`Another Claude session sent a message`, `<task-notification>`).
- **task**: `kb-session-reflect -- --ray-turns` emitting a structured list.
- **skill**: **NOT EARNED as a new skill.** The *judgement* — "was this tracked?"
  — cannot be regexed; it is an agent step inside `/clear-prep`, fed by the task's
  structured output. Adding a whole skill for it duplicates `kb-session-reflect`
  and is exactly Ray's open-question-3 risk.

### A6 — Second-config-surface coverage (RANK 6, the C1/C2/C3 mechanism)
- **module**: widen `skill_lint.DEFAULT_SKILL_GLOB` and `md_budget._SKILL_RE` to
  `.agents/skills/*/SKILL.md`, plus a mirror check so the 9 hand-copied dirs
  cannot drift. One-line changes each; **this is the cheapest correctness fix in
  the report.**
- **task**: none new.
- **skill**: **NOT EARNED.**

### A7 — `docs/direction/**` gets a reader (RANK 7, the purest instance of the disease)
- **No code at all.** A Layout row in `CLAUDE.md` and a read step in
  `clear-prep/SKILL.md`, exactly as `docs/goals/` already has both. **A finding
  whose fix is two lines of markdown should not be given a module.**

### A8 — Plan-mode preference (RANK 8, stated twice, two lines)
- Two lines in the **existing eager** `.claude/rules/clarify-before-acting.md`:
  in plan mode render options with pros/cons, multi-select, free-text escape.
  No module, no task, no skill.

### Fix the tools that already exist, before adding any
- `session_reflect`'s `mutation-harness` rule: scope the run to the **same command
  segment** as the patch, or downgrade it — 72 hits with no command context.
- Its frozen "149 harnesses across 21 sessions" string (:16-18, :223) is
  contradicted by `kb-distill` and printed 72× per run. Re-derive or date-stamp it.
- Its graph-first counter (:543) should count `mcp__graphify__*` in the numerator.
- `kb-goal-check` run **bare** audits the empty string and emits **10 false FAILs**.
  Control-armed: against a real pair it returns 15 OK / 0 FAIL. It should exit 2 on
  a missing argument the way `kb-skill-score` does. **Never quote a bare run.**
- `kb-distill` run bare scans **50 sessions**, not 14 — it takes `--limit`, not
  `--sessions`. Its 826/53 are habit figures, not round figures.

---

## 7. WHAT THIS WORKFLOW ITSELF GOT WRONG

**Unarmed premises that survived into findings.**
- The single load-bearing premise of §1 — that Ray clarified the cap is a **`$`
  spend** cap — is **inherited from another agent's report, not re-probed**. It is
  the only thing separating Hunt A from Hunt B and it decides the headline.
- Two claims about MCP calls being invisible to `session_reflect` rest on reading
  the scanner's source, **not on a positive probe** that an `mcp__graphify__*` call
  exists in one of the 14 transcripts.
- The `github-cli` pin recommendation was never tested (`mise use` would write a
  tracked file). It rests on provenance evidence, not on a tested fix.

**Partial coverage, deliberately.**
- **Only issue TITLES were swept** (203 of them), not bodies — except #314. A
  requirement buried in an issue body is graded "untracked" by F3 and F5. **This is
  the cheapest and most valuable follow-up in the report.**
- `session-reflect` capped away **295 rows** (159 command shapes, 124 wrapper
  candidates, 12 probes, plus 123 piped-rc / 9 relative-cd / 6 bare-interpreter
  excerpts). Reading them requires editing a tracked module, which was forbidden.
- The 9 `.agent/plans/session-*.md` handoffs were **enumerated but not read**. They
  are gitignored, so a requirement living only there is graded "forgotten" here and
  "written down" by anyone with the file open. Given that 7 of 9 sessions open by
  reading one, **this is a real blind spot in exactly the artifact the round runs on.**
- graphify #2787 / PR #2794 were **not fetched** — "was it actually fixed" is unprobed.
- No `subprocess.run([...])` sweep of `kb_setup` first-arguments: unpinned binaries
  the code depends on but no session happened to type are **unmeasured**.
- Sidechain/subagent transcripts were not walked (`isSidechain` is 0 in every
  in-window file), so the 20 delegations' own context cost is unmeasured.
- Token figures for tool traffic are `chars/4` estimates; only the peak-context
  column is a true token count.

**Probes caught broken mid-flight, reported because the near-misses are instructive.**
- `xargs -a` is not supported by BSD `xargs` — it silently produced an empty
  CONTROL, which would have read as *"no home-config writes"*, a clean false
  negative on `do-not.md` #11.
- A `$F` newline-joined file list collapsed to one argument (rc=2).
- The naive user-turn extractor was wrong **in both directions** — it swallowed
  teammate-messages and `<task-notification>` blocks (which arrive as `type=="user"`)
  and dropped 4 slash-command prompts. Only a second independent route found it.
- The first `session-reflect` run was **piped to `tail`** and lost its head — the
  exact `piped-rc` habit this report ranks. It had to be re-run to a file.

**What a second run should do differently.**
1. **Ask Ray the cap question first**, via AskUserQuestion, before spending any
   hunt. Two agents spent a full pass each on a question one sentence settles.
2. **Sweep issue BODIES, not titles.**
3. **Read the 9 handoffs** — they are where the round's real instructions live.
4. **Run the tools with arguments**: `kb-distill -- --limit 14`, `kb-goal-check --
   <path>`. Two of the four "existing tool" outputs in this round were
   window-mismatched or argument-artifacts.
5. **Delegate the transcript reads.** This review itself is a ~5-agent fan-out over
   426 MB — the single best instance of §5's own advice, and it worked: no agent
   read a `.jsonl` into context.

---

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — issue #2787 and PR #2794 cited in Ray's directive (F1); the pinned corpus dependency whose version sprawl and 512 MiB graph cap are the subject of §1 and §4.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo; all 203 issues, git history 2026-08-15..17, and every rule/skill/module cited.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — sibling repo; swept by the cap hunt, source of the `$200.00` statusline capture and `docs/specs/orchestration-takeover.md`.
- [anthropics/anthropic-cli](https://github.com/anthropics/anthropic-cli) — named in Ray's addendum as a candidate source of model metadata; not yet probed.
