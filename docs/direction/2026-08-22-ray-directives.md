# Ray's directives — 2026-08-22 (f) — VERBATIM

Written 2026-08-23 at `/clear-prep`, from the landing session `48d40647` (the one
that landed PR #459 and built the `record` verb on `corpus-gate-bundle-rebased`,
PR #463). Session model Fable 5, effort max; the fable-orchestrator flow was armed
(`implementation lane = codex`).

## On how we run commands — VERBATIM (filed as #461)

> add a github issue to fix how we run commands
> we should be ouputting to a log file with the ability to output into structured output as a secondary log file so that we can make it machine readable
> - we can add it to the list of items to aggregate/triage

Measured while filing: this is the structured half of **#350** (the 2026-08-18 P0
universal-logger directive); the JSONL sink already exists
(`kb_setup.sinks.stdout_sink(jsonl_path=…)`) but is opt-in behind `KB_EVENTS_JSONL`
at `cli.py:49` and covers only `kb_setup`'s own events. The sample that prompted it:
a `mise run kb-gates 2>&1 | tail -12` background run killed when its terminal closed
— all six gates' output gone with the pipe.

## On PR bots — VERBATIM (filed as #462)

> file a github issue also to handle repowise/coderabbit and any other pr bot's in place comment updates instead of checking for new comments so we actually read all their comments and action on them

Control-armed on PR #459: Repowise `created 23:41:34Z / updated 23:59:23Z`,
CodeRabbit `23:43:20Z / 23:59:28Z` — two re-verdicts on a new push, zero new
comments. `[code]smith` is Blacksmith's autofix upsell check (always `skipping`).

## On the round's sequencing (AskUserQuestion answers)

- Opening: *"Yes, land it"* — land `extraction-readiness-sweep` (PR #459) first.
- The record-verb fork (deferred on 08-22 to "the next session with the evidence"):
  *"Build the verb now, on this branch"* — its first real run is the eighth record,
  done by the tool. Evidence that decided it: the fresh plan moved exactly the two
  IDENTITY digests (plan manifest, execution config) and left both DECISION digests
  (advisories, exclusions) byte-identical — the same class as all seven hand
  re-records.
- After PR #463 lands: *"Re-scope the run issues, then START the deep extraction"*
  — close/re-scope #455 #456 #411 #457 #458 against what landed, confirm `verify`
  = authorized, then run `kb-graphify-semantic-corpus -- run` (26 chunks, cap $63)
  in a supervised session.
- On the run's configuration Ray asked, VERBATIM:

  > where are the details for option 1?
  > there is a new claude release that will require me to restart the claude terminal session after /clear:
  > - https://github.com/anthropics/claude-code/releases/tag/v2.1.241
  > - will require another claude resync

  Answered in-session: the recorded plan is `graphify-out/graphify-semantic-corpus/execution-config.json`
  (effort high, total cap $63, 26 chunks / 170 units, graphify 0.9.48 derived,
  claude 2.1.240); the live `claude` is already **2.1.241**, so the slice's frozen
  `_CURRENT_CLAUDE_VERSION = "2.1.240"` + executable digest will refuse the run's
  preflight until the claude resync advances them — which moves
  `semantic_slice_sha256`, so the ninth record is one `record --accept` by the tool.
  Assumption recorded: the run keeps effort high / cap $63 unless Ray says otherwise.

## On clear-prep — the answer to the 73.5% context offer

> Yes — /clear-prep now, land #463 next session

## What this round measured that bears on the brief

- `premise-verifier` ran FOUR rounds on one spec and each found a real, load-bearing
  gap (the planner digests its own file; a plan dir must hold exactly six files;
  ruff SLF001 on private names; `encode_canonical` sorts keys). The spec that
  reached codex was the fifth revision.
- hk's `typos --write-changes` commit hook rewrote a short commit id inside the
  authorization ledger (the #413 class) — fixed by full-length hashes and a
  `proseExclude` entry for the ledger.
- The record tests seeded their authority from the REAL recorded authority and
  flipped to "nothing to record" the moment the first real accept landed — a
  fixture that depended on repo state.
- `graphify_semantic_corpus_run.py` is digested into every plan (`runner_sha256`):
  even a message-wording edit there is a re-authorization.

## ADDENDUM — the 2026-08-23 landing session — VERBATIM

Written 2026-08-23 at `/clear-prep` by the session that landed PR #463 (Fable 5,
effort max; `implementation lane = codex`, `codex effort = xhigh` from that PR on).

### On the unreceipted commit on top of PR #463

`/kb-resume` found HEAD `d85f2835…` (the one-line `fable-orchestrator: codex effort =
xhigh` in `.claude/CLAUDE.md`) local-only and unreceipted above the PR head. Asked how
to land, Ray, VERBATIM:

> i made that change to make change to 'fable-orchestrator: codex effort = xhigh'
> can we just do a quick git push and land since that change shouldn't affect actual code or changes we were working on

Done as a kb-review §4 fix-round (no new lane round; the gate would have refused a
bare push + `kb-land`): report at the new SHA, receipt, `kb-ship`, bots read by
body, 2 real CodeRabbit items fixed in `f0659e51…` (second fix-round), `kb-land`.
**#464** carries the two deferred items.

### On how every landing/resync session must END — VERBATIM (rejecting the first plan)

> automatically run /clear-prep with the session-review workflow as step 8
> - the next session will work on the Claude resync 2.1.240 → 2.1.241
>   - and automaically [sic] run /clear-prep again with the session-review workflow after that

Encoded: a session does not end on `kb-land`; it ends on `clear-prep` invoked WITH
`kb-session-select -- --current` → `Workflow session-review {output:'handoff'}` →
`kb-handoff-check`, then the `/clear` question. The same for the resync session.

### On the resync session's scope (AskUserQuestion, clear-prep step 0)

Asked whether session N+1 stops after the resync lands or also re-scopes #455–#458
and starts the deep extraction: *"Resync only, then clear-prep (Recommended)"*. So:
N+1 = slice constants (`_CURRENT_CLAUDE_*`, re-hash the installed `claude`, re-check
the `--help` digest) + `sources/claude-code.manifest` + `currency.toml
[tool.claude-code]` + the #464 comment, ninth `record --accept` by tool, `verify`
authorized, review/ship/land, `/clear-prep` + session-review. N+2 = re-scope #455
#456 #411 #457 #458, then `kb-graphify-semantic-corpus -- run` (26 chunks, cap $63,
effort high), supervised.

### On the review's CONFIRMED P1 and on the review itself (AskUserQuestion, after the session-review workflow ran)

The session-review workflow's P1: `verify` says `execution_authorized` at claude
2.1.241 against a plan recorded at 2.1.240 — the run's preflight checks the graphify
half only, the Claude compare is post-hoc per chunk, so a run would spend the cap
staging 26/26 failed. Asked whether the resync session also closes that window:
*"Yes — close it in the resync (Recommended)"*. Encoded: the resync makes the run's
preflight compare the LIVE claude identity against the plan's and refuse before any
spend; both modules are digested, so it is the same single re-record.

Asked to `/clear`, Ray instead asked, VERBATIM:

> what did we do w the results of the session-review workflow?
> what actions where taken? did it do any self-improvement to this project?

Answered honestly: consumed, not applied — the handoff was checked, one composer
claim refuted (stale remote-tracking refs), the P1 turned into the question above,
memories written, lane reports copied to a dated dir; **no repo change from the
review until that question**. Then applied the cheap CONFIRMED items before the
clear: the `AGENTS.md` contradiction (`md-size-budgets.md:81`, `md_budget.py:123`),
the stale 499 MB figure in `CLAUDE.md`, and a dated `reportDir` in the
kb-session-review invoke snippet (#431's collision). The lesson is the skill's own
§5 — the apply half is the half that gets skipped — and the standing brief is now:
**a session-review run ends with its CONFIRMED findings applied or filed, named one
by one, before the `/clear` question is asked.**
