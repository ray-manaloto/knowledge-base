---
type: "query"
date: "2026-08-19T22:50:12.528568+00:00"
question: "What does advancing seven pinned dependencies actually cost in this repo, and what does the release-notes review buy?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does advancing seven pinned dependencies actually cost in this repo, and what does the release-notes review buy?

## Answer

# Currency sweep 2026-08-19c — what the round asked and what it found

The round asked: advance seven pinned dependencies (agnix 0.49.0, conda:ffmpeg
9.0.1, anthropic 0.124.0, graphifyy 0.9.47, datamodel-code-generator 0.74.0,
ty 0.0.73, claude-code manifest v2.1.236), make agnix and
datamodel-code-generator currency dependencies with graphify sources, and review
each release's notes before moving its pin.

All seven landed in PR #398 (`71cccbb0` on `main`), every pin moved through its
OWNING command (`mise use` / `uv add`) rather than an editor.

## What a currency sweep actually costs here, measured

**One dependency bump touched EIGHT places.** graphifyy 0.9.46 -> 0.9.47 put the
repo into 8 simultaneous ref-binding drifts: the pyproject pin, the source
manifest, `graphify_baseline.py` (ref + commit), `graphify_semantic_corpus.py`
(ref + commit), `graphify_semantic_slice.py` (ref + commit), and
`sources/graphify.dispositions.json`. Six of the eight were advanced this round;
the two in the slice are EVIDENCE for a committed receipt and may not move until
the slice re-runs (#373). That is what `[[tool.graphify.ref_binding]]` detects
and nothing prevents — the measurement behind #393.

**And at least one MORE restatement site is invisible to that machinery.** (The
source comment calls it "the ELEVENTH"; that ordinal is INHERITED and not
derivable from anything checkable here, so do not repeat it. The checkable fact
is that `currency.toml` has **8** `[[tool.graphify.ref_binding]]` rows, all
scoped to `sources/graphify.manifest`, and none of them reaches this line.)
`_CURRENT_CLAUDE_VERSION` in `graphify_semantic_slice.py` was left at 2.1.235
while claude-code moved to 2.1.236 in four other places. The ref-binding check
compares against `sources/graphify.manifest`, so a claude-code binding is out of
its scope entirely. The constant's own comment already recorded that a cold lane
found it last time. **A cold lane found it again this round.** Two independent
misses by one blind spot.

## The release-notes review, per tool, and what each was worth

* **graphifyy 0.9.47** was the most valuable item. It closes #2787 (sidecar
  writes dirtying a pinned checkout), fixes an `AttributeError: 'ThinkingBlock'`
  crash in the CLAUDE backend — the only backend this repo permits — makes
  `graph.json` field order stable across a read-rebuild round trip, stops
  `manifest.json` rewriting timestamps on a no-op run, and makes `graphify query`
  name the graph it opened and its node count.
* **agnix 0.49.0** adds CC-SET-024. agnix runs warnings-as-errors here, so an
  upstream rule addition is a lint FAILURE by construction. Verified by RUNNING
  `--strict`, not by reading the note.
* **ffmpeg 8.1.2 -> 9.0.1** is a MAJOR and is presence-only in currency, so it
  got a real decode probe rather than a version string: a generated 10KB m4a
  transcoded to an 88KB wav, both directions.
* **datamodel-code-generator 0.73.0** ships real breaking changes; none reach us,
  and that was MEASURED (all three generators regenerate byte-identically at
  0.74.0), not inferred from non-use.

## Two pre-existing defects the sweep exposed, neither caused by it

1. **`sources/agnix.manifest` had been at v0.40.0 since 2026-08-02** — six minors
   behind an installed 0.46.0, with nothing reporting it because no
   `[tool.agnix]` row existed to ask. The engine reported green forever by never
   asking. Ray's "make it a currency dependency" is precisely the fix.
2. **`mise run kb-build` FAILS** — `anthropic-sdk-python` has three unclassified
   files (`Brewfile`, two `.keep`) and graphify's detect fails closed, writing no
   stamp. So the "graph build stamp pending" item several handoffs carried as a
   scheduling to-do is a DEFECT (#397). One is a to-do, the other is a bug, and
   the check's wording made the bug look like the to-do.

## Review, and what it caught

ONE cold lane (`cold:antigravity` — codex was hard out of credits, probed live),
two rounds, six findings. **Three of the six were defects written IN THIS
SESSION**, and round 2's two findings were both inside round 1's fix.

Bot reviews then found a seventh thing NEITHER lane saw: an unauthored telemetry
hunk in `.codex/config.toml` that reached the PR via `git add -u`. It landed in
the authority re-record commit, which by design no lane re-read — and the
fix-round report for that commit said so at the time. The honest coverage note
is what made the gap findable rather than invisible (#399).

Issues filed: #393, #394, #395, #396, #397, #399, #400, plus a recurrence
comment on #235.


## Outcome

- Signal: useful