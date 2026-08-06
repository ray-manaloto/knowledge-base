# #186 — graphify 0.9.34, the cold review, both rounds, verbatim

Promoted from `.agent/kb/review/reports/` because PR
[#190](https://github.com/ray-manaloto/knowledge-base/pull/190)'s body cites
these filenames, and `.agent/` is gitignored — a citation only one machine can
open is not a citation.

Promotion was **deliberately deferred to the branch after the round**, the same
way `e566a9e` handled the #185 reports: `docs/research/**` is not
`review.EXEMPT_PATHS`, so committing these onto the reviewed branch would have
moved HEAD past its own receipt and orphaned it.

Lane: `cold:codex` (GPT-5.6 Sol, read-only sandbox), cross-family against a
Claude-written diff. Two rounds, the `kb-review` bound. **7 findings, 0
blocking.** Both rounds exceeded codex's ~1,500-line single-shot guard and ran
in batches.

| file | round | outcome |
|---|---|---|
| `review-4ca3d6411882cfe9fe75b0d977b9d0d668f75e59-cold.md` | 1 | 3 findings — 1 **P1**, 2 P2 |
| `review-e1c7044021f7d1b3b4ad177c3b90272e4799c878-cold.md` | 2 | 4 findings — 2 **P1**, 2 P2 |
| `review-6ff46ac499a2fae5acde9e33a11a67e48c7c84ad-cold.md` | fix | no lane re-ran; records what verified the fixes |

## Why these are worth keeping past the round

**Round 1's P1 is the one that changed the shipped design.** The round retired
`kb_setup.hyperedges`' capture/reattach carry on the premise that 0.9.34 fixes
the underlying defect natively — and nothing in the retiring code checked which
binary would actually run. `graphify_exe()` falls back to a bare
`shutil.which("graphify")` whenever `mise which` cannot resolve the pin, a
pre-0.9.34 binary returns **rc=0 while silently writing `[]`**, and `_labelled`
then stamps success and re-derives the prose graph from the emptied artifact.
Not hypothetical here: bare `graphify` on this host was a stale 0.9.32 install
dir. The fix was a **writer version gate** across every graph-writing
`kb-setup` command.

That is this repo's `a-tool-that-guesses-a-tier-will-guess-wrong` shape again —
a safety margin removed on a version premise the code could not see.

**Both of round 2's P1s were about the fix from round 1**, and both were
measured rather than argued:

- Chunk-level `captured_at` is a **max over the chunk's nodes**, so an
  assembled chunk that mixes a fresh `source_file` with a stale one replays
  last as a whole and the stale half wins. Measured against the live corpus:
  exactly 2 cross-chunk `source_file` intersections, both the intended
  supersession, **zero date inversions** — so it is real but not live, and
  per-file supersession cannot be expressed by replay order alone. Deferred to
  [#189](https://github.com/ray-manaloto/knowledge-base/issues/189) with the
  probe.
- Legacy bare-basename identities coexist with the new clone-relative form,
  which re-extraction has to retire rather than merely add to. Deferred to
  [#187](https://github.com/ray-manaloto/knowledge-base/issues/187), whose
  process owns it.

## Findings that produced work outside this round

- **Round 1 P2 — a dependency bump changed CLI semantics under a doc nothing
  edited.** 0.9.34 switched `graphify path` (and MCP `shortest_path`) from
  undirected-by-default to direction-respecting-by-default. The skill reference
  `.claude/skills/graphify/references/query.md` was not in the diff and still
  documented the old behaviour, so a path query could flip found/not-found
  purely from the bump. Fixed inside PR #190.
- **Round 1 P2 — a warning that can never be actioned.** `skillopt` pins
  `ref = main` by design, so `'main'` vs `'v0.2.0'` is permanently unorderable
  and prints `NOT CHECKED against upstream` every session — against
  `run.py`'s own stated design that silence is the signal. Filed as
  [#188](https://github.com/ray-manaloto/knowledge-base/issues/188).

## What the lane did NOT cover, stated rather than dropped

The committed extraction chunk
`sources/extractions/claude-code-docs-2026-08-05-refresh-docs.json` (2,830 diff
lines in round 1, 2,493 in round 2) was never sent to codex — it is corpus
data, not judgeable behaviour. In round 2 it was verified directly instead, in
full rather than sampled: both sides parse, all 542 changed lines are
`source_file` values, and 116 nodes + 149 edges + 6 hyperedges = 271 matches
the 271 removed / 271 added lines exactly.

Round 1 also records a **citation off by ~9 lines** in the lane's own P1
(`graphify_ops.py:232-238` cited; the real existence check is at `:223-230`),
caught by spot-checking every citation against the file at the reviewed SHA
rather than trusting the transcript. The substance held; the anchor did not.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the
  0.9.34 release whose serve, path-direction and hyperedge behaviour the
  reviewed change is about.
- [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) — the
  `source_only` tool whose `ref = main` pin produces the permanent
  `NOT CHECKED` print in round 1's third finding.
