# `#66` — the exempt-delta receipt fallback, and the credential it uncovered

Ten verbatim lane reports from the four review passes over `fix/receipt-exempt-artifacts`
(merged as `d530258`, PR #69). Promoted out of gitignored `.agent/` because
**tracked files now cite their measurements** — see "What rests on these" below.

Not normalised, not trimmed (`docs/research/README.md`). SHAs are the commit
each pass read; the round-1 SHA no longer exists in history, deliberately.

| Pass | SHA | Lanes | Findings | Blocking |
|---|---|---|---|---|
| 1 | `9db94ea` *(rewritten out of history)* | all four | 19 | **4** |
| 2 | `7c72a02` | all four | 9 | 0 |
| 3 | `8f54fda` | cold only | 3 | 0 |
| verify | `69b233d` | cold only | 1 | 0 |

Round 1's SHA is unreachable because that commit contained three live
credentials and the branch was rebuilt so no commit ever held them. The reports
describing the finding survive; the blob does not.

## What rests on these

- **`.gitleaks.toml`**'s comment block — the allowlist was scoped on the
  measurement in the round-1 silent-failure report: in-repo scan of the offending
  file → `scanned ~0 bytes`, the same bytes outside the allowlist → `leaks found: 3`.
- **`hk.pkl`**'s `exclude` / `proseExclude` split — rests on the round-2
  silent-failure report's measurement that **`gitleaks dir` ignores its path
  arguments once there is more than one** (1 arg → 5.01 KB scanned, 2 args →
  8.62 MB, flagging a token in a path named by neither), which is why the
  scanner appeared to cover paths every other builtin was blind to.
- **`tests/test_gitleaks_scope.py`**'s module docstring — the incident it is a
  regression gate for.
- **Issues #67 and #68** — both filed from round-3 and verification findings,
  with the reasoning for filing rather than fixing recorded in the reports.

## The finding worth reading first

Round 1, standards lane, **S1**: a `kb-remember` work-memory note *about* two
agents leaking credentials had the probe output pasted into it verbatim — three
live tokens, in a tracked file, in a public repo. Every gate was green over it.
The cold and silent-failure lanes reached the same finding independently, and
the silent-failure report carries the four-arm control table that proves the
scanner was configured to look away rather than looking and finding nothing.

Nothing reached the remote: 0 hits across all 57 commits of `origin/main`
against a control term returning 487.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review.
- [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) — 8.30.1 arg-handling and RE2 behaviour, probed directly rather than read.
- [jdx/hk](https://github.com/jdx/hk) — `Config.pkl` / `Step.pkl` schema, for whether a per-step `exclude` overrides the global (it does).
