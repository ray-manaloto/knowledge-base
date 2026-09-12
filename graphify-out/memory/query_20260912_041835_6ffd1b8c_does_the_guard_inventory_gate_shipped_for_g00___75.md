---
type: "query"
date: "2026-09-12T04:18:35.589373+00:00"
question: "Does the guard-inventory gate shipped for G00 (#753) detect what it claims to?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does the guard-inventory gate shipped for G00 (#753) detect what it claims to?

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

- Signal: useful