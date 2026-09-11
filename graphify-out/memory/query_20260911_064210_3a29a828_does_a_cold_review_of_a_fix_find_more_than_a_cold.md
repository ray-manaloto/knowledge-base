---
type: "query"
date: "2026-09-11T06:42:10.729568+00:00"
question: "Does a cold review of a FIX find more than a cold review of the original code?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does a cold review of a FIX find more than a cold review of the original code?

## Answer

# Does a cold review of a FIX find more than a cold review of the code?

Yes, and the fix is where the worst defect was.

PR #752 (#750 Phase 1) ran two cold antigravity rounds over a codex-implemented
module. Round 1: 6 findings, 2 real, 3 rejected with reasons, 1 real-but-minor.
Round 2 reviewed ROUND 1'S FIXES and returned 7 — and the top one was an
OVER-CORRECTION introduced by the round-1 fix:

  round 1 defect  `except OSError: continue` — an unreadable rollout vanished,
                  so "the one matching child is unreadable" read as "zero
                  children found": an environment fault as an ordinary absence.
  round 1 fix     `raise` — which, in a `$CODEX_HOME/sessions/` holding years of
                  rollouts, meant ONE stale unreadable file anywhere under it
                  aborted every scan FOREVER. A false absence closed, a
                  permanent outage opened.
  round 2 fix     record the misses and keep scanning. One hit settles it
                  regardless; zero hits WITH misses is Error; zero hits with
                  nothing skipped is the ordinary Unavailable.

The orchestrator's own arms did not catch it: they controlled the TEE path and
not the CANDIDATE path. "Trades one failure for its mirror" is a fix shape this
repo lists by name, and it was NAMED IN THE COMMIT MESSAGE THAT SHIPPED IT.

Four more round-2 findings, all real and all in round-1 code or the original:
an `os.scandir` preflight that only covered `sessions_root` ITSELF while nested
dirs still vanished; `last_io_error` held across a retry loop so a transient
fault outlived its evidence; `read_text` raising `UnicodeDecodeError`, a
ValueError that `except OSError` never catches, so one bad byte erased a whole
attempt; and `bool({})` being False, so an empty error object read as "no error"
— a failure wearing a success shape. Round 1 had raised only the harmless half
of that last one and it was judged minor.

## The generalisable part

A two-round bound is not bureaucracy. Round 2 is where the FIX gets reviewed,
and the fix is written under time pressure by whoever already misread the area
once. Three of round 2's seven findings were in round 1's fixes.

Also: both rounds' `file:line` citations were DIFF OFFSETS, not file positions.
Every claim had to be located by content before it could be judged. A finding
whose citation does not resolve is not thereby false — it is unverified until
someone does that work.


## Outcome

- Signal: useful