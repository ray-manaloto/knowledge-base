# Refute lane — unpinned finding #22 (#414 "P1 blocker", 55.1% duplicate tokens)

CLAIM: "#414 P1 blocker: 55.1% of 1,038,052 estimated tokens (571,462 tokens, ~$36)
is byte-identical re-extraction across different paths; planner dedup keyed only on
(path,slice_index)"

VERDICT: **REFUTED** — the measurement half is true of a SUPERSEDED artifact; the
mechanism half and the "P1 blocker" framing are false at HEAD (b30a80c9).

## The decisive probe (the synthesis's OWN probe, re-run at both ends)

Synthesis §1 G3 (docs/research/reports/2026-08-21-session-review-synthesis.md:107-110)
states: "The only duplicate check in the planner is graphify_semantic_corpus.py:1452-1454,
keyed on (unit.path, unit.slice_index) ... grep -c "dedup" over that module -> 0 with
control arms `def ` -> 82".

Re-run, same command shape, both ends:

    grep -c "dedup" python/src/kb_setup/graphify_semantic_corpus.py                      -> 17   (HEAD b30a80c9)
    git show 3d9bb3ff~1:python/.../graphify_semantic_corpus.py | grep -c "dedup"         ->  0   (pre-fix)
    grep -c "def "  ... HEAD -> 87 ; pre-fix -> 83                                       (control: probe discriminates)

The probe reproduces the finding's 0 exactly at 3d9bb3ff~1 and returns 17 at HEAD. The
finding is a pre-fix reading carried forward.

## The fix, and proof it is not decorative

git log --oneline 8929d47f..HEAD (branch corpus-gate-bundle-0821, 7 ahead of origin/main):
  3d9bb3ff feat(corpus): dedupe byte-identical paths at plan time (#414)
  964fb112 fix(corpus): answer cold review of #414 ...

graphify_semantic_corpus.py:1310-1364 — "Content-hash dedupe (#414)": key is
`canonical_by_parent.setdefault(member.sha256, relative)` (line 1352), i.e. parent_sha256,
NOT (path, slice_index). Line 1450's `by_identity = {(unit.path, unit.slice_index): ...}`
survives but is the chunk-ledger unit identity, no longer "the only duplicate check".

ARM (fix-claims need one): mutate line 1352 back to the path-keyed form the finding
describes — `canonical_by_parent.setdefault(relative, relative)`:
  HEAD   : pytest ...::test_duplicate_content_is_admitted_once_and_recorded_with_its_canonical -> PASS
  MUTANT : same test -> FAILED, "assert 0 == 1 ... duplicate_groups"
  restored -> PASS
The mutant is the exact pre-fix behaviour, and it dies at the intended line.

## The stale plan cannot even be executed

graphify-out/graphify-semantic-corpus/source-inventory.json (mtime Aug 20 22:23, i.e. BEFORE
the fix) is schema_version 1, 475 units, sum(estimated_tokens) = 1,038,052, duplicate_groups
absent — so the finding's measurement is arithmetically CORRECT against that file.
But decoding it under HEAD's type:
    msgspec ValidationError: Object missing required field `duplicate_groups`
CONTROL ARM: supplying the five new required fields makes the same decode succeed
("CONTROL DECODED OK schema 2 units 475 admitted_tokens 1038052"), so the failure is the
schema bump, not a broken decoder. The 571k-token duplicate plan is unloadable at HEAD.

Commit 3d9bb3ff's own re-plan measurement: 28 groups / 257 paths / 305 units / 571,462 of
1,038,052 (55.1%) dropped; admitted 170 units / 466,590 tokens; chunks 58 -> 26.

## What survives

- The NUMBERS (1,038,052 / 571,462 / 55.1%) are verified — gh issue view 414 body and the
  commit's independent re-derivation agree to the digit.
- gh issue view 414 --json state -> OPEN. But an open issue is not current state (the repo's
  own probes-need-a-control-arm.md worked case). All three acceptance criteria are
  implemented in 3d9bb3ff/964fb112.
- "~$36" appears nowhere in #414's body; it is the synthesis's own derived slice of ~$65,
  and the completeness report already marks G3 "no lane claim at all ... never adversarially
  passed" (docs/research/reports/2026-08-21-session-review-completeness.md:65).

## Contradictions with other live findings

- **Finding 21** ("#426 P0 ... execution will stage 58/58 chunks failed (~$65, ~10.6h)") rests
  on the SAME pre-dedupe plan. 3d9bb3ff records chunks 58 -> 26 and admitted tokens 466,590,
  so 58/58 and ~$65 are stale by the same commit. Two findings, one superseded artifact.
- **Finding 35** (readiness doc still carries 6 stale figures, untouched since 8929d47f) is
  CORROBORATED and explains this one: `git log 8929d47f..HEAD -- <synthesis>.md` is empty
  while the module it describes changed in 4 commits. Finding 22 is an instance of 35.

## Shell hazards hit while probing (recorded, per the brief)
- `grep --include=*.md` unquoted -> zsh "no matches found", a FALSE zero. Quoted it.
- `echo ===` -> zsh EQUALS-expansion, "== not found".
- `cmd | tail; echo $?` returned tail's 0 while the test had FAILED — read the body, not the rc.

## GitHub repos touched
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issue #414, branch corpus-gate-bundle-0821

## Cross-lane hazard observed (do NOT revert it)
After my mutation was restored (`sed -n 1352p` -> the sha256-keyed form, test green), a
SECOND, foreign edit appeared in the same file at line ~240: `_measured_runtime` replaced by
a hardcoded `RuntimeIdentity(version="0.9.47", ...)`. My pre-mutation backup is byte-identical
to `git show HEAD:` (diff empty), so it was written after 08:xx by a CONCURRENT lane — almost
certainly the lane arming finding 21 (#426, _ACCEPTED_GRAPHIFY_RUNTIME at 0.9.47). I left it
in place rather than `git checkout --` it; reverting would destroy another lane's in-flight arm.
My own mutation at 1352 IS restored.
