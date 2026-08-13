---
name: clear-prep
description: "Prepare for a /clear in the knowledge-base repo: drive the next task to zero ambiguity, close the corpus loop (kb-remember + kb-reflect + kb-goal-outcome) BEFORE shipping, sync docs, persist memory + a self-sufficient handoff, and emit a one-line resume prompt. Invoke explicitly as /clear-prep [next-task]."
disable-model-invocation: true
argument-hint: "[one-line description of the next task, optional]"
---

# Clear-Prep — Session Handoff Before `/clear`

Run this **before** `/clear` so the next session loses nothing. Three jobs, in
this order: (1) find out what the next task actually is, (2) put everything
worth keeping somewhere that survives the clear, (3) print one line to paste
afterwards.

`$ARGUMENTS` is the next task, if the user named one. If it is empty, infer the
next task from open issues and the prior handoff, and *say what you inferred* —
a guess the user never saw is a guess nobody corrected.

Work top-to-bottom. The ordering in step 2 is not stylistic; it is the one thing
in this skill that cannot be reordered without losing work.

> **This skill is model-invisible on purpose.** `disable-model-invocation: true`
> removes it from the skill listing entirely, so it fires only when a human types
> `/clear-prep`. That is deliberate — a handoff that auto-triggers mid-task
> writes a handoff for work that is not finished. It also means the
> `triggering_accuracy` dimension in `mise run kb-skill-score` is permanently
> low for this skill and should be ignored here: it measures a trigger this
> skill is designed not to have.

## 0. Resolve next-task ambiguity FIRST (Ray, 2026-07-08)

**Before writing anything, drive the next task to zero ambiguity by asking the
user via `AskUserQuestion`** — and keep asking across rounds until nothing
material is unresolved. Every question goes through that tool, including a plain
yes/no; a question in prose at the end of a message is easy to miss and gives
the user nothing to click (`clarify-before-acting.md`).

The handoff's "next task" section is only as good as this step. If the task
admits multiple readings, a scope fork, an undecided B-vs-C, or an unstated
end-goal, surface each one, get the answer, and encode it **verbatim** — a
paraphrase of a decision is a decision the next session gets to relitigate.
Skipping this because the task "seems clear" is the exact failure this step
exists to prevent.

Then ask the losing-nothing question directly: *if I `/clear` right now and the
next session has only auto-memory + the handoff + the persisted reports, can it
continue with no gaps?* If the answer is no, fix that before step 7.

## 1. Snapshot the working state

Gather, don't recall — **one task, not four commands** (#144):

```bash
uv run kb-setup session-state
```

**Deliberately not `mise run kb-session-state`.** Same code, but mise redacts
digit runs matching your secrets, so the task mangles **the branch, every commit
SHA, and every issue/PR number** — the three fields a handoff most needs
verbatim, and the two that `kb-gates` records and `kb-review` receipts are keyed
by. `feat/144-…` prints as `feat/[redacted]44-…` and `90e2591cda13` as
`90e259[redacted]cda[redacted]3`. The `tier1.mise-redaction-legible` eval case
tracks this and is advisory-by-design; the cause is your user-level mise config,
which `do-not.md` #11 bars this repo from editing.

It prints the branch, the staged/unstaged/untracked split, the recent commits,
and the open PR with its check state, already shaped like a handoff bullet. Four
hand-run commands reformatted by hand is four chances to transcribe something,
and this repo has already paid for that twice — a `file:line` read off a `sed`
window by eye (`:1836` for `:1830`, propagated into three files) and a PR number
read out of a redacted `mise run` log (`pull/[redacted]59`).

**`COULD NOT ASK` is not `none`.** If the PR line says the former, `gh` was
unreachable, rate-limited or unauthenticated — write that into the handoff as
unknown, never as "0 open PRs". A claim nobody checked is the exact thing
`mise run kb-handoff-check` exists to catch in step 6.

Then add the in-flight task from the previous `.agent/plans/session-*.md`.

Also inventory **session-local runtime state**: background tasks and agents
still running, and any scheduled wakeups or crons created this session. Stop
what should not outlive the session and note anything deliberately left running.
A stale wakeup firing after the handoff re-triggers work that is already done.

**Do not block `/clear` on anything that runs without this session.** GitHub
Actions runs and bots like Renovate execute on GitHub's schedule whether you
clear or not — they are not this session's background tasks. Inventory them in
the handoff (number, what each is, expected outcome, any legitimately failing
and why), pin the handoff to the current HEAD, note that `main` is bot-advanced
and the next session just pulls. Waiting for a quiet `main` an active bot will
never produce is waiting forever. Wait on a run only when *you* need its result
to finish *this* session's task.

## 2. Close the corpus loop — and do it BEFORE `kb-ship`

This is the step the sibling repo's version of this skill has no equivalent for,
and the one with a real ordering trap.

**The trap:** `mise run kb-land` squash-merges. The squash commit is a *new*
commit, so the SHA your `kb-review` receipt was written against stops being an
ancestor of `main`. `review.EXEMPT_PATHS` (`graphify-out/memory/`,
`docs/goals/README.md`) exists so a round can commit its own closing artifacts
under an ancestor's receipt — but that rescue only works while the reviewed
commit *is* an ancestor. Run `kb-remember` after the land and there is no
receipt that covers it, so the artifacts either never land or force a whole new
review round for a memory file.

So close the loop while the branch is still unmerged:

```bash
mise run kb-remember -- --question "<what this round asked>" \
                       --answer-file .agent/round-answer.md --outcome useful
# A round that OVERTURNED a belief is `corrected`, and then the lesson is
# REQUIRED — kb-remember refuses without it, because `graphify reflect` renders
# only this field and 21 of 32 past corrections reached LESSONS.md empty:
mise run kb-remember -- --question "<the belief that was wrong>" \
                       --answer-file .agent/round-answer.md --outcome corrected \
                       --correction-file .agent/round-lesson.md
mise run kb-reflect                       # aggregate -> reflections/LESSONS.md
mise run kb-remember -- --audit           # any correction still missing its lesson?
mise run kb-goal-outcome -- <pair> --result <r> [--turns N]   # if a /goal ran
mise run kb-distill                       # did this round hand-write a tool twice?
mise run kb-session-reflect               # what did it do by hand that a task owns?
```

`kb-remember` is what makes the corpus compound: a lesson that lives only in a
transcript is private to a session nobody will re-read. `kb-reflect` turns the
accumulated work-memory into the learning overlay every future query benefits
from. Both are cheap; skipping them is how a round's real finding evaporates.

Also write anything durable into **auto-memory** (step 4a) — the two layers
answer different questions. `graphify-out/memory/` teaches the *corpus*;
auto-memory teaches the *next session*.

**`kb-distill` is the third thing a round can leave behind, and the one nobody
was capturing** (#219). It reads this project's transcripts for throwaway
scripts — a `python3` heredoc, a scratchpad `.py` — and proposes a
`skill -> mise task -> kb_setup module` for any shape written more than once.
It lives here rather than in its own skill precisely because a task does not
need one: `md-size-budgets.md`'s listing budget is a real cost, and the trigger
for this one is "a round just ended", which is what this skill already is.

Read its output as **leads**. It always exits 0 and gates nothing; an
undistilled probe is a statement about future cost, not a failure. **Nothing to
propose is the common, correct result** — a session of one-off work should
produce an empty report, and that is what makes a non-empty one worth reading.
The measured backdrop: 785 ad-hoc scripts across 40 sessions, of which
`python/src/kb_setup` (patch a source file, run tests, restore) is the largest
group — i.e. the mutation harness, hand-written five times and still tracked as
open in #160.

**`kb-session-reflect` is the fourth, and it asks what distill cannot.** distill
is a FREQUENCY miner — it groups scripts across 50 sessions by import signature,
so it answers *was a program written twice?* A step done by hand ONCE, in one
session, has no frequency to mine and is invisible to it: a directive violated
at a rate, a probe that answered without asking, a run of adjacent tasks wanting
one wrapper. That gap has a number on it — distill's largest group is now **149**
hand-written mutation harnesses across 21 sessions, every one a fresh scratchpad,
while `kb-arms` has existed to replace them since #160.

Both read the same transcripts through one reader (`distill.tool_uses`), and
both are advisory. Read `.claude/skills/kb-session-reflect/SKILL.md` when a
finding looks worth turning into a `skill -> task -> module` triple; it carries
the rule for which of those three layers a lead actually earns.

## 3. Documentation sync — make the docs match what happened

For everything this session changed (uncommitted **and** commits not yet
reflected in docs):

1. **Root `CLAUDE.md`** for cross-cutting changes — new tasks, changed
   invariants, a new derived artifact. It sits near its 200-line budget, so any
   addition needs an offsetting trim; prefer collapsing duplication into a
   pointer over deleting a load-bearing fact.
2. **`.claude/rules/*.md`** when a lesson generalises past this round.
   `.claude/CLAUDE.md` for anything about the issue tracker or the executor
   lanes.
3. **Cross-references.** Grep for anything renamed, moved, deleted or re-timed:

   ```bash
   git grep -nE "<old-filename>|<old-task>|<renamed-symbol>" -- ':!.agent*' ':!*.lock'
   ```

   Common sources: mise task names, `kb_setup` module names, doc paths, issue
   numbers that got superseded.
4. **`docs/` specs and `sources/REGISTRY.md`.** Update status banners; keep
   point-in-time analysis legible by marking the old state as baseline rather
   than rewriting the reasoning. Any repo an agent read this session goes in a
   `## GitHub repos touched` section and into the registry backlog
   (`research-repo-enumeration.md`).
5. **GitHub issues** — tick checklists, file follow-ups, cross-link
   (`gh issue edit`, `gh issue comment`). An issue that a round silently
   resolved but never closed is the same defect as a stale doc.

**Never rewrite `sources/**` to match a rename.** Corpus content records what a
source said at ingestion time; editing it to keep links tidy falsifies the
provenance the manifest exists to guarantee. Fix the pointer in the authored
doc instead.

Markdown size is **class-aware** — the table lives in
`.claude/rules/md-size-budgets.md` and the gate is the `md_size_budget` hk step.
Do not restate a flat "200 lines / 12,000 chars": the 12,000 figure is
Windsurf's, and misattributing it is what that rule exists to kill.

## 4. Persist recovery context — three layers

Different layers survive different things. Do all three.

| Layer | Survives `/clear` | Survives a fresh clone | Answers |
|---|---|---|---|
| auto-memory (`~/.claude/projects/…/memory/`) | yes | yes | what the next session must know |
| `.agent/plans/session-*.md` | yes | **no** — gitignored | how to resume *this* work |
| `.agent/kb/reports/agents/*.md` | yes | **no** — gitignored | the evidence behind a finding |
| `graphify-out/memory/` (via `kb-remember`) | yes | yes — committed | what the *corpus* learned |

### a. Auto-memory — survives `/clear` AND a fresh clone

Write or update one fact per file under
`~/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/memory/`
with the usual frontmatter (`name`, `description`, `metadata.type`), then add a
one-line pointer to `MEMORY.md`. Record what shipped, what is next with issue
and PR numbers, decisions that are now settled, and any non-obvious gotcha.
Convert relative dates to absolute — "yesterday" is unreadable next week.

Update an existing memory rather than adding a near-duplicate, and delete one
that turned out to be wrong. A wrong memory is worse than a missing one because
it is auto-loaded and believed.

### b. The handoff — survives `/clear`, dies with the clone

Write `.agent/plans/session-<YYYY-MM-DD>[-letter].md`. Append a letter suffix
rather than overwriting an existing handoff for the same day.

It must be **self-sufficient**: step 7's resume prompt only points here, so
everything the next session needs is in this file. Include state at handoff
(branch, PR, gate results with their real exit codes), what shipped, the next
task with preload pointers, and the gotchas — especially any probe that
misled you, since that is what the next session would otherwise repeat.

### c. Findings-bearing agent reports — verbatim, at receipt

Per `agent-report-persistence.md` these should already be on disk at
`.agent/kb/reports/agents/<agent-name>.md`, written the moment each report
arrived. At clear-prep, **audit the coverage**: list every agent launched this
session; each findings-bearing one maps to a file, or to an explicit N/A in the
handoff. Anything missing gets written now, verbatim from context, before
`/clear` destroys the only copy.

**Cite each report by NAME, and `mise run kb-handoff-check` will audit the
coverage for you** (#148). Abbreviating the sha is fine and is what these
documents already do — `review-8a46d08…-cold.md` is checked as a pattern, so a
lane named for a commit nothing was ever written for now fails rather than
passing silently. Two things it cannot see, both stated so the silence is not
read as a pass: a name written in PROSE rather than as a filename (measured at
1-in-42 precision over 37 handoffs, so it is deliberately not extracted), and an
agent that ran and was never mentioned at all — out of reach for anything in
python, and out of scope per the ticket. Cite a report you know is missing as
`` `name` (absent) ``; the marker is checked both ways, so it cannot hide a real
one.

If a report is now load-bearing — something tracked cites it —
**promote a copy to `docs/research/reports/`**. `.agent/` is gitignored and dies
to any `git clean -xdf`, and a citation only one machine can open is not a
citation. `kb-review` lane reports are the exception with a stricter rule: they
live at `.agent/kb/review/reports/review-<sha>-<lane>.md` with any `:variant`
stripped from the lane, because `kb_setup.review` *reads* those filenames.

## 5. Validate, then commit

Run the gates that apply to what changed; each must exit 0 before you commit.
`verify-before-advancing.md` has the full matrix.

**Start with `mise run kb-gates`.** It runs the always-rows (`lint`, `test`,
`brain-audit`, `eval`), does *not* stop at the first failure, and writes each
result — task, exit code, the commit, the finish time — to
`.agent/kb/gates/gates-<sha>.json`. It exits 1 if any gate failed. That file is
what step 6 checks the handoff against; a number you retyped from a terminal has
nothing behind it once the session ends.

Then the conditional rows, by hand:

```bash
mise run lint-docs                  # CLAUDE.md / .claude/** touched
mise run kb-skill-score             # .claude/skills/** touched (advisory)
mise run kb-currency-check          # mise.toml pins touched
mise run kb-build                   # sources/** touched — reproduce from committed inputs
```

Capture the real exit code for those. `<gate> 2>&1 | tail -40` returns *tail's*
status and will report success for a gate that failed; redirect to a file, record
`rc=$?`, and read the file. That form is still correct for a one-off — what it
cannot do is survive the session, which is why the always-rows go through
`kb-gates` instead.

Stage specific paths rather than `git add .`. If you are on `main`, branch
**first** — `kb-land` ends by syncing `main`, so it leaves you checked out there
and the next commit lands on the default branch (`do-not.md` #7). Open a PR only
if the user asked; the handoff and auto-memory are not committed.

## 6. Self-verify the handoff against reality

The handoff is written from memory, and a wrong detail costs the next session
more than a missing one. Before printing the resume prompt:

- every path it cites exists;
- every `file:line` is real — read the cited line, do not eyeball it off a `sed`
  window, which is how a `:1836` that was really `:1830` reached three files;
- every `mise run <task>` it names is in `mise tasks ls`;
- every gate result matches `.agent/kb/gates/gates-<sha>.json`, not your
  recollection. **`mise run kb-handoff-check` now does this one for you** (#147)
  — it reads each `rc=` claim back against the record and checks the ROWS, not
  just the top-level `sha`. What it needs from you is the **commit, in the same
  bullet as the claim** — the shape `- Gates on 77661a3: …` with the sha
  backticked. A claim that names no commit cannot be looked up and is reported
  `UNVER`, and a sha in a neighbouring paragraph is deliberately not inherited.
  A branch name is not a commit. Read the verdicts as: `FAIL` the record
  contradicts you; `UNVER` nothing can speak to it (no record at that commit, or
  that gate was not in the run); `AMBIG` it holds with a caveat — usually that
  the tree was dirty, so the result describes that tree and not the commit;
- every number it repeats was measured *this* session, or is labelled as
  inherited and unverified (`probes-need-a-control-arm.md` rule 6).

**Say which branch the handoff is for, in its lead.** `mise run kb-ship` re-runs
this check against the **newest** handoff, and only when that handoff records
the branch you are on (#149) — so a handoff whose lead names no branch is one
the next session's ship skips. The lead is the paragraph
before the first `##`; step 1's `mise run kb-session-state` block already opens
with a backticked `- **branch**:` bullet, so pasting it satisfies this.

## 7. Emit the resume prompt — one line

All the context is in auto-memory (loaded automatically) and the handoff. The
prompt is therefore a pointer and nothing more. Inlining the task plan, issue
summaries or gate commands is the duplication this skill exists to prevent —
and a prompt that disagrees with the handoff sends the next session to the
wrong one.

```text
Read and follow .agent/plans/session-<date>.md
```

Then one line for the human: *"Run `/clear`, paste that, and the session resumes
from the handoff."*

## Keeping this skill honest over time

This repo can measure its own skills, so use that rather than taste:

- `mise run kb-skill-score` scores every project skill with `plugin-eval`'s
  deterministic static layer — free, no LLM, and comparable run to run. Read the
  **Δ column**, not the score: it is computed against the committed baseline in
  `docs/skills/baseline.json`, so the comparison is the task's job and not
  yours. Re-baseline with `-- --write` once a change is deliberate. A score
  never fails a gate (there is no validated floor), but a skill name matching
  nothing exits **2** rather than reporting an empty corpus.
- Read the number with its condition attached. `triggering_accuracy` is a regex
  over the description, so it rewards the literal words "proactively" and
  "automatically". Chasing it is keyword-stuffing; fixing a genuinely vague
  description is not. For this skill the dimension is inert (see the banner).
- SkillOpt's mutable marketplace plugin is disabled while its immutable
  provenance/API contract is established. `/skillopt-sleep` is intentionally
  unavailable until a later project-local adapter preserves explicit adoption.
- The durable record of how a round went is `mise run kb-remember` (step 2), not
  a comment in this file.

## Checklist

- [ ] Next-task ambiguity driven to zero via `AskUserQuestion`; answers encoded verbatim.
- [ ] Nothing-lost check passed: auto-memory + handoff + persisted reports reconstruct the working context.
- [ ] Working state snapshotted; open PR/CI state known.
- [ ] Session-local background tasks, agents and wakeups inventoried; stale ones stopped.
- [ ] Session-independent processes (GHA runs, Renovate) inventoried, not waited on.
- [ ] **Corpus loop closed BEFORE `kb-ship`**: `kb-remember` + `kb-reflect` (+ `kb-goal-outcome` if a goal ran).
- [ ] Docs, rules, issues and `sources/REGISTRY.md` match what happened; cross-refs grep-clean.
- [ ] Applicable gates green with their real `rc`; at-budget markdown files flagged in the handoff.
- [ ] Every findings-bearing agent report on disk verbatim; load-bearing ones promoted to `docs/research/`.
- [ ] Auto-memory written + `MEMORY.md` pointer added.
- [ ] Handoff written and self-verified (paths, `file:line`, task names, gate rcs, inherited numbers labelled).
- [ ] Branch is not `main`; commit made if appropriate.
- [ ] One-line resume prompt printed.

## See also

Related skills and rules this one defers to rather than restating:

- `.claude/skills/kb-review/SKILL.md` — the review that must precede `kb-ship`;
  its receipt is what step 2's ordering trap is about.
- `.claude/skills/kb-curator/SKILL.md` — the ingestion loop that owns
  `kb-remember` / `kb-reflect` in full; step 2 only covers closing them out at
  handoff time.
- `.claude/skills/goal-engineering/SKILL.md` — the companion for a round that
  ran a `/goal`, and the owner of `kb-goal-outcome`.
- `.claude/rules/clarify-before-acting.md` — why step 0 uses `AskUserQuestion`
  for every question, including the small ones.
- `.claude/rules/agent-report-persistence.md` — the verbatim-at-receipt contract
  step 4c audits.
- `.claude/rules/verify-before-advancing.md` — the full gate matrix step 5
  samples from.
- `.claude/rules/md-size-budgets.md` — the per-class markdown budgets, and why
  no flat character limit is quoted here.
