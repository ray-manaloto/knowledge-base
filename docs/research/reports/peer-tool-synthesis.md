# Peer-tool synthesis — three gap analyses, one comparison

**Status**: COMPLETE. This document *combines* three finished reports. It does
not research and it does not verify. Where an input marked something
UNVERIFIED it stays UNVERIFIED here; where two inputs disagree, the
disagreement is reported rather than resolved.

## Inputs, and the condition each one holds under

| Report | Tool | Pinned SHA | Lens | Executed? |
|---|---|---|---|---|
| `codebase-memory-mcp-retrieval-gap.md` | [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) ("CBM"), C, MIT | `d6be58ef9d43c574a2d1b0827ecc1e3c4846f0fe` | retrieval | **no** — source read only |
| `code-review-graph-retrieval-gap.md` | [tirth8205/code-review-graph](https://github.com/tirth8205/code-review-graph) ("CRG"), Python, MIT | `c3f3a6681791f6c6d870e8e437ecfe4e8500e377` | retrieval | **no** — source read only |
| `mindwalk-harness-observability.md` | [cosmtrek/mindwalk](https://github.com/cosmtrek/mindwalk), Go, MIT | `e208b6b8504138843f671e031f28129b66003a67` | **observability, not retrieval** | **yes** — built the pinned binary, ran `trace`/`build` on real sessions |
| `verifier-tests-cover-change.md` ⚠️ **fourth input, not in the brief** | adversarial verification of one CRG-report claim | HEAD `99eb824` | retrieval | **yes** — ran `affected`/`path`/`explain` on the live graph |

**A fourth report was in the working tree and is included.** The brief named
three inputs; `verifier-tests-cover-change.md` was staged alongside them and
**refutes the headline claim of one of the three** — the claim this synthesis
had ranked as the single clearest gap in the set. Excluding it because it was
unlisted would have shipped a known-false headline. Its effect is carried in
**G1** and §4.1(c). Flagged to the team lead: the input list was incomplete.

**Baseline in all four: graphify 0.9.31**, read off the pinned install at
`~/.local/share/mise/installs/pipx-graphifyy/0.9.31/bin/graphify` (both
retrieval reports state that provenance explicitly).

Three conditions travel with everything below and are easy to drop:

1. **No peer tool except mindwalk was executed.** Every CBM and CRG capability
   claim is a source read at a pinned SHA. Neither binary was built, neither MCP
   server was handshaked, no benchmark was re-derived. "CRG can do X" throughout
   means "CRG's source at `c3f3a66` implements X", not "X was observed working".
   The two reports that *did* execute something — mindwalk's and the verifier's —
   both ran against **our** side, not the peer's. This asymmetry is why the one
   claim that got an execution arm on the graphify side (G1) is also the one
   claim that collapsed.
2. **The graphify side is 0.9.31 specifically**, and several claims are about
   `serve.py` as shipped — a version bump can invalidate them.
3. **The retrieval reports and the observability report are not on one scale.**
   Their confidence vocabularies were never reconciled and their authors were
   different agents. Do not read a CRG row and a mindwalk row as equally strong
   because both say "CONFIRMED".

---

## 1. Cross-tool comparison

**The comparison axis is the question in the left column — not a feature name.**
A tick would hide the only thing that matters: whether adopting the tool changes
what a session can actually answer. Read each cell as an answer to that row's
question.

`n/c` = **not comparable on this axis** (see §3), which is a different answer
from "no".

| Question an agent actually asks | graphify 0.9.31 (as this repo runs it) | CBM | CRG | mindwalk |
|---|---|---|---|---|
| **"Is the index I'm reading current with my working tree — right now, in this response?"** | **No.** `built_at_commit` is written (`export.py:317`) but `serve.py` never reads it (grep → 0; control `token_budget` → 20). Compensated out of band by `kb-currency-check`, which the MCP consumer never sees | Not addressed in the CBM report; it reports a `file_hashes` table + watcher that keeps the index fresh, which answers a *different* question | **Yes, per call.** `_graph{updated_at, age_seconds, built_at_sha, built_on_branch, head_sha, head_matches_build}` wrapped onto every tool result by `with_provenance()`; `head_matches_build` is a live `git rev-parse` compared to the stored build SHA. Commits only — deliberately makes no claim about staged/unstaged | n/c |
| **"Which tests cover this symbol?"** | **Yes for the tool, no for our own code.** ⚠️ The CRG report's "no" was **REFUTED by execution** — `graphify affected "<symbol>" --depth 1` returns test functions with `file:line` today. It fails **only across extraction runs**, and this repo splits `python/` and `tests/` into two. See **G1** | Not claimed either way in the CBM report | **Yes, and by name.** 63 `TESTED_BY` sites, `get_transitive_tests` (`graph.py:541`) follows direct edges plus indirect coverage through `CALLS` hops, frontier capped at 50/hop; exposed as the `tests_for` pattern | n/c |
| **"Which tests must I run for *this diff*?"** | **No.** `affected` answers symbol → dependents; there is no `affected --since <ref>`. Mapping a changed hunk to the symbols it touches is the caller's job | Not claimed | **Yes** — diff → changed nodes → `TESTED_BY`, plus coverage-gap detection (changed nodes with no reachable test) | n/c |
| **"I just edited some files — what did I endanger?"** | **Partly.** `compute_pr_impact(files, G)` (`prs.py:252`) does take a changed-file list, and `list_prs`/`get_pr_impact`/`triage_prs` expose it — but the change-set comes from `gh pr diff --name-only` (`prs.py:230`), so it needs GitHub **and an open PR**, and is file-granular and community-level | **Yes.** `detect_changes` maps *uncommitted git changes* to affected symbols with risk classification | **Yes, and finer.** `parse_git_diff_ranges` uses `git diff --unified=0` to intersect **hunk line ranges** with node spans; reads staged **and** unstaged (`get_staged_and_unstaged`), plus SVN; node-level scores with decay, `truncated` flag | n/c |
| **"Before I touch X, who is downstream of it?"** | **Yes.** `graphify affected "X" [--relation R] [--depth N]` — reverse BFS from one resolved node, with call-site `file:line`. No score, no cap, no truncation flag | Reachable via `trace_path(direction="inbound")` or Cypher | **Yes**, as `find_dependents` / `callers_of`, with an explicit `.truncated` | n/c |
| **"Can I state a precise structural question and get an exact answer?"** | **No structured input surface.** `query_graph` takes a natural-language string and walks BFS/DFS at depth ≤ 6 under a token budget. graphify **emits** Cypher (`exporters/graphdb.py`, 29 hits; control `neo4j` → 24) but accepts none. Reachable indirectly by pushing to Neo4j/FalkorDB and querying there | **Yes** — a Cypher-like engine (`src/cypher/`) exposed as the `query_graph` tool | **Yes** — a closed 16-pattern relational vocabulary (`_QUERY_PATTERNS`), six of them *framework*-semantic (Spring schedulers, event buses, HTTP endpoints) | n/c |
| **"Will it find the thing when my words differ from the code's words?"** | **Partly, and the previously-stated reason was wrong.** graphify **does** IDF-weight the *seeds* (`_compute_idf`, `serve.py:275`, called from `_score_query`, `serve.py:468`) with a trigram prefilter and tiered label matching. What it does not do is stem, or rank the *returned* neighbourhood. This repo's `--idf` arm ranks the returned set and adds stemming | **Yes, deterministically** — a frozen 40,856-token × 768d int8 vector table compiled into the binary (`.incbin`); no model runs at index or query time, no key, no daemon | **Yes** — FTS5/BM25 with `tokenize='porter unicode61'`, RRF-fused with optional vector embeddings (local `sentence-transformers`, or 4 cloud providers) | n/c |
| **"How much of the answer was dropped to fit my context, and was I told?"** | **Disputed across the two inputs — see §4.1.** `--budget N` exists; whether truncation is surfaced to the caller is claimed both ways | **Told: no. Compressed: yes.** No token budget at all (armed: 0 hits; control `"limit"` → 7); instead TOON dense encoding (`compact_out.h`) claiming 40–60% fewer tokens on homogeneous sets | **Yes, in a type.** `DependentList.truncated`, `get_impact_radius(...)["truncated"]`, plus a `detail_level: minimal\|standard` dial on nearly every tool | n/c |
| **"How was this edge derived, and can I audit that in aggregate?"** | **Yes, aggregate.** Closed validated vocabulary `{EXTRACTED, INFERRED, AMBIGUOUS}` (`validate.py:5`) with default scores, preserved through GraphML, rolled up as the `graphify://audit` MCP resource. Control: `ZZQQNOTATOKEN` → 0, `INFERRED` → 85, `EXTRACTED` → 188 | **Per edge, richer; no rollup.** Numeric confidence **plus a named resolution strategy** in the edge `properties` JSON (`pass_calls.c:355`, `pass_configlink.c:182`) — better for debugging one bad edge, unvalidatable in aggregate because nothing constrains the strategy vocabulary | **Same vocabulary, thinner discipline.** `confidence_tier TEXT DEFAULT 'EXTRACTED'` (`graph.py:104`), but `INFERRED` is written in exactly 2 modules / 4 sites across 41,753 lines and **0 times in `parser.py`** — a demotion marker on two heuristics, not extraction-time provenance. Richer in one way graphify is not: `ambiguous_targets`/`unresolved_targets` returned *in the payload* | n/c |
| **"Can I ask about a doc, a paper, a transcript, a URL?"** | **Yes — this is the corpus's reason to exist.** `ingest.py:64 _detect_url_type` → youtube/pdf/arxiv/tweet/web; `llm.py` extracts prose *semantics*; this repo's whole `kb-extract` fan-out | **Headings only.** It does parse markdown structurally (`lang_specs.c:834–836`, `extract_defs.c:3630`) — so a free deterministic heading outline. But `.pdf`/`.doc(x)`/`.xls(x)`/`.ogg`/`.mkv`/`.webm` are on the *skip list* (`discover.c:73`); armed `youtube`/`whisper`/`fetch_url` → 0 files each, control `Dockerfile` → 8 | **No, and it cannot fetch at all.** The only network code in the entire package is `embeddings.py` (armed: `urlopen\|urllib.request\|socket.connect` → 1 file). Its `get_docs_section_tool` reads CRG's own packaged reference, not user docs | n/c |
| **"Does answering this cost an LLM call or a key?"** | **Free for code, LLM for the rest.** `update`/`query`/`path`/`explain`/`affected` are deterministic; community *labelling* and prose extraction are LLM paths (Claude-only here, by invariant) | **No LLM anywhere**, index or query. README states it and the design corroborates: frozen embedding table, Louvain, TF-IDF/BM25/MinHash | **No chat/completion LLM** (armed: 0 hits; control 44 embedding-endpoint hits). Embeddings are optional and can be fully local. Its cloud providers `{google, minimax, openai, voyage}` would violate `do-not.md` rule 4 here; the local provider makes that tractable, not a blocker | Judge is opt-in only (`mindwalk analyze`); `trace`/`build` are LLM-free |
| **"What did the agent actually read and touch this round, and did that match its brief?"** | **No** — nothing in this repo reads a transcript | **No** | **No** | **Yes — this is its entire surface.** Confirmed by execution: a real `kb-review` cold lane replayed as 93 events, 24 distinct paths ranked, `edit: 0`, alongside the lane's own verbatim brief |

---

## 2. Consolidated gap list

Ranked by *how much a session's answerable questions would change*, not by
effort. Each entry carries the verification status **from the input report** —
nothing here was re-derived.

### G1 — Test-impact mapping: a repo wiring defect, **not** a graphify capability gap

This entry was drafted as "graphify cannot answer which tests cover this
change", ranked #1, and sourced to a control-armed grep in the CRG report. **The
fourth input refutes it by execution.** The corrected finding is narrower, more
actionable, and points at our own code rather than at the tool.

- **What is REFUTED**: *"graphify cannot answer 'which tests cover this change'"*. `graphify affected "get_document_from_graph" --depth 1` returns test functions with `file:line` under `tests/`, from the same graph the CRG report was written against. Four control arms, three positive: bogus symbol → `No unique node match` (discriminates absence); `_state` → 9 test functions in this repo's own `tests/`; `commit_file` → 17 test functions across two files from a `conftest.py` fixture; `get_document_from_graph` → tests under `cognee-mcp/tests/`.
- **Why the original probe was wrong — and it is a failure mode this repo has a rule for.** `grep -rln "tested_by\|TESTED_BY\|tests_for"` → 0 files is *literally true*: graphify has no relation **named** `TESTED_BY`. It reaches tests through ordinary `calls` edges instead. That is a **token-spelling bound** — the exact `lmstudio` vs `LM Studio` shape in `probes-need-a-control-arm.md`, which the CRG report itself cites two sections earlier. The grep's control arm (`affected` present in `cli.py`) proved the *file* was readable; it never proved the *term* was the right one. **A control arm that discriminates the corpus does not discriminate the vocabulary.**
- **What survives, and is CONFIRMED by measurement**: graphify links a test to the symbol it exercises **whenever both are in the same extraction run**, and cannot link across sub-graphs joined by `merge-graphs`, which re-namespaces node ids and adds no cross-graph edges. This repo's `kb_setup.graph._SELF_TREES = ("python", "tests")` runs **two** separate `graphify extract` passes and union-merges them.
  - Structural scan of `graphify-out/graph.json`: edges touching a `tests::` node **3,368**; within `tests::` only **3,368**; **crossing `tests:: ↔ other`: 0**. Control: edges within `::python::` only → **2,194**, proving the scan sees real edges.
  - Natural experiment: `cognee` is pinned as a **single** source extracted in **one** run — same scan, same script, same graph file → **10,099** test↔src crossing edges (control `src<->src` → 33,848). One variable differs: one extraction run versus two.
  - Isolating A/B: `sync.restamp_artifacts(…)` called with byte-identical syntax from `graph.py:252` (edge **present**) and `test_currency_staleness.py:378` (edge **absent**). So it is not an attribute-call resolution failure; attribute calls work.
- **Unanswerable today, precisely**: given a changed symbol in `kb_setup`, which of **our** tests exercise it. The capability works for every pinned source extracted in one run; it is dark for exactly the code we write. `knowledge-base#101` is therefore **CONFIRMED by measurement** — upgraded from the inherited status this synthesis first assigned it.
- **A second, genuinely-absent thing that the refutation does not rescue**: `affected` answers **symbol → dependents**, not **diff → tests**. There is no `affected --since <ref>`; mapping a changed hunk to the symbols it touches is the caller's job. That ergonomic gap is real, is CRG's actual advantage here, and is now split out as its own row in §1.
- **Cost to close**: **one line, plus a rebuild** — merge `python/` and `tests/` into a single extraction root in `kb_setup.graph`. Far cheaper than the "upstream extractor feature" this entry originally estimated. ⚠️ **The fix's efficacy is UNVERIFIED**: the verifier could not probe a combined single-run extraction of `python/`+`tests/` directly, because that needs a raw `graphify extract` and `kb_setup.hook_guard` denies it. The cognee experiment is the *indirect* arm; a direct arm is a `kb_setup.graph` change plus `kb-build`.
- **What this costs the comparison**: CRG keeps a real but much smaller edge here — a *named* `TESTED_BY` relation with transitive closure, a diff-driven entry point, and coverage-gap detection. It no longer demonstrates a capability graphify lacks.

### G2 — An MCP consumer cannot tell whether the graph predates the working tree

- **Demonstrated by**: CRG (`with_provenance()` / `graph_provenance()` in `tools/_common.py`).
- **Status**: **CONFIRMED, control-armed.** `grep -rn "built_at_commit" serve.py` → 0; `rev-parse` → 0; `stale` → 2 unrelated hits. Control `grep -c "token_budget" serve.py` → **20**, so the probe discriminates on that file.
- **Unanswerable today**: any consumer of `mise run kb-serve` — including another repo — asks a question and gets an answer with no indication whether the graph was built three commits ago. `kb-currency-check` answers it *offline, repo-locally*, which the MCP consumer never sees.
- **Cost to close — the lowest in this set, and the best value-to-effort item across all three reports.** The datum already exists in our own `graph.json`: `export.py:317` writes `built_at_commit` from `_git_head()`. `serve.py` simply never reads it. Adding a `_graph` envelope needs that read plus one bounded `git rev-parse`. CRG's implementation is *~40 lines* — ⚠️ an **inherited estimate from the CRG report**, not a measurement of what it would cost here.
- **Carry CRG's two design decisions with it**: the whole path is `try/except`-wrapped so a missing or locked store degrades to *no envelope* rather than a failed call, and the read uses a 50 ms timeout so a concurrent build never blocks a query. Also carry its **scope honesty**: `head_matches_build` compares commits only and explicitly declines to claim staged/unstaged files are represented (they withdrew an older `is_stale=False` contract for exactly that reason, their #458). A staleness flag that overclaims is worse than none.

### G3 — Impact analysis needs GitHub and an open PR, and stops at file granularity

- **Demonstrated by**: CBM (`detect_changes`) and CRG (`parse_git_diff_ranges`, `get_staged_and_unstaged`).
- **Status**: **CONFIRMED**, and it survived a refutation: the stronger draft claim *"graphify has no change-set blast radius"* is **false** — `prs.py:252 compute_pr_impact(files, G)` exists and is exposed over MCP. The surviving, narrower claims are (a) the change-set source is `gh pr diff --name-only` (`prs.py:230`), and (b) granularity is community-level, not node-level, and file-level, not hunk-level.
- **Unanswerable today**: "I have uncommitted edits — what did I just endanger?" There is no local-diff entry point. And a one-line change in a 3,000-line file has the same blast radius as a rewrite of it.
- **Cost to close**: moderate and **entirely wrapper-side**, which makes it attractive. A `kb_setup` module can produce a changed-file list from `git diff`/`git status` and feed the *existing* `compute_pr_impact`, removing the GitHub dependency without touching graphify. Hunk-level intersection additionally needs node `line_start`/`line_end` spans — check whether the graph already carries them before assuming this is upstream work.

### G4 — Nothing here can see what an agent actually did

- **Demonstrated by**: mindwalk. **This is the observability lens, not a retrieval gap** — it belongs in the same list because it is a real capability gap, not because it competes with G1–G3.
- **Status**: **CONFIRMED BY EXECUTION** — the only such status in this set. The pinned binary was built (`go build`, rc=0) and run on a real 2,800-line session of this repo (388 events, 135 paths) and on a real `kb-review` cold lane (93 events, 24 paths, `edit: 0`, brief captured verbatim including the SHA).
- **Unanswerable today**: *what did the review lane actually read?* The `kb-review` receipt records which lane ran and where its report is; it records nothing about the lane's footprint. **A lane that reviewed 3 of 40 changed files leaves a receipt indistinguishable from one that read all 40.** The related metric `editsAfterLastVerify` is a machine-readable score for `verify-before-advancing.md`, a rule this repo currently enforces by assertion only.
- **Cost to close**: `mindwalk trace <session> -o out.json` and `mindwalk build <repo> -o out.json` are **headless JSON emitters** — no browser, no 3D, rc=0 — so the cheap version is a `kb_setup` module plus a mise task, well inside `zero-bash-logic.md`. Confirmed working *for this repo's subagents specifically*: all 89 `agent-*.jsonl` under this project's dir sit at `<sessionID>/subagents/`, the exact path `agents.go:41` computes.
- **Two hard bounds to carry, or the adoption over-promises**:
  - **Workflow subagents are invisible** — machine-wide, 1,733 of 1,946 `agent-*.jsonl` live at `<sessionID>/subagents/workflows/wf_<id>/`, one level below a non-recursive `ReadDir` that skips directories. **Zero of those are in this repo's project dir today** — so this bound is dormant here, and would bite the moment a round used `Workflow` instead of `Agent`.
  - **The judge's "spec" is a 600-rune prefix** of a user message (`maxUserMessageLen = 600`, `judge/input.go:18`). This repo's `docs/goals/*-goal.md` payloads are budgeted to ≤4,000 chars *by design* and mindwalk cannot read them at all. Its `scope` category is real and first-class — but scored against a truncated prompt, not against the tracked goal.

### G5 — No stemming, and the returned set is unranked

- **Demonstrated by**: CRG (FTS5, `tokenize='porter unicode61'`, RRF).
- **Status**: **CONFIRMED**, after a refutation that changes the reason but not the gap. graphify has no BM25/FTS5/RRF (`grep -rln "bm25\|fts5\|reciprocal rank"` → **0 files**) and no vector index (`embedding\|cosine` → 4 files, **all four are the English word** — YAML escaping, Go interface embedding; control `networkx` present).
- **The correction that must travel with this row**: *"graphify's query is an unscored BFS"* is **REFUTED**. `_compute_idf` (`serve.py:275`) is called from `_score_query` (`serve.py:468`), with a trigram prefilter, tiered label matching, coverage scaling and an IDF-weighted whole-query bonus. The accurate statement: **graphify ranks the SEEDS by IDF and returns an unranked, budget-truncated neighbourhood of them**; this repo's `--idf` ranks the *returned set* and adds stemming. The measured 1/8 → 3/8 → 5/8 recall gain stands; the reason previously given for it did not. ⚠️ See §4.2 on that number's noise floor.
- **Unanswerable today**: a query whose terms are morphological variants of the code's (`parsing` vs `parse`), or one where the right answer is 40 nodes into an unranked neighbourhood that the budget cut at 30.
- **Cost to close**: stemming inside `kb_setup`'s `--idf` arm is cheap and already half-built. Genuine FTS5/BM25 means an indexed store, i.e. G7.

### G6 — No structured query input

- **Demonstrated by**: CBM (Cypher engine, `query_graph`) and CRG (16 closed patterns incl. framework semantics).
- **Status**: **CONFIRMED**, after a refutation: *"graphify has no Cypher"* is **false as stated** (29 hits, control `neo4j` → 24). All of them are **export-side** — `exporters/graphdb.py`, `export.py:339 _cypher_escape`. The precise claim is *no Cypher **input** surface*.
- **Unanswerable today**: "who calls X" as an exact indexed lookup. Today it is a keyword BFS whose recall depends on the question's tokens matching node labels — the exact failure mode `probes-need-a-control-arm.md` documents (`lmstudio` → 0, `LM Studio` → 3).
- **Cost to close**: near-zero for the capability, high for the convenience — graphify already reaches it by pushing to Neo4j/FalkorDB and querying there (`push_to_neo4j`/`push_to_falkordb`, `--push`). That is infrastructure, not code. CRG gets indexed relational query with **zero** infrastructure; that is the honest framing of the difference.

### G7 — The graph must be fully loaded to be queried, and cannot be shared

- **Demonstrated by**: CBM (SQLite + committable `.codebase-memory/graph.db.zst`, 8–13:1, `merge=ours` gitattributes) and CRG (SQLite + 9 indexes + FTS5; impact traversal executes *in SQL*).
- **Status**: **CONFIRMED** as a design difference. The *consequence* figures are weaker — see §4.
- **Unanswerable today**: nothing, strictly — but it is why `--budget` is a survival mechanism here rather than a product decision, and why a teammate or consumer repo cannot receive a graph as a file (`do-not.md` invariant 5).
- **Cost to close**: the native answer already exists (Neo4j/FalkorDB push) and costs a running server. There is no cheap path to a *committable* artifact at this corpus's size.

### G8 — CBM-only capabilities with no counterpart here

Grouped because none is individually decisive for this repo, all **CONFIRMED**
as present in CBM by source read:

- **Automatic cross-client freshness** — one coordination daemon shared across Claude Code / Codex / OpenCode plus a background watcher, versus this repo's explicit `mise run kb-watch`.
- **Cross-service linking** — HTTP route ↔ call-site, gRPC/GraphQL/tRPC, `EMITS`/`LISTENS_ON` edges. graphify has no service-topology layer.
- **IaC as graph nodes** — Dockerfile/K8s/Kustomize with `IMPORTS` edges.
- **Dense output encoding (TOON)** — a genuinely different answer to the context-window problem than a budget cap. The 40–60% figure is the vendor's; see §4.
- **Zero-dependency static binary**, no Python runtime.

### G9 — Two defects in *our own* tooling, surfaced by the researchers

Both **CONFIRMED**, both about this repo rather than any peer tool, and both
cheap:

1. **`study-graph.json` has no sanctioned query path.** The `graphify query --graph …` form the round's brief suggested is **denied** by `kb_setup.hook_guard` (it fired), and `mise run kb-query` exposes only `--prose`/`--idf`/`--budget`/`--top` — **no `--graph`** (control: `--prose` found by the same grep of `mise.toml:263-287`). So the study graph `kb-build` produces is currently readable only by parsing the JSON by hand. **Cost to close: one flag** on `kb_setup.query`.
2. **The study graph's `repo` field does not discriminate study sources.** Every node carries `repo ∈ {knowledge-base: 41,154, mindwalk: 2,845}`; **no node is attributed to `code-review-graph`** although 2,612 nodes have `code_review_graph/…` source paths (control: `code_review_graph/parser.py` alone → 604 nodes, so the corpus is really there). `_build_study_graph` seeds from the first study source and merges the rest, and `repo` does not survive as a per-source discriminator. Filtering by tool must use `source_file` today. **Cost to close: a merge-time attribution fix in `kb_setup.graph`.**

### G10 — Not gaps: assumptions that died

Recorded so they are not re-proposed. **CRG independently ships** community
detection, hub/bridge nodes (graphify's `god_nodes`), a generated wiki, an
architecture overview, graph stats, an eval harness, visualization/exports,
multi-repo cross-search, **and** a near-shape-identical work-memory module
(`memory.py`: `save_result`/`list_memories`/`clear_memories`, writing markdown
to `<repo>/.code-review-graph/memory/`). Every one was on the researcher's
initial "graphify-only" list and none survived.

**The surviving distinction is narrow and specific: memory yes, reflection no.**
`grep -rln "reflect\|LESSONS\|half_life\|decay"` over CRG → 1 file
(`context_savings.py`, unrelated). graphify's `reflect.py` — `_decay(half_life_days)`,
`aggregate_lessons`, `render_lessons_md`, community mapping of memory docs — has
no CRG counterpart. So `kb-remember` is table stakes; `kb-reflect` is the
differentiator.

---

## 3. Not comparable

Collapsing "not applicable" into "scored badly" is how a comparison stays true
row-by-row and misleads as a whole. These are the cells where that would happen.

### 3.1 mindwalk on every retrieval axis — a category error, not a low score

mindwalk reads Claude Code / Codex **session logs** and replays agent footprint
on a deterministic repository layout. **It has no symbols.** Its citymap entry
schema, dumped from a real `mindwalk build .` run on this repo (357 entries), is
eight keys: `{id, path, dir, lines, bytes, lang, rect{x,z,w,d}, ghost}` — control
arm: `lines`/`lang` *are* present, so the dump is not empty. Height encodes LOC.
There is no call edge, no query surface, **nothing to ask it**.

So every `n/c` in §1's retrieval rows means *this tool does not operate on that
surface*. Scoring mindwalk 0 on "which tests cover this change" would be like
scoring a profiler 0 on spell-checking. Conversely, graphify, CBM and CRG all
score a genuine **no** on §1's last row — none of them reads a transcript — and
that one *is* a comparable absence.

Two properties make mindwalk structurally disqualified as a substitute for any
part of graphify's role here, independent of features:

- **Its input is machine-local and unversioned.** `~/.claude/projects` /
  `~/.codex/sessions` — never committed, pruned by the harness. **A trace is not
  reproducible on another machine, ever.** That is a direct conflict with this
  repo's reproducibility invariant, not a missing feature.
- **Its reports are keyed to a session, not a commit.** Cached in
  `~/.mindwalk/reports`, stale on content change. Nothing binds a report to a
  SHA, so nothing can gate a merge on one. **A session is not a change.**

The correct framing, from the observability report and endorsed here: *graphify
knows the code; mindwalk knows the walk.* They occupy disjoint surfaces.

### 3.2 CBM and CRG on prose — genuinely comparable, and both lose

This is **not** a not-comparable row, and it is worth saying so explicitly
because it is the axis on which this repo's whole reason to exist sits. Both
tools were probed and both have a real, non-zero answer:

- CBM parses markdown *structurally* (heading outline, `lang_specs.c:834–836`) but excludes PDF/office/video formats outright and has no fetch path.
- CRG cannot fetch a URL at all (only `embeddings.py` touches the network) and has no LLM path of any kind.

Neither can hold this corpus's 2,553 indexed prose nodes as anything but a
heading skeleton. That is a **low score on a fair axis**, not a category error.

### 3.3 Numbers that must not be ranked

- **MCP tool counts (graphify 11 · CBM 15 · CRG 30).** All three were counted correctly (CRG's is control-armed: `grep -c "@mcp.tool()" main.py` → 30). They are **not** a capability measure — CRG's 30 include a wiki generator, a docs reader over its own packaged reference, and refactor writers; graphify's 11 sit over a corpus 26 sources wide. Reporting them as a ranking would be false precision.
- **Language counts.** CBM's is 158 (README badge) or 159 (`THIRD_PARTY.md`) — the off-by-one was **not reconciled**, and a vendored grammar proves a file *parses*, not that useful nodes are emitted. CRG's is **unknowable from source** — it delegates to `tree_sitter_language_pack.get_parser()` at runtime. graphify's 28 `extractors/*.py` is a **lower bound on its own set**, explicitly not a like-for-like number. There is no valid three-way language comparison in these inputs.
- **Every vendor benchmark.** See §4.3.

---

## 4. Disagreements, inherited numbers, and noise floors

### 4.1 Two unresolved cross-report disagreements

Two probes of one fact disagreeing is a finding, and the finding is usually in a
probe. Neither is resolved here — resolving them is research, which this
synthesis does not do.

**(a) Does graphify report its own truncation?**

| Input | Claim |
|---|---|
| CBM report §2 | graphify's `query` "**reports its own truncation**" — quoting `TRUNCATED: showing 70 of 487 nodes… raise --budget` |
| CRG report, verdict item 2 | "**`kb-query`'s budget truncation is currently silent.**" |

These may be compatible — one is about `graphify query`, the other about this
repo's `kb_setup.query` wrapper, which could be swallowing the notice — but
**nothing in either report establishes that**, and §1's truncation row is
therefore marked disputed rather than answered either way. Anyone acting on
"add truncation flags" should settle this first; it may already be a
wrapper-level one-liner rather than a feature.

**(b) How large is `graphify-out/graph.json`?**

| Source | Figure |
|---|---|
| CBM report §4 | **382 MB** |
| CRG report, indexing model | **119 MB** |
| `CLAUDE.md` | 119 MB |

A 3× disagreement on a load-bearing number — it is the stated reason the graph
cannot be committed and the reason `--budget` is survival rather than
convenience. The *conclusion* (too large for git) is unaffected at either value,
which is why neither report caught it. **Do not repeat either figure without
re-measuring.**

**(c) Can graphify answer "which tests cover this symbol"? — RESOLVED, against the input report.**

Unlike (a) and (b), this one **is** settled, because the fourth input ran the
command rather than grepping for a keyword.

| Input | Claim | Method |
|---|---|---|
| CRG report | **No** — `TESTED_BY\|tests_for` → 0 files, control armed | keyword grep over the installed package |
| `verifier-tests-cover-change.md` | **Yes** — `affected "<symbol>" --depth 1` returns test functions with `file:line` | ran the command, 4 control arms |

**The executing probe wins, and the grep was defeated by vocabulary, not by
the corpus.** Full treatment in G1. Recorded here because of what it says about
the *method*: of the ~52 capability rows in these reports, this is the only one
where anybody ran the tool being judged, and it is the only row that reversed.
That ratio is a finding about the process, not about graphify.

A third, smaller mismatch, noted rather than resolved: both retrieval reports
state the prose graph holds **2,553** indexed nodes; `CLAUDE.md` says **2,105**.
Most likely a doc that predates an ingestion — but it is unestablished, so
2,553 travels here with that caveat attached.

### 4.2 The 1/8 → 3/8 → 5/8 recall gain has no stated noise floor

The `--idf` arm's measured recall improvement is real, is this repo's own
measurement, and is **not** discarded here. But before it is used to rank
anything: **n = 8 queries, one run per arm, and no same-input variance was ever
measured.** A 4/8 swing on 8 items is large enough that it is probably not
noise — and "probably" is the honest word, because nothing in these inputs
establishes what the noise floor is. Its condition is also specific: it compares
`--prose` and `--prose --idf` arms against a natural-recall baseline on the
prose graph, not the aggregate.

The corollary, per the round's own correction: the gain stands, the **reason**
previously given for it (`graphify's BFS is unscored`) does not. Anyone citing
the number must cite the corrected mechanism — seed IDF exists upstream; the
delta is stemming plus ranking the returned set.

### 4.3 Inherited numbers, labelled

None of these were re-derived. Each is repeated here **only** with its owner
attached, and none may be used to rank anything:

| Figure | Owner | Status |
|---|---|---|
| Linux kernel indexed in 3 min · <1 ms Cypher · 120× fewer tokens · arXiv 83% / 10× / 2.1× | CBM vendor | **UNVERIFIED** — binary never built or run |
| TOON saves 40–60% of tokens on homogeneous result sets | CBM vendor | **UNVERIFIED** |
| 38×–528× token reduction · ~10 s for a 500-file project | CRG vendor | **UNVERIFIED** — CRG never executed |
| CRG's staleness envelope is "~40 lines" | CRG report's own read | plausible, but an estimate of *their* code, not of the work here |
| ~9.5 s unscoped `kb-query` vs ~0.3 s on the prose graph | this repo's earlier measurement | inherited into the CRG report; n and conditions not restated there |
| mindwalk sidecar `toolUseId`-present rate ~3.5% | mindwalk report | **explicitly UNVERIFIED** — first 400 sidecars by glob order; the bound was not removed |

The mindwalk report's own execution figures (388 events / 135 paths on a real
session; 93 events / 24 paths on a real lane; 357 citymap entries; rc=0 builds)
are **not** in this table — those were produced by running the pinned binary in
this session, and are the strongest evidence in the whole set.

---

## 5. Claim counts

**Counting rule, stated because the number is meaningless without it**: these
count entries in the reports' *own* registers and armed tables. I re-derived
none of them. "Control-armed" means the report states both a test result and a
control result that discriminates.

| Report | Control-armed / confirmed | Refuted | Explicitly UNVERIFIED |
|---|---|---|---|
| CBM (retrieval) | **6** control-armed (version provenance · `semantic_query` 16 vs 77 · Cypher 29 vs 24 · token-budget 0 vs 7 · confidence vocabulary 0/85/188 · non-code exclusion 0 vs 8), plus ~8 further `file:line`-cited claims with no explicit control | **5** | **6** |
| CRG (retrieval) | **9** control-armed within 25 enumerable comparison rows (14 Direction 1 · 7 Direction 2 · 4 orientation receipts) | **4** refuted + **1 narrowed** | **3** |
| mindwalk (observability) | **6** confirmed in its §6 register, each with its arm stated — **1 of them by execution**; plus 7 Direction-A and 7 Direction-B capability rows | **5** | **6** (5 in the register + 1 in §2.4) |
| verifier (fourth input) | **4** control arms on one claim (1 negative + 3 positive), plus a structural scan with its own control and a natural experiment | **1** — and the only one refuting *another report* | **1** (efficacy of the proposed fix, blocked by the hook guard) |
| **Total** | **25 control-armed/confirmed** across ~53 enumerable capability rows | **15 refuted, 1 narrowed** | **16** |

### The refutation counts are the number that matters

**15 refuted.** Fourteen were the author's own draft killed before it reached
the file; **the fifteenth killed a claim that had already shipped in another
report** — and it was this synthesis's #1-ranked gap. Per this synthesis's own
standing rule, *zero refuted anywhere would mean the verifier never ran* — that
failure mode is absent here, in all four reports independently.

Two of the 15 were claims **this repo's own documentation asserted**, which is
the strongest available evidence the verification was real rather than
performed:

1. *"graphify's query is an unscored BFS."* — refuted by `serve.py:275 _compute_idf` called from `_score_query` at `:468`. Close to how `mise.toml` and `CLAUDE.md` described it.
2. *"graphify's `affected` is single-seed only; it has no change-set blast radius."* — refuted by `prs.py:252 compute_pr_impact(files, G)` plus the `list_prs`/`get_pr_impact`/`triage_prs` MCP tools.

Two structural lessons from the refutation set, both already in this repo's
rules and both re-earned here:

- **Three of mindwalk's five refutations were the same defect** — a 12-file,
  one-project sample reported as a property of the machine. `isSidechain never
  true`, `agentId never present`, `ai-title dead` all reversed under a
  2,419-file scan. A display bound is a bound.
- **One CBM probe returned 0 for the test *and* its control** because zsh
  rejected an unquoted `--include=*.c` glob. A uniform negative is a broken
  probe, not a finding — it was correctly discarded rather than written up.
- **A control-armed grep still shipped a false headline (G1).** The arm proved
  the *file* was searchable; it never proved the *search term* was the word the
  tool uses. Armed and wrong is a real state, and it is the most dangerous one
  in this set, because the arm is what persuades a reviewer to stop checking.

### What the counts do not say

25 control-armed claims out of ~53 enumerable rows means **over half the
capability rows in these reports rest on a `file:line` citation without an
explicit control arm.** That is not a criticism — an armed probe for every row
would have cost more than the round had — but it bounds how hard any single
unarmed row should be leaned on.

**And the armed rows are not automatically safe.** G1 was armed, was in the
armed count, and was false. The distinguishing property of the probe that caught
it was not a better control arm — it was that it **ran the tool** instead of
searching its source. Of ~53 rows, exactly one was tested that way, and it
reversed. Nothing here establishes what the reversal rate would be for the other
52; the honest statement is that **it is unmeasured**, and that "graphify lacks
X" claims sourced to greps of graphify's source are the specific population at
risk.

---

## 6. What to do with this

Stated as a ranking of *changes to what a session can answer* per unit of work,
which is the only ordering that survives the caveats above:

1. **G1, the single extraction root** — `knowledge-base#101`. Now the top item, and it moved *up* precisely because the refutation shrank it: it is one line in `kb_setup.graph` plus a rebuild, not an upstream extractor feature, and it lights up a capability graphify **already has** and every other pinned source already enjoys (cognee: 10,099 test↔src edges; us: 0). Confirm with the direct arm the verifier could not run — after the change, re-run the crossing-edge scan and expect a non-zero count.
2. **G2, per-response staleness** — the data is already in our `graph.json`; only `serve.py` needs to read it. Best value-to-effort among the *additive* items, and the one place a peer design can be copied nearly verbatim (including its scope honesty and its degrade-to-nothing error handling).
3. **G9, both local defects** — a `--graph` flag on `kb-query` and a merge-time `repo` attribution fix. Small, and both were found *by* this round rather than proposed for it.
4. **G3, local-diff impact** — reuses the existing `compute_pr_impact`; wrapper-side only. Note it now shares a root with G1's residue: both want *diff → symbols*, which graphify does not ship (`affected --since` does not exist). One wrapper could serve both.
5. **G4, footprint capture** — headless, rc=0, one `kb_setup` module. Adopt only with both bounds stated aloud (workflow subagents invisible; the judge's spec is a 600-rune prefix).

Everything else is either infrastructure (G6, G7), or genuinely not worth it
here (G8, G10).

**A process note that outranks every item above.** The single most expensive
error in this set was not missing a capability — it was **attributing to a tool
a defect that lived in one line of our own config**, with a control-armed grep
standing behind it. The cheap guard is now known and costs one command: before
writing "graphify cannot X", **run the graphify command that would do X**. That
is the arm that reversed G1, and it is the arm ~52 of ~53 rows here never got.

**Neither CBM nor CRG is a replacement.** Both are structurally unable to hold
the prose corpus that is this repo's reason to exist — CBM by exclusion list,
CRG by having no fetch path at all. **mindwalk is not a replacement either, and
not a competitor**: it answers a question none of the other three can, on a
surface none of them touch.

## GitHub repos touched

_This synthesis read no upstream source. The repos below are enumerated because
its three inputs rest on them, and the enumeration is this repo's source-backlog
index (`research-repo-enumeration.md`)._

- [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) — subject of input 1; pinned in `sources/`, `scope = study`.
- [tirth8205/code-review-graph](https://github.com/tirth8205/code-review-graph) — subject of input 2; pinned in `sources/`, `scope = study`.
- [cosmtrek/mindwalk](https://github.com/cosmtrek/mindwalk) — subject of input 3; pinned in `sources/`, `scope = study`; the only one built and executed.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the baseline in all three inputs, read as the **installed 0.9.31** tree.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo; the subject of G9 and of `knowledge-base#101`.
- [topoteretes/cognee](https://github.com/topoteretes/cognee) — already a pinned source; the natural experiment behind **G1** (single-run extraction → 10,099 test↔src edges).
- [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter) — vendored by CBM and used by CRG; read by input 1 only to establish it is third-party.
- [nomic-ai/nomic-embed-code](https://huggingface.co/nomic-ai/nomic-embed-code) (HuggingFace, not GitHub) — source model for CBM's compiled-in static vector table.

Referenced by the inputs but read by none of them, and no claim rests on them:
`tree_sitter_language_pack`, sentence-transformers, Voyage AI.
