---
source_url: "https://www.cerebras.ai/blog/how-we-built-our-knowledge-base"
type: article
title: "How We Built Our Knowledge Base (Cerebras Knowledge)"
authors: "Isaac Tai, Daniel Kim, Mike Gao"
published: 2026-07-15
captured_at: 2026-07-24
provenance: primary
fetch_note: >-
  CORRECTED 2026-07-24. The canonical URL returns HTTP 500 to every non-browser
  client tried (graphify `add`, curl bare, curl browser-UA, host WebFetch) — an
  earlier pass concluded from that agreement that the page was "genuinely broken".
  WRONG: real Chrome (claude-in-chrome) renders it fine and returned the full body.
  The 500 is served to non-browser clients (UA/TLS-fingerprint/JS gating), not a
  server fault. LESSON: four fetchers agreeing does NOT make a control arm when they
  share a failure mode — non-browser HTTP is one route, not four. Escalate to a real
  browser before declaring a page dead.
---

# How We Built Our Knowledge Base — Cerebras

Employees ask the internal knowledge base **more than 15,000 questions every day**. It
became one of the most widely adopted internal tools at the company within 3 months of
launch, used by humans, automations, and agents.

Cerebras teams span data center operations, chip design, hardware, training, inference,
and cloud platform. With hundreds of new employees a year, channels filled with repeats
of "Where can I find X?", "Who is the expert in Y?", "What is Z?"

## Pipeline (top-level)

```
SOURCES (Slack · Wiki · Code · Incidents)
  → DISTILLATION (LLM extractors)
  → EMBEDDINGS (pgvector, 3072-dim, HNSW)
  → RETRIEVAL (six lists in parallel)
  → FUSION + RERANK (RRF k=60 → LLM rerank)
  → SYNTHESIS (answer + citations)
```

## Meeting data where it lives

The recurring "brilliant fix" of recording everything in one platform — the single
source of truth — "rarely works in practice." Information is generated wherever it is
convenient: suggested edits in a doc, threads in Slack, code references in GitHub,
status metadata in Jira. Those platforms are tailor-made for their domains. "Discussing
a pull request in Google Docs would be a terrible experience."

So the system was designed to require **minimal change to existing behavior**: extract
from each platform directly rather than migrating data.

## Anatomy — three things

1. A platform for collecting and storing internal data.
2. A platform for querying that data.
3. A layer enforcing **authentication and authorization, with auditing and analytics**.

At the core is **a single Postgres table** holding embeddings, raw summaries, and
metadata from many sources. Every source — Slack threads to netlists — lands in the same
embeddings table and is immediately queryable through the same interface:

```
SLACK · WIKI/CONFLUENCE · CODE REPOS · NETLISTS · PRM DOCS · CUSTOM DATABASES
  → ONE EMBEDDINGS TABLE (document · embedding · metadata · source + timestamps)
  → QUERY (MCP · Web UI · Agents)
ONE CONNECTOR PER SOURCE
```

Each data source defines what the data is, how to connect, and how often to fetch. Each
embedding row follows the same interface regardless of origin.

## Slack — the most important source

Slack is where the most up-to-date engineering discussion happens. Initial testing showed
**simple embeddings over raw text were insufficient; vector search alone was inadequate**.

Challenges named:
- Information density varies enormously ("hey yeah sure mike" vs. a kernel explanation).
- Shorter messages frequently beat longer, more detailed ones in cosine similarity.
- A message's meaning often depends on surrounding conversation.

### Hybrid retrieval — four complementary scorers

- **Full-text search** catches exact tokens embeddings blur: error strings, flag names,
  host names. A pasted literal error is almost always the best evidence, and no amount of
  semantic similarity should outrank it.
- **Embedding search** catches paraphrase — "restore hangs after manifest load" vs.
  "checkpoint stalls on the NFS mount" share no vocabulary.
- **Inverse document frequency** separates signal from filler. A short message built on a
  rare token deserves to rank; "sounds good, thanks!" scores near zero once term rarity
  is applied.
- **Age decay** encodes that Slack answers expire. When relevance is otherwise equal, the
  newer thread wins.

"No single scorer is trusted on its own." Each produces its own ranked view, fused at
query time.

### Socket Mode ingestion

A Slack bot runs in **Socket Mode** — Slack pushes every message event over a persistent
WebSocket, giving real-time updates without polling and burning Web API rate limits.
Events are acknowledged immediately and **deduplicated by stable event ID**.

The ingest consumer does not save a message in isolation: it resolves the thread the
message belongs to, **re-fetches the entire conversation** (parent + every reply), and
writes the whole thread back **as one row**. So stored content, participant list, and
last-activity timestamp always reflect the complete conversation.

**Every Slack channel is its own data source**, giving fine-grained freshness tuning (a
busy incident channel can be ingested more frequently).

### Distillation — embed the artifact, not the transcript

Raw Slack text is keyword-searchable immediately via a Postgres **full-text (GIN) index**.
For vector search, an LLM extracts structured data from the full thread:

- A one-line **question** an engineer would actually search for.
- A short **summary**.
- The **resolution**.
- The **systems and code references** mentioned.

These are embedded and written to the shared table. **The original transcript is not
embedded directly** — "accuracy increased significantly when the thread was normalized
into a consistent format." The extra metadata also gives the semantic match more signal.

### Bursting — rescuing signal inside long threads

Important messages inside long threads were not always represented in the thread-level
summary. A **burst** is a run of consecutive messages from the same author, embedded
**with the thread topic prepended as context** (contextual retrieval), so an answer
living in one tangent message stays findable.

Each burst must clear a weighted threshold before being embedded:
- Contains a relatively rare token — **IDF ≥ 4.0**.
- Combined burst is at least **200 characters**.
- One or more messages carry **reactions** (social boost).

## Code repositories

The team debated whether embedding code was necessary at all — "grep is all you need"
felt right in the Claude Code era. After industry conversations and reading Cursor's
findings on semantic search in large codebases, they tried it. Repos are large: some
exceed **40 GB**.

**CocoIndex** (open-source document-embedding framework specializing in codebases) does
the work. Code is split using **language-specific regex boundaries ordered coarse to
fine**: try classes first; if a chunk is still too large, fall back to method boundaries,
then smaller blocks. **A single file may generate multiple embeddings at different levels
of specificity** (file-level and function-level).

CocoIndex tracks sync metadata in Postgres. On each commit it **re-embeds only the
changed chunks** rather than recomputing the repository — helped by sync state and
embedding store living in the same database.

As codebases grew, **repository onboarding moved into config files teams submit
themselves**, including path-level allowlists and denylists.

## Custom data sources — plugin scripts

Teams with their own databases did not want to migrate data just to participate. Custom
sources are **plugin scripts**: a team opens a PR with a small Python module that reads
its system and emits rows shaped like the embeddings table, plus a data-source entry. As
long as it writes the shared schema, the rest of the stack works unchanged.

## Planning and tool fan-out

Every query first runs a **short planning pass** where an LLM decides which tools and
data sources matter. The main tools:

- `subsystem_index` — per-file LLM summaries.
- `search` — unified vector pipeline across Slack, wiki, code and other sources, merged
  and reranked internally.
- `search_slack` — direct Slack retrieval.
- `search_code` — ripgrep over source repositories.
- `recent_prs` — recent pull requests relevant to the question.
- `who_knows` — people with demonstrated expertise on a topic.

The planner works over **a compact description of what is indexed**: which projects
exist, which sources are in each, and what each source is good at answering. It emits
tool selections the executor **fans out in parallel**, normalizes into a common evidence
format, and passes to a final synthesis LLM.

## Reranking

A document can surface high merely by sharing vocabulary while answering a different
question. Before reranking, incompatible result lists are combined with **reciprocal rank
fusion (RRF)**: for every document add `weight / (60 + rank)` for each list it appears
in — **default weight 1.0, smoothing constant k = 60**.

The smoothing constant "makes consensus matter more than a single strong vote": a
document near the top across several retrievers beats one ranked first in only one.

Then: merge duplicate chunks back to one source, **cap how many results each file can
contribute**, ending with a more diverse **top twenty**. Those go with the original query
to a **small reranker model** scoring each **0–10**; keep the **top ten**.

**Context expansion after ranking:** once ranking is final, context is added back to the
winners — e.g. matching a wiki section pulls in the **two neighboring sections** so the
heading, preconditions and caveats that chunking split apart are not lost.

So `search` outputs "a rich packet of evidence: results fused from different retrievers,
deduplicated at the source level, reranked against the actual question, and only then
expanded with surrounding context."

## MCP — primitives, not an answer endpoint

The MCP integration exposes **retrieval building blocks as direct tools** rather than
hiding them behind one "answer this question" endpoint. The tools are "intentionally
simple and as LLM-free as possible" so clients query them quickly and cheaply.

Each MCP tool maps to one retrieval primitive (`search_slack`, `search_code`, `search`,
`who_knows`). Inputs and outputs are narrow, structured and stable — callable from any
client or agent without embedding orchestration logic in the tool.

**Claude Code, or any MCP-compatible agent, becomes the orchestration engine.** It
decides which tools to call, in what order, and how to assemble results. The retrieval
layer does not depend on those LLM decisions to serve requests.

## Web UI — the pipeline runs server-side

The same tools exist, connected to a complete pipeline that runs end to end. The UI agent
owns planner → executor → synthesis:

- **Planner**: lightweight LLM pass inspects query + active project, chooses tools.
- **Executor**: fans tool calls out in parallel, normalizes results into a shared evidence
  schema with scores, recency, and source hints.
- **Synthesis**: final LLM pass produces the answer with citations, caveats, and
  cross-source synthesis.

MCP clients can recreate the same pattern explicitly.

## Organization — projects and scoped search

As the corpus grew, "search everything everywhere" stopped being useful. Compiler
engineers did not want infrastructure runbooks in results, and vice versa.

A **project** is a named bundle of data sources: specific Slack channels, code repos,
internal databases, document spaces. Projects are intentionally lightweight — the same
source (a shared incidents channel, a central platform repo) can be **referenced by
multiple projects instead of duplicated**.

During onboarding users select or create a **default project** matching how they work
(ML training infra, Compiler, Data Center Ops). It is stored on the user profile and
**scopes queries automatically**, so a new engineer gets high-signal answers without
first learning which channels/repos/spaces matter.

## Final thoughts (theirs)

"The knowledge base works because it meets people where the information already lives,
instead of forcing everything into one rigid system."

## References cited by the article

1. Malkov & Yashunin, *HNSW* — arXiv:1603.09320 / IEEE TPAMI 2018.
2. Anthropic, *Introducing Contextual Retrieval*, 2024.
3. Cormack, Clarke & Büttcher, *Reciprocal Rank Fusion…*, SIGIR 2009.
4. Li et al., *Search-o1: Agentic Search-Enhanced Large Reasoning Models*, arXiv:2501.05366.
5. Anthropic, *Code Execution with MCP*, 2025.
6. Liu et al., *Lost in the Middle*, arXiv:2307.03172, 2023.
7. Anthropic, *Use XML Tags*.
8. Salesforce/Slack Engineering, *How Slack AI Processes Billions of Messages*.
9. *Improving Agents, Best Nested Data Format*.
10. Cursor, *Improving Agent with Semantic Search*, 2025.
