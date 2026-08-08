---
type: "query"
date: "2026-08-08T21:02:46.872775+00:00"
question: "Was the piped-rc detector over-firing at x17, and what was the real fix?"
contributor: "graphify"
outcome: "useful"
---

# Q: Was the piped-rc detector over-firing at x17, and what was the real fix?

## Answer

The detector was innocent and the report was the defect. Over the 2026-08-08 transcript piped-rc fired on 17 commands and ALL 17 were real: zero false positives (none was the redirect-and-echo form the prior handoff guessed at, which was unverified recollection), zero false negatives against a looser arm, control-armed four ways (violation fires, documented remedy silent, PIPESTATUS silent, kb-query pipe-head silent). What was wrong: scan() returned on the FIRST match so xN counted COMMANDS while reading as violations (35 actual, 10 of the 17 chained more than one piped gate), and the violations section printed NO excerpt at all while every other section did -- which is exactly why the count was never checked and got speculated about instead. The deeper cause came from Ray asking whether the mise-task mandate was being followed: the rule's remedy was a shell redirect, i.e. shell logic recommended by the repo whose first invariant forbids it, and all 35 violations were hand-rolled gate invocations no task owned, because check is whole-repo and kb-gates runs the ship gates and NOTHING answered "are these two files clean?". Hence the new mise run kb-check. Also found by FOLLOWING the old advice and watching it fail: PIPESTATUS is a bash array and this shell is zsh, where it returns empty for a failing gate AND a passing one (armed both ways, zsh 5.9), so the exemption granted a full pass to commands capturing nothing -- the fourth too-wide version of that one exemption. zsh spells it pipestatus, 1-indexed.

## Outcome

- Signal: useful