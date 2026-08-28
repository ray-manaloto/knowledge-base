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

## Three comments on the blueprint page (`aggregated-research-plugin-blueprint`, 2026-08-28 05:25–05:29), verbatim

On *"What a plugin can carry"*:

> make sure to use and add this schema to the the config file for the marketplace:
> https://json.schemastore.org/claude-code-marketplace.json
> and validate against it and use that as what we can add to a marketplace

On *"hooks/hooks.json"*:

> is there a schema for hooks.json?
> or do we use https://json.schemastore.org/claude-code-settings.json?

On *"No plugin mechanism downloads and installs an external CLI"*:

> but we can have a script that downloads the cli from repo as a github package or artifact

Read together: the marketplace manifest carries `$schema` and is validated against
it (that schema defines what a marketplace can hold); the hooks file's schema is a
question to answer by probing schemastore; and the CLI is delivered by a plugin
script (the documented `SessionStart` + `${CLAUDE_PLUGIN_DATA}` pattern) that
fetches it from a GitHub release/package — so "the plugin cannot install a CLI"
is true only of first-class manifest fields, not of the hook script.

## Two more blueprint comments (05:34–05:39), verbatim

On the CLI-vs-MCP fork:

> the aggregated-search cli can internally call other mcp servers if necessary

On the build order (anchored at the "Every step goes fable-advisor → codex-implementer" paragraph):

> the definition of done is to install the marketplace  and plugin in an isolated environment like a docker container that can be fully and autonomously installed via ai llm optimized instructions from a claude code agent only following the instructions from the marketplace and plugin's documentation
> our documentation needs to be very specific on what environment variables need to be set fo the dependency plugins/skills
> - such as:
>    - firecrawl
>    - exa
>    - context7
>    - last30days
> - it is oke to delegate the instructions to the other tools, it just needs to be very specific to direct where to look

So: the interface is CLI-only (the CLI may be an MCP *client* internally); and the
DEFINITION OF DONE is an autonomous install in an isolated container — a Claude Code
agent, given only the marketplace's and plugin's own documentation, installs the
marketplace, the plugin, its dependency plugins, and sets every required
environment variable for firecrawl / exa / context7 / last30days, with the docs
naming exactly where each is documented upstream.

## Five more artifact comments (05:08–05:56), verbatim

On the transport page (`the-team-is-a-transport`), title:

> this research was supposed to be done by the aggegated-search plugin
> you did not follow instructions

On the same page, "The picture in one line":

> did we review how https://github.com/openai/codex-plugin-cc works?

On the blueprint, the MCP row ("no — the CLI is the interface"):

> we can also deploy an mcp server
> but we are cli first
> is it possible to make the mcp features 1:1 with the cli?
> i would like to support the latest protocol standard: https://github.com/modelcontextprotocol/modelcontextprotocol
> can we use 3rd party libraries and sdks to rapidly prototype
> like:
> - https://github.com/modelcontextprotocol/python-sdk
> - or other popular libraries and sdks

On the blueprint, the LSP row ("no"):

> can we have it use these lsp servers:
> - astral-sh ty
> - https://github.com/facebook/pyrefly

On the blueprint, "docker container":

> use mise oci features to create the docker image
> can create a mise-first script that uses mise to install all the tools needed to build the cli and plugin from scratch
> can be tested via ci/cd gha workflow
> gha workflows can generate the artifacts to download if needed

Read together: (1) the agent-team research was to be run THROUGH the plugin; it was
run through the repo-local skill because the plugin did not exist — a sequencing
failure, recorded as such; the remedy is that the plugin's first real question,
and its acceptance test, is that same question re-run through it. (2)
`openai/codex-plugin-cc` (the `codex@openai-codex` plugin installed here) was NOT
reviewed and must be — it is a Claude↔Codex transport in production. (3) MCP is
a second surface, 1:1 with the CLI, on the current MCP spec, prototyped with the
official python-sdk or a popular library. (4) The plugin bundles `.lsp.json`
entries for `ty` and `pyrefly`. (5) The container is built with mise's OCI
features from a mise-first bootstrap script, exercised by a GitHub Actions
workflow that can also publish downloadable artifacts.
