# refute — pending-work finding 30 (three audits, zero cleanup)

CLAIM: "The exact same worktree/branch/stash pending-work inventory has now been
flagged by THREE separate audits (2026-08-18, an earlier 2026-08-23 session, and
this pass) with zero cleanup action taken across 5+ days and 13+ landed PRs."

## Probe 1 — is the inventory "the exact same"? NO.

    awk '/^\| branch \| ahead/,/^## Per-branch disposition/' \
      docs/session-review/runs/2026-08-18-1/pending-work.md | ... | sort -u > /tmp/b18.txt
    git for-each-ref --format='%(refname:short)' refs/heads | sort > /tmp/bnow.txt
    comm -23 /tmp/b18.txt /tmp/bnow.txt   # gone since 08-18: docs-directive-addendum
    comm -13 /tmp/b18.txt /tmp/bnow.txt   # new since 08-18: claude-resync-2.1.241, close-2026-08-20-round

24 branches at audit 1, 25 today. One branch was DELETED (docs-directive-addendum,
the 08-18 round's own branch), and one NEW stale branch was ADDED to the pile
(close-2026-08-20-round, absent from audit 1, flagged in audit 2 §3). The pending-work
pile ACCRETED between audits; it is not "the exact same inventory".

My own first extraction of that list was bound-limited (`grep -oE '\|\|\|'` missed the two
rows carrying an upstream field: 22 not 24). Re-derived from the ahead/behind table.

## Probe 2 — "reproduce identical SHAs": false for the refs that moved.

Audit 2 (docs/session-review/runs/2026-08-23-1/pending-work.md, header) records
HEAD == origin/main == main == `272d14bc3785`. Today `git for-each-ref refs/heads`
gives main `c4ea46a0` and claude-resync-2.1.241 `24d11e49`. The salvage/*, chore/*,
codex/* SHAs and both stash subjects DO reproduce identically.

## Probe 3 — did the three audits actually flag THE SAME THING? No: two of them
give OPPOSITE verdicts on the two headline items, and audit 2 is wrong on both.

    git show c8b821ca --name-only --format=''   # chore/round-close-2026-08-09b
    git cat-file -e origin/main:<that path>     # -> PRESENT
    git show 771f022e --name-only --format=''   # chore/session-work-memory
    git cat-file -e origin/main:<that path>     # -> PRESENT

- audit 1 (08-18): both files "EXIST on origin/main" (superseded).
- audit 2 (08-23-1 §4): both "confirmed MISSING from origin/main ... a genuine
  unlanded lesson". **Ground truth: PRESENT. Audit 2 is wrong.**
- Reverse direction: `git cat-file -e origin/main:python/src/kb_setup/critical_corpus.py`
  and `:colibri_canary.py` -> ABSENT. Audit 1 called
  salvage/canonical-worktree-snapshot "confirmed sole copy, at risk"; audit 2 §3 filed
  it under "content-verified LANDED (safe to delete) ... Superseded".
  **Ground truth: absent from main. Audit 2 is wrong here too, in the direction that
  would have destroyed the content.**

Control arm for the existence probe: same command shape returns ABSENT for
`.claude/skills/gh-stack/SKILL.md` and a bogus path, PRESENT for `CLAUDE.md` and
`python/src/kb_setup/graph.py`.

## Probe 4 — "zero cleanup action taken": an action WAS taken and is tracked.

`gh issue view 368` — OPEN, labels P2 + directive, created 2026-08-18T21:03:40Z, i.e.
filed BY audit 1. Its body assigns a per-branch disposition, records Ray's clarification
that "the backup directory" IS salvage/canonical-worktree-snapshot plus the 4 linked
worktrees, and parks the rest on a human: the worktrees "should probably be removed —
but that needs confirmation, not inference"; the skillopt branches are "Ray's call".
Deletion has not happened because the audit escalated it, not because nobody looked.


## Probe 5 — "THREE separate audits" is a BOUNDED count. There were at least FOUR.

    find . -name '*pending-work*' -print   # unbounded, no -maxdepth, no 2>/dev/null

A fourth pending-work lane ran on **2026-08-22**:
`.agent/kb/reports/agents/2026-08-22-session-review/pending-work.md`
(stat: birth 2026-08-22T16:51:12Z, 15,705 bytes, `main = cc26510121c7`).
It is invisible to the claim because `.agent/**` is gitignored and the claimant
enumerated only tracked `docs/session-review/runs/`. Its inventory is NOT the same
either — its **headline** item is a branch none of the other three ever saw.

## Probe 6 — the decisive one: a pending-work finding WAS acted on inside the window.

The 08-22 lane's headline: `corpus-gate-bundle-0821`, "10 unmerged commits that
already fix two OPEN issues ... no PR was ever opened".

    git for-each-ref --format='%(refname)' | grep -i 'corpus-gate'   -> rc=1 (no ref anywhere)
    control: same shape | grep -c 'salvage/stash-0'                 -> 2 (probe discriminates)
    gh pr view 463 --json ... -> {"n":463,"head":"corpus-gate-bundle-rebased",
                                  "s":"MERGED","m":"2026-08-23T03:23:29Z",
                                  "c":"272d14bc3785e07bf935bb356d63af427354eba1"}

So between the 08-22 audit and today the branch was rebased, LANDED as PR #463, and
its refs removed — i.e. a pending-work item was cleaned up within ~11 hours of being
flagged, inside the exact "5+ days / 13+ landed PRs" window the claim says produced
zero action. (PR counts: 19 merged since 2026-08-18T00:00Z, 15 since #368 was filed —
that half of the claim is accurate.)

## Probe 7 — the remaining non-cleanup is PROHIBITED, not neglected.

`~/.codex/archives/repo-recovery/20260813T195951Z/FREEZE-STATUS.md`, captured
2026-08-13, "Blocking gate ... Prohibited until the gate clears":

    - No checkout cleanup or reset.
    - No worktree or clone removal.
    - No branch deletion.
    - No canonical directory replacement.
    - No Graphify upgrade work.

The gate is unlifted (finding 34 in this same set). And #368 records Ray's
clarification that the 4 linked worktrees + `salvage/canonical-worktree-snapshot`
ARE "the backup directory" his 2026-08-18 directive says must not lose pending work.
Deleting them is the action the directive and the freeze both forbid.

## VERDICT: REFUTED

Four of the claim's five load-bearing components fail:
- "exact same inventory" — 24 -> 25 branches; one deleted, two added, one
  (`corpus-gate-bundle-0821`) appeared and was removed between audits.
- "reproduce identical SHAs" — main moved `272d14bc` -> `c4ea46a0`.
- "THREE separate audits" — at least four; the count is bounded to tracked paths.
- "zero cleanup action taken" — #463 landed a flagged branch and removed its refs;
  #368 was filed with per-branch dispositions and escalated to Ray; the residual
  deletions are prohibited by an unlifted freeze gate.
Only "5+ days / 13+ landed PRs" survives (15 PRs since #368).

Bonus free defect: the audits contradict each other and audit 2 (08-23-1) is wrong in
BOTH directions — see Probe 3.

## Contradicts, within this round's own set

- **34** (freeze gate forbids worktree/clone removal and branch deletion) directly
  explains away 30's "zero cleanup action" as compliance.
- **33** (Ray designated those worktrees as the backup directory) — deleting them
  conflicts with the directive.
- **31** ("never reconciled or explicitly decided across 3 audits") vs **36** ("should
  explicitly NOT be merged") — 36 IS an explicit decision, recorded in #368; both
  cannot be true of the same refs.
- **38** (188 vs 93 file counts disagree) is itself proof the audits did not produce
  "the exact same inventory".

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issue #368, PRs #463/#466, branch and ref state.
