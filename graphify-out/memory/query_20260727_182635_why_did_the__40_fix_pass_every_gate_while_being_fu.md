---
type: "query"
date: "2026-07-27T18:26:35.396424+00:00"
question: "Why did the #40 fix pass every gate while being fully revertible, and what did cold review catch that adversarial refutation did not?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did the #40 fix pass every gate while being fully revertible, and what did cold review catch that adversarial refutation did not?

## Answer

The fix moved four call sites to graphify_exe() but the only assertion touched was Path(argv[0]).name == 'graphify', which is TRUE of the bare name — so reverting the entire fix left the suite green (proved by re-running the reviewer's sed mutation). Lesson: when a change replaces a bare command name with a resolved path, a basename assertion cannot discriminate; the sentinel must be a path whose basename is still the command, and the whole argv[0] compared. Second lesson: the two review modes found DIFFERENT defect classes. Adversarial refutation (told to refute a claim) found semantic divergences - build vs stamp reading different binaries, cwd-sensitivity of 'mise where'. Cold review (given only the diff) found structural ones the refuters never looked at: a destructive tmux kill-server ordered BEFORE its own preflight, a missing found-is-None branch fabricating 'reports None', and the missing regression test itself. Run both; neither subsumes the other. Third: a repair step that runs before its own validation is an outage with no rollback.

## Outcome

- Signal: useful