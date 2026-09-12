---
type: "query"
date: "2026-09-12T11:48:00.110917+00:00"
question: "G02 (#755): can one schema own the settings-guard policy and generate both the Python and TypeScript consumers, with a drift gate that catches what the native codegen check misses?"
contributor: "graphify"
outcome: "useful"
---

# Q: G02 (#755): can one schema own the settings-guard policy and generate both the Python and TypeScript consumers, with a drift gate that catches what the native codegen check misses?

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

- Signal: useful