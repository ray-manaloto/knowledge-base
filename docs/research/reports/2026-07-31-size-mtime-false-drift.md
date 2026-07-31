# `size:mtime_ns` cries stale on ordinary git operations — use a content hash

**Issue**: [#89](https://github.com/ray-manaloto/knowledge-base/issues/89), a
frontier ticket of the `Fluent` map ([#85](https://github.com/ray-manaloto/knowledge-base/issues/85)).
**Date**: 2026-07-31. **Verdict**: the map Notes' `size:mtime_ns` **must move to a
content hash** for the INPUT fingerprint. Three negative-arm cases fired.

Tracked rather than left in `.agent/`, because the map Note it corrects will cite
it (`agent-report-persistence.md` rule 1b) — a citation to a file only one
machine can open is not a citation.

## What was measured

The map Notes fix "stale" as `sources/*.manifest` + `sources/extractions/*.json`
versus the build, fingerprinted as `size:mtime_ns` — matching what
`.currency-stamp.json` already uses for OUTPUTS
(`kb_setup.currency.sync.artifact_fingerprint`, `f"{st.st_size}:{st.st_mtime_ns}"`).

The probe reimplements that function byte-for-byte over the input set, and
records a **sha256 alongside it**. That pairing is the whole method: a moved
fingerprint on unchanged bytes is FALSE drift, and a fingerprint on its own
cannot tell the two apart — which is the question. Run in a throwaway clone at
`67b9665`; 43 inputs (27 manifests + 16 extraction chunks).

## Result

| case | `size:mtime_ns` | `sha256` |
|---|---|---|
| `git status` / `git diff` sweep | OK | OK |
| checkout to a branch that does NOT touch `sources/`, and back | OK | OK |
| stash + pop of an UNRELATED file | OK | OK |
| merge a branch that does not touch `sources/` | OK | OK |
| **edit a manifest, then `git checkout --` it back** | **DRIFT (false)** | OK |
| **checkout to a branch that DOES touch `sources/`, and back** | **DRIFT (false)** | OK |
| **stash + pop of a `sources/` edit** | **DRIFT (false)** | OK |
| CONTROL — a real content edit | DRIFT | DRIFT |

**`size:mtime_ns` fired on every row of the bottom four.** For this class of
operation it is a probe that can only say DRIFT, so its agreement with the
control row carries no information. `sha256` discriminates on all eight.

In each false case the tree was `git status` **clean** and the bytes were
identical to what was built. git rewrites a file whenever the checkout target
differs from the working tree — which restores content but never the mtime — so
the ticket's prediction ("git only rewrites files whose content differs") is
true and does not imply what it looks like it implies: *coming back* to the
original content is itself a rewrite.

The three failing cases are not exotic. Every ingestion PR touches `sources/`,
so switching branches around one is routine, and `git checkout --` is the normal
way to abandon a WIP chunk.

## The fresh-clone case is safe, and for a reason worth writing down

A fresh clone moves **43 of 43** fingerprints, all on identical bytes. It is
nonetheless not a false positive, because a fresh clone has **no
`graphify-out/.currency-stamp.json` and no `graph.json`** (measured: both absent;
only the committed `memory/` survives). So the honest answer is *never built*,
and the check reaches the input comparison only if it fails to look for the stamp
first.

**That makes an ordering requirement, not an observation**: absence of a stamp
must short-circuit to *never built* / *not verifiable* BEFORE any input is
compared. Reversed, the very first session in a new clone would be told its
entire corpus had gone stale. This is the same DRIFT/SKIP/OK distinction
`currency` already refuses to collapse.

## Cost — the reason the output stamp's rationale does not transfer

`artifact_fingerprint`'s docstring justifies a stat over a digest: *"these graphs
are hundreds of megabytes and this runs in a per-session hook."* True of the
outputs; **not** true of the inputs.

| set | size | cost |
|---|---|---|
| outputs (`graph.json` + `graph-prose.json`) | **341 MB** | a digest would be untenable in a hook |
| inputs (43 committed files) | **2.4 MB** | sha256 over all of them: **1.8 ms** (best of 5) |

142x smaller. 1.8 ms sits inside the ~10 ms `kb-currency-check` already advertises.

**The tool built-in was checked and LOSES here** (`use-tool-builtins.md`):
`git hash-object` over the same 43 files takes **~870 ms** — the subprocess and
git start-up dominate a 2.4 MB hash. In-process `hashlib` is ~480x faster.
Recording it so the check is not re-run: the native path exists, was measured,
and is the wrong one for this input size.

## What this decides for the goal round

1. **The input fingerprint is a content hash** (sha256, in-process), not
   `size:mtime_ns`. The map Notes' `size:mtime` wording must be corrected — it is
   listed among the locked decisions, and this is the ticket that was raised to
   falsify it before the goal round built on it.
2. **The OUTPUT stamp keeps `size:mtime_ns`.** Nothing here argues against it;
   the two sets differ by 142x in size and the reasoning is size-dependent.
3. **No stamp / no graph short-circuits to *never built*** before any input
   comparison happens.

## Reproduction

Probe: `fp.py` in the session scratchpad (`snap` / `cmp` over the input set,
recording `size:mtime_ns` and sha256 together), driven against a throwaway clone.
Every case resets with `git checkout -q main && git checkout -- sources/` before
running, so no case inherits the previous one's mtimes.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) —
  the repo under measurement; `kb_setup.currency.sync.artifact_fingerprint` is the
  function the probe reimplements.
