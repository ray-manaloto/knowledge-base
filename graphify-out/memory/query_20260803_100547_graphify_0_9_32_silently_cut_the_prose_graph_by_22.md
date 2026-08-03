---
type: "query"
date: "2026-08-03T10:05:47.560991+00:00"
question: "graphify 0.9.32 silently cut the prose graph by 22 percent — why, and how is it prevented?"
contributor: "graphify"
outcome: "useful"
---

# Q: graphify 0.9.32 silently cut the prose graph by 22 percent — why, and how is it prevented?

## Answer

0.9.32's new _is_ast_tier (build.py) trusts _origin when present and otherwise GUESSES from shape: a source_location matching ^L\d is read as AST. Our host-agent extraction agents emit L5/L13 unprompted — kb-extract.js never asked for the field — so 629 committed doc nodes (621 claude-docs-docs, 8 claude-commands-docs) were stamped _origin=ast at load and vanished from graph-prose.json (2864 -> 2235 nodes, 3747 -> 2849 links). Silent: no error, no warning. Control arm: chunks whose source_location values do NOT match the regex (claude-workflow-blogs 223/223, goal-engineering 290/290) lost nothing, so the predictor is the shape test not the field. Upstream anticipated it — build_from_json comments that fresh semantic chunks 'may carry drifted L<line> source_locations and the shape fallback would misread them as AST' — and guards THAT call site strictly; the load-time backfill does not. Fixed at three layers: all 2864 nodes across 18 chunks stamped _origin=semantic; kb-extract.js requires the literal; kb_setup.chunks REJECTS a chunk lacking it. The gate's FAIL direction needed no synthetic mutation — HEAD's own unstamped bytes give 52 _origin errors vs 0 now.

## Outcome

- Signal: useful