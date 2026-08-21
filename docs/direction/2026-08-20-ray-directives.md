# Ray's directives — 2026-08-20 (VERBATIM)

Written 2026-08-21, from the transcripts of the five 2026-08-20 sessions
(`6d692fdd`, `ff9f0bbd`, `3ccb33e0`, `a03ce3ad`, `61da2c9e`).

**Why this file exists at all, written a day late.** `docs/direction/` is the
standing brief every round is measured against, and both `/clear-prep` step 0
and `/kb-resume` read *the newest file in it*. On 2026-08-21 the newest was
**2026-08-19** — so an entire day of direction, including a ruling that four
source manifests now depend on, was reachable only through transcripts and one
issue TITLE. A directive that no reader consults is the failure this directory
was created to prevent, and it had been failing silently for a day.

Found by the session-review lane run on 2026-08-21, whose probe was:
`ls docs/direction/` → 4 files, newest `2026-08-19`, against a control of
`ls sources/` returning 100+ entries.

**Scope note.** Only Ray's own typed messages appear below. The 08-20 transcripts
also contain auto-injected skill prompts (`artifact-design`,
`artifact-diagramming`) and inter-session teammate messages, which arrive in the
user turn but are **not** Ray and are excluded. Bare answers to
`AskUserQuestion` ("yes", "1") are also excluded — they are choices among options
this file cannot reproduce, and are recorded in the round handoffs instead.

---

## THE RULING THAT IS NOW LOAD-BEARING — VERBATIM

> our goal is to get to the full graphify repo extraction and reflection
> for now, if we run across an issue, just set it to skip and create a github issue on the problem so we don't forget it and we can get back to it on the aggregaton/triage work after graphify is fully extracted

**Status: IN USE.** Five source manifests carry `build = skip` with a
`skip_reason` under this ruling — `codebase-memory-mcp`, `codegraph`, `colibri`,
`codex`, `GitNexus` — and **#417** is the register. `manifest.py` makes
`skip_reason` REQUIRED and non-empty when `build = skip`, so the ruling's "create
an issue so we don't forget" half is machine-enforced rather than remembered.

**The half that is NOT yet honoured:** "we can get back to it on the
aggregation/triage work **after** graphify is fully extracted". The graphify
extraction has **not** run — `graphify-out/graphify-semantic-corpus/` holds only
PLAN artifacts, no run output.

## THE QUESTION THAT NAMES THE GOAL — VERBATIM

> was the deep extraction/reflection/generated all artifacts done on the graphify repo clone on graphify version 0.9.47?

**Answer, measured 2026-08-21: NO.** It has not been done at 0.9.47 and has not
been done at 0.9.48. Only the plan exists.

## Everything else Ray typed on 2026-08-20 — VERBATIM

> start the mise/hk resync

> fix all three and test the changes

> the purpose of tasks."update:claude" is to update the marketplace and all plugins for all claude projects on this box
> if we can parallize it using mise, that would be ideal
> and it doesnt have to be a shell command, we can use python instead if that makes it easier to read/manage and parallelilze
> - or some ofther programming language

> remove that broken context7 install

> start #397

> run mise run kb-build and see whether build 4 is green

> i added comments to the artifact on what to research

> run the four lanes

> can you do a quick test to see if we can at least get it complete by running command 'update-all' under directory ~/.config/mise/

> provide me the exact prompt to run for /subtask

---

## One attribution correction, made rather than inherited

The 2026-08-20-d handoff listed **"update all first level dependencies and get
codex to 0.149.0"** under *"Ray, this round"*. Searching all 94 extracted human
messages for `0.149` returns **nothing**; the nearest real quote is from
**2026-08-18** (`773421d1`):

> the outputs of these commmand need to have zero outdated first level dependencies (these checks need to be integrated into our kb currency sweeps and have agents perform the same relese-notes/feature/changes review):

So the standing requirement — **zero outdated first-level dependencies, checked
by the currency sweep, with agents doing the same release-notes review** — is
real and is Ray's. The specific target `0.149.0` is not traceable to a message
and should be treated as a session's own inference until re-confirmed. The
requirement is what carries forward; the version number is not evidence.
