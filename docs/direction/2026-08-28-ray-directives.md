# Ray's directives — 2026-08-28

Verbatim. This file is the PRIMARY SOURCE; anything restating it must cite it
rather than another restatement. Session `kb-20260827.08` (the trackers adapter
review + land, and the lychee-py spike).

## Session opener, verbatim

> /i-have-adhd
> /ponytail ultra
> /fable-orchestrator:orchestration
> /graphify
> /kb-resume
> use fable-advisor andcodex-implementer lanes

## The three answers (AskUserQuestion option labels, verbatim)

1. Resume: **"Start step 3: cold review (Recommended)"** — the trackers adapter's
   cold review → refutation → merge → receipt → `kb-ship` → `kb-land`. Landed as
   PR #557 (`aefb65ff`).
2. Spike exit: **"C: measure latency first (Recommended)"** — one more bench
   before committing the binding's cost.
3. After the bench: **"A: stop — keep the CLI in hk (Recommended)"** — the
   lychee-py binding is NOT built. This supersedes the 2026-08-27 round-3 answer
   *"Own repo, after a spike here"*: the spike ran, and its numbers ended it.

## Where each landed

- The trackers adapter: `python/src/kb_setup/research/trackers.py`, PR #557.
- The spike: `docs/research/reports/2026-08-28-lychee-py-spike-result.md`;
  `docs/artifacts/the-binding-and-the-spawn.html`
  (<https://claude.ai/code/artifact/b824161f-70f5-44f8-91b8-15e61253bbf3>).
- The `#lt;`/`#gt;` mermaid lesson: `.claude/skills/eli5-visual/SKILL.md` §2b
  (both copies), per the 2026-08-27 "add it to §2b" answer.

## The correction, verbatim (AskUserQuestion free text, after the clear-prep "next task" question offered backlog triage)

> you are not following our historical plans
> we want to use aggregate-search plugin to search how to build a claude/codex agent team that optimizes use of limited fable-5 tokens and communication between claude and codex agents
> and the ultimate goal of graphify setup starting with openai-cli backend

This is the next round's task, and it is the 2026-08-27c rescope's steps (2)–(3) — point
`aggregated-research` (#509, the plugin Ray calls "aggregate-search") at the question of a
Claude/Codex agent team that optimises limited Fable-5 tokens and the Claude↔Codex channel —
with the standing end goal named explicitly: graphify running on the fork's `openai-cli`
backend. Backlog triage (step 4) is NOT the next round.

## Correction, verbatim (artifact comment on `where-the-aggregated-research-plugin-stands`, 2026-08-28 05:05, on the row that read *"lychee-py binding … you chose 'A: stop — keep the CLI in hk'"*)

> i didnt understand your question
> I didnt want to stop this work
> i wanted a full cli built for aggregated-search plugin

Two things this settles. The "A: stop" answer above was about the **PyO3 binding
only** — it did not stop the plugin, the `links` module, or the CLI work; the prior
session's *"the lychee-py binding is NOT built"* reading stands, but nothing wider
was ever stopped. And the deliverable is a **full CLI for the aggregated-search
plugin** — the plugin ships a CLI, not only a skill. The 2026-08-27 decisions
(staged in `kb_setup/research/`, split out to a `uv`-installable package, plugin
in `ray-manaloto/claude-code-marketplace`) are the HOW; this names the WHAT the
marketplace step was waiting on.

Also, in the same session, the opener verbatim: *"we have not setup the
aggregated-search plugin from the https://github.com/ray-manaloto/claude-code-marketplace
- review session history and previous plans on this"* — measured: the marketplace
still holds only `mise-toolkit`, 0 tags, last push 2026-04-08; this repo still runs
the local skill; 1 of 3 adapter modules exists (`trackers.py`, #557).

## The plugin's shape, verbatim (AskUserQuestion free text, after the CLI-shape question)

> research all that can be bundled in a claude code plugin
> it should work similar to the plugins for the firecrawl cli and ctx7 cli

So the next step is research, not a spec: what a Claude Code plugin can bundle
(the manifest schema and the docs at the pinned `claude-code-docs` ref), and how
the installed `firecrawl` and `context7` (ctx7) plugins wrap their CLIs — that
pair is the model for the aggregated-search plugin.
