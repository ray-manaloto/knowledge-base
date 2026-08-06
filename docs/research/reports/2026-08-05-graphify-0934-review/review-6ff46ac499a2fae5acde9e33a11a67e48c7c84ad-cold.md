# Fix-round record — 6ff46ac499a2fae5acde9e33a11a67e48c7c84ad

Round 2 reviewed e1c7044021f7d1b3b4ad177c3b90272e4799c878; see
`review-e1c7044021f7d1b3b4ad177c3b90272e4799c878-cold.md` for the findings
(4: 2 P1, 2 P2). Round 1 reviewed 4ca3d6411882cfe9fe75b0d977b9d0d668f75e59;
see `review-4ca3d6411882cfe9fe75b0d977b9d0d668f75e59-cold.md` (3 findings:
1 P1, 2 P2). The two-round bound is spent.

No lane re-ran against 6ff46ac499a2fae5acde9e33a11a67e48c7c84ad. Verification
for the fix commit is the local gates, all read from file-recorded rc, none
from a piped tail:

- `mise run lint` rc=0 (hk check --all, includes agnix via lint-docs run
  separately: rc=0)
- `mise run test` (full suite via `uv run pytest tests/ -q`) rc=0
- `uv run ruff check python/src tests` — All checks passed
- `uv run ty check python/src tests` — All checks passed

Round-2 finding dispositions in 6ff46ac499a2fae5acde9e33a11a67e48c7c84ad:

- P2 (gate blocks docs-mirror updates): FIXED — gate moved from the cli
  dispatch to `graph.update`'s code-kind branch; both arms tested.
- P2 (captured_at format unvalidated): FIXED — YYYY-MM-DD enforced, null
  grandfathered with its harmless-direction rationale; three test arms.
- P1 (per-chunk vs per-file capture dates): MEASURED AND DEFERRED — the live
  corpus has exactly 2 cross-chunk source_file intersections, both the
  intended supersession, zero date inversions; per-file supersession cannot
  be expressed by replay order alone, so the detector belongs to #189 (scope
  widened there with the measurement probe).
- P1 (legacy bare-basename identities coexist with the new form): CONFIRMED
  BY THE LANE AND DEFERRED to #187 — re-extraction must retire/migrate old
  chunks' claims for a page, which is that issue's process; recorded there.
