---
type: "query"
date: "2026-09-03T23:57:57.635454+00:00"
question: "Phase U step 0: how do you make this repo's tool resolution observable, and what did removing the patch-level gate actually take?"
contributor: "graphify"
outcome: "useful"
---

# Q: Phase U step 0: how do you make this repo's tool resolution observable, and what did removing the patch-level gate actually take?

## Answer

# Phase U step 0 (resolution half) + the codex 0.153.1 resync — 2026-09-03

Landed as PR #707, squash `b1d92a56`, from four commits reviewed cold at
`1a99a161` (`cold:codex`, 2 findings / 0 blocking).

## What shipped

**A three-fact resolution check.** `currency/sync.py` asked one question — what
would a BARE call in this process reach — and reported one answer, so a stale
shell PATH and a genuinely wrong install produced the same DRIFT. It now also
asks `mise which` and `mise exec -- <bin> --version`, deep-path only, and the
pair separates "this shell is stale" from "the pinned version is not installed".
The shallow path cannot reach a subprocess at all: the finding row is ABSENT
rather than SKIP when `deep=False`, so the SessionStart contract holds by
construction rather than by a flag someone must honour.

**codex resynced to 0.153.1** across `mise.toml`, `mise.lock` and
`sources/codex.manifest`, the manifest pinned to the PEELED tag commit
`98564127…` because `rust-v0.153.1` is annotated (#500). `mise use` moved both
the pin and the lock row; it was armed on a scratch copy first because
`mise config set` is recorded here as eating comments — it does not, exactly one
line of 1674 changed.

**The patch-level gate removed**, on Ray's ruling: *"we always want to be on the
latest version"*. It measured digit position rather than risk — codex
`0.152.1 -> 0.153.1` blocked while mise `2026.9.0 -> 2026.9.1` passed, purely
because calver puts a release in the patch slot — and nothing could ever clear
it, unlike the tracked-issue gate.

## The finding worth carrying

Deleting that gate whole would have opened two holes, both measured rather than
reasoned: `_has_upgrade("1.0.5", "1.0.2")` is True, so a DOWNGRADE would have
self-applied; and `same_release("main", "feature-x")` is False, so two strings
that are not versions at all read as an upgrade. One function was doing three
unrelated jobs and only one of them was the job under review. What replaced it,
`_gate_readable`, keeps the other two and tests nothing for size.

The general shape: **before removing a check, enumerate what it does, not what it
is named.** A gate's name describes the job someone objected to; its body may be
carrying others silently.


## Outcome

- Signal: useful