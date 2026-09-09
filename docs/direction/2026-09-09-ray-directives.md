# Ray's directives — 2026-09-09

VERBATIM. This file is the standing brief a round is measured against; do not
paraphrase, and do not "tidy" the wording. Session `kb-20260909.001`. Tracked as
**#726** (parent) with children **#727–#733**; the one-page agreement is
`docs/artifacts/upgrade-workflow-grill.html`.

## 1. The ask

> create a dynamic worklow to perform the following steps:
> 1. update the graphify fork for the openai-cli backend to rebase to the latest graphify latest git commit and update the graphify skills in:
> - .agents/skills/graphify
> - .claude/skills/graphify
>
> ensure the skills have the latest graphify version in:
> - .agents/skills/graphify/.graphify_version
> - .claude/skills/graphify/.graphify_version
>
> 2. update and/or add modular skill(s) -> mise task(s) -> python library module(s)/function(s) to update all first level mise.toml and pyproject.toml dependencies and their graphify sources
>
> add this as pwf task plan items with linked github issues to ensure all of this is the top priority and completed first
>
> the workflow must have subagents optimized for roles/model/effort and anything else that can be customized for a subagent as we want to save and reuse these subagents and workflows going forward
>
> run /grilling until there is a shared understanding and there is no ambiguity

## 2. The fork work happens in ONE place

Round 1, on who performs the rebase (he chose "Claude does it inline" and added):

> but must perform work in the existing local directory: /Users/rmanaloto/dev/github/ray-manaloto/graphify
> ensure this is where all work on the fork going forward

**Scope:** every future rebase, patch and test run of the graphify fork uses that
checkout — never `sources/graphify/` (the gitignored corpus clone) and never a
scratchpad. The checkout has `origin` = the fork and `upstream` = Graphify-Labs.

## 3. Search before designing — and never forget it

Round 1, when asked where the dependency-update machinery should live:

> we have been working towards this already
> the dynamic workflows should search this project, git local branches or git worktrees, github issues, plasn (include from ~/.claude)
> and ensure we never forget this

**Scope:** phase 0 of the saved workflow (`kb-recall-work`, #727) searches the repo,
local branches and worktrees, GitHub issues, and plans under `.planning/`,
`.agent/plans/` and `~/.claude/plans/` before any design step, and reports what it
found. It was right: 13 published design pages, ~10 plan files, 7 handoffs, ~12
unmerged branches and 199 matching issues already existed for this exact topic.

## 4. The August machinery design is input, not a constraint

Round 2, asked whether to continue #638's design as ruled: **"Re-decide from
scratch."** Round 3, asked where per-dependency state lives:

> [SQLite + DBOS] but dynamic workflow must reresearch this and update it to use modern best practices and check for any inefficiencies/bugs/issues/vagueness

and, asked what happens to `currency.toml`:

> should be part of the dbos systems that we are trying to build
> add dynamic workflow steps needed to research and architect  this system

**Scope:** DBOS on SQLite remains the direction; `currency.toml`'s judgment folds
into that system; the workflow carries an explicit research-and-architect phase
(#729) that re-verifies the library and audits the prior design before anything is
built (#730).

## 5. Review the unpushed commit before deciding its fate

Round 2, on the fork checkout's one unpushed commit `6ca68bd`: **"review what that
commit is first."** Reviewed (Phase G commit 1, #518 — 928 lines + 630 test lines,
premise-verified twice, no cold review, upstream since changed all three files it
edits); round 3 ruling: **park it on its own branch**; only the eight pushed
patches replay.

## 6. Who builds, who reviews, who the agents are

Round 4: two layers (Python engine for every mechanical step; the saved Claude
workflow for judgment only) · **"I build it, codex reviews cold"** · roster:

> option 3 [eight new roles]
> should be re-examined after the graphify sources for claude have been resynced
> especially from: sources/claude-code-docs/content/en/docs/claude-code

**Scope:** the roster's final knobs (#732) wait for the Claude Code sources resync
(#731); one commit per dependency and one PR per run.

## See also

- `docs/direction/2026-09-03-ray-directives.md` — the previous brief.
- `#726` — Phase V, which every directive here shapes; `#672` — Phase U, which
  resumes after it.
