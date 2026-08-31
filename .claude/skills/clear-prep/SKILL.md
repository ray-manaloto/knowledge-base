---
name: clear-prep
description: "Prepare for a /clear in the knowledge-base repo: drive the next task to zero ambiguity, close the corpus loop (kb-remember + kb-reflect + kb-goal-outcome) BEFORE shipping, sync docs, persist memory + a self-sufficient handoff, and emit a one-line resume prompt. MAIN SESSION THREAD ONLY — never from a subagent, fork, or agent team. Use it PROACTIVELY, without being asked, when a round is ending (PR open and gates green, BEFORE kb-land, so the corpus loop closes while the reviewed commit is still an ancestor); whenever the user asks to /clear, asks for a handoff or a wrap-up, or asks what the next session should do; explicitly as /clear-prep [next-task]; and on a context threshold you must MEASURE with `mise run kb-context` rather than estimate — the token countdown in your context is a SPEND BUDGET, not window occupancy, so it will read as roomy at 48% full. It prepares the handoff and then ASKS the user to /clear; it never clears."
disable-model-invocation: false
argument-hint: "[one-line description of the next task, optional]"
---

# Clear-Prep — Session Handoff Before `/clear`

Run this **before** `/clear` so the next session loses nothing. Three jobs, in
this order: (1) find out what the next task actually is, (2) put everything
worth keeping somewhere that survives the clear, (3) print one line to paste
afterwards.

## The context trigger: MEASURE it, and only on the main thread

**You cannot see your own context occupancy, and the number you CAN see is a
different quantity.** The "~20% of the window" trigger never once fired, because
nothing reports what it names: the only context-ish signal a session gets is
`<total_tokens>N tokens left</total_tokens>`, a **spend budget**. Measured on
transcript `672f23a4` — real occupancy **475,917, 47.6% of a 1M window**, while
that reminder read **14,981,005 of 15,000,000 left, 99.9% remaining**, so a
session concludes it has room at twice the threshold. Flipping
`disable-model-invocation` could not fix that: the flag governs whether you MAY
invoke this skill, not whether you can tell the condition holds.

So the trigger is `mise run kb-context`, never an estimate — run it when a round
feels long, after a large read or fan-out, and before deciding you have room.
Exit **10** at or over threshold · **0** under · **127** could not measure (which
is *not* "you are fine") · **3** not the main thread — reserved and UNREACHABLE,
`CHILD_MARKERS` being empty since #451, which is why the next line enforces it.

**Main session thread only** (Ray, 2026-08-21: *"not on subtasks or spawned
agents or agent teams"*) — **nothing tells you which you are, so this instruction
IS the enforcement.** A fork carries its parent's session id and transcript, and
the two env vars that looked like the answer are a Bash-subprocess marker and an
operator enable-flag, set on the main thread too — so `kb-context` refused there
100% of the time until 2026-08-22 (#451). If you are a subagent, report back.

Work top-to-bottom. The ordering in step 2 is not stylistic; it is the one thing
in this skill that cannot be reordered without losing work.

> **Model-invocable since 2026-08-21 (Ray, verbatim: "it should also be able to be
> triggered by an agent so that it runs when context hits over 20% — so toggle this
> flag").** Until then `disable-model-invocation: true` hid it from the listing so only a
> human could fire it; the 2026-08-21 session review measured why that failed — 20% of
> context was crossed 15 minutes in and the ask came at ~75%. The trigger is still a
> question, never a silent run: an agent invokes this skill to PREPARE the handoff and
> then asks the user to `/clear` (AskUserQuestion). The intended mechanical trigger is a
> DENY-style guard on context usage (session-review R1, #431/#433) — not built yet, so
> until it lands the trigger is the description plus the agent's own context reading.
> The description is what model invocation matches on, so it now names the triggers
> (context past ~20%, a round ending, the user asking for a handoff). Step 7 is where
> the "asks the user" half is made concrete.

## 0. Resolve next-task ambiguity FIRST (Ray, 2026-07-08)

**The next task is GENERATED, not chosen.** `$ARGUMENTS` if the user named one;
otherwise `uv run kb-setup next-ticket`, quoted VERBATIM — offering options it
already answered is inferring one with extra steps (Ray, 2026-08-29, handed a
menu built from a definite answer: *"shouldnt this be generated now?"*). **When
its output is an IMPERATIVE — `STALE CHAIN … remove it, then re-run` — that is
work, not a status: do it, re-run, hand over what comes back.** This rule lived
in the preamble and lost to the numbered step below; it now leads that step.
**Then drive whatever REMAINS to zero ambiguity via `AskUserQuestion`** — every
question through it, yes/no included; prose gives the user nothing to click.

**On a model-invoked run this step is also the consent gate.** The skill can
trigger itself (`disable-model-invocation: false` — Ray, 2026-08-21: *"flip the
flag so this can be automated"*), so when the user did not type `/clear-prep`,
say so in this first `AskUserQuestion` and offer *"not now"* alongside the
next-task options. Nothing is written before that answer — no work-memory, no
handoff, no auto-memory, no commit. Automatic invocation buys the EARLY ask, not
an unattended write, and that is the whole of the difference.

On *"not now"*, **stop**: write nothing and resume whatever the session was
doing. That answer defers on the same terms as step 7's *"not yet"* — it expires
on the next qualifying trigger listed there, so it is a deferral rather than a
refusal, and the skill will offer again rather than either nagging or going
silent for the rest of the window.

The handoff's "next task" section is only as good as this step. If the task
admits multiple readings, a scope fork, an undecided B-vs-C, or an unstated
end-goal, surface each one, get the answer, and encode it **verbatim** — a
paraphrase of a decision is a decision the next session gets to relitigate.
Skipping this because the task "seems clear" is the exact failure this step
exists to prevent.

Then ask the losing-nothing question directly: *if I `/clear` right now and the
next session has only auto-memory + the handoff + the persisted reports, can it
continue with no gaps?* If the answer is no, fix that before step 7.

**Read the newest `docs/direction/*-ray-directives.md` before you frame that
question.** It holds Ray's directives VERBATIM and is the standing brief the
round is measured against, so a "next task" chosen without it can be locally
sensible and off the brief. Until 2026-08-17 **nothing read this directory** —
the only tracked references to it were two lines in `hk.pkl` about a formatter
exclusion — so a directive could be filed carefully and never consulted again,
which is the failure this step now closes. `docs/goals/` has both a Layout row
and a reader; this now has both too.

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

**If a `planning-with-files` plan is active, its files are gather inputs** — all
of them, from the dir `resolve-plan-dir.sh` prints. `progress.md` is the round's
narration, `task_plan.md`'s decisions journal the reasoning behind what shipped,
and **`findings.md` is where the round's research actually accumulated** (it is
the plugin's untrusted-content sink, so it holds what `task_plan.md` may not).
`ledger-*.jsonl` is the per-action record. All feed the handoff; none replaces it
— the plan dies with the clone and carries no gate evidence, receipt, or
generated next task.

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

So close the loop while the branch is still unmerged. **Write the answer and
lesson files first** — `kb-remember` refuses a path that does not exist, and
`.agent/` is gitignored so it may not be there at all:

```bash
mkdir -p .agent/plans && : > .agent/round-answer.md   # + round-lesson.md if correcting
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

**`kb-distill` is the third thing a round can leave behind** (#219). It reads
this project's transcripts for throwaway scripts — a `python3` heredoc, a
scratchpad `.py` — and proposes a `skill -> mise task -> kb_setup module` for any
shape written more than once. Read its output as **leads**: it always exits 0 and
gates nothing, and **nothing to propose is the common, correct result** — which
is what makes a non-empty report worth reading.

**`kb-session-reflect` is the fourth, and asks what distill cannot.** distill is
a FREQUENCY miner, grouping scripts by import signature: *was a program written
twice?* A step done by hand ONCE has no frequency to mine and is invisible to it
— a directive violated at a rate, a probe that answered without asking, adjacent
tasks wanting one wrapper. Both read the same transcripts through one reader
(`distill.tool_uses`) and both are advisory. Read
`.claude/skills/kb-session-reflect/SKILL.md` when a lead looks worth a
`skill -> task -> module` triple; it carries the rule for which layer it earns.

## 3. Documentation sync — make the docs match what happened

For everything this session changed (uncommitted **and** commits not yet
reflected in docs):

1. **Root `CLAUDE.md`** for cross-cutting changes — new tasks, changed
   invariants, a new derived artifact. It sits near its 200-line budget, so any
   addition needs an offsetting trim; prefer collapsing duplication into a
   pointer over deleting a load-bearing fact.
2. **`.claude/rules/*.md`** when a lesson generalises past this round.
   `.claude/CLAUDE.md` for the issue tracker or the executor lanes.
3. **Cross-references.** Grep for anything renamed, moved, deleted or re-timed —
   mise task names, `kb_setup` modules, doc paths, superseded issue numbers:

   ```bash
   git grep -nE "<old-filename>|<old-task>|<renamed-symbol>" -- ':!.agent*' ':!*.lock'
   ```

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

Write `.agent/plans/session-<YYYY-MM-DD>[-letter].md` — after `mkdir -p
.agent/plans`, since `.gitignore` ignores `.agent/` and a fresh clone has none,
so the write fails before the round's recovery artifact exists. Append a letter suffix
rather than overwriting an existing handoff for the same day.

It must be **self-sufficient**: step 7's resume prompt only points here, so
everything the next session needs is in this file. Include state at handoff
(branch, a backticked-sha `- **HEAD**:` bullet in the lead, PR, gate results
with their real exit codes), what shipped, the next
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
passing silently. Two things it cannot see, stated so the silence is not read as
a pass: a name written in PROSE rather than as a filename (1-in-42 precision over
37 handoffs, so deliberately not extracted), and an agent that ran and was never
mentioned at all. Cite a report you know is missing as `` `name` (absent) ``; the
marker is checked both ways, so it cannot hide a real one.

If a report is now load-bearing — something tracked cites it — **promote a copy
to `docs/research/reports/`**. `.agent/` is gitignored and dies to any
`git clean -xdf`, and a citation only one machine can open is not a citation.
`kb-review` lane reports are the exception, with a stricter rule: they live at
`.agent/kb/review/reports/review-<sha>-<lane>.md` with any `:variant` stripped
from the lane, because `kb_setup.review` *reads* those filenames.

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

**Then re-pin the handoff to the commit you just made.** Step 4b wrote its
`- **HEAD**:` bullet before this commit existed, so it names that commit's
PARENT — every round, by construction, since what you are committing IS step 2's
`kb-remember` output. Re-run `uv run kb-setup session-state`; correct the sha and
the ahead-count. It costs nothing — `.agent/` is gitignored, so the handoff is
never committed and there was no ordering paradox, only a missing step.

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
- **the HEAD in its lead is still HEAD** — `kb-handoff-check`'s `head` row FAILS
  one behind by real work, AMBIGs one behind by only `review.EXEMPT_PATHS` (step
  5's closing commit), and UNVERs one whose branch was squash-merged away;
- every number it repeats was measured *this* session, or is labelled as
  inherited and unverified (`probes-need-a-control-arm.md` rule 6).

**Say which branch the handoff is for, in its lead.** `mise run kb-ship` re-runs
this check against the **newest** handoff, and only when that handoff records
the branch you are on (#149) — so a handoff whose lead names no branch is one
the next session's ship skips. The lead is the paragraph
before the first `##`; step 1's `mise run kb-session-state` block already opens
with a backticked `- **branch**:` bullet, so pasting it satisfies this.

## 7. Emit the resume prompt — one line

All the context is in auto-memory (loaded automatically) and the handoff, so the
prompt is a pointer and nothing more. Inlining the task plan, issue summaries or
gate commands is the duplication this skill exists to prevent, and a prompt that
disagrees with the handoff sends the next session to the wrong one.

**The pointer is a skill, so there is nothing to paste:**

```text
/session-resume
```

It finds the newest handoff itself, reads the newest directive with it, and — the
part a pasted path cannot do — CHECKS both against the repo, reporting where they
disagree. Ray, 2026-08-19: *"we need to automate this better so that i can just
run a slash command and/or skill on the next session that just knows how to jump
to handoff so there is less copy/paste needed."* `/session-resume <path>` reads a
SPECIFIC handoff instead; that skill documents the fresh-clone fallback.

**Print this line even when the round ended untidily.** It was skipped on
2026-08-19 and the next session had no idea where to start.

**Then ASK the user to `/clear` — via `AskUserQuestion`, never in prose, and
never by clearing yourself.** This is the "asks the user" half of the banner,
and it is the last thing this skill ASKS (the archive below still follows it on a
*"/clear now"*) whether a human typed `/clear-prep` or an agent invoked it at
~20% context: one question, options *"/clear now (then `/session-resume`)"* and
*"not yet — keep going"*, with the handoff path and the resume line in the
question text so answering is one click. Only the user runs `/clear`. On *"not
yet"*, resume the work — the handoff stays valid until something changes — and do
not ask again until the NEXT qualifying trigger: a further PR opened or landed, a
new directive, the user raising it, **or roughly another 25 percentage points of
context consumed** (so a *"not yet"* at ~20% asks again near ~45%, then ~70% —
bounded, never *never*). Re-asking next turn is the nagging this skill must not
become; a deferral that never expires is the worse failure, leaving a session
writing its handoff at the end of the window instead of the start.

**On *"/clear now"* — and only then — ARCHIVE the plan, but only if it is DONE:**

```bash
PWF="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/cache/planning-with-files/planning-with-files/3.12.0}"
sh "$PWF/scripts/check-complete.sh"   # phases still in_progress? then DO NOT archive
mkdir -p .planning/.archive && mv .planning/<id> .planning/.archive/<id>
grep -qx '<id>' .planning/.active_plan 2>/dev/null && rm .planning/.active_plan
```

**Archiving an UNFINISHED plan destroys the thing the plugin exists for** — its
`SessionStart` hook (matcher `startup|resume|clear|compact`) restores a live plan
after exactly the `/clear` you are preparing, and in gated mode the Stop hook is
still counting its phases. So check first — an incomplete plan is normal and stays.
The `.active_plan` guard matters: one global pointer a parallel `PLAN_ID` may hold.

Two details are load-bearing. Nothing creates `.archive/`, so without `mkdir -p`
the first archive fails and an `&&` chain silently leaves the plan selected. And
the leading dot matters because `resolve-plan-dir.sh` falls back to the newest
`.planning/<dir>/` by mtime while **skipping hidden dirs** (`.*) continue ;;`).

**Find the plan before you move it** — `resolve-plan-dir.sh` honours `PLAN_ID`
and `PWF_PLAN_ROOT`, and legacy mode keeps `task_plan.md` at the repo ROOT with
no `.planning/` at all. Archive rather than delete; `.planning/` is gitignored,
so none of it is corpus. After the answer, never before the ask. Then stop: next
is the user's `/clear`, then `/session-resume`.

## Keeping this skill honest over time

This repo can measure its own skills, so use that rather than taste:

- `mise run kb-skill-score` scores every project skill with `plugin-eval`'s
  deterministic static layer — free, no LLM, comparable run to run. Read the
  **Δ column**, not the score: it is computed against `docs/skills/baseline.json`.
  Re-baseline with `-- --write` once a change is deliberate. A score never fails a
  gate, but a skill name matching nothing exits **2**, not an empty corpus.
- Read the number with its condition. `triggering_accuracy` is a regex over the
  description, so it rewards the literal words "proactively" and "automatically" —
  chasing it is keyword-stuffing; fixing a vague description is not.

## Checklist

- [ ] Next task GENERATED (`next-ticket`, verbatim; an imperative EXECUTED then re-run); only what remains asked.
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
- [ ] Branch is not `main`; commit made if appropriate — then the handoff's HEAD re-pinned to it (step 5).
- [ ] Resume prompt printed — `/session-resume` (skipped on 2026-08-19; the next session had no idea where to start).
- [ ] Step 7's `AskUserQuestion` was PUT to the user and the answer recorded — `/clear now` **or** `not yet`; both valid, and only the user ever clears.
- [ ] On `/clear now` **only**, and only if `check-complete.sh` says every phase is done: plan archived to `.planning/.archive/`, and `.active_plan` cleared **only if it named that plan**.

## See also

- `.claude/skills/session-resume/SKILL.md` — the other end of this loop, and
  where a surviving plan gets reported.
- `.claude/skills/kb-review/SKILL.md` — the review that must precede `kb-ship`;
  its receipt is what step 2's ordering trap is about.
- `.claude/skills/kb-curator/SKILL.md` — owns `kb-remember` / `kb-reflect` in
  full; step 2 only closes them out at handoff time.
- `.claude/skills/goal-engineering/SKILL.md` — for a round that ran a `/goal`;
  owns `kb-goal-outcome`.
- `.claude/rules/clarify-before-acting.md` — why step 0 uses `AskUserQuestion`
  for every question, including small ones.
- `.claude/rules/agent-report-persistence.md` — the verbatim-at-receipt contract
  step 4c audits.
- `.claude/rules/verify-before-advancing.md` — the gate matrix step 5 samples.
- `.claude/rules/md-size-budgets.md` — the per-class budgets, and why no flat
  character limit is quoted here.
