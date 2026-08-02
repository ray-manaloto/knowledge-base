---
type: "query"
date: "2026-08-02T06:59:48.601738+00:00"
question: "Did exercising kb-tool-review.js end-to-end prove the harness, and what did it cost?"
contributor: "graphify"
outcome: "corrected"
---

# Q: Did exercising kb-tool-review.js end-to-end prove the harness, and what did it cost?

## Answer

It ran: 31 agents, 0 errors, 4,589,913 subagent tokens, 46 min, 10 verified / 16 refuted across codegraph and GitNexus. And it wrote NOTHING to docs/research/reports/. Three compounding defects: a workflow script has no filesystem access so the script's reportDir was only ever interpolated into agent prompts; researchers were pointed solely at gitignored .agent/; and the return omitted the unverified and reports:[] fields its own header documented, so a 16,249-char synthesis existed only in the run result. Its own invocation example said name:, the #13 stale-cache trap in documentation form. 'Committed is not proven' was exactly right — and the incremental-write rule is the only reason the researcher output survived.

## Outcome

- Signal: corrected