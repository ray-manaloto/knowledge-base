---
type: "query"
date: "2026-09-09T15:49:26.068103+00:00"
question: "Does the codex review banner's model line confirm which model performed the review?"
contributor: "graphify"
outcome: "corrected"
correction: "The banner is NOT evidence of which model reviewed. It prints the SESSION model, which ~/.codex/config.toml:2 pins to gpt-6-astra on this machine, so all three arms (Astra, Sol control, and a bogus slug) printed the identical line. `review_model` selects the sub-agent that `start_review_conversation` spawns (core/src/tasks/review.rs:123-127), which the banner never names, and the session JSONL records only the session model. What DOES prove the key is read is the FAIL arm: `-c review_model=\"definitely-not-a-real-model-xyz\"` exits 1 with the API quoting the slug back. By contrast the banner's `sandbox:` line IS a valid observable — the review sub-agent clones the session sandbox, and it flipped from danger-full-access to read-only when `-c sandbox_mode=` was passed (SessionFlags precedence 30 beats the user config's 20, config_layer_source.rs:38-47). Lesson: a banner that names a value you pinned globally can never discriminate; arm the mechanism with an input that must FAIL.\n"
---

# Q: Does the codex review banner's model line confirm which model performed the review?

## Answer

The research lane and the implementer's first pass both cited the `codex review` banner line `model: gpt-6-astra` as confirmation that the Astra model performed the review.


## Outcome

- Signal: corrected
- Correction: The banner is NOT evidence of which model reviewed. It prints the SESSION model, which ~/.codex/config.toml:2 pins to gpt-6-astra on this machine, so all three arms (Astra, Sol control, and a bogus slug) printed the identical line. `review_model` selects the sub-agent that `start_review_conversation` spawns (core/src/tasks/review.rs:123-127), which the banner never names, and the session JSONL records only the session model. What DOES prove the key is read is the FAIL arm: `-c review_model="definitely-not-a-real-model-xyz"` exits 1 with the API quoting the slug back. By contrast the banner's `sandbox:` line IS a valid observable — the review sub-agent clones the session sandbox, and it flipped from danger-full-access to read-only when `-c sandbox_mode=` was passed (SessionFlags precedence 30 beats the user config's 20, config_layer_source.rs:38-47). Lesson: a banner that names a value you pinned globally can never discriminate; arm the mechanism with an input that must FAIL.
