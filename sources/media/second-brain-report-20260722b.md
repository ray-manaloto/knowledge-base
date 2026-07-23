# Research — graphify as a persistent "second brain" for the Fable-5 orchestrator (2026-07-22)

**Deliverable arc:** RESEARCH → DESIGN → PROTOTYPE (multi-session, Ray). **This report closes the
RESEARCH phase** and hands a recommended integration direction + open questions to DESIGN.

> **⚠️ Read the [Addendum (dogfood pass)](#addendum--dogfood-pass-2026-07-22-corrects-the-record) at the
> end first.** Ray asked whether the research used graphify's own KB-graph data on Obsidian/second-brain
> sources. It did **not** — and querying that data afterward surfaced a **named, documented, already-built
> pattern** (graphify + Obsidian as Claude memory) with **two working reference repos**, which **partially
> refutes the "novel whitespace" claim below**. The addendum corrects it.

**Method:** 4 parallel research threads (general-purpose agents, web + local + installed-source) +
1 Opus verification pass that independently re-probed every load-bearing claim with control arms.
Full per-thread reports (verbatim, with command output) in `agents/`. graphify **0.9.23** installed;
the sibling **knowledge-base** repo already runs graphify as a substrate; the Fable-5 orchestrator is
**adopted** (Claude architect → codex/antigravity lanes → Opus fallback) and its `orchestrator-routing`
skill already prescribes *"ground every decision in the KB graph first."*

---

## The answer, in one paragraph

**Yes — graphify can be the persistent second brain, and most of the machinery already exists.** A
git-tracked **plain-markdown vault** (edited through **Obsidian**, but the source of truth is the
`.md` files) is ingested by **`graphify update`** into a knowledge graph *for free* — wikilinks become
real graph edges, zero LLM tokens. The Fable-5 architect queries that graph at decision time via a
**deterministic CLI shell-out** (`mise run kb-query`, 0 schema tax, sub-second on our graph size), and
writes outcomes back through the **already-built, collision-safe** `kb-remember`/`kb-reflect` learning
overlay. The three things that are genuinely *new work* — and therefore the DESIGN phase — are: (1) a
paid-semantic-enrichment cadence, (2) the GraphRAG "global search / community summaries" capability
graphify lacks, and (3) whether one graph can meaningfully span both the PKM vault *and* the codebase.
Nobody has published a drop-in for "a knowledge graph grounds an AI orchestrator's routing decisions" —
this is novel ground, so we borrow the *memory* patterns (Reflexion/ExpeL/Voyager, GraphRAG) and invent
the *routing-grounding* seam ourselves.

---

## Verified findings (every load-bearing claim was independently re-probed)

| # | Claim | Verdict | What the control arm showed |
|---|---|---|---|
| A | `graphify update <vault>` ingests a markdown vault's `[[wikilinks]]` as real EXTRACTED edges, FREE (no LLM/key, rc=0); the plain `graphify <path>` build routes `.md` to a paid semantic pass that writes **nothing** on failure | **CONFIRMED** (all 4 sub-claims, both gotchas) | Fresh synthetic vault, clean env: `update .` → rc=0, 9 nodes/9 edges, `Token cost: 0 input · 0 output`. Frontmatter `tags:`/`aliases:` → 0 nodes. Bare cross-folder `[[Gamma]]` → no edge; path-qualified `[[sub/gamma#h]]` → edge (positive control: bare *sibling* wikilinks DO resolve). Plain build, no key → error, no `graph.json` written at all. |
| D | graphify has **no** per-community LLM summaries and **no** map-reduce "global search" (the biggest gap vs mature GraphRAG) | **CONFIRMED** | Community prompt asks for a "concise 2-5 word plain-language **name**… no prose." `global.?search`/`map.?reduce`/`community.?report` grep = 0 (control-armed: `community`=19, `god`=22, `louvain\|leiden`=5 files — grep works). query/path/explain are local BFS/DFS only. |
| C | Logseq is moving to a SQLite DB; its markdown-on-disk path is now feature-frozen → a dead-end for a file-ingest design | **CONFIRMED (date nuance)** | Logseq's own split announcement: OG (markdown) = *"maintenance… no new features"*; DB = SQLite; markdown-in-DB *"still researching."* **Nuance:** announcement is **April 2026**, not "2026-07-13"; OG is *maintained-but-frozen* (security/Electron), not dead. Conclusion holds: don't build a *new* foundation on Logseq markdown. |
| B | `kb-query` is deterministic + 0 LLM tokens; `graph.json` written atomically but **no lock** → concurrent writes lose updates | **NUANCED** | Determinism ✓ (byte-identical twice, control-armed). Atomic `os.replace` ✓. **"No flock" REFUTED:** `watch.py` holds a per-repo `.rebuild.lock` `fcntl.flock` guarding the `update`/`watch`/hook path (#1059) → concurrent `graphify update` is **serialized + change-queued, NOT a lost update**. Lost-update risk survives **only** for `merge-graphs` / full-build export (bare `write_json_atomic`) and mixed update+merge. **The concurrency constraint is looser than the KB memory warned.** |

---

## The recommended integration design (input to the DESIGN phase — not yet final)

A layered "second brain" that reuses what's live and adds only what's missing:

### 1. PKM front-end → **Obsidian**, but the truth is plain `.md` in git
- **Winner: Obsidian** — free for personal use, huge ecosystem, and (uniquely) graphify has native
  round-trip (`--obsidian`) and a 2026 Local REST API + MCP for AI write-back. **But the decision is
  cheaply reversible** because the on-disk source of truth is plain markdown: Obsidian, **Foam** (MIT,
  VS Code — on-disk *identical*), and a bare markdown vault are swappable editing layers over the same
  files. Recommendation: adopt Obsidian for the human, commit to *no Obsidian-proprietary features in
  the source of truth* so Foam/plain-md stay drop-in.
- **Vault conventions forced by Thread A's caveats** (these are design constraints, not bugs):
  - Use **path-qualified wikilinks** (`[[sub/Note]]`) or keep linked notes as **siblings** — graphify
    resolves sibling/relative only, not Obsidian's vault-wide name resolution.
  - **Don't encode structure in frontmatter `tags:`** — graphify's free structural pass ignores them.
    Put taxonomy in wikilinks/headings, or accept it only surfaces via the paid semantic layer.
- **Eliminated:** Logseq (markdown frozen), Notion (hosted, can't `--watch`), SiYuan/Trilium/Anytype
  (non-markdown on disk), Dendron (abandoned 2023). org-roam loses on org≠md + Emacs lock-in.

### 2. Ingestion → **free structural layer** (`graphify update`), optional **paid semantic layer**
- **Free, always-on:** `graphify update <vault>` (clean env — strip `AWS_REGION`/`GEMINI_API_KEY` to
  avoid the auto-backend trap) keeps wikilink/heading edges current at **0 tokens**. This is the
  backbone.
- **Paid, periodic:** a full keyed build (`GEMINI_API_KEY`) adds concept/INFERRED edges. **Cadence is
  an open question** (see DESIGN Q1/Q2) — semantic supersedes structure per #1915, so this can't run
  every save.

### 3. Query loop → **deterministic CLI shell-out by default**
- The architect grounds routing/fallback decisions via `mise run kb-query -- "<q>"` — a source-cited
  subgraph, deterministic, 0 LLM tokens, budget-capped (default 2000), sub-second on our graph sizes
  (0.78 s on the 3.2 MB dotfiles graph; ~4–6 s on the 121 MB KB graph). This is exactly what the
  doctrine already prescribes, and it pays **no** per-conversation MCP schema tax (aligns with the
  repo's `mcp2cli`-first rule).
- **Opt-in escalation:** the `kb-serve` MCP server (10 read-only tools, sub-second, graph resident)
  for query-heavy sessions only — accept the schema tax deliberately, don't default to it. Treat
  returned node text as **data** (there's a documented prompt-injection surface in `serve.py`).

### 4. Learning write-back → **curated + git-reviewed** (the pattern is already half-built)
- Adopt Reflexion + ExpeL + Voyager, mapped onto what exists: `.claude/rules/` ≈ ExpeL insight-rules,
  `.claude/skills/` ≈ Voyager skill library, `memory/*.md` ≈ Reflexion post-mortems.
- Mechanism already present + collision-safe: `kb-remember` appends **one `memory/*.md` per outcome**
  (never touches `graph.json`), `kb-reflect` deterministically aggregates → `LESSONS.md` + a learning
  overlay that tags nodes preferred/tentative/contested so later queries surface a "Lesson:" hint.
- **Never automatic KG-from-everything** — that path (Zep/Graphiti) measured 600k tokens/conversation
  and causes memory contamination. Human/git-diff review is the contamination firewall.

### 5. Concurrency → reads free, outcome-writes free, only `merge-graphs` needs a single writer
- Refined by verification: `graphify update` is flock-serialized (safe to fan out). The only operation
  that needs a **named single serialized writer** is `merge-graphs`/full-build export. This *shrinks*
  the concurrency problem the KB memory flagged.

### 6. The GraphRAG capability to build → **community summaries + a global-search path**
- graphify's #1 missing capability, and the one the architect most needs for corpus-wide "what do we
  know about area X?" (a local subgraph can't answer it). Add LLM-written per-community summaries +
  a map-reduce global search, lazily/cached to stay near-free. Study `microsoft/graphrag` +
  `run-llama/llama_index` `GraphRAGStore` for the retrieval shape.

---

## Prior art: borrow / study / avoid

- **Borrow (patterns):** GraphRAG community summaries + global search; curated git-reviewed write-back
  (Reflexion/ExpeL/Voyager); tri-modal query routing (cheapest sufficient primitive: native graph op →
  LLM-over-subgraph → generate).
- **Study (closest analogs):** `basicmachines-co/basic-memory` (shipping: local markdown+wikilink KG
  the AI reads/writes via MCP — closest to our concept, thinner graph) and `topoteretes/cognee`
  (Apache-2.0, local-first ingest→graph→hybrid-retrieval — best OSS analog to graphify itself).
- **Avoid:** hosted memory services (Zep retired self-host; Mem0 managed-first) — violate local-first;
  full agent runtimes as "memory" (Letta/MemGPT want to *be* the orchestrator); automatic
  extract-KG-from-everything; and the "a vault alone is memory" fallacy (the retrieval/graph layer is
  the whole point).
- **Novel whitespace (no drop-in prior art):** KG-grounded *orchestration routing*; curated git-native
  graph write-back; one graph spanning a hand-written PKM vault **and** the codebase. Opportunity and
  risk both — prototype before committing.

---

## Open questions the DESIGN phase MUST resolve

1. **Two-layer refresh cadence (sharpest).** Per #1915, once a doc gets a paid semantic build, `update`
   won't re-scan its structure (semantic supersedes AST) — structure freezes until the next keyed full
   build. What triggers a paid rebuild, and how do the free structural layer and paid semantic layer
   coexist without one clobbering the other?
2. **Full-semantic-build cost is UNMEASURED on a real vault.** Every thread used 4-note toy vaults or
   the pre-built 121 MB graph. Get a real token/$/latency number over a representative vault before
   committing to *any* paid layer (including the GraphRAG global-search fill).
3. **Does "one graph spanning vault + codebase" actually connect?** Cross-doc INFERRED edges are thin
   (Thread B: `path` across two docs returned "No path found"); a naive merge risks two weakly-connected
   islands. Needs a real cross-corpus merge prototype before it's designed in.
4. **Where does the vault live + who is the single graph-writer?** New repo vs KB repo vs dotfiles.
   Given the refined concurrency model, DESIGN must name the serialized writer for any `merge-graphs`
   and decide vault-as-merge-input vs its own project graph.

**Recommended first PROTOTYPE (answers Q2+Q3 cheaply):** stand up a small real markdown vault (10–30
notes of actual project knowledge, path-qualified wikilinks), `graphify update` it (free) → inspect the
structural graph; then one keyed full build → **measure** the token cost and inspect whether concept
edges connect vault notes to the codebase graph via a `merge-graphs`. That single prototype retires the
two most uncertain open questions before any deeper design commitment.

---

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — installed 0.9.23 source, the authoritative behavior for ingestion (`extractors/markdown.py`, `detect.py`, `extract.py`), query/path/explain engine, `export.py`/`paths.write_json_atomic`, `watch.py` `_rebuild_lock`/`.rebuild.lock` (#1059), `cache.py`, `cli.py`, `llm.py` label prompt, `cluster.py`, `global_graph.py`, `report.py`, `serve.py` MCP tools — control-armed against synthetic vaults.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the KB substrate: `CLAUDE.md`, `mise.toml` kb-* tasks, `docs/graphify-reference.md`, `orchestrator-routing` skill, live 121 MB `graphify-out/graph.json`, `memory/` work-memory, `kb-remember`/`kb-reflect` overlay, multi-repo `merge-graphs` topology.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — `python/src/dotfiles_setup/graphify.py` (#313 deterministic query read-path), `graphify-query` mise task, 3.2 MB dotfiles graph.
- [microsoft/graphrag](https://github.com/microsoft/graphrag) — hierarchical community summaries + local/global search (the capability graphify lacks).
- [run-llama/llama_index](https://github.com/run-llama/llama_index) — `GraphRAGStore` community-summary retrieval implementation.
- [basicmachines-co/basic-memory](https://github.com/basicmachines-co/basic-memory) — closest shipping analog: local markdown+wikilink KG, Claude reads/writes via MCP.
- [topoteretes/cognee](https://github.com/topoteretes/cognee) — Apache-2.0 local-first ingest→graph→hybrid-retrieval; best OSS analog to graphify.
- [getzep/graphiti](https://github.com/getzep/graphiti) — temporal KG memory (bi-temporal fact invalidation); Zep retired self-host (avoid).
- [mem0ai/mem0](https://github.com/mem0ai/mem0) — bolt-on memory (vector-first, optional graph); managed-first (avoid as dep).
- [letta-ai/letta](https://github.com/letta-ai/letta) — MemGPT runtime; wants to be the orchestrator (avoid).
- [agiresearch/a-mem](https://github.com/agiresearch/a-mem) — Zettelkasten agentic memory w/ evolving-note write-back (NeurIPS 2025).
- [langchain-ai/langmem](https://github.com/langchain-ai/langmem) — long-term memory (facts+semantic, no graph).
- [neuml/txtai](https://github.com/neuml/txtai) — embeddings DB with optional semantic-graph layer.
- [khoj-ai/khoj](https://github.com/khoj-ai/khoj) — self-hostable AI second brain over a vault (vector RAG, not graph).
- [foambubble/foam](https://github.com/foambubble/foam) — MIT VS Code md/wikilink PKM; the open-source escape hatch, on-disk identical to Obsidian.
- [coddingtonbear/obsidian-local-rest-api](https://github.com/coddingtonbear/obsidian-local-rest-api) — Obsidian REST API + built-in MCP (2026) for orchestrator write-back.
- [logseq/logseq](https://github.com/logseq/logseq) + [logseq/docs](https://github.com/logseq/docs) — OG(markdown, maintenance) vs DB(SQLite) split; `db-version.md` confirms DB direction. Eliminated as a *new* foundation.
- [siyuan-note/siyuan](https://github.com/siyuan-note/siyuan) — block-JSON `.sy` on disk (eliminated).
- [TriliumNext/Trilium](https://github.com/TriliumNext/Trilium) — SQLite HTML/JSON, md export-only (eliminated).
- [dendronhq/dendron](https://github.com/dendronhq/dendron) — dev stopped 2023 (eliminated).
- [org-roam/org-roam](https://github.com/org-roam/org-roam) — `.org` + SQLite backlink index, Emacs (off-stack).
- [jfcostello/AnyBlock-To-Markdown](https://github.com/jfcostello/AnyBlock-To-Markdown) — evidence Anytype exports are verbose JSON (eliminated).

---

## Addendum — dogfood pass (2026-07-22): corrects the record

**Why this exists:** Ray asked whether the four threads used graphify's *own* KB-graph data on the
Obsidian / second-brain sources. **They did not** — the sweep did fresh web + installed-source research;
Thread B queried the KB graph only for the orchestrator-routing doctrine. Querying the KB graph
afterward (`mise run kb-query` on the 121 MB graph) surfaced curated sources that were sitting unused —
and they change two conclusions. This is a real process gap: I researched "graphify as a second brain"
without querying the graphify second brain that already held sources on it.

### What the KB graph already knew

Two YouTube transcripts (ingested into the KB graph) describe **exactly this system, already built**:

- **`yt-rtutpoT4SYg.txt`** (Hyper Automation Labs) documents a **named loop**: **Capture → Map → Ask →
  Write-back** — "a second brain that maintains itself":
  1. **Capture** — `graphify add <url>` (fetch → `raw/` → wire into graph), or the agent clips a page
     to clean markdown with **Defuddle**.
  2. **Map updates itself** — `graphify --watch` rebuilds on file change, or a git post-commit hook
     redraws on every commit.
  3. **Ask the graph** — `graphify query` / shortest-path instead of re-reading files.
  4. **Write-back** — the agent writes what it learns back as proper notes with `[[wikilinks]]`.
  5. **Next rebuild** picks up those notes → the map grows. (This is precisely the write-back loop the
     main report derived from Reflexion/ExpeL/Voyager first principles — it already has a name.)
- The pairing is **two tools**: **graphify = "the map"** (`graphify export obsidian` turns the graph
  into a real Obsidian vault — one `.md`/concept, `[[wikilinks]]`, honesty tags, + a JSON Canvas), and
  **`kepano/obsidian-skills` = "the hands"** — the Obsidian CEO's (Steph Ango) official MIT agent skills
  that let an agent write valid Obsidian (Markdown, **Bases**, **JSON Canvas**, the **Obsidian CLI**
  100+ cmds, Defuddle). **This "hands" layer is the concrete write-back mechanism the main report
  glossed** — and it is explicitly cross-agent (Claude Code, Codex, OpenCode), which fits the
  cross-vendor orchestrator.
- **`yt-mHSOsy_usAg.txt`** contributes a "Brain First rule set in CLAUDE.md" + "Self-maintaining wiki"
  + "Five-rung search ladder" cluster — a complementary agent-memory discipline.

### Drop-in prior art — control-armed, CONFIRMED (this is the correction)

Thread D called "graphify graph as agent memory" **novel whitespace with no drop-in prior art.** That
is **REFUTED for the memory/second-brain layer.** Two working, popular reference implementations of the
*exact* graphify + Obsidian + Claude-Code pairing exist (both verified live via web search):

- **[lucasrosati/claude-code-memory-setup](https://github.com/lucasrosati/claude-code-memory-setup)** —
  "persistent memory, codebase knowledge graphs, chat-import pipeline"; a **centralized Obsidian vault
  as Claude's second brain**, Zettelkasten atomic notes, `permanent/` + `logs/` + `graphify/` dirs,
  session logs. A ready-made **vault template** that directly informs DESIGN open-question #4 (vault
  location + structure).
- **[albertludi/second-brain-claude](https://github.com/albertludi/second-brain-claude)** — "persistent,
  relational memory system for Claude Code using graphify and Obsidian." A second independent take.

**What stays genuinely novel** (narrowed, not eliminated): grounding an **orchestrator's ROUTING /
delegation decisions** (Fable-5 architect → codex/antigravity lanes) in the graph — *not* just Q&A or
session memory. Neither reference repo does cross-vendor orchestration-routing. So the second-brain
*foundation* is a solved, documented, forkable pattern; our delta is the **routing-grounding + cross-vendor
lanes** on top of it.

### Caveat (control-arm rule 6 — an inherited number is not a measurement)

The headline **"71.5× fewer tokens"** appears in the video, the Rosati README, and several Medium
reposts — it is an **unverified creator/vendor benchmark** (traces to graphify's own token-reduction
benchmark on a 52-file corpus), n=1, no independent control. **Do not bank it.** What is CONFIRMED is
the *existence and shape* of the pattern and the tools — not the multiplier. (Star counts likewise soft:
video "42k", web "~37k" for obsidian-skills — directionally "very popular," exact figure unverified.)

### How this changes DESIGN

1. **Start by evaluating/forking the two reference repos** (`use-tool-builtins` gate), not building the
   second-brain from scratch. Rosati's vault layout + chat-import pipeline is a concrete starting point.
2. **Adopt `kepano/obsidian-skills` as the write-back "hands"** — it's the MIT, cross-agent mechanism for
   valid Obsidian writes (Bases/Canvas/CLI). Re-run the Thread-A caveats against it (does its writer emit
   path-qualified wikilinks that graphify's sibling-only resolver will pick up?).
3. **Re-scope the novelty** to the orchestration-routing grounding — that is where the design effort and
   the genuine contribution live; the memory layer is largely assembly of existing parts.
4. **Ingest these sources into the research corpus** (they were in the KB graph but unread): the two YT
   transcripts + both reference repos. Next dogfood step: `graphify add` the two repos and re-query.

### Process lesson (recorded, not just noted)

A `probes-need-a-control-arm` cross-check failure of a new kind: the sweep never queried the **local
substrate that already indexed the answer.** Before declaring external "novel whitespace," query the
in-house graph first — it is the cheapest control arm and it was one command away. Folded into the
DESIGN handoff as a standing step.

## GitHub repos touched (addendum)

- [lucasrosati/claude-code-memory-setup](https://github.com/lucasrosati/claude-code-memory-setup) — drop-in prior art: graphify + Obsidian as Claude Code persistent memory (vault template, chat-import pipeline). CONFIRMED live.
- [albertludi/second-brain-claude](https://github.com/albertludi/second-brain-claude) — second independent graphify + Obsidian Claude-memory implementation. CONFIRMED live.
- [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) — "the hands": Obsidian CEO's MIT agent skills (Markdown/Bases/JSON Canvas/CLI/Defuddle), cross-agent. The write-back mechanism. CONFIRMED live (~37k★).
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — KB graph queried in the dogfood pass; sources `sources/media/yt-rtutpoT4SYg.txt` + `raw/video-map.txt` + graph nodes from `yt-mHSOsy_usAg`/`yt-22iy2mDFiF8` transcripts.
