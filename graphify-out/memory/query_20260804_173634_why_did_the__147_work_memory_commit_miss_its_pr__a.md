---
type: "query"
date: "2026-08-04T17:36:34.180374+00:00"
question: "Why did the #147 work-memory commit miss its PR, and what is the actual ordering rule?"
contributor: "graphify"
outcome: "corrected"
correction: "The rule is BEFORE kb-ship, not before kb-land — and I misread my own correct memory entry saying so while doing it again on PR #156. kb-ship is what PUSHES, so the PR head is fixed the moment ship runs and anything committed afterwards is not in the PR no matter how long you wait to land. Running kb-remember after ship but before land FEELS safe because the merge has not happened; it is not. Recovery is worse than it looks because kb-land SQUASH-merges: the reviewed SHA stops being an ancestor of main, and review.EXEMPT_PATHS — the mechanism that exists so a round can commit its own graphify-out/memory/** under an ancestor's receipt — needs that ancestry, so landing a stranded file costs a fresh review round for one prose file. The order is: review -> receipt -> kb-remember + kb-reflect -> commit what they wrote -> kb-ship -> kb-land, with NO safe window after ship. If a commit is stranded, put a branch on it immediately (git branch <name> <sha>, the reflog expires) and carry it into the next round's branch. Generalisable shape: when a rule names a specific STEP, the step is the load-bearing part, not the phase — 'before shipping' and 'before landing' read as the same intent and are one irreversible action apart."
---

# Q: Why did the #147 work-memory commit miss its PR, and what is the actual ordering rule?

## Answer

Before kb-ship, not before kb-land. Hit 2026-08-04 on PR #156 while holding a
work-memory entry that says exactly this, which is what makes it worth
re-recording: the entry was correct and I still misread it.

kb-ship is what PUSHES. So the PR head is fixed at the moment ship runs, and
anything committed after that is not in the PR no matter how long you wait
before landing. Running kb-remember after kb-ship but before kb-land FEELS safe
because the merge has not happened yet; it is not. kb-land then merges pinned to
the SHA ship pushed, and the memory commit is left behind on a branch.

Recovery is worse than it looks, and the reason is the squash. kb-land
squash-merges, so the reviewed SHA stops being an ancestor of main — and
review.EXEMPT_PATHS, the mechanism that exists precisely so a round can commit
its own graphify-out/memory/** artifacts under an ancestor's receipt, needs that
ancestry. Landing the stranded file afterwards therefore costs a whole fresh
review round for one prose file. The escape hatch is spent by the same action
that creates the need for it.

Two operational rules. First, the order is: review -> receipt -> kb-remember +
kb-reflect -> commit what they wrote -> kb-ship -> kb-land, and there is no safe
window after ship. Second, if a commit does get stranded, put a branch on it
immediately (git branch <name> <sha>) — a deleted branch leaves the commit
reachable only through the reflog, which expires. Then carry it into the next
round's branch, where it rides the exempt path normally, rather than opening a
PR for it.

The generalisable shape: when a rule names a specific step, the step is the
load-bearing part, not the phase. "Before shipping" and "before landing" read as
the same intent and are one irreversible action apart.

## Outcome

- Signal: corrected
- Correction: The rule is BEFORE kb-ship, not before kb-land — and I misread my own correct memory entry saying so while doing it again on PR #156. kb-ship is what PUSHES, so the PR head is fixed the moment ship runs. Recovery is worse than it looks because kb-land SQUASH-merges: the reviewed SHA stops being an ancestor, and review.EXEMPT_PATHS needs that ancestry. The order is review -> receipt -> kb-remember + kb-reflect -> commit -> kb-ship -> kb-land, with NO safe window after ship. When a rule names a specific STEP, the step is the load-bearing part, not the phase.