---
type: "query"
date: "2026-08-23T20:46:03.051331+00:00"
question: "Did typos --write-changes corrupt the staged corpus fragments, and can the damage be reversed?"
contributor: "graphify"
outcome: "corrected"
correction: "The first investigation reported `typos` as REFUTED. That refutation was invalid\ntwice over, and the correction matters because it is what made the repair\npossible.\n\n1. The probe could not discriminate. It ran `typos --diff` / `--write-changes`\n   on the already-corrected files and observed no change. Running a corrector\n   after its corrections are applied is a no-op WHATEVER the truth is, so the\n   observation is consistent with both hypotheses and settles neither.\n   (probes-need-a-control-arm.md rule 1: arm the negative.)\n\n2. It does not reproduce. `typos` still flags chunk 0002 today. The reason\n   `--write-changes` changes nothing is that every surviving flag is AMBIGUOUS\n   (two suggestions), and typos auto-fixes only single-suggestion entries.\n\nThe positive evidence, measured this session: across all 26 fragments (~1.5 MB\nof model prose) EVERY remaining flag is ambiguous. Not one unambiguous typo\nsurvives anywhere — precisely the residue of a `--write-changes` sweep that took\neverything it was sure about and left everything it was not.\n\nConfirmed by repair: reverting one specific typos correction per file reproduced\nthe recorded sha256 exactly, twice. That is a cryptographic confirmation of the\nmechanism, not an inference.\n\nSecond-order lesson, hit twice while writing the fix: a test fixture containing a\nreal misspelling CANNOT survive in this repo. `proseExclude` covers the corpus\nbut not `tests/` or `python/`, so `mise run fmt` \"corrected\" the fixture and the\ndocstring, leaving both sides of the comparison equal — a test that could not\nfail. Build such fixtures from non-dictionary bytes. This is #413 recurring.\n"
---

# Q: Did typos --write-changes corrupt the staged corpus fragments, and can the damage be reversed?

## Answer

Three staged fragments (0002, 0005, 0009) failed the merge on
fragment-digest-mismatch + fragment-size-mismatch. Deltas were -2, +1, -1;
node/edge counts and source paths were intact, so the content was not
regenerated — a handful of prose characters moved.

Two independent digests (receipt.json:fragment_sha256 and
provider-receipt.json:semantic_fragment_sha256) agree with each other on all 26
chunks and disagree with the file on exactly those three. Two witnesses written
by different code paths cannot both have been tampered with identically, so the
RECEIPTS are authoritative and the FILE was altered.

Cause: `typos --write-changes`, which reached these paths before hk.pkl:183's
exclusion existed (added 11:39:36 in 5ae9f9ff, message "lint unblocked" — lint
was red on these files; committed already damaged at 12:33:06 in a7ae6d7b, the
only commit that ever added them, so git holds no clean copy).

Repair: a digest-verified search. Generate candidate misspellings from the words
present in the file, batch-confirm each through `typos` itself, keep only
whole-word unambiguous ones whose occurrence count times the length delta equals
the missing bytes, apply, and accept only a candidate whose sha256 equals the
recorded digest. A match is proof, not judgement — only the provider's original
bytes produce the provider's recorded digest.

Result: 0002 and 0005 RESTORED and verified against both receipts; the merge went
from 6 refusal reasons to 2. 0009 is NOT repaired.


## Outcome

- Signal: corrected
- Correction: The first investigation reported `typos` as REFUTED. That refutation was invalid
twice over, and the correction matters because it is what made the repair
possible.

1. The probe could not discriminate. It ran `typos --diff` / `--write-changes`
   on the already-corrected files and observed no change. Running a corrector
   after its corrections are applied is a no-op WHATEVER the truth is, so the
   observation is consistent with both hypotheses and settles neither.
   (probes-need-a-control-arm.md rule 1: arm the negative.)

2. It does not reproduce. `typos` still flags chunk 0002 today. The reason
   `--write-changes` changes nothing is that every surviving flag is AMBIGUOUS
   (two suggestions), and typos auto-fixes only single-suggestion entries.

The positive evidence, measured this session: across all 26 fragments (~1.5 MB
of model prose) EVERY remaining flag is ambiguous. Not one unambiguous typo
survives anywhere — precisely the residue of a `--write-changes` sweep that took
everything it was sure about and left everything it was not.

Confirmed by repair: reverting one specific typos correction per file reproduced
the recorded sha256 exactly, twice. That is a cryptographic confirmation of the
mechanism, not an inference.

Second-order lesson, hit twice while writing the fix: a test fixture containing a
real misspelling CANNOT survive in this repo. `proseExclude` covers the corpus
but not `tests/` or `python/`, so `mise run fmt` "corrected" the fixture and the
docstring, leaving both sides of the comparison equal — a test that could not
fail. Build such fixtures from non-dictionary bytes. This is #413 recurring.
