# Rider — `Legible` round (knowledge-base)

This rider holds the prescriptive constraints for the goal at
`docs/goals/2026-07-27-1702-kb-redaction-legibility-goal.md`. It supersedes nothing; it composes
forward from `.agent/plans/session-2026-07-27-d.md`, which is the ground truth for
what is left. **When the plan and this rider disagree, the plan wins; fix the rider
in the same commit.** (Pattern lifted from Ceccarelli's audit-anchor rule —
`res-ceccarelli.md:370-379`, "the matrix wins. Update the rider in the same commit.")

---

## 1. Scope decision — this is ONE round, and two items were split out

The brief asked me to judge whether the open work is one round or two. **It is one
round, headline word `Legible`, and it covers item (a) only.**

The plan (`session-2026-07-27-d.md:16-54`) lists three open items:

| Item | Verdict | Why |
|---|---|---|
| (a) `[redacted]` over-redaction, cause unestablished | **IN this round** | The only code-shaped work. It has a question, a forbidden answer, and a testable end state. |
| (b) Secret rotation | **OUT — Ray's, hand-back** | `session-2026-07-27-d.md:42-46`: "Nothing in the repo can do this and no code change substitutes for it." An agent cannot do it and must never report it done. |
| (c) CodeRabbit "Review rate limited" | **OUT — a decision, not a task** | `session-2026-07-27-d.md:49-54` states it as a disjunction Ray picks between: "Either wait out the rate limit and request a re-review, or stop treating that check as evidence." Policy, not implementation. |

### Why (a) and (c) are NOT one round, even though they rhyme

They share a failure *shape* — a signal that reads as evidence without being one.
`[redacted]` corrupts gate output; `CodeRabbit pass "Review rate limited"` is a check
that "never asked the question" (`verify-before-advancing.md`, quoted at
`session-2026-07-27-d.md:51-53`). It is tempting to fold them under one word like
"Evidence".

Do not. Ceccarelli's test is that the headline word names **the state of the world
after the round** (`res-ceccarelli.md:895-899`), and the two items reach different
states by different means: (a) ends in a merged PR or a recorded negative finding;
(c) ends in a *policy decision by a human* plus possibly a re-review request to a
third-party service on its own rate-limit clock. Bundling them gives the agent a
second, human-gated arm it cannot close, which is precisely the "goal that can never
be satisfied" hazard — a failure mode Ceccarelli's piece does **not** cover
(`res-ceccarelli.md:810`) and that we therefore have to guard ourselves.

`Legible` names (a)'s end state exactly: **task output in this repo says what it
actually says.**

---

## 2. The evaluator constraint — the single discipline that shapes every clause

Claude Code's `/goal` evaluator is a session-scoped prompt-based Stop hook. Verbatim
from the docs (`res-bestpractices.md:104-114`, quoting `/docs/en/goal.md`):

> The evaluator runs on whichever provider your session is configured for. It does
> not call tools, so it can only judge what Claude has already surfaced in the
> conversation.

and

> It doesn't run commands or read files independently, so write the condition as
> something Claude's own output can demonstrate.

**Consequence, and the rule for this whole pair:** a clause is legitimate only if a
Haiku-class reader, given the transcript and nothing else, can answer it by string
match. "The tests pass" is unjudgeable. "The transcript contains the line
`PASS  gate test rc=0`" is judgeable.

Sabrina's operational test says the same from the other side
(`res-sabrina.md:212-218`): a good VERIFICATION line "gives Claude something it can
literally check". Her two best-shaped examples (#4, #5) both name an instrument, a
threshold, and a loop-until — and both happen to land as *text in the conversation*,
which is what makes them portable to our evaluator (`res-sabrina.md:272-280`).

### Conflict resolved: Ceccarelli's verification style does not survive this harness

Ceccarelli's Verification sections are "a set of commands a human can paste into a
terminal" (`res-ceccarelli.md:843-849`), and his answer to LLM-as-judge is an
external watchdog, `dr-gate`, which "re-runs the goal's executable checks itself and
signs the result with a secret the agent process cannot read"
(`res-ceccarelli.md:36-43`). He is explicit that Claude Code's `/goal` "leans on an
LLM-as-judge inside the same harness … which is opinion, not evidence."

**We do not have dr-gate and cannot build one this round.** So:

- **KEEP** from Ceccarelli: the five-section skeleton, the headline-word test, Posture
  as negations, and the preserve list ("the agent's permission slip",
  `res-ceccarelli.md:314-320`).
- **REPLACE** his verification style with literal-quoted-transcript assertions, per
  Anthropic's docs and Sabrina's test.
- **BE HONEST ABOUT THE RESIDUAL:** a quoted gate line is evidence the agent
  produced about itself. It is strictly weaker than a signed receipt. Our only
  hardening is that the strings are (i) *exact*, including spacing, so a paraphrase
  fails the match, and (ii) *produced by code the agent did not write this round*
  (`kb_setup.pr`), so forging them means editing a gate — which the preserve list and
  `zero-skip-policy.md` both forbid. Say this out loud rather than pretending the
  loop is closed.

### Second conflict: eleven phases and test-first

Ceccarelli mandates ~11 phases, each opening with named failing depth tests
(`res-ceccarelli.md:197-234`). This round is an **investigation**; several phases
produce a *finding*, not a diff, and a finding has no failing test to write first. He
concedes the number himself — "The eleven is a target, not a religion. Some pairs are
9" (`res-ceccarelli.md:200`). **Resolution: seven phases (P1–P7); depth tests are
mandatory only for phases that change code, and the repo's own rule already sets that
bar** (`verify-before-advancing.md`: a new module with no test file is not covered by
a green suite).

### Third conflict: where the pair lives

Ceccarelli: `<project>/docs/goals/<YYYY-MM-DD>-<HHMM>-<project>-<topic>-{goal,rider}.md`,
"the pair lives in docs/goals/ forever … It has a sha" (`res-ceccarelli.md:29-32,
101-108`).

**RESOLVED — and this section is the record of it changing.** The draft of this rider
said the repo had no `docs/goals/` and proposed leaving the pair under `.agent/`, with
promotion deferred to P7. That is no longer true: `docs/goals/` was created when this
pair was adopted, and both files live there under Ceccarelli's schema, tracked. The
paragraph is rewritten rather than deleted because a rider that still described the
old plan would be the "two docs, opposite claims, neither checked" defect
`tool-currency-and-native-first.md` rule 5 exists to prevent.

The reasoning that forced it stands: `.agent/**` is gitignored
(`agent-artifact-conventions.md`), and `agent-report-persistence.md` rule 1b requires
a load-bearing artifact to be **promoted** to a tracked path, because "a citation to a
file only one machine can open is not a citation." The goal file is cited by the
`/goal` condition itself, which makes it load-bearing by definition.

What stays under `.agent/` is the disposable layer: the four research reports
(`res-*.md`) and the two synthesis drafts (`syn-*.md`) this pair was distilled from.
`docs/goals/README.md` is the tracked index.

---

## 3. PRESERVE LIST — change everything except these

Ceccarelli's sharpest lesson: without this list, "an agent doing an editorial pass
eventually decides the cyan banner is 'inconsistent' and removes it. Removing it
improves the audit metric" (`res-ceccarelli.md:314-320`). The metric here is "no more
`[redacted]` in output", and the cheapest way to satisfy it is to delete or silence
things this repo exists to protect. So:

| Must not change | Where | Why |
|---|---|---|
| The archived verbatim agent reports | `docs/research/reports/*.md` | `session-2026-07-27-d.md:114-117`: the directory "is excluded from hk builtins and must stay so — rumdl and the whitespace builtins would rewrite the archived agent reports." Do not reformat. Do not rename to `.../agents/` (agnix reads `**/agents/*.md` as agent *definitions*). |
| `_STRIP_BACKEND_ENV` and `_STRIP_MISE_ENV_PREFIX` as **two separate constants** | `python/src/kb_setup/graphify_env.py:31` and `:88` | The code comment at `:64` says it in the file: "A SECOND, unrelated reason to strip — do not merge this into the tuple above." Merging them makes one list serve two unrelated invariants. |
| The two deliberately-unchanged call sites | `mise which` in `graphify_exe()` (`graphify_env.py:112`) and the Claude Code spawn in `python/src/kb_setup/launch.py` | `session-2026-07-27-d.md:86-88`: "with reasons in the code so they do not read as oversights." An agent tidying for consistency will "fix" them. |
| The retracted-probe record | `mise.toml:114-121` (`[tasks.eval]` comment) | It is the artifact that stops a **third** retraction of the `[env]` theory. Deleting it as "stale comment" destroys the round's own guardrail. |
| `version_pattern` in `[tool.mise]` | `currency.toml` | `session-2026-07-27-d.md:118-121`: `mise --version` prints a trailing date; the default heuristic returns the DATE. Removing the pattern silently reports the wrong version. |
| `PASS  gate <name> rc=<rc>` and the ship/land strings | `python/src/kb_setup/pr.py:82,156,166,226` | These are this round's evidence channel. Changing their text invalidates every verification clause in the goal. |

---

## 4. POSTURE — what this round does not do

Six of these are negations, by design (`res-ceccarelli.md:157-171`).

1. **No dotfiles changes.** Deferred by Ray's explicit decision
   (`session-2026-07-27-d.md:129-138`); the port happens only after a real mise
   self-update is caught end-to-end. This includes the `__MISE_DIFF` strip, which is
   "deliberately NOT done yet, same reasoning: prove it here first" (`:136-138`).
2. **No `[tools] "ubi:jdx/mise"`.** `session-2026-07-27-d.md:108-110`: it moves
   `which(mise)` into the install dir, so currency compares pinned against pinned and
   reports in sync forever.
3. **No `{{ get_env(name='PATH') }}`.** `session-2026-07-27-d.md:104-107`: bound to
   `PRISTINE_ENV` it reverses `__MISE_DIFF` and removes every path mise added. The
   published proof that made it look right used `env -i`, where the diff is empty.
4. **No `.sh` file and no inline shell logic** in `mise.toml` / `hk.pkl`
   (`zero-bash-logic.md`; this repo has zero and that is the invariant).
5. **No inline lint suppression** — no `noqa`, `type: ignore`, `nosec`; the
   `no_lint_skip` hk step rejects them (`do-not.md` #9).
6. **No bare `graphify`.** Every graphify operation goes through a `kb-*` mise task;
   the PreToolUse guard denies the alternative (`do-not.md` #3, `mise-tasks-only.md`).
7. **No commit on `main`.** Branch first, then `mise run kb-ship` (`do-not.md` #7).
8. **No third proposal of the retracted theory** — see §6.
9. **Turn cap: 25.** Sabrina's mechanism, prose inside the constraints, not a flag
   (`res-sabrina.md:169-191`: "Add a turn cap in CONSTRAINTS, like 'stop after 30
   turns.'"). Note the docs' caveat: the bound is **not harness-enforced** — Claude
   self-reports progress and the evaluator judges the self-report
   (`res-bestpractices.md:288-296`). And a `--resume` silently re-arms it
   (`res-bestpractices.md:453-456`). Treat 25 as a discipline, not a fuse.

---

## 5. The question this round answers

**Observation to explain.** `mise run <task>` masks literal substrings of its own
output as `[redacted]`; `mise doctor` run directly does not
(`session-2026-07-27-d.md:25-27`). Confirmed victims, from
`session-2026-07-27-d.md:19-23` and `mise.toml:115-121`:

| Output | Printed as | Implied match |
|---|---|---|
| `16` | `[redacted]6` | the one-character string `1` |
| `S105` (a ruff rule code) | `S[redacted]05` | the one-character string `1` |
| `~/.local/state/hk/` | `~/.[redacted]/` | `local/state` or a component of it |
| `1 check(s) green`, `24 memories`, a PR URL | digits eaten | same |

The one-character match on `1` is the sharpest lead in the set: **something in mise's
redaction set is the literal string `1`.** A redaction engine whose set contains a
single common digit will corrupt essentially every numeric line it sees, which is
exactly the observed damage. That observation is a *discriminator*, not an answer —
do not skip to a cause.

**Established, do not re-derive** (`session-2026-07-27-d.md:25-27`,
`docs/research/reports/mise-path-research.md:326-335`):

- It is mise's task-output redaction, not the Claude Code harness.
- Redaction is a **display** feature: "Redactions work by intercepting task output
  line-by-line, so they require a non-`raw` output mode"
  (`docs/environments/index.md:170`, quoted at `mise-path-research.md:332-335`). It
  was never an env-var confidentiality mechanism — which is also why `__MISE_DIFF`
  escapes it entirely.
- `redact` appears 232× across mise `src/` — `src/redactions.rs`, `src/logger.rs`,
  `src/cmd.rs`, `src/cli/run.rs`, `src/cli/env.rs`, `src/config/env_directive/**`,
  `src/toolset/**` — and **0×** in `src/env_diff.rs` / `src/hook_env.rs`
  (`mise-path-research.md:326-331`). The grep has a control arm; it works.
- `mise env --redacted --values` "enumerates the values mise itself considers
  sensitive" (`mise-path-research.md:360`, citing `docs/environments/index.md:159-166`).

---

## 6. The banned move, and what counts as a NEW discriminator

`session-2026-07-27-d.md:28-32`, verbatim:

> **Retracted TWICE — do not propose a third time without a NEW discriminator:** the
> "a mise `[env]` value is the match source" theory. `mise.toml:116-121` records a
> prior session probing and disproving it; the session after that offered it again
> and it was retracted again.

A **new discriminator** is a probe whose two arms give *different* answers and at
least one of which no prior session ran. It is not a new argument, a new phrasing, or
a re-reading of this repo's config. Concretely, a qualifying discriminator would:

- read mise's own source or docs for what populates the redaction set **by default**,
  independent of `[env]` (`session-2026-07-27-d.md:34-38` names this as "exactly where
  the two retracted attempts never looked"); **or**
- compare `mise env --redacted --values` output against the strings actually being
  masked, and show they do or do not coincide.

Every negative in this round is control-armed or it is not reported
(`probes-need-a-control-arm.md`): before reporting "X is not the source", show the
same probe finding a source it *does* detect. A 0-result grep is not an answer until
a control arm has run — and note the token-spelling trap: mise spells things its own
way, so grep a term you know is present first.

---

## 7. PHASES

Each phase: do the work → produce the named transcript evidence → one conventional
commit whose subject ends `(rider P<N>)`. Green gates on every commit that changes code.

### P1 — Ground in HEAD, restate the round

Read, in order: this rider, `.agent/plans/session-2026-07-27-d.md`,
`.claude/rules/probes-need-a-control-arm.md`, `.claude/rules/verify-before-advancing.md`,
`mise.toml:110-125`, `docs/research/reports/mise-path-research.md` § Q4.
Create the branch. **No code.**
Evidence: post the preserve list back as a checklist, and the sentence "the `[env]`
theory is retracted twice and is banned without a new discriminator."

### P2 — Reproduce, with both arms

Produce the masking on demand and produce a control that does not mask. The plan
already names the shape: same figures via `mise run` (masked) vs `uv run kb-setup …`
(unmasked) (`mise.toml:115-121`).
Evidence: one `REDACT-ARM+` line and one `REDACT-ARM-` line (format in §8), showing
the same string masked under one command and intact under the other.

### P3 — Enumerate what mise itself calls sensitive

Run `mise env --redacted --values`. Compare its output against the strings observed
masked in P2. This is the plan's own nominated new angle
(`session-2026-07-27-d.md:36-38`).
Evidence: `REDACT-PROBE:` line stating whether the two sets coincide, with the
literal overlap or the literal disjointness.

### P4 — Read mise's redaction source for its DEFAULT population

Target `src/redactions.rs` first, then `src/cli/run.rs` and `src/logger.rs`
(`mise-path-research.md:326-329`). The question is narrow: **what enters the redaction
set when no `[env]` directive asks for it?** Verify against the installed/pinned
source, not the issue tracker (`use-tool-builtins.md`; graphify's stale-open #959 is
this repo's worked example of that trap).
Evidence: `REDACT-PROBE:` line citing `file:line` from mise's source.

### P5 — Land a cause, or land a negative

Exactly one of:

- **Arm A (cause established).** Ship the smallest change that makes output legible —
  a mise setting, a task-level flag, or a `kb_setup` seam. If it touches
  `python/src/kb_setup/**`, the module's own test file gets a named test and **both
  directions are armed**: break the thing, confirm rc=1, restore, confirm rc=0, and
  make the break realistic — delete the line that *calls* the function, do not rename
  its definition (`probes-need-a-control-arm.md` rule 2).
- **Arm B (no cause).** Record the negative *with the discriminator that produced it*
  in `mise.toml`'s existing `[tasks.eval]` comment block (extend it; do not rewrite
  it) so a fourth session does not re-run the same dead end. Arm B is a legitimate
  landing, not a failure — but only when §6's control-arm bar was met.

Evidence: the `REDACT-FINDING:` block (§8).

### P6 — Gates and ship

`mise run kb-ship`. It runs `lint`, `test`, `brain-audit`, `eval` in that order
(`python/src/kb_setup/pr.py:74`) and refuses to push if any fails. Quote all four
`PASS  gate …` lines and the `ship: OK …` line verbatim.
If anything is red, that *is* the current task — `zero-skip-policy.md`; do not defer
past it, do not suppress it.
Then `mise run kb-land -- <PR#>` and quote the `land: OK …` line.

### P7 — Close the loop, and the doc closure

- `mise run kb-remember -- --question "…" --answer "…" --outcome useful` — the
  durable half; the notepad is scratch and gitignored
  (`notepad-enforcement.md`).
- `mise run kb-reflect`.
- Write the next session handoff at `.agent/plans/session-<date>-<letter>.md`, and
  carry forward the two items this round did **not** touch (secret rotation;
  CodeRabbit) so they are not lost by being out of scope.
- If Ray adopted this goal+rider pair, promote both files to a tracked path (§2,
  third conflict).

---

## 8. SENTINEL FORMATS — exact strings the evaluator matches

The docs do not describe this technique; it is the inference at
`res-bestpractices.md:219-223` — "Naming a literal, unique, greppable token … is the
strongest way to make the judgement unambiguous." Emit these into the **main**
transcript. A result produced inside a subagent is invisible to the evaluator unless
the main session restates it (`res-bestpractices.md:544-547`).

```
REDACT-ARM+: <command> -> <literal output showing the mask> @ <sha>
REDACT-ARM-: <command> -> <literal output showing no mask> @ <sha>
REDACT-PROBE: <what was probed> -> <literal result> (<file:line or command>) @ <sha>
REDACT-FINDING: cause=<one sentence> | cause=NOT-ESTABLISHED @ <sha>
REDACT-FINDING-ARM: <the control arm that discriminated it> @ <sha>
HANDBACK: rotation — Ray @ <sha>
HANDBACK: coderabbit — Ray @ <sha>
GOAL-BLOCKED: <blocker> — tried: <probe1>; <probe2> @ <sha>
```

### The `@ <sha>` suffix is load-bearing — do not drop it

`<sha>` is the current `git rev-parse --short HEAD`, emitted at the time the line is
written. It exists because of a defect the rubric caught (`syn-rubric.md` T12), and
the defect is real:

- Setting a goal **starts a turn with the condition itself as the directive**, and the
  evaluator is sent *"the condition and the conversation so far"* (`goal.md`).
- So every literal string spelled out in the condition is **already in the transcript
  on turn 0**. A clause reading *"the transcript contains `REDACT-ARM+`"* is arguably
  satisfied before any work happens — by the condition quoting itself.

A short SHA cannot be pre-satisfied: it did not exist when the goal was authored, and
it changes as the round commits. Paired with the goal's EVIDENCE RULE (*"the text of
this condition is NOT evidence"*), it binds each sentinel to a real, later turn.

**Corollary — restate subagent output.** The evaluator sees only the main
conversation. A probe run inside a subagent, a `Workflow` fan-out, or a background
task is invisible to it. Paste the output into this conversation, or it did not
happen as far as the round is concerned.

`GOAL-BLOCKED:` is the **satisfiable second arm**, not a footnote. The docs name no
"I am blocked, hand back" primitive — the only documented exits are evaluator-yes,
`/goal clear`, `/clear`, and Ctrl+C (`res-bestpractices.md:332-342`). So the bound has
to be an arm the evaluator can say *yes* to, or the run is effectively unbounded.

---

## 9. VERIFICATION — the literal lines that must appear

Every one of these is a string match against the transcript. Nothing here requires the
evaluator to run, read, or infer.

**Always required:**

1. A `REDACT-ARM+` line and a `REDACT-ARM-` line from P2.
2. A `REDACT-FINDING:` line, and immediately after it a `REDACT-FINDING-ARM:` line.
3. Both `HANDBACK:` lines, verbatim.
4. The transcript contains **no** claim that a secret was rotated.

**Required on Arm A or Arm B (a shipped change or a recorded negative):**

5. These four lines, verbatim, two spaces after `PASS` (`pr.py:82`):

   ```
   PASS  gate lint rc=0
   PASS  gate test rc=0
   PASS  gate brain-audit rc=0
   PASS  gate eval rc=0
   ```

6. An `OK eval: N passed, N skipped, 0 failed, 0 unarmed` line (`evals.py:1163`).
7. `ship: OK — PR open, gates green` (`pr.py:166`) **or**
   `ship: OK — PR #N updated, gates green` (`pr.py:156`).
8. **The round stops at `ship:`. Merging is Ray's call, not this round's.** The
   drafted version required `land: OK — PR #N merged, main synced` (`pr.py:226`);
   that was removed deliberately. A goal loop that satisfies itself by merging is
   autonomously landing code on `main` — and right now CodeRabbit returns
   `pass  "Review rate limited"` on every PR, so nothing external is actually
   reviewing the diff. Requiring a merge would make "no review happened" a
   precondition of "done". The agent opens the PR and stops.
9. `Saved to graphify-out/memory/<file>.md` from `kb-remember`.
10. `Reflected N memories (N useful, N dead ends, N corrected) -> graphify-out/reflections/LESSONS.md`
    from `kb-reflect`.
11. A `kb-currency-check rc=0` line. **This one needs care:** the task prints nothing
    and exits 0 when there is no drift, so silence is indistinguishable from "never
    ran". The agent must echo the real exit status — redirect to a file and read the
    recorded `rc`, never a piped `| tail`, which returns tail's 0
    (`long-running-command-hangs.md` rule 3).

**Instead of 5–11, the round may satisfy:**

12. A `GOAL-BLOCKED:` line naming the blocker and at least two probes already tried.

**The Arm B floor — two discriminators, not zero.** Arm B ("cause NOT established")
is a legitimate landing, but without a floor it is satisfiable on turn 1 by simply
declaring the cause unknown. So Arm B additionally requires **at least two distinct
`REDACT-PROBE:` lines**, each naming its command and carrying that command's pasted
output. A discriminator that was never run is not a discriminator, and "I could not
find it" after no search is not a negative result — it is an unarmed probe
(`probes-need-a-control-arm.md`). The same floor applies to `GOAL-BLOCKED:`, which is
why it names two probes rather than none.

**A note on what this cannot prove.** Clauses 5–11 are text the agent emitted about
its own run. The evaluator cannot re-run them. That is the acknowledged residual risk
(§2) and the reason the strings are exact and externally-authored.

---

## 10. OUT OF SCOPE — the overflow valve

Anything below is a real decision that would otherwise eat the round
(`res-ceccarelli.md:744-768`). If a phase proves one is needed: **stop, write it into
the P7 handoff, do not silently expand scope.**

- Filing the `__MISE_DIFF` hardening request upstream. `mise-path-research.md:365`
  notes it "is not currently tracked as one" — worth doing, not this round.
- Porting anything to dotfiles (Posture 1).
- Any change to how `kb-ship`'s gate list or output strings are formed.
- Rebuilding the graph (`kb-build`) unless a `sources/**` input actually changed;
  it re-clones every pinned manifest and this round changes no corpus input.
- Regenerating derived views (`kb-artifacts`).
- Deleting the two stale local branches (`session-2026-07-27-d.md:65-68`) — verified
  safe, but housekeeping is not this round.

---

## 11. HAND-BACK — decisions that are Ray's

Neither of these may ever be reported as done by the agent.

1. **Secret rotation.** `session-2026-07-27-d.md:42-46`: decoding `__MISE_DIFF` in an
   earlier session surfaced live values (an AWS access key + secret, several API
   tokens) into a transcript. PR #49 stops the blob propagating *from now on*; "it
   cannot un-disclose what already leaked." If any are still live, only Ray can
   rotate them.
2. **CodeRabbit.** PRs #48/#49/#50 all returned `CodeRabbit  pass  "Review rate
   limited"` (`session-2026-07-27-d.md:49-54`). #49 was a security fix and got no
   external review. The choice between waiting out the limit and de-counting the check
   as evidence is a policy call.

The agent's obligation is to *surface* both, verbatim, as the `HANDBACK:` lines in §8
— and to keep them in the P7 handoff so being out of scope does not mean being lost.

---

## 12. GitHub repos touched

- [jdx/mise](https://github.com/jdx/mise) — the redaction engine under investigation;
  `src/redactions.rs` / `src/cli/run.rs` / `src/logger.rs` are P4's read targets, and
  the release-note and grep control arms in `mise-path-research.md` § Q4 came from it.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — cited only as
  this repo's worked example of a stale-open issue (#959) misread as current state.
