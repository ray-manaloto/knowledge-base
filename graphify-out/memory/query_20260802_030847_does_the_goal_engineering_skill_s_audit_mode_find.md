---
type: "query"
date: "2026-08-02T03:08:47.886581+00:00"
question: "Does the goal-engineering skill's audit mode find defects that the author's own step-6 self-audit missed?"
contributor: "graphify"
outcome: "corrected"
correction: "An author's own step-6 self-audit is NOT sufficient, and the reason is structural rather than one of care: three of the five defects the audit mode found were interactions with TRACKED-BUT-UNFIXED open issues, which are invisible from the goal text alone. So a goal audit must read the OPEN ISSUE LIST. The five on the Settled pair: (1) invoking the harness by Workflow name resolves to a STALE CACHED copy (#13), so the round would have reported HARNESS-RAN about a pre-patch script — use scriptPath; (2) no landing existed for a legitimate negative, so a refuted fix could only exit via GOAL-BLOCKED, pressuring the agent to CLAIM it (#65's Arm-C defect verbatim) — add a LANDINGS clause admitting REFUTED/UNREACHABLE/DECLINED; (3) 3974/4000 chars is tighter than the 3941 #65 records as unamendable — reserve an amendment budget; (4) a PASS gate of 'lint rc=0' is green about nothing for files lint cannot see (#94); (5) goal and rider carried different truncation sentinels."
---

# Q: Does the goal-engineering skill's audit mode find defects that the author's own step-6 self-audit missed?

## Answer

Yes, five on the Settled pair, three from live open issues that a self-audit had no reason to consult. (1) The rider told P5 to invoke the harness by Workflow name, which #13 proves resolves to a STALE CACHED copy -- so the round would have reported HARNESS-RAN about a pre-patch script, reproducing the committed-is-not-proven error the round exists to correct. Fix: scriptPath, plus paste the tool result's script path. (2) No landing existed for a legitimate negative, so a refuted #101 fix could only exit via GOAL-BLOCKED, pressuring the agent toward CLAIMING the fix -- #65's Arm-C defect verbatim. Fix: a top-level LANDINGS clause admitting =REFUTED/=UNREACHABLE/=DECLINED. (3) The goal sat at 3974/4000, TIGHTER than the 3941 goal #65 records as unamendable; cut to 3820 to reserve an amendment budget. (4) P4 adds sources/<key>.manifest, which lint cannot see (#94), so PASS gate lint rc=0 would be green about nothing. (5) Goal and rider carried DIFFERENT TRUNCATION sentinel formats. Lesson: read the OPEN ISSUE LIST during a goal audit -- three of five defects were interactions with tracked-but-unfixed defects, invisible from the goal text alone.

## Outcome

- Signal: corrected
- Correction: An author's own step-6 self-audit is NOT sufficient, and the reason is structural rather than one of care: three of the five defects the audit mode found were interactions with TRACKED-BUT-UNFIXED open issues, which are invisible from the goal text alone. So a goal audit must read the OPEN ISSUE LIST. The five on the Settled pair: (1) invoking the harness by Workflow name resolves to a STALE CACHED copy (#13), so the round would have reported HARNESS-RAN about a pre-patch script — use scriptPath; (2) no landing existed for a legitimate negative, so a refuted fix could only exit via GOAL-BLOCKED, pressuring the agent to CLAIM it (#65's Arm-C defect verbatim) — add a LANDINGS clause admitting REFUTED/UNREACHABLE/DECLINED; (3) 3974/4000 chars is tighter than the 3941 #65 records as unamendable — reserve an amendment budget; (4) a PASS gate of 'lint rc=0' is green about nothing for files lint cannot see (#94); (5) goal and rider carried different truncation sentinels.