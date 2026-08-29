---
type: "query"
date: "2026-08-28T22:16:26.876569+00:00"
question: "What did the 2026-08-28 aggregated-research round actually establish?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the 2026-08-28 aggregated-research round actually establish?

## Answer

The round was rescoped mid-flight by Ray: the aggregated-research plugin's CLI
is 1 of 24 instructed capabilities, not a nearly-finished tool, and two prior
rounds had gone into DELIVERY (mise confinement, container acceptance,
agent-driven install, a leaked env var) rather than the product.

What the round produced instead of more delivery work:

- A diagnosis with a control arm: `CLAUDE_PLUGIN_DATA` leaks another plugin's
  data dir into the Bash tool, so the plugin CLI refused to start. Fixed in the
  marketplace repo (PR #5), armed both directions.
- The recovered spec. It was never lost so much as never written down durably:
  every slice's spec lived in a session scratchpad. Five verbs were decided,
  one exists. Rungs 1-3 were done; rung 4 was never started.
- Spec #568 and 21 tickets #569-#589, sized to one session each.
- #574 built and cold-reviewed: a tracked chain file plus `kb-setup
  next-ticket`, so /clear-prep names the next ticket instead of inferring one.

The durable finding: in this project, a decision survives if and only if it
reaches a tracked file. Transcripts, scratchpads and .agent/ all die. Four
artifact pages and the chain file are this round's answer to that, and the
next-ticket task is the mechanism that keeps it true without anyone
remembering to.


## Outcome

- Signal: useful