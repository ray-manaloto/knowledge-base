# Ray's directives — 2026-08-27

Verbatim. This file is the PRIMARY SOURCE; anything restating it must cite it
rather than another restatement. Session `kb-20260827.06`, the grilling of the
aggregated-research plugin (rounds 1–4) and the lychee work.

## Standing directives, verbatim

> /fable-orchestrator:orchestration use fable-advisor with codex-implementer

> always use the fable-advisor with codex-implementer

Both mid-turn, 2026-08-27. The second generalises the first: **every
`codex-implementer` dispatch is preceded by a `fable-advisor` consult** — the
advisor at the commitment boundary, codex as the implementation lane.

## The grilling — every answer, verbatim where Ray typed it

Round 1 (AskUserQuestion, then artifact comments):

> Q1: see my comments · can you take a step back and review especially how
> /deep-review workflow and /antigravity:research work as the structure where
> we use all these sources to query for information and provide the workflow ·
> be very detailed · use the /eli5-visual skill w fixes i've been asking for and
> using the mermaid mcp · must list all tools/libraries/sdks/mcp/plugins/skills
> used and where · also, use the already existing plugins/skills to search for
> a way to use lychee's library functionality to bind to our python library
> (python to rust bridge). Regarding this feature: https://lychee.cli.rs/guides/library/:
> /last30days:last30days · /firecrawl:firecrawl-search ·
> /firecrawl:firecrawl-developer-index · /firecrawl:firecrawl-research-index ·
> /exa:search · /context7:context7-mcp or /context7:docs · i would also like to
> use lychee on this library now to scan and validate the links in our
> code/documentation - if we can make it a custom hk linter

> Q2: Both, on-demand first · Q3: Any of your repos · Q4: probably option 2
> (see artifact comments)

Artifact comments, round 1 (`what-is-aggregated-research-for.html`):

> is this where lychee or similar tools will be used?
> most likey just A as we want to be able to tune the models/effort/family
> (claude or codex) that /deep-research does not provide the ability to tune
> also want to prefer by tools/libraries/sdks/frameworks/etc that are actively
> being worked on (filter by release date/git commit/etc)
> missing: firecrawl search and developer index search · context7 · also
> missing /antigravity-research skill
> we might need /deep-research workflow but use its techniques/structure/workflow
> this is still black-on-black text · use the mermaid mcp to help fix this and
> update the /eli5-visual skill

Round 2:

> Q1: Mostly — with changes I will comment on the page · Q2: Tiered · Q3: Built
> + offline pre-commit · Q4: Nothing yet — finish the grilling first

Artifact comments, round 2 (`the-research-spine.html`):

> we have to build the python to rust binding using a modern framework library
> use agy instead of gemini
> context7 too
> is the firecrawl mcp necessary or can we just use the firecrawl cli? — make
> sure the firecrawl cli is pinned to the latest version in mise.toml

Round 3:

> Q1: PyO3 0.29 + maturin 1.15 · Q2: asyncio-native await check() · Q3: Own
> repo, after a spike here · Q4: Add it anyway

Round 4:

> Q1: Plugin · Q2: option 1 with the ability to output in machine readable
> structured output for other systems to be able to pass along · Q3:
> deep-research constants as per-call defaults · Q4: Wait for the fable-advisor
> verdict first

## Where each landed

- The design tree: `docs/artifacts/what-is-aggregated-research-for.html`
  (<https://claude.ai/code/artifact/668c6e9c-9211-47c8-aefa-afb797dff721>).
- The spine, both engines dissected, the tool inventory, the binding decision:
  `docs/artifacts/the-research-spine.html`
  (<https://claude.ai/code/artifact/a3bf44f2-f540-4d72-ae38-fba84f6c8534>).
- The lychee sweep: `docs/research/reports/2026-08-27-lychee-from-python.md`.
- lychee as an hk linter: `hk.pkl` (`lychee`, `lychee_offline`), `lychee.toml`,
  `mise run kb-links`, `currency.toml` `[tool.lychee]`, `mise.toml` `lychee = "0.24.2"`.
- The mermaid mechanism and fix: `.claude/skills/eli5-visual/SKILL.md` §2b.
