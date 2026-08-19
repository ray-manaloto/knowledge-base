---
type: "query"
date: "2026-08-19T22:50:12.856264+00:00"
question: "Is an inherited number safe to restate if the correction around it is careful?"
contributor: "graphify"
outcome: "corrected"
correction: "An INHERITED NUMBER is not a measurement, and re-stating it inside a CORRECTION\ndoes not make it one. This round did both, three times, and each was caught by\nsomeone other than the author.\n\n1. **\"datamodel-code-generator is declared but never invoked.\"** Repeated from\n   `docs/directives-2026-08-08.md`'s `git log -S datamodel --all` -> 0 hits — an\n   11-day-old figure, true when written and false when quoted. It was used to\n   argue that 0.73.0's breaking changes cost nothing BECAUSE nothing invoked it:\n   a right conclusion resting on a wrong premise, which is the most disarming\n   shape a comment can take. Three generators invoke it and produce three\n   committed modules. Cold lane, P1.\n\n2. **The sentence written WHILE CORRECTING that claim was itself false.** The\n   replacement read \"none of the three passes `--additional-imports`,\n   `--extra-template-data` or a custom template dir\". All three pass\n   `--custom-template-dir`. A correction can be wrong twice, and the replacement\n   gets LESS scrutiny than the sentence it replaces precisely because writing it\n   feels like being careful. Cold lane round 2, P1.\n\n3. **\"52 of 73 manifests pin `ref = main`, so 71% of the corpus is not\n   reproducible-by-reference.\"** Filed as a P0 issue title. All 52 pin an\n   explicit 40-hex `commit`, so `kb-build` clones deterministically and the\n   corpus IS reproducible. The issue's own body carried the caveat four\n   paragraphs down while the title contradicted it — which made it worse, not\n   better, because a headline reads as verified. Refuted by Ray.\n\nThe habit that catches all three: **before a number or an absence is used to\nsupport a conclusion, re-derive it in the session that is using it, and arm the\nprobe.** The fix for (1) and (2) was two greps with a control\n(`--additional-imports` 0 hits, `--extra-template-data` 0 hits,\ncontrol `--custom-template-dir` 3 hits). The fix for (3) was one loop\n(`52 of 52 carry a 40-hex commit`, control: no manifest lacks a commit line).\nEach cost seconds. Each was skipped because the claim felt already-established.\n\nA corollary this round proved twice: **a claim stated wider than its evidence is\nnot saved by a caveat elsewhere in the document.** Both the codegen comment and\nthe #397 issue contained the accurate version somewhere in their own text. The\nreader takes the headline.\n"
---

# Q: Is an inherited number safe to restate if the correction around it is careful?

## Answer

No. A careful correction is where inherited numbers are MOST likely to survive,
because writing one feels like being careful and the replacement sentence then
gets less scrutiny than the sentence it replaced.

Measured over one round (2026-08-19c), three false claims, none of them caught
by their author:

1. **"datamodel-code-generator is DECLARED BUT NOT YET USED."** Carried from
   `docs/directives-2026-08-08.md`'s `git log -S datamodel --all` -> 0 hits — an
   11-day-old figure, true when written and false when quoted. It was doing real
   argumentative work: it explained why 0.73.0's breaking changes cost nothing
   *because nothing invoked it*. Three generators invoke it and produce three
   committed modules under `python/src/kb_setup/generated/`. Cold lane, P1.

2. **The sentence written WHILE CORRECTING (1) was itself false.** The
   replacement read "none of the three passes `--additional-imports`,
   `--extra-template-data` or a custom template dir". All three pass
   `--custom-template-dir`, one call site each. Cold lane round 2, P1. The true
   version was STRONGER — `schemas/templates/` supplies the ROOT template, and
   0.73.0 explicitly leaves trusted custom root templates alone — so the false
   claim was not even buying anything.

3. **"52 of 73 manifests pin `ref = main`, so 71% of the corpus is not
   reproducible-by-reference."** Filed as a P0 issue TITLE. All 52 carry an
   explicit 40-hex `commit` and `kb-build` clones at the commit. Refuted by Ray.

And a fourth, caught by the read-only cold lane on the round's own closing
commit: **"an eleventh restatement site"** — an ordinal carried from a source
comment while the same paragraph asserted a measured "eight". The checkable
figure is that `currency.toml` has 8 `[[tool.graphify.ref_binding]]` rows, all
scoped to `sources/graphify.manifest`; the ordinal is not derivable from
anything and should not have been repeated.

## What actually works

Re-derive the number in the session that USES it, and arm the probe. Each
refutation above cost one command and seconds:

- `grep -c custom-template-dir schemas/*.py` -> 3, against
  `--additional-imports` -> 0 and `--extra-template-data` -> 0. Control present,
  so the zeros are absences rather than a broken grep.
- `for f in $(grep -l '^ref = main$' sources/*.manifest); do ...` -> 52 of 52
  carry a 40-hex commit; control `grep -L "^commit = "` returns nothing.
- `git log -S datamodel --all` -> re-running it is the whole check.

## The corollary this round proved twice

A claim stated wider than its evidence is NOT saved by a caveat elsewhere in the
same document. Both the codegen comment and issue #397 contained the accurate
version in their own text — four paragraphs below a headline that contradicted
it. Burying the true version makes it worse, not better: the reader takes the
headline, and a headline reads as verified.


## Outcome

- Signal: corrected
- Correction: An INHERITED NUMBER is not a measurement, and re-stating it inside a CORRECTION
does not make it one. This round did both, three times, and each was caught by
someone other than the author.

1. **"datamodel-code-generator is declared but never invoked."** Repeated from
   `docs/directives-2026-08-08.md`'s `git log -S datamodel --all` -> 0 hits — an
   11-day-old figure, true when written and false when quoted. It was used to
   argue that 0.73.0's breaking changes cost nothing BECAUSE nothing invoked it:
   a right conclusion resting on a wrong premise, which is the most disarming
   shape a comment can take. Three generators invoke it and produce three
   committed modules. Cold lane, P1.

2. **The sentence written WHILE CORRECTING that claim was itself false.** The
   replacement read "none of the three passes `--additional-imports`,
   `--extra-template-data` or a custom template dir". All three pass
   `--custom-template-dir`. A correction can be wrong twice, and the replacement
   gets LESS scrutiny than the sentence it replaces precisely because writing it
   feels like being careful. Cold lane round 2, P1.

3. **"52 of 73 manifests pin `ref = main`, so 71% of the corpus is not
   reproducible-by-reference."** Filed as a P0 issue title. All 52 pin an
   explicit 40-hex `commit`, so `kb-build` clones deterministically and the
   corpus IS reproducible. The issue's own body carried the caveat four
   paragraphs down while the title contradicted it — which made it worse, not
   better, because a headline reads as verified. Refuted by Ray.

The habit that catches all three: **before a number or an absence is used to
support a conclusion, re-derive it in the session that is using it, and arm the
probe.** The fix for (1) and (2) was two greps with a control
(`--additional-imports` 0 hits, `--extra-template-data` 0 hits,
control `--custom-template-dir` 3 hits). The fix for (3) was one loop
(`52 of 52 carry a 40-hex commit`, control: no manifest lacks a commit line).
Each cost seconds. Each was skipped because the claim felt already-established.

A corollary this round proved twice: **a claim stated wider than its evidence is
not saved by a caveat elsewhere in the document.** Both the codegen comment and
the #397 issue contained the accurate version somewhere in their own text. The
reader takes the headline.
