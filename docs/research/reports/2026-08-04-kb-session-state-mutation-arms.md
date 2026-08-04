# kb-session-state (#144) — 18 mutation arms, and a harness that lied

Promoted from `.agent/` because two findings here are cited elsewhere and
outlive this ticket: the **third recurrence of the harness bytecode-cache
defect** — which is evidence that writing the lesson down has stopped working,
not a new discovery (see Finding 1) — and the **measured blast radius
of mise output redaction** (now referenced from `mise.toml`,
`.claude/rules/mise-tasks-only.md`, `.claude/skills/clear-prep/SKILL.md` and
`kb_setup.session_state`'s docstring).

Subject: `python/src/kb_setup/session_state.py` at `90e2591` and its review
follow-up. Harness:
`scratchpad/arms.py` (embedded below in substance — each arm is one textual
mutation of the production module plus the ONE named test that must fail).

## Result

**20 arms run, 20 died. Control green unmutated; module restored green after
each arm.** Three arms were reported `BROKEN — pattern not found` across
intermediate runs — two after the `pr` → `with_pr` rename, one after `clean`
gained the `unmerged` term — and were repointed. The harness reporting that
rather than silently scoring them as deaths is the behaviour that makes the
other seventeen worth anything.

A19 and A20 pin the two defects the **cold cross-family lane** (codex) found
after both Claude lanes had passed — see Finding 4.

| arm | mutation | test that died |
|---|---|---|
| A1 | `gh` failure returns `PrState.NONE` | `…failed_gh_lookup_is_its_own_state…` |
| A2 | rename origin field not consumed | `…rename_does_not_shift_the_entries_after_it` |
| A3 | `clean` drops the `self.read` conjunct | `…non_repo_reports_an_unread_state…` |
| A4 | worktree half (Y) never read | `…staged_and_then_modified_again_is_in_both_buckets` |
| A5 | renderer prints UNVERIFIABLE as NONE | `…render_prints_the_three_pr_states_differently` |
| A6 | probe uses `gh pr view <branch>` | `…probe_asks_only_for_open_prs_on_this_branch` |
| A7 | detached-HEAD guard removed | `…detached_head_does_not_report_a_checked_no_open_pr` |
| A8 | unparsable `gh` output read as `[]` | `…unparsable_gh_output_is_unverifiable…` |
| A9 | unknown flags ignored | `…main_refuses_an_unknown_flag` |
| A10 | `--no-pr` ignored | `…main_accepts_the_no_pr_flag` |
| A11 | failed status read reported clean | `…non_repo_reports_an_unread_state…` |
| A12 | commit subject split on space | `…branch_and_recent_commits_are_gathered` |
| A13 | `gather` returns rendered prose | `…gather_returns_structured_data_not_a_string` |
| A14 | `true` accepted as a PR number | `…boolean_pr_number_is_refused…` |
| A15 | checks verdict hardcoded green | `…red_check_is_carried_as_data_not_only_as_prose` |
| A16 | multi-PR note written to `detail` | `…multi_pr_annotation_does_not_land_in_the_unverifiable_field` |
| A17 | positional args ignored | `…main_refuses_a_positional_argument` |
| A18 | commit count narrowed to 5 | `…default_commit_count_matches_the_workflow_it_replaces` |
| A19 | `symbolic-ref` probe removed (unborn HEAD) | `…unborn_branch_is_read_not_reported_as_unreadable` |
| A20 | unmerged paths fall through to staged+unstaged | `…merge_conflict_is_its_own_bucket…` |

A15–A18 exist because the two-axis review found the defects they pin; A13/A14
exist because an earlier run listed them as gaps with no test rather than
quietly omitting them.

## Finding 1 — the bytecode defect, for the THIRD time. Not a discovery.

**Read this correction before the section below.** The first draft of this
report presented the `__pycache__` defect as a finding. It is not. It is the
third occurrence of a lesson this repo has already written down twice:

| # | harness | outcome |
|---|---|---|
| 1 | `#145` `kb-handoff-check` (2026-08-04, earlier) | **had** the invalidation; its index entry states the `(mtime, size)` reason |
| 2 | `#146` `kb-gates` (2026-08-04) | regressed it; report says *"not a discovery — a REGRESSION of a lesson already written down"* |
| 3 | `#144` this harness | regressed it again |

And the #146 report closes its section with a prediction that has now come true
verbatim:

> **A lesson recorded in a report is not a lesson carried into the next
> harness.** […] *If a third harness is written, it should import this one
> rather than restate it.*

A third harness was written. It did not import; it restated, badly, and paid
the same cost. **That is the actual finding here** — not the cache mechanics,
which were fully understood before this ticket started.

The recorded remedy ("write it down") has now failed twice in a row, which is
evidence about the remedy rather than about the three authors. The structural
fix is that the harness stops being a per-ticket scratchpad throwaway and
becomes a `kb_setup` module with a test, so a fourth harness cannot be written
without it. Filed rather than built here, because it is outside #144's scope.

The mechanics below are retained for the record, and because this occurrence
has a detail the previous two did not: the exact pair of colliding arms.

## Finding 1a — how it presented this time (false SURVIVAL)

**A12 was reported `SURVIVED`. Run by hand at the same commit it died reliably
(rc=1, correct assertion diff).** Two probes of one fact disagreed, and the
broken one was the harness.

Cause: CPython validates a cached `.pyc` against **(source mtime in whole
seconds, source size)**. A11 and A12 both shorten `session_state.py` by exactly
one byte:

- A11 `Changes(read=False)` → `Changes(read=True)` — −1 byte
- A12 `partition("\0")` → `partition(" ")` — −1 byte

So the two mutants are **byte-identical in size**. When A12's write landed in
the same wall-clock second as the pyc entry written during A11's run, the cache
entry matched and pytest imported **A11's bytecode while A12's source was on
disk**.

**Why this matters beyond one arm.** The false *survival* is the safe
direction — it makes you look. The identical mechanism can produce a false
*DEATH*: an arm credited with killing a test when the test never saw its
mutation. That would have made all 18 arms worthless **while reading green**,
which is this repo's defining failure class arriving inside the very tool built
to detect it.

**What is new in this occurrence** (the previous two record the mechanism but
not this): the colliding pair is identifiable in advance. Both A11 and A12 are
`−1` byte. Most single-token mutations change a file's length by `0` or `±1`,
so collisions are the common case, not the tail — any harness rewriting one
file in a loop should assume a collision on every adjacent pair rather than
hope for a size difference.

Fix, both belt and braces:

- delete `python/src/kb_setup/**/__pycache__/*.pyc` before every arm;
- run each arm with `PYTHONDONTWRITEBYTECODE=1`, so no arm can leave an entry
  another one matches.

After the fix A12 dies on every run.

**Generalisation for future harnesses:** any harness that rewrites a source
file in a loop and shells out to a fresh interpreter is exposed to this. Size
collisions are not rare — most single-token mutations change length by 0 or ±1.

## Finding 2 — a fixture that could not exhibit the harm (rename pairing)

The rename arm nearly shipped as a false pass. Probed bytes (not assumed):

```
git status --porcelain -z  ->  R  zz-new-name.txt\0old-name.txt\0A  zzz-after.txt\0
```

Tracing the **unfixed** parse: the un-consumed origin field `old-name.txt` is
read as a record with `X='o'`, `Y='l'`, path `-name.txt` — a spurious entry in
both staged and unstaged — while `zzz-after.txt` **still parses correctly**.

So the intuitive assertion (*"is the later path still staged?"*) is satisfied
**with the bug present**. What discriminates is the spurious entry, so the test
asserts the buckets whole:

```python
assert changes.staged == ("zz-new-name.txt", "zzz-after.txt")
assert changes.unstaged == ()
```

This is rule 3 of `probes-need-a-control-arm.md` — a bound (here, which paths
the assertion looks at) turning "absent" into "unreachable".

## Finding 3 — mise redaction, measured on both transports

Same code, same flags, one HEAD:

| transport | branch | SHA |
|---|---|---|
| `mise run kb-session-state -- --no-pr` | `feat/[redacted]44-kb-session-state` | `90e259[redacted]cda[redacted]3` |
| `uv run kb-setup session-state --no-pr` | `feat/144-kb-session-state` | `90e2591cda13` |

The first draft of every disclosure named only the **branch**. Both review axes
independently pointed out that **commit SHAs and issue/PR numbers are mangled
too** — the fields `kb-gates` records and `kb-review` receipts are keyed by, and
exactly the `pull/[redacted]59` defect #144 cites as its motivation. A reader
who checked the branch per the docs would still have pasted a corrupted SHA.

Independently corroborated by the repo's own advisory eval case
`tier1.mise-redaction-legible`, which reports *7 of 49 non-empty redacted values
are shorter than 12 chars (shortest=1)* and states that every figure `mise run`
prints is untrustworthy while that holds. Cause is the **user-level** mise
config (`_.fnox-env`); `do-not.md` #11 bars this repo from editing it, so the
mitigation is the transport, not a code change.

## Finding 4 — the cold cross-family lane found two defects both Claude lanes missed

Round 1 was Standards + Spec, **both Claude**, and between them they found 8 real
things. The cold lane (`codex-reviewer`, OpenAI — a different family from the
author) then found **two more that neither had seen**, and it found them by
running probes against live git rather than by reading:

**P1 — an unborn branch reported as unreadable.** `git rev-parse --abbrev-ref
HEAD` exits **128** on a repo with no commits yet, while still printing `HEAD`
to stdout. Trusting only its rc turned a knowable branch into the module's
"could not be asked" state. The lane ran the actual `gather()` against a live
unborn repo and showed the render saying `COULD NOT READ` **beside a correctly
read staged-file list** — git had answered; it had been asked the wrong plumbing
command. `git symbolic-ref --short HEAD` returns rc=0 there and fails when
detached, so the two commands are complementary; `symbolic-ref` now goes first.

This is the module's own thesis running backwards. Everything in it is built so
an unchecked claim never renders as a checked one — and here a *checked answer*
was being thrown away as unknown. Both failure directions are the same bug.

**P2 — a merge conflict indistinguishable from an ordinary `MM`.**
`git-status(1)` spells an unmerged path seven ways (`DD AU UD UA DU AA UU`).
None of those letters is a "nothing here" code, so every one fell through to the
generic `x not in _UNMODIFIED` / `y not in _UNMODIFIED` branches and was reported
as **both staged and unstaged** — rendering exactly like a file that was staged
then modified again. The lane verified it with a real `git merge`, `xxd`-ing the
porcelain output to `UU f.txt\0`. A reader mid-conflict would conclude the file
needs re-staging when in truth nothing can be committed at all. `unmerged` is now
its own bucket, rendered first and shouted, and `clean` counts it.

**What this measures.** The one-lane policy in `.claude/skills/kb-review` trades
coverage for proportion, and notes that on #67 *method* — a lane that mutates or
executes to test its claim — predicted blockers better than lane identity did.
That held here: the instruction to prefer running a probe over reasoning is what
produced both findings, and both are states no fixture in the suite constructed.

**P3 (latent, partly unverified by the lane's own account):**
`pr.checks_state` took no directory and ran `gh` in the process's cwd, so it was
the only read in the module ignoring the `repo_root` it was handed. Not reachable
from the shipped task, where `cli.py` sets `repo_root = Path.cwd()`. Fixed
additively — `checks_state(..., *, cwd=None)` — so `ship`/`land` are unchanged.

## GitHub repos touched

_None._ All work was against this repository's own source and its installed
toolchain; no external repo source or docs were read.
