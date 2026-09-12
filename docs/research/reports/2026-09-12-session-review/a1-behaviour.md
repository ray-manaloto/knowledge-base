# Lane a1-behaviour — session behaviour review

Commit examined: `c1d8afb8` (branch `feat/754-plugin-types-contract`)
Scope: 5 sessions, 2026-09-11T20:39Z -> 2026-09-12T19:27Z, in
`/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/`

## Session chain (control-armed: confirmed via `custom-title` + boundary timestamps)

| # | session id | title | window (UTC) | lines | bytes |
|---|---|---|---|---|---|
| 1 | `4c634319-…` | kb-20260911.002 | 20:39:29 -> 00:38:16 | 3115 | 6,055,927 |
| 2 | `36755013-…` | kb-20260911.003 | 00:41:02 -> 04:28:34 | 2861 | 5,056,115 |
| 3 | `0181d8d8-…` | kb-20260911.003 (cont.) | 04:28:37 -> 11:56:30 | 2992 | 5,504,873 |
| 4 | `8d789cf9-…` | kb-20260911.004 | 11:56:31 -> 13:58:31 | 1103 | 2,554,123 |
| 5 | `3b921834-…` | kb-20260911.004 (cont.) | 13:58:32 -> 19:27:09 | 4312 | 7,978,235 | <- TARGET

Sessions 2->3 and 4->5 share the SAME `custom-title`, and each pair's boundary
timestamp is contiguous to the second (e.g. session 3 starts 04:28:37, 3s after
session 2's last record at 04:28:34) — this is a `/clear`-continuation chain
inside one logical "round" per title, not five independent sessions.

## The three ~24KB "stub" files: CONFIRMED as `/clear` markers, not bridge/fork stubs

Refuting the task brief's guess of "bridge or fork stubs" — read their `user`
records directly:

- `e4b70cf6-…` (kb-20260911.002) — its only `user` record is the `/clear`
  command itself, timestamped **2026-09-12T00:38:37Z**, i.e. 2s before
  session 1 (`4c634319`)'s last record (00:38:16) and 2m25s before session 2
  (`36755013`) starts (00:41:02). This is the /clear that ended session 1.
- `15c81024-…` (kb-20260911.001) — `/clear` at **2026-09-11T20:37:53Z**, 1m36s
  BEFORE session 1 starts (20:39:29). This is the /clear that STARTED the
  kb-20260911.002 round (ended a still-earlier, unlisted `.001` session).
- `482eaedb-…` (kb-20260911.004) — `/clear` at **2026-09-12T19:27:51Z**, 42s
  after session 5 (`3b921834`, the target)'s last record (19:27:09.699Z).
  **This is the `/clear` that ended the 100%-full session.**

So the target session did not simply vanish mid-turn — it ran to a final
`/clear` 42 seconds after its last logged record. This bounds where to look
for "did not properly run": the failure is IN the 5h29m of session 5's own
content, not in how it ended.

Each stub also carries `bridgeSessionId`/`ownerAccountUuid` fields — these are
real fields Claude Code writes for EVERY session (cross-device sync
plumbing), not evidence of a "bridge" device. Arm: session 1 (`4c634319`,
6MB, clearly a full local session) carries the identical `bridge-session`
record shape. So `bridge-session` presence does not distinguish stub from
real session; only record-type composition and `/clear` content do.

## GitHub repos touched

_None yet — will append if any surface during analysis._

## 1. Context-exhaustion cause — the target session (`3b921834`, kb-20260911.004 cont.)

**Direct evidence of the crash mechanism**, read from the transcript's own final records:

- Last coherent assistant text (19:26:48.528Z): *"**0 broken.** ... Committing the
  remainder:"* — the session was finishing a self-audit of its own handoff file
  (`.agent/plans/session-2026-09-12-f.md`, `kb-setup handoff-check`, "Nine broken
  ... Fixing all of them").
- 19:27:05.736Z: runs `git commit -F -` with the message that became
  `c1d8afb8` — **this commit landed** (`git log` confirms
  `c1d8afb8 2026-09-12T14:27:06-05:00`, i.e. 19:27:06 UTC, matching to the second).
- 19:27:09.678Z: the commit's tool_result returns successfully.
- **19:27:09.699Z, the very next record: `{"type":"assistant","content":["Prompt
  is too long"]}`.** No further tool calls, no summary, no handoff message to
  the user. The transcript ends there. 42 seconds later a `/clear` was issued
  (stub session `482eaedb-…`, confirmed by its `/clear` command timestamp
  19:27:51Z).

**So the crash did not lose in-flight code work** — the last commit landed
clean and a handoff file (`.agent/plans/session-2026-09-12-f.md`, mtime 14:26
local) already existed on disk. What was lost is the **turn where the session
would have told the user what happened and what's next** — the model's own
next completion failed outright on prompt size, with no fallback summary. This
is consistent with Ray's report ("filled to 100% and did not properly run"):
work landed, but the session could not close itself out, leaving Ray to start
a fresh session (`kb-20260912.000` / `105dc66e-…`, currently orchestrating
this very review) to work out what state things were left in via 7 rounds of
manual "grilling" (27 Q&A, `docs/artifacts/session-review-3b921834-grill.html`,
`docs/dag/2026-09-12-session-review-round.toml` — both written by
`105dc66e-…` AFTER `3b921834` ended, timestamps 15:09/15:22 local vs the
crash at 14:27 local — NOT part of the crashed session, corrected after an
initial timezone mix-up in this analysis: UTC transcript timestamps vs local
(CDT, -05:00) file mtimes).

### What consumed the context over 5h29m (13:58 -> 19:27 UTC)

Record-type byte breakdown of the 7,978,235-byte transcript:

| type | records | bytes | share |
|---|---|---|---|
| assistant | 965 | 3,454,580 | 43% |
| attachment (mostly system-reminders + hook context) | 1,530 | 2,237,297 | 28% |
| user (tool_results) | 476 | 1,954,695 | 25% |
| everything else (queue-operation, bridge-session, mode, etc.) | ~1,341 | ~331,663 | 4% |

Tool-call composition (965 assistant turns): **287 Bash**, 67 SendUserMessage,
24 AskUserQuestion, 10 SendMessage (to named background lanes), **10 Agent**
(all `kb-codex-astra-advisor` dispatches), 4 ListAgents, 7 Write, 6 Edit.

No single tool result dominates (`user` records: largest is 166,769 bytes,
next 52,881 — not a smoking gun by itself). The `attachment` layer is mostly
the **`ELI5 Visual` output-style reminder repeated 441 times** (59.5KB) and the
**graph-first hook's "MANDATORY: graphify-out/graph.json exists" reminder,
220 times** (measured across the WHOLE transcript incl. quoted rule text —
the Bash-tool-scoped subset is ~110-130; both readings are noted because this
reminder is ambient harness behaviour, attached to nearly every Bash call
regardless of prior compliance, not a sign this session specifically ignored
graph-first). These are `system-reminder` overhead the harness attaches every
turn, not something the session did wrong — but they are real, cumulative
bytes: at ~130-400 bytes each, hundreds of repeats add up to hundreds of KB
over a 5.5-hour session with 287 Bash calls.

**The real driver is turn COUNT, not any single oversized payload**: 965
assistant turns average ~3.6KB each (mostly `thinking` blocks + prose +
tool_use JSON), and 287 Bash round-trips each carry ~2-3 attachment/hook
records. A session this long, doing this many small iterative steps, fills a
context window through volume, not through one bloated read.

### The single biggest identifiable cost: 10 background `kb-codex-astra-advisor`
dispatches, only some concluded before the crash

`ListAgents`, called 4 times in this session, shows the state of the team
just before the crash (a call late in the session — full roster below).
**22 teammates total** were tracked, most `idle` after finishing, but at the
time of that last check **three were still `running`**:
`session-audit-lead` (started 1h ago), `scratch-isolation-review` (39m ago),
`claudex-loop-mining` (36m ago) — all `kb-codex-astra-advisor`. Given the
session crashed shortly after, **it is plausible these three lanes' reports
were never read into this session** before it ended (see §4, Abandoned work).

Ten fresh `kb-codex-astra-advisor` dispatches happened IN THIS SESSION ALONE
(`Re-review function-hooks sources`, `Lead GitHub+graphify extraction
research`, `Synthesize function-hooks research`, `Own graphify fork currency
and extraction`, `Audit everything done this session`, `Research
graphify-first as a function hook`, `Research agentsview for session mining`,
`Optimize advisor agents for durability`, `Review scratchpad isolation fix`,
`Ingest and mine claudex-loop`) — a very wide breadth of concurrent research
threads for one 5.5h session, on top of ~12 already-idle lanes from earlier in
the day. Each report that DID return had to be read back into this session's
context to be acted on (the four `SendMessage` calls broadcasting "kb-recall-work
FIRST — now a precondition, pass to sub-lanes" to `graph-first-hook-research`,
`session-audit-lead`, `agentsview-research`, `advisor-durability` show the
session actively managing this fleet mid-flight, including a **process
defect**: the "run kb-recall-work first" precondition was not established at
dispatch time and had to be retrofitted to 4 already-running lanes one at a
time, each a separate SendMessage).

## 2. Circles (repeated probes/questions across sessions)

**The dominant circle, spanning ALL FIVE sessions**: reverse-engineering the
Claude Code function-hook contract by reading `.claude/mods/kb-settings-guard/hooks/register.ts`
and `claude-code.d.ts`, over and over, with a regenerated `mise -p /plugin-types`
`.d.ts` compared each time. Raw mention counts (`grep -o <term> <file> | wc -l`,
i.e. counting every occurrence across the whole transcript, arms both directions
against a term absent early and present by session 5):

| session | `register.ts` | `claude-code.d.ts` | `plugin-types` invocations | `mod_runtime.py` |
|---|---|---|---|---|
| 1 (`4c634319`) | 157 | 96 | 25 | 0 |
| 2 (`36755013`) | 126 | 2 | 3 | 0 |
| 3 (`0181d8d8`) | 523 | 48 | 26 | 0 |
| 4 (`8d789cf9`) | 72 | 39 | **411** | 0 |
| 5 (`3b921834`, target) | 57 | 44 | 1 | 60 |

**`mod_runtime.py` — the module that finally PINS the contract — does not
exist until session 5**, i.e. the actual shippable artifact (landed as
`4cdd8bfb feat(754): pin the function-hook runtime contract with a live probe`,
09:50 local, inside session 3's successor) was preceded by roughly **935**
raw mentions of `register.ts` and **229** of `claude-code.d.ts` across four
earlier sessions of investigation. Session 5's own 287 Bash calls include at
least 6 distinct heredoc rewrites of the SAME regex-based static-analysis
approach to `register.ts` (progressively fixing a `\b` word-boundary bug that
can't match before `$`, then a dataflow/rooted-binding pass, then a fixpoint
pass) — visible directly in the command bodies (see raw transcript,
`toolu_*` tool_use blocks around 19:0x-19:1x UTC) — this is a real, evidenced
circle: the same static-analysis idea attempted five-plus times with
incremental fixes, in one session, on top of four prior sessions already
spent orienting on the same two files.

Session 4's **411** separate invocations touching `plugin-types` in a session
lasting only 2h02m (11:56-13:58 UTC) is the single most concentrated circle
in the whole day — consistent with this being the exact mechanism named in
this repo's own committed memory (`kb-mod-runtime-check`, #754 G01): "it runs
`/plugin-types` on the INSTALLED `claude`" as a live probe, repeated many
times while iterating the contract-derivation regex against real output.

**What finally settled it**: `mod_runtime.py`'s `required_runtime_tokens()` +
a live `/plugin-types` regeneration + reachability check, landed in `4cdd8bfb`,
then hardened in `c33a1fb5` ("the gate was green only because of WHERE it
ran") after a P1 was found in the FIX itself (matches the standing lesson
already in `MEMORY.md`: [the fix is where the defect lives](the-fix-is-where-the-defect-lives-measured-twice.md)).

## GitHub repos touched

_None — all analysis was of local transcript files and repo working-tree state,
no GitHub reads performed in this lane._

## 3. Contradicted directives, as a RATE (per this repo's own convention)

Measured over the union of all 5 sessions' `Bash` tool_use commands
(`jq -r '.input.command'` on every `tool_use` named `Bash`; 1,049 Bash
calls total: 230+221+214+97+287). Control arm noted per row.

| Rule | Opportunities (denominator) | Violations | Rate |
|---|---|---|---|
| `clean-git-state.md` / `do-not.md` #: no blanket `git add -A`/`.`/`:/ ` | 1,049 Bash calls | **0** | 0/1049. One `git add -A <named-files>` match is a scoped add, not a blanket one (confirmed by reading the full command, session 1 line 1473); a second match is the session's OWN prose *describing* the guard correctly denying an add elsewhere, not a command. |
| `zero-bash-logic.md` / hook_guard: bare `python`/`python3` instead of `uv run` | 1,049 Bash calls | 2 | 2/1049 (0.2%), both in session 2/3, single-line inline probes (`python3 -c "…"`, `python3 - <<'PY'`). **Not independently confirmed denied or allowed** — UNVERIFIED whether the hook caught these; the transcript's `tool_result` for both was not individually checked in this pass. |
| `mise-tasks-only.md` §2a `check_first`: hand-run `ruff check`/`ty check` outside `mise run kb-check` | 1,049 Bash calls | **0** confirmed via tool_use-only search | An earlier whole-file `grep` in this analysis found "4" hits of `ruff check` in **every** session identically — that was a broken probe (see below), not a finding. |
| `mise-tasks-only.md`: raw `graphify <subcommand>` at command position | 1,049 Bash calls | 0 (measured on a narrow pattern `"command":"graphify (install\|extract\|merge\|update\|cluster\|label)`) | 0/1049, narrow pattern only — not a full tokenised re-check of every command. |

**One probe in this lane's own work failed its own rule** (worth naming
per `probes-need-a-control-arm.md`): grepping the whole-file text of each
transcript for `ruff check` returned exactly **"4"** in all five sessions —
identical across sessions of wildly different length and content, which is
the tell of a broken instrument. The match is this repo's own
`.claude/rules/mise-tasks-only.md` and `long-running-command-hangs.md` text
(quoted verbatim as system context in every session), not an actual command.
Re-run scoped to `tool_use.input.command` only (the correct instrument) found
zero hand-run `ruff check`/`ty check` invocations. **Recorded here because
the failure mode is exactly what `change-the-route.md` describes**: the wrong
route (whole-transcript grep) produced a confident, uniform, wrong number.

**Overall picture: near-zero measured rule violations across ~1,049 Bash
calls and 5 sessions.** This repo's PreToolUse guard stack (`hook_guard`,
`check_first`, `graph_first`, `stage_explicitly`) appears to be doing its job
— the near-total absence of blanket-add and hand-chained-gate patterns is
consistent with guards that deny before the pattern can appear in a
successful command, not merely with good behaviour. This lane did not verify
DENY-vs-ALLOW on each of the 2 bare-python hits; flagged as the one open
compliance question worth a follow-up grep on `tool_result.content` for those
two specific `tool_use_id`s.

## 4. Abandoned work

1. **Three `kb-codex-astra-advisor` lanes were still `running` when the
   target session's last `ListAgents` check ran, shortly before the crash**:
   `session-audit-lead`, `scratch-isolation-review`, `claudex-loop-mining`
   (see §1). Whether their reports were ever read by ANY session is
   **UNVERIFIED in this pass** — it would require checking each lane's own
   report file / transcript for a completion timestamp against
   19:27:09Z and confirming a later session (`105dc66e`/`kb-20260912.000`)
   consumed it. Flagged as the single highest-value follow-up for another
   lane or a fast recheck.
2. **`docs/artifacts/session-review-3b921834-grill.html` and
   `docs/dag/2026-09-12-session-review-round.toml` are UNCOMMITTED** (both
   shown untracked in this round's `git status`) despite being the decision
   record for the ENTIRE round now in flight (this very S8 review is `docs/dag/...toml`'s
   own `unit id = "S8"`). If this round does not commit them, the next
   `/clear` loses the DAG that is currently the only committed-to-disk record
   of Ray's 7 rounds / 27 answers of `/grilling`.
3. **22 background teammates accumulated over the day**, most `idle` for
   many hours by the time of the last check (`g00-fix-advisor` idle 17h,
   `g00-fix-impl` idle 17h, etc.) — several clearly finished lanes from
   earlier tickets (#755, #754) that were never explicitly torn down or their
   idle state confirmed consumed. Not itself a defect, but it is unclosed
   loop count worth naming: a 22-agent roster is a lot of state for one human
   to reason about when a session crashes without a summary.

## 5. What a rule or gate could have prevented, ranked by cost

1. **Highest cost — no rule requires a periodic self-checkpoint against
   `mise run kb-context` inside a long autonomous run.** `request-clear-prep-at-20-percent-context.md`
   (per MEMORY.md) exists as a standing call, but the target session's own
   commit body shows it was doing a LATE, large self-audit (finding "Nine
   broken" handoff references, re-deriving an inherited number, closing the
   corpus loop) at 19:26 UTC — i.e. in the last 60 seconds before running out
   of room entirely, not with headroom to spare. Had a hard measured
   `kb-context` check forced a `/clear-prep` earlier (e.g. at 85-90% rather
   than "20% left" being read only as a soft trigger), the session's own
   handoff and final commit would likely have landed with room left over to
   also emit a short summary to Ray, instead of failing on the very next
   completion. Cost: an entire extra session (`kb-20260912.000`) and ~90
   minutes of manual "grilling" to reconstruct state that a clean handoff
   would have stated directly.
2. **Medium cost — no mechanism confirms all dispatched background lanes are
   `idle` (not `running`) before a session treats its own work as closed.**
   The commit that closed the round landed while 3 lanes were still running.
   A `kb-ship`/`clear-prep`-adjacent check that refuses to finalize while
   `ListAgents` reports any `running` teammate of the current session would
   have caught this mechanically rather than relying on the model to notice.
3. **Lower cost, but real — the "kb-recall-work FIRST" precondition had to be
   broadcast to 4 already-running lanes individually** rather than being
   part of the dispatch prompt template from the start. This is a few
   SendMessage calls' worth of overhead, not a session-ending problem, but it
   is exactly the kind of process gap `docs/dag/2026-09-12-session-review-round.toml`
   (written by the FOLLOW-UP session) is now trying to close by making the
   DAG itself the enforced dispatch contract.

## Correction to §4.1, made after `--no-sync` unblocked agentsview

Team-lead reported `mise run kb-session-search -- "<pattern>" --since Nd --limit N --no-sync`
works around the `daemon sync error` (two unrelated foreign harness files break
the all-or-nothing sync pass). Re-checked the "abandoned lanes" flag directly
against the local transcript (not agentsview, which returned no hits for these
specific lane names — noted as its own negative, unconfirmed against a known-
present control term in this pass) and found the original claim was **partially
wrong**:

- **`session-audit-lead` was NOT abandoned.** Its completion message arrived at
  19:12:42Z (*"Session audit complete: 5 lanes + Astra synthesis, verdict and
  handoff on disk"*), and the crashing session copied its synthesis into
  `docs/research/reports/2026-09-12-function-hooks-round/` at 19:13:05Z — 14
  minutes before the crash. Fully consumed.
- **`scratch-isolation-review` and `claudex-loop-mining` sent INTERIM reports**
  (18:23:09Z and 18:28:58Z respectively) that WERE read and acted on (both
  explicitly say "INTERIM" and name further nested codex sub-lanes still
  running underneath them: *"Three codex lanes (sweep / native-research /
  gate-design) are still running"* for the former, *"Lanes A/B/C/D are
  running"* for the latter). **The `ListAgents` snapshot's `running` status
  for these two, taken later in the session, is consistent with those nested
  sub-lanes never finishing before the 19:27:09Z crash** — so the TOP-LEVEL
  lane was not abandoned (its interim findings were read and, per the
  handoff/commit content, partly acted on), but whatever FINAL synthesis
  those two lanes' own nested codex fan-outs were going to produce is, as far
  as this transcript shows, still unresolved. This is a narrower and more
  accurate claim than the original "3 lanes abandoned" — one lane (session-audit-lead)
  fully closed the loop; two lanes' outer shells reported in, but an unknown
  number of their own nested codex children did not, before the session that
  would have read them stopped existing.

This is itself worth naming per `change-the-route.md`: my first read (a
`ListAgents` snapshot's `running`/`idle` column) was the wrong instrument for
"was this lane's work incorporated" — the right instrument was the
transcript's own `teammate-message` records, which show completion status and
timing directly.
