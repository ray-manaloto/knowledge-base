---
type: "query"
date: "2026-08-25T00:51:38.831070+00:00"
question: "What did the three codex lanes find about the graphify extraction gap, the kb-build health check, and the graph-first guard?"
contributor: "graphify"
outcome: "corrected"
correction: "My 43.2% extraction-gap figure was inflated by a probe that ignored the leading dot on method labels; the real figure is 35.6% and most of it is pre-#1504 id staleness, not lost extraction."
---

# Q: What did the three codex lanes find about the graphify extraction gap, the kb-build health check, and the graph-first guard?

## Answer

THREE CODEX LANES LANDED 2026-08-25. What each found, and the corrections they forced.

**1. The 43% extraction gap was THREE causes, and my headline number was wrong.**
(#478, corrected there.) Miss rate 43.2% -> **35.6%** once method labels' LEADING DOT
is stripped — `.__init__()`, `.passed()`, no class prefix, 148 of them in our slice.
That was my third probe error in one investigation, after trailing `()` on callable
labels and basename-vs-path file matching.

Most of the REMAINDER is **staleness, not lost extraction**: `graph.json` was built by
a pre-#1504 graphify, whose ids are not path-qualified, so across a 492k-node 58-repo
corpus same-named symbols collide and one is dropped. Corroborated by graphify itself —
`mise run kb-query` prints "this graph uses the pre-#1504 node-ID scheme" on EVERY
invocation, which I had already seen and not connected. **The remedy is a rebuild with
the current pin**, not an extraction fix.

The one REAL current bug: `graphify/ids.py`'s `make_id` casefolds and collapses repeated
underscores in the FINAL joined id, making `make_id(scope, name)` **non-injective** —
`add_node`'s `if nid in seen_ids: return` then drops the second declaration SILENTLY.
Confirmed in kb_setup: `_source_path_evidence`/`source_path_evidence` (graph.py, +3 more
pairs), `Dropped`/`dropped` (handoff_reconcile.py), `_provider_plan` vs `Provider.plan`
(artifact_download.py). Fixed on `fix/extraction-symbol-id-collision` (`5daeaa2`, local
clone, NOT pushed) following graphify's own Go precedent #2779. Clean single-repo arm:
1.9% -> 1.0% miss, all 7 pairs (present, DROPPED) -> (present, present).
Left documented-unfixed: a function nested INSIDE a function is never emitted at all.

**2. kb-build's health check now passes a benign line and still fails a novel one.**
`graphify_health.py` gained `_ROUTINE_PRUNE_PROGRESS` — a line-anchored regex matching
ONLY graphify's own "Pruned N node(s)…" f-strings — plus a shared `_unaccounted_stderr`
helper. A real `[graphify] WARNING:` sharing the prefix, or the benign text with trailing
extra, still blocks. Both arms proven by reverting each fix. `build_outcome.describe()`
no longer asserts "re-running WILL fail again" as fact — it says the record does not
re-test its own cause. Verified independently: `kb-check` rc=0, 47 tests.

**3. The graph-first guard's hole is STRUCTURAL, and the recommendation is to leave it.**
`decide()` never routes `Read` at all — `tool_name != "Bash"` and `!= "Grep"` returns
`None` unconditionally, and that is a documented acceptance criterion with tests. Live
probe over all 75 files: Read x75 -> 0 denied, single-file Grep x75 -> 0 denied, and ONE
non-recursive `grep` naming all 75 explicitly -> ALLOWED (recursive=False short-circuits
before the path check). The whole tree is readable one file at a time with zero guarded
operations. Two tightening designs were REJECTED on false-positive grounds — this
classifier has already regressed twice from added shape-based judgment, and both would
flag the module's own protected case. Recommended instead: `kb_setup.session_reflect`
already computes `graph_queries` vs `graph_skipped` and is wired to `/clear-prep` —
a checkpoint, not an inline nag. Honest residual: nobody has verified that report is
read and acted on.

**`.artifacts/` is now gitignored.** mde's `observability.py`/`statusline`/`hooks` write
7 telemetry files there; nothing in this repo reads them. Armed both ways.

**THE CROSS-CUTTING LESSON: "it crashed" and "43% missing" were both symptoms, not
diagnoses.** Every one of these three lanes changed the verdict its own brief started
from, because it read the traceback or re-derived the number instead of inheriting it.


## Outcome

- Signal: corrected
- Correction: My 43.2% extraction-gap figure was inflated by a probe that ignored the leading dot on method labels; the real figure is 35.6% and most of it is pre-#1504 id staleness, not lost extraction.