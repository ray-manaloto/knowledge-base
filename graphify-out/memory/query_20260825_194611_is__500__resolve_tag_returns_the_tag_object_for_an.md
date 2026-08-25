---
type: "query"
date: "2026-08-25T19:46:11.659663+00:00"
question: "Is #500 (resolve_tag returns the tag object for annotated tags) the defect the ticket describes, and what does fixing it require?"
contributor: "graphify"
outcome: "corrected"
correction: "A ticket's ROOT CAUSE is a claim like any other, and this repo believes its own\ntickets too readily.\n\n#500 was filed with a probe, a control arm and three named SHAs — everything this\nrepo asks of a finding — and two of its three claims were still wrong. The probe\nwas real; the mechanism inferred from it was not. `--refs` was blamed for hiding\nthe peeled line when the ref PATTERN was doing it, and `kb-build` was said to be\ncorrupted when it peels before verifying and carries a comment saying so.\n\nThe cost of believing it: a first spec that told the implementer `--refs` was a\nred herring to leave alone. Under that spec the fix becomes a silent no-op —\nbecause `--refs` IS inert while the pattern is exact, and strips the peel the\nmoment you ask for it. Two cold premise passes were needed to catch that, and the\nsecond pass caught two more defects **in the fix for the first**.\n\nThe rule: **re-derive a ticket's mechanism before building on it, even when the\nticket is yours and even when it shows its work.** A correctly-measured probe with\na wrong explanation attached is more dangerous than no probe, because it reads as\nverified. Ask specifically: does the stated cause, applied, produce the observed\neffect — and would the proposed fix change the observation?\n\nCorollary, measured three times today: **the fix is the least-reviewed code in the\nround.** Round 1's fix broke branch resolution for 58 sources; my own commit\nmessage repeated a mechanism the repo had already measured a month earlier and\nrecorded in `hk.pkl`; and a \"control arm\" I wrote to prove an allowlist was safe\ncould not have produced the other answer until I rewrote it.\n"
---

# Q: Is #500 (resolve_tag returns the tag object for annotated tags) the defect the ticket describes, and what does fixing it require?

## Answer

# 2026-08-25f — the round that started at #500 and ended in a security gate

## What the round asked

Fix #500 — `manifest.resolve_tag` returning the tag object rather than the commit
for annotated tags — as the first step of the approved config-mutation plan.

## What it found instead

**#500 as filed was wrong in two of its three claims**, and the defect it named
was smaller and differently-shaped than the ticket said.

1. `--refs` is NOT what hides the peeled entry. `git ls-remote --tags --refs <url>
   v0.50.0` and the same command without `--refs` return byte-identical output —
   the peel is named `v0.50.0^{}` and the EXACT ref pattern never matched it. A
   fix that only drops `--refs` is a no-op that passes its own test.
2. A tag-object SHA does NOT break `kb-build`, which peels before it verifies and
   says so at `graph.py:640-642`; `sync.py:1433` accepts both identities by design.
3. The live defect ran the other way: `latest_commit` also returns the tag object,
   and `graph.py:3276` compares it RAW against the recorded commit, so five
   manifests reported a phantom advance on every `kb-update`. Filed as #501.

An audit of all 84 manifests against live remotes found the corpus **split 5 to 4**
between the two identities, with 16 of 25 tag-pinned sources on lightweight tags
where the difference cannot be observed — which is why it survived.

## The measurement that decided the fix

`gitleaks dir` takes ONE path (`cmd/directory.go:27`: `if len(args) == 1`). hk's
builtin passes `{{files}}`. Measured: 1 path → 20,490 bytes; 2 paths → 49,957,227;
`.` → the same 49,957,227, byte-identical. **A one-file commit and a nine-file
commit ran different gates**, and the multi-file one scanned gitignored content.
It had `mise run lint` red repo-wide, so nothing could ship.

## Outcome

Shipped: one peeling resolver shared by `resolve_tag` and `latest_commit`, four
manifests migrated, four bump recipes corrected, #503 (a tail-match accepting a
tag it did not ask for) closed as a side effect, the gitleaks pre-commit gate
scoped to staged content, and its whole-tree profile scoped by allowlist.

Filed: #501, #503, #504, #505, #506, #507, #508, #509, and
jdx/hk discussions#1246 upstream.


## Outcome

- Signal: corrected
- Correction: A ticket's ROOT CAUSE is a claim like any other, and this repo believes its own
tickets too readily.

#500 was filed with a probe, a control arm and three named SHAs — everything this
repo asks of a finding — and two of its three claims were still wrong. The probe
was real; the mechanism inferred from it was not. `--refs` was blamed for hiding
the peeled line when the ref PATTERN was doing it, and `kb-build` was said to be
corrupted when it peels before verifying and carries a comment saying so.

The cost of believing it: a first spec that told the implementer `--refs` was a
red herring to leave alone. Under that spec the fix becomes a silent no-op —
because `--refs` IS inert while the pattern is exact, and strips the peel the
moment you ask for it. Two cold premise passes were needed to catch that, and the
second pass caught two more defects **in the fix for the first**.

The rule: **re-derive a ticket's mechanism before building on it, even when the
ticket is yours and even when it shows its work.** A correctly-measured probe with
a wrong explanation attached is more dangerous than no probe, because it reads as
verified. Ask specifically: does the stated cause, applied, produce the observed
effect — and would the proposed fix change the observation?

Corollary, measured three times today: **the fix is the least-reviewed code in the
round.** Round 1's fix broke branch resolution for 58 sources; my own commit
message repeated a mechanism the repo had already measured a month earlier and
recorded in `hk.pkl`; and a "control arm" I wrote to prove an allowlist was safe
could not have produced the other answer until I rewrote it.
