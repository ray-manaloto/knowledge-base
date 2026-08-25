# Ray's directives — 2026-08-24 — VERBATIM

Written 2026-08-24 at `/clear-prep`, from the session that forked graphify onto
PR #2981, rebased it onto upstream v0.9.49, and ran `/grilling` on the
documentation-currency mandate. Session model Opus 5; the fable-orchestrator
flow was invoked repeatedly by Ray (`/fable-orchestrator:orchestration`).

The 2026-08-24 native-graphify ruling itself was filed a day early, as ADDENDUM
(c) of `2026-08-22-ray-directives.md` — *"just do native graphify
extract/reflection/generate output. stop doing internal hashing"*. Everything
below is new.

## On the fork — VERBATIM

> A new graphify release at v0.49.0 was released. Make sure our firk is from the
> latest git commit to pick up all changes

(The tag is **v0.9.49**, not v0.49.0 — released 2026-08-24T13:19:05Z, about four
hours after the fork. Recorded as spoken; the correction is measurement, not
editing.)

Asked which of PR #2981's commits the fork should carry, Ray chose **"Take the
whole branch as-is"** over a cherry-pick. Asked where the fork should live:

> Fork under ray-manaloto org

Asked how currency should treat a forked pin, Ray chose **both** a fork-aware
state in `currency.toml` **and** rebase-on-each-upstream-release. Asked how much
to do in one round: **"Everything — manifests and the fork"**. Asked how to
re-attest the deterministic baseline when `kb-build` was red: **"Re-attest
without a full kb-build"** — which was correct, `kb-graphify-baseline` is
Graphify-only and never touched the blocker.

## THE STANDING MANDATE — documentation currency — VERBATIM

Asked whether to run the six research questions, Ray answered with a directive
instead:

> option 2
> and since the claude subscription tokens are running out we must also update all:
> - documentation
> - AGENTS.md/CLAUDE.md
> - claude rules
> - hooks
> - MEMORY.md
> - skills
> - README.md and other markdown files
> - provide other changes needed
> to make sure all new changes are up to date and a handoff document for codex to
> take over if there are no claude subscription tokens remaining so that any new ai
> llm agent or human can take over and understand the new direction and not follow
> or work on old and stale documentation
>
> and enforce this practice going forward
> - even if another ai llm agent's subscription depletes and we need to go back to claude
>
> in summary the project needs to always be up to date and never has anything that
> is old/stal/incorrect/vague
>
> run the /grilling skill if there is any ambiguity so we have a shared agreement
> on what to do

`/grilling` was run. Two rounds were settled; the frontier was NOT emptied.

### Round 1 — settled

- **Enforcement**: ALL FOUR layers — a `kb-ship` gate, a narrow hook DENY, a
  rule file, and an advisory task. (Ray selected every option, not one.)
- **Predicate**: gate the machine-checkable set (stated-vs-derived numbers, dead
  paths, versions disagreeing with the pin, named tasks/flags that are gone);
  send "is anything here stale or vague?" to a `kb-review` lane, because a gate
  claiming to detect vagueness is a check that can only pass.
- **Scope**: all five doc load classes, with the gate scoped to what the diff
  TOUCHED — *"if your diff changes a fact, every surface stating that fact moves
  in the same commit."*
- **Handoff shape**: `AGENTS.md` as the loader-visible entry point plus the
  substance in vendor-neutral `docs/`.

### Round 2 — settled, and the recursive scheme — VERBATIM

> ensure every subdirectory has an AGENTS.md/CLAUDE.md
> where CLAUDE.md first line is:
> @AGENTS.md
>
> and then claude specific documentation/instructions are after
> see: sources/agent-harness-docs/docs/claude-code/memory.md
>      - section '### AGENTS.md'
> - i dont know where the https://github.com/thevibeworks/claude-code-docs offline
>   cloned repo is to point to that source instead

**MEASURED, and the cited source is STALE — which is this mandate proving its
own case.** The pinned mirror's `memory.md` says only that Claude Code walks UP
the directory tree from cwd; on that text the recursive scheme is inert. The
LIVE page (`https://code.claude.com/docs/en/memory.md`, fetched this session)
carries a sentence the mirror lacks: *"Claude also discovers `CLAUDE.md` and
`CLAUDE.local.md` files in subdirectories under your current working directory.
Instead of loading them at launch, they are included when Claude reads files in
those subdirectories."* **The scheme works.** Three more facts from the same
page: `@path` imports cap at **four hops**; imports load at launch so a root
`@AGENTS.md` deduplicates but saves NO tokens (the saving is entirely from
nesting); the target is **under 200 lines per CLAUDE.md**; and an
`InstructionsLoaded` hook exists that can PROVE the scheme fires.

The claude-code-docs clone Ray could not find does not exist yet —
`sources/claude-code-docs.manifest` was registered this session (@ `6b2327de`)
but `kb-build` has not cloned it. `sources/agent-harness-docs/` is still on disk
(39 MB, gitignored); only its manifest was deleted.

### On graphify as the fact registry — VERBATIM

> i'm not sure, but maybe if we can have it be mapped to graphify so it can be
> traversed to verify

and, on generated-vs-authored context files:

> option 2 unless we can achieve this via graphify

**REFUTED BY MEASUREMENT, live this session** over the 492,654-node aggregate:

    links 1,155,720   ast-ast 1,149,288   prose-prose 6,432   CROSS = 0

**Zero edges between the prose and code layers.** graphify can FIND where a fact
is restated; it cannot VERIFY the restatement against the code constant, because
the two layers never touch. A single `kb-query` against that graph also exceeded
**10 minutes**, so it could not be a gate even if the edges existed. The
recommendation carried into the next round is to generalise `currency.toml`'s
`ref_binding` — which already does exactly this verification, offline, in ~10 ms.

### On the codex docs source — VERBATIM

> /research if there is an offline documentation equivalent to
> https://github.com/thevibeworks/claude-code-docs for chatgpt/codex
> - else we still need agent-harness-docs to map for codex resync sources

UNANSWERED — the lane dispatched for it never reported.

## On the next round — VERBATIM

> option 4
> in addition to make sure all first level mise.toml and pyproject.toml
> dependencies are up to date and their sources are at least synced and graphify
> runs the AST steps on all dependencies
> - update <path>           re-extract code files and update the graph (no LLM needed)
>
> ensure all work is done w the /fable-orchestrator:orchestration skill

**"option 4" is RE-CURATE the exclusion catalogue** against graphify 0.9.49's
detector, so the 24 red semantic-corpus tests go green.

**THIS SUPERSEDES AN EARLIER ANSWER IN THE SAME SESSION**, and the reversal is
recorded rather than smoothed over: asked the same question two hours earlier,
Ray chose *"Make its tests fork-aware, don't re-authorize"*. The later ruling
wins. What changed in between is the measurement — retiring the layer was shown
to be surgically clean but NOT a fix for chunk 0009, so "don't re-authorize" no
longer bought a green suite.

Also ruled, by choosing to re-run rather than resume: **the `/grilling` session
starts from scratch next round**, not from this round's two settled rounds.

## On how the corpus decision was explained — VERBATIM

> /eli5 visually explain it to me using visual artifact skills and pros/cons to
> solution provided
> and what other research we should do

Answered as a published artifact (`Why 24 Tests Went Red`), updated once when
its own claim — that retiring would remove the red gate — was refuted by
measurement.

## What this round measured that bears on the brief

- **The `PreToolUse` hooks were running `mise exec` on every Bash and Grep call.**
  `.venv/bin/graphify hook-guard search` takes **0.116 s**; the `mise exec` form
  was **still running past 180 s**. Each held mise's tool-version install lock,
  which is what refused Ray's `mise update-all`. Fixed to call the venv binary.
- **Two tools in the USER's global `~/.config/mise/config.toml` cannot install** —
  `npm:renovate@44.37.1` (missing, install hangs) and `pipx:aider-chat@0.86.2`
  (scipy from source, needs an absent `gfortran`). While they are unresolvable
  every `mise run` in this repo hangs, which blocks every gate.
  `MISE_DISABLE_TOOLS="pipx:aider-chat,npm:renovate"` is the measured workaround;
  the fix is Ray's, in his own config (`do-not.md` #11 bars this repo from it).
- **`GATE_TASKS` is SEVEN** — lint, test, brain-audit, eval, graph-size, hk-test,
  kb-corpus-integrity. Repo prose has carried "four" and later "six".
- The fork's replant onto v0.9.49 was verified against upstream's own suite:
  ours **15 failed / 5057 passed**, pristine v0.9.49 **15 failed / 5019 passed** —
  identical failure set, +38 passing.

## ADDENDUM — the update-automation mandate, VERBATIM (2026-08-24, late)

Given as comments on the artifact `Sixteen Commits, No Passport` and as answers
to an `AskUserQuestion`. Recorded verbatim because this file is the standing
brief every round is measured against.

On the orchestration trigger — **"Remove the gate from line 31"**. Applied the
same turn; `.claude/CLAUDE.md` line 30 is now un-gated and carries the reason.

On task 2, answering *"how far should the single invocation reach?"* he chose
**the full chain including the graph rebuild**, and then said:

> i want i a visual artifact of this workflow
> it must include the skill pipeline
> the mise task(s) pipeline
> the python library module(s)/function(s) pipeline
> what config files are used and how/when
>
> should we be using tools like mermaid/uml-plant/etc to help build this
> - i want this to be synced w the code
> - i had asked for this to be researched previously if could annotate code to help generate the diagrams or use tools like:
>   - https://github.com/tree-sitter/tree-sitter-graph
>   - AST treesitter/LSPs for the call hiearachies
>
> any tools used should be added as a dependency to either mise.toml or pyproject.toml and must become a critical/currency dependency
>
> the rule is that any tool/library/sdk/api/framework/plugin/skill/etc this project used is added as a graphify source that is synced to the latest version of the dependency
> the session-review workflow should be analyzing the telemetry logs to determine what is not in mise.toml/pyproject.toml
> - this should probably be its own lane
>
> and to be more specific
> when reading the release-notes, the agent(s) need to analyze and think about how the changes affect this project and how to apply them to this project
>
> and use a universal logger for the python library so that stdout/stderr are not silently dropped
> and exporting the mise environment variable for outputting to a log file
> use /graphify skill, graphify query/explain tools and kb-query to help research

On what the automated command does when the six gates refuse — **options 1 and
2** (refuse-and-report AND an explicit override), plus:

> and maybe merge option 2 and 3 to different enums on why something was skipped w an optioonal comment in the historical transcripts
> - use code generation tools

### The nine obligations this creates

Numbered so a later round can cite one rather than re-reading the block.

1. **A workflow artifact with four pipelines drawn**: skill, mise task, python
   module/function, and the config files — *how and when* each is read, not just
   named.
2. **Diagrams generated from the code, not hand-authored** — the artifact must
   stay synced as the code moves. Mermaid / PlantUML / an equivalent.
3. **Research the generation mechanism**: code annotations,
   [`tree-sitter/tree-sitter-graph`](https://github.com/tree-sitter/tree-sitter-graph),
   and tree-sitter / LSP call hierarchies. **He notes he asked for this before**
   — treat a second unmet ask as the finding, not the request.
4. **Every tool adopted becomes a pinned dependency** in `mise.toml` or
   `pyproject.toml`, AND a **critical/currency-tracked** one.
5. **THE STANDING RULE, broader than this task**: *every* tool, library, SDK,
   API, framework, plugin and skill this project uses becomes a **graphify
   source synced to the latest version of that dependency**. This is a corpus
   invariant, not a step in one workflow.
6. **A session-review lane that reads the telemetry logs** and reports what the
   project actually invoked that is absent from `mise.toml` / `pyproject.toml` —
   the drift between what we *use* and what we *pin*. Its own lane.
7. **Release-note review is analysis, not summary**: the agent must reason about
   how each change affects THIS project and how to apply it here.
8. **A universal logger for the python library** so no subprocess `stdout` /
   `stderr` is ever silently dropped, plus a **mise environment variable
   exported for log-file output**.
9. **Skip reasons become a typed enum with an optional comment**, persisted in
   the historical transcripts — replacing the binary applied/refused split. Use
   **code generation** rather than hand-writing the enum plumbing.

Obligations 5, 6 and 8 are the ones that outlive this task; the rest are the
task. Research (3) gates the shape of (1) and (2), so it runs first.

### Settled by AskUserQuestion, same session

- **The emitter feeds BOTH consumers.** Ray: *"Yes — emit diagrams AND a graph
  source."* So `kb_setup.diagrams` emits mermaid for humans **and** an extraction
  chunk under `sources/extractions/` for the graph. One extractor, two consumers.
  The chunk carries the same drift gate as the diagrams.

  The measurement that made this the obvious answer, taken from `graph.json`
  directly: this repo is **7,054 of 492,654 nodes (1.43%)** across 58 sources —
  `codex` alone is 95,031, 13.5× our whole repo — and within our slice there are
  **zero** nodes for `mise.toml`, any `SKILL.md`, `currency.toml`, any `.md`,
  `CLAUDE.md` or `hk.pkl`. The four pipelines obligation 1 asks to draw are the
  exact nodes the graph lacks, so "query our own repo better" and "generate the
  workflow diagram" are one piece of work. Obligation 5's standing rule points
  the same way.

- **The rebuild ran, in parallel with the research** (Ray: *"run 2 and 3 in
  parallel"*). Note for whoever reads this later: clearing
  `graphify-out/.build-failure.json` by hand was **not** needed —
  `build_outcome.clear()` removes it after a build SUCCEEDS, so the record never
  gated the build. It was copied to the session scratchpad instead, so the
  original evidence survives whatever the run reports.

- **That record was a stale prediction.** It named
  `.agent/skills/blocking-io-guard/templates/anchor.template.py`, which **no
  longer exists** (control-armed: the same probe finds a 22 KB file under
  `.agent/` fine, and finds no `blocking-io-guard` tree and no
  `anchor.template.py` anywhere). `kb-currency-check` nevertheless announced every
  session that *"re-running `mise run kb-build` will fail again"* — a fresh
  prediction generated from a persisted record with no re-test of its cause.
  **Worth its own ticket regardless of how the rebuild turns out.**
