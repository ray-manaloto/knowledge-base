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

## TWO HARD MANDATES (Ray, 2026-07-22 — machine-enforced)

**1. NEVER run graphify by hand — every graphify operation is a mise task.**
Do NOT type `graphify …`, `_merge_docs.py`, or run graphify's bundled interpreter
directly. Drive it through the task; the PreToolUse guard (`kb_setup.hook_guard`,
wired in `.claude/settings.json`) DENIES raw graphify calls and redirects here.
The task map:

| Operation | mise task | not the raw command |
|---|---|---|
| add a URL (page/blog/article/video) | `mise run kb-add -- <url> [--author NAME]` | ~~`graphify add`~~ |
| rebuild from committed inputs | `mise run kb-build` | ~~`graphify extract`/`merge-graphs`~~ |
| advance a repo source | `mise run kb-update -- <name>` | ~~`graphify update`~~ |
| merge one doc chunk | `mise run kb-merge -- <chunk.json> [root]` | ~~`_merge_docs.py`~~ |
| (re)label communities | `mise run kb-label` | ~~`graphify label`~~ |
| transcribe local audio | `mise run kb-transcribe -- <audio>` | ~~`graphify.transcribe`~~ |
| query | `mise run kb-query -- "<q>"` | ~~`graphify query`~~ |
| record / reflect | `mise run kb-remember` / `mise run kb-reflect` | ~~`graphify save-result`/`reflect`~~ |
| artifacts | `mise run kb-artifacts` | — |

**2. Claude Code only — NEVER Gemini or any auto-detected key.** All LLM work is
Claude (the host-agent Workflow for extraction; deterministic no-LLM for labeling).
Every task strips `GEMINI_API_KEY`/`GOOGLE_API_KEY` (`graphify_env.clean_env`) so
graphify's backend auto-detect can never pick a non-Claude provider. graphify's
`claude-cli` backend exists but is BROKEN for labeling (#2076 — prose-wrapped JSON),
so `kb-label` defaults to the deterministic hub labeler.

## Ingest every source THROUGH graphify (via the tasks above)

**All ingestion goes through graphify's own tooling, never an ad-hoc fetch** — and
via the task, per mandate 1. Entry points:
- **GitHub repo** → `sources/<name>.manifest` + `mise run kb-build`.
- **Any URL** (docs page, blog, article) → `mise run kb-add -- <url>` — fetches to
  `./raw` (graphify writes `source_url`/`captured_at` frontmatter). `--author`/
  `--contributor` tag provenance. No-key `add` fetches but does NOT re-cluster, so
  batch all adds, then merge once.
- **Sitemap** → enumerate, then `mise run kb-add --` each on-topic page.
- **Video/YouTube** → `mise run kb-add -- <url>` downloads audio, then
  `mise run kb-transcribe -- raw/<yt>.m4a` (local faster-whisper — NO key, NO LLM).
- **Live PostgreSQL** → (add a task if this recurs; do not hand-run `graphify extract`).

`curl`/WebFetch/manual vendoring are a **fallback ONLY** when graphify genuinely
cannot reach a source — and even then route the content into the graph via an
extraction chunk. With no API key the *semantic* extraction falls to the host agent
(Claude), but the FETCH + pipeline is graphify's. One ingestion path = uniform
provenance, the freshness policy, and reproducibility.

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
2. **Ingest** (via the tasks — never raw graphify).
   - Repo → write the manifest, `mise run kb-build`. A prose-only repo (no code)
     is skipped without aborting — its value comes from the prose step, not AST.
   - URL(s) → `mise run kb-add -- <url>` (batch all; no-key add fetches to `./raw`
     without re-clustering). Video → `mise run kb-add --` then
     `mise run kb-transcribe -- raw/<yt>.m4a`.
   - Prose extraction = **Claude host-agent, and for N sources use a `Workflow`
     fan-out** (proven 2026-07-22: 32 docs, 0 errors). Each `agent()` reads one raw
     file and returns a schema-validated `{nodes, edges}`; assemble into ONE combined
     chunk `sources/extractions/<name>-docs.json` with `source_url` + `captured_at`
     per node. A single-shot source can be one `general-purpose` subagent instead.
     Write incrementally / rely on Workflow resume — an agent dying at source 13 of
     20 must leave 13 (`agent-report-persistence`). **This is the ONLY LLM path and
     it is Claude — never Gemini** (mandate 2).
3. **Merge.** `mise run kb-merge -- <chunk.json> [root]` (one chunk into the graph),
   or `mise run kb-build` to replay all committed chunks. Both re-cluster; Louvain
   renumbers communities globally + non-deterministically → **every merge staleifies
   labels**, so relabel after.
4. **Label.** `mise run kb-label` — deterministic, no-LLM hub labels (Gemini-free,
   instant). Do NOT expect an LLM to name communities: graphify's only non-Gemini LLM
   backend is `claude-cli`, and it is broken for labeling (#2076 — prose-wrapped JSON).
   Unlabeled communities cripple the wiki, so always relabel after a merge.
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

- **NEVER Gemini / never an auto-detected key.** graphify's `detect_backend()`
  priority is gemini→kimi→claude→openai→deepseek→azure→**bedrock (any `AWS_REGION`/
  `AWS_PROFILE`)**→ollama. A stray global `GEMINI_API_KEY` (a mise secret) once made
  `graphify label` silently use Gemini; stripping only Gemini then fell to Bedrock
  (25 failed "Converse" batches). `graphify_env.clean_env()` strips ALL of them from
  every graphify subprocess (keeping only `ANTHROPIC_*` — the Claude path), so
  detect_backend returns None. Verified 2026-07-22.
- **`kb-label` = deterministic hub labels, and that is correct.** graphify prints
  "no LLM backend configured; keeping Community N placeholders" — MISLEADING: the
  deterministic hub labeler (names each community after its highest-degree node) still
  runs during clustering, so `.graphify_labels.json` ends up fully named (2,409/2,409,
  0 placeholders), just not LLM-enriched. Do not chase that warning.
- **claude-cli backend is BROKEN for labeling (#2076).** It returns prose-wrapped
  JSON ("Done — cluster names above") graphify can't parse → every batch fails. This
  is why `kb-label` is deterministic by default; `--claude-cli` only to re-probe a fix.
- **Never run graphify by hand** — the PreToolUse guard (`kb_setup.hook_guard`) denies
  raw `graphify …`/`_merge_docs.py`/graphify-python and redirects to the task. Also
  never `graphify hook install` (#857) or bare `graphify install` (mutates `~/.claude`).
- **`graphify extract --code-only` exits non-zero on a no-code repo.** `kb-build`
  tolerates it (skips, keeps the pin). Never treat a prose-only repo as fatal.
- **Python 3.14**: no Leiden (Louvain fallback, accepted) and `export svg` needs a
  scipy inject (`mise run kb-ensure-deps`).
- **YouTube**: `mise run kb-add -- <url>` downloads audio; then
  `mise run kb-transcribe -- raw/<yt>.m4a` (graphify's bundled faster-whisper — local,
  NO key, NO LLM; ffmpeg pinned). Then host-agent extract the transcript like any prose.
- Version-gated (0.9.24+, not in installed 0.9.23): `reflect --if-stale`,
  `extract --dedup-llm`. Bump the pin before relying on them.

## Improving THIS skill (skill-creator loop)

This skill was authored with the skill-creator methodology and is meant to be
measured and improved, not frozen. When ingestion behavior drifts or a new source
type recurs, run the skill-creator eval loop: draft/adjust test prompts in
`evals/evals.json`, run with-skill vs baseline, review, and rewrite. Generalize
from feedback — bundle a repeated helper into `scripts/` rather than hard-coding a
one-off. Keep the description "pushy" so agents actually trigger it on a bare URL.
