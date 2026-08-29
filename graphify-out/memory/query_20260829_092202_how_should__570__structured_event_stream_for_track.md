---
type: "query"
date: "2026-08-29T09:22:02.575126+00:00"
question: "How should #570 (structured event stream for trackers.py) be implemented, and does the fable-orchestrator review-routing table actually work as declared for a codex-authored diff?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should #570 (structured event stream for trackers.py) be implemented, and does the fable-orchestrator review-routing table actually work as declared for a codex-authored diff?

## Answer

### #570 — the research CLI emits on the structured event stream

Converted `python/src/kb_setup/research/trackers.py`'s 4 `print()` sites in
`main()` to `kb_setup.events.say/warn/fail`, carrying `adapter`/`repo`/`term`
(the latter two truncated unconditionally)/`duration_s`/`outcome`/`path`
fields. Landed as PR #594 (`fb94a26`, two commits: `249b5f16` initial
conversion, `c759500` fix-round), then the chain-file removal as PR #595
(`3e78e8b`).

Two rounds of premise verification caught real defects before implementation:
converting the stderr prints to `events.fail` adds an unavoidable `"ERROR: "`
prefix (no route through the sink layer is unprefixed at WARNING/ERROR), which
the ticket's "byte-identical" acceptance criterion hadn't anticipated — fixed
by scoping "byte-identical" to the stdout/INFO path only and updating exactly
2 test assertions. `codex-implementer`'s first dispatch then correctly
dissented: "repo/term are bounded" only held on the `ok` outcome, since
`_bad_request` — the validator — runs first inside `search()`, so on the
`bad_request` outcome they're exactly the values that FAILED validation.
Fixed by truncating unconditionally on every outcome rather than narrowing
the claim.

Two SEPARATE cold-review passes ran on this diff. First, an Opus cold review
of `249b5f16` (run before realizing this repo's own routing table applied)
raised 11 findings (3 P2 + 8 P3); 3 were confirmed real by the architect's
refutation pass and fixed in the `c759500` fix-round: a missing `outcome`
field on one event, `Rc.NOT_RUN` silently collapsed into a generic `"error"`
(losing this repo's own doctrine distinction between "never asked" and
"answered no"), and an off-by-one truncation bound (200 vs the actually-valid
201 chars). Second, the OFFICIALLY-routed cold lane (`antigravity:review`,
per `kb-review`'s own table — see below) reviewed the final diff twice (once
on `249b5f16..c7595007`, once on the full `origin/main..HEAD` range) and
raised 4 more findings total; every one was refuted with a direct arm (Python
enum identity, `JsonlSink`'s `default=str` handling `Path`, `HumanSink`'s
no-prefix-at-INFO behavior, a pre-existing constant outside diff scope) — so
the fix-round introduced nothing new.

Outcome: **useful**. This is the first ticket in the #569–#589 chain worked
end-to-end through the full fable-orchestrator flow (premise-verifier →
codex-implementer → cold review → refutation → fix-round → ship/land) in one
session, and it surfaced a real gap in this repo's own tooling: the review
skill's default cold-lane routing assumed a Claude author, when this repo's
`.claude/CLAUDE.md` fixes the implementation lane to `codex` — meaning the
correct cross-family cold lane is `antigravity:review`, not another `codex`
instance or an unconditional Opus fallback. That routing table already exists
in `kb-review`'s SKILL.md; it just hadn't been exercised this round until now.


## Outcome

- Signal: useful
