---
type: "query"
date: "2026-08-19T23:53:41.668285+00:00"
question: "Should mise.toml's min_version.hard move to 2026.8.9 alongside soft, and what becomes of soft?"
contributor: "graphify"
outcome: "corrected"
correction: "A file's own explanatory comment is a DOCUMENTED DOCTRINE, not a settled fact —\nand the owner may overrule it.\n\nmise.toml's comment states that `min_version.hard` is a correctness floor\n(\"below that there are known-bad behaviours\"), that `soft` tracks \"the version\nthis repo has actually been verified against\", and that \"keep soft > hard or\nsoft is inert\". Reading that comment produces a confident recommendation: hard\nshould not move. Ray moved it anyway, and then kept the now-inert `soft` key\nrather than deleting it.\n\nTwo durable lessons:\n\n1. When a comment argues for a position, present it as the repo's stated\n   doctrine WITH its consequence, then let the owner decide — do not report the\n   comment's conclusion as the answer. The comment was written by a past\n   session, not by the owner.\n2. A key kept deliberately inert is indistinguishable from a defect unless the\n   comment beside it SAYS it is deliberate. This exact file has already had a\n   cold lane catch its comment drifting from its value. The comment rewrite is\n   part of the change, not follow-up work.\n"
---

# Q: Should mise.toml's min_version.hard move to 2026.8.9 alongside soft, and what becomes of soft?

## Answer

This round (2026-08-19 d) was a short close-out: `/kb-resume` reconciled
handoff-c against the repo, `mise run kb-land -- 402` merged the SIXTH-ADDENDUM
commit `4c0ed9603f16` (main is now `7bfb9a211ee0`), and Ray answered the two
open `min_version` questions that handoff-c had left unresolved.

The reconciliation found ONE disagreement, and it is a class worth naming: a
handoff written by `/clear-prep` cannot describe the PR that `/clear-prep`
itself then opens. Handoff-c said "no background tasks left running" and listed
no open PR, but PR #402 — carrying that very handoff's own closing commit — was
open and mergeable when the next session read it. `kb-handoff-check` reported
37 OK / 0 broken, because a citation check cannot see an omission that happened
after the file was written. `/kb-resume`'s repo cross-check is what caught it,
which is the argument for that skill checking rather than believing.

Ray's rulings, verbatim in effect:

1. `min_version.hard` MOVES to 2026.8.9 alongside soft, overriding mise.toml's
   own documented doctrine that `hard` is a correctness floor (2026.7.14, where
   task-freshness fixes #11288/#11296 landed) and `soft` is the last verified
   version. The concern that this makes `soft` unobservable was raised and Ray
   reaffirmed the choice.
2. `soft` STAYS at 2026.8.9 rather than being deleted — deliberately inert,
   retained as a slot in case the two-tier split returns. The comment in
   mise.toml must be rewritten to say so, or the file will read as a defect to
   every future reviewer and to the cold lane that already caught this comment
   drifting from its value once.
3. Next round scope: mise 2026.8.9 + hk 1.56.0 ONLY, plus filing the two
   findings this round surfaced and nobody filed.


## Outcome

- Signal: corrected
- Correction: A file's own explanatory comment is a DOCUMENTED DOCTRINE, not a settled fact —
and the owner may overrule it.

mise.toml's comment states that `min_version.hard` is a correctness floor
("below that there are known-bad behaviours"), that `soft` tracks "the version
this repo has actually been verified against", and that "keep soft > hard or
soft is inert". Reading that comment produces a confident recommendation: hard
should not move. Ray moved it anyway, and then kept the now-inert `soft` key
rather than deleting it.

Two durable lessons:

1. When a comment argues for a position, present it as the repo's stated
   doctrine WITH its consequence, then let the owner decide — do not report the
   comment's conclusion as the answer. The comment was written by a past
   session, not by the owner.
2. A key kept deliberately inert is indistinguishable from a defect unless the
   comment beside it SAYS it is deliberate. This exact file has already had a
   cold lane catch its comment drifting from its value. The comment rewrite is
   part of the change, not follow-up work.
