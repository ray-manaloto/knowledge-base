---
type: "query"
date: "2026-09-12T11:48:00.480307+00:00"
question: "Is a test that builds a hostile enum whose names and values differ enough to prove PROTECTED_SUFFIXES is derived rather than hand-written?"
contributor: "graphify"
outcome: "corrected"
correction: "# A test I READ and judged correct was still tautological — the arm said so\n\nI read `test_protected_suffixes_are_built_from_enum_values_not_names` after a\nlane rewrote it, saw that it built a HOSTILE enum whose member names and values\ndeliberately differ, and concluded the tautology was fixed. I told the user so.\n\nIt was not fixed. The round-2 cold lane ARMED it: reverted `PROTECTED_SUFFIXES`\nto a hand-maintained literal tuple holding the same values, and the test passed\nat rc 0 — the exact defect its own docstring says it rules out.\n\n**Why my reading was wrong.** The hostile enum proves the FUNCTION\n`_protected_suffixes_from` reads `.value`. It never proves the CONSTANT is built\nby that function. Every assertion in the test compares VALUES, and a literal\nholding today's values equals the derived tuple by construction. The test was\ncorrect about one thing and silent about the thing its name claims.\n\n**What closes it**: an assertion about PROVENANCE that no choice of strings can\nsatisfy — parse the module's own source and require the binding to be a CALL.\nThat cannot be made to pass by a literal, whatever it contains.\n\n**The general form, and it is the one to carry:** reading a test tells you what\nit asserts; only reverting the thing it guards tells you whether it can fail.\nA test written alongside its fix routinely cannot fail, and **a mutation sweep\nis structurally blind to it** — an arm mutates production code, so a test\nasserting nothing is invisible to the sweep as well as to the reader. Reverting\nis the only cheap probe for this class, and I skipped it because the test LOOKED\nclever.\n\nSame session, same class, three more times: a 9/9 arm sweep that did not contain\nthe test it appeared to cover; `grep -c` counted lines while I described it as\ncounting code; and I wrote `assert ... != Rc.FINDINGS or True` — an assertion\nthat cannot fail — inside the commit fixing assertions that cannot fail.\n"
---

# Q: Is a test that builds a hostile enum whose names and values differ enough to prove PROTECTED_SUFFIXES is derived rather than hand-written?

## Answer

# G02 (#755): schema-owned guard-policy codegen, and what three review rounds cost

## What shipped

One committed JSON Schema is now the single authority for the settings guard's
protected-path policy. `datamodel-codegen` emits the Python enum as the 10th job
in the existing `--all-jobs` batch; a new `kb_setup.guard_codegen` renders the
TypeScript literal the hooks module imports; `kb-guard-codegen-check` is the
drift gate. PR #774, 10/10 gates green.

## The finding that justified the ticket, measured

Native `datamodel-codegen --check` catches a DELETED generated file (rc 1,
`MISSING:`) and MISSES a stale extra (rc 0). Armed three ways against the real
tree, twice independently. So the new gate's whole reason to exist is the
extra/orphan direction, which the native check cannot see.

## The expensive lesson: THE FIX IS THE DEFECT

Round 1 returned 16 findings. Round 2 returned 13 — and **both of its P1s were
defects in round 1's fixes**, on the very ticket where the lane had been told to
review the fix hardest *because* that is this repo's recorded pattern.

1. The fix for "report could-not-run correctly" made `NOT_RUN` **unreachable**
   for the commonest could-not-run input: `check()` opened with an unguarded
   `json.loads(read_text())` ahead of every check, so a deleted or malformed
   schema raised and exited 1 — numerically `FINDINGS`.
2. The expanded protected set covered the schema, the generator, the Python
   consumer and the generated TS data, and **omitted the file that does the
   denying**.

Both were confirmed by my own probes before anything was changed.

## What a static gate structurally cannot do

Round 2 defeated the consumer check five ways; two are caught by nothing —
`if (true) return false;` inside the predicate, and deleting its call site so a
perfectly correct predicate is invoked by nobody. Those are BEHAVIOURAL
properties of a TypeScript module and the gate reads text.

Ray ruled: narrow the claim rather than chase shapes. The gate's clean line now
ends *"NOT proven here: that isProtectedPath is reachable, called, or behaves —
this gate reads text, it does not run the guard"*, and the residual is #773,
against the ticket that registers the mod — the first point at which an
end-to-end arm is possible at all. Adding a sixth pattern would have been "raise
a bound instead of removing it".

## Machinery that earned its keep

- **The receipt gate refused the ship** because the reviewer binary self-updated
  mid-round (agy 1.2.0 for round 1, 1.2.2 for round 2). A drifted reviewer is a
  stale review. Pin bumped across four files.
- **`kb-arms` refused two arms** as `PROBE BROKEN` after edits moved their
  anchors, rather than mutating the wrong occurrence.
- **Premise verification refuted two of my own rows** and found three problems
  that would each have broken one of my own fixes.
- **The METHOD paragraph** — *construct the input that should trip each check and
  RUN it* — is what produced both rounds' findings. Reading would have found
  almost none of them.

## Issues filed

#771 (live probes, advisory, blocked on a cost measurement) · #772 (NotebookEdit
is registered but reads a field it does not have, so one of three guarded tools
can never deny) · #773 (five static-gate gaps needing the mod registered).


## Outcome

- Signal: corrected
- Correction: # A test I READ and judged correct was still tautological — the arm said so

I read `test_protected_suffixes_are_built_from_enum_values_not_names` after a
lane rewrote it, saw that it built a HOSTILE enum whose member names and values
deliberately differ, and concluded the tautology was fixed. I told the user so.

It was not fixed. The round-2 cold lane ARMED it: reverted `PROTECTED_SUFFIXES`
to a hand-maintained literal tuple holding the same values, and the test passed
at rc 0 — the exact defect its own docstring says it rules out.

**Why my reading was wrong.** The hostile enum proves the FUNCTION
`_protected_suffixes_from` reads `.value`. It never proves the CONSTANT is built
by that function. Every assertion in the test compares VALUES, and a literal
holding today's values equals the derived tuple by construction. The test was
correct about one thing and silent about the thing its name claims.

**What closes it**: an assertion about PROVENANCE that no choice of strings can
satisfy — parse the module's own source and require the binding to be a CALL.
That cannot be made to pass by a literal, whatever it contains.

**The general form, and it is the one to carry:** reading a test tells you what
it asserts; only reverting the thing it guards tells you whether it can fail.
A test written alongside its fix routinely cannot fail, and **a mutation sweep
is structurally blind to it** — an arm mutates production code, so a test
asserting nothing is invisible to the sweep as well as to the reader. Reverting
is the only cheap probe for this class, and I skipped it because the test LOOKED
clever.

Same session, same class, three more times: a 9/9 arm sweep that did not contain
the test it appeared to cover; `grep -c` counted lines while I described it as
counting code; and I wrote `assert ... != Rc.FINDINGS or True` — an assertion
that cannot fail — inside the commit fixing assertions that cannot fail.
