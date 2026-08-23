# Refutation lane — "2.76x token burn increase after compaction at 17:18:24Z"

Session under review: `5ec8da38-160b-4594-9560-c07a86b46f27` (16:57:18.335Z -> 18:17:09Z),
transcript `/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/5ec8da38-160b-4594-9560-c07a86b46f27.jsonl`.

VERDICT: REFUTED.

## 1. The compaction event is unattested (control-armed)

    grep -c '"isCompactSummary":true' 5ec8da38-...jsonl   -> 0
    grep -c '"isCompactSummary":true' 3cd95785-...jsonl   -> >=1   (CONTROL, discriminates)

Control record (3cd95785 line 1574) is the real shape:
"This session is being continued from a previous conversation that ran out of context.
The summary below covers the earlier..."

Target session: zero hits for isCompactSummary / compactMetadata / preCompact / "compact.
Line 148 at 17:18:24 is an ORDINARY user prompt, new promptId 82b92303-b094-4dae-b34a-b85babe91213:
"research and analyze and fix\n2. Noted but untouched: .mcp.json's existing graphify..."
The preceding 3m22s is the gap between turn_duration (17:15:08.595Z) and that prompt - a human typing.

## 2. The counter is a rolling quota, and its resets are not compactions

Immediately-prior session 33c070af (same day, same repo) - zero compaction markers - jumps UP twice:
  15:40:03.945Z  delta=-171035 -> 15000000
  16:10:15.146Z  delta=-30845  -> 14981005   (partial refund, non-round: cannot be a compaction)
Also 33c070af ENDS at 14736660 (16:54:33) while 5ec8da38 STARTS at 14881077 (17:00:25) - the counter
went back up 144,417 between sessions. It is not a per-session context odometer.

## 3. Phase 1's rate is a truncated-window artifact - the true direction is DOWN

First reminder of the session is 14881077 at 17:00:25, but the session began 16:57:18:
  15,000,000 - 14,881,077 = 118,923 tokens spent BEFORE the first observation
  (84% of the phase's spend, excluded by construction).
The transcript's own reset delta states Phase 1's total: 15,000,000 - 14,858,403 = 141,597.
  PHASE1 TRUE: 141,597 tok / 21.1 min (16:57:18 -> 17:18:24) = 6,708 tok/min
  PHASE2      : 172,267 tok / 49.5 min                        = 3,482 tok/min   (reproduces exactly)
=> burn rate FELL 1.93x, not rose 2.76x.

## 4. Idle-gap artifact

Phase 1's 18-min window contains ONE 793.6 s (13.2 min) gap at 17:01:34 -> 17:14:47 = 73% of the window.
Excluding gaps > 60 s:
  Phase 1 active: 19,901 tok / 1.39 min  = 14,289 tok/min
  Phase 2 active: 165,297 tok / 24.83 min = 6,658 tok/min (finding's window); 6,838 full session
=> burn rate FELL 2.1x.

Both corrected measures invert the sign. Only the Phase-2 half of the arithmetic reproduces.

## Cross-findings

- Finding 24 shares the same unattested compaction premise; refuted by the same probe.
- Finding 26 (no context_usage events, only 157x total_tokens_reminder) is CORRECT and is precisely why
  22/24/25 cannot stand - the sole instrument is a rolling quota that resets non-deterministically.
- Finding 23 supplies the real confound: the phase boundary IS a new user task, so any rate difference
  is task composition, not compaction.

## GitHub repos touched

_None._
