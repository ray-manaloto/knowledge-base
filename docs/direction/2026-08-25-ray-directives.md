# Ray's directives — 2026-08-25 — the dependency sweep round

Verbatim where quoted. This file is the PRIMARY SOURCE for the rulings below;
`.claude/rules/do-not.md` #4 and its ten restatements descend from it and must
cite it rather than each other.

## 1. The sweep's scope — settled by AskUserQuestion

Asked how far the dependency sync should go, Ray chose **all five stages
including the rebuild**: bump the drifted pins, advance the manifests, fill
every gap, re-decide the exclusions, run the AST sweep, verify by query.

Asked which of the eight manifest-less pins should get a source, he chose
**"All eight, uniformly"** — over the three narrower subsets offered. The stated
rationale is the standing rule already recorded as obligation 5 of the
2026-08-24 directive: *every* tool, library, SDK, API, framework, plugin and
skill this project uses becomes a graphify source. It is a corpus invariant, not
a per-source judgment call.

Asked about `ffmpeg`'s build state, he chose **"Include — measure before
excluding"**. A large C codebase is not a reason to exclude; an unmeasured cost
is not a budget decision. `defer` requires a number.

## 2. THE RULING THAT CHANGES AN INVARIANT — openai-cli is permitted

Verbatim:

> we are going with claude-cli and openapi-cli as agents that can perform
> graphify agentic work
> - so remove and/or refactor the phrasing for #4 in .claude/rules/do-not.md

This **relaxes** the Claude-only mandate that has governed every extraction in
this corpus. `do-not.md` #4's phrasing goes; `claude-cli` and `openai-cli` are
both sanctioned graphify agents.

Three facts the rewrite must carry, all read from the installed fork this
session, because the existing prose gets the mechanism backwards:

1. **`clean_env()` was never what enforced Claude-only for the CLI backends.**
   `llm.py:3412` — `detect_backend()`'s fallback loop excludes `claude-cli` AND
   `openai-cli`, so neither can EVER be auto-selected regardless of environment.
   `clean_env()` stops the *key-driven* backends. Every sentence crediting
   `clean_env()` with the CLI carve-out is **misattributed**, and a naive
   rewrite preserves the error.
2. **`clean_env()` needs no change.** `_call_openai_cli` (`llm.py:1868-1885`)
   shells `codex exec` and reads no API key — only `GRAPHIFY_OPENAI_CLI_MODEL`,
   `_EFFORT` and `_PARALLEL`, none of which `clean_env()` strips.
3. **Keeping the `OPENAI_API_KEY` strip is now load-bearing for a NEW reason.**
   The upstream patch comment (`llm.py:1870-1874`) says the CLI route exists to
   stay on the owner's ChatGPT OAuth subscription, and that reverting it "can
   send the same work through a metered `OPENAI_API_KEY` instead". Stripping the
   key removes that possibility. Do not relax it while relaxing the rule above.

`.claude/rules/ai-cli-invocation.md:25-29` states the OPPOSITE in plain terms
("None of these lanes may do the corpus's LLM work") and is the highest
contradiction risk if the rewrite misses it. Issue **#455**'s entire premise was
this invariant and should be closed or superseded in the same change.

## 3. codex comes out of `build = skip`

Chosen: advance the manifest FIRST (`rust-v0.149.0` -> `0.149.1`), re-derive the
zero-node file list against the NEWLY pinned bytes, register one
`ExpectedMetadataOnly` entry, then flip to `include`. Registering a hash for
bytes we do not build is a silent failure, which is why the order is fixed.

The `learn.chatgpt.com` crawl is explicitly deferred:

> we will do option 2 later once we decide how to create our own protocol for
> getting offline versions of documentation similar to how thevibeworks repos
> are done

## 4. Sources must include their DOCUMENTATION, not just their product repo

Verbatim, the general rule:

> in general, we should try to sync a dependency to at least is product repo and
> other additional documentation sites that can be made offline

Named instances:

- **antigravity-cli** — eventually an offline scrape of
  <https://antigravity.google/docs>, crawling `robots.txt` / `sitemap.xml` and
  saving each page as markdown (already supported upstream, e.g.
  `https://antigravity.google/docs/cli/overview.md`).
- **codex** — also sync
  <https://github.com/mrkhachaturov/agent-harness-docs> (the
  `sources/agent-harness-docs/docs/codex` subtree) and
  <https://github.com/openai/codex>; plus a crawl of `learn.chatgpt.com` via
  `robots.txt`, `sitemap-index.xml`, `chatgpt-sitemap-0.xml`, pages as `.md`
  (e.g. `https://learn.chatgpt.com/docs/skills-and-plugins.md`).
- **claude-code** — `currency.toml`'s `docs_watch` list of three
  `code.claude.com/docs/en/*.md` pages is called out as INCORRECT:

  > we should be using the repos from thevibeworks

**Before adding a crawler dependency, check the pinned ones.** `firecrawl-cli`
1.23.1 (sitemap map + scrape-to-markdown) and `trafilatura` 2.2.0 (sitemap
crawling + extraction) are both already pinned and both now have manifests.
`use-tool-builtins.md` makes researching those the first step, not a courtesy.

## 5. The dependency table — the round's flagship deliverable

Verbatim:

> it would be easier if we can generate a tabular report from:
> - mise.toml
> - pyproject.toml
> - currency.toml
> - generated manifest files
> - suggest other files
> - that outputs these columns
>   - dependency
>   - declared file: mise.toml / pyproject.toml
>   - sync enum status
>   - datetime timestamp of last sync
>   - latest version or git sha
>   - last resync version or git sha
>   - suggest other columns

All proposed additions were accepted: clone-vs-manifest drift, nodes-in-graph,
currency-tracked?, owning bump tool, build state + exclusion reason + docs
sources, and the extra inputs `uv.lock` / `mise.lock` /
`.currency-stamp.json` / `graph.json`.

Then the clause that changes its shape:

> research all the steps done for the resync and deep extracton, reflection,
> generated artifacts. add all possible steps being done into the table

So the table is a **dependency x pipeline-step matrix**, not a dependency list.
`.agent/kb/reports/agents/pipeline-steps.md` is the inventory it rests on: 22
steps, each marked PER-SOURCE or WHOLE-GRAPH, each with "what file on disk would
prove this ran" — and nine gaps where the honest answer is *nothing records it*.
Those must render as UNKNOWN. A table that invents a green cell for an
unrecorded step is worse than no table.

## 6. Process

Asked how to spend a session already over its context threshold, Ray chose
**let the lanes land, then `/clear-prep`** — and, for the missing
`currency watch-reviewed` command, **ticket it and hand-append the notes for
now** (#486). `currency.toml` is the record, not a pin, so hand-editing it does
not violate the owning-tool rule.

## 7. ADDENDUM — the code generator owns every model type (2026-08-25, later)

Asked whether `decide()`'s six arguments should be wrapped by a hand-written
dataclass or by generated Structs, Ray chose **generated**, and restated a
standing requirement that is wider than the question asked. Verbatim:

> i had already requested all model data types, enums and any other code a code
> generator to generate be the protocol
> and if there are common types and enums to move them to a base schema that is
> available to the other schemas

Two obligations, and the second is new here:

1. **Anything a generator can generate, a generator generates.** Model data
   types and enums are not hand-authored. `datamodel-code-generator` is the ONE
   owner (Directive R6, 2026-08-08) and this extends it from the three existing
   schemas to the currency engine's own type family.
2. **Common types and enums live in a BASE schema the others `$ref`.** Not
   copied per schema. Today there is no base schema — `source-groups`,
   `fetch-receipt` and `session-select` each stand alone, and
   `session_select.py` already imports from `source_groups.py`, which is
   generated-module-to-generated-module coupling standing in for a shared base.

### What that costs here, measured 2026-08-25

The obstacle is real and was surfaced before the ruling
(`docs/artifacts/what-the-generator-cannot-reach.html`): a JSON Schema cannot
describe a method, and generated models in this repo carry **0 methods across 41
classes**. Three of `decide()`'s six argument types carry properties the gates
call — `SyncStatus.drifted`/`.ok` (`sync.py:88-94`), `ViewStatus.quiet`
(`views.py:122`), `Observation.usable`/`.differs_from` (`issues.py:43-68`). So
adopting this ruling means those properties move OUT of the types and into
module-level functions. That is a change to the currency engine's core shape,
accepted deliberately rather than discovered later.

### Two gaps this uncovered, both open

- **`session-select` has no mise task at all** — neither generate nor check,
  though `schemas/generate_session_select.py` and
  `schemas/check_session_select_codegen.py` both exist. One of three generators
  is unregistered; control-armed, only four `*-codegen*` tasks exist and both
  belong to the other two.
- **No codegen check runs in any gate.** None appears in a `depends` anywhere,
  so even the two registered ones only run when someone types them.
