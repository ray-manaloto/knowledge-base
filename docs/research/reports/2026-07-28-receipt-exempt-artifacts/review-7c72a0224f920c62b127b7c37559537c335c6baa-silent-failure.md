# Silent-failure lens — round 2 — `f3e233a..7c72a02`

HEAD: `7c72a0224f920c62b127b7c37559537c335c6baa`
Range: `f3e233a92ef2b963f072c287e9be0dcc403fa203..HEAD`

Commits in range:

- `65caf23` fix(security): gitleaks was allowlisting the one committed graphify-out path
- `eb91aaf` chore(memory): fold in the Legible round's orphaned P7 artifacts
- `7c72a02` fix(review): an ancestor receipt covers HEAD when the delta is exempt (#66)

Changed surface: `python/src/kb_setup/review.py` (+277/−25), `.gitleaks.toml`,
`tests/test_review.py`, `tests/test_pr.py`, `tests/test_gitleaks_scope.py`,
`.claude/skills/kb-review/SKILL.md`, `.claude/skills/goal-engineering/SKILL.md`,
`docs/goals/README.md`, three `graphify-out/memory/*.md` notes.

`uv run pytest tests/test_review.py tests/test_pr.py tests/test_gitleaks_scope.py -q`
→ 112 passed. All probe files created during this review were removed;
`git status --short` is clean and `.gitleaks.toml` is byte-identical to HEAD
(`git diff --stat -- .gitleaks.toml` → empty).

---

## Findings

### M1 — MEDIUM — the `EXEMPT_PATHS` "scanner coverage is a PRECONDITION" claim rests entirely on an undocumented `gitleaks dir` argument-handling accident; every other hk builtin is measurably blind to those paths, and the test that pins it deliberately never runs the scanner

**Claim:** `python/src/kb_setup/review.py:109-113` and `.gitleaks.toml:11-18`
both assert that because a commit whose whole delta is `graphify-out/memory/**`
can now ship without any review lane reading it, **scanner** coverage of that
path is load-bearing. That coverage is real today, but it is held up by a
behaviour nothing in this repo documents, pins, or tests — and `hk.pkl` is
actively configured against it.

**The chain, measured:**

1. `hk.pkl:15-19` sets a **global** `exclude = List("graphify-out/**", …)`,
   documented in hk's own `Config.pkl:76` as *"Global exclude patterns that apply
   to all hooks and steps"*. It really applies: adding one file under
   `graphify-out/memory/` left hk's file count at **172**; adding one under
   `docs/` raised it to **173**.
2. `Builtins.gitleaks` is `gitleaks dir --redact --verbose --no-banner
   {{ files }}` (hk `builtins/gitleaks.pkl:14`) — a `{{ files }}` consumer, so
   on the plain reading the exempt path is never passed to it.
3. It is nonetheless scanned, because **`gitleaks dir` ignores its path
   arguments once there is more than one**:

   | invocation | bytes scanned | verdict |
   |---|---|---|
   | `gitleaks dir … .agnix.toml` (1 arg) | 5.01 KB | honours the arg |
   | `gitleaks dir … .agnix.toml CLAUDE.md` (2 args) | **8.62 MB** | scans the whole tree — flagged a planted token in `graphify-out/memory/`, which is in **neither** arg |

   hk passes 172 args, so the gitleaks step is in effect
   `gitleaks dir .` and `.gitleaks.toml` is doing 100% of the scoping.
4. Builtins that **do** honour `{{ files }}` are correspondingly blind. Probed
   with a synthetic PEM header, both arms, `hk run check --all --step
   detect_private_key`:

   | file | result |
   |---|---|
   | `docs/zzz_probe_key.md` (control) | **FLAGGED**, rc=1 |
   | `graphify-out/memory/zzz_probe_key.md` | **not flagged** |

   Same for `typos`, `rumdl`, `check_added_large_files`, `trailing_whitespace` —
   every `{{ files }}` builtin.
5. `tests/test_gitleaks_scope.py:17-20` states outright that it is
   *"Config-level, not a gitleaks invocation"*. So the one arm that would notice
   the coverage disappearing does not exist. The suite stays green whether or
   not gitleaks ever reads those paths.

**Hidden errors this can suppress:** any secret, oversized blob, or malformed
content committed under `graphify-out/memory/**` after gitleaks changes its
`dir` argument handling (a version bump, a `--max-target-megabytes` default, a
switch to `gitleaks git`) — at which point `hk.pkl`'s `graphify-out/**` exclude
removes the file from `{{ files }}` and the step scans nothing there, silently.
That is precisely a "could not check rendered as a pass": the config test still
passes, `mise run lint` still exits 0, and no review lane reads the path either
because `EXEMPT_PATHS` removed the only lane read it would ever get.

**Severity rationale — why MEDIUM, not HIGH:** coverage is *currently* real. I
control-armed the whole point of `65caf23` end-to-end and it holds:

| `.gitleaks.toml` allowlist | `graphify-out/memory/zzz_probe_leak.md` | `docs/zzz_probe_leak.md` (control) | leaks |
|---|---|---|---|
| HEAD (enumerated) | **FLAGGED** | FLAGGED | 2 |
| pre-fix (`'''^graphify-out/'''`) | skipped | FLAGGED | 1 |

(Token used was gitleaks' own public test fixture from `builtins/gitleaks.pkl`,
not a live credential.) The control fires in both arms, so the probe
discriminates; the only variable is the allowlist. gitleaks also catches PEM key
material there, so `detect_private_key`'s blindness is redundancy loss rather
than an open hole *today*.

**Recommendation** — pick either, in the same change:

- carve the exempt paths out of `hk.pkl`'s global exclude, e.g. give the
  `gitleaks` and `detect_private_key` steps a step-level
  `exclude` that omits `graphify-out/memory/**` (`Config.pkl:699-727` supports
  per-step override), so the coverage comes from the file list rather than from
  gitleaks' arg handling; **and/or**
- add one invocation-level arm to `tests/test_gitleaks_scope.py` that plants the
  public fixture token under `graphify-out/memory/` in a tmp repo and asserts
  the pinned `gitleaks` binary reports it, with the `docs/` control beside it.
  The test's stated reason for not doing this ("a slower question less
  directly") is exactly backwards here: the config regex was never the only way
  this coverage can vanish.

**Files:** `.gitleaks.toml:11-18`, `tests/test_gitleaks_scope.py:17-20`,
`hk.pkl:15-19`, `python/src/kb_setup/review.py:109-113`.

---

### L2 — LOW — the refusal reported when every ancestor is rejected is the first one `git rev-list` yields, which the code's own docstring says is not the nearest; combined with `_MAX_NAMED_PATHS` it can name the wrong delta and hide the real one

`python/src/kb_setup/review.py:725-731`:

```python
first_refusal = ""
for candidate in candidates:
    accepted, note = _exempt_delta_note(repo_root, candidate, sha)
    if accepted:
        return candidate, note
    first_refusal = first_refusal or note
return sha, first_refusal
```

`_reviewed_ancestors`' docstring (`review.py:657-660`) correctly retracts the
round-1 claim that rev-list yields the nearest first — *"rev-list orders by
commit date, so a merge can put a farther commit ahead of a nearer one"*. The
loop then keeps the **first** refusal anyway, and `_covering_receipt`'s docstring
justifies that with *"they are usually refused for the same file"*
(`review.py:714-716`), which is the property the other docstring just said does
not hold in the presence of a merge.

Consequence: on a merge-containing branch the refusal can quote a far ancestor's
much larger delta. `_summarise` (`review.py:751-761`) then names five paths
alphabetically and appends `(+N more)`, so the file that actually needs
re-reviewing may not appear at all. This is a diagnosis-quality defect, not a
gate hole — the outcome is still a refusal — but the stated purpose of carrying
the note is "a refusal the reader cannot act on" (`review.py:829-833`), which is
the failure mode it can still produce.

**Recommendation:** report the refusal from the candidate with the **smallest**
reviewed-path set (or the fewest non-exempt paths), not the first encountered —
one `min()` over the collected notes, no ordering claim required.

---

### L1 — LOW — `_covering_receipt` commits to the first ancestor whose *delta* is exempt-only, without checking that ancestor's receipt actually validates; a later ancestor with an equally-exempt delta and a valid receipt is never tried

`python/src/kb_setup/review.py:726-729` returns on the first `accepted`. If that
ancestor's receipt then fails any check in `_all_reasons` /
`_base_coverage_gap`, `receipt_state` refuses outright — it does not fall
through to the next delta-acceptable candidate. `tests/test_review.py:732-749`
and `:858-875` pin the refusal, and `:828-855` pins multi-candidate iteration
for the *delta* dimension only; no test covers "first accepted candidate has a
bad receipt, a later accepted candidate has a good one".

This is **fail-closed** — an unwarranted refusal, never an unwarranted
acceptance — which is why it is LOW and why it is invisible to a green suite.
It is the same class of defect as the round-1 single-candidate bug this commit
fixed (`review.py:651-667`), one dimension over: that one asserted an ordering
property in the delta dimension, this one asserts a "first accepted is as good
as any" property in the receipt-validity dimension.

**Recommendation:** move the receipt validation inside the candidate loop, or at
minimum collect all delta-acceptable candidates and return the first whose
`_all_reasons` is None.

---

## Checked and cleared (no finding)

### The two deliberate asymmetries are intact — neither is inverted

- **`kb_setup.hook_guard` still fails OPEN.** `hook_guard.py:156-176`: every
  error arm (`json.JSONDecodeError`/`ValueError` on stdin, non-Bash tool,
  non-string command, and a bare `except Exception` around `decide`) returns
  `0` = allow, under a docstring that says so (`:159`). Correct — a crashed
  PreToolUse guard must not brick every Bash call.
- **`kb_setup.pr.checks_state` still fails CLOSED.** `pr.py:152-164`: an
  unparsable payload returns `(False, "could not read checks …")`, and the
  element-type check (`not all(isinstance(r, dict) …)`) returns `(False,
  "unexpected checks payload …")`. Only a well-formed empty array is green
  (`pr.py:166-167`). Correct.

### Near-miss worth recording: `hook_guard.py:163` is valid Python, not a Python-2 relic

`except json.JSONDecodeError, ValueError:` — no parentheses. Byte-verified with
`od -c`. This is **PEP 758**, accepted for Python 3.14, which permits unbracketed
exception tuples in `except`/`except*`. Control arm: `py_compile.compile(...,
doraise=True)` on the interpreter this repo pins → `COMPILES OK`. Two probes
disagreed (my reading vs. the compiler) and the compiler was right. Not a
finding; recorded because the next reviewer will trip on the same line.

### Round-1 fixes 1–4, each re-checked against what it could have introduced

1. **`_git_result` returns RAW stdout; `_git` strips** (`review.py:270-331`).
   Verified consistent at every call site: `head_sha`/`base_sha` go through
   `_git` (stripped, and both legitimately never answer empty);
   `_reviewed_ancestors` uses `out.split()` on newline-separated SHAs, immune to
   the missing strip; `_delta_paths` uses `out.split("\0")` and filters empties
   (`review.py:647`), which is the case the raw return exists for. The added
   `UnicodeDecodeError` arm is genuinely reachable (`text=True` decodes strictly
   in `Popen._communicate`) and returns `(False, "")` → `_delta_paths` → `None`
   → refusal. Fail-closed both ways. No new silent path.
2. **`_covering_receipt` tries every reviewed ancestor** — the delta dimension
   is now correct and tested (`tests/test_review.py:828-855`). What it bred is
   L1 and L2 above, both refusal-side.
3. **`note` carried onto the failure returns** (`review.py:834-843`). Traced all
   four states of `(require_base, receipt-exists, candidates, accepted)`:
   `refused` is `True` exactly when `covering == sha` and a note exists, which
   is unreachable when `sha`'s own receipt is present (`review.py:718-719`), so
   the note lands inside `_load_receipt`'s "no receipt" message in that case and
   in the `suffix` otherwise. No state where a note is both suppressed and
   needed, and none where a note is emitted on a `True` return that misdescribes
   it.
4. **`.gitleaks.toml` de-allowlisting** — verified load-bearing end-to-end (the
   two-arm table under M1). The residual risk is M1, not the fix itself.

### Other things looked at, nothing found

- `_delta_paths` uses two-dot `git diff A B` with `--no-renames` and `-z`
  (`review.py:642-644`) — tree comparison, which is what the fallback's safety
  argument actually needs; a rename out of a reviewed path into an exempt one
  decomposes into a delete + add and the delete refuses
  (`tests/test_review.py:677-696`).
- `_is_exempt` (`review.py:624-628`) — prefix vs. exact is correct and
  both-armed at `tests/test_review.py:778-787`; no glob surface to get wrong.
- `_missing_reports` (`review.py:402-421`) — `except OSError: body = ""` reads
  as "missing", i.e. refuses. Fails closed.
- `_reviewed_ancestors` walk bounded to `base_ref..sha` (`review.py:674-679`) —
  every failure arm returns an empty candidate list **with** a non-empty reason,
  so `_covering_receipt` can never return an empty note alongside a refusal.
- `pr.py:406-449` (`land_main`) — `require_base="main"` is passed on the PR head
  oid, and every unreadable answer (`pr_head_oid` → `None`, `checks_state` →
  `False`) returns 1 rather than proceeding.
- `pr.py:392-401` — the non-fatal `--set-upstream-to` failure is printed with
  the remedy, not swallowed. Acceptable: it cannot affect what was pushed.
- `await_terminal` (`pr.py:191-226`) — declines to assert "reached a terminal
  state" on a non-zero rc or a timeout; `checks_state` is the verdict. Correct.

## GitHub repos touched

- [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) — `dir` subcommand
  argument handling and the v8.30.1 `.pre-commit-hooks.yaml` invocation quoted
  by hk's builtin.
- [jdx/hk](https://github.com/jdx/hk) — `Config.pkl` global-`exclude` semantics
  and `builtins/gitleaks.pkl` / `builtins/detect_private_key.pkl` at v1.52.0.
