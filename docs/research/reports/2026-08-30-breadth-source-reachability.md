# breadth source reachability (#577)

Date: 2026-08-30

## Verdict

**Source count confirmed: 4** — `firecrawl`, `exa`, `context7`, `last30days`, read
directly from the aggregated-research plugin manifest
(`plugins/aggregated-research/.claude-plugin/plugin.json:7-12` in
`ray-manaloto/claude-code-marketplace`).

**All four are reachable from a headless, non-Claude-session process**, but
**not through one shared transport/record shape** — they split into three
distinct reachability classes, which forces `breadth` to be **more than one
adapter ticket**, the same shape of premise failure #576 found for
codesearch:

| Source | Reachability class | Invocation the standalone CLI would use | Auth |
|---|---|---|---|
| `firecrawl` | installed CLI binary | `firecrawl search "<query>"` (mise-pinned `npm-firecrawl-cli@1.23.3` on PATH) | `FIRECRAWL_API_KEY` env var |
| `context7` | installed CLI binary | `ctx7 library <name>` / `ctx7 docs <id> <query>` (mise-pinned `npm-ctx7@0.5.8` on PATH) | stored login session (`ctx7 login`), not env-var based |
| `exa` | direct HTTP client, no CLI on PATH at all | `POST https://api.exa.ai/search` with header `x-api-key` | `EXA_API_KEY` env var |
| `last30days` | subprocess of a **vendored script inside a Claude plugin clone**, not an installed binary and not on PyPI | `uv run <plugin-clone-path>/skills/last30days/scripts/last30days.py "<topic>" --search <sources>` | none required for the free/keyless sources probed; several per-source keys are optional |

This directly corrects premise **L4** in the dispatch spec, which asserted
last30days is "only reachable in a Claude session via its skill." That premise
was checked with `command -v last30days` alone, which only tests for a named
PATH binary. last30days ships no such binary — it is a bundled Python script —
but the script itself ran cleanly outside any Claude session in this probe
(see below), returning real, discriminating data. **Absence of a PATH binary
is not absence of headless reachability**; the earlier premise conflated the
two.

## Method and evidence authority

Live probes were run directly in this session (not inherited from a prior
transcript), on 2026-08-30, from this repository's working directory unless
noted. Every negative or auth-only result below is paired with a control arm
per `probes-need-a-control-arm.md` rule 1 — a known-good input using the
identical command/transport shape.

Graph orientation was attempted first per `research-doc-sources.md` step 0:
`mise run kb-query -- "aggregated-research plugin dependencies firecrawl exa
context7 last30days"` returned 182 BFS-truncated nodes, none topically related
to the aggregated-research plugin or its four dependencies (unrelated matches
on the literal tokens "research", "dependencies", "Plugin", "Exa" as an
unrelated Python variable name, etc.). This is the corpus's genuine scope: the
aggregated-research plugin lives in the sibling `claude-code-marketplace`
repo, not in this one, and has not been ingested here. The graph check is
recorded as a completed, negative-but-armed step, not skipped.

## Acceptance criteria

- [x] **1. Source count and shape.** Verdict states 4 sources (confirmed from
  the plugin manifest, cited above) and that they do **not** converge on one
  transport/record shape — three classes, detailed in the table above.

- [x] **2. Every reachability claim is control-armed.** See per-source
  sections below; each negative-looking result (an auth error, a 404, a
  missing PATH binary) is paired with a known-good probe on the identical
  transport.

- [x] **3. Reachability is judged from a headless, non-Claude-session
  vantage.** No `mcp__claude_ai_Firecrawl__*`, `mcp__plugin_exa_exa__*`, or
  `mcp__plugin_context7_context7__*` tool was invoked anywhere in this spike.
  Every probe below is a bare CLI subprocess or a bare `curl`/HTTP call, per
  A1.

- [x] **4. Findings are written to this tracked research report.**

## Per-source findings

### firecrawl — installed CLI binary, real reachability confirmed

`command -v firecrawl` resolves to
`/Users/rmanaloto/.local/share/mise/installs/npm-firecrawl-cli/1.23.3/bin/firecrawl`
(matches premise L1). `firecrawl --status` reports **authenticated via
`FIRECRAWL_API_KEY`** — an env-var credential, not a browser/MCP session, so
it survives outside this Claude session's tool bindings.

Control-armed positive probe — `firecrawl search`:

```
$ firecrawl search "graphify knowledge graph AST extraction" --limit 1
GitHub - Graphify-Labs/graphify: Turn any codebase, with ...
  URL: https://github.com/Graphify-Labs/graphify
  ...

$ firecrawl search "zzzqxnotarealsearchtermxk4829571kb" --limit 1
Award | SBIR
  URL: https://www.sbir.gov/awards/6800
  ...
```

The two queries returned **different, query-relevant content** — the real
query surfaced the graphify repository, the nonsense query surfaced an
unrelated grant listing rather than an identical fixed response. This is a
weaker discrimination than a clean null (firecrawl's search does not appear to
have a "no results" floor the way grep.app's MCP tool did in #576 — it always
returns *something* for a web query), but it is genuinely discriminating: the
result content tracks the query rather than being a canned string, which rules
out the response being a cached/static stub.

**Reachable: yes, via the installed CLI, no Claude session required.**

### context7 (`ctx7`) — installed CLI binary, cleanly discriminating

`command -v ctx7` resolves to
`/Users/rmanaloto/.local/share/mise/installs/npm-ctx7/0.5.8/bin/ctx7` (matches
premise L2). `ctx7 whoami` reports a logged-in session
(`ray.manaloto@gmail.com`) — this is a stored CLI login, independent of any
Claude session or MCP registration.

Control-armed positive probe — `ctx7 library`:

```
$ ctx7 library graphify
1. Title: Graphify
   Context7-compatible library ID: /graphify-labs/graphify
   ...

$ ctx7 library zzznotarealexistinglibraryname123456
✖ No libraries found for "zzznotarealexistinglibraryname123456". Try a different search term.
```

Clean discrimination: a real library name returns three ranked matches with
IDs and metadata; a bogus name returns an explicit "no libraries found"
message. Same shape as #576's grep.app MCP finding.

**Reachable: yes, via the installed CLI, no Claude session required.**

### exa — no CLI on PATH; reachable via a direct, discriminating HTTP call

Premise L3 (`command -v exa` returns nothing) is confirmed — there is no
`exa` binary. Unlike last30days below, though, exa has a public HTTP API and
an `EXA_API_KEY` was present in this session's environment (checked
presence-only via `[[ -v EXA_API_KEY ]]`, never printed, per
`docs/secrets.md`).

Control-armed probe against `https://api.exa.ai/search`:

Both calls were `POST https://api.exa.ai/search` with
`Content-Type: application/json` and body
`{"query":"knowledge graph extraction with graphify","numResults":1}`. The
only difference was the request's auth header value:

| Auth header value | HTTP status | Body |
|---|---|---|
| the session's real `EXA_API_KEY` (env var, never printed here per `docs/secrets.md`) | 200 | `{"requestId":"...","results":[{"id":"https://github.com/Graphify-Labs/graphify", ...}], ...}` |
| an invalid placeholder string, deliberately not reproduced verbatim so this report itself does not read as an embedded-credential pattern | 401 | `{"requestId":"...","error":"Invalid API key","tag":"INVALID_API_KEY"}` |

The real key returns HTTP 200 with real search results; a bogus key returns
HTTP 401 with an explicit `INVALID_API_KEY` error. This is a clean
authentication-level control arm, and it is a **different transport class**
from firecrawl/context7's CLI-subprocess shape: a standalone `breadth` CLI
reaching exa has to be a direct HTTP client (matching #568's `httpx2`
decision), not a subprocess wrapper. Whether `EXA_API_KEY` is available to the
*future standalone CLI's own end user* (as opposed to this Claude session's
environment) is unverified by this spike — that is an adapter-ticket concern,
not a reachability one; the finding here is that the endpoint itself is
reachable and does discriminate on a real key.

**Reachable: yes, via bare HTTP, no CLI and no Claude session required.**

### last30days — no installed CLI, no PyPI package, but reachable as a vendored script subprocess

Premise L4 (no `last30days` PATH binary) is confirmed as literally true but
**incomplete as a reachability verdict**, which is itself the finding: the
plugin ships a real, executable, argparse-based Python CLI at
`skills/last30days/scripts/last30days.py` inside its plugin-marketplace clone
(`~/.claude/plugins/marketplaces/last30days-skill/`), runnable via
`uv run <path-to-script> "<topic>" --search <sources>` — no MCP binding, no
Claude tool call, and no active Claude session required for the script to
execute.

Control-armed positive probe — real vs. nonsense topic, Hacker News only
(free/keyless source):

```
$ uv run .../skills/last30days/scripts/last30days.py "graphify knowledge graph" --search reddit,hackernews --quick
...
- Hacker News: 1 item
- Reddit: 0 items (auth-failed: ... HTTP 402: Payment Required ...)

$ uv run .../skills/last30days/scripts/last30days.py "zzzqxnotarealtopicxk9384756kb" --search hackernews --quick
[HN] Found 0 stories
✓ Research complete (1.7s) - HN: 0 stories
```

Real topic → 1 Hacker News story; nonsense topic → 0 stories. This
discriminates cleanly. Reddit's failure (HTTP 402 on its paid backfill path)
is a real per-source auth/billing condition surfaced by the tool's own
`doctor` diagnostics, not a broken probe — the run itself completed and
returned data for the source that needed no paid key.

**But this reachability comes with a packaging caveat that the other three
sources do not have**, and it is the report's central finding for this
source: the script only exists on this machine because Claude Code's plugin
manager cloned `last30days-skill` into
`~/.claude/plugins/marketplaces/last30days-skill/`. Checked and confirmed:

```
$ curl -o /dev/null -w "http=%{http_code}\n" https://pypi.org/pypi/last30days-skill/json
http=404
$ curl -o /dev/null -w "http=%{http_code}\n" https://pypi.org/pypi/graphifyy/json   # control: known-good package
http=200
```

`last30days-skill` is **not published on PyPI** (control-armed against a known
package that does resolve), so a future standalone `breadth` CLI cannot
`uv add` or `pip install` it as an ordinary dependency. The only way to depend
on it today is to either (a) require the user to already have the
`last30days-skill` Claude Code plugin installed and locate its clone path at
runtime — fragile, and orthogonal to "does not run inside a Claude session"
— or (b) vendor/fork the script, which the plugin's own `README`/`SKILL.md`
license terms would need to be checked before doing (out of scope for this
spike; not attempted).

**Reachable: yes, as a subprocess, no Claude session required — but with no
installable package to depend on, unlike the other three sources.**

## Closing verdict, restated

1. **Source count: 4**, confirmed from the plugin manifest.
2. **No single shared shape.** Three reachability classes: installed CLI
   binary (firecrawl, context7), direct HTTP client (exa), and vendored-script
   subprocess with no installable package (last30days).
3. **This forces `breadth` to split into more than one adapter path**, same
   as #576's finding for codesearch: at minimum a CLI-subprocess adapter
   (firecrawl + context7 can likely share this shape, pending a future ticket
   verifying their output/record shapes actually converge), a direct-HTTP
   adapter (exa, reusing the `httpx2` pattern #576 already established), and a
   third, higher-risk path for last30days that must resolve the packaging gap
   before a `breadth` verb can depend on it as an ordinary dependency.
4. **last30days is the one genuinely new risk this spike surfaces beyond
   #576's shape**: it is not merely "a different transport" like exa, it is
   "reachable today only because of an artifact (a plugin clone) that a
   standalone package has no principled way to require." That should be
   flagged to whoever writes the `breadth` ticket(s) as an open packaging
   question, not silently assumed solvable.

## Explicitly out of scope

This spike did not add a `breadth` CLI verb, did not modify
`python/src/kb_setup/research/cli.py`, did not touch
`schemas/research-record.schema.json`, and did not run code generation. It did
not evaluate last30days-skill's license terms for vendoring, and did not
verify whether firecrawl's and context7's *record* shapes (not just their
transport) actually converge — that record-shape question is left to the
adapter-build ticket(s), per this report's closing verdict.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — used only as a stable, known-real search subject to test firecrawl/context7/exa discrimination; its content was not otherwise analyzed.
- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — read its `pyproject.toml`, `SKILL.md`, and ran its bundled `last30days.py` script from a local plugin clone to determine headless reachability and packaging status.
