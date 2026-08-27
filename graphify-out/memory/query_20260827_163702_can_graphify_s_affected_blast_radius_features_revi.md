---
type: "query"
date: "2026-08-27T16:37:02.836723+00:00"
question: "Can graphify's affected/blast-radius features review a PR in this repo?"
contributor: "graphify"
outcome: "corrected"
correction: "They cannot, and the failure is two-sided.\n\nBLIND: 25 of 77 `kb_setup` modules are absent from `graph.json`, including BOTH files\nPR #550 changed (`graphify_sdk.py`, `graphify_health.py`) and four of the five stateless\nBash guards. Control-armed — `hook_guard.py` returns 40 hits from the same grep that\nreturns 0 for `graphify_sdk.py`, same directory and same build. Nine further modules are\nin the graph but no longer on disk.\n\nWRONG: `graphify affected \"assess()\"` does not miss — it ANSWERS, with a Swift function\nin a different ingested repo. The pre-#1504 node-ID scheme collides same-name symbols\nacross 85 sources and the tool resolves rather than refuses. `\"classify_unclassified()\"`\nreturns \"No unique node match\", which conflates zero matches with several, so the caller\ncannot tell a miss from an ambiguity.\n\nUse the PR bots and a cold cross-family review for blast radius until the graph indexes\nthis repo's own code. On PR #550 that is exactly what worked: repowise named five\ndependent test files (all rc=0) and the codex cold lane caught a real P1 that no graph\nquery would have surfaced.\n"
---

# Q: Can graphify's affected/blast-radius features review a PR in this repo?

## Answer

Ray asked for graphify's PR/blast-radius features on PR #550. The answer is that they
cannot see this PR, and the probe that established it is worth keeping.

MEASURED 2026-08-27 against graphify-out/graph.json (built 2026-08-21):
  kb_setup modules on disk        77
  kb_setup modules in the graph   61
  ON DISK BUT ABSENT              25  (32%)
  IN GRAPH BUT NOT ON DISK         9  (stale, deleted modules still indexed)

Absent includes BOTH files PR #550 changed — graphify_sdk.py and graphify_health.py —
and four of the five stateless Bash guards: absent_binary, check_first, secret_guard,
stage_explicitly (graph_first is present). Also funnel, hk_test, graph_size,
build_outcome, telemetry, model_limits, session_select.

Control-armed, and the control is what makes it a finding rather than a miss:
  grep -o -m 40 'kb_setup/graphify_sdk\.py' graph.json  ->  0
  grep -o -m 40 'kb_setup/hook_guard\.py'   graph.json  -> 40
Same directory, same build, same language, same extractor. A `kb-query` for
"classify_unclassified" returns cognee, ruff, TurboFieldfare — nothing of ours — while
a query for "hook_guard decide" returns `decide()` at python/src/kb_setup/hook_guard.py:L124.

NOT explained by recency alone. `classify_unclassified` was added 2026-08-16 (5308c69c),
five days BEFORE the graph was built. So "the graph is stale" is at most half of it;
something also dropped a file that existed at build time. Both candidate causes are
recorded and NEITHER is picked here.

The second, independent failure is worse than a miss. `graphify affected "assess()"`
returns a match — for `assess()` in Sources/TurboFieldfareApp/.../RepackModelInstallerClient.swift,
a Swift function in a DIFFERENT ingested repo, not kb_setup.graphify_health.assess. The
graph carries the pre-#1504 node-ID scheme and warns about same-name collisions on every
query; what it does NOT do is refuse. `classify_unclassified()` and `require_complete()`
returned "No unique node match", which conflates zero matches with several — so the tool
answers confidently about the wrong repo in one case and ambiguously in the other, and a
caller cannot tell those apart from the output.

The consequence for doctrine: `.claude/CLAUDE.md` says to route non-trivial decisions
through the graph, and `kb_setup.graph_first` DENIES a broad source search until a graph
query has run. Both are pointing at a graph that cannot answer about a third of the module
tree they govern. This is the same shape as the 2026-08-27 finding that the KB holds its
own code and none of its own doctrine — one layer down, and now measured for CODE too.

What actually found the bug on this PR was not graphify: it was the repowise bot naming
five dependent test files (all pass, rc=0) and a cold codex review that caught a real P1.
Bot comments are free; the graph tooling here was not free and returned another project's
Swift.


## Outcome

- Signal: corrected
- Correction: They cannot, and the failure is two-sided.

BLIND: 25 of 77 `kb_setup` modules are absent from `graph.json`, including BOTH files
PR #550 changed (`graphify_sdk.py`, `graphify_health.py`) and four of the five stateless
Bash guards. Control-armed — `hook_guard.py` returns 40 hits from the same grep that
returns 0 for `graphify_sdk.py`, same directory and same build. Nine further modules are
in the graph but no longer on disk.

WRONG: `graphify affected "assess()"` does not miss — it ANSWERS, with a Swift function
in a different ingested repo. The pre-#1504 node-ID scheme collides same-name symbols
across 85 sources and the tool resolves rather than refuses. `"classify_unclassified()"`
returns "No unique node match", which conflates zero matches with several, so the caller
cannot tell a miss from an ambiguity.

Use the PR bots and a cold cross-family review for blast radius until the graph indexes
this repo's own code. On PR #550 that is exactly what worked: repowise named five
dependent test files (all rc=0) and the codex cold lane caught a real P1 that no graph
query would have surfaced.
