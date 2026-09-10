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

   **Before DESIGNING anything, also run `mise run kb-recall-work -- "<topic>"`**
   (#727; Ray, 2026-09-09: *"ensure we never forget this"*). It searches this
   repo, the sibling checkouts, branches and worktrees, issues open and closed,
   every plan and the work-memory, with an examined count beside each match. It
   is phase 0 of every saved workflow and is never skipped: the day it was built,
   13 design pages, ~10 plans and ~12 branches already existed for the topic.

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

## When you need EXAMPLES rather than docs, SEARCH GITHUB — all four indexes

The chain above answers *"what do the docs say"*. It does not answer *"how does
anyone actually use this"*, and for an undocumented or experimental feature that
is the only answerable question. **GitHub is a first-class source here, not a
fallback.**

**Ray has asked for this FOUR times** — `docs/direction/2026-08-26:62`,
`2026-09-03:55`, and twice on 2026-09-10, the last verbatim: *"we need to start
actually using github as a source of information on how to find examples."* It
was never written down, so it was never done. That is why it is a rule now
rather than a preference.

### The four indexes are four different answers

Search **code**, **repositories**, **issues** and **discussions** separately.
Measured 2026-09-10 on `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS`: the code index alone
would have found **20% of the dedicated projects and none of the issues** — 4 of
5 dedicated repos appeared in no code result, and **the two most valuable
artifacts of that day were issues**. A code-only sweep is not a GitHub search;
it is one quarter of one.

### `gh api`, never `gh search`

```bash
gh api -X GET search/code   -f q='<query>' --paginate
gh api -X GET search/issues -f q='<query>'
```

Still prefer `gh api` — but this rule's REASON was refuted, armed on gh 2.98.0
by a cold review of `7b28f460`. It claimed `gh search` "returns an empty array
rather than an error", making a missing token look like no results:

| failure | `gh search code` | `gh api search/code` |
|---|---|---|
| missing token | **rc 4**, auth error | **rc 4**, same error |
| bad `repo:` scope | rc 0, `[]` | rc 0, `incomplete_results: true` |

Missing-token is false, and false SYMMETRICALLY — no reason to prefer either.
Bad-scope holds, and what rescues it is a field this rule never named:
**`incomplete_results`**, carried by the raw body and dropped by `--json`/`--jq`.
That is the discriminator; the exit code is not. **Unarmed, so open:** whether a
rate limit reaches you as a zero. Never report one as a zero — this rule just no
longer claims to know how you would tell.

### A bare query is mostly noise, and this is measurable

GitHub's legacy code tokenizer splits on `-` and `.`, so `plugin-types` returns
**288,256** junk hits and quoting does not help. `filename:`, `path:`, `repo:`
and `language:` qualifiers are what make a query discriminating. A tool that
takes a bare string and no qualifiers will mostly return noise.

### Control-arm every zero, and pin every quote

Before reporting a search found nothing, run the same shape against a term you
KNOW has hits and say which arm you ran — `probes-need-a-control-arm.md` rule 1,
and code search is where it bites hardest because so many zeros are real.

Permalinks go to a **commit SHA**, never a branch: a branch link rots silently
and takes your quoted bytes with it. Note that a commit-pinned link still does
not prove the bytes you quoted are at that commit — only a blob fetch does.

### Then route it into the corpus

Same obligation as the rest of this file: a repo worth reading is a candidate
source. Append it to `sources/REGISTRY.md` at minimum
(`research-repo-enumeration.md`), and prefer a `sources/<name>.manifest` when the
examples are worth querying later.

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
