---
type: "query"
date: "2026-07-30T22:32:37.010782+00:00"
question: "Is a SKILL.md description over 1,536 chars the only skill-listing truncation?"
contributor: "graphify"
outcome: "corrected"
correction: "The rule attributed all skill-listing truncation to a per-description 1,536-char cap, which is the mechanism LEAST likely to bite this repo."
source_nodes: ["ccskills_listing_budget_is_one_percent_of_context", "ccskills_desc_cap_is_combined_and_configurable"]
---

# Q: Is a SKILL.md description over 1,536 chars the only skill-listing truncation?

## Answer

NO — and md-size-budgets.md said it was 'the only real cliff a repo here can hit' until 2026-07-30. There are TWO mechanisms. (1) A per-entry cap of 1,536 chars over the COMBINED description + when_to_use text, configurable via skillListingMaxDescChars. (2) A whole-listing budget scaling at 1% of the model's context window; on overflow Claude Code 'drops descriptions starting with the skills you invoke least'. So a short description can lose its keywords purely because OTHER skills exist, with nothing about that skill having changed. The listing always keeps every skill NAME, so the symptom presents as a badly-written description rather than a full budget — and no per-skill edit would fix it. With 7 project skills plus 5 enabled plugins, (2) is the one this repo can actually hit. Measure with /doctor and the /context Skills row (post-budget size), not by reasoning.

## Outcome

- Signal: corrected
- Correction: The rule attributed all skill-listing truncation to a per-description 1,536-char cap, which is the mechanism LEAST likely to bite this repo.

## Source Nodes

- ccskills_listing_budget_is_one_percent_of_context
- ccskills_desc_cap_is_combined_and_configurable