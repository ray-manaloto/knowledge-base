# Refutation lane — finding [unpinned] GAP-3 "four gate claims unverified"

CLAIM: "Four gate claims resting on unverified adversarial checks per completeness
GAP-3: DW-14 ('25 committed chunks, ZERO merged'), DW-19 ('build=skip is DEBT not
fix'); both rank high in extraction readiness gate."
EVIDENCE OFFERED: "Completeness.md GAP-3; ... adversarial verification never ran (capped at 5/lane)"

## Probes run (in order)

1. `mise run kb-query -- "extraction chunks merged into graph and build skip manifests" --prose --idf` (graph-first, orientation only)
2. GAP-3 located: `.agent/kb/reports/agents/2026-08-21-session-review/COMPLETENESS.md:80-92`
   and its committed twin `docs/research/reports/2026-08-21-session-review-completeness.md:83-95`.
   Four ids: A5-11, RR-34, DW-14, DW-19. Restatement is FAITHFUL.
3. `grep -rn --include='*.md' "DW-14\|DW-19" .agent/kb/reports/agents/ docs/` ->
   HIT: `.agent/kb/reports/agents/notepad-recovered-2026-08-21-6ae19ff6.md:9`
   "GAP-2/3 probes re-run: ER-10 CONFIRMED ...; DW-14 25 chunks committed (merged
   half unmeasured); DW-19 5 skip manifests."  <-- recovered from main transcript,
   timestamped 06:55:21Z, i.e. INSIDE the reviewed window and 8 min after PR #422
   merged the completeness doc (8929d47f, 2026-08-21 01:47:48 -0500 = 06:47:48Z).
4. Independent re-derivation of both substances:
   - `ls sources/extractions/*.json | wc -l` -> 25   (DW-14 chunk half CONFIRMED)
   - `grep -ln "build *= *[\"']*skip" sources/*.manifest | wc -l` -> 5 (DW-19 CONFIRMED)
5. "rank high in extraction readiness gate": `grep -on "DW-[0-9]*\|ER-[0-9]*\|A5-[0-9]*\|G[0-9]"`
   on `extraction-readiness.md` -> 0 hits; CONTROL `grep -oc "DW-[0-9]*" COMPLETENESS.md` -> 11.
   `grep -oc "DW-" SYNTHESIS.md` -> 2, neither is DW-14/DW-19.

## The decisive probe (primary artifact = the reviewed session's own transcript)

Reviewed-session transcript:
`/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/6ae19ff6-2b88-4aea-8fa7-c0430395e2da.jsonl`

Extracted the tool_use at 2026-08-21T06:21:14.512Z (`isSidechain=False`, i.e. the
ORCHESTRATOR, not a capped lane). Command, verbatim tail:

    echo "--- DW-14: committed extraction chunks:"; ls sources/extractions/*.json | wc -l; \
    echo "--- skip manifests:"; grep -l "^build = skip" sources/*.manifest

tool_result at 2026-08-21T06:21:14.692Z, verbatim tail:

    --- DW-14: committed extraction chunks:
          25
    --- skip manifests:
    sources/codex.manifest
    sources/codebase-memory-mcp.manifest
    sources/codegraph.manifest
    sources/colibri.manifest
    sources/GitNexus.manifest

=> GAP-3's OWN prescribed action ("verify DW-14 (`ls sources/extractions/ | wc -l` ...)
and DW-19") ran on the main chain, 26 minutes before the merge of the doc that asked
for it and INSIDE the reviewed window. DW-19 fully confirmed (5, named). DW-14's
chunk-count half confirmed (25).

## And the one half that was NOT probed is not "unverified" — it is FALSE

DW-14's second half, "still ZERO merged", re-derived here:

    chunks=25 with>=1 of first-5 node names present in graph-prose.json: 23
    NOT matched: claude-code-docs-2026-08-05-refresh-docs.json, claude-docs-docs.json
    control bogus token in prose: False

Direct route: `grep -c "www_mindstudio_ai_blog_claude-code-agentic-workflow-patterns"`
-> graph-prose.json **51**, graph.json **3**; CONTROL `zzz_no_such_source_token_xyz` -> **0**.
That source is carried by the committed chunk `sources/extractions/claude-workflow-blogs-docs.json`.

## Why the original probe could only say "unverified"

It read the review fan-out's per-lane verify artifacts
(`.agent/kb/reports/agents/2026-08-21-session-review/*verify*.md`, capped 5/lane).
A main-chain orchestrator Bash probe leaves NO file in that directory, so that search
is structurally incapable of returning "verified" for a fact the orchestrator checked
by hand. Classic bounded search.

## Cross-check against the rest of the set

- Item 35 CORROBORATES the refutation: it names "'4 manifests' vs the actual 5 with
  build=skip" as a known stale figure, i.e. the 5-skip fact was independently measured
  by a second route. The synthesis itself names all five at
  `docs/research/reports/2026-08-21-session-review-synthesis.md:227`, and
  `extraction-readiness.md:55` states "5 manifests now carry `build = skip`".
- No finding in the set contradicts this refutation.

## VERDICT: REFUTED
