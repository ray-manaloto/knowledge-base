# Research Doc Sources: Preference Chain

When an agent or skill needs to fetch library/framework/tool documentation
during research, it MUST walk this preference chain top-to-bottom and use
the first option that returns the answer. Lower steps cost more tokens
(per-query or per-conversation) — never skip a step that would have worked.

## The chain

0. **Query the graph first.** This repo *is* the cache. Run
   `mise run kb-query -- "<question>"` (deterministic BFS/DFS, no LLM,
   source-cited) before any network call — the answer may already be ingested,
   and a graph read spends **zero** LLM tokens. `graphify path "A" "B"` and
   `graphify explain "X"` are the relationship/concept variants and are
   allowed direct (read-only, no task equivalent).

   **This step is machine-enforced (#253).** `kb_setup.graph_first` DENIES a
   repo- or directory-wide source search until one graph query has run in the
   session, and prints the exact `mise run kb-query` to run. A `Read` of a named
   file, a search scoped to ONE file, and any search of prose/logs/`/tmp` are
   never denied — the target is *orientation*, which is the job the graph
   replaces. There is no override token, by Ray's explicit decision. The
   enforcement exists because the prior *warning* was measured at **0 of 19**
   compliance in one session, against 62→0 for the guard that denies.

   **Control-arm an empty result** before concluding the corpus lacks it — see
   `probes-need-a-control-arm.md` § "The graph is a probe too". A miss may be a
   term-spelling mismatch against the extracted node labels, not an absence.

1. **`curl <site>/llms.txt`** — AI-optimized plain-text index, one entry per
   page. The cheapest *remote* lookup. `grep` the output to pick the page(s)
   you want.

2. **`curl <site>/<path>.md`** — for mintlify-hosted sites, appending `.md` to
   any visible page URL returns clean markdown (no HTML chrome, no JS). Use
   this once step 1 has told you which page you want.

   **Do NOT guess a project's docs domain.** A plausible-looking domain that
   404s is not evidence the docs don't exist — it is a probe with no control
   arm.

3. **`ctx7`** — for libraries whose docs live outside mintlify, or where
   `llms.txt`/`.md` doesn't cover what you need. It is a **direct
   doc-fetcher**; call it straight, in two steps:

   ```bash
   ctx7 library <name> [query]        # resolve a name -> Context7 library ID
   ctx7 docs <libraryId> <query>      # fetch the docs
   ```

   Its `skills` subcommands still run but are **hidden from `--help` and
   deprecated** — do not build on them, and do not treat their absence from
   `--help` as proof they are gone.

4. **Raw HTML fetch** (`curl <url>`) — **last resort only.** Pays the full
   HTML-parse cost in agent context.

## If it was worth fetching, it is probably worth ingesting

That is the whole point of this repo. A doc you fetched at step 1–4 answered
*your* question and then vanished. Route it into the graph so it answers the
next session's too:

- a code repo → `mise run kb-manifest-add -- <url>` then `mise run kb-build`
  (AST extraction is **free**, no LLM);
- prose/a URL → `mise run kb-add -- <url>`, host-agent extract, then
  `mise run kb-merge -- <chunk>`;
- always close with `mise run kb-remember` + `mise run kb-reflect`.

At minimum, append the repo to `sources/REGISTRY.md` — see
`research-repo-enumeration.md`.

## Why per-repo mintlify MCP URLs are NOT in the chain

`https://mintlify.com/<owner>/<repo>/mcp` URLs are **GET-only preview
descriptors** auto-generated for every repo Mintlify indexes. `curl GET`
returns a JSON tool-schema descriptor; POST (which `mcp2cli` sends to speak MCP
protocol) returns `404 Not found`. There is no live MCP server behind the
descriptor.

Live mintlify MCP servers exist only at the customer's own documentation
domain (e.g. `docs.anthropic.com/mcp`). Mintlify's central MCP at
`https://mintlify.com/docs/mcp` works but is scope-limited to Mintlify's own
platform docs — it does not search per-repo customer sites. **An API key does
not unlock this path**: Mintlify keys are organization-scoped.

`mcp2cli` itself remains fine for **other** MCP servers, including a customer-
domain MCP. The ban is specifically on per-repo mintlify subpath URLs.

## `mcp2cli`-first, but MCP registration is allowed when required

**Prefer `mcp2cli` (process-spawn) or the curl-based options above** for one-off
doc/tool lookups. Registering an MCP server natively injects every tool's JSON
schema into Claude's system prompt for every conversation, forever — even
conversations that never call the tool pay that context tax.

**But native MCP registration is NOT forbidden.** When a third-party plugin or
tool **requires** MCP for its features, registering it is allowed, done
knowingly. This is a documented **preference**, not a gate.

**The required companion: check before you register.** `codex mcp add --url`
once wrote a USER-GLOBAL `~/.codex/config.toml` entry that collided by NAME
with this repo's PROJECT `[mcp_servers.kb]` entry and broke codex outright
(`url is not supported for stdio` — `.codex/config.toml:122`). Ray accepted
that risk knowingly, on the condition that this check runs first: before any
registration command, establish (a) whether it writes user-global or
project-scoped config, and (b) if user-global, whether a project entry of
the SAME NAME already exists. Do not register under a name already claimed
in the other scope.

Judgement call: query it rarely → `mcp2cli` wins on cost; the plugin's value
depends on Claude selecting its tools natively and you'll use it often →
register it. When unsure, reach for `mcp2cli` first.

**`mise run kb-serve` is this repo's own MCP server** — read-only, pinned to
an absolute `graph.json` path so multiple graphify projects never collide. Its
tools are graph reads and spend zero LLM tokens.

## See also

- `research-repo-enumeration.md` — record which repos an artifact touched.
- `use-tool-builtins.md` — the parent principle; this chain is that principle
  applied to doc fetching.
- `probes-need-a-control-arm.md` — a 404 or an empty result is not an answer.
