---
type: "query"
date: "2026-09-09T15:49:25.706240+00:00"
question: "How is the cold:codex-astra review variant invoked, when is it used, and what was its first measured duration?"
contributor: "graphify"
outcome: "useful"
---

# Q: How is the cold:codex-astra review variant invoked, when is it used, and what was its first measured duration?

## Answer

cold:codex-astra is a VARIANT of kb-review's single cold slot, not a second lane: review._lane_prefix strips everything after the first colon, so the report path stays review-<sha>-cold.md and `--lanes cold:codex-astra` needs no receipt schema change. It is REQUESTED by name (guidance: past ~20 files or 1,000 changed lines, or two or more interacting guards/gates/modules), only for Claude- or antigravity-authored diffs (still codex family — never in place of cold:antigravity). The exact call: `mise run kb-codex -- --review --base <fixed> --model gpt-6-astra --effort xhigh --sandbox read-only --timeout 3600 --output .agent/kb/review/reports/review-<sha>-cold.md < method.txt`; `--model` becomes `-c review_model=`, `--effort` becomes `-c model_reasoning_effort=`, `--sandbox` becomes `-c sandbox_mode=` (mandatory — without it the review inherits danger-full-access from the user config, do-not.md #13), and kb-codex writes `--output` itself because `codex review` has neither `-m` nor `-o` (#678). Astra may refuse authorized security work (openai/codex 43163 43781 43131 43208 42939) — a refusal is reported verbatim and the lane falls back to cold:codex; never "no findings". First measured duration on a real 12-file/+1,694-line review: 699 s, rc 0, with 1 P1 + 4 P2 real findings — every one demonstrated by a process probe rather than a reading.


## Outcome

- Signal: useful