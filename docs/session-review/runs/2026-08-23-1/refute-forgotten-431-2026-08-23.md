# Refutation lane — finding [forgotten] #431 "zero comments and zero commits since filing"

VERDICT: **REFUTED** (the "zero commits" half, and the evidence that supported it).

## The claim
"#431 ... has zero comments and zero commits against it since being filed 2026-08-21,
across 3 subsequent rounds (e, f, and this one)."
Evidence offered: `gh issue view 431 --json state,updatedAt` -> updatedAt == createdAt
"(never touched again)"; `--json comments` -> 0.

## Probe that returns the opposite answer
```
gh api repos/ray-manaloto/knowledge-base/issues/431/timeline --paginate \
  --jq '.[] | {event, created_at, actor: .actor.login, src: (.source.issue.number // null)}'
{"actor":"sortakool","created_at":"2026-08-21T17:12:23Z","event":"cross-referenced","src":435}
{"actor":"sortakool","created_at":"2026-08-21T17:42:40Z","event":"cross-referenced","src":437}
{"actor":"sortakool","created_at":"2026-08-22T18:11:46Z","event":"cross-referenced","src":451}
{"actor":"sortakool","created_at":"2026-08-22T21:07:16Z","event":"referenced","src":null}
{"actor":"sortakool","created_at":"2026-08-23T03:23:31Z","event":"referenced","src":null}
```
`referenced` is GitHub's event for **a commit referencing the issue**. Their commit ids:
```
gh api .../issues/431/timeline --jq '.[]|select(.event=="referenced")|{created_at,commit_id}'
{"commit_id":"cc26510121c752a87eb0a2002a5c68ca1f90eb01","created_at":"2026-08-22T21:07:16Z"}
{"commit_id":"272d14bc3785e07bf935bb356d63af427354eba1","created_at":"2026-08-23T03:23:31Z"}
```
272d14bc is **this round's own landed merge** ("corpus gate bundle rebased (#463)").
So 5 post-creation events, 2 of them commits — not "never touched again", not "zero commits".

Also missed: `a4ca09e2` (author date 2026-08-21 11:12:41 -0500 = 16:12:41Z, **23 min after
filing**), body line 4: "a session-review lane overwrote `.agent/notepad.md` mid-round (#431)
— so, per agent-report-persistence.md rule 1b ... promoted verbatim", 13 files into
docs/research/reports/. That is remedy (1) of the #431 memory note, landed as a commit.

## Why the original probe could only give the answer it gave
`updatedAt` on this repo's issues does **not** move for `referenced` / `cross-referenced`:
```
#433 created=2026-08-21T15:50:24Z updated=...T15:50:24Z same=true   (timeline: 2 cross-referenced)
#424 created=2026-08-21T04:38:56Z updated=...T04:38:56Z same=true   (timeline: 2 referenced + 2 cross-referenced)
#431 created=2026-08-21T15:49:39Z updated=...T15:49:39Z same=true   (timeline: 5 events)
```
Other direction (probe is not universally frozen): #417 same=false (has comments),
#459 same=false. So `updatedAt` tracks COMMENTS, and the gloss "never touched again"
extended a comment-probe over a commit question.

## Control arm for the timeline probe
`#457` -> ["labeled","labeled","labeled"] and `#458` -> ["labeled","labeled","labeled"]:
zero `referenced`, zero `cross-referenced`. The probe can return "no commit touched this".

## What SURVIVES of the finding (do not discard)
- **0 comments is true.** Control: `#459` -> 2 comments, so the comments probe discriminates.
- **The mechanism is genuinely unbuilt.** `.claude/workflows/session-review.js:280`
  `const reportDir = cfg.reportDir || '.agent/kb/reports/agents'`; `:353`
  "Write your findings to ${reportDir}/<your-lane>.md"; `:392`
  "${reportDir}/refute-<lane>.md" — still fixed shared paths (#431 remedy 3).
  `grep -rln notepad python/src/kb_setup/` -> only `citations.py` (control:
  `grep -rln reportDir` n/a; the guard remedies 1-2 have no module).
  This lane's own brief handed me `refute-<lane>.md`, i.e. the collision is live.
- Handoffs corroborate the carry: `session-2026-08-22-e.md:160-163`, `-f.md:31,51,79`.

## Contradiction with other live findings
None contradicts. #17 (kb-session-reflect blind to repeating structure) and #19
(Repowise dead-code FPs on session-review.js) are adjacent, both consistent.

## GitHub repos touched
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issue timelines, git history.
