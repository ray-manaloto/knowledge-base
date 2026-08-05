---
type: "query"
date: "2026-08-05T00:17:02.025827+00:00"
question: "Does implementing an acceptance criterion literally protect you, when the ticket body says something different?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does implementing an acceptance criterion literally protect you, when the ticket body says something different?

## Answer

Yes, and the finding was in the READING of the ticket rather than in the code.

#149 asked that kb-ship refuse a branch whose handoff has broken citations. The
issue BODY said "skips when THE NEWEST handoff describes a different branch";
acceptance criterion 1 said "the newest handoff WHOSE RECORDED BRANCH EQUALS the
current branch". Those are different rules. It was built to the criterion — scan
handoffs newest-first for a branch match — and every gate passed, 15 of 15
mutation arms died, and a two-axis review's Standards lane found nothing wrong
with it.

The Spec lane ran both rules over the real corpus. .agent/plans/ is append-only
and handoffs cite paths, so an old handoff ROTS as unrelated commits delete what
it named. Scanning for a match refuses 8 of the 21 branches this repo's 35
handoffs record, every one on a handoff 1-7 days stale. Newest-only refuses 0.
The scan did not remove the harm the ticket exists to prevent — a healthy ship
blocked by another session's staleness — it relocated it one file back, and it
grows monotonically with the handoff count.

Three durable lessons.

1. WHEN A TICKET'S BODY AND ITS ACCEPTANCE CRITERIA DISAGREE, THAT IS THE
   FINDING, NOT A FORMATTING PROBLEM. Both were written by the same person on the
   same day and both read as authoritative. Picking one silently is how a round
   ships a defect with a green audit trail. Measure both readings against real
   data, implement the one that survives, and AMEND the loser on the issue with
   the measurement attached.

2. A TICKET'S STATED JUSTIFICATION CAN FAIL ITS OWN CHECKER. #149 justified
   itself with a handoff that "pinned a commit six behind" and "asserted no
   review receipt". Neither is a FAIL under kb-handoff-check: a stale-but-valid
   SHA resolves and the receipt line is prose. Every FAIL in the corpus is a
   PATH. So the harm class was path rot over time, not stale claims — and the fix
   that follows from the real harm class is different from the one that follows
   from the stated one. Re-derive the motivating example before designing for it.

3. A SURVIVING MUTATION ARM IS NOT ALWAYS A TEST GAP. Flipping `*?` to `*` in the
   branch regex survived. It was a NO-OP: a backtick-free character class can
   terminate at exactly one position, so greedy and lazy find the same match.
   Chasing the survival found the real defect — the constant's comment credited
   the LAZINESS for a nearest-span property the character CLASS enforces, which
   would have told anyone widening the class that they were still protected.
   Before treating a survival as missing coverage, prove the mutation can change
   behaviour at all; when it cannot, read the comment next to it.

Corollary worth keeping: designing the arms, on paper and before running any,
exposed two tests that could not fail — a guard whose deletion changes only the
wording, and a first-wins rule every fixture had exactly one element for. The
design pass is a cheaper detector than the run.

## Outcome

- Signal: useful