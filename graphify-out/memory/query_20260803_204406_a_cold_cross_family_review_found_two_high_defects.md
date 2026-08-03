---
type: "query"
date: "2026-08-03T20:44:06.718979+00:00"
question: "A cold cross-family review found two HIGH defects in already-shipped, already-gated code. What made it work?"
contributor: "graphify"
outcome: "useful"
---

# Q: A cold cross-family review found two HIGH defects in already-shipped, already-gated code. What made it work?

## Answer

It RAN the code instead of reading it. Both HIGH findings on PR #139 were in currency/skill.py, from an earlier commit that had already passed its own review. (1) The post-install repair ran a batch "git checkout --" over several paths, discarded the rc, and never re-read the tree. That command is ATOMIC across its pathspecs, so one unresolvable path reverts NOTHING -- yet the result came back listing those paths as repaired and the note said "repaired", over a file still sitting there damaged. (2) An installer that failed partway left its damage in the working tree with only "installer failed" in the note, even though the pre-flight had proved the tree started clean. The bitter detail: the code's own comment already described that atomicity and the narrowing meant to dodge it. The surviving case was reachable because "git status --porcelain" reports untracked files with a leading question-mark pair, and the narrowing fed those straight back into the argv. Round 2 verified the fixes by replaying its round-1 repros, constructing three edge cases nobody had written (deleted file, both paths dirty, batch-succeeds-outright), and mutating the fix back to confirm the new tests catch the regression they name. The lesson is not that the reviewer is smarter. It does not share the author's assumption about what the code does, and it tests rather than reasons. Two corollaries that cost real effort: it also reported a "pre-existing failure" no gate ever sees, because it ran pytest directly while every gate goes through the mise task (issue #140); and writing THIS memory with an unquoted shell argument executed the backticked commands inside it and spliced a pytest transcript into the corpus, which had to be deleted and redone -- pass prose through a quoted heredoc, never an inline argument.

## Outcome

- Signal: useful