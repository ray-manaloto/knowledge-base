# Refutation attempt — [bot-reviews] musl lock entries / issue #391 cross-ref

## Claim
graphify-labs flagged mise.lock linux-x64-musl -> linux-64 glibc conda packages on PR #439
(3x, medium→high). REAL finding, third+ recurrence of the class tracked in OPEN #391; never
cross-referenced back to #391.

## Probes so far
- `gh issue view 391 --json state` -> OPEN (confirmed). Body confirms the #385 prior recurrence
  and "left un-dispositioned" wording, verbatim.
- `gh pr view 439 --json reviews` -> 15 reviews, 3 by graphify-labs:
  19:14:33Z (commit 9fec8ec2), 20:17:01Z (0aeae4a9), 20:45:37Z (a9d661ab).
- grep of the 3 graphify-labs review bodies:
  - 19:14:33 line 18: "**linux-x64-musl lock entries point at linux-64 conda packages** —
    `mise.lock` · _Escalate · medium_"
  - 20:17:01: NO musl finding in the body. 5 findings, all uv.lock/clear-prep. Body ends
    "· 1 more finding(s) on lines outside this diff (see the check run)."
  - 20:45:37 line 166: "**Linux musl lock entries point at glibc linux-64 Conda packages** —
    `mise.lock` · _Escalate · high_"
  => the musl finding is named in 2 of 3 review bodies, not 3.
- Inline PR review comments (`gh api .../pulls/439/comments`, 15 rows): zero graphify-labs rows
  at all; 0 musl/glibc hits.
- Issue comments on 439 (236 lines): 0 musl, 0 "#391". Control: 16 'coderabbit' hits in the
  same file, so the grep discriminates.
- Cross-reference probe on #391 (GraphQL timelineItems CROSS_REFERENCED/REFERENCED/CONNECTED):
  totalCount = 0. CONTROL ARM: same query on #381 -> 6, #437 -> 3, #418 -> 1, #440 -> 0.
  The probe can return non-zero, so #391's 0 is real.

## The refutations

### R1 — "3x" is wrong: the musl finding appears in 2 of graphify-labs' 3 reviews on PR #439
`awk '/^=== /{r=$2} /musl/{print r}'` over the three dumped review bodies:
- 2026-08-21T19:14:33Z (commit 9fec8ec2) — "linux-x64-musl lock entries point at linux-64
  conda packages — `mise.lock` · _Escalate · medium_"
- 2026-08-21T20:17:01Z (commit 0aeae4a9) — ABSENT. 5 findings, all uv.lock/clear-prep.
- 2026-08-21T20:45:37Z (commit a9d661ab) — "Linux musl lock entries point at glibc linux-64
  Conda packages — `mise.lock` · _Escalate · high_"

The middle review ends "· 1 more finding(s) on lines outside this diff (see the check run)".
Probed the check run: `gh api repos/.../check-runs/96898346061 --jq '.output.text'` (2,734 chars)
-> 0 hits for musl/glibc/linux-64/mise.lock. CONTROL: `grep -c 'Escalate'` on the same text -> 5,
so the grep discriminates. annotations_count = 0 on both graphify-labs check runs for that commit.
=> two occurrences, medium then high. Not three.

### R2 — "third+ recurrence" undercounts; the #385 premise was inherited from #391's prose, never re-derived
`gh pr view 385 --json reviews --jq '.reviews[]|select(.author.login=="graphify-labs")|...'`:
- 2026-08-19T17:04:38Z — "uv linux-arm64 platform points to musl artifact — `mise.lock` · medium"
- 2026-08-19T17:56:09Z — "linux-arm64-musl ffmpeg lock points at glibc conda artifact — `mise.lock:3378` · medium"
- 2026-08-19T18:21:39Z — "musl platform locked to glibc linux-64 conda artifact — `mise.lock` · medium"
PR #385 carried the class THREE times, not once. #391's body says "graphify-labs flagged this on
PR #385" (singular). The PR-439 occurrences are therefore the 4th and 5th, not "the third+".

### R3 — the class IS cross-referenced to #391 in a committed artifact (partial contradiction)
`docs/research/reports/2026-08-21-session-review-synthesis.md:622-635` (F13), committed in
`8929d47f 2026-08-21T01:47:48-05:00`:
  "**The first half is answered — cite #391, do not re-file it.** #391 (OPEN, created 2026-08-19)
   states the cause: the Linux rows are conda-backend portability slots with no live consumer here.
   Independently confirmed: ... 135 `[conda-packages.linux-x64.…]`, 135 musl ..."
That predates the PR-439 reviews (14:14 local), so it is not a disposition OF the PR-439
recurrence — but "the class was left un-cross-referenced" is too strong as written.

## What SURVIVES (I could not refute these)
- #391 is OPEN — `gh issue view 391 --json state` -> "OPEN".
- The bytes are as described: `mise.lock:2115-2116`
  `[conda-packages.linux-x64-musl."_openmp_mutex-4.5-20_gnu"]` /
  `url = "https://conda.anaconda.org/conda-forge/linux-64/_openmp_mutex-4.5-20_gnu.conda"`.
- No cross-reference of the PR-439 recurrence anywhere I can reach:
  - #391 GraphQL timelineItems[CROSS_REFERENCED,REFERENCED,CONNECTED] totalCount = **0**.
    CONTROL ARM: same query, #381 -> 6, #437 -> 3, #418 -> 1, #440 -> 0. The probe discriminates.
  - PR #439 issue comments (236 lines): 0 musl, 0 "#391". CONTROL: 16 'coderabbit' hits.
  - PR #439 inline review comments (15 rows): 0 graphify-labs rows at all.
  - Transcript of the round that OWNED PR #439 (`e159128a…jsonl`, tool-sync-0821 = 1,774 hits):
    `grep -oc musl` = 55 but every hit is `mise lock` progress output or a lockfile diff;
    `grep -oc 'graphify-labs'` = **0** — that session never fetched the bot review bodies.
    `grep -oc '391'` = 80, all incidental (timestamps, token counts, uuids).
  - No issue created 2026-08-21/22 cites #391 or os_filter (`gh search issues ... os_filter` -> []).

## CONTRADICTS finding 18 (same miscount, shared root)
`awk '/^=== /{r=$2} /httpx2/{print r}' gl439.txt | sort | uniq -c` ->
  3  2026-08-21T20:17:01Z
  2  2026-08-21T20:45:37Z
i.e. httpx2 appears in **2** of the 3 graphify-labs reviews, not 3. Review 1 (19:14:33Z) has only
two findings, and neither is httpx2 (`sed -n '1,71p' | grep '^- \*\*'`). Findings 18 and 19 both
report "3 reviews" for a finding that appears in 2 — the lane appears to have counted
graphify-labs' three REVIEWS and attributed every finding to all three.
