# Cold review — verification pass

Range under review: f3e233a92ef2b963f072c287e9be0dcc403fa203..HEAD
HEAD (full SHA): 69b233d54a6de7f86cfad80a32f0d5b9223aeefd

This is a VERIFICATION pass. A prior cold pass already reviewed the range up to
8f54fdafeffac1e2a05bf4020fc87b4141c9a546 and raised three findings, addressed in
commit 69b233d ("fix(review): round-3 cold-lane findings; file the
endpoint-diff gap as #67"). The only content change since 8f54fda is the
32-line delta (`git diff 8f54fda..HEAD --stat`):

```
python/src/kb_setup/review.py | 14 ++++++++++++++
tests/conftest.py             |  7 +++++++
tests/test_gitleaks_scope.py  | 12 +++++++++++-
3 files changed, 32 insertions(+), 1 deletion(-)
```

This report concentrates on that delta: did the three claimed fixes do what
they claim, and did they introduce anything new. Codex (GPT-5.6 Sol,
codex-cli 0.145.0) reviewed the same delta cold, confined to those three
files. I then verified its one finding against the actual tree, ran the
touched test files, and ran `ruff`/`ty` over the changed files.

## Fix 1 — `_delta_paths` docstring states the endpoint-diff bound (python/src/kb_setup/review.py:659-675)

Documentation-only change (no code touched in this function). Verified, not
just trusted:

- The claim "`land` merges with `--squash`" is true:
  `python/src/kb_setup/pr.py:459` passes `--squash` to the merge call.
- The claim rests on `EXEMPT_PATHS`, which exists and matches the described
  shape: `python/src/kb_setup/review.py:125` —
  `EXEMPT_PATHS = ("graphify-out/memory/", "docs/goals/README.md")`.
- The gap the docstring describes (an added-then-deleted file is invisible to
  an endpoint diff) is filed as GitHub issue #67 (OPEN), whose body matches
  the docstring's framing exactly (squash-merge bound holds `main`; the
  pushed-branch exposure is real and unpatched, by design — filed, not fixed
  under this commit).

VERDICT: accurate, no defect. This fix is pure documentation and introduces no
runtime risk.

## Fix 2 — git fixture disables commit/tag signing (tests/conftest.py:58-64)

`run("config", "commit.gpgsign", "false")` / `run("config", "tag.gpgsign",
"false")` are added right after `user.email`/`user.name`, before the first
commit (`tests/conftest.py:67`), and are set on the **local** (per-repo, `-C
tmp_path`) config — never `--global` — so the fix cannot leak into or depend
on the invoking machine's global git config.

Checked that every git commit made by the test suite actually goes through
this same `git` fixture (i.e., nothing bypasses it and could still hit a
global `commit.gpgsign=true`): `commit_file`/`commit_files` fixtures
(`tests/conftest.py:73-107`) and every `git("commit", …)` call in
`tests/test_review.py` (e.g. lines 645, 812, 920, 965, 1049) all call through
the `git` callable bound to the one `tmp_path` repo initialized at
`tests/conftest.py:34-69`. No second, independent git-init path exists in the
test suite that could skip the new config lines.

Ran the touched suite as a live check: `uv run pytest tests/test_gitleaks_scope.py tests/test_review.py -q`
→ all pass (94 tests, 0 failures) on this machine.

VERDICT: fix is complete and correctly scoped (local, not global; applied
before first commit; the only commit path in the suite).

## Fix 3 — RE2 backreference check widened from a literal list to a pattern (tests/test_gitleaks_scope.py:97-104, 126, 139)

`_NOT_IN_RE2` dropped the literal `"\\1", "\\2", "\\3"` entries; a new
`_BACKREFERENCE = re.compile(r"\\[1-9]")` (tests/test_gitleaks_scope.py:104)
replaces the enumeration, checked at line 126
(`assert not _BACKREFERENCE.search(pattern), …`) and exercised on the fail arm
at line 139 (`assert _BACKREFERENCE.search(r"^(a)graphify-out/\4")`).

This does fix the stated defect: the old literal list let `\4` and any
backreference numbered 4+ pass a test whose name promises RE2-safety.
Confirmed live: `\4` now triggers the new check (line 139 passes;
`uv run pytest tests/test_gitleaks_scope.py -q` is green).

### FINDING (codex, confirmed) — the fix itself has a narrower false-positive edge

- Severity: P3 / low (no live impact today — confirmed no current allowlist
  pattern in `.gitleaks.toml` trips it; a `grep -n '\\\\' .gitleaks.toml` for
  a literal double-backslash sequence returns zero hits).
- Claim: `_BACKREFERENCE = re.compile(r"\\[1-9]")` (tests/test_gitleaks_scope.py:104)
  matches a backslash immediately followed by a digit 1-9 **without checking
  whether that backslash is itself escaped**. A regex pattern that
  legitimately matches a literal backslash followed by a digit — written as
  `\\4` in the pattern text (i.e. an escaped backslash, then the digit) — is
  a construct BOTH Python's `re` and Go's RE2 accept (it is not a
  backreference at all, just "match `\` then `4`"). The new check
  misclassifies it as a backreference and would fail
  `test_patterns_are_re2_safe` (tests/test_gitleaks_scope.py:126) for a
  pattern that is actually RE2-safe.
- Reproduced directly (not just asserted):
  ```
  >>> import re
  >>> _BACKREFERENCE = re.compile(r"\\[1-9]")
  >>> pattern = r"\\4"   # regex matching literal backslash + digit 4, valid in RE2
  >>> bool(_BACKREFERENCE.search(pattern))
  True   # false positive — this pattern is not a backreference
  ```
- No current allowlist entry in `.gitleaks.toml` hits this, so it is latent,
  not active. It is a real correctness gap in the test helper: a future,
  legitimate allowlist regex containing an escaped literal
  backslash-then-digit would be wrongly rejected by
  `test_patterns_are_re2_safe`. Fix direction (not applied, per review scope):
  strip escaped-backslash pairs (`re.sub(r"\\\\", "", pattern)`, or a lookbehind
  for an even count of preceding backslashes) before searching for `\[1-9]`.

VERDICT: the P2 defect this fix targets (missed `\4`+ backreferences) is
genuinely closed. The fix itself introduces one new, narrow, currently-inert
false-positive edge case, cited above.

## Other checks run

- `uv run ruff check tests/test_gitleaks_scope.py tests/conftest.py python/src/kb_setup/review.py` → All checks passed!
- `uv run ty check` (same files) → All checks passed!
- No new findings outside the three fixes' own scope; the wider round-2→round-3
  diff (docs/skills/hk.pkl/.gitleaks.toml changes prior to 8f54fda) is out of
  scope for this verification pass per the task framing and was already
  covered by the prior cold pass.

## Summary

| # | Fix | Verdict |
|---|---|---|
| 1 | `_delta_paths` docstring states endpoint-diff bound, files #67 | Accurate, verified against `pr.py` and the filed issue. No defect. |
| 2 | git fixture disables `commit.gpgsign`/`tag.gpgsign` locally | Complete, correctly scoped, only commit path in suite. No defect. |
| 3 | `_NOT_IN_RE2` backreference literal list → `_BACKREFERENCE` pattern | Closes the stated `\4`+ gap. Introduces one new P3 latent false-positive (escaped-backslash-then-digit patterns misclassified as backreferences) — currently inert, no live allowlist pattern trips it. |

## GitHub repos touched

_None._ (No external repo docs/source were consulted for this verification;
all checks were against this repo's own tree, tests, and issue tracker.)
