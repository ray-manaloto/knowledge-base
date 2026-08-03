# Research: distributing a large pre-built knowledge graph to third-party consumers

**Status: COMPLETE** (written incrementally as evidence landed)
**Date:** 2026-08-02

## TL;DR

1. **The question's premise is inflated by 41%.** 164.4 MB of the 400.5 MB
   `graph.json` is a `knowledge-base::` namespace prefix repeated up to **26
   times** per node id, accumulated by `graphify merge-graphs` re-prefixing the
   accumulator once per merged source. Confirmed unfixed in graphify **0.9.32**
   (latest on PyPI). Minify + de-duplicate → **193.7 MB**.
2. **`gzip -6` takes `graph.json` to 11.5 MiB (33x) in 1.6 s.** There is no
   distribution problem at that size. The prose graph is **437 KiB** gzipped.
   Calibration: **`tldr.zip` — the entire tldr-pages corpus — is 20.1 MB.** Our
   whole aggregate graph compressed is half of that.
3. **The expensive part of the corpus is the tiny part.** 2,817 prose nodes cost
   real Claude tokens and are irreplaceable; 137,863 AST nodes are free and fully
   re-derivable from 33 pinned manifests.
4. **Recommend: T0 prose (437 KiB) ships in the package; T1 aggregate ships as a
   gzipped GitHub Release asset fetched on first use; `kb-build` stays the
   reproducibility guarantee, not the install path.** Reject graph-DB push
   (write-only, unbatched, drops `_origin`) and reject a hosted-endpoint default
   (contradicts the product; static-key auth only).
5. **Do the byte fixes first.** The repo has **already** blown graphify's 512 MiB
   cap once because of this bug, and split off `study-graph.json` to survive it.

**Question:** `graphify-out/graph.json` is ~375–384 MB and gitignored. The repo is
becoming a distributable tool (library + SDK + CLI + Claude Code plugin). A third
party who installs it needs a corpus. How should it be distributed?

## Measured baseline (this repo, 2026-08-02)

| Artifact | Bytes | Human |
|---|---:|---|
| `graphify-out/graph.json` | 400,499,125 | 382 MiB |
| `graphify-out/graph-prose.json` | 4,163,770 | 4.0 MiB |
| `graphify-out/study-graph.json` | 134,099,401 | 128 MiB |
| `graphify-out/manifest.json` | 6,166 | 6 KiB |

Prose graph is **96x smaller** than the aggregate graph (400.5 MB / 4.16 MB).
33 `sources/*.manifest` pins.

---

## (d) Graph-DB push — READ THE SOURCE, it is not what the docs imply

Source read: `~/.local/share/mise/installs/pipx-graphifyy/0.9.31/graphifyy/lib/python3.14/site-packages/graphify/exporters/graphdb.py`
(installed 0.9.31 = the pin).

Three findings, all from the installed source, not the issue tracker:

1. **Push is one round-trip per node and one per edge.** `push_to_neo4j` L44-75 and
   `push_to_falkordb` L144-171 both loop `for node_id, data in G.nodes(data=True)`
   issuing a single `session.run(...)` / `graph.query(...)` MERGE each, then the
   same for every edge. **No `UNWIND`, no batching, no transaction chunking.** At
   ~140k nodes plus edges this is hundreds of thousands of serialized network
   round-trips. This is fine for a demo graph and a real problem for a 382 MB one.
2. **Push DROPS every `_`-prefixed property.** Both functions filter
   `if isinstance(v, (str,int,float,bool)) and not k.startswith("_")`. This repo's
   prose/code split is exactly `_origin=ast` (CLAUDE.md). So a pushed DB **cannot
   reconstruct the prose subgraph** — the discriminating attribute is stripped on
   the way in. Any list-valued or dict-valued property is dropped too.
3. **Push is WRITE-ONLY — graphify cannot QUERY a graph DB.**
   **Control arm stated:** grep for `push_to_falkordb` (a term I know exists) →
   3 files, so the probe discriminates. Grep for `GraphDatabase.driver|FalkorDB(`
   → **only** `exporters/graphdb.py` L40/L134, i.e. inside the two push functions.
   Grep for `MATCH (n` read-back → 0. There is no `from_neo4j` / `load_from_*`.
   `graphify query` / `path` / `explain` / `serve` **always** load a local
   `graph.json` (`build_from_json`). So pushing to Neo4j/FalkorDB gives a
   consumer a Cypher database — **not** a working graphify. They would have to
   write their own queries and would lose ranked BFS, `--prose`, `--idf`,
   god-nodes and the MCP surface.

   `cli.py` L2519-2522 says it in graphify's own words: the non-`--push` path
   writes `cypher.txt`, and FalkorDB has "no bulk script import", so the only
   load path is the unbatched `--push`.

**Verdict on (d): graph-DB push is an ANALYTICS/scale-out surface, not a
distribution channel.** It is the wrong tool for "give a stranger a corpus".

## THE HEADLINE MEASUREMENT: graph.json compresses 33x

Measured 2026-08-02 on this machine, `gzip -6`:

| Artifact | raw | gzip -6 | ratio | wall time |
|---|---:|---:|---:|---:|
| `graph.json` | 400,499,125 B (382 MiB) | **12,065,737 B (11.5 MiB)** | **33.2x** | 1.61 s |
| `graph-prose.json` | 4,163,770 B | **447,626 B (437 KiB)** | 9.3x | <1 s |

This is the single most important number in the report and it reframes the whole
question. **11.5 MiB is not a distribution problem.** It fits inside:

- a GitHub **Release asset** (2 GiB limit) — trivially;
- a **PyPI wheel** (100 MiB default per-file project limit) — trivially;
- an **npm** package (Claude Code plugin marketplaces are git-based, so this is
  really "a git blob") — GitHub's hard per-file push limit is 100 MiB, warn at
  50 MiB, so 11.5 MiB is even *committable*, though churn per rebuild argues
  against it;
- **git LFS** — comfortably.

JSON of this shape (highly repetitive keys, repeated path prefixes, repeated
relation strings) is exactly the pathological case for uncompressed storage. The
"375 MB is past git limits" framing is TRUE of the raw file and FALSE of the
artifact you would actually ship.

**Caveat, verified in source:** graphify has **no** compressed-graph read path.
Control arm: `build_from_json` → 10 files (probe works); `gzip|zstd|zlib|sqlite|
parquet|msgpack` across the package → the only hit is `extractors/dm.py`'s zlib,
an unrelated Discord-message decoder. So the consumer must **decompress on
install**; the shipped artifact is `.json.gz`, the on-disk artifact is `.json`.

## graphify hard-caps graph.json at 512 MiB

`graphify/security.py` L32: `_MAX_GRAPH_FILE_BYTES = 512 * 1024 * 1024`,
overridable by `GRAPHIFY_MAX_GRAPH_BYTES`. Enforced by
`check_graph_file_size_cap`, called from `build.py` L1146, `paths.py` L338,
`serve.py` L32, and `cli.py`'s `_enforce_graph_size_cap_or_exit`.

**This repo is at 382 MiB — 75% of the cap.** Any distribution plan built on
"ship the aggregate graph" is planning against a ceiling this corpus will hit,
and hitting it means every consumer must set an env var to use the product.
That is an independent argument for tiering.

## ⚠️ UNPLANNED FINDING — 41% of graph.json is a repeated namespace prefix (a real defect)

While measuring where the bytes are, the byte-attribution came out wrong enough
to be worth chasing. Composition of `graph.json` (measured, minified re-encode):

| Region | Bytes |
|---|---:|
| nodes (140,680) | 93.3 MB — of which `_origin=ast` is **90.7 MB** and prose **2.6 MB** |
| links (329,558) | **264.3 MB** — ~800 B per edge |

An 800-byte *edge* is absurd, so I looked at one. Node ids look like this:

```
knowledge-base::knowledge-base::knowledge-base:: … (×26) … ::cognee::cognee_tests_unit_shared_test_usage_logger_testsanitizevalue
```

Per-key attribution over a 30,000-link random sample: `source` **44%** +
`target` **44%** = **88% of all link bytes are node ids**.

Repetition histogram of the literal `knowledge-base::` prefix in node ids
(all 140,680 nodes): counts range 0 → **26**, with large modes at 12 (28,526
nodes), 14 (22,394), 19 (21,025) and 26 (10,987).

**Redundant bytes if you keep at most one prefix:**

| Where | Redundant |
|---|---:|
| node ids | 27.4 MB |
| link `source`/`target` | 137.0 MB |
| **total** | **164.4 MB — 41% of the 400.5 MB file** |

**The prose graph is CLEAN**: its 2,817 node ids carry 0 or 1 prefix, never
more. So the accumulation lives entirely in the AST/merge path, and each merge
round appears to prepend the namespace again — i.e. this is **monotonic growth
that is a function of how many times you have merged, not of how much you
have ingested.** That is a corpus heading for the 512 MiB cap on churn alone.

**Consequences for this question:**

- "382 MB" overstates the real corpus by ~1.7x. A de-duplicated aggregate graph
  is ~236 MB, i.e. 46% of the cap instead of 75%.
- It also explains the 33x gzip ratio: gzip is mostly deleting this.
- **Fix this before designing any distribution mechanism around the size.** Sizing
  a delivery pipeline against a number that is 41% artifact is how you end up
  paying for LFS/CDN you never needed. This deserves its own GitHub issue.

### Where the bug is: UPSTREAM in graphify, and unconditional

`graphify/build.py` L1449-1467:

```python
def prefix_graph_for_global(G, repo_tag):
    relabel = {n: f"{repo_tag}::{n}" for n in G.nodes}
```

No idempotence guard — it prefixes whatever it is handed, including an
already-prefixed graph. Call sites: `global_graph.py` L117 and **`cli.py` L2116,
which is `graphify merge-graphs`**.

`kb_setup/graph.py` L578 and L606 run `merge-graphs <out> <sub> --out <out>` **in
a loop over sources**, so the accumulator is re-prefixed once per merged source.
33 manifests → the observed max of 26 stacked prefixes. Growth is therefore
**O(sources x edges x len(prefix))** — adding sources is superlinear in bytes.

### The repo has ALREADY hit the 512 MiB cap because of this

`kb_setup/graph.py` L163-169, verbatim:

> Kept out of the aggregate because merging them into it took graph.json 7.6 MiB
> past graphify's 512 MiB cap and failed the build outright: 71.0 MB of
> sub-graphs became >=155 MiB of aggregate growth, since `merge-graphs`
> re-namespaces ids and expands edges on every merge.

That is a **2.2x amplification** already recorded, and it is why
`study-graph.json` exists as a separate 128 MB tier. **Tiering is not a proposal
here — the cap already forced it once.** What is new in this report is the
*quantity*: 164.4 MB / 41% of the current aggregate is redundant prefix bytes.

---

## Corpus anatomy — the fact that decides the answer

| Layer | Nodes | Raw bytes | Cost to (re)produce | Replaceable by a stranger? |
|---|---:|---:|---|---|
| **prose** (`_origin` unset) | 2,817 | 2.6 MB of nodes; whole `graph-prose.json` = 4.16 MB (437 KiB gz) | **real Claude tokens** — host-agent extraction fan-out, the ONE LLM path | **No.** Irreplaceable without paying again. |
| **code AST** (`_origin=ast`) | 137,863 | 90.7 MB of nodes + the bulk of 264.3 MB of links | **free** — deterministic local AST parse | **Yes.** Fully re-derivable from 33 pinned manifests. |
| study tier | — | `study-graph.json` 128 MB | free | yes |

**The expensive part of this corpus is 0.4 MB compressed. The 382 MB is the
cheap part.** Everything downstream follows from that.

Committed inputs, measured: whole tracked repo = **7.3 MB** (`.git` = 24 MB), of
which `sources/extractions/` = **2.5 MB** and `sources/media/` = **1.1 MB**.
The LLM-expensive material is *already* fully committed and clones in seconds.

---

## (c) Rebuild-on-install from pinned sources — the numbers

`kb-build` needs no LLM (deterministic AST + replay of committed chunks), so it
is *reproducible*. Its cost is not compute, it is **network**:

- `_ensure_clone` (`kb_setup/graph.py` L51) runs
  `git clone --quiet --branch <ref> <url>` — **full clones, no `--depth`**.
  Deliberate: `kb-update`'s `git diff <old-sha> <new-sha>` (L849) needs history.
- Measured on-disk `sources/` = **3.6 GB** across 33 clones. Largest:
  `codebase-memory-mcp` 1.6 GB, `cognee` 386 MB, `GitNexus` 269 MB,
  `deer-flow` 176 MB, `codegraph` 169 MB.
- `graphify-out/` after a build = **4.4 GB** total (graph.json 382 MB,
  graph.graphml 350 MB, plus wiki/obsidian/svg views).
- The graphify AST cache is only 16 MB and is gitignored, so a stranger's first
  build is fully cold.

**Viable for a stranger? Only as an opt-in "power user" path.** Asking someone
who ran `claude plugin install` to pull 3.6 GB from 33 third-party repos, and to
tolerate any one of those pins having been force-pushed away, is not an install
experience. It is also fragile in exactly the way `persistence-gate-retry.md`
documents: 33 network round-trips, each a chance to fail environmentally.

**COULD NOT DETERMINE: cold `kb-build` wall-clock.** No timing is recorded
anywhere in the repo, and measuring it honestly means a ~3.6 GB cold clone plus
a full extraction — well past what this research task should spend. What *is*
determined is the input volume above, which is the dominant term.

## Runtime cost of the artifact once delivered (measured)

| | time | peak RSS |
|---|---:|---:|
| `json.load(graph.json)` | 0.9–1.0 s | 1.52 GB |
| `+ networkx.node_link_graph` (140,680 n / 329,558 e) | +1.1 s | **1.70 GB** |

**Load time is a non-issue; memory is not.** Every `kb-query` and every
`kb-serve` process resident-sets ~1.7 GB for the aggregate graph. The prose graph
is ~1/96 the size, so ~tens of MB. For a plugin a stranger runs on a laptop
alongside an IDE, 1.7 GB per query invocation is a real tax and a second
argument for shipping prose-first.

## (b) Hosted/remote endpoint — supported natively, but it makes you an operator

Read from installed `graphify/serve.py` L2028-2090:

- `serve_http()` speaks **MCP Streamable HTTP** (spec 2025-03-26) — "the same
  tools/resources as the stdio transport, so a single shared process can host
  the graph for a whole team".
- Auth is a **static shared key**: `--api-key` / `GRAPHIFY_API_KEY`, checked as
  `Authorization: Bearer <key>` or `X-API-Key: <key>` (`_ApiKeyMiddleware`).
  The docstring says **"OAuth is a deliberate follow-up"** — so there is no
  per-user identity, no revocation, no scoping.
- DNS-rebinding protection is on for a specific bind, **off for a wildcard bind**
  (L1993), with a warning if you bind `0.0.0.0` without a key.
- `stateless` and `json_response` modes exist; needs the `graphifyy[mcp]` extra.
- **This repo already has the seam**: `mise run kb-serve -- --transport http
  --port 8080` (documented in `mise.toml` L297-298).

So (b) is technically free today. What it costs is everything around it: a host,
1.7 GB RSS per process, a shared secret you cannot rotate per user, uptime, and a
corpus that is only as fresh as the last box you rebuilt on. **Do not make a
hosted endpoint the primary install path for a tool whose selling point is
"local, deterministic, no vector store, zero LLM tokens."** It contradicts the
product. It is a fine *optional* team deployment.

## How comparable tools actually do it

Full evidence in the companion report `research-peer-data-distribution.md`
(10 tools, primary sources, live-measured sizes). The four rows that decide this
question:

| Tool | Mechanism | What it teaches us |
|---|---|---|
| **spaCy** | Models are pip **wheels hosted on GitHub Releases** (`explosion/spacy-models`), NOT on PyPI. `en_core_web_sm`=12 MB, `lg`=**382 MB**, `trf`=436 MB. A `compatibility.json` maps library version → model version. | The canonical precedent, and it is *exactly* our size class. PyPI's 100 MiB/file limit is why they use Releases. **Two version axes need a compatibility table** — plan for one. |
| **tldr-pages** | GitHub Releases: `tldr.zip` (all) **20.1 MB** + 39 **per-language zips** (`en`=3.29 MB) + `tldr.sha256sums`. | Genuine tiering by picking a different archive, not a partial fetch. Our whole aggregate corpus gzips to **~10–11.5 MiB — half of `tldr.zip`.** That is the calibration that says this is not a hard problem. |
| **NLTK** | Per-package zips indexed by a live `index.xml` carrying **MD5 *and* SHA-256 per package**. Never auto-downloads; `nltk.download('<pkg>'\|'all')`. | Granular opt-in tiers + per-artifact checksums. Copy the checksum discipline. |
| **Grype** | `latest.json` on plain HTTPS object storage with an explicit `checksum` field; auto-fetched at launch; **refuses to scan with a DB older than 5 days**. | A derived index needs a *staleness policy*, not just a version. Ours should at minimum report corpus age. |

Two more worth knowing: **Trivy** ships its DB as an **OCI artifact** on
`ghcr.io` (ORAS), tag = schema version, rebuilt ~6-hourly — the heaviest-weight
option, and overkill until there is a release cadence. **Hugging Face** does
file-level content-addressing plus a chunk-level CAS (Xet, ~64 KB chunks) with
`allow_patterns` partial fetch — the right model at 100x our scale, wrong at ours.

**And the one that changes the plugin story:**

> **`${CLAUDE_PLUGIN_DATA}` → `~/.claude/plugins/data/{id}/`** — a lazily-created
> per-plugin directory that **persists across plugin updates**. Claude Code
> marketplaces are git-based (`github`/`url`/`git-subdir` sparse clone/`npm`) and
> the docs state **no size limit or guidance**, but they do point bulky *derived*
> data at this directory.

That is the documented mechanism for "ship a small plugin, materialise big data
after install" — precisely the T0/T1 split recommended below, and it means the
fetch-on-first-use design is the *intended* pattern rather than a workaround.

## (a) Package registry / release asset — the mechanically correct channel

Once the artifact is 11.5 MiB gzipped, the constraint disappears. Exact limits,
all primary-sourced in the companion report:

- plain `git push` **hard-blocks files > 100 MiB**, warns > 50 MiB; repo-size
  guidance < 1 GB ideal, < 5 GB strong;
- **GitHub Release asset: 2 GiB per file**, no total-release cap, 1,000
  assets/release;
- Git LFS free tier: **10 GiB storage + 10 GiB bandwidth/month** (Free/Pro);
- **PyPI: 100.0 MiB per file, 10.0 GiB per project** (defaults).

Raw `graph.json` (382 MiB) exceeds git's hard block by ~3.8x — the framing in the
question is correct *for the raw file*. Gzipped it is 11.5 MiB and every channel
above accepts it with room to spare. The shape that matters here:

- **GitHub Release asset** — no realistic size problem, versioned by tag,
  checksummable, CDN-backed, does not enter git history, and a release is
  already what `kb-ship`/`kb-land` produce a commit for.
- **PyPI wheel / sdist** — works, but bakes the corpus into the *code* version.
  Corpus freshness and library version then move together, which is wrong:
  you want to re-ingest weekly without cutting a library release.
- **Committed in the plugin repo** — a Claude Code plugin marketplace is a git
  repo the client clones. 11.5 MiB is under the 100 MiB per-file hard limit, so
  it *works* — but every corpus rebuild adds another ~11.5 MiB to history
  **permanently**, and a KB that re-ingests is a KB that rebuilds constantly.
  Reject: this is the one option whose cost is unbounded over time.

## (e) Tiered / partial corpora — this is the answer, and it is already half-built

Three tiers already exist in this repo, two of them forced by the 512 MiB cap:

| Tier | Artifact | raw | gzip | how a stranger gets it |
|---|---|---:|---:|---|
| **T0 prose** | `graph-prose.json` | 4.16 MB | **437 KiB** | ships with the plugin/package |
| **T1 aggregate** | `graph.json` | 382 MiB (236 MiB after the prefix fix) | 11.5 MiB | release asset, fetched on demand |
| **T2 study** | `study-graph.json` | 128 MiB | **4.86 MiB** | release asset, opt-in |

### Cheap size wins, measured, before any distribution work

Applied to the current `graph.json` (400,499,125 B):

| Transformation | Result | Cumulative saving |
|---|---:|---:|
| minify (drop pretty-print indent) | ~357.6 MB | −11% |
| + collapse the repeated `knowledge-base::` prefix to one | **193.7 MB** | **−52%** |
| + `gzip -6` | **10.13 MB** | **−97.5%** |

`graph.json` is currently written **pretty-printed**, which alone costs ~43 MB.
Two changes nobody has to design a pipeline for take the corpus from 382 MiB
(75% of graphify's cap) to 185 MiB (36% of it).

---

## RECOMMENDATION

**Ship a tiered corpus: prose in the package, aggregate as a fetched-on-demand
gzipped release asset, rebuild-from-source as the documented power-user path.
Do the two byte-level fixes first. Do not build a hosted service, and do not use
graph-DB push as a distribution channel.**

Concretely, in order:

**0. Fix the prefix accumulation before sizing anything.** 164.4 MB / 41% of the
artifact is a bug, not a corpus. Combined with minified output it is a 52%
reduction for no design work. File it upstream against
`graphify.build.prefix_graph_for_global` (make it idempotent — skip nodes already
carrying `repo_tag::`) and, until that lands, normalise in `kb_setup` after the
merge loop. **Everything below gets cheaper if this happens first, and the size
numbers everyone will quote get honest.**

**1. T0 — `graph-prose.json` ships INSIDE the distributable (437 KiB gzipped).**
This is the whole product for most consumers:
- It is the layer that cost real Claude tokens and that a stranger cannot
  reproduce at any price.
- It is the arm `CLAUDE.md` already recommends for document questions
  (`--prose --idf`, recall 1/8 → 3/8 → 5/8).
- It costs tens of MB of RSS instead of 1.70 GB.
- At 437 KiB it can simply be committed to the plugin/package repo. Even a
  hundred rebuilds of history is ~44 MiB.

**2. T1 — the aggregate as a `graph.json.gz` GitHub Release asset, fetched on
first use, not at install.** ~10–11.5 MiB. Version it by release tag, publish a
`SHA256SUMS` alongside (NLTK/tldr-pages both do), and fetch into
**`${CLAUDE_PLUGIN_DATA}`** (`~/.claude/plugins/data/{id}/`) for the plugin lane
or an XDG cache dir for the CLI lane. This is the `nltk.download()` /
`spacy download` / `grype db` shape and it is what Claude Code's own docs point
bulky derived data at.
Never bake it into a wheel: PyPI's 100 MiB/file cap is survivable at 11.5 MiB,
but corpus freshness must be able to move without cutting a library release —
which is exactly why spaCy hosts 382 MB models on GitHub Releases rather than
PyPI. Carry a `compatibility.json`-style map (corpus schema version ↔ tool
version) and a corpus-age field so the client can warn on staleness the way
Grype does.

**3. T2 — `study-graph.json.gz` (4.86 MiB) as a second, explicitly opt-in asset.**
It is already a separate tier for a *different* reason (the cap), and that
tiering is already correct for distribution too.

**4. Keep `kb-build` as the documented reproducibility path, and stop implying it
is an install path.** It is the provenance guarantee — "you can verify every byte
from 33 pinned SHAs" — and that is genuinely valuable for a research substrate.
It is not an onboarding flow: 3.6 GB of full clones across 33 third-party repos,
any of which can force-push a pin away.

**5. Offer `serve_http` as a documented team deployment, not the default.** It
works today and needs no new code. Say plainly that auth is a single shared key
with no OAuth and no revocation, and that each process holds ~1.7 GB.

### The prose-only tradeoff is REAL — measured, both arms

I did not want to recommend T0 on the strength of `CLAUDE.md`'s recall claim
alone, so I probed the failure it implies.

- **Arm A (the claim):** `kb-query -- "push_to_falkordb" --prose --idf --top 5`
  → **0 relevant hits.** The top 5 are `handoffkit`, three unrelated
  `.mcp.json`/channels/PR-push prose nodes, and "Stripe's minions" — the lexical
  scorer matching the English word *push*.
- **Arm B (the control):** the same term against the aggregate graph → **11**
  matching lines, including the definition site.

So the probe discriminates, and the answer is unambiguous: **a code-symbol
question against a prose-only corpus does not degrade, it fails — and it fails
while returning confident-looking output.** That is the worst failure shape
there is. It makes the "explain the miss and offer the T1 fetch" mitigation in
the recommendation load-bearing rather than a nicety.

### Tradeoffs, stated honestly

| Choice | What you give up |
|---|---|
| prose-only default | Code-level questions ("where is X defined in cognee?") fail until T1 is fetched. Mitigation: the CLI should say *why* and offer the fetch, never return an empty result — an empty graph answer is indistinguishable from a corpus gap (`probes-need-a-control-arm.md`). |
| release asset over a wheel | Two version axes (tool version, corpus version) and a compatibility table to maintain — exactly the `compatibility.json` problem spaCy has. Needs a schema/corpus version field in the artifact. |
| fetch-on-demand | Breaks air-gapped/offline installs. Provide an explicit `--corpus <path>` and an offline bundle. |
| gzip on the wire | graphify has **no** compressed read path (verified), so install must decompress and the on-disk cost stays 194–382 MB. |
| not building a hosted endpoint | No always-fresh corpus, no usage telemetry. Accepted: a hosted default contradicts "local, deterministic, zero LLM tokens". |
| not using graph-DB push | No Cypher/analytics surface out of the box. Accepted: push is write-only, unbatched, and drops every `_`-prefixed property including `_origin` — the very attribute the prose tier is defined by. |

### The licensing constraint sits on top of all of this

A companion report, `.agent/kb/reports/agents/research-corpus-licensing.md`,
finds that `graph.json` is the **safest** artifact (a ~98% pointer index) while
`sources/media/` (verbatim third-party prose) and `sources/extractions/` are the
exposed ones — and both are **already public**. That does not change the
mechanism recommended here, but it does mean **T0 prose is the tier that needs a
licensing read before it ships**, because it is the derived-paraphrase layer.
Read that report before acting on this one.

---

## What I could NOT determine

1. **Cold `kb-build` wall-clock for a stranger.** Nothing in the repo records it.
   Measuring it means a ~3.6 GB cold clone across 33 repos plus a full
   extraction. What is measured instead: the input volume, the full-clone
   strategy, and that the AST cache (16 MB) is gitignored so the first build is
   always cold.
2. **Whether the 26-deep prefix stacking has corrupted any node identity**
   (e.g. two distinct nodes colliding, or `local_id` being wrong). `local_id` is
   written with `setdefault` (`build.py` L1461), so on a re-prefix it retains the
   *previously prefixed* value — it looks wrong, but I did not prove a
   user-visible defect from it. Worth a follow-up probe.
3. ~~Whether the prefix bug is already fixed in graphify > 0.9.31.~~
   **RESOLVED — it is NOT fixed.** PyPI latest is **0.9.32** (pin is 0.9.31), and
   0.9.32 is also installed locally. `prefix_graph_for_global` in
   `0.9.32/.../graphify/build.py` is **byte-identical** to 0.9.31 — same
   unconditional `relabel = {n: f"{repo_tag}::{n}" ...}`, same
   `setdefault("local_id", ...)`. The 512 MiB cap is unchanged too. Verified
   against the shipped source, not the issue tracker.
4. **`study-graph.json` composition** — I measured its size and gzip only; I did
   not check whether it carries the same prefix pathology (likely, same code
   path).
5. ~~Claude Code plugin size guidance.~~ **RESOLVED by the companion report:**
   marketplaces are git-based and the docs state **no size limit or guidance** at
   all; the documented home for bulky derived data is `${CLAUDE_PLUGIN_DATA}`.
   So "no stated limit" is not "any size is fine" — it means the platform
   expects you not to put it in the repo.
6. **Trivy DB artifact size.** The companion report could not verify it from a
   primary source (a secondary source says "hundreds of MB"). Not load-bearing
   here.
7. **Whether `graph.json.gz` should instead be an OCI artifact** (the Trivy/ORAS
   route). Defensible once there is a publish cadence and mirrors matter; not
   evaluated in depth because at 11.5 MiB a Release asset dominates on
   simplicity.

## Probes run, and their control arms

| Probe | Result | Control arm |
|---|---|---|
| graphify has a graph-DB READ path? | **No** | `push_to_falkordb` → 3 files (probe works); `GraphDatabase.driver\|FalkorDB(` → only `exporters/graphdb.py`; `MATCH (n` → 0 |
| graphify has a compressed graph format? | **No** | `build_from_json` → 10 files (probe works); `gzip\|zstd\|zlib\|sqlite\|parquet\|msgpack` → 1 unrelated hit in a Discord extractor |
| prose-only fails a code-symbol query? | **Yes, and silently** | Arm A `--prose` → 0 relevant of 5; Arm B aggregate → 11 hits |
| is the 41% prefix redundancy real? | **Yes** | Histogram over all 140,680 node ids (0→26 reps); prose graph is clean (0 or 1), so the measurement discriminates rather than matching everything |

**Not control-armed, and flagged as such:** the gzip and RSS figures are single
measurements on one machine (Apple silicon, `gzip -6`, CPython 3.13 + networkx).
Ratios of this magnitude are not noise-sensitive, but the absolute seconds are.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the subject repo: `mise.toml`, `python/src/kb_setup/graph.py`, `graphify-out/*.json`, `sources/`, issue list.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — read the **installed** 0.9.31 source: `exporters/graphdb.py`, `build.py`, `cli.py`, `security.py`, `serve.py`.
- [mattpocock/skills](https://github.com/mattpocock/skills) — ingested at `sources/mattpocock-skills/`; read its ADR `0002-ship-as-a-claude-code-plugin.md` for a peer's Claude-Code-plugin distribution decision (manifest shape, `skills` array vs single path, symlinks dropped on install, plugin `version` as the update signal).
- [topoteretes/cognee](https://github.com/topoteretes/cognee) — appeared in graph query results as the largest single-run source (10,099 test↔src edges); used only as a size/shape reference.

Cited in this report via the companion research (full evidence and additional
repos are enumerated in `research-peer-data-distribution.md`):

- [explosion/spacy-models](https://github.com/explosion/spacy-models) — the closest precedent: 12–436 MB models as wheels on GitHub Releases + `compatibility.json`.
- [tldr-pages/tldr](https://github.com/tldr-pages/tldr) — per-language zips + `tldr.sha256sums` on Releases; the 20.1 MB `tldr.zip` is this report's size calibration point.
- [nltk/nltk](https://github.com/nltk/nltk) / [nltk/nltk_data](https://github.com/nltk/nltk_data) — per-package `index.xml` with MD5 + SHA-256 per package.
- [anchore/grype](https://github.com/anchore/grype) — `latest.json` + checksum on plain HTTPS storage, plus a 5-day DB staleness refusal.
- [aquasecurity/trivy](https://github.com/aquasecurity/trivy) / [trivy-db](https://github.com/aquasecurity/trivy-db) — OCI/ORAS artifact on `ghcr.io`, tag = schema version.
- [ollama/ollama](https://github.com/ollama/ollama) — OCI Distribution v2 registry, SHA-256 content-addressed blobs, resumable 16-part pulls.
- [huggingface/huggingface_hub](https://github.com/huggingface/huggingface_hub) — blobs/snapshots/refs cache + Xet chunk-level CAS + `allow_patterns` partial fetch.
- [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter) — the counter-example: official tooling compiles grammars locally, no prebuilt distribution.


`--prose` and `--idf` are already the *recommended* query arms in `CLAUDE.md`
("best arm, natural recall 1/8 -> 3/8 -> 5/8"). The documented reason is that
138k AST nodes crowd prose out of the answer budget. **The retrieval quality
argument and the distribution argument point the same way**, which is unusual
and worth leaning on: shipping prose-only is not a degraded corpus, it is the
arm the repo already tells you to use for document questions.



