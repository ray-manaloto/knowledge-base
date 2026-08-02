# Cold review — commit 0f22927 (round 2, fix verification)

Reviewed `git diff 04312f3..0f22927` — the fix delta for the three findings
raised against `04312f3`. Round-1 report: `.agent/kb/review/reports/review-04312f3-cold.md`.

Method: read the diff and the surrounding `graph.py` context in full, then
attacked the shipped `refresh_self`/`_read_base_guard`/`_write_base_guard`
directly (not mutants of them — the real functions, imported from
`python/src/kb_setup/graph.py`) under adversarial conditions: a concurrent
third-party writer, a truncated guard file, a directory-shaped guard file, a
leftover crash-staging file. Every probe ran against the actual code at
`0f22927`; nothing in the repo was mutated or left dirty (`git status --short`
clean throughout — probes ran in `tempfile.TemporaryDirectory()`, not on repo
files). Also mutated the guard *comparison* itself (a length-only check) to
confirm the new tests genuinely require content-level disagreement, not just
"some check exists".

## Findings, worst first

### 1. [CONFIRMED, HIGH] The base guard is checked ONCE at the top of `refresh_self`, but the destructive swap happens after a long-running loop — a third-party write landing in that window is silently destroyed, then the guard is REARMED to certify the loss as verified

**File:** `python/src/kb_setup/graph.py:224-238` (the guard check) vs. `:282-294`
(the swap, prose re-derivation, and guard re-arm).

**Claim:** The guard fix closes the *sequential* ordering bug (`kb-build` →
`kb-merge` → `kb-watch`) but does not close the *concurrent* one. `refresh_self`
reads `_read_base_guard`/`_digest(out)` exactly once, at the very top, before
doing anything else. Between that read and the final `staging.replace(out)`,
the function runs two `graphify extract --force` + `graphify merge-graphs`
subprocess round-trips per self-tree — real wall-clock time, the exact class of
operation `long-running-command-hangs.md` warns can take minutes. Nothing
re-validates `out` against the guard immediately before the swap. So a
`mise run kb-merge` that lands *while* a `kb-watch` is in flight is invisible to
the check that exists specifically to catch it, gets unconditionally
overwritten by `staging.replace(out)`, and the function then calls
`_write_base_guard(repo_root)` against the now-clobbered result — reproducing
finding 1 from round 1 (silent revert + false-green restamp) through a timing
window instead of a strict ordering. There is no lock file and no PID guard on
either task, so two `mise run` invocations racing is not a contrived scenario.

**Verified by direct execution** against the real, unmutated `refresh_self`:
armed the guard for a clean `out`, stubbed `_run` so that the FIRST
`merge-graphs` call (mid-loop, i.e. strictly after the guard check already
passed) writes a competing `MERGED_DOC_CHUNK_DURING_REFRESH` marker into `out`
— exactly what `_merge_docs.py` does. Result:

```
guard armed at start: 25c3534fda9e...
  [simulated kb-merge] wrote MERGED_DOC_CHUNK_DURING_REFRESH into out mid-loop
[kb-watch] refreshed python/ + tests/ into graphify-out/graph.json
refresh_self completed without raising. survived-in-final-out=False
final out content: {"nodes": [], "base": true}
guard after refresh: 25c3534fda9e... == digest(out) 25c3534fda9e...? True
```

`refresh_self` returned 0, printed its normal success line, and the guard now
*agrees* with the graph that just silently lost the concurrent write —
`kb-currency-check` would report this clean, which is the identical failure
mode round 1 found, just triggered by concurrency rather than sequence.

**Why the new tests don't catch it:**
`test_refresh_self_refuses_when_another_writer_touched_the_graph` writes the
third-party content *before* calling `refresh_self` at all — it only models the
writer landing strictly *before* the function starts, never *during* its
execution. Neither new test drives `_run` to mutate `out` from inside the loop.

### 2. [CONFIRMED, HIGH] `_read_base_guard` treats "guard file exists but is unreadable/corrupt" identically to "guard legitimately never existed" — both collapse to `""` and silently disable the fail-closed check

**File:** `python/src/kb_setup/graph.py:328-340` (`_read_base_guard`'s bare
`except OSError: return ""`) vs. `:229-238` (the caller, which treats an empty
`expected` as "nothing to check").

**Claim:** The design comment on `_read_base_guard` (`graph.py:331-336`)
justifies returning `""` on absence: "A graph built before this guard existed
has no recorded digest, and refusing those would break every existing clone."
That's a real, narrow case (guard file does not exist). But the implementation
doesn't distinguish "does not exist" from "exists and I could not read it" —
`except OSError` is broad enough to also swallow `IsADirectoryError`,
`PermissionError`, and a decode failure on empty/binary content, all of which
mean "we don't know", not "there is no history". The surrounding code's own
stated intent is "FAIL CLOSED if anything else has written graph.json since the
snapshot was composed" (`graph.py:224`) — an unreadable guard is exactly the
case that should fail closed, and instead fails open.

**Verified by direct execution**, two ways, both against the real code:

*(a) Empty (0-byte) guard file* — the realistic trigger is an interrupted
`_write_base_guard` write (process killed mid-write, which `long-running-command-hangs.md`
explicitly tells operators to do to a wedged process):

```
refresh_self completed WITHOUT raising. final out: {"nodes": [], "base": true}
CONFIRMED: empty guard file silently bypassed the check and the third-party
merge was reverted with no error.
```

*(b) Guard path is a directory* — `_read_base_guard` still swallows the
`IsADirectoryError` and returns `""`, so the destructive `staging.replace(out)`
still runs and the third-party content is destroyed exactly as in (a). The
function only fails *afterward*, and only because `_write_base_guard` (unlike
its read-side counterpart) has **no** `except OSError` at all:

```
crashed with: IsADirectoryError: [Errno 21] Is a directory: '.../.base-graph.sha256'
out content AFTER crash: '{"nodes": [], "base": true}'
```

The third-party marker is already gone from `out` by the time the exception
surfaces — the crash gives the operator *something*, but the data loss is
already committed and irreversible, and the error message ("Is a directory")
gives no indication that a write was just silently discarded. This is also an
asymmetry worth flagging on its own: `_read_base_guard` catches `OSError`
broadly, `_write_base_guard` catches nothing, for what is otherwise one
mechanism with two halves.

**Why the new tests don't catch it:** neither new test exercises a guard file
that exists-but-can't-be-read; both only exercise "guard present and
disagrees" or implicitly "guard absent, first-ever refresh".

### 3. [PLAUSIBLE, MEDIUM — unchanged tier from round 1] The `??` fix in `kb-tool-review.js` covers only the documented "agent resolves to null" path; a thunk that *rejects* still produces a bare `null` array entry that bypasses the fallback and is silently dropped

**File:** `.claude/workflows/kb-tool-review.js:117-139`.

**Claim:** The fix is correct for the case it targets: when `agent()`
*fulfills* with `null` (its documented behavior for "the user skips the agent
mid-run or the subagent dies on a terminal API error after retries"), `v ?? {
refuted: true, ... }` now synthesizes the fail-safe object, and downstream
`!v.verdict?.refuted` correctly reads `false` — the claim is counted as
refuted, not surviving. That part is fixed and I did not find a way to make it
misbehave.

But the `Workflow` tool's own contract for `parallel()` states a *second*,
distinct failure path: "A thunk that throws (or whose agent errors) resolves
to `null` in the result array — the call itself never rejects." That means if
the thunk `() => agent(...).then((v) => ({...}))` itself ends up rejecting —
i.e. `agent()`'s returned promise rejects rather than fulfilling with `null`,
for any reason not covered by the specific "skipped/terminal-API-error"
clause — `.then`'s success handler never runs at all (rejections skip `.then`,
they propagate to `.catch`/rejection), so the `v ?? {...}` fallback is never
reached. `parallel()` itself substitutes a **bare `null`** for that array
slot, not `{...c, verdict: {refuted: true, ...}}`. That bare `null` then IS
removed by `verdicts.filter(Boolean)` at line 139 — so the claim silently
disappears from both the `refuted` and `surviving` tallies entirely, rather
than being explicitly armed as the phase's own stated goal requires ("every
NEGATIVE claim refuted or armed", `meta.phases[1].detail`).

This is a narrower defect than the original (a dropped claim can't falsely
inflate `surviving`, so it doesn't reproduce the exact false-green), but it is
a real gap in the fix's coverage: the `WARNING: 0 claims refuted` guard at
line 174 only fires when the *total* across all tools is zero, so one silently
dropped claim among several successfully-refuted ones raises no signal at all.

Unchanged confidence from round 1: Workflow scripts are not pytest-testable,
and I was not asked to invoke the real `Workflow` tool to force a live
rejection, so this rests on re-reading the documented `agent()`/`parallel()`
contract (verbatim above) rather than an observed failure.

## Ruled out (checked, not a bug)

- **The literal "kb-merge, then kb-build, then kb-merge again" sequence** the
  brief asked about: traced through `build()` (`graph.py:410-528`) and
  `refresh_self`. `build()` starts every artifact from committed inputs
  wholesale and unconditionally rearms both `base` (`:505`) and the guard
  (`:526`) against the graph it just produced — any `kb-merge` that ran
  *before* a subsequent `kb-build` is irrelevant to the graph `kb-build`
  produces (it isn't replayed unless the chunk was already committed under
  `sources/extractions/`, which is the documented, intended surface). A
  `kb-merge` that runs *after* that `kb-build` and before the next `kb-watch`
  is exactly the case the guard is designed for and correctly catches it
  (confirmed by the existing `test_refresh_self_refuses_when_another_writer_touched_the_graph`).
  The only way this ordering becomes unsafe is if the second `kb-merge`'s
  write lands inside a `kb-watch` already in flight (finding 1) or the guard
  file is itself unreadable (finding 2) — not the sequential case by itself.
- **Leftover staging file (`graph.json.refresh`) from a previous crashed run.**
  `shutil.copy(base, staging)` (`graph.py:255`) unconditionally overwrites the
  destination — `shutil.copy` truncates-and-writes an existing regular-file
  destination, it does not append or merge. Verified by direct execution:
  pre-seeded `graph.json.refresh` with a `STALE_CRASH_LEFTOVER` marker, ran
  `refresh_self`, and the marker was gone from the final `out` — clobbered by
  the fresh copy from `base` before the loop even starts. Not exploitable.
- **Ordering of `prose.derive_for` / `_write_base_guard` / `_restamp_self`
  after the swap** (`graph.py:284-295`): all three run against `out` only
  after `staging.replace(out)` has completed, so each reads the post-swap
  graph as intended. No stale-read found.
- **Do the two new tests constrain what they claim, or would a weaker
  implementation pass them?** For the disagreement case
  (`test_refresh_self_refuses_when_another_writer_touched_the_graph`): yes,
  genuinely — mutated the guard comparison to a length-only check (`len(expected)
  != len(actual)`, which is always `False` since sha256 hexdigests are always
  64 characters) and confirmed this weak check would never fire, so the test's
  pass depends on real content comparison, not merely "some exception exists".
  For the atomic-swap case (`test_refresh_self_leaves_the_graph_intact_when_a_merge_fails`):
  its own docstring already documents the realistic mutation (reverting to a
  direct `shutil.copy(base, out)`), matching round 1's original reproduction;
  I did not need to re-derive it. **Neither test, however, constrains findings
  1 or 2 above** — both pass unchanged against the current implementation,
  which is vulnerable to both, because neither test models a writer arriving
  *during* the loop or a guard file that is present-but-unreadable.

## Total

**3 findings: 2 CONFIRMED-HIGH (new, both verified by direct execution against
the real, unmutated `refresh_self` — a TOCTOU race across the guard-check/swap
window, and a fail-open guard-read on any unreadable/corrupt/truncated guard
file), 1 PLAUSIBLE-MEDIUM (carried over from round 1, unchanged — the
`kb-tool-review.js` fix covers the documented null-resolution path but not a
rejecting thunk).**

Both HIGH findings reproduce finding 1's exact original consequence — silent
revert of real corpus content, followed by the guard being rearmed to certify
the corrupted graph as verified — through paths the two new regression tests
do not exercise. Neither requires an adversarial actor: ordinary concurrent
`mise run` usage (finding 1) or killing a wedged `kb-watch`/`kb-build` process
mid-write (finding 2, empty guard) are both patterns this repo's own rules
(`long-running-command-hangs.md`) instruct operators to do.

## GitHub repos touched

_None._ This review read only this repository's own source and tests.
