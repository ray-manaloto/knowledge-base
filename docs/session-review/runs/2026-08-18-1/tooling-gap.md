# tooling-gap — iteration 1 findings

Scope: session `52f5798a-5d4b-43f2-b534-8bc05f903750` (the session that shipped
f772f5eb and PRs #337/#338/#339, ~4.5MB, 299 Bash tool_use calls, ends
2026-08-18T08:07:48Z) plus this review session `f1d1c0cf` (78 Bash calls so far).
Bash commands extracted via `jq` into a scratch file, never by reading the
`.jsonl` into context.

Control arm run first: `mise run kb-query -- "session review workflow"` (graph
read, satisfies the graph-first guard) — TRUNCATED at 53/349 nodes, all Rust/TS
symbols from the codex/graphify AST corpus, none relevant to this repo's own
python. Confirms the aggregate graph is dominated by vendored-repo AST, as the
root `CLAUDE.md` already documents (`--prose`/`--idf` exist for exactly this
reason) — not a new finding, just the control arm for why the rest of this
report greps the transcript instead of querying the graph for repo-local shape.

---

## Finding 1 — the cold-lane (`agy`) invocation is hand-typed every single time; no task or module owns it

**Evidence.** Extracted every Bash command containing `agy --model` /
`agy -` from session 52f5798a:

```
grep -n "agy --model\|agy -" bash_cmds_52f5798a.txt
```

8 distinct FULL invocations across the session (lines 6, 7, 11, 13, 66, 211,
332, 1129, 1457, 1769 — 10 lines matched, 2 are `--help`/`--version` probes),
each hand-constructing:

```
mise exec -- agy --model gemini-3.7-flash-high --output-format text --mode plan \
  --dangerously-skip-permissions --print-timeout <20m|25m|30m|40m> \
  --print "$(cat $SP/<name>-prompt.txt)" > $SP/<name>-report.md 2>&1; echo "rc=$?"; wc -l $SP/<name>-report.md
```

The `--print-timeout` value was re-picked ad hoc each time (20m, 30m, 40m,
30m, 30m, 25m — no stated rule for which). The scratch-file naming
(`$SP/<name>-prompt.txt` / `$SP/<name>-report.md`) was hand-invented per call
site too.

**Control arm — is this already wrapped anywhere?**
- `grep -rn "agy" python/src/kb_setup/*.py mise.toml` → only `eval_cases.py:44`
  (`DECLARED_LANES`, a tuple of lane names, not an invoker) and mise.toml's own
  pin-note prose about the `agy` binary shadow. **Zero invocation code.**
- `grep -n "agy\|mise exec" .claude/skills/kb-review/SKILL.md` → **zero hits**.
  The skill that owns "run the cold lane" does not even name the CLI.
- `grep -n "agy" .claude/workflows/*.js` → zero (kb-tool-review.js mentions
  `antigravity` only in a comment about not writing a third CLI).
- `mise.toml` tasks list (`grep -n '^\[tasks\.' mise.toml`) has no
  `kb-cold-review` / `kb-lane-run` / anything agy-shaped among its 60+ tasks.

So the control is armed both ways: the CLI-invocation shape recurs 8+ times in
one session, and a repo-wide search across the three places such a wrapper
would live (`kb_setup`, the skill, the workflow) finds nothing. This is not "a
task already does this" — it's a genuine gap.

**Why it's expensive as hand-work, not just untidy:**
1. The known gotcha "`--mode plan` blocks a lane's incremental report write, so
   a watchdog kill loses everything" (recorded in the handoff and in memory
   `ray-directive-2026-08-16...`) is a fact about the FLAGS, and every hand
   invocation re-risks it rather than a wrapper defending against it once.
2. `mise.toml:116-127` documents a live PATH-shadow hazard: a hand-installed
   `~/.local/bin/agy` (1.1.2) can shadow the mise-pinned shim silently. A
   wrapper can assert `agy --version` matches the pin before every run; a
   hand-typed command never does, and none of the 8 calls in this session did
   either.
3. The model/effort ("gemini-3.7-flash-high") is a standing Ray pin recorded
   only in prose (memory + the handoff). A wrapper is where a pin like that
   actually gets enforced instead of re-typed from memory.

**Which layer is earned:** a `kb_setup.cold_lane` module + a `kb-cold-review`
mise task, called as `mise run kb-cold-review -- <prompt-file> [--timeout 30m]`.
It should (a) verify `agy --version` against the pin before running, (b) fix
`--output-format text --mode plan --dangerously-skip-permissions`, (c) write
`<slug>-report.md` under the scratchpad with a name derived from the prompt
file rather than hand-invented, (d) print `rc=` and line-count the same way
every time so downstream parsing is uniform, (e) carry the `--mode plan`
gotcha as a code comment so it cannot be silently "fixed" into losing
incremental writes again. This is a mise task wrapping a kb_setup module, not
a skill — the skill (`kb-review`) should call the task rather than the raw
binary, closing the doc gap noted above in the same change.

**Cost estimate:** 8 hand-invocations this session alone, each ~150-200 chars
of hand-typed flags a human/agent must get exactly right; one wrong flag
(`--mode plan` vs. an incremental-write mode) has already cost a full lane's
output once this round (item 8 in the handoff's "things that will bite you").

---

## Finding 2 — bulk source-file surgery via `uv run python - <<'PY'` heredocs recurs 16+ times; Edit tool is available and was the documented right answer

**Evidence.**
```
grep -c "uv run python - <<" bash_cmds_52f5798a.txt   # 20
```
Sampled bodies (lines 836-960 of the extracted file) show these heredocs doing
`pathlib.Path(...).read_text()` → `str.index`/`str.replace`/slice surgery →
`.write_text()` on `python/src/kb_setup/graphify_semantic_corpus.py`,
`tests/test_graphify_semantic_corpus.py`,
`.agent/kb/arms/corpus-chunk1-findings.toml`, and
`python/src/kb_setup/graphify_semantic_corpus_authority.py` — i.e. exactly the
job the `Edit` tool exists for (`old_string`/`new_string` replacement), done
instead with a throwaway python script per call site.

**This is a KNOWN lesson, not a new one** — user memory already carries
`bulk-text-edits-belong-in-the-edit-tool.md` from a prior round, and this
session's own handoff records the session-reflect output calling the same
shape a "false positive of the mutation-harness detector" while conceding "the
underlying habit is real." **What's new here:** the lesson is recorded but
nothing enforces it, and the habit did not shrink — it happened 20 times in
this ONE session, the same session that is supposed to be the one improving
this repo's own tooling.

**Control arm on "is there already a guard for this":**
`kb_setup.hook_guard` and `kb_setup.check_first` deny raw `graphify`/`ruff`/`ty`
invocations at the command position, but neither pattern-matches
`python - <<` / `python -c` heredocs used for file surgery — confirmed by
reading the redirect table in `mise-tasks-only.md` (`.claude/rules/`) which
lists graphify subcommands and gate tools, nothing about inline python. So this
is a real enforcement gap, not a duplicate of an existing guard.

**Which layer is earned — sceptical case:** NOT a mise task (there's no single
recurring "job" here, every heredoc does something different). The closest
existing mechanism is `mise run kb-distill`, whose whole job is "hand-rolled
script written twice → propose a skill/task/module triple" (#219). But
`kb-distill` is a detector over what's already on disk / in a chunk's history —
it is not positioned to catch "used python heredoc instead of Edit" as a
class, because the 20 heredocs are 20 *different* scripts, not one script run
20 times. The earned layer is a **PreToolUse guard addition** in
`kb_setup.hook_guard` (same family as `check_first`) that fires when a Bash
command's first token is `uv run python` (or bare `python -c`) AND the
heredoc/`-c` body contains `.read_text()`/`.write_text()`/`str.replace(` on a
path under version control — i.e. detects "this is doing what Edit does" and
denies with a pointer to the Edit tool. This is narrower than banning python
heredocs outright (some of the 20 calls, e.g. the sha256-diff comparisons
below, are legitimate one-off computation, not file surgery) — the guard must
discriminate READ+COMPUTE from READ+MUTATE+WRITE, which is checkable
syntactically (presence of `.write_text(` or `open(..., "w")` in the same
heredoc as a `.read_text()`).

---

## Finding 3 — ad hoc sha256/diff comparison of `execution-config.json` recurs and IS the right shape, but has no artifact — worth noting, not automating

**Evidence.** `grep -c "sha256" bash_cmds_52f5798a.txt` → 30 hits, mostly
inline python computing `hashlib.sha256(path.read_bytes()).hexdigest()` to
compare two `execution-config.json` snapshots after a re-plan (lines ~955-966
sampled). This is genuinely one-off diagnostic work tied to the specific
"does editing X un-authorise the corpus plan" question this session was
chasing (already in `CIRCLES_ALREADY_DIAGNOSED` — the plan-authority digest
covers five files including the planner). **Not proposing automation here**:
this is COMPUTE, not the write-surgery Finding 2 targets, and it was asked and
answered inside one investigation rather than repeated across many. Recording
it only so the next round doesn't re-count it as a Finding-2 instance.

---

## Finding 4 — the graphify-version-bump procedure is documented as FOUR coupled manual steps with no task chaining them

**Evidence.** The handoff itself states it: *"The graphify bump is four
coupled places and one is EVIDENCE… Order: bump → re-clone
`sources/graphify.manifest` → re-run the slice → re-plan → re-record
`AUTHORITY_JSON` → `kb-build`. It is its own round."* — and separately, user
memory `a-revision-is-restated-in-twelve-places.md` / `the-graphify-bump-is-
not-a-one-line-change.md` record that a prior bump (0.9.44→0.9.45) touched the
revision in **thirteen** places by hand.

**Control arm — does a task already chain this?**
```
grep -n "kb-graphify-contract\|kb-graphify-baseline\|kb-graphify-semantic-slice\|kb-graphify-semantic-corpus\b" mise.toml
```
→ each step (`kb-graphify-contract`, `kb-graphify-semantic-slice`,
`kb-graphify-semantic-corpus`) exists as its OWN task, confirming the pieces
are already tasked. What's missing is a **composite** `kb-graphify-bump` task
that runs them in the documented order and refuses to proceed past a failing
step — currently a human/agent has to remember the 4-6 step order from prose
(the handoff, two memory notes) every time a bump happens, and this repo has
already gotten the count of "how many places" wrong across notes at least
once (13 vs 4 vs "one field of 43 moved" — three different numbers appear in
the transcript for what should be one authoritative fact).

**Which layer is earned:** a `kb-graphify-bump` mise task (python module
`kb_setup.graphify_bump`) that: (1) edits the pin in `pyproject.toml`, (2)
re-clones the manifest, (3) re-runs the slice, (4) re-plans, (5) re-records
`AUTHORITY_JSON` from the ACTUAL new digests (never hand-typed), (6) runs
`kb-build`, stopping and reporting at the first step whose output disagrees
with the previous step's assumption. This is squarely inside
`tool-currency-and-native-first.md`'s remit and would retire the
"remember the order from three different docs" failure mode the transcript
exhibits in miniature (see the three-different-counts note above).
**Caveat: this is a bigger build than Findings 1-2** — it touches the same
corpus-planning surface the handoff says is mid-circle (`CIRCLES_ALREADY_DIAGNOSED`),
so it should wait until the corpus-run rescoping settles, not be built into a
moving target.

---

## Finding 5 — NOT a finding: `kb-currency-check` was used correctly

Checked because it's the highest-stakes recurring check this round (Ray's
directive #10 gates all other work on it). `grep -n "kb-currency-check\|kb-
currency\b" bash_cmds_52f5798a.txt` shows exactly one substantive invocation
(line 1131), used through the task as intended, output quoted verbatim into
the directive doc. No hand-rolled replacement found. Recorded so this lane
does not get re-asked to check it.

---

## COVERAGE

**Reached and analysed:** the full Bash-command shape of session
`52f5798a` (299 tool_use calls, all extracted via `jq`, grepped for
heredoc/agy/sha256/currency/git-log/gh/kb-* patterns); cross-checked each
candidate against `kb_setup/*.py`, `mise.toml`'s task list, `.claude/skills/
kb-review/SKILL.md`, and `.claude/workflows/*.js` to confirm no existing task
already covers it (control-armed per `probes-need-a-control-arm.md` — searched
all three plausible homes, not just one). One graph query run first
(graph-first guard satisfied) and reported as inconclusive-by-corpus-mix
rather than silently skipped.

**Opened but not finished analysing:** this review session's OWN transcript
(`f1d1c0cf`) — swept the same `jq` extraction against it (now ~90 Bash calls,
still being written, so this is a partial count): 0 `agy` hand-invocations, 1
heredoc-python call (not yet inspected for the read/write-surgery shape
Finding 2 targets) among MY OWN commands. Sibling agents (`main`,
`circles-breaker`, `plan-advisor`, `plan-auditor`, `workflow-scoper`) run as
separate in-process subagents and did not write to this `.jsonl` — I could not
grep their Bash calls from here, so Finding 1/2 recurrence among them is
UNCHECKED, not "checked, found none." `kb-extract.js` / `kb-tool-review.js`
tiering defects were flagged as already-known (per the task's
`KNOWN_GAPS_NOT_FINDINGS`) and intentionally not re-derived here.

**Never reached:** the 3 small stub transcripts (`7604bd97`, `d1e6ab78`, and
the `02006b75` 2.4KB file) — sized as stubs per the task's own note, not opened.
The `.agent/telemetry/` request/response pairs (3,701 files / 1.6GB per the
task's `TELEMETRY` note) were not queried for cost/model attribution — out of
this lane's scope (tooling-gap, not cost-audit) and explicitly warned against
reading into context. Did not examine `python/src/kb_setup/` files beyond
`review.py`, `eval_cases.py`, and `hook_guard`/`check_first` (by rule-file
description, not full source read) for other candidate gaps — a second pass
naming specific modules (e.g. `graphify_semantic_corpus.py`,
`graphify_semantic_corpus_authority.py`) by their actual current line count
would likely surface more Finding-4-shaped detail.
