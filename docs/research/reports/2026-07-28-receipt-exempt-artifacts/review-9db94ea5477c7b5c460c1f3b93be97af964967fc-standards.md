# kb-review — Standards lane

- **Diff**: `git diff f3e233a92ef2b963f072c287e9be0dcc403fa203...HEAD`
- **HEAD**: `9db94ea5477c7b5c460c1f3b93be97af964967fc`
- **Commits**: `238417c` (chore(memory): fold in the Legible round's orphaned P7 artifacts), `9db94ea` (fix(review): an ancestor receipt covers HEAD when the delta is exempt (#66))
- **Files**: `python/src/kb_setup/review.py`, `tests/test_review.py`, `.claude/skills/kb-review/SKILL.md`, `.claude/skills/goal-engineering/SKILL.md`, `docs/goals/README.md`, 3 × `graphify-out/memory/*.md`

Standards sources read: `CLAUDE.md`, all 22 `.claude/rules/*.md`,
`.claude/skills/kb-review/references/repo-smells.md`, `.gitleaks.toml`, `hk.pkl`.

Findings are ordered by severity. **HARD** = a documented standard is breached.
**JUDGEMENT** = a baseline (Fowler ch.3) or repo-specific smell, always a
judgement call.

---

## S1 — HARD / BLOCKING. Live credentials are committed in a tracked file

**File**: `graphify-out/memory/query_20260728_072907_in_a_multi_round_kb_review_loop__which_lane_finds.md`
(new in `238417c`)

The `## Answer` body ends with a pasted JSON object carrying **three
format-valid credential values**: one `EXA_API_KEY` (UUID-shaped), and two
`ghp_`-prefixed GitHub personal access tokens under `GITHUB_TOKEN` and
`MISE_GITHUB_TOKEN` (the two token values are identical). Values are
deliberately not reproduced here.

Probe (names/counts only, no values printed):

```
$ git grep -l -E 'ghp_[A-Za-z0-9]{20,}|EXA_API_KEY' HEAD
HEAD:graphify-out/memory/query_20260728_072907_in_a_multi_round_kb_review_loop__which_lane_finds.md
$ git grep -c -E 'ghp_[A-Za-z0-9]{20,}' HEAD -- graphify-out/
HEAD:graphify-out/memory/query_20260728_072907_...md:2
```

Control arm: the same two patterns over the rest of `HEAD` return **zero**
files, so the probe discriminates — it is not matching everything.

The bitter irony is that the memory text *is a lesson about this exact
failure*: it says "two independent agents leaked live credentials by running
`…`, so constrain that explicitly in lane prompts" — and then embeds the leaked
payload verbatim as the illustration. The lesson was recorded by committing the
leak.

Standards breached:

- `.claude/rules/` (dotfiles sibling, loaded in this session) `do-not.md` #10 —
  *"Do NOT write an environment dump into a tracked file. Not `env`, not
  `printenv` … Write a dump to the scratchpad and delete it."*
- `secrets-out-of-the-shell-env.md` rule 1 — same prohibition, same wording.
- Auto-memory `never-print-mise-redaction-values` — *"leaked three times in one
  session"*. This is the fourth, and the first one that is **committed** rather
  than transient.
- `zero-skip-policy.md` rule 5 ("green means clean") — see S2: the gate reported
  green because it was looking away.

**Remedy** (in this order, none of which is optional):

1. **Revoke and rotate first**, before touching git. The GitHub PAT and the Exa
   key must be treated as public from the moment they were written to disk. Git
   history rewriting is not containment; revocation is.
2. Rewrite the memory file to describe the leak without the payload (e.g. "a
   JSON object containing an Exa key and two GitHub PATs"). The lesson survives
   intact — the payload was never the lesson.
3. Because `238417c` is on the branch and unpushed, the cheapest fix is an
   interactive rebase / `git commit --amend` on that commit so the values never
   enter a pushed history. If the branch has already been pushed, the commit
   must be considered public.

## S2 — HARD. The gitleaks allowlist's stated premise is false for `graphify-out/memory/`

**File**: `.gitleaks.toml` (unchanged by this diff, but this diff is what makes
it wrong, and `238417c` is the proof)

```toml
# … the derived graphify-out/ cache are gitignored research data that inherently
# contain secret-LIKE strings (leaked prompts, fixture keys). They are never
# committed, so scanning them is pure noise.
paths = [
  '''^sources/''',
  '''^graphify-out/''',
  …
]
```

The comment's load-bearing claim — *"They are never committed"* — is
contradicted by `CLAUDE.md` invariant 5 and by the layout table: **`memory/` is
the ONE committed subdirectory of `graphify-out/`.** So the allowlist is
correct for ~all of `graphify-out/` and precisely wrong for the only part that
reaches git. S1 landed in the one blind spot the config creates, and hk's
`gitleaks` step passed while a PAT went in.

This is the repo-smells entry **"a doc and the code it describes disagreeing"**
in its most expensive form, and `probes-need-a-control-arm.md` rule 4's *"when a
scanner reports clean, ask what it can see"* — restated verbatim in
`secrets-out-of-the-shell-env.md` rule 4.

**Remedy**: narrow the allowlist so the committed subtree is scanned. gitleaks
allowlist `paths` are regexes, so the fix is a negative-lookahead-free split —
allowlist `^graphify-out/(?!memory/)` is not supported by Go's RE2, so instead
enumerate the derived siblings, or (cleaner) drop `^graphify-out/` and add the
specific noisy derived paths (`^graphify-out/wiki/`, `^graphify-out/graph.*`,
`^graphify-out/\.graphify`, …). Either way, **prove the FAIL direction**
(`verify-before-advancing.md` § "Prove the FAIL direction of anything you add"):
plant a synthetic format-valid token under `graphify-out/memory/` and confirm
`mise run lint` goes red, then remove it and confirm green.

Same change should update the comment, which is the thing that made this
invisible (`tool-currency-and-native-first.md` rule 5 — sync the describing doc).

## S3 — HARD (interaction). `EXEMPT_PATHS` now excuses the directory that carried S1

**File**: `python/src/kb_setup/review.py`

```python
EXEMPT_PATHS = ("graphify-out/memory/", "docs/goals/README.md")
```

described as *"Paths a review lane cannot meaningfully review"*. S1 is a
counter-example produced by the very commit pair under review: a lane **can**
meaningfully review `graphify-out/memory/**` — this lane just found a live
credential in it, and no other layer would have (S2).

The design is otherwise careful and I am not arguing against the mechanism (see
S5 for what I think is right about it). The specific claim in the docstring is
what is now falsified. Two things follow:

1. The rationale should be restated honestly — these are paths whose content is
   *generated by the round's own closing tasks and therefore cannot exist at
   receipt time*, which is the real and sufficient argument. "A lane cannot
   meaningfully review it" is a stronger claim that this diff disproves.
2. Since the exemption removes the human/lane read from these files, the
   *machine* check must cover them. That makes S2 a **precondition** for S3
   being safe, not an independent nice-to-have: with the gitleaks allowlist as
   it stands, `EXEMPT_PATHS` creates a path into git that neither a lane nor a
   scanner inspects. Fix S2 before shipping S3.

## S4 — JUDGEMENT. Asymmetric display bound in `_covering_receipt`

**File**: `python/src/kb_setup/review.py`

The refusal branch bounds its path list and states the remainder, with a comment
citing `probes-need-a-control-arm.md` rule 3 — exactly right:

```python
shown = ", ".join(reviewed[:_MAX_NAMED_PATHS])
extra = len(reviewed) - _MAX_NAMED_PATHS
more = f" (+{extra} more)" if extra > 0 else ""
```

The acceptance branch three lines later does not:

```python
covered = ", ".join(paths) if paths else "an identical tree"
return candidate, f"covered by the receipt for {candidate[:12]}; since then only {covered}"
```

A round that ran `kb-remember` several times produces N memory files, and the
whole list is interpolated into the summary line the skill advertises ("The
summary line says which receipt covered HEAD and what changed since"). It is the
*permissive* direction that gets the unbounded dump, so the message a reader
most needs to skim is the one most likely to be a wall of text.

Low severity — cosmetic, not a correctness hole. Reusing the same
`_MAX_NAMED_PATHS` summarisation for both branches would also remove a small
piece of near-**Duplicated Code** between the two formatting sites.

## S5 — JUDGEMENT. The `(+N more)` branch of `_MAX_NAMED_PATHS` is never exercised

**Files**: `python/src/kb_setup/review.py`, `tests/test_review.py`

The new constant gets a four-line docstring arguing (correctly) that a display
bound must state its own remainder rather than truncate silently. But every
refusal test constructs exactly **one** disqualifying path:

- `test_one_reviewed_path_in_the_delta_refuses` → 1 path
- `test_a_rename_out_of_a_reviewed_path_refuses` → 1 path

so `extra = 1 - 5 = -4` and `more` is always `""`. The `extra > 0` branch — the
entire reason the constant exists — has no test. Under
`repo-smells.md` § "A gate verified only in the PASS direction", the question to
ask is: *would deleting the `more` computation keep the suite green?* It would.
That makes the remainder-reporting decoration until a 6-reviewed-path case
pins it.

Cheap fix: one test committing six reviewed files in the post-receipt commit and
asserting `"+1 more"` appears. Same for the `paths == []` → `"an identical
tree"` arm, which is likewise unreached (an empty commit on top of the receipt).

Everything else in the new test block is genuinely two-armed — the real-git
choice over a stubbed `base_sha` is the right call and the docstring says why,
`test_the_fallback_is_opt_in_with_require_base` is a proper control arm, and
`test_an_unreadable_delta_fails_closed` runs its control (`assert
review.receipt_state(...)[0]`) before the mutation. This is one gap in an
otherwise well-armed suite.

## S6 — JUDGEMENT. The fallback note is dropped on the two failure paths that follow it

**File**: `python/src/kb_setup/review.py`, `receipt_state`

`_covering_receipt`'s docstring commits to a principle:

> The note is returned in BOTH directions — it explains an accepted fallback,
> and equally explains a refused one.

`receipt_state` honours that for the refused case (folded into `_load_receipt`)
and for the success case (`suffix`), but not for the two failure returns in
between:

```python
suffix = f" — {note}" if note and not refused else ""

if require_base is not None:
    gap = _base_coverage_gap(repo_root, data, require_base, covering)
    if gap is not None:
        return False, f"receipt for {covering[:12]} {gap}"       # note dropped

reason = _all_reasons(repo_root, data, covering)
if reason is not None:
    return False, f"receipt for {covering[:12]} {reason}"        # note dropped
```

`suffix` is computed but only ever consumed on the final success line. So when
an accepted fallback then fails on base-coverage or on a blocking finding, the
operator is told about `receipt for <some-sha> …` where `<some-sha>` is **not
HEAD**, with nothing explaining why a different commit is being discussed. That
is precisely the "hides that a candidate existed" failure the docstring
identifies, just on a different branch of the same function.
`test_the_ancestors_own_receipt_still_has_to_pass` asserts only
`"blocking review finding" in summary`, so it passes either way.

Fix is one character each: append `{suffix}` to both f-strings.

## S7 — Positive control: what the change gets right

Recorded because a review that only lists defects gives no signal about whether
the rest was read.

- **`_git_result` / `_git` split** is the correct fix for a real
  "could-not-check rendered as green" (`repo-smells.md`, `zero-skip-policy.md`).
  `_git` reads as **Middle Man** under the Fowler baseline; it is **not** a
  finding — the two-function shape is what carries the ok-flag distinction, and
  the docstring names exactly why collapsing them would be wrong.
- **`--no-renames` in `_delta_paths`** closes a genuine bypass (move a reviewed
  file into an exempt directory and rename detection would show only the exempt
  destination). This is the kind of adversarial case the exemption needed and it
  was thought through rather than asserted.
- **`-z` splitting** avoids `core.quotePath` re-encoding. Correct, and rarely
  remembered.
- **The `graphify-out/reflections/` non-entry** is documented as deliberately
  absent because it is gitignored and an entry could only ever be dead —
  `probes-need-a-control-arm.md` applied to a data table, which is unusual and
  right.
- **`_reviewed_ancestor` bounds the walk to `base_ref..sha`**, so a receipt from
  a commit already on `main` can never vouch for new work. That bound is the
  difference between this being a narrow exemption and a hole.
- **The test block chose real git over a stub** and justified it in a comment —
  "a stubbed git could only ever confirm the stub". That is
  `probes-need-a-control-arm.md` reasoning applied to test design.
- **Both skill docs were updated in the same change** (`kb-review/SKILL.md`,
  `goal-engineering/SKILL.md`), satisfying `tool-currency-and-native-first.md`
  rule 5. `docs/goals/README.md` Status flip is consistent with the memory file.

## Checked and clean

- `zero-bash-logic.md` — no `.sh` added; all new logic is in `kb_setup`, invoked
  through existing seams. No inline shell grew in `mise.toml` / `hk.pkl`.
- `mise-tasks-only.md` / `do-not.md` #3 — no raw `graphify` call introduced.
- `do-not.md` #4 — no non-Claude backend trigger touched.
- `do-not.md` #9 — no `noqa` / `type: ignore` / `nosec` in the diff.
- `md-size-budgets.md` — both SKILL.md additions are small (+17 / +7 lines).
- Tooling-enforced surfaces (ruff `select=ALL`, ty, rumdl, typos, agnix) skipped
  per the brief.
- Fowler baseline: no Mysterious Name, Feature Envy, Data Clumps, Primitive
  Obsession, Repeated Switches, Shotgun Surgery, Divergent Change, Speculative
  Generality, Message Chains, or Refused Bequest observed in the new code. The
  only baseline hits are the Middle Man (overridden, S5) and the minor
  duplication noted in S4.

## Minor, sub-finding

`tests/test_review.py` defines a module-level `_git(root, *args)` whose name
collides with `review._git(repo_root, *args)` while behaving oppositely (the
test helper uses `check=True` and raises; the module's returns `""`). Both are
private to their file so nothing breaks, but a reader moving between the two
files has to hold two contracts under one name — borderline **Mysterious Name**.
`_run_git` in the test file would remove the ambiguity. Also, `LANES_RAN` is
defined *below* the `_receipt_for` function that references it; legal (resolved
at call time) and ruff-clean, but it reads backwards.

## GitHub repos touched

_None._ All evidence is local to this repo.
