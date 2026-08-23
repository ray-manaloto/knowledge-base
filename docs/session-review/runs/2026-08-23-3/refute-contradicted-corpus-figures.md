# Refutation lane: "docs + mise.toml describe 58 chunks / ~10.6h / $140.0 / 16h at ~1.5x"

Probe run 2026-08-21T15:31Z, repo /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base,
branch corpus-gate-bundle-0821, HEAD c720f1c9.

## Working tree (the primary artifact an operator reads/runs)

```
$ grep -n "140\.0\|58 chunk\|10\.6h\|1\.5x\|16h\|63\.0\|26 chunk\|4\.8h" docs/agents/graphify-semantic-corpus.md mise.toml
mise.toml:688:# 26 chunks (post-dedupe, #414; was 58 pre-dedupe) at the measured ~11
mise.toml:689:# min/chunk projects to ~4.8h; 16h is roughly 3.3x that (was ~1.5x pre-dedupe),
mise.toml:694:timeout = "16h"
docs/...:416:The full run is projected at roughly 4.8h of wall clock (26 chunks, post-dedupe
docs/...:417:per #414 — was 58 chunks / ~10.6h pre-dedupe — at concurrency 1, ~11
docs/...:432:  money is bounded separately by `_MAX_TOTAL_COST_USD` (63.0, post-dedupe; was
docs/...:433:  140.0 pre-dedupe — see its comment ...
docs/...:434:  arithmetic). The task's own `timeout = "16h"` is roughly 3.3x the projected
```
python/src/kb_setup/graphify_semantic_corpus.py:107 `_MAX_TOTAL_COST_USD = 63.0`.
=> docs, mise.toml and the constant AGREE post-dedupe. No contradiction.

## Control arm (same grep, other artifact -> the other answer)

```
$ git show HEAD:docs/agents/graphify-semantic-corpus.md | grep -n ...
416: roughly 10.6h ... (58 chunks at
431: `_MAX_TOTAL_COST_USD` (140.0; ...
433: `timeout = "16h"` is roughly 1.5x the projected 10.6h
$ git show HEAD:mise.toml | grep -n ... -> 688: 58 chunks ... 10.6h; 689: 1.5x
$ git show HEAD:python/.../graphify_semantic_corpus.py | grep _MAX_TOTAL_COST_USD -> 93: 140.0
```
So the probe discriminates; and at HEAD docs/mise/code ALSO agree — at 140.0.

## Per-commit sweep of the whole branch

a67cbac4 -> 100.0 (docs not yet carrying the block)
d8114ab1 / ebcf9fcb / 3d9bb3ff / c720f1c9 -> constant 140.0, docs 140.0/58/10.6h/1.5x
=> No commit, and not the working tree, ever pairs "docs say 140.0/58" with "code says 63.0".

## Mechanism of the original probe's error

`git diff --stat` shows the in-flight (uncommitted) change set is NINE files,
including docs/agents/graphify-semantic-corpus.md (+16/-8... 16 changed) and mise.toml (11),
not just graphify_semantic_corpus.py (+206) and tests (+273). The original probe read the
DOC from one artifact and the CONSTANT from another.

Contradiction inside the finding set: item 33 characterises the sixth in-flight change as
"graphify_semantic_corpus.py (+206) and tests_...(+273)" only; the same diff carries the doc
and mise.toml updates that dissolve this finding.

## Live hazard noted

All 9 modified files share mtime 1787326252.90x (2026-08-21T15:30:52Z) and .git/AUTO_MERGE +
`reflog HEAD@{0}: reset: moving to HEAD` were written at the same second — the working tree
is being mutated by something else during this review (cf. items 2 and 9).

## Repo-wide sweep for the stale tokens (no bound, no maxdepth)

`grep -rn "58 chunks\|10\.6h\|140\.0" --include='*.md' --include='*.toml' --include='*.py' ...`
The only remaining live carriers are `graphify_semantic_corpus_authority.py` (an APPEND-ONLY
dated-ruling ledger — historical statements by construction, and NOT named by the finding)
and explicit "was ... pre-dedupe" back-references in the two named files. Neither of the two
named artifacts asserts 58/10.6h/140.0/1.5x as the CURRENT projection.

## Residual true core (stated so it is not lost)

Between 3d9bb3ff (#414's dedupe, 58 -> 26 chunks) and c720f1c9 (HEAD), the committed docs and
mise.toml did describe a 58-chunk / 10.6h workload that the plan no longer produced. That
staleness window is real, is in COMMITTED history, and is closed by the in-flight change set.
It is not the contradiction the finding states (docs at 140.0 vs code at 63.0), which exists
in no snapshot.

VERDICT: refuted = true.
