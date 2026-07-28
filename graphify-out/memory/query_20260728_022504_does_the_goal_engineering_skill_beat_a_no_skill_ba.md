---
type: "query"
date: "2026-07-28T02:25:04.557746+00:00"
question: "Does the goal-engineering skill beat a no-skill baseline in this repo?"
contributor: "graphify"
outcome: "corrected"
---

# Q: Does the goal-engineering skill beat a no-skill baseline in this repo?

## Answer

No measurable gap: 92% vs 92%, delta 0.00, 24/26 each, n=1 per cell. The skill's real contribution is procedural — the baseline never reached for kb-goal-check — not defect-finding, where the baseline is already at ceiling. Critical condition: the baseline is NOT naive Claude, it runs with every eager rule loaded and a worked goal+rider exemplar in docs/goals/ that it demonstrably cribbed the EVIDENCE RULE from. Two of the nine eval-2 assertions do not discriminate because they pass on a fix that never names the defect. Time/tokens were not captured at all.

## Outcome

- Signal: corrected