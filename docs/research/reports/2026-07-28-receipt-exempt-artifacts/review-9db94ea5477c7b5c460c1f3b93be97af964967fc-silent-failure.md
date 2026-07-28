# Silent-failure lane — review of f3e233a...9db94ea

- **Range**: `f3e233a92ef2b963f072c287e9be0dcc403fa203...9db94ea5477c7b5c460c1f3b93be97af964967fc`
- **HEAD**: `9db94ea5477c7b5c460c1f3b93be97af964967fc`
- **Commits**: `9db94ea fix(review): an ancestor receipt covers HEAD when the delta is exempt (#66)`,
  `238417c chore(memory): fold in the Legible round's orphaned P7 artifacts`
- **Diff surface**: `python/src/kb_setup/review.py` (+206/-15), `tests/test_review.py` (+208),
  three `graphify-out/memory/*.md`, `.claude/skills/{goal-engineering,kb-review}/SKILL.md`,
  `docs/goals/README.md`.
- **Only behaviour-bearing file**: `python/src/kb_setup/review.py`. Everything else is prose
  or test.

## Deliberate-direction check (asked for explicitly)

Both are **INTACT**, in the correct opposite directions:

| module | direction | evidence |
|---|---|---|
| `kb_setup.hook_guard` | fails **OPEN** | `python/src/kb_setup/hook_guard.py:156-176` — `run()` returns `0` (allow) on a stdin JSON parse error (`:161-164`) and on any exception out of `decide()` (`:170-173`). Docstring `:159` states it. Correct: a crashed PreToolUse guard must not brick every Bash call. |
| `kb_setup.pr.checks_state` | fails **CLOSED** | `python/src/kb_setup/pr.py:152-164` — a `json.JSONDecodeError` returns `(False, "could not read checks …")`; a payload that is not a list-of-objects returns `(False, "unexpected checks payload …")`. Only a well-formed empty array reaches `return True, "no checks configured"` (`:166-167`). Correct: unparsable is "never asked", which must not authorise a merge. |

Neither is inverted. Neither is in the reviewed range; both were read to confirm the
reasoning survived the change.

### One thing I checked and it is NOT a finding (recorded so nobody re-raises it)

`hook_guard.py:163` reads `except json.JSONDecodeError, ValueError:` — Python-2-looking
syntax. It is **valid**: PEP 758 (unparenthesised `except` tuples) landed in Python 3.14,
and this repo runs 3.14.0 (`python3 -VV` → `Python 3.14.0`). Control-armed: a synthetic
`except ValueError, TypeError:` file compiles clean on this interpreter, while a
non-existent path raises `FileNotFoundError` from the same probe, so the probe
discriminates between "compiles" and "could not compile". My first pass read this as a
module-killing SyntaxError; the cross-check refuted it. (`json.JSONDecodeError` is a
subclass of `ValueError`, so the second arm is redundant — cosmetic, out of range.)

---

## Findings

_(appended as found — see below)_
### F1 — CRITICAL — A live-credential dump is committed in this range, and BOTH gates that should have caught it are configured to look away

**Claim**: commit `238417c` adds a tracked file containing three high-entropy
credentials (one `EXA_API_KEY` UUID, two 36-char-body `ghp_` GitHub tokens), and
`gitleaks` reports "no leaks found" only because `.gitleaks.toml` allowlists the
directory the file is in. The change under review then removes the *other*
remaining check on that same directory.

**Location**:
- `graphify-out/memory/query_20260728_072907_in_a_multi_round_kb_review_loop__which_lane_finds.md:15-17`
  (the credential JSON block; committed by `238417c`)
- `.gitleaks.toml:18` — the `^graphify-out/` allowlist entry
- `python/src/kb_setup/review.py:112` — `EXEMPT_PATHS = ("graphify-out/memory/", …)`

**The dump is self-describing.** The memory note's own sentence reads: *"two
independent agents leaked live credentials by running { … } to a terminal within
minutes of each other, so constrain that explicitly in lane prompts."* The lesson
about leaking credentials **pasted the leaked JSON verbatim** into the committed
record. Entropy hints, values never printed: both `ghp_` bodies are 36 chars, 29
distinct characters, 10 digits — the classic GitHub PAT shape, not a placeholder.

**Why "could not check" is rendered as a pass — control-armed, both arms:**

| arm | command | result |
|---|---|---|
| in-repo (allowlisted) | `gitleaks detect -s .` over 150 commits | `no leaks found` |
| in-repo, file directly | `gitleaks detect --no-git -s <the file>` | `scanned ~0 bytes` — it **never read the file** |
| **control** — same bytes, copied outside the allowlisted path | `gitleaks detect --no-git -s <copy>` | **`leaks found: 3`** |
| control (negative) | same probe over the range's other two memory files | `0` findings |

The scanner is not broken; it is pointed away. `~0 bytes` is the proof: this is a
*never asked*, printed as a clean bill of health — the exact failure mode
`probes-need-a-control-arm.md` §4 names and that `review.py`'s own comments refuse
everywhere else.

**The allowlist rests on a premise that is false in this repo.**
`.gitleaks.toml:1-5` justifies the entry as *"the derived `graphify-out/` cache
are **gitignored** research data … **They are never committed**, so scanning them
is pure noise."* But `graphify-out/memory/` is the ONE committed subdirectory —
stated in `CLAUDE.md` invariant 5, in `.gitignore:48` (*"committed under
graphify-out/: ONLY memory/"*), and confirmed by `git check-ignore`:
`graphify-out/reflections/LESSONS.md` → IGNORED, `graphify-out/memory/x.md` →
**not ignored**. The allowlist is broader than its own stated rationale by exactly
the one subdirectory that is tracked.

**How this change makes it worse.** `EXEMPT_PATHS` (`review.py:112`) adds
`graphify-out/memory/` to the set of paths an ancestor receipt may cover, i.e.
paths that ship **with no review lane having read them**. Its docstring
(`review.py:92`) calls them *"Paths a review lane cannot meaningfully review"* —
that assumption is what just failed. After this commit the two independent layers
over `graphify-out/memory/**` are:

- gitleaks → allowlisted, never reads it;
- the four `kb-review` lanes → exempt, never required to read it.

Neither is a defect alone. Together they are an unwatched path in a **PUBLIC**
repo (`gh repo view` → `{"nameWithOwner":"ray-manaloto/knowledge-base","visibility":"PUBLIC"}`).

**Containment (good news, and the reason this is urgent rather than an incident).**
`238417c` is **not pushed**: `git branch -r --contains 238417c` → empty, and
`git merge-base --is-ancestor 238417c origin/main` → false. Nothing has reached
the public remote yet. `mise run kb-ship` would push it, and would pass every
gate on the way.

**Recommendation**, in order:
1. **Treat all three credentials as compromised and rotate now** — they were
   printed to at least two agent terminals per the note's own account, and they
   sit in a local commit. Rotation is cheap; assuming they are stale is a probe
   with one face.
2. **Rewrite `238417c`** (it is unpushed — `git rebase -i` / recommit) so the
   credential block never enters history. Redact to `ghp_<redacted>` /
   `<redacted-uuid>`; the *lesson* is worth keeping, the values are not.
3. **Narrow the gitleaks allowlist to match its own stated rationale** — replace
   `'''^graphify-out/'''` with the gitignored subtrees only, so the one tracked
   subdirectory is scanned:
   ```toml
   paths = [
     '''^sources/''',
     '''^graphify-out/(?!memory/)''',   # or enumerate: cache/, wiki/, obsidian/, transcripts/, …
     '''^brain/graphify-out/''',
     '''^raw/''',
   ]
   ```
   Then control-arm it: the file above must report 3 findings *in place* before
   the fix is believed.
4. **Only then** keep `graphify-out/memory/` in `EXEMPT_PATHS`. Exempting a path
   from review is defensible only while some other layer still reads it; right
   now nothing does.
5. Add the note's own lesson to the lane prompts, as it asks — but as
   *"never print environment VALUES"*, not as a pasted example.

**User impact**: a public-repo credential disclosure, one `mise run kb-ship`
away, with every local gate green. The debugging story afterwards is the worst
kind — "gitleaks passed" is on record, so the leak looks impossible.

---

### F2 — LOW (advisory; safe direction, but the stated invariant is false) — `_reviewed_ancestor`'s justification for considering only one candidate is empirically wrong

**Claim**: the docstring asserts a delta-subset property between a nearer and a
farther ancestor that git does not have. Today it errs toward refusing, so it is
not a gate hole — but it is a load-bearing sentence in a module where the comments
*are* the contract, and it is the kind of claim a later change would relax on.

**Location**: `python/src/kb_setup/review.py:627-631`

> "Nearest, and only one candidate is ever considered, because a farther ancestor
> is **strictly harder to accept**: **every path in the nearer delta is also in the
> farther one**, so if the nearest is refused for touching a reviewed path, so is
> everything below it."

**Disproof** (real git, both arms, in a throwaway repo): commits `A → B → C`
where `B` edits `foo.py` and `C` restores it to `A`'s content —

```
delta B..C (NEAREST)  -> foo.py        # non-exempt -> REFUSED
delta A..C (FARTHER)  -> (empty)       # identical trees -> would be ACCEPTED
```

So the nearer delta contains a path the farther one does not, and the farther
ancestor is *easier* to accept, not harder. The premise is inverted.

**Why it is not F1-grade**: the code picks the nearest and therefore refuses,
which is the conservative side. And the underlying rule is in fact sound for
*any* ancestor — the check is tree-based (`git diff A B` compares trees, not
history), so "the reviewed bytes at `sha` are identical to the reviewed bytes at
a commit that was reviewed" holds whichever ancestor is chosen. The docstring
argues for the right behaviour from the wrong reason.

**Second-order note (unverified, low confidence)**: `git rev-list` default
ordering is commit-date descending, not topological. Under a rebase, cherry-pick
or clock skew the first receipted commit found need not be the topologically
nearest. Per the paragraph above this is still *sound*, but it means the code
does not reliably do what the name `_reviewed_ancestor`'s docstring says
("NEAREST"). Add `--topo-order` if the word is meant literally.

**Recommendation**: replace the subset argument with the true one — "any ancestor
whose delta to `sha` is entirely exempt is sound, because the check compares
trees; the nearest is chosen only because it is cheapest to find" — and add
`--topo-order` to the `rev-list` at `review.py:641` if "nearest" is a claim
rather than a heuristic.

---

### F3 — LOW — `_git_result`'s `.strip()` can silently re-classify a `-z` path, contradicting `_delta_paths`' stated byte-fidelity

**Claim**: `_delta_paths` documents that `-z` makes paths compare "as the bytes
git actually has rather than as a re-encoded display form", but the shared
`_git_result` strips the whole stdout before splitting, so a leading-whitespace
path — the first record in the NUL stream — loses that whitespace and can become
exempt when it is not.

**Location**: `python/src/kb_setup/review.py:305` (`return True, proc.stdout.strip()`)
consumed by `python/src/kb_setup/review.py:616-621` (`_delta_paths`), claim at
`review.py:611-614`.

**Probe** (both arms):
```
raw split      -> [' docs/goals/README.md', 'python/x.py']   # not exempt
after .strip() -> ['docs/goals/README.md',  'python/x.py']   # EXEMPT
'\0'.isspace() -> False    # so the trailing NUL is safe; only the leading edge bites
```

**Hidden errors this masks**: exactly one — a tracked path whose name begins with
whitespace, sorting first in `git diff` output, silently reclassified from
reviewed to exempt.

**Reachability is genuinely low** (a file literally named ` docs/goals/README.md`),
and the module's threat model is "a model talks itself past the gate", not a
filename attack. Reported because the docstring makes a byte-fidelity promise the
code does not keep — the same doc-vs-code divergence this module calls out at
`review.py:63-65` ("a doc and the code disagreeing is worse than either alone").

**Recommendation**: have `_delta_paths` bypass the strip, e.g. give `_git_result`
a `raw=True` (returning `proc.stdout` unstripped) for NUL-delimited callers, and
keep `.strip()` for the line-oriented ones. Then assert `_is_exempt(" docs/goals/README.md")`
is False in `test_exempt_paths_match_prefixes_and_exact_files`.

---

### F4 — LOW — an accepted-fallback `note` is dropped on every downstream refusal, so the message names an ancestor SHA with no explanation

**Claim**: when the ancestor fallback is *accepted* but the ancestor's receipt
then fails validation, the refusal is worded against `covering` while the note
that explains why an ancestor is being discussed is discarded.

**Location**: `python/src/kb_setup/review.py:765-774`

```python
suffix = f" — {note}" if note and not refused else ""      # 765
...
return False, f"receipt for {covering[:12]} {gap}"          # 770  <- suffix unused
return False, f"receipt for {covering[:12]} {reason}"       # 774  <- suffix unused
```

`suffix` is applied only on the success return (`:781`). So a user running
`kb-ship` at HEAD `abc…` sees `receipt for 1f2e3d4a5b6c 2 blocking review
finding(s)` — a SHA that is not HEAD, with nothing saying an ancestor receipt was
consulted or why. `test_the_ancestors_own_receipt_still_has_to_pass` asserts the
refusal happens but not that it is explicable.

**User impact**: diagnosis only — the verdict is correct and fails closed. But the
module's own stated principle at `review.py:751-756` is that a refusal must say
*which* file to look at, and this path drops that. It is the mirror of the
`refused` branch the change got right.

**Recommendation**: append `suffix` to both refusal returns at `:770` and `:774`,
and extend the existing test to assert the covering SHA is explained, not merely
named.

---

## What I checked and found CLEAN

Recorded so the same ground is not re-walked, and so the negatives are attributable.

- **No bare `except`, no `except Exception: pass`, no empty catch** anywhere in
  the diff. The only new `except` arms are in `_git_result`
  (`review.py:287-294`), both of which **print the reason and return
  `(False, "")`** — a refusal carrying diagnosis, not a swallow.
- **The `_git` / `_git_result` split is the fix for a real silent failure, and it
  is correct.** `_git` collapsing failure to `""` is safe only because its two
  callers (`head_sha`, `base_sha`) ask questions with no legitimate empty answer;
  `git diff` does have one, and conflating them would have made a broken `git
  diff` the single most permissive input the gate has. `_delta_paths` returning
  `None` on `ok=False` and `_covering_receipt` refusing on `None`
  (`review.py:683-685`) closes it. `test_an_unreadable_delta_fails_closed`
  carries its own control arm.
- **Every new failure path in `_covering_receipt` fails CLOSED**, verified branch
  by branch: unresolvable base (`:638-640`), unreadable `rev-list` (`:641-643`),
  no receipted ancestor (`:647`), unreadable delta (`:683-685`), any non-exempt
  path in the delta (`:687-695`). All five return `sha` unchanged, so the strict
  identity check runs and refuses.
- **The fallback cannot launder a bad receipt at HEAD.** `_covering_receipt`
  short-circuits when `receipt_path(sha).is_file()` (`:676`), so an *invalid*
  receipt for HEAD is refused rather than escaping to an ancestor. Correct
  direction.
- **The fallback picks which receipt is read, not how hard it is read.**
  `_base_coverage_gap`, `_all_reasons` (identity, range, lanes, blocking) and
  `_evidence_gap`'s on-disk lane reports all run against `covering`
  (`review.py:768-774`). Confirmed by `test_the_ancestors_own_receipt_still_has_to_pass`.
- **The relaxation is opt-in.** It requires `require_base`, so `cli.py:287`'s
  post-write read-back keeps the unrelaxed answer; `pr.py:343/361/442` (ship
  pre-gate, ship push-gate, land) all pass `"main"`. `test_the_fallback_is_opt_in_with_require_base`
  is the control arm.
- **The ancestry walk cannot reach a receipt on `main`** — bounded to
  `base_ref..sha` (`review.py:638-641`), tested.
- **`--no-renames` is load-bearing and correct**: moving a reviewed file *into* an
  exempt directory shows as a delete of the reviewed path, which refuses. Tested.
- **The `EXEMPT_PATHS` matcher is prefix-vs-exact and does not over-match** —
  `graphify-out/memory-of-a-thing.md` and `docs/goals/README.md.bak` are both
  correctly non-exempt (`review.py:598-602`, tested both arms).
- **The comment at `review.py:106-111` justifying the *absence* of
  `graphify-out/reflections/` is CORRECT** and I control-armed its premise:
  `git check-ignore` → `graphify-out/reflections/LESSONS.md` IGNORED,
  `graphify-out/memory/x.md` not ignored. A rule that could only be dead was
  correctly left out.
- **Display bound is honest**: `_MAX_NAMED_PATHS` states its remainder
  (`"+N more"`, `review.py:689-691`) instead of truncating silently.
- **`tests/test_review.py` passes**: `uv run pytest tests/test_review.py -q` →
  56 passed. The new tests use a REAL git repo rather than a stubbed `base_sha`,
  which is the right call — the mechanism under test is git behaviour, and a stub
  could only confirm the stub.
- **The two prose diffs (`kb-review/SKILL.md`, `goal-engineering/SKILL.md`) match
  the code.** No claim in either overstates what the gate does; both state the
  narrowing ("one reviewed path and the fallback is refused", "a blocking finding
  on that ancestor still refuses").
- **The other two memory files added in this range are clean** — 0 gitleaks
  findings when scanned outside the allowlist (the same probe that returns 3 on
  the third file, so it discriminates).

## Probe hygiene note against myself

While isolating F1 I printed one credential value (the `EXA_API_KEY` UUID) to the
terminal, because my first redaction regex covered only the `ghp_` shape. That is
the very failure the leaked note was recording. No value is reproduced in this
report, the scratchpad copies made during control-arming were deleted, and the
remaining exposure is the committed file itself, which F1 addresses. Flagging it
because a lens that hides its own miss is worth less than one that reports it.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review.
- [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) — allowlist/path semantics for the F1 control arm.
