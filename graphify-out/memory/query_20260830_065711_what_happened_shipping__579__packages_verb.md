---
type: "query"
date: "2026-08-30T06:57:11.941417+00:00"
question: "What happened shipping #579 (packages verb)?"
contributor: "graphify"
outcome: "useful"
---

# Q: What happened shipping #579 (packages verb)?

## Answer

Shipped #579 (packages verb) via codex-implementer, 4 dispatch rounds:
1. First dispatch: legitimate dissent — adding httpx2 as a direct dependency
   forces `uv lock` to re-resolve, and codex's sandbox has no network egress
   for the git-sourced `graphifyy` dependency that touches. Confirmed with a
   real control arm (clean repo passes, modified repo fails on git fetch).
2. Architect ran `uv lock` in a network-enabled environment, produced the
   exact 2-line lockfile diff, sent it back for a hand-apply (no re-resolve).
   The premise-hook required a literal PREMISES heading even on a correction
   round — a prose reference to "the restated premises" did not satisfy it.
3. Second dissent, same class: `mise run kb-codegen` needs network for a
   DIFFERENT locked transitive dep (`more-itertools`, via datamodel-code-generator).
   Architect ran kb-codegen directly (had network), regenerated
   research_record.py, handed codex the remaining mechanical lint/format/test
   work plus the pre-computed ruff findings list.
4. Cold review (Opus fallback, since codex genuinely implemented this one and
   grok isn't installed — same-family codex-reviewer would not be cross-family)
   found 7 findings, 2 blocking: an unencoded-dot-segment path-traversal that
   let a bogus "package not found" null pass its own control arm, and
   unbounded untrusted-string lengths that crashed validate(). Both fixed in
   a follow-up commit, verified directly by the architect (not just trusted
   from the report), gates re-run clean (7/7) on the fix SHA.
Landed as PR #629 (95454d39). kb-land hit the #619 worktree-branch-delete
misreport again (5th+ recurrence this round) — confirmed the actual merge
succeeded via `gh pr view --json state,mergedAt,mergeCommit` before treating
it as landed.


## Outcome

- Signal: useful