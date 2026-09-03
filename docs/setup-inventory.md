# Setup inventory — what is CONFIGURED vs what was OBSERVED RUNNING

**Every row names the command that proved it.** A row asserting configuration
without an observation is the defect this document exists to kill (#672, DoD 1).

Ray, 2026-09-02, verbatim: *"we are going in circles and not accomplishing
anything because you dont understand how to setup claude/graphify/codex/etc"*.
The diagnosis in #672 is that this repo's agent **reasons from documentation
instead of from the running installation**. So this file records only what a
command printed, and says plainly where it did not ask.

**Observed 2026-09-03**, session `kb-20260902.004`, on this machine
(darwin 25.6.0, arm64). Every figure below was re-derived in that session —
none is quoted from a prior report, a handoff, or `GRAPH_REPORT.md`.

> **This file goes stale by design.** It is a snapshot of a running
> installation, not a spec. Treat any row older than the tool it describes as
> unverified until re-run. The `## How to re-observe` section at the bottom is
> the whole file as one script.

---

## 1. The graph — which one each client actually reaches

🔴 **This is #668, and it is the ordering constraint for all of Phase U.**
Deep-extracting into a graph no client reads spends real tokens for zero
reachable benefit.

| what | configured | observed | proved by |
|---|---|---|---|
| Claude → graphify | `.mcp.json` → `https://api.graphify.com/mcp` (http) | hosted, kept; **`kb` added** for the local graph | `uv run python -c` reading `.mcp.json` |
| codex → graphify | global `~/.codex/config.toml` | hosted, Auth `OAuth`; project adds **`kb`** | `codex mcp list` |
| hosted index size | — | **13,126 nodes / 23,160 edges / 1,484 communities**, at commit `295955dbeb84`; **13,152 nodes** when re-read 2026-09-03 — it re-indexes, so this figure moves | `mcp__graphify__graph_stats`, then `mcp__graphify__list_repositories` |
| local aggregate graph | `graphify-out/graph.json` | **359,026 nodes / 806,869 edges / 553,479,428 bytes** | `json.load` on the file |
| local prose graph | `graphify-out/graph-prose.json` | **11,330 nodes / 16,864,486 bytes** | same |
| `kb-serve` (local stdio MCP) | exists, documented in `CLAUDE.md` as *the* way consumers reach this graph | **was registered in NEITHER client** at the start of the round | `grep -l 'kb-serve' .mcp.json .codex/config.toml` → no match |

### How it was settled — and the swap I first shipped was WRONG

I read hosted-vs-local as two routes to one graph and swapped both clients to
local. Ray corrected it: *"the app.graphify.com mcp provides more features we
dont yet support / so we should keep that / and our code for the rest"*. A codex
lane's 319-line capability comparison confirmed him — and found the reverse gap
too. **Neither is a subset of the other**, counted from
`sources/graphify/graphify/serve.py:1614-1744`:

| | hosted `graphify` | local `kb` |
|---|---|---|
| tools | **24** — re-counted authenticated 2026-09-03 (U-R0) | **10** |
| corpus | this repo's own files, **13,152 nodes**, one of 15 indexed repositories in the workspace | the **359,146**-node aggregate: every ingested source |
| only there | seed search, file ranking, callers/callees/references, traces, file-neighbors, imports/exports, tests-for, `impact_and_risk`, `graphify_render_subgraph`, `remember`/`recall`/`memories_about`, workspace + repository discovery, Formal Verification | `list_prs`, `get_pr_impact`, `triage_prs` |

**THREE** tool names exist on both — `graph_stats`, `query_graph`,
`shortest_path` — which is why they carry distinct prefixes. This line said
*seven* until 2026-09-03; where that figure came from is not established, so it
is corrected rather than explained, and it was equally wrong against the
2026-08-17 inventory, whose overlap with the local ten is the same three.
Measured with `comm` over the two sorted name lists.

🔴 **THE NAME IS LOAD-BEARING — SHARING ONE BREAKS CODEX OUTRIGHT.** Ray ran
`codex mcp add graphify --url …`, which writes a **global** entry (its own output
says "Added global MCP server"). With this repo's project entry using the same
key as a stdio command, codex refused to start at all:

```text
Error: failed to load bootstrap configuration
Caused by: url is not supported for stdio   in `mcp_servers.graphify`
```

Not a soft ambiguity about which server answers — a total outage of the CLI,
reproduced and fixed 2026-09-03 by renaming ours to `kb`.

**U-R0 — DONE 2026-09-03. The count is now measured, not inherited: 24.**

Why it took a second round to get: the August lane could not authenticate (HTTP
401, OAuth challenge); its own session's `graph_stats` was refused by approval
policy; and its second attempt was **blocked by that round's own `codex_lane`
guard**, which denies raw `codex exec` and routes to `mise run kb-codex`, whose
project config was already the local server. Ray ran `codex mcp login graphify`
on 2026-09-03, which is what made asking possible.

| | count | delta |
|---|---|---|
| 2026-08-17 (last complete inventory) | 23 | — |
| 2026-09-03 (authenticated, this session) | **24** | +`graphify_render_subgraph`, +`memories_about`, −`ingest_turns` |

`memories_about` is the row worth reading twice: the August report recorded it as
*proposed but unverified* and found it absent from every bounded evidence set it
could reach. It is live. That is an absence-of-evidence being retired by
evidence, which is the whole reason U-R0 was a ticket rather than a shrug.

**Control arm**, because a tool-registry count is a probe like any other: the
same session listing reports `kb` at exactly **10**, matching the count measured
independently from the pinned source (`python/src/kb_setup/mcp_serve.py:4` —
"10 tools + 6 resources unconditionally"). A listing that agrees with an
independent count on one server is not silently truncating the other.

**Liveness, not merely a schema.** `mcp__graphify__list_workspaces` answered —
workspace `ray-manaloto`, plan Pro, role owner, `boundVia: token_claim` — and
`mcp__graphify__list_repositories` returned 15 repositories, of which
`ray-manaloto/knowledge-base` is `status: ready`, `queryable: true`, **13,152
nodes**. The count comes from a server that answered, not from a registration
that merely exists.

**The gap is a BACKLOG, not a border.** Ray: *"one of our goals is to be able to
replicate the functionality the remote one does and its formal verification and
other features"*. The lane framed every hosted-only row as a permanent division
of labour because nothing it read said otherwise — recorded because that is a
defect in the lane's brief, not only in its output.

**The hosted index holds 3.7% of the corpus by node count** — but that is a
statement about SCOPE, not about quality, and it is not an argument against
hosted. Hosted indexes this repo's own files with 24 tools; `kb` holds every
ingested source with 10. Both are now reachable, under distinct names.

⚠️ **Two corrections this document earned on ITSELF, within one session**, kept
rather than smoothed away because both are the shape it exists to prevent:

1. An earlier line called the hosted index "pinned to a commit already one merge
   behind `main`", measured at `295955dbeb84`. It **re-indexes** — a later call
   the same session reported `72fd9b834c2b`. Staleness was never its problem.
2. The node counts in the table above (**359,026** / 806,869) were measured
   BEFORE this round's rebuild. The rebuild finished green and the aggregate is
   now **359,146 nodes / 807,085 edges**. Correctly measured, wrong within the
   hour — `probes-need-a-control-arm.md` rule 6 arriving from a measurement
   rather than an inheritance.

### `kb-build` was broken, and only running it showed that

Wiring a client to a stale graph is worse than wiring it to the wrong one,
because it looks right (#668). So the rebuild was run — and it **failed, exit
1**, on a defect nobody knew about:

The `OpenSymphony` extract **succeeded** (11,004 nodes, 34,665 edges written) and
`kb_setup.graphify_health` then failed the whole build on one line Graphify
narrates in the ordinary course:

```text
[graphify] 3 source file(s) deleted or excluded since last run — no matching
nodes or edges in graph, already clean.
```

Not a network transient — **zero** network signatures in 92 lines of log. Same
class as #438: a stderr-is-a-refusal rule breaking on the tool's own narration.

Fixed narrowly, and the narrowness was read out of Graphify's own source
(`build.py:1969-1997`) rather than judged by wording: that code branches on
`(prune_set or prune_abs) and not _matched_prune_entries`, and the **suspicious**
branch prints a different `WARNING: … matched no nodes or edges … (#2446)` line,
which is still refused. Three arms, 3/3 dying, control held.

⚠️ **One of those arms was an INERT MUTANT first, and the correction is the more
useful finding.** Widening only the pattern's wording SURVIVED — because the
regex ends `\.\Z` and the WARNING line ends `(#2446)`, so no wording change alone
can make it match. What actually refuses the suspicious sibling is the **anchor**,
not the wording, and the test's docstring had credited the wording. Both were
corrected; the arm that kills it now widens *and* unanchors.

### Is the local graph worth wiring? Armed three ways, yes

A dead server is worse than an unregistered one, so this was probed before being
proposed:

| arm | query | result | rc |
|---|---|---|---|
| **gibberish** | `xqzzy vlurbnak thopwis kreegan` | `No matching nodes found.` | 0 |
| **near-miss** | `zzqx not a real concept kb9384756` | 15 nodes — it matched on the real word *concept* | 0 |
| **real** | `hook_guard deny` | 104 nodes, relevant seeds | **3** (truncation guard) |

The probe discriminates, so the graph is healthy. **rc 3 means TRUNCATED, not
failed** — the prefix returned is not evidence of absence.

⚠️ **The first control arm here was invalid and is recorded rather than
quietly replaced**: the "nonsense" string contained the ordinary English words
*concept* and *real*, so it matched real nodes and looked like a probe that
could not discriminate. A control arm built from words that exist is not a
control arm.

---

## 2. codex — the lane, and the hooks that silently do not fire

| what | configured | observed | proved by |
|---|---|---|---|
| version | `sources/codex.manifest` | **0.152.0** (U3 wants 0.152.1) | `codex --version` |
| `.codex/hooks.json` `pre_tool_use` | 3 entries | **3 TRUSTED** | `[hooks.state]` in `~/.codex/config.toml` |
| `.codex/hooks.json` `post_tool_use` | 1 entry, shipped in `cbc66c54` | 🔴 **0 TRUSTED — it does not fire** | same |
| `session_start` / `session_end` | | 2 and 2 trusted | same |

🔴 **Trust is keyed to each hook's HASH, and an untrusted hook is SKIPPED
SILENTLY** — not reported. So a lane can run with no guard stack and no ty
diagnostics while every config file on disk says otherwise. Editing a hook
re-breaks its trust, so this recurs on every change to `.codex/hooks.json`.

**Control arm — the absence is real, not a schema artifact.** Other repos on
this same machine *do* carry trusted `post_tool_use` entries:
`ray-manaloto/dotfiles` and `ray-manaloto/harness-evolution-ledger` both have
one. So the mechanism works and this repo's entry is genuinely untrusted.

The only lever this repo owns is `--dangerously-bypass-hook-trust` on the codex
invocation: trust is granted interactively via `/hooks` and persists in
`~/.codex/config.toml`, a file `do-not.md` #11 forbids us to write.

**This is exactly the U1 case.** The flag was missing from every invocation
until Ray said so, because nothing owns the flags. `mise run kb-codex` plus a
guard denying a raw `codex exec` is the fix.

---

## 3. Type checking and the toolchain

| what | pinned | observed serving | proved by |
|---|---|---|---|
| ty | 0.0.77 | **0.0.77 (371111b45, 2026-09-01)**, from `.venv/bin/ty` | `uv run ty --version`; `command -v ty` |
| graphify | `graphifyy[all]==0.9.53`, fork rev `157a957e89a1` | **0.9.53** | `uv run graphify --version` |
| codex | manifest `rust-v0.152.1`, `mise.toml` `0.152.1` (bumped this round) | 🔴 **0.152.1 via `mise exec`, 0.152.0 via bare `codex`** | `mise exec -- codex --version` vs `codex --version` |
| mise | `mise.toml:40` hard/soft `2026.9.0` | 🔴 **2026.9.1** — self-updated | `mise --version` |
| Claude Code | `currency.toml:1110` expected `2.1.258` | 🔴 **2.1.259** — self-updated | `claude --version` |

🔴 **PATH SKEW IS LIVE, and it is this document's thesis in one row.** After
`mise install "npm:@openai/codex@0.152.1"`, `mise which codex` resolves
`…/installs/npm-openai-codex/0.152.1/bin/codex` while `command -v codex` resolves
`…/0.152.0/bin/codex`. This shell's PATH holds an **install directory**, not a
shim, so it is frozen at whatever was current when the session started. Every
config file on disk says 0.152.1; the binary a bare command reaches is 0.152.0.

**This is the second measured argument for `mise run kb-codex` (#672 U1)**, and
it is independent of the flags one: a task routed through mise always gets the
pinned version. Ask `mise exec -- <tool> --version`, never a bare one.

Related and out of scope: the codex install tree still holds `0.144` through
`0.151` — `mise prune` has not been run.

**ty is correct and has been all along.** The three sessions that reported its
LSP dead were wrong: the server starts **on demand** (#666). The live registrant
is `astral@astral-sh`, declaring ty **inline in its `plugin.json`** — not a
`.claude/.lsp.json`, which is not a location Claude Code reads at all.

**Five stale version sites**, all carried, none fixed by this round:
`mise.toml:40`, `currency.toml:666`, `sources/mise.manifest` (mise);
`currency.toml:1110`, `sources/claude-code.manifest` (Claude Code).
⚠️ Those manifests want the **tag object** SHA, not the commit (#395).

---

## 4. Plugins

| what | configured | observed | proved by |
|---|---|---|---|
| declared `true` in `.claude/settings.json` | — | **21** | `jq`-equivalent over `enabledPlugins` |
| effective after `settings.local.json` overrides | — | **17** | merge of both files |

`CLAUDE.md` § *Cross-vendor orchestration* says **19** declared. **That is stale
— it is 21.** That paragraph carries its own warning that the count has drifted
four times by being quoted instead of measured; this is the fifth. Fix by
re-deriving, never by quoting this table either.

⚠️ `.claude/settings.local.json` is **untracked**, so the 4 overrides exist only
on this machine. The 17 is not reproducible from a fresh clone.

---

## 5. What this file has NOT observed

Named explicitly, because an inventory that hides its gaps is the thing it was
built to replace.

- **Whether `codex review` or `codex exec review` is the right cold lane.** Both
  subcommands exist (#672 U2). Neither has been run here.
- **What `fable-advisor` has that `kb-advisor`/`kb-codex-advisor` lack.** U6
  requires the diff in hand; it has not been taken.
- **Whether the guard stack actually fires inside a CODEX lane.** Section 2 reads
  the trust table, and the new `codex_lane` deny was armed live in a **Claude**
  session (`codex exec …` → denied with its remedy; `codex --version` → allowed
  and ran). Neither observes a denial happening *inside* codex, which is the
  claim `--dangerously-bypass-hook-trust` is supposed to make true.
- **`sources/codex` extraction.** `build = skip` since 2026-08-20 (#417), so the
  corpus cannot answer questions about a tool this repo runs.

---

## How to re-observe

```bash
codex --version
codex mcp list                      # Auth column; graphify's url
claude --version
mise --version
uv run ty --version && command -v ty
uv run graphify --version
mise run kb-query -- "hook_guard deny" --prose    # rc 3 = truncated, not failed
mise run kb-query -- "xqzzy vlurbnak thopwis kreegan" --prose   # the control arm
```

**Re-counting the hosted tool surface (U-R0's own probe).** There is no CLI for
it: the count comes from the client's own registry after a `tools/list`
handshake, so ask the client, not the network. In a Claude session, list the
`mcp__graphify__*` names and the `mcp__kb__*` names, sort each, and `comm` them.
Then run the two arms, or the number is an opinion:

- **control arm** — `mcp__kb__*` must come to exactly **10**, the count
  independently fixed by `python/src/kb_setup/mcp_serve.py:4`. If it does not,
  the listing is truncating and the hosted number is worthless too.
- **liveness arm** — call `mcp__graphify__list_workspaces`. A registration that
  exists is not a server that answers, and hosted needs
  `codex mcp login graphify` (codex is the one client that does not sign in on
  first use).

Hook trust, graph sizes and plugin counts are read with short `uv run python -c`
snippets over `~/.codex/config.toml`, `graphify-out/*.json` and
`.claude/settings*.json`. **Never `python3` directly** — a bare interpreter
resolves off `$PATH` and this repo ran its gates on the wrong Python for two
weeks that way.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under inventory; issues #417, #666, #668, #672 read.
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — the pinned fork supplying the installed `graphify` 0.9.53.
