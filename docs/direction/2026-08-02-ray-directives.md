# Direction — Ray's directive list, 2026-08-02 (VERBATIM)

> **This is the TRACKED, authoritative copy.** Captured at `/clear-prep`, on
> Ray's instruction: *"we just need to make sure all the instructions in this
> chat are not lost and we can begin reviewing it after /clear-prep"*. It is
> committed rather than left under `.agent/` because `.agent/` is gitignored and
> dies to `git clean -xdf` or a fresh clone — and this is project direction,
> which `.claude/rules/agent-artifact-conventions.md` says belongs tracked.
>
> **Do not paraphrase the verbatim block away, and do not "tidy" it.** It is a
> record of what was said, not a spec. Answers and status established at capture
> time are in a clearly separated section below, so his words stay unedited.
>
> A working copy also exists at `.agent/plans/RAY-DIRECTIVES-2026-08-02.md`, and
> the substance is mirrored into auto-memory as
> `ray-directive-backlog-2026-08-02` so it survives a clone even without this
> file. Three layers, deliberately — the instruction was that none of it be lost.
>
> **Status of each item is NOT tracked here.** As items are actioned they become
> GitHub issues or `sources/REGISTRY.md` rows; this file records the ask.

## VERBATIM

```text
below is a list of things on my mind that i dont want to forget that i want done
and will affect the wayfinder workflow and what we are building

did we run the skill to ingest/extract/learn from: sources/agent-harness-docs/docs/claude-code?
- if not, let's do that as we have had too many issues of you not understanding how claude code works
- i dont actually see this skill, what is it? if it doesnt exist we need to create it

we need to enforce all queries go through our graphify knowledge-base
- via hooks/rules/claude markdown via progressive disclosure

we should be integrating the graphify python library instead of the graphify cli/mcp since we are already building a python library of our own
- and it will also help us identify quickly if graphify releases breaks our python library since we will be tightly coupled

what is the status of our graphify peer gap analysis research?

add all of this project's dependencies as graphify ingested sources. we can hold off on the extraction/learning if those cost tokens. but at least we have it available via whatever graphify provides for free
- these sources (but also review what is in mise.toml and pyproject.toml)
  - https://github.com/jdx/mise
  - https://github.com/jdx/hk
  - https://github.com/jdx/fnox
  - https://github.com/apple/pkl
  - https://github.com/agent-sh/agnix
  - https://github.com/astral-sh/uv
  - https://github.com/astral-sh/ruff
  - https://github.com/astral-sh/ty
- and we should start snapshotting their documentation for offline access also and ingest
this also:
- https://pkl-lang.org/

we should review and research these to help improve our current skills and always use the /skills-creator skill to create them (or with the help of /mattpocock-skills:writing-great-skills)
- https://github.com/microsoft/skillopt
  - https://microsoft.github.io/SkillOpt/
- https://github.com/microsoft/SkillLens
  - https://microsoft.github.io/SkillLens/
https://github.com/wshobson/agents
- https://github.com/wshobson/agents/tree/main/plugins/plugin-eval

build a re-usable agent team to work on larger tasks when necessary
- with agents for specific roles like:
  - orchestrator
  - planner
  - architect
  - executor
  - qa
  - researcher
  - self-learner/self-optimizer/self-improver
- adjust model/effort level per agent specific to their role to not burn context/tokens
- specify plugins/skills/tools/mcps they should use
  - especially our graphify/knowledge-base library
- i have some fable-5 tokens available, so we should this model wisely for bigger planning/architecture tasks that involve the most upfront thinking/planning and the instructions for the other agents should be clear and detailed enough from that so that they can run on smaller models/effort
- after the team finishes, a self-improvement loop should kick in to adjust the team based on issues, mistakes and skills we can create or adjust to improve/automate the process


always enforce all plugins/skills we build to follow this protocol:
- skills that call mise tasks that is a wrapper for python library
- try to automate agents work into skills to reduce tokens instead of having agents follow step by step instructions via the skill/mise wrapped python library

do we have a way to get code hierachy of our code and dependencies code?

but we just need to make sure all the instructions in this chat are not lost and we can begin reviewing it after /clear-prep
```

## Ray's other answers this session — VERBATIM

A session audit found these existed in no artifact. They are decisions, in his
words, and several override a recommendation. Order is chronological.

```text
[destination, after 2 rounds of options]
  will be a 3rd party library/sdk/cli for any tool or ai/llm agent/cli to use

[corpus or engine?]
  we are building a tool that can be queried for existing knowledge in our sources
  if they dont exist, all research is done in the tool so that they get added and
  compound the tool's knowledge/sources

[whose knowledge compounds?]
  the library/sdk/cli we are building will have an init workflow that will setup a
  directory to store all its sources. this is where graphify and the other tools we
  are researching will also store their sources
  this directory will also store the:
  - extractions
  - learnings
  - cloned repos
  - anything else that is generated by our tools

  research how to best do this and how other similar tools accomplish this
  - for example graphify itself is an sdk and cli that hosts mcp servers

  i forget to mention, but this will also be a claude code plugin
  - if we haven't run the skill to ingest/extract/learn from
    sources/agent-harness-docs/docs/claude-code
       - especially: sources/agent-harness-docs/docs/claude-code/plugins.md
          - we should ingest/extra/learn from all of the claude-code sources and
            make sure it is up to date
     - it might be worth following this offline model also for the documentation of
       tools we are researching. and how to store sources for our sources

[new repo or this one?]
  this repo becomes the tool
  all the sources and research are the initial data we need to build this tool and
  is useful going forward
  we might just need to adjust the directory structure and allow to export it to
  our final directory structure
  but we should have enough sources using graphify's query and other tools as a
  good starting point and we can do more research if needed

[wayfinder charting — STOPPED here]
  Im not sure i want to follow the wayfinder workflow to build this. We might need
  to run the skill to ingest/extract the mattpcock skills similr to the offline docs
  so graphify can fully understand it and we run graphifys queries on it

[the 12-ticket fan-out]
  I dont know

[aihero pages]
  can we crawl it from https://www.aihero.dev/sitemap.xml
  i want the actual pages available for offline access. we should follow how
  sources/agent-harness-docs does it

[spec scope, and whether the concrete fixes go in it]
  use knowledge-base/graphify library to follow wayfinder process
  use knowledge-base/graphify query and tools to follow wayfinder workflow

[filing the three issues]
  [No preference]
```

**Three of these are load-bearing and easy to lose:**

- *"make sure it is up to date"* — the **freshness** half of #82. Not just
  "extract the 171 unextracted files" but keep the mirror current thereafter.
- *"how to store sources for our sources"* — a distinct requirement from the
  managed directory: provenance for third-party docs we snapshot.
- *"graphify itself is an sdk and cli that hosts mcp servers"* — his named
  comparator for the `init`/managed-directory design.

## Answers to the three ANSWERABLE questions in the list

Established at capture time. Each is a fact I looked up, not a plan.

### 1. "did we run the skill to ingest/extract from `sources/agent-harness-docs/docs/claude-code`?"

**Mostly NO — 4 of 175 files.** Measured across all 17 committed extraction
chunks by `source_file`:

| | |
|---|---|
| claude-code docs in the pinned mirror | **175** |
| actually extracted | **4** — `goal.md` (6 nodes), `hooks.md` (5), `skills.md` (15), `sub-agents.md` (132) |
| `plugins.md` | **NEVER ingested** — 0 source_files match `plugin`; control arm `sub-agents` → 1, so the probe discriminates |

**This is issue #82**, and it was **BLOCKED by #93** until 2026-08-02 — #93 is now
fixed and merged (PR #108), so **the sweep is unblocked**. Measured cost:
**~141k tokens/file**, so 171 files ≈ **24M tokens**. That number is why it has
not just been run.

### 2. "i dont actually see this skill, what is it?"

**It exists: `kb-curator`** (`.claude/skills/kb-curator/SKILL.md`), and it IS in
this session's skill list. It automates exactly this: register → ingest →
merge → cluster → label → `kb-remember` + `kb-reflect`.

**Why you may not see it** is a real, documented mechanism, not your mistake —
`.claude/rules/md-size-budgets.md` records **two** separate skill-listing limits:

1. a per-entry cap of **1,536 chars** on `description` + `when_to_use` combined;
2. a **whole-listing budget at ~1% of the context window**, on overflow of which
   Claude Code *"drops descriptions starting with the skills you invoke least"* —
   **keeping the name, dropping the description**.

With 7 project skills plus five enabled plugins' skills, the *listing* budget is
the one this repo can plausibly hit. `/doctor` estimates the listing's cost and
names the biggest contributors; `/context`'s Skills row shows the size **after**
the budget is applied. **Worth actually measuring rather than assuming** — if it
is the listing budget, no per-skill edit will fix it, and the levers are
`skillListingBudgetFraction` / `SLASH_COMMAND_TOOL_CHAR_BUDGET` / setting
low-priority entries to `name-only` in `skillOverrides`.

### 3. "what is the status of our graphify peer gap analysis research?"

**Five peer tools analysed; the track is paused, and its one measured payoff is
recorded.** Reports persisted under `.agent/kb/reports/agents/`:
`kb-tool-researcher-codegraph.md`, `kb-tool-researcher-gitnexus.md`, and
`docs/research/reports/peer-tool-synthesis.md`.

- `codegraph` (C, MIT) and `GitNexus` (TS) were pinned as sources #73/#74 on
  2026-07-30 — Ray chose both over four other candidates; registry rows 69–72
  (`blarify`, `aider`, and two others) stay **`pending`**, none chosen.
- ⚠️ **GitNexus is PolyForm Noncommercial 1.0.0** and is `scope = study`, which
  **provably partitions it out of the shipped graph**: 0 occurrences in
  `graph.json` vs 218,754 in `study-graph.json` (control: cognee → 225,658 in
  `graph.json`).
- The peer track's only measured payoff was cognee's 10,099 test↔src edges,
  visible only because a query over the AGGREGATE reached them — which is why
  #73 was deliberately `scope = corpus`.
- **`wayfinder-over-the-whole-backlog` memory records that the standing
  per-round peer analysis was RETIRED** (Ray, 2026-08-02) — it now earns a
  ticket only if the map calls for one.

### 4. "do we have a way to get code hierarchy of our code and dependencies code?"

**Partly, and the gap is specific.** graphify already provides, free and
AST-only: `graphify god-nodes` (the most-connected symbols), `export wiki` (an
index plus an article per community and per god-node), `GRAPH_REPORT.md`, and
`graphify explain` / `path` for concept and relationship views. `mise run
kb-artifacts` regenerates all of them.

**What is missing is a call/containment HIERARCHY, and two open issues say so:**

- **#106** — module-qualified calls (`lexical.build_index(...)`) produce no edge,
  so `affected` under-reports. This session's research found its filed root cause
  is **WRONG**: the real defect is that `from kb_setup import lexical` in
  `tests/` resolves to `__init__.py` rather than `lexical.py`, so the existing
  Module arm's receiver match fails. **~30 lines to repair locally.**
- **The retrieval layer never traverses an edge.** `lexical.py` is flat — every
  typed relation the corpus paid to extract is unused at query time. ~20 lines of
  networkx. Flagged as a hypothesis, **not a measured recall delta**.

So: hierarchy of *our* code is close (fix #106, add traversal). Hierarchy of
*dependency* code needs those deps ingested first — which is directive 5 in the
list above.

### 5. "review what is in mise.toml and pyproject.toml" — the full dependency set

**NONE of your 8 named repos is pinned.** Control arm: `Graphify-Labs/graphify`
→ `sources/graphify.manifest`, so the grep discriminates. This is exactly what
**#81** records (*"26 pinned sources, and not one is a tool we run"* — now 33
sources, still none of the toolchain).

Your 8 — all **NOT PINNED**: `jdx/mise`, `jdx/hk`, `jdx/fnox`, `apple/pkl`,
`agent-sh/agnix`, `astral-sh/uv`, `astral-sh/ruff`, `astral-sh/ty`.

**The review you asked for finds 10 more that your list misses:**

| From `mise.toml [tools]` | From `pyproject.toml` |
|---|---|
| `typos` 1.48.0 · `taplo` 0.10.0 · `rumdl` v0.2.40 · `gitleaks` 8.30.1 | `trafilatura>=2.0` (the `fetch` extra) |
| `codex` 0.145.0 · `antigravity-cli` 1.1.5 | `pytest>=8` · `hatchling` (build backend) |
| `python` 3.14.6 · `conda:ffmpeg` 8.1.2 | (`ruff`/`ty` are already on your list) |
| `pipx:graphifyy` 0.9.31 — **the one already pinned** | |

`codex` and `antigravity-cli` are worth calling out: they are the **executor
lanes** `.claude/CLAUDE.md` routes work to, so the corpus knowing nothing about
them is the same class of gap as not knowing Claude Code.

**Your "hold off on extraction" instinct is right and now has a number.**
Measured this session: **~141k tokens/file** for host-agent extraction. AST
extraction via a `kind = code` manifest is **free** — no LLM — so pinning all of
these and running `kb-build` costs only clone time and disk. That is the
free-tier version of this directive and it can be done immediately; prose
extraction of their docs is the expensive half and can wait.

**Disk is NOT the constraint** — measured **471 GiB available**, against
`sources/` at 3.6 GB and `graphify-out/` at 4.4 GB (repo total 8.4 GB). I nearly
wrote a "check headroom first" caution here and it would have been wrong.

**The real ceiling is graphify's aggregate-graph cap** — `GRAPHIFY_MAX_GRAPH_BYTES`,
default 512 MiB, and we sit at ~75% of it. That is what forced `study-graph.json`
to be split off. Adding 18 more code repos will push against it, so expect to
either raise the cap (it is tunable — this session's research corrected an earlier
claim that it was a hard architectural ceiling) or partition with `scope = study`.

⚠️ **And 41% of that budget is currently a BUG, not corpus** — graphify's
`prefix_graph_for_global` has no idempotence guard, so ids carry
`knowledge-base::` up to 26 times: **164.4 MB of 400.5 MB**, still present in
0.9.32. **Fixing that recovers more headroom than any partitioning scheme**, and
it should probably be done BEFORE pinning 18 more repos.

### 6. The other repos in the list — pinning status

- **`wshobson/agents` IS already pinned** (`sources/agents.manifest`,
  `kind = code`). Its `plugins/plugin-eval` subtree is therefore already in the
  corpus — a graph query about it should work today.
- **`microsoft/SkillOpt` IS pinned** (`sources/skillopt.manifest`).
- **`microsoft/SkillLens` is NOT pinned.**
- **`/skills-creator`**: the skill is registered as **`skill-creator:skill-creator`**
  (plugin-scoped), and `mattpocock-skills:writing-great-skills` is also
  available. Both exist; invoke by those exact names.
