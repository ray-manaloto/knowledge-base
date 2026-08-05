---
type: "query"
date: "2026-08-04T21:44:59.847354+00:00"
question: "Does a cold cross-family review lane find defects that same-family lanes miss, and what class are they?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does a cold cross-family review lane find defects that same-family lanes miss, and what class are they?

## Answer

A cold cross-family review lane found 2 real defects in code that TWO Claude review lanes had already passed, and it found both by executing probes against live git rather than by reading the diff. This is a measurement about review METHOD, not about lane identity.

Round 1 on kb-session-state (issue 144) was Standards + Spec, both Claude: 8 findings, all real. Round 2 was one cold lane from a different model family (codex-reviewer, OpenAI) reviewing by ref with no design context. It found 3 more:

1. An unborn branch was reported as unreadable. "git rev-parse --abbrev-ref HEAD" exits 128 on a repo with no commits yet while STILL printing HEAD to stdout, so trusting only its rc turned a knowable branch into the module's could-not-be-asked state. The lane ran the real gather() against a live unborn repo and showed COULD NOT READ printed beside a correctly-read staged file list. The fix is to try "git symbolic-ref --short HEAD" first, which answers rc=0 there and fails when detached, so the two commands are complementary.

2. A merge conflict was indistinguishable from an ordinary MM. git-status spells an unmerged path seven ways (DD AU UD UA DU AA UU) and none of those letters means "nothing here", so every one fell through to the generic staged and unstaged tests and was reported as BOTH. A reader mid-conflict would conclude the file needs re-staging when nothing can be committed at all.

3. pr.checks_state ignored the repo root it was handed and ran gh in the process cwd. Latent, not reachable from the shipped task; fixed additively.

THE GENERALISABLE LESSON: a module built entirely around not collapsing states can still collapse them in the OPPOSITE direction. Every guard in kb_setup.session_state exists so an unchecked claim never renders as a checked one. Defect 1 was a CHECKED ANSWER being discarded as unknown. Both directions are the same bug, and only the first direction had been designed against.

SECOND LESSON, a regression not a discovery: the CPython bytecode cache defect (a .pyc is validated by source mtime in whole SECONDS plus source size, so two same-size mutants written inside one second make pytest import the previous arm's bytecode) hit a THIRD mutation harness. Harness 1 (issue 145) had the fix; harness 2 (issue 146) regressed it and recorded the regression; harness 3 (issue 144, this round) regressed it again. The issue-146 report closed by predicting exactly this: "if a third harness is written, it should import this one rather than restate it." Writing the lesson down has now failed twice consecutively, so the remedy is structural, filed as issue 160: make the harness a kb_setup module with a test. The false SURVIVAL is the safe direction because it makes you look; the same mechanism produces a false DEATH, which makes an entire run worthless while reading green.

THIRD LESSON: a fixture can be unable to exhibit the harm it targets. The rename arm nearly shipped as a false pass. Probed bytes show "R  zz-new-name.txt NUL old-name.txt NUL A  zzz-after.txt NUL"; tracing the unfixed parse, the un-consumed origin field becomes a SPURIOUS entry while the later path still parses correctly, so the intuitive assertion "is the later path still staged?" passes with the bug present. Assert the buckets whole instead.

Evidence: 20 of 20 mutation arms died, control green, restored green. Shipped as PR 161, merged 4a5ab968aceb.

## Outcome

- Signal: useful