# Refutation — [circles] "session-review ... no run of it has ever gated anything"

VERDICT: **REFUTED** on the load-bearing clause. Two of the four runs it enumerates
produce an artifact a live gate reads and refuses on — and that gate is failing on
HEAD right now.

## What reproduces exactly (not disputed)

    awk -F'\t' '$3=="Workflow"' tools.tsv            -> 4 rows, timestamps as stated
    awk '($3=="Edit"||$3=="Write") && $4 ~ /session-review\.js/' | wc -l   -> 41
    awk '$2>="2026-08-18T08:00" && $2<="2026-08-18T18:30"' | wc -l         -> 564
    wc -l tools.tsv                                                        -> 1693

## The refutation

Runs 3 and 4 ran `mode:"handoff"` with `handoffOut:".agent/plans/session-2026-08-18-c.md"`
(verbatim in the Workflow args, tools.tsv:1490). That file exists, 10,570 B.

`kb_setup.pr._handoff_holds` (python/src/kb_setup/pr.py:404-448) reads the newest
`.agent/plans/session-*.md` and `kb-ship` REFUSES the push when it is BROKEN.

    $ uv run python -c "... handoff.check_for_branch(Path('.'), 'docs-directive-addendum')"
    source: session-2026-08-18-c.md
    coverage: Coverage.BROKEN
    summary: `session-2026-08-18-c.md` records branch `docs-directive-addendum` — 2 broken, 20 OK
    WOULD kb-ship REFUSE?: True

    CONTROL ARM (same call, branch the handoff does not record):
    coverage: Coverage.SKIPPED  |  WOULD kb-ship REFUSE?: False

    $ mise run kb-handoff-check
    FAIL  reconcile .agent/plans/session-2026-08-18-c.md:24 ...
    FAIL  reconcile .agent/plans/session-2026-08-18-c.md:129 ...
    20 OK, 6 ambiguous, 0 unverifiable, 2 broken   (only broken exits 1)
    [kb-handoff-check] ERROR task failed

The gate is not incidental: `.claude/skills/kb-session-review/SKILL.md:209` —
"**Always run `mise run kb-handoff-check` on the result.**" — and
`.claude/workflows/session-review.js:179` says the caller validates with it.
The round's own transcript records it happening (tools.tsv:1584, 17:53:47Z):
"It wrote `.agent/plans/session-2026-08-18-c.md` and **ran `kb-handoff-che[ck]**".

So "a run that produces nothing is indistinguishable from one that produces
everything" is false for handoff mode: a run that produces nothing leaves no
handoff, and one that produces a wrong handoff makes `kb-ship` refuse.

## Second defect — the 564 is a TIME WINDOW read as ATTRIBUTION

    in-window rows mentioning session-review at all : 169  (30%)
    in-window rows mentioning graphify_semantic_*   :   6
    in-window rows mentioning NEITHER               : 385  (68%)

The window opens at 08:00Z, **3h10m before the first launch (11:10:24Z)**. Rows
08:00-08:22Z are clear-prep handoff writing, `gh api` bot-review triage and
`check_first.py`/`graphify_*` reads — not session-review. Token-attributable
share is 189/1693 = 11%, not 33%.

## Cross-check against finding 3 (no contradiction)

Finding 3's window (first->last `graphify_semantic_corpus*` Edit/Write) is
2026-08-17T22:49:20Z -> 2026-08-18T06:48:24Z, 1,037 rows. Overlap with the
08:00-18:30Z window: **0 rows**. The two are disjoint; they share the same
window-as-attribution weakness but do not double-count.

## Scope note (minor)

"ever" is wider than the probe: a 5th launch exists — an inline-script Workflow
named `kb-session-review` at 2026-08-17T20:53:28Z in session fb633adf, found by
scanning all 238 transcripts (24,266 tool_use records; control: 8 `kb-extract`
Workflow launches, so the scan discriminates). 2 of the 41 edits (hours 04Z, 06Z)
also fall outside the stated 08:00-18:30Z window.
