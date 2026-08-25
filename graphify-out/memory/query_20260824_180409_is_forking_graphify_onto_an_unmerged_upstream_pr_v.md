---
type: "query"
date: "2026-08-24T18:04:09.753840+00:00"
question: "Is forking graphify onto an unmerged upstream PR viable, and what does it actually cost?"
contributor: "graphify"
outcome: "useful"
---

# Q: Is forking graphify onto an unmerged upstream PR viable, and what does it actually cost?

## Answer

Forked graphify to ray-manaloto/graphify carrying upstream PR #2981's `openai-cli`
backend (semantic extraction through the locally authenticated codex CLI), then
rebased it onto upstream v0.9.49 the same day when that release shipped four hours
later and flipped the PR to CONFLICTING.

Six of the PR's seven feature commits replant cleanly onto v0.9.49. Only the
extract-lock does not: it re-indents the whole extract pipeline inside a `with`,
and v0.9.49 rewrote that pipeline. Dropped rather than hand-merged.

Verified against upstream's OWN suite, control-armed:
  ours     15 failed, 5057 passed
  pristine 15 failed, 5019 passed  (v0.9.49, identical 15)
Same failure set, +38 passing — exactly the tests the replanted features add.

The fork's blast radius was five surfaces the fork research did not predict:
a git-locked dependency has no wheel and no sdist (RuntimeIdentity gained
`git_commit`); `_ACCEPTED_GRAPHIFY_URL` hardcoded upstream; a test fixture named
`wheel_sha256` literally instead of following the constant; the semantic corpus
must materialise at its own frozen constants rather than the moving fork base;
and #420 is live — graph_first writes its marker inside the pinned clone.

Baseline re-derived by a real build against the installed fork: detected
429 -> 450, extracted 421 -> 442, gap UNCHANGED at 8 — the check that matters,
since a backend-only addition must not change extraction behaviour.


## Outcome

- Signal: useful