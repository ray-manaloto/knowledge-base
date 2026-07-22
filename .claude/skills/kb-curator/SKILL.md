---
name: kb-curator
description: >-
  Automate adding a source to this knowledge-base graph and keep the corpus
  self-improving: register in the source backlog, ingest (code=AST free, or
  prose=host-agent), MERGE into the aggregate graph, re-cluster, label, and —
  ALWAYS — record work-memory (`graphify save-result`) and run `graphify reflect`
  so lessons compound across every ingestion. Use this whenever the user wants to
  add/ingest/extract a source into the KB (a GitHub repo, a docs URL or
  sitemap.xml, a PDF, a video/transcript, a blog/reddit thread), refresh an
  existing source, run reflection/LESSONS, or "teach the KB" something — even if
  they just paste a URL or say "add this to the graph" without naming the skill.
  Prefer graphify ingestion+extraction over raw web search: graphify fetches the
  URL itself, so the graph is the primary research surface.
---

# kb-curator — self-improving ingest → extract → reflect

You are the curator of a graphify knowledge graph that many Claude Code agents
query. Your job: take a new source from "I want this in the KB" to a merged,
clustered, labelled part of the aggregate graph — and leave the corpus a little
smarter each time by recording what you learned. **Read `docs/graphify-reference.md`
first** for the graphify mental model; this skill is the workflow on top of it.

Why the self-learning step is non-negotiable: a knowledge base that only grows
nodes but never records *how the last ingestion went* repeats every mistake.
`save-result` + `reflect` turn each run's outcome into a durable, graph-aware
lesson (`reflections/LESSONS.md` + the `.graphify_learning.json` overlay), which
`graphify explain`/`query` then surface to the next agent. That is the whole point.

## MANDATE — ingest every source THROUGH graphify (and its extensions)

**All ingestion goes through graphify's own tooling, never an ad-hoc fetch.** This is
enforced (KB repo + the consuming dotfiles repo). Entry points:
- **GitHub repo** → `graphify clone <url>` (or a `sources/<name>.manifest` + `kb-build`).
- **Any URL** (docs page, blog, article) → `graphify add <url>` — it fetches to `./raw`
  and updates the graph. `--author`/`--contributor` tag provenance.
- **Sitemap** → enumerate, then `graphify add` each on-topic page.
- **Video/YouTube** → `graphify add <url>` (downloads audio; whisper transcribes at
  extraction — needs ffmpeg, pinned).
- **Live PostgreSQL** → `graphify extract --postgres <DSN>`.

`curl`/WebFetch/manual vendoring are a **fallback ONLY** when graphify genuinely
cannot reach a source — and even then the content must be routed into the graph via
the extraction chunk, never left as a loose file. With no API key the *semantic*
extraction still falls to the host agent, but the FETCH + pipeline is graphify's.
Why: one ingestion path = uniform provenance (`source_url`/`captured_at`), the
freshness policy, and reproducibility. Reaching for `curl` first is the thing this
mandate exists to stop.

## The aggregate-graph model

The KB is MANY per-source graphs merged into one (`graph.json`), extended every
time a source lands. Each source is extracted into its own sub-graph, then
union-merged. **Cross-project dedup is disabled by design** — a `main` in repo A
is not repo B's — so merges never dedup across repos (`merge-graphs` for code;
`dedup=False` for the doc path). Do not fight this; it is correct.

## Pick the ingestion path by source type

| Source | Path | Cost |
|---|---|---|
| **GitHub repo** | add `sources/<name>.manifest` (url+ref+SHA); `mise run kb-build` clones + AST-extracts + merges | free (AST) |
| **Docs page / sitemap.xml** | parse the sitemap (use `advertools`/`usp` — do NOT hand-roll), fetch on-topic pages, host-agent prose-extract → chunk | tokens |
| **PDF / video / transcript / blog / forum** | vendor under `sources/media/`, host-agent prose-extract → `sources/extractions/<name>-docs.json` | tokens |
| **Any URL (quick)** | `mise run kb-add -- <url>` (graphify fetches → `./raw` → updates graph) | varies |

**Tier by relevance** (host-agent prose is token-costly): T1 = full semantic + code
for authoritative/on-topic sources; T2 = code-AST or README-only; T3 = register but
defer (live timelines → reach via a trend tool, not static ingest). Record the tier
in `sources/REGISTRY.md`.

## The workflow (every ingestion)

1. **Register.** Add/append a row in `sources/REGISTRY.md` (kind, tier, status) so
   nothing is lost. The registry IS the backlog the KB works down over time.
2. **Ingest.**
   - Repo → write the manifest, `mise run kb-build`. A prose-only repo (no code)
     is skipped without aborting — its value comes from the prose step, not AST.
   - Prose → dispatch `general-purpose` subagent(s) that READ the source and emit
     graphify node/edge JSON (there is no API key; host-agent extraction is the
     no-key prose path). Instruct them to write incrementally, not at the end — an
     agent that dies at source 13 of 20 should leave 13 (see `agent-report-persistence`).
     Commit the chunk to `sources/extractions/<name>-docs.json`.
3. **Merge + cluster.** `kb-build` merges and re-clusters. Louvain renumbers
   communities globally and non-deterministically → **every merge staleifies labels**.
4. **Label.** `graphify label <path> --missing-only` names new/placeholder
   communities (host-agent when no key). Unlabeled communities cripple the wiki.
5. **SELF-LEARN (do not skip).** Record the outcome, then reflect:
   ```bash
   mise run kb-remember -- --question "Q" --answer "A" --nodes N1 N2 --outcome useful|dead_end|corrected
   mise run kb-reflect                 # aggregates memory/ -> reflections/LESSONS.md + overlay
   ```
   Record the load-bearing thing you learned (a gotcha, a working command, a dead
   end), citing the graph nodes it touched. `corrected` + `--correction` when you
   fixed a wrong prior belief. This is what makes the KB self-improve per run.
6. **Verify.** `mise run kb-query -- "<something the new source should answer>"`
   returns cross-source hits; `mise run lint && mise run test` green.

## Gotchas (hard-won — see LESSONS.md as it grows)

- **`graphify extract --code-only` exits non-zero on a no-code repo.** `kb-build`
  tolerates it (skips, keeps the pin). Never treat a prose-only repo as fatal.
- **Never `graphify hook install`** (#857 shared-manifest skip) and **never bare
  `graphify install`** (mutates `~/.claude`) — project-scoped only.
- **Python 3.14**: no Leiden (Louvain fallback, accepted) and `export svg` needs a
  scipy inject (`mise run kb-ensure-deps`).
- **`graphify add <youtube>`** downloads audio but transcription happens at
  extraction (whisper needs ffmpeg, pinned in `mise.toml`).
- Version-gated (0.9.24+, not in installed 0.9.23): `reflect --if-stale`,
  `extract --dedup-llm`. Bump the pin before relying on them.

## Improving THIS skill (skill-creator loop)

This skill was authored with the skill-creator methodology and is meant to be
measured and improved, not frozen. When ingestion behavior drifts or a new source
type recurs, run the skill-creator eval loop: draft/adjust test prompts in
`evals/evals.json`, run with-skill vs baseline, review, and rewrite. Generalize
from feedback — bundle a repeated helper into `scripts/` rather than hard-coding a
one-off. Keep the description "pushy" so agents actually trigger it on a bare URL.
