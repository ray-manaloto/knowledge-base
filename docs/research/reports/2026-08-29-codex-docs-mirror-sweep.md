# Codex/OpenAI offline-docs mirror sweep — full evidence trail

Ray asked, verbatim (2026-08-29): "i wanted to find other sources that might
make blogs offline ... the searches i requested were not done or i dont have
evidence it was done." This report is that evidence: every tool from his
named list, the exact query run, and the exact result — including nulls.

Context: `sources/agent-harness-docs.manifest`'s `docs/codex/` content was
confirmed (2026-08-29) to be a strict subset of `chenrui333/codex-docs`'s
coverage — see `sources/REGISTRY.md` row 152 and issue #605. This sweep looks
for OTHER candidates beyond that one.

## Tool 1 — `context7` (direct MCP calls)

**Query**: `resolve-library-id(libraryName="OpenAI Codex CLI", query="Codex
CLI configuration, sandboxing, and command reference documentation")`

**Result**: 5 matches, most relevant:

- `/openai/codex` — the CLI's own repo, 2159 snippets, benchmark 78.59.
- **`/llmstxt/learn_chatgpt_llms-full_txt`** — context7's own indexed mirror
  of `learn.chatgpt.com/docs/llms-full.txt`. 1999 snippets, high reputation,
  benchmark 69.06. **Already offline-queryable right now, no manifest or
  registration needed** — context7 is an installed plugin in this session.
- `/shanraisshan/codex-cli-best-practice`, `/luohaothu/everything-codex` —
  configuration/skill collections, not doc mirrors.
- `/openai/codex-universal` — the reference Docker image, not docs.

**Follow-up query**: `query-docs(libraryId="/llmstxt/learn_chatgpt_llms-full_txt",
query="Codex CLI sandboxing and configuration file reference")`

**Result**: real, current-looking content returned verbatim — `config.toml`
examples, the full global CLI flag table (including `--dangerously-bypass-
hook-trust` and `--remote`, both recent-looking flags), sandbox commands.
Confirmed substantive, not a stub.

**Verdict**: real, immediately usable additional source. No repo to add to
`sources/` — it is queried live through the installed context7 plugin.

## Tool 2 — `firecrawl:firecrawl-developer-index` (direct MCP call)

**Query**: `firecrawl_developer_search(query="offline mirror of OpenAI Codex
CLI documentation and developer blog for AI agents, similar to
claude-code-docs", k=15)`

**Result**: 15 hits, none a genuine offline doc-mirror repo beyond what was
already known. Mostly comparison blog posts (Verdent, Tessl, Augment),
"awesome list" curations (`milisp/awesome-codex-cli`,
`ai-for-developers/awesome-ai-coding-tools`, `jamesmurdza/awesome-ai-devtools`)
that link OUT to official docs rather than mirroring them, and unrelated
Claude Code infrastructure repos. `milisp/awesome-codex-cli` is worth noting
as a curated link directory (not an offline archive itself).

**Verdict**: genuine negative result for NEW mirror candidates via this index.

## Tool 3 — `exa:search` (the skill, dispatched as a subagent per its own
"Moderate query -> 1 subagent" classification, not the bare MCP tool)

**Query given to the subagent**: find GitHub repos/archives mirroring OpenAI
Codex CLI docs, the OpenAI dev blog, or OpenAI cookbook content offline,
beyond `chenrui333/codex-docs`; 4 diverse search angles; validate each
candidate is real and on-topic.

**Result** (`sources_reviewed: 51`, 13 tool calls): two genuinely NEW
candidates, both control-armed by me afterward (not taken on the subagent's
word alone):

- **`mehmetbaykar/codex-docs-skill`** — mirrors `learn.chatgpt.com/docs` as an
  installable Agent Skill, 3-hour GitHub Actions sync. (Also independently
  found earlier this session via a bare exa search — corroborated twice.)
- **`milord-x/Codex-CLI-Wiki`** — confirmed real via direct fetch (2026-08-29):
  0 stars, single contributor, MIT, offline-first static HTML wiki with
  search, built from `codex --help`/`codex --version` verification against a
  locally-installed `codex-cli 0.115.0`. Small and low-adoption, but genuinely
  offline and genuinely about Codex CLI.

Also surfaced and correctly filtered as NOT candidates: `openai/openai-cookbook`
(the live primary source, not a mirror), `Devanik21/openai-cookbook` and
`kimtth/azure-openai-llm-cookbook` (annotated forks, not offline archives),
`ojesusmp/codex-guides` (generates docs USING Codex, not a mirror OF Codex
docs), `Pratiyush/llm-wiki` (archives the user's OWN sessions, not external
docs).

**Explicit negative finding from this subagent, worth keeping**: no OpenAI
developer-BLOG mirror exists with anything like `chenrui333/codex-docs`'s
maturity. The nearest thing for the *blog* specifically (as opposed to CLI
docs) is ad-hoc Archive.ph/Wayback snapshots, not a maintained GitHub mirror —
contrasted against Anthropic's blog having a dedicated mirror
(`chyornyy/anthropic_engineering_md`) with no OpenAI equivalent found.

## Tool 4 — `last30days` (direct engine invocation, `--auto-resolve --quick
--search=reddit,hackernews,github,web`, keyless free sources only)

**Query**: `"offline mirror repository for OpenAI Codex CLI documentation and
developer blog"`

**Result**: genuine null. The engine's internal deterministic planner (used
because I passed `--auto-resolve` rather than doing the full WebSearch
pre-research protocol the skill normally wants a reasoning model to run)
chose a mistargeted generic query (`"httrack wget mirror website repository"`)
and returned 0 items across Reddit/HN/GitHub/Web. Raw output saved by the
engine itself to `~/Documents/Last30Days/offline-mirror-repository-for-
openai-codex-cli-documentation-and-developer-blog-raw.md`.

**Caveat on this result's strength**: this is weak evidence specifically
because the auto-planner's query was poorly targeted, not because the topic
was exhaustively searched by a well-planned query. A hand-crafted `--plan`
(reasoning-model-authored, per the skill's own LAW 7) would be a stronger
probe if this remains open later.

## Tool 5 — `firecrawl:firecrawl-research-index` — DELIBERATELY SKIPPED

This index is scoped to academic/biomedical paper search (arXiv, life
sciences). It cannot answer "is there a GitHub repo mirroring Codex docs" —
using it here would be running a tool to say it was run, not because it could
answer the question. Named explicitly so the omission reads as a decision,
not a silent gap.

## Net finding

Two new, real, small-but-genuine candidates beyond `chenrui333/codex-docs`
(`mehmetbaykar/codex-docs-skill`, `milord-x/Codex-CLI-Wiki`), plus one
zero-setup-cost source already live (`context7`'s `/llmstxt/learn_chatgpt_llms-
full_txt`). None of the three is currently registered in `sources/REGISTRY.md`
or `sources/*.manifest` — that registration is a follow-up decision (see
issue #605, which currently only names `chenrui333/codex-docs`; these two
additional candidates should be folded into that same issue rather than a new
one, since it's the same underlying decision).

No dedicated OpenAI developer-BLOG mirror was found anywhere in this sweep —
that gap remains open and may not have a solution today (confirmed via 3 of
the 5 tools independently).

## GitHub repos touched

- [chenrui333/codex-docs](https://github.com/chenrui333/codex-docs) — the baseline this sweep compares against.
- [mehmetbaykar/codex-docs-skill](https://github.com/mehmetbaykar/codex-docs-skill) — new candidate, corroborated by two independent searches.
- [milord-x/Codex-CLI-Wiki](https://github.com/milord-x/Codex-CLI-Wiki) — new candidate, confirmed real via direct fetch.
- [milisp/awesome-codex-cli](https://github.com/milisp/awesome-codex-cli) — curated link directory, not an archive; read for context.
- [openai/openai-cookbook](https://github.com/openai/openai-cookbook) — the live primary source; read to confirm it is not itself a "mirror".
- [chyornyy/anthropic_engineering_md](https://github.com/chyornyy/anthropic_engineering_md) — named as the Anthropic-blog analog that has no OpenAI-blog equivalent; not fetched, cited from the subagent's search only (mark as unverified by me directly).
