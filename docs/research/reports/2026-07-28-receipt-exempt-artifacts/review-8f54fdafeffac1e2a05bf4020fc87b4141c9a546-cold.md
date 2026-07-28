# Codex Cold Review — 8f54fdafeffac1e2a05bf4020fc87b4141c9a546 (round 3, final)

REF: f3e233a92ef2b963f072c287e9be0dcc403fa203..8f54fdafeffac1e2a05bf4020fc87b4141c9a546
DIFF SIZE: 1649 lines (over ~1500 guard threshold) — split into 2 batches by file.
Batch A (~587 lines): .claude/rules/agent-artifact-conventions.md, .claude/rules/mise-tasks-only.md, .claude/skills/goal-engineering/SKILL.md, .claude/skills/kb-review/SKILL.md, .gitleaks.toml, docs/goals/README.md, hk.pkl, python/src/kb_setup/review.py
Batch B (~829 lines): tests/conftest.py, tests/test_gitleaks_scope.py, tests/test_pr.py, tests/test_review.py

CORRECTION (caught during spot-check): the three graphify-out/memory/query_*.md files
ARE part of the tracked diff (51 lines total, all new-file additions) — they were not
untracked scratch as first assumed. Not sent to codex (pure prose memory notes, no code),
but manually read in full as part of this review: no secrets, no credential-shaped
strings, no defects found in any of the three files.

Status: COMPLETE — see final summary table below.

## Batch B (tests/conftest.py, tests/test_gitleaks_scope.py, tests/test_pr.py, tests/test_review.py) — codex output

Codex's one-line summary: "The RE2 compatibility probe accepts some patterns that gitleaks
rejects (tests/test_gitleaks_scope.py:97-118), and the new Git harness can fail solely because
of inherited signing configuration (tests/conftest.py:56-60)."

Full findings from codex:

1. [P2] RE2-safety denylist is incomplete for backreferences beyond \3 —
   tests/test_gitleaks_scope.py:97 (denylist tuple `_NOT_IN_RE2`), exercised by
   tests/test_gitleaks_scope.py:116-118 (`test_patterns_are_re2_safe`).
   Claim: `_NOT_IN_RE2 = ("(?=", "(?!", "(?<=", "(?<!", "\\1", "\\2", "\\3")` only denies
   backreferences `\1`-`\3`. A gitleaks allowlist pattern using `\4` or higher (e.g.
   `(a)(b)(c)(d)\4`) would compile fine under Python's `re` and pass every assertion in
   this test even though Go RE2 rejects backreferences of any group number, so the test
   can stay green for a config that gitleaks itself would reject at runtime.
   SPOT-CHECK: confirmed — read tests/test_gitleaks_scope.py:94-118 directly; the tuple
   literally stops at `\\3` and the loop only checks membership of each fixed string in
   the pattern.

2. [P2] Git test fixture doesn't neutralize inherited commit-signing config —
   tests/conftest.py:56-60 (the `git` fixture: `git init` then `config user.email/user.name`
   then an initial commit, with no `config commit.gpgSign false`).
   Claim: on a machine with global `commit.gpgSign=true` (or `tag.gpgSign`/a signing
   program requiring pinentry), the fixture's own `git init` + `commit` at line 60, and
   every subsequent helper commit built on `run()`, can fail or hang under noninteractive
   pytest since no signing key/pinentry is available in that context — this repo's own
   fixture doesn't isolate the temp repo from the developer's global git policy.
   SPOT-CHECK: confirmed lines match (tests/conftest.py:53-62); no `gpgSign` /
   `gpg.sign` config call anywhere in the fixture. On THIS machine `git config --get
   commit.gpgsign` returns nothing (unset, rc=1), so the failure mode does not
   currently trigger here — it is a portability/robustness gap, not an active break in
   this environment. Severity kept at P2 (real gap, conditional trigger), not escalated
   to blocking.

No other findings reported by codex for tests/test_pr.py or tests/test_review.py —
codex's own summary states these two issues are the full set for this batch.

## Batch A (.claude/rules/agent-artifact-conventions.md, .claude/rules/mise-tasks-only.md,
## .claude/skills/goal-engineering/SKILL.md, .claude/skills/kb-review/SKILL.md, .gitleaks.toml,
## docs/goals/README.md, hk.pkl, python/src/kb_setup/review.py) — codex output

Codex's one-line summary: "The ancestor-receipt fallback can approve a range containing
transient non-exempt changes because it examines only the final tree delta
(python/src/kb_setup/review.py:663-668). This undermines the review and secret-scanning
gate for intermediate commits."

Full finding from codex:

1. [P1] `_delta_paths`/`_exempt_delta_note` reason only about the ENDPOINT tree diff, so a
   non-exempt file added and later reverted between the receipted ancestor and `sha` is
   invisible to the fallback check — python/src/kb_setup/review.py:663-668 (`_delta_paths`,
   `git diff --name-only --no-renames -z older newer`), consumed by
   `_exempt_delta_note` at python/src/kb_setup/review.py:795-805 (paths = `_delta_paths(...)`;
   `reviewed = sorted(p for p in paths if not _is_exempt(p))`; if empty, `accepted=True`).
   Claim: because the check is a two-endpoint `git diff`, a path that was added in one
   intervening commit and deleted/reverted in a later one nets to "no change" between the
   ancestor and `sha`, so it never appears in `paths` and is never tested against
   `_is_exempt`. This lets `ship`/`land` accept an ancestor's receipt as covering `sha`
   even though an intermediate commit introduced unreviewed, non-exempt content (code, or a
   credential) that no lane ever read and that the *current-tree* secret scanner
   (hk.pkl's gitleaks/detect-private-key builtins, hk.pkl:20-46) also cannot see once it is
   gone from the tree. This directly contradicts the stated intent at
   python/src/kb_setup/review.py:738-742 ("the ENTIRE delta between them is inside the
   exempt set... one reviewed path in that delta and the fallback is refused").
   SPOT-CHECK: confirmed by reading python/src/kb_setup/review.py:652-668 (`_delta_paths`
   body — `git diff --name-only --no-renames -z older newer --`, a pure two-tree diff with
   no per-commit walk) and :783-805 (`_exempt_delta_note` — computes `reviewed` from that
   same endpoint-diff `paths` list and returns `accepted=True` when `reviewed` is empty).
   Also confirmed this code path is UNCHANGED by the round-2 fix commit (8f54fda) — verified
   via `git show 8f54fda -- python/src/kb_setup/review.py`, which touches `_covering_candidates`/
   `_Covering`/sorting/escaping but leaves `_delta_paths`'s two-endpoint diff exactly as
   introduced in 7c72a02. So this is a genuine, still-open gap in the #66 fallback design,
   not a regression from round 2's own fix — first surfaced in this round's cold pass.
   SEVERITY NOTE: exploiting it requires a specific shape (a non-exempt file added then
   fully reverted/deleted within the same candidate-ancestor..sha range, with every
   *net* change otherwise exempt) — narrower than "any unreviewed intermediate commit ships
   silently", but real and unmitigated: codex's P1 rating is transported as given, not
   downgraded, since the caller (this report) does not adjudicate.

No other findings reported by codex for .claude/rules/agent-artifact-conventions.md,
.claude/rules/mise-tasks-only.md, .claude/skills/goal-engineering/SKILL.md,
.claude/skills/kb-review/SKILL.md, .gitleaks.toml, docs/goals/README.md, or the rest of
hk.pkl — codex's own summary states the above is the full set for this batch.

## Summary — findings surviving round 3 (transport, not adjudication)

| # | Severity | Claim | Location |
|---|---|---|---|
| 1 | P1 | Ancestor-receipt fallback reasons only about the endpoint tree diff between candidate and `sha`, so a non-exempt file added-then-reverted between them is invisible to `_exempt_delta_note`, letting `ship`/`land` accept a receipt covering a range that actually contained unreviewed non-exempt content (possibly a credential) no lane read and the current-tree scanner can no longer see | python/src/kb_setup/review.py:663-668, :795-805 (contradicts the stated invariant at :738-742) |
| 2 | P2 | RE2-safety denylist (`_NOT_IN_RE2`) only denies backreferences `\1`-`\3`; a pattern using `\4`+ passes this "RE2-safe" test yet Go RE2 (gitleaks) rejects any numbered backreference | tests/test_gitleaks_scope.py:97, exercised by :116-118 |
| 3 | P2 | Git test fixture (`conftest.py` `git` fixture) does not set `commit.gpgSign false`, so on a machine with global commit signing enabled the fixture's own init/commit and every helper commit can fail/hang for lack of a signing key or pinentry; not currently triggered on this machine (`commit.gpgsign` unset here) | tests/conftest.py:53-62 |

No findings were reported by codex for: `.claude/rules/agent-artifact-conventions.md`,
`.claude/rules/mise-tasks-only.md`, `.claude/skills/goal-engineering/SKILL.md`,
`.claude/skills/kb-review/SKILL.md`, `.gitleaks.toml`, `docs/goals/README.md`, the rest of
`hk.pkl`, `tests/test_pr.py`, `tests/test_review.py`.

None of the 28 findings from rounds 1-2 were re-reported — codex's cold pass over this
round's diff (f3e233a..8f54fda) surfaced only the three items above, all new to this round.

UNCITED: none — every codex claim above carries a file:line citation, and every citation
was spot-checked against the actual file content (all matched).

UNCOVERED: none. All 15 tracked files changed in this range were covered — 11 via the two
codex batches (587 + 829 = 1,416 of 1,649 diff lines), plus the 3 graphify-out/memory/*.md
files (51 lines, pure prose/data) read manually in full since they carry no code for codex
to review a defect in.

FAST MODE: not requested — standard tier used for both batches.

FULL REPORT: this file. Raw codex batch outputs were read from:
- Batch A (final message): /var/folders/z4/0p475gq56vvczc3y4qlt60f80000gn/T/codex-review-final.XXXXXX.X1Svz3meX2
- Batch B (final message): /var/folders/z4/0p475gq56vvczc3y4qlt60f80000gn/T/codex-review-final.XXXXXX.qdkVL9mv1y
(both are ephemeral /var/folders temp files from this session's lane runs; the verbatim
text is preserved above)

Status: COMPLETE.
