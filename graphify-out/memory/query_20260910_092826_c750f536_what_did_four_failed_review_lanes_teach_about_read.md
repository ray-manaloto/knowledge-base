---
type: "query"
date: "2026-09-10T09:28:26.872361+00:00"
question: "What did four failed review lanes teach about reading a lane's silence?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did four failed review lanes teach about reading a lane's silence?

## Answer

A review lane that fails is not a review lane that found nothing — and four
failed in a row before one worked.

`cold:codex-astra` and `cold:codex` both returned `Selected model is at
capacity` (openai/codex 43706), forty minutes apart, after 750KB and 1.1MB of
real work respectively. Two different models, same string: service-side, NOT the
transient class `persistence-gate-retry.md` describes, so retrying a third codex
lane would have been the same probe a third time.

`cold:antigravity` then returned `PERMISSION_DENIED` — it read 72,076 input
tokens, requested the `command` permission, and headless mode auto-denied it, so
NO WORK WAS DONE. The cause was MY prompt telling it to verify by running
things. A no-tools instruction succeeded on the fourth attempt and produced 8
findings, 4 real.

Its documented fixes were both unavailable: a `permissions.allow` rule lives in
`~/.gemini/antigravity-cli/settings.json`, which `do-not.md` #11 forbids
writing, and `--yolo` auto-approves every tool for an external model. The prompt
was the cheaper fix and the correct one.

🔴 THE LANE THAT WORKED STILL REVIEWED A SUBSET AND DID NOT KNOW IT. It reported
"no tests included or modified"; `tests/test_graphify_catalog.py` sat at byte
251,952 of 281,121 in the piped diff. Its silence about the tail is ABSENCE, not
clean — and N findings from a lane that stopped early is indistinguishable from
N findings from one that finished.

And the receipt gate caught something no version check could: `agy` SELF-UPDATED
mid-session. `--version` read 1.1.25 before dispatch and 1.2.0 an hour later,
because 1.2.0 published at 01:43:29Z that morning. `kb-review-receipt` refused
the receipt on the pin/binary disagreement. `agy-delegate` resolves from the
plugin cache, NOT through mise's shim, which is how an unpinned binary reviewed
a repo that pins it.


## Outcome

- Signal: useful