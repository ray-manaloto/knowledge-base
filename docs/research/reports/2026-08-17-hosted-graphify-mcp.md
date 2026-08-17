# The hosted graphify MCP — what it is, what it holds, what it is not

**Written 2026-08-17.** Reference doc, not a narrative: this exists so nobody
re-derives what the hosted MCP does or re-runs the probes below.

Every claim is either cited to a source or a live probe run on 2026-08-17, or is
labelled **UNVERIFIED** / listed under [§7 Unknowns](#7-what-is-still-unknown).
All probes were **read-only**. Nothing was installed, registered, or written
through the MCP.

---

## 1. What is registered, and where

`.mcp.json` at the repo root, **tracked and committed**:

```json
{ "mcpServers": { "graphify": { "type": "http", "url": "https://api.graphify.com/mcp" } } }
```

| | |
|---|---|
| Landed in | `98b116fd` — *"feat(graphify): resync every pin to 0.9.44 and gate the class (#225, #315) (#325)"* — i.e. **PR #325** |
| Verified by | `git log --follow -- .mcp.json` (single commit touching it) |
| Registration style | **native**, not `mcp2cli` — see [§5](#5-relation-to-this-repos-invariants) |

### The two URLs are NOT established to be the same thing

Ray's 2026-08-16 directive cited **`https://app.graphify.com/ray-manaloto/mcp`**.
The repo registers **`https://api.graphify.com/mcp`**. These are different hosts
and different path shapes.

Probed, with a control arm:

| URL | HTTP | Note |
|---|---|---|
| `https://api.graphify.com/mcp` | **401** | exists, requires auth |
| `https://api.graphify.com/<bogus-path>` | **404** | **control** — the probe discriminates |
| `https://app.graphify.com/ray-manaloto/mcp` | **307** → `/login?returnTo=%2Fray-manaloto%2Fmcp` | |
| `https://app.graphify.com/` | **307** → `/login` | |
| `https://app.graphify.com/<bogus-path>` | **307** → `/login?returnTo=%2F<bogus-path>` | **control** |

**Conclusion: cannot be established, and the redirect is not evidence.** The
bogus `app.graphify.com` path returns the *identical* 307-to-login with
`returnTo` merely echoing whatever was requested. So the 307 on
`/ray-manaloto/mcp` carries **no information about whether that path exists** —
it is a blanket unauthenticated redirect. (This is
`probes-need-a-control-arm.md` rule 4 — *"a redirect/timeout/parse-error is not
a 'no'"* — and rule 1, armed.)

What *is* established: `api.graphify.com/mcp` is a real authenticated endpoint,
and it is the one this repo actually talks to. Whether `app.graphify.com` is the
same service's web UI is **UNVERIFIED**; the corpus quote in [§6](#6-prior-research-already-in-the-corpus)
suggests `app.graphify.com` is the *early-access sign-up surface* for the same
product, but that is inference from marketing copy, not a probe.

---

## 2. What it actually holds — live probe, 2026-08-17

Re-run this session, not inherited.

**`list_workspaces`:**

```json
{"handle":"ray-manaloto","name":"ray-manaloto","planLabel":"Pro",
 "role":"owner","active":true,"boundVia":"token_claim"}
```

One workspace. Plan **Pro**. Role **owner**. Bound via **`token_claim`** — i.e.
the workspace is selected by a claim inside the credential, not by config in
this repo.

**`list_repositories`:**

| fullName | repositoryId | defaultBranch | status | queryable | nodeCount |
|---|---|---|---|---|---|
| `ray-manaloto/knowledge-base` | `6ff1824a-bfe8-4bcd-849a-7aa5ebef8569` | `main` | ready | yes | 9,357 |
| `ray-manaloto/dotfiles` | `b47464de-4426-4b67-ba21-29c95e0f573f` | `main` | ready | yes | 7,795 |

**`graph_stats`:**

| | knowledge-base | dotfiles |
|---|---|---|
| tenantId | `629ea3d7-4f32-43b2-9a21-76a1c733ca7b` | same |
| buildId | `6f439474-078d-4f79-aa8b-a8853d437271` | `bececb34-980e-4376-9b21-b4178d4512c7` |
| **commitSha** | **`5308c69c52b33a820d2a5b6ed20cddc59ae26ff1`** | `600494ca1331fa7509c42144c6a69276f9c7bc40` |
| pipelineVersion | `production-v1` | `production-v1` |
| format_version | 5 | 5 |
| n_nodes / n_edges / n_communities | 9,357 / 17,778 / 661 | 7,795 / 14,027 / 540 |
| model | `minishlab/potion-base-8M` | `minishlab/potion-base-8M` |

---

## 3. Tool surface — 23 tools

Schemas loaded and read on 2026-08-17; descriptions below are paraphrased from
each tool's own `description` field, not invented.

### Discovery / workspace

| Tool | Purpose |
|---|---|
| `list_workspaces` | Which workspaces this agent can target, which is active, how it was selected |
| `set_workspace` | Point the session at a workspace by handle; `make_default: true` persists it **across sessions** |
| `list_repositories` | Repos in the workspace, their ids, and whether each index is queryable yet |
| `graph_stats` | Non-sensitive summary statistics for the promoted graph |

### Retrieval / search

| Tool | Purpose |
|---|---|
| `query_graph` | Semantic retrieval **with materialized definition bodies**. `budget` (500–50,000 tokens), `k`, `skeleton: true` for signatures only |
| `graphify_find_seeds` | Scored seed nodes **without** expansion — cheap locate |
| `graphify_find` | Symbols by **label substring** (a fragment, not a question) |
| `graphify_rank_files` | Rank source files for a natural-language question |
| `graphify_expand` | Materialize node handles (`id` fields from other results) into definition bodies |
| `graphify_node` | A symbol's body plus its direct neighborhood |

### Navigation / structure

| Tool | Purpose |
|---|---|
| `graphify_callers` / `graphify_callees` | Exact directed call edges. `strict_calls` defaults **true** here (resolved edges only) |
| `graphify_references` | Non-call references touching a symbol |
| `graphify_trace` | Directed call paths from `src` to `tgt`, up to `k_paths` (1–10) |
| `shortest_path` | Confidence-weighted path between two symbols |
| `graphify_file_neighbors` | Per-file blast-radius map |
| `graphify_imports_exports` | Import/export dependency edges for a file |
| `graphify_tests_for` | Tests linked to a symbol **or** a file (accepts both) |

### Impact

| Tool | Purpose |
|---|---|
| `graphify_impact` | Broad change-impact fanout from a target symbol |
| `impact_and_risk` | Fanout **+ linked-test coverage** → ranked hotspot files. Its own description warns it is *"a STATIC, graph-derived signal — it does not run or verify anything, and is NOT a verification or review verdict"* |

### Memory — **these WRITE** ⚠️

| Tool | Purpose |
|---|---|
| `remember` | Store one durable fact/decision/gotcha. **"It is stored for the workspace, not just this session."** |
| `recall` | Retrieve consolidated entity-facts + verbatim notes, ranked for a query |
| `ingest_turns` | Store a **whole conversation** (ordered turns, ≤64 per call, `start_index` for longer). Also workspace-scoped |

**`strict_calls` default differs by tool** — `true` for `callers`/`callees`/`trace`,
`false` for `graphify_node`. Worth knowing before comparing results across them.

---

## 4. The three facts that decide how to use it

### 4a. It indexes Ray's REPOS, not the ingested corpus

| | hosted | local |
|---|---|---|
| knowledge-base | **9,357 nodes** | ~140,295 (`CLAUDE.md:47`) |
| what is in it | this repo's own code | this repo **plus 71 ingested sources** |
| prose-only view | — | 2,553 nodes (`graph-prose.json`) |

The hosted graph is roughly **6.7%** the size of the local aggregate, and the
difference is the corpus. So:

- **hosted answers** *"how does my code work?"*
- **local `kb-query --prose` answers** *"what do the sources say?"*

They are complementary, not substitutes. The hosted MCP **cannot** answer a
corpus question, and no amount of querying it will surface an ingested source.

### 4b. It tracks `main` — and is exactly `origin/main`, not merely "behind"

Measured 2026-08-17:

```
hosted commitSha         5308c69c52b33a820d2a5b6ed20cddc59ae26ff1
git rev-parse origin/main 5308c69c52b33a820d2a5b6ed20cddc59ae26ff1   ← identical
git rev-parse HEAD        df4001df87fce22743feed7b5e85ef27546d26de
git rev-list --count 5308c69c..HEAD → 8
```

`defaultBranch` is `main` for both repos. **The precise statement is that the
index was current with `origin/main` and 8 commits behind the unmerged feature
branch** — not that it lags `main`. It cannot answer questions about work in
flight, but it is not stale with respect to what has landed.

Whether it refreshes automatically on push is **UNKNOWN** ([§7](#7-what-is-still-unknown)).

### 4c. It uses an embedding model — a different retrieval design

`graph_stats` reports `model: minishlab/potion-base-8M` for both repos.

`CLAUDE.md:7` describes the local approach as:

> *"local, deterministic AST parsing; every edge tagged EXTRACTED/INFERRED; **no vector store**"*

**These are different retrieval designs, not remote and local copies of one
thing.** Consequences that matter in practice:

- Hosted results are **not reproducible** the way a deterministic BFS is; two
  runs need not rank identically.
- A hosted answer is **not** evidence about the local graph, and vice versa.
- The local repo's "no vector store" property is a *local* property. Citing it
  while using the hosted MCP would be carrying a fact past its condition
  (`verify-before-advancing.md` § *Carry a fact's CONDITION*).

---

## 5. Relation to this repo's invariants

### Invariant 4 — "One MCP server per graph"

`CLAUDE.md:25-27`:

> *"**One MCP server per graph.** The server binds to an ABSOLUTE `graph.json`
> path (`mise run kb-serve`), so multiple graphify projects on one host never
> collide."*

**No conflict.** Read the invariant's stated *rationale*, not just its title:
it exists so that two local graphify projects on one host do not collide over
`graph.json`. The hosted MCP binds no local path at all — it is a remote HTTP
service over a server-side index. It cannot collide with `kb-serve` because they
share no resource. `kb-serve` remains the only server bound to this repo's
`graphify-out/graph.json`.

### `research-doc-sources.md` — `mcp2cli` preferred over native registration

That rule prefers `mcp2cli` because native registration *"injects every tool's
JSON schema into Claude's system prompt for every conversation, forever."*
`.mcp.json` here **is** a native registration, so it pays that tax — 23 tools.

**Not a violation.** The rule states plainly that native registration *"is NOT
forbidden"* and is *"a documented **preference**, not a gate"*, with the
judgement call being *"query it rarely → `mcp2cli` wins on cost; … you'll use it
often → register it."* `do-not.md` § *On MCP* repeats this. Registering it was a
deliberate, allowed choice.

**But the tax is real and worth re-testing.** In this session the graphify MCP
tools were **deferred** (schema-on-demand via `ToolSearch`), which materially
reduces that cost. Whether that deferral is guaranteed or incidental is
**UNVERIFIED**.

### Invariant 1 — project-scoped, never global

`.mcp.json` is project-scoped and committed to this repo. It writes nothing to
`~/.claude`. **No conflict** with invariant 1 or `do-not.md` #11.

### The one to actually watch: `remember` / `ingest_turns`

These are **write** tools whose own descriptions say the data is *"stored for
the workspace, not just this session"*, and `ingest_turns` is designed to absorb
**whole conversation transcripts**. Nothing in this repo's invariants currently
governs them, because they were not part of the corpus design. See
[§7](#7-what-is-still-unknown) — this is the highest-value unknown here.

---

## 6. Prior research already in the corpus

`sources/extractions/graphify-2026-08-06-docs.json`, node 507
(`.nodes[507].label` = `graphify Enterprise`), `rationale` verbatim:

> *"graphify Enterprise is the always-on hosted layer at graphify.com applying
> the same graph approach to meetings, files, docs and code, updating
> continuously in the background rather than only on demand. Early access is
> open at app.graphify.com."*

Two things to take from it, and one not to:

- ✅ It names **`app.graphify.com`** as the early-access surface — consistent
  with (but not proof of) the login redirect in [§1](#1-what-is-registered-and-where).
- ✅ *"updating continuously in the background rather than only on demand"* is
  the vendor's claim about refresh. It is **marketing copy, not a probe**, and
  is the closest thing available to an answer for the refresh question in §7.
- ❌ Do **not** read *"meetings, files, docs and code"* as a description of what
  Ray's workspace holds. The live probe shows two **repositories** and nothing
  else.

---

## 7. What is still UNKNOWN

Named rather than guessed. An unknown named is worth more than a guess.

### Indexing and refresh

- **How is indexing triggered?** Push webhook, poll, or manual? The corpus quote
  claims "continuously in the background"; the observed `commitSha` was exactly
  `origin/main`, which is *consistent* with that but also with a push hook or a
  recent manual build. **Not distinguishable from one observation.**
- **Can it be pointed at a branch?** `defaultBranch: main` is reported per repo,
  and no tool in the surface accepts a ref/branch argument. Whether branch
  indexing exists at another layer (web UI, settings) is unknown.
- **What is `buildId`, and is build history queryable?** Two distinct ids
  observed; no tool exposes a build list.
- **What does `status: ready` exclude?** Presumably `pending`/`failed` exist;
  unobserved.
- **How were these two repos onboarded?** Not recorded anywhere in this repo.

### Auth, cost, residency

- **Token provenance.** `boundVia: "token_claim"` means the workspace comes from
  a claim in the credential — but *where that credential lives* is unknown.
  `.mcp.json` carries no token and no `headers` block, so it is supplied by the
  harness or an ambient store. **Not established, and worth knowing before
  assuming another machine can reach this.**
- **Cost model.** Plan is `Pro`. Whether queries are metered, and against what,
  is unknown. No usage figures are exposed by any tool.
- **Data residency / retention.** `tenantId` observed; jurisdiction, retention
  and deletion policy unknown.
- **Rate limits.** Unobserved. No 429 was encountered.

### The memory tools — the highest-value unknown

- **Does `remember` / `ingest_turns` write data Ray would not want uploaded?**
  Their descriptions say workspace-scoped and durable, and `ingest_turns` is
  explicitly for replaying chat logs. This repo has its own committed
  work-memory (`graphify-out/memory/`, via `mise run kb-remember`) which is
  local and reviewable. **Whether the hosted memory should ever be used, and
  what policy governs it, has never been decided.** Nothing has been written
  through it — verified: this document's research was read-only.
- **Is there any deletion path** for something written by mistake? No tool in
  the surface deletes.
- **`set_workspace(make_default: true)` persists across sessions** — i.e. a
  cross-session side effect from a tool call. Where that default is stored is
  unknown.

### Relationship questions

- Is `app.graphify.com/ray-manaloto/mcp` the same service as
  `api.graphify.com/mcp`? **See [§1](#1-what-is-registered-and-where) — not
  established.**
- Does the hosted pipeline (`production-v1`, `format_version: 5`) correspond to
  any pinned local graphify version? The local pin is `graphifyy[all]==0.9.45`;
  no mapping is exposed.
- Is the schema-injection tax actually paid here, or does tool deferral avoid
  it? **UNVERIFIED** ([§5](#5-relation-to-this-repos-invariants)).

---

## 8. How to use it — the short version

1. **Ask it about your own repos' code.** `query_graph`, `graphify_rank_files`,
   `graphify_callers`, `impact_and_risk`. It is good at *"what calls this"* and
   *"what breaks if I change this"*.
2. **Do not ask it corpus questions.** Use `mise run kb-query -- "…" --prose --idf`.
3. **Do not treat its answers as evidence about the local graph** — different
   index, different retrieval design, different commit.
4. **Check `graph_stats().commitSha` before trusting an answer about recent
   work.** It indexes `main`; a feature branch is invisible to it.
5. **Treat `remember` / `ingest_turns` as out of scope** until someone decides
   the policy. This repo already has a local, reviewable, committed work-memory.

---

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) —
  the repo this document lives in; `.mcp.json`, `CLAUDE.md`, `do-not.md`,
  `research-doc-sources.md`, `sources/extractions/graphify-2026-08-06-docs.json`
  read, and its hosted index probed.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — the second
  repository in the hosted workspace; its hosted `graph_stats` probed. No source
  was read.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the tool
  whose hosted layer this document describes; the pinned local source is the
  contrast case in [§4c](#4c-it-uses-an-embedding-model--a-different-retrieval-design).
