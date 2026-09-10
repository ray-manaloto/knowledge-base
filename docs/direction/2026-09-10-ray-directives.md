# Ray's directives — 2026-09-10

VERBATIM. This file is the standing brief a round is measured against; do not
paraphrase, and do not "tidy" the wording. Session `kb-20260910.000`.

**Why this file exists at all is itself a finding.** A loss audit at the end of
the round grepped `docs/`, `.claude/` and `python/` for *function hooks* and
found **2 hits, both false positives inside vendored `sources/**`** — control
arm, same command shape: `kb-recall-work` → 5 tracked files. Every directive
below had been acted on and **none was recorded anywhere tracked**. The round
would have ended with its own instructions surviving only in a transcript.

🔴 **Four of these arrived as queued-command attachments, not as message
content.** A review reading only message text plus `AskUserQuestion` answers
found **zero** of them. Both routes are needed; neither is complete alone. That
is now filed against the session-review skills, because a retrospective that
reads one route under-reports what was asked.

## 1. The complaint that started the round

> the output of the commands being run are not using the universal logger and
> the stdout/stderr is being silently dropped and i see a lot of warnings and
> errors that are not being handled
> and it is not following the modular skill(s) -> mise task(s) -> python library
> module(s)/function(s) requirement
>
> have a kb-codex-astra-advisor lane review and enforce following the requirement

**Scope, as the advisor established it.** All three parts are real. The logger
half is broad — **396 `print()` sites across 58 modules against 163 event calls
in 19**, with only `events.py` and `sinks.py` importing stdlib `logging` at all.
The dropped-stream half is far smaller than the complaint implied: **0 confirmed
false greens out of 87 spawn sites**; what is actually lost is the DIAGNOSTIC,
never the outcome. The chain half is real for recurring work, and the door is
`uv run python - <<PY`, which `check_first` allows.

The design is `.agent/kb/reports/agents/advisor-logging-and-chain-enforcement.md`
(501 lines): five enforcement mechanisms, T201 re-enabled with **no `--fix`**
(ruff's fix DELETES the statement), and the insight that outranks the rest —
**build the diagnostic escape route BEFORE the deny**, or the guard forbids a
thing with no replacement.

**The risk that decides it, in the advisor's words:** *the recommendation fails
if the universal boundary conflates logging with the program's output protocol.*
`hook_guard` writes a JSON `permissionDecision` to stdout and `kb-serve` speaks
MCP there. Zero prints and green gates are achievable while breaking both.

## 2. mise logging, and the fan-out

> have the adviser also research mise settings/environment variables for logging
> such as location and log level as that might help with how to direct
> stdout/stderr in addtion to using the universal logger
> there are a lot of features of mise we are not using that would improve our
> process
> so the adviser should plan how to fan out to other codex lanes w specialized
> subagents as what we were working on before to find all mise settings we should
> be using in addition to researching its github issues/prs/discussions and other
> github repos and other sources of how to use mise features and advanced features

**Read as ADDITIVE — and the decisive arm points the other way.** `MISE_LOG_FILE`
captures **zero bytes** of task output, even when a task exits rc 3; it records
mise's own log-crate records only. So it is neither substitute nor supplement for
the events/sinks migration.

What the sweep did find: **`MISE_SILENT=1` deletes a task's own stdout
wholesale**, inherited from any parent, with no trace — the complaint in §1
available as one environment variable. And **`MISE_TASK_CACHE` defaults to
`read-write` and READS**, so a task's result can be replayed and the task never
run. Wave 1 (three lanes) is done; wave 2 is planned and unspent.

## 3. GitHub as a source — the FOURTH time asked

> have codex lanes research all the results from this github query:
> https://github.com/search?q=CLAUDE_CODE_ENABLE_FUNCTION_HOOKS&type=code
> we need to start actually using github as a source of information on how to
> find examples

**Recorded twice before and never built:** `2026-08-26:62` and `2026-09-03:55`
carry the earlier asks, and a grep for `gh search` / `gh api … search` /
`GitHub as a source` across `.claude/` and `docs/direction/` returned **zero
files**. No rule, no step in `research-doc-sources.md`. This round is the one
that writes it.

**Measured while doing it, and it is why the rule needs a shape rather than a
reminder:** searching only the code index would have found **20% of the dedicated
projects and none of the issues** — 4 of 5 dedicated repos appeared in no code
result, and the two most valuable artifacts of the day were issues. GitHub's
legacy code tokenizer splits on `-` and `.`, so a bare `plugin-types` returns
**288,256** junk hits and quoting does not help; `filename:`/`path:` qualifiers
are what make a query discriminating.

## 4. Function hooks — adopt them

> we want to start using the claude feature of
> have the adviser fan out research to claude function hooks
> …
> it is fine if it is an expermiental feature and could change, we just need to
> adapt to the changes as it progresses

Plus, later: `have the adviser also review https://www.aitmpl.com/function-hooks/
regarding function hooks`.

**Scope:** this is an enforcement-architecture ruling, not a research request —
the mechanism this repo's guard stack is intended to move onto. Established:
the feature is real in `anthropics/claude-code`'s `mods/` folder, **five tiers**
(`prepend`/`user`/`append`/`builtin`/`core`) with `next.to()` typed to skip only
inward, and **unreleased at 2.1.267**.

🔴 **The fact that governs any adoption plan: a broken hook is SKIPPED, not
failed closed.** Seating in `prepend` is necessary and not sufficient — the hook
must catch-and-deny itself or a bug in it quietly opens the gate.

🔴 **And the one that would have bitten us:** `anthropics/claude-code#92533` —
registering *any* `tool.call` hook on Bash breaks every Bash call in a subagent
with `isolation: "worktree"`. Our guard stack is a `PreToolUse` matcher on
`Bash|Grep`; the obvious migration lands directly on it, and the failure would
present as our guards breaking.

## 5. File upstream, but only after diligence

> file the graphify issue
> only after due dilligence and we know the issue is not in our code
> have codex lanes research this and then file the upstream issues if necessary

**Followed in that order.** Not our invocation (no filter; `src/env.rs` reached
the extractor and produced 101 nodes with zero bindings), not our fork (diff
touches 10 files, `grep -ic extract` → 0), not configured away (no node-kind
knob), and reproduced on a **pristine PyPI `graphifyy==0.9.57`** in a clean venv.
Only then filed: **Graphify-Labs/graphify#3471**.

The general rule this sets: *ours first, upstream last, and the pristine
reproduction is what actually rules out everything of ours.*

## 6. Zero agent work, one command

> zero agent work / one command

**Scope:** when a task is a single command, run the command. Do not spend a lane
on it. Recorded because the round it was given to had reached for a subagent on
work a `grep` settles.

## 7. The session review that produced this file

> have codex lanes review this session to make sure nothing was lost and correct
> and in the task plan

Two lanes: a loss audit and a correctness/plan reconcile. Between them they found
a defect that had **already shipped** (`mise.lock` left at `antigravity-cli
1.1.25` while `mise.toml` moved to 1.2.0 — the round's own thesis, recurring one
commit after the gate built to catch it), a second lockfile orphan weeks old,
that **`kb-remember` never ran this round**, and that this file did not exist.

The reconcile lane's own headline edit was **refuted** — it recommended deleting
#728's chain row on the strength of a merged PR that cited the ticket, when
`kb-fork-rebase` does not exist and the work is genuinely unfinished. Its
diagnosis of its own error is worth keeping: *"I inferred done from the PR that
referenced it merged. I'd run exactly that artifact-with-control grep six times
elsewhere in the same report and skipped it on my own headline claim."*

## See also

- `docs/direction/2026-09-09-ray-directives.md` — the previous brief.
- `#726` — Phase V, which §2 and §3 both feed.
