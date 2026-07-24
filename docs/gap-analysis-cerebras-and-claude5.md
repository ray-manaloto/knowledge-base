# Gap analysis: Cerebras Knowledge vs. this KB — and what Claude-5 context engineering changes for the orchestrator

Sources ingested 2026-07-24 as registry #57–60 (`sources/REGISTRY.md`), merged as
`sources/extractions/context-engineering-kb-arch-docs.json` (119 nodes / 181 edges).

---

## Part 1 — Cerebras Knowledge vs. this KB

### The finding that frames everything

While verifying this very ingestion, the KB failed a retrieval test **on its own new
content**:

- 119 prose nodes merged. **Control-armed: 119/119 present in `graph.json` by exact id.**
- Two on-topic queries (`"context engineering … progressive disclosure"`,
  `"hybrid retrieval reciprocal rank fusion reranker age decay thread distillation"`)
  returned **~43 code symbols** — `distill.py`, `HybridRetriever`, `fusion.py` from
  cognee/deerflow/pensyve — and **zero** of the 119 new nodes.

Ingestion is not the bottleneck. **Retrieval is.** That is precisely the problem the
Cerebras article is about: *"we quickly realized that vector search alone was
insufficient."* We are a step behind that — we have neither a vector scorer nor a tuned
lexical one.

### Architecture diff

| Dimension | Cerebras Knowledge | This KB (graphify) | Verdict |
|---|---|---|---|
| **Store** | One Postgres table (document, embedding, metadata, source+timestamps); pgvector 3072-dim, HNSW | One `graph.json` (node-link), 128k nodes / 299k edges. No vector store | **Gap** |
| **Ingest interface** | One connector per source; uniform row schema; teams add connectors by PR (Python plugin) | Repo manifest (AST) or extraction chunk `{nodes,edges}`; uniform schema; contributor-extensible | **Parity** |
| **Code ingestion** | CocoIndex, language-aware recursive chunking (class→method→block), multi-level per-file embeddings, incremental re-embed on commit | AST extraction, free, deterministic, SHA-pinned | **We lead on cost**; they lead on incrementality |
| **Prose handling** | LLM distills thread → question/summary/resolution/systems; embeds the **artifact, not the transcript**; bursting (IDF≥4.0, ≥200 chars, reactions) for sub-thread signal | Host-agent extraction → typed `{nodes,edges}` semantic graph | **We lead** — typed relations beat a 4-field summary blob |
| **Freshness** | Per-channel cadence; Slack Socket Mode real-time push; incremental re-embed per commit | Manifest SHA pin; manual `kb-update`; ">1 month" refetch policy for docs | **Gap** — pull-only, human-initiated |
| **Retrieval scoring** | Four scorers in parallel — full-text (exact tokens), embedding (paraphrase), IDF (rarity), age decay (recency). *"No single scorer is trusted on its own."* | One path, no scoring | **THE gap** (demonstrated above) |
| **Fusion + rank** | RRF `weight/(60+rank)`, k=60 across six lists → dedupe → per-file cap → top 20 → 0–10 reranker → top 10 | None; budget-truncated node list | **Gap** |
| **Post-ranking** | Context expansion — pull the two neighbouring sections so headings/preconditions/caveats survive chunking | `path`/`explain` can walk relations, but not wired into query output | **Partial** — our edges are a *better* substrate than section adjacency |
| **Query planning** | Planner LLM selects tools; executor fans out in parallel; synthesis LLM answers **with citations** | Single `kb-query`; the agent picks tools by hand | **Gap** |
| **Scoping** | `projects` = named bundles of sources; per-user default scopes every query automatically | None — every query hits all 128k nodes across ~40 sources | **Gap** (root cause of the failure above) |
| **Agent interface** | MCP exposes **LLM-free retrieval primitives**; *"Claude Code becomes the orchestration engine"* | `mise run kb-serve` — read-only MCP pinned to the graph | **Parity** — their stated end-state *is* our architecture |
| **Self-learning** | Analytics + auditing; no described mechanism for the KB to learn from query outcomes | `kb-remember` → `kb-reflect` → `LESSONS.md` + learning overlay | **We lead** |
| **AuthZ/audit** | AuthN/AuthZ layer with auditing and analytics | Single-user local repo | N/A for our threat model |
| **Scale** | 15,000 questions/day, 3 months post-launch | Single user, session-scoped | Different regime |

### What to add, ranked by leverage (not by glamour)

**P0 — Scoping (`projects`).** Cheapest fix, highest impact, no new infrastructure. Every
node already carries `source`. A `--source`/`--kind` filter (or "prose only" / "exclude
code AST") on `kb-query` would have fixed today's failure outright. Do this first.

**P1 — Lexical scorer with IDF.** Their lesson is vector-only fails; we have neither.
BM25/IDF over node labels + summaries beats today's behaviour immediately, and IDF
specifically kills the false neighbour that bit us (`distill.py` matching "distillation"
because the token is common in our corpus but the node is irrelevant).

**P2 — RRF fusion.** Once there are ≥2 scorers, RRF at k=60 is ~15 lines and is the
documented way to merge incompatible ranked lists. Their insight worth copying: the
smoothing constant *"makes consensus matter more than a single strong vote."*

**P3 — Reranker.** Their 0–10 rerank over top-20. Note theirs is a **small** model; we
are Claude-only, so price this at `effort: low` or defer until P0–P2 are measured.

**P4 — Post-rank context expansion.** For us this is "pull 1-hop neighbours of each
winner" — strictly better than their section adjacency, because our edges are typed.

**P5 — Embeddings.** The most "obvious" and the one to do **last**. Needs a vector store,
an embedding model, and a re-embed pipeline. Marginal value is *lower for us* than for
them: they had no relational structure and embeddings were their only semantic bridge;
we already encode relations explicitly.

**P6 — Age decay.** They needed it because Slack rots. We already record `captured_at`
and have a freshness policy — but it is not a ranking signal.

### Where we already exceed them

- **Typed relations + communities.** Their store is flat rows plus vectors; `path` and
  `explain` answer "how does X relate to Y", which a rank-ordered row list cannot.
- **Free, deterministic code ingestion.** AST costs no tokens; CocoIndex embedding does.
- **Reproducibility.** SHA-pinned manifests and a deterministic rebuild from committed
  chunks. Theirs is a live mutable database with no described replay.
- **A self-improving loop.** `kb-remember`/`kb-reflect` turn each run's outcome into a
  durable lesson. Cerebras describes analytics, not learning.

### The uncomfortable summary

We optimised **ingestion breadth**; they optimised **retrieval quality**. We can ingest
119 perfect nodes and then fail to find them. Until P0–P2 land, adding more sources makes
retrieval *worse*, not better — every new source is more noise competing for an unscored,
unscoped top-N.

---

## Part 2 — What the Claude-5 articles change for the Fable-5 orchestrator

### 2a. Context engineering — the direct challenge to our doctrine

Anthropic removed **over 80% of Claude Code's system prompt** for Opus 5 / Fable 5 **with
no measurable loss** on coding evals. Six inversions:

| Then | Now |
|---|---|
| Give Claude rules | Let Claude use judgement |
| Give Claude examples | Design interfaces (expressive parameters, enums) |
| Put it all upfront | Progressive disclosure (skills, deferred tools via ToolSearch) |
| Repeat yourself | Simple tool descriptions (instructions live on the tool) |
| Memory in CLAUDE.md | Auto-memory |
| Simple specs | Rich references (artifacts, code, test suites, **rubrics**) |

The named failure mode is ours: *"several conflicting messages in a single request…
Claude must think more carefully about these overlapping and conflicting messages before
deciding what to do."* Our orchestrator session loads `orchestrator-routing/SKILL.md`
(126 lines of prescription) **plus** dotfiles `AGENTS.md` **plus** `.claude/CLAUDE.md`
**plus** ~15 eager rule files. That is exactly the overlapping-instruction surface the
article says to cut.

**But do not gut the doctrine.** The same article carves out: *"Avoid making them
overconstrained, **except in highly important areas**"* and *"It's best when skills encode
particular opinions… particular to you, your team, or product."* Correctness-critical
routing is a highly-important area, and our doctrine is exactly a team-specific opinion.

**The correct move is progressive disclosure, which the article recommends explicitly for
long skills:** keep the decision-relevant core in `SKILL.md` (the routing table, the
fallback ladder, the guardrails) and split the *rationale and evidence* into linked files
loaded on demand. Same doctrine, smaller always-on footprint.

Second consequence: **rubrics as references, driving verifier agents.** This names and
validates what the `brain/` vault gropes toward, and points at Managed-Agents rubrics with
a separate grader as the productised form.

### 2b. Verification loops — the taxonomy we were missing

The article gives four kickoff modes. We already operate all four but have never named
them, so we cannot reason about which tier a new check belongs in:

| Mode | Our instance |
|---|---|
| **Standalone** | `mise run lint` / `test` / `brain-audit` |
| **Embedded** | `brain-transcript-audit` on SessionEnd |
| **Chained** | `kb-ship` invoking its gates before opening the PR |
| **On every PR** | CI |

Two things to take:

- The **escalation signal** — *"you've outgrown standalone when you're running it after
  every change"* — is a concrete, testable rule for promoting a check a tier.
- **Chaining is how you add verification to a skill you cannot modify** (wrap it). That is
  the mechanism for putting a gate around the vendored plugin lanes.

Note the tension with the Opus-5 migration guidance (delete verification scaffolding —
Opus 5 over-verifies): these do not conflict. That guidance is about telling a model to
re-check **its own** output. Verification loops here are **deterministic, external checks**
and the doctrine's cross-vendor review is **an independent verifier**. Neither is
self-verification. Keep both.

### 2c. Models explained — the first quantified support for our whole framework

- **"Start with the most intelligent model and use effort to dial cost."** Cost-per-task
  is often **lower** for smarter models because they take fewer turns. Our doctrine
  already says "prefer a cheaper lane at higher effort over an expensive one at low
  effort" — the article's framing is compatible but sharper: start high, dial down.
- **The advisor number.** On SWE-bench Pro, **Sonnet 5 with a Fable 5 advisor lands within
  10% of Fable 5 at 63% of the price.** This is the first *measured* validation of the
  advisor/executor pattern the entire framework rests on — until now we had blog-post
  assertions. It also suggests a config we do not currently run: **Sonnet executor +
  Fable advisor**, rather than Fable architect + Sonnet-wrapped CLI lanes.
- **Sonnet is vendor-blessed for "high-volume sub-agents in multi-agent orchestration"** —
  which is exactly what `codex-implementer` (`model: sonnet`) is.
- **Opus vs Fable rule of thumb:** *"if your evals show Opus struggling, Fable is the
  answer; if Opus already clears the bar, its speed and price make it the better choice."*

That last line **answers the architect-tier question directly, and unfavourably for us**:
the decision is supposed to be **eval-driven**. We have no orchestrator evals. The honest
answer to "Fable 5 or Opus 5 as architect" is *we cannot know yet*.

### The convergent conclusion

All three articles point the same way: **stop adding prescription; start adding
measurement.** Build rubrics and evals, then let the model judge. Our framework is heavy
on doctrine and light on measurement — and the `brain/` vault, which is the seed of
measurement, records *our own* verdicts rather than scored evals.

That is the same shape as the Part 1 finding: we have over-invested in **inputs**
(sources, rules) and under-invested in **scoring** (retrieval quality, eval-driven
routing). One diagnosis, two systems.

## GitHub repos touched

_None._ All four sources are articles; no repository source was read for this analysis.
