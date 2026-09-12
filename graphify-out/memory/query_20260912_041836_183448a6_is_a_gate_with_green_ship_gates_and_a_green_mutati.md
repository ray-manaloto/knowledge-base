---
type: "query"
date: "2026-09-12T04:18:36.416119+00:00"
question: "Is a gate with green ship gates and a green mutation-arm suite an armed gate?"
contributor: "graphify"
outcome: "corrected"
correction: "# The belief: a green gate with a green arm suite is an armed gate\n\nIt is not. This round the gate passed ten ship gates and TWO cold review rounds\nover a surface with eleven detectable defects, and the arm suite reporting\n`11/11 died` contained a row that could not fail.\n\n**What the arms were actually measuring.** All seven original arms mutated\n`guard_inventory.py` — the CODE. Not one mutated `docs/guards/inventory.toml` —\nthe DATA the gate exists to reconcile. They corrupted what was present and never\ninjected the ABSENCE the gate detects, which is why all three wave-1 defects\nshipped under a clean sweep. The fix is not \"more arms\"; it is asking, per arm,\n*which authority does this mutation attack* — and noticing when the answer is\nalways the same one.\n\n**Two ways a green arm lies, both hit here in one round.**\n\n- **An INERT MUTANT.** A7's `new` renamed a local and aliased it back, so it was\n  semantically identical to its `old`. It survived twice and was reported as\n  `6/7 armed` with A7 as the sole survivor — which reads as a coverage gap and\n  was a no-op harness row. Test: can you state what OBSERVABLE the mutation\n  changes? If not, it is not an arm.\n- **A TAUTOLOGICAL TEST.** A8 severed the fail-closed backstop and survived — and\n  the mutation was fine; the tests could not fail. `assert dispatched_module_names(root) == frozenset()`\n  against a fixture holding ONLY dynamic indirection is satisfied whether the\n  backstop fired or the walker found nothing in that body. A mutation sweep is\n  structurally blind to this: it mutates production code, so a test asserting\n  nothing is invisible to it. Only reverting the behaviour and watching the test\n  stay green finds it.\n\n**The asymmetry that makes this expensive.** A surviving arm is loud — it shows\nup in the score and sends you looking. A *dying* arm is silent, and a dying arm\nproves only that SOME test noticed SOMETHING. Both of this round's arm defects\nwere found by the survivor being investigated, which means the ones that die are\nthe ones never audited.\n\n**So: a clean sweep is a statement about your TESTS, never about your premise.**\nFour clean sweeps in this repo's history — 12/12, 15/15, 17/17, 21/21 — each\nimmediately preceded a real blocking defect in the code it scored, twice in the\nfix itself. This round makes five.\n\n**The habit that would have caught wave 1 on day one:** for each authority the\ngate reads, delete a row from it and confirm the gate reddens. The gate read four\nauthorities — `inventory.toml`, `settings.json`, `hook_guard.py`, `mise.toml` —\nand was armed against exactly one.\n"
---

# Q: Is a gate with green ship gates and a green mutation-arm suite an armed gate?

## Answer

# Round: ship G00 (#753), and find out whether the gate it shipped works

Ray's ruling was procedural — `kb-review` → receipt → `kb-ship` → `kb-land` →
close #753. What the round actually asked, once the review started, was: **does
the guard-inventory gate shipped at `334b65b1` detect what it claims to?**

**No. Eleven defects, in four waves, every one found by RUNNING something rather
than reading it.**

## Wave 1 — three ways past the gate (round 1 + the advisor)

1. **3 of 11 guard modules could be deleted from the inventory and the gate said
   OK** — the `direct-registration` route had no reconciliation branch at all.
   One of the three was `module.hook-guard`, the dispatcher for the other eight.
2. **3 of 21 registrations were filtered out of reconciliation entirely.**
   Deleting a `register.ts` row read clean; so did INVENTING one for a tool that
   does not exist.
3. **`dispatched_module_names` recognised one of four ordinary static import
   forms.** A brand-new guard reached by `import kb_setup.x`, `from . import x`
   or `from kb_setup.x import y` was invisible — the exact failure
   `UNCLASSIFIED` exists to catch, needing no file edit, only ordinary Python.
   Rated P1 and found by the ADVISOR, not by a review lane.

Fixing #3 surfaced a **twelfth module**: `hook_guard.py:28` imports `result.py`
by a submodule form the old walker could not see. The census moved a third time
— 7/2,859 → 11/4,024 → **12/4,278**.

## Wave 2 — five defects IN THE FIX (round 2)

4. **The `enabled` state check could only ever return one answer.**
   `marketplace_known` compared `extraKnownMarketplaces` KEYS to the PLUGIN name;
   those keys are marketplace names, so measured against all 11 live keys every
   comparison was False. And `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` — named in the
   design, a TRACKED fact in `.claude/settings.json` `env` — was referenced
   nowhere in the module.
5. **The function-hook comparison ignored `source.event`**, so a row repointed at
   `tool.result` stayed green while the code claimed to reconcile
   `(path, "tool.call", tool)`.
6. **`from importlib import import_module as load` bypassed the fail-closed
   backstop**, yielding a silently short set instead of NOT_RUN.
7. **`module_ids` rejected only NONEXISTENT modules**, so deleting the field
   outright was invisible.
8. **The mise task route was a hand-copied duplicate of `mise.toml`'s `run`
   lines** — reconciliation made zero reads of the authority.

## Wave 3 — two in the arms themselves

9. **A7 was an INERT MUTANT** that survived two runs while being counted as
   armed. Its mutation renamed a local and aliased it back.
10. **A8, added to cover the backstop, caught a TAUTOLOGICAL test.** It survived
    at first — and the mutation was not inert, the tests were. All three
    fail-closed fixtures held only dynamic indirection, so
    `assert … == frozenset()` passed whether the backstop fired or the walker
    merely found nothing.

## Wave 4 — two in the chain bookkeeping

11. Removing #753's row, I **also deleted it from four `blockers` lists**. The
    file's own header permits an edge with no ticket entry, and all four
    dependent issues still list G00 in their live bodies. Refuted by the review.
    And **moving G05 did not make the header's V1 claim true** — V1 was still
    ninth; that needed a second move I had asserted was unnecessary.

## What the gate catches now

A deleted module row on any route · an invented registration · a fabricated tool
· an event repointed away from `tool.call` · a guard added via any of four import
forms · dynamic indirection under any binding · a missing `module_ids` route · a
`mise.toml` task repointed underneath it. Arms: **18/18 died, 3/3 controls held**,
21 rows.

Three PRs: **#768**, **#769**, **#770**.


## Outcome

- Signal: corrected
- Correction: # The belief: a green gate with a green arm suite is an armed gate

It is not. This round the gate passed ten ship gates and TWO cold review rounds
over a surface with eleven detectable defects, and the arm suite reporting
`11/11 died` contained a row that could not fail.

**What the arms were actually measuring.** All seven original arms mutated
`guard_inventory.py` — the CODE. Not one mutated `docs/guards/inventory.toml` —
the DATA the gate exists to reconcile. They corrupted what was present and never
injected the ABSENCE the gate detects, which is why all three wave-1 defects
shipped under a clean sweep. The fix is not "more arms"; it is asking, per arm,
*which authority does this mutation attack* — and noticing when the answer is
always the same one.

**Two ways a green arm lies, both hit here in one round.**

- **An INERT MUTANT.** A7's `new` renamed a local and aliased it back, so it was
  semantically identical to its `old`. It survived twice and was reported as
  `6/7 armed` with A7 as the sole survivor — which reads as a coverage gap and
  was a no-op harness row. Test: can you state what OBSERVABLE the mutation
  changes? If not, it is not an arm.
- **A TAUTOLOGICAL TEST.** A8 severed the fail-closed backstop and survived — and
  the mutation was fine; the tests could not fail. `assert dispatched_module_names(root) == frozenset()`
  against a fixture holding ONLY dynamic indirection is satisfied whether the
  backstop fired or the walker found nothing in that body. A mutation sweep is
  structurally blind to this: it mutates production code, so a test asserting
  nothing is invisible to it. Only reverting the behaviour and watching the test
  stay green finds it.

**The asymmetry that makes this expensive.** A surviving arm is loud — it shows
up in the score and sends you looking. A *dying* arm is silent, and a dying arm
proves only that SOME test noticed SOMETHING. Both of this round's arm defects
were found by the survivor being investigated, which means the ones that die are
the ones never audited.

**So: a clean sweep is a statement about your TESTS, never about your premise.**
Four clean sweeps in this repo's history — 12/12, 15/15, 17/17, 21/21 — each
immediately preceded a real blocking defect in the code it scored, twice in the
fix itself. This round makes five.

**The habit that would have caught wave 1 on day one:** for each authority the
gate reads, delete a row from it and confirm the gate reddens. The gate read four
authorities — `inventory.toml`, `settings.json`, `hook_guard.py`, `mise.toml` —
and was armed against exactly one.
