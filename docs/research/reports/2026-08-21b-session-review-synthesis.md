# Session review synthesis — round of 2026-08-21 (transcript 6ae19ff6-2b88-4aea-8fa7-c0430395e2da)

Written 2026-08-21 by the kb-synthesist from eight lane reports + one cross-check pass. This
document combines; it did not research and did not verify. Every number below is INHERITED
from a lane or a refuter and is labelled with which. The only things this synthesist measured
itself: `git branch --show-current` -> `corpus-gate-bundle-0821`, HEAD `b30a80c9`,
`git status --short` -> empty (clean) at synthesis time; and one `kb-query --prose --idf`
(graph-first compliance; returned /clear-vs-/compact doctrine, nothing that changes a rank).

## 0. Counts, and the process finding they carry

| bucket | n | note |
|---|---|---|
| CONFIRMED by cross-check | 3 | only **2 distinct facts** — the 20%-context finding was confirmed twice (context lane + tooling-gap lane, same timestamps) |
| REFUTED by cross-check | 11 | 9 leave a narrowed, still-live residue; 2 are void (kb-setup direct-call "gap"; GAP-3 "unverified") |
| returned UNVERIFIED | 0 | the cross-check agent that ran returned on everything it reached |
| NOT TRIAGED (budget ran out) | 30 | nobody looked at these; they are NOT clean |
| total | 44 | |

- The verifier ran (refuted > 0), but it reached **14 of 44 = 32%** and refuted **11 of those 14 in whole
  or part (79%)**. Read the 30 untriaged items at roughly that prior, not as confirmed.
- Refutation classes, because they are evidence about the probes: **5 of 11 read a pre-fix artifact or a
  stale secondary source** (#426 constant, #414 dedupe, the six readiness-doc figures, GAP-3, the launcher)
  — exactly the stale-open-issue / graphify-circle trap the repo's own rules describe; **3 were token or
  count attribution** (pgrep vs ps, "2-arg", "five passes" -> eight); **2 were causal-actor attribution**
  (who blocked the round; who reversed the proxy decision); **1 was doc-scope** (tokenise sentence belongs
  to item 2a, not the graphify guard).
- Three lanes filed issues (#428–#434) BEFORE the cross-check ran; three of those rest partly or wholly on
  refuted framing (see R8).

## 1. Ranked by cost of leaving it unfixed

Legend: CONFIRMED = survived cross-check. RESIDUE = the finding as stated was refuted; what is listed is
the part the refuter showed still holds. UNTRIAGED = nobody cross-checked it.

### R1 — No mechanical trigger for /clear-prep; 20% of context crossed 15 min in, Ray volunteered 8h43m later  (CONFIRMED, ×2 lanes)
- **Facts carried (context + tooling-gap lanes, same probe):** usage total 200,224 at 06:23:23Z (session start
  06:08:40Z); later AskUserQuestion boundaries at ~24% and ~55% also passed without a /clear-prep ask
  (UNTRIAGED restatement); Ray types "/clear-prep… context is getting full" at 15:06:04Z; no
  `isCompactSummary` record (0, control 24). Condition: "20%" assumes the 1M-class window Ray stated; the
  session reaching ~783k uncompacted is consistent with that, and no lane measured the window itself.
- **Cost of leaving it:** one full round's context per round, every round; this round the ask came at
  ~75–77%. This is the top circle because nothing in the repo's enforcement stack touches it.
- **Fix existing first, do NOT add a warning:** (a) the circles lane reports **259 `total_tokens_reminder`
  attachments** in the same transcript, while the tooling-gap lane reports no system-reminder mentioning
  context% — **two lanes disagree about whether the harness already warned**; settle that before building
  anything (see §6). (b) If the harness signal exists and was ignored 259 times, a second reminder
  repeats the measured 0/19 outcome; the house pattern that moved behaviour is a DENY. The hook is already
  wired on `Bash|Grep`; a `kb_setup` guard beside `stage_explicitly`/`check_first` that reads the session
  transcript's own usage and refuses non-trivial tool calls past a threshold — printing "AskUserQuestion:
  ask Ray to run /clear-prep" (the skill is `disable-model-invocation`, so the model cannot run it;
  UNTRIAGED finding: the one attempt to Skill() it was refused at 15:06:16Z) — is the shape consistent
  with this repo's evidence. (c) Do not build it as a new mise task first: a task is invoked; a guard fires.

### R2 — The stale-artifact circle around the 0.9.48 extraction decision  (RESIDUE of four refuted findings — the circle is what survives)
- **What the refuters established (unpinned lane ×3, bot-reviews lane ×1, all refuted as stated):**
  - `_ACCEPTED_GRAPHIFY_RUNTIME` is GONE at HEAD (d8114ab1, ancestor of HEAD; `_measured_runtime()` at
    graphify_semantic_corpus.py:219-240; the fix's test goes red under the reverted mutant and anchors to
    `graphify_baseline.runtime_identity`, not a pasted copy) — the "#426 P0" read origin/main.
  - Dedupe IS content-hash keyed at HEAD (3d9bb3ff + 964fb112; `setdefault(member.sha256, …)` at :1360;
    test red under the path-keyed mutant) — the "#414 P1" read 3d9bb3ff~1. The NUMBERS survive
    (28 groups / 257 paths / 571,462 of 1,038,052 = 55.1%; chunks 58 -> 26; admitted 466,590).
  - `mise run kb-graphify-semantic-corpus -- verify` -> `execution_authorized:false, reasons:[typed-member-invalid]`,
    so the "~$65 / 10.6h / 58 chunks" spend cannot be authorised; the on-disk plan
    (execution-config.json 0.9.47, source-inventory.json schema 1, mtime 2026-08-20 22:23) is STALE and now
    fails decode / trips `plan-graphify-runtime-mismatch` rather than passing silently.
  - The readiness doc `docs/research/reports/2026-08-21-session-review-synthesis.md` is unmodified since
    8929d47f while graphify_semantic_corpus.py changed in FOUR commits; its real CodeRabbit comments sit at
    lines 16, 33, 43 (ER-10 prerequisite), 284 (unmet-requirement count), 668, 766 — two of the "six" the
    finding listed belong to other files.
  - GAP-3's DW-14 "25 committed, ZERO merged" is FALSE: 23 of 25 chunks have node names in graph-prose.json
    (control: bogus token 0/0); DW-19's five `build = skip` manifests were measured on the main chain at
    06:21:14Z.
  - BONUS, found by the #426 refuter while arming: `tests/test_graphify_semantic_corpus.py::
    test_recorded_authority_authorizes_this_plan_and_only_this_plan` FAILS at clean HEAD with
    `plan-authority-mismatch, cost-advisory-review-required, provisional-input-decisions` — consistent
    with the UNTRIAGED "21 run tests + frozen-authority test expected-red until re-plan; kb-arms unrunnable".
- **Cost of leaving it:** round 3 reads the readiness doc + two OPEN issues + a stale plan and re-derives
  the same three "blockers" for the sixth time; this is THE GRAPHIFY CIRCLE (memory) in its current form,
  and it already consumed three of this round's fourteen triaged findings.
- **Fix existing first:** (1) `mise run kb-graphify-semantic-corpus -- plan` then `-- verify` ONCE (re-plan)
  — it is the root of the expected-red set and of kb-arms being unrunnable; sequence it FIRST in round 3.
  (2) Close or re-scope #426 and #414 citing d8114ab1 / 3d9bb3ff+964fb112 (stale-open issues are the
  secondary-source trap that produced two refutations). (3) Edit the readiness doc's lines 16/33/43/284 and
  replace GAP-3's DW-14 sentence with "23/25 present in prose graph" — in the SAME commit as R4's
  promotion. (4) `#301` ("25 committed, ZERO merged") — re-check its body against the 23/25 measurement
  before round 3 acts on it (not settled here).

### R3 — The graphify hand-run guard has a measured EVASION and a false-positive class at once  (RESIDUE ×2, contradicted lane; both real defects)
- **Evasion (refuter of "deny did not fire under bypass"):** `hook_guard.py:34 _CMD_POS` has no `\n` in its
  separator class and `^` is not MULTILINE, so `cd <repo>\ngraphify update .` is NOT at a command position
  and `decide()` returns None; the same string with `;`/`&&` denies. Live: four graphify commands ran
  that way in a Workflow subagent, including **`graphify update .` performing real root-path AST
  extraction (100→400 of 861 files) stopped only by a downstream SIGPIPE** — the actively-bad case
  do-not.md #2 names. `stage_explicitly` denied `cd …\ngit add -A` in the same session because its shlex
  uses `punctuation_chars="();<>|&\n"`. No corpus damage (graph.json mtime unchanged) — by luck.
- **False positive (refuter of the "tokenise" contradiction):** a literal `|` inside a quoted grep
  alternation (`"foo\|graphify query"`) is read as a separator and denied (3/3 live; 2/2 pass without the
  `|`). hook_guard.py:36-37's comment ("not … a quoted mention") contradicts :38; `_code_only()` exists and
  is applied only in `_bare_python`; `tests/test_hook_guard.py:61` fixture has no `|`, so it cannot see it.
  The rule doc was NOT contradicted — the tokenise sentence is item 2a (check_first).
- **Cost of leaving it:** every "62→0" claim rests on this guard, and every fan-out lane writes multi-line
  `cd repo\n…` Bash; the first measured evasion in the guard's history is one character wide.
- **Fix existing first (not a new guard):** `[;&|]` -> `[;&|\n]` in `_CMD_POS`; apply `_code_only()` in
  `decide()` before the graphify regex; add the two test pairs (multi-line cd form -> deny; quoted `|`
  alternation -> allow). Re-file the tokenise finding against hook_guard.py:36-38 + the fixture, not
  against mise-tasks-only.md.

### R4 — Round 3's only record lives in gitignored `.agent/`, and lanes overwrite that tree  (CONFIRMED + UNTRIAGED #431)
- **CONFIRMED (forgotten lane):** cold-review-lane1/2/3.md + cold-review-round2.md exist only under
  `.agent/kb/reports/agents/`; `git ls-files docs/research/reports/ | grep -i cold-review` -> 0; Ray's
  addendum scopes round 3 to exactly those residuals; the promotion mechanism was used the same week for
  a PR #422 artifact, so this is an omission.
- **UNTRIAGED but same class (#431, circles lane):** a session-review lane overwrote `.agent/notepad.md`
  wholesale (recovered from transcript, 16/16 appends) and the same run clobbered three 2026-08-18 lane
  reports (birth 08-18, mtime 08-21) — nobody cross-checked this, but if true it raises R4's cost from
  "a /clear could lose it" to "the next review run WILL".
- **Fix:** `cp` the four files (verbatim, rule 1b) into `docs/research/reports/` in the commit that records
  this round's handoff — before any /clear. No tooling needed; it is a cp. Include the readiness-doc edits
  (R2) in that commit.

### R5 — The four-name proxy exemption: eight passes, two executed rounds, deferred to a third  (RESIDUE, circles lane)
- **Refuted clauses:** "never armed" (test_scrub_route_overrides_excludes_proxy_configuration goes red under
  the realistic revert; ebcf9fcb's body records a live HTTP_PROXY arm) and "a reviewer overturned a recorded
  decision" (both reviewers asked for a DOCSTRING; the ARCHITECT ordered the behaviour change at
  spec-lane1-round2.md:14(b)). "Five passes / three rounds" undercounts: eight touches, two rounds + one planned.
- **Residue:** no typed CLI refusal for the reachable `ValueError: forbidden routing environment names:
  HTTP_PROXY` (P2-1; pre-existing at 8929d47f and ruled out of scope in advance), and lowercase proxy names
  were never in `_ROUTE_OVERRIDE_NAMES` at any revision (P2-2). Still item 9 of spec-round3-DRAFT.
- **Cost:** one more round of the same item. **Fix:** decide lowercase in/out and add the typed refusal in
  round 3 as one change; #434's remedy (b) ("a reversal owes an arm") is moot for this case — re-scope #434 to
  "architect routed severity-LOW doc-only items into a behaviour change without quoting the DECIDED line".

### R6 — Dead time in the round  (RESIDUE; #433's headline figure is wrong)
- **Refuted:** "AUQ blocked 4h14m / 44% with three lanes finished" — two lanes were still running for
  31.9 min after the question, only one lane was idle at the instant, no spawn was delayed.
- **Durable figures (refuter):** dead time 09:01:49Z -> 12:44:14Z = **222.4 min = 38.7%** of a 574.3-min
  span; last idle notification delivered 223.0 min late; recoverable throughput ≈ Lane 3's ~35-min run.
  Confound never tested by the lane: the gap is 03:29–07:44 LOCAL (UTC-5) — the lowest-activity hours
  across every transcript in this project dir (8× spread), so a human dependency at 03:30 incurs this wait
  regardless of placement.
- **Fix:** amend #433's body to the 222-min/35-min figures; the placement rule (drain the mailbox, dispatch
  everything independent of the answer, batch questions — 5 asked separately, the tool takes 4) stands
  but is worth ~35 min, not 4h.

### R7 — Liveness by `ps`/`pgrep` instead of ListAgents  (RESIDUE; count re-attributed)
- `pgrep` appears in 2 of 102 Bash calls; the "7" is the `pgrep|ps -` union (5 are the byte-identical
  preflight chain's `ps -axo … | grep -E 'codex exec'`; one is a ChatGPT.app disambiguation the lesson
  permits). Substance holds: 7 process probes vs **1 ListAgents across 20 Agent spawns**, lanes were
  Agent-tool teammates. MEMORY.md renders the enforcement precedent as 62→1, the memory file as 62→0.
- **Fix:** #428's proposed deny pattern (`pgrep -f .*codex`) would have matched 2 of 7; it must cover the
  `ps … | grep … codex` form or it is decoration. Fix the 62→0/62→1 inconsistency in whichever file is wrong.

### R8 — Issue hygiene: issues filed on refuted or stale premises  (bookkeeping, but it is how R2 propagates)
- **#429** ("no _REDIRECT for graphify-semantic-corpus/-slice") — premise VOID: `_REDIRECT` is keyed on
  graphify subcommands; `uv run kb-setup <cmd>` is the sanctioned form (zero-bash-logic.md, three hk
  steps, mise-tasks-only's session-state row); the task body IS the command byte-for-byte; all 7 calls were
  provider-free preflight/verify/plan. Close it.
- **#433** amend (R6). **#434** re-scope (R5). **#426 / #414** close or re-scope with the fixing commits
  (R2). **#428** widen the pattern (R7). **#301** re-check against 23/25 (R2).

### R9 — `docs/agents/evidence/issue-301/prototype-corrected-launcher.py`  (RESIDUE; low)
- "2-arg", "silently", "broke" all refuted: 3 positional + keyword-only `live_runtime`; c720f1c9's body names
  file:line and the decision; the script was already unrunnable pre-round (`boundary_path`, 98b116fd).
  Survives: outside hk's pyGlob, no tracking issue. Fix: one header line marking it non-executable evidence,
  or nothing.

### R10 — Direct `uv run kb-setup graphify-semantic-*` calls  (REFUTED, void — no action; see #429)

## 2. NOT TRIAGED — 30 findings nobody cross-checked

Nobody verified these. Given 11/14 refutations among the triaged set, treat the tier as "cost IF true".
Duplicates of already-ranked material are marked.

| tier if true | claim (lane) | note |
|---|---|---|
| high | #431 notepad overwritten wholesale; three 08-18 lane reports clobbered (circles) | feeds R4 |
| high | session-review workflow failed mid-run, killed/relaunched twice, 29 min, Ray's screenshot; per-run script copy needs hand `cp` (circles) | the instrument reviewing this round |
| high | 100% round-2 rework: 7 commits for 3 units, 13 P1 / 0 P0 across 4 cold reviews; pv passes pre-empted none (circles) | not separately filed |
| high | six commits landed with kb-arms unrunnable; expected-red hand-derived ×4 (circles) | R2's re-plan is the remedy; `--expect-red` (#430) untriaged |
| high | manifest.py validates enum VALUES not KEY NAMES: `buld = skip` silently drops the build=skip protection (bot-reviews) | fresh repro claimed; `added` key in 37/73 manifests must be allowlisted |
| high | kb-review skill invoked 0 times while cold reviews ran by hand-spawn; receipt ×7, ship ×11, land ×14 (tooling-gap) | |
| high | CodeRabbit "Merge Risk: Moderate" at 06:11:25Z, merged 06:47:48Z, never adjudicated; pr.py reads no risk marker (bot-reviews) | 2 of 3 named risks still live per lane |
| high | 8 of 20 subagents nudged; 109,165 bytes re-injected; discriminator = one prompt clause (#432, circles) | |
| medium | #401: clear-prep does not invoke kb-session-review; Ray asked a third time (unpinned) | |
| medium | orchestrator-routing SKILL.md never invoked/read; fable-orchestrator:orchestration did fire on time (tooling-gap) | needs a decision, not a wrapper |
| medium | ExpectedX.relative_path read via `root / …` with no containment; `_safe_root_regular_file` wired to one caller (bot-reviews) | lane itself: "agreed 2/2, NOT verified" |
| medium | `_drop_skipped_builds` raises before printing skip reasons in the all-skipped state (bot-reviews) | |
| medium | `manifest.add()` writes unvalidated `kind`; not in #421 (bot-reviews) | |
| medium | no test pair for `approve_same_file_id_collision_note` (bot-reviews) | |
| medium | 18 silent turns re-prompted by the harness, all after idle-notification wakes (circles) | folded into #433 |
| medium | collision validation runs before skip filter — lane could not construct a failing case (bot-reviews) | self-declared UNCERTAIN |
| medium | worktree graphify-0942 holds untracked `.codex/` + `.agents/skills/` state (pending-work) | |
| medium | branch 7 ahead / 0 behind — expected pending work (pending-work) | matches my `git status`: HEAD b30a80c9 clean |
| low | `.claude/CLAUDE.md` "Nine plugins" vs 10 in settings.json (contradicted) | bookkeeping |
| low | delegation 22/261 tool calls (8.4%) (context) | lane itself says "not the primary lever" |
| low | tool_result payload only ~379KB; blowout is history replay (context) | supports R1 |
| low | session 9h31m uncompacted, 783,653 tokens ~78% (context) | DENOMINATOR STALE — transcript was still appending (refuter) |
| low | two checkpoints at ~24%/~55% passed without ask (context) | restatement of R1 |
| low | /clear-prep at 15:06; "Haiku model context budget ~48k tokens" (unpinned) | evidence line is GARBLED — 48k is not the session model's window; treat as unusable |
| low | orientation agent re-discovered handoff item 1 / #426 as a "headline" (circles) | presentation defect |
| low | Skill({skill:'clear-prep'}) refused (disable-model-invocation) instead of AskUserQuestion (tooling-gap) | feeds R1 remedy text |
| low | five preflight chains / four kb-check bucketing chains / six notepad heredocs / 7 ps probes (circles + unpinned ×2) | three lanes, one fact; #428–#430 already filed; R7 covers the ps part |
| low | session-review.js parse error at 15:39:02Z — backtick inside template literal; no lint over .claude/workflows/*.js (tooling-gap) | `node --check` catches this class; memory says it misses broken-ESM semantics — a different blind spot |
| low | kb-session-review manually invoked (unpinned) | dup of #401 row |
| low | /clear-prep threshold "unverified (requires full token accounting)" (unpinned) | superseded by R1, which did the accounting |

## 3. Refuted findings — the whole list, with what refuted them (evidence about the probes)

| # | claim (lane) | refuted by | survives | probe defect |
|---|---|---|---|---|
| 1 | AUQ blocked 4h14m/44%, three lanes idle (circles) | per-lane first/last activity; empty-gap jq; 24h availability histogram | 222 min dead, ~35 min recoverable | causal attribution without the confound; stale live denominator |
| 2 | graphify deny failed under bypass/Workflow (contradicted) | `decide()` on the verbatim multi-line strings -> None; `;`/`&&` forms deny; live deny in the same agent type | newline hole in `_CMD_POS` (R3) | the lane's "identical payload" control stripped the `cd\n` byte that was the whole outcome |
| 3 | #426 frozen 0.9.47, verify passes, $65/10.6h (unpinned) | HEAD has `_measured_runtime()`; verify -> not authorised; `git show d8114ab1^` reproduces the cited lines | stale plan artifact; pre-existing failing authority test | read origin/main / pre-fix commit; stale-open issue |
| 4 | #414 dedupe keyed on (path,slice) (unpinned) | :1360 sha256 key; mutant goes red; schema-2 decode fails on old plan | the numbers; stale-open issue | read 3d9bb3ff~1 |
| 5 | GAP-3 DW-14/DW-19 unverified (unpinned) | main-chain Bash at 06:21:14Z measured both; 23/25 chunks present in prose graph | nothing — DW-14 "zero merged" is FALSE | bounded search of per-lane verify files cannot see a main-chain probe |
| 6 | six stale figures, none fixed/filed (bot-reviews) | PR comment ids/paths; #426 filed; d8114ab1 fixed; doc says 'will burn' | doc unmodified since 8929d47f; lines 16/33/43/284/668/766 | two items misattributed to other files; "not filed anywhere" wrong |
| 7 | proxy frozenset reversed by a reviewer, never armed (circles) | test goes red under realistic revert; spec-lane1-round2.md:14(b) names the architect; lowercase 0 at all revisions | eight passes, missing typed refusal, lowercase undecided | wrong actor; wrong count |
| 8 | launcher silently broke, 2-arg (forgotten) | AST bind probe at HEAD and base; c720f1c9 body names the file | outside gates, untracked, pre-broken | synthesised "2-arg"/"silently" not in its own cited source |
| 9 | mise-tasks-only claims the graphify guard tokenises (contradicted) | line 92 is item 2a (check_first); check_first behaves as documented | quoted-`|` false deny is real — against hook_guard.py:36-38 | doc-scope misread |
| 10 | pgrep ×7 (unpinned) | per-command extraction: pgrep in 2/102; 7 = pgrep+ps union | 7 process probes vs 1 ListAgents | token spelling |
| 11 | five direct kb-setup calls bypass tasks, no _REDIRECT (unpinned) | `_REDIRECT` keyed on graphify subcommands; sanctioned form; task body = same command | nothing | category error; remedy unimplementable |

Refuters' own recorded probe hazards (three refuters, independently): unquoted `--include=*.md` -> zsh
"no matches found"; `echo ===` -> zsh EQUALS expansion; `pytest | tail; echo $?` reported 0 for a FAILED
test. All three are the pipe/bound classes the rules already name, reproduced inside the verifier.

## 4. Lane coverage — ALL EIGHT lanes are PARTIAL; none returned nothing

| lane | never reached (so its findings are a LOWER BOUND for that territory) |
|---|---|
| circles | every SUBAGENT transcript (codex-lane*, cold-review-*, pv-*, explore-*, plan-dedupe-design) — ~6× more activity than the 257 main-chain calls it saw; the 05:17Z run's clobbered artifacts; spec-round3-DRAFT content; any live kb-build/kb-arms/test run. Opened-not-finished: session-2026-08-20-d.md; cold-review-lane2/3 bodies (their 3+5 P1s counted, not traced to pv items) |
| forgotten | the assistant/tool_use stream (user turns only); SIXTH ADDENDUM items beyond #427; the in-flight synthesis/completeness output of this very run; cold-review-lane3 P1 bodies; pv-* persisted files |
| contradicted | root cause of its own finding 2 was OPEN at lane end — **closed by the refuter (newline hole), not by the lane**; mutation-arm specs and cold/pv reports not read line-by-line; only 2 of ~20 _REDIRECT rows live-tested |
| unpinned | context accounting (none); per-Bash-command classification; subagent transcripts — and its one context item carries garbled evidence ("Haiku ~48k") |
| context | per-call redundancy judgement; subagent context growth (whether any lane blew its own window) |
| tooling-gap | lane specs and cold/pv reports beyond timing; kb-ship/land/receipt exit codes taken from the handoff at face value; the 14-session automation-candidates window |
| bot-reviews | ~90 graphify-labs coupling-hotspot items; F9 ordering left UNCERTAIN by its own statement |
| pending-work | stash@{0} other 9 files and stash@{1} at --stat only; worktree `.codex/agents/*.toml` contents |

Systemic: no lane opened a subagent transcript. Every "circle" count above is orchestration-level only.

## 5. Not comparable — do not rank lanes or counts against each other

- Same transcript, different filters: context lane 261 tool calls / circles 257 main-chain / tooling-gap
  102 Bash / circles+unpinned 101 Bash / forgotten "2,813-line" vs tooling-gap "2,826-line" vs circles
  "2,796 records". The file was still appending (15:40 → 15:52 → 15:56 across lanes). These are not
  disagreements; they are the noise floor. No percentage of session span computed by any lane is stable.
- bot-reviews and pending-work review a different OBJECT (PR #422's thread; git refs/stash/worktrees) than
  the six transcript lanes; their zero-overlap with the others is category, not a low yield.
- The confirmed/refuted split is not a per-lane quality score: the cross-check reached 3 of 8 lanes'
  items disproportionately (unpinned ×4, circles ×2, contradicted ×2, bot-reviews ×1, forgotten ×1,
  context ×2, tooling-gap ×1, pending-work ×0).

## 6. What this review itself got wrong, or could not settle

1. **Coverage, not cleanliness.** The cross-check reached 32% of findings and refuted 79% of what it
   reached. This synthesis cannot say anything about the 30 untriaged items beyond listing them; they
   are NOT "lower-ranked", they are unreviewed.
2. **The confirmed count is inflated.** 3 confirmed = 2 facts. Two lanes ran the identical probe on the
   identical transcript and both "confirmations" are the same evidence.
3. **Two lanes disagree on whether the harness already warned about context** (259
   `total_tokens_reminder` attachments per circles vs "no reminder mentions context%" per tooling-gap).
   Nobody read those attachments. R1's remedy depends on which is true and this synthesis did not settle it.
4. **Refuters mutated the working tree concurrently.** Two refuters observed a foreign uncommitted
   `RuntimeIdentity(version="0.9.47")` edit in graphify_semantic_corpus.py appear mid-probe (one anchor
   shifted 1352→1360); a third mutated graphify_semantic_slice.py. The lane that wrote it reports restoring
   it; at synthesis time `git status --short` is empty, so the tree IS clean now — but "never edit while a
   mutating lane runs" was violated inside the verifier itself, and for a window the anchors of two arms
   were unreliable.
5. **Every denominator is stale on arrival** (9.55h / 9.571h / 9.73h; 783,653 tokens "final"); the
   transcript was appending while being measured. Durable figures are deltas and absolute timestamps only.
6. **This synthesis measured nothing.** The 23/25 merged-chunk figure, the 222-min dead time, the newline
   hole, the verify output — all inherited from refuters; none re-derived here. The ranks are judgements
   over inherited evidence.
7. **Issues were filed before verification** (#428–#434). This synthesis ranks their correction (R8) but
   did not read the issue bodies itself; the amendments named are what the refuters' text implies.
8. **`#301`'s body** was not read by any lane in this round; the 23/25 finding may or may not contradict it.
9. **The "1M-class window" premise** behind every context percentage was stated by Ray and never
   measured by a lane; "20%" is conditional on it.
10. **Cold-lane residuals themselves were not re-read** — the round-3 scope (R4) is carried by filename,
    not by content; whether all 13 P1s are still live at b30a80c9 is unknown to this synthesis.

## 7. Fix existing tools first — no new automation where a task or a cp already does it

1. `python/src/kb_setup/hook_guard.py` — `_CMD_POS` newline; `_code_only()` in `decide()`; two test pairs (R3).
2. `mise run kb-graphify-semantic-corpus -- plan` / `-- verify` once — the re-plan closes R2's stale plan and
   the expected-red set; no new checker (R2).
3. `cp` four cold-review reports into `docs/research/reports/` + edit the readiness doc's six lines in the
   same commit (R4, R2). No task needed.
4. `gh issue` close/amend: #429 close; #426/#414 close or re-scope with commits; #433/#434/#428 amend (R8).
5. R1: establish what the harness's existing reminder says BEFORE building; if something is built it is a
   deny-shaped guard in `kb_setup` on the already-wired hook, not a new warning or a new task.
6. Proposed-new and untriaged (do not build before triage): `kb-context-check`, `kb-note` (#431),
   `kb-round-check` / `kb-check --expect-red` (#430), `kb-workflow-sync`, a `.claude/workflows/*.js` lint.

## Counts (repeated for the parser)

verified: 3 (2 distinct) · refuted: 11 (9 with residue, 2 void) · returned-unverified: 0 · not triaged: 30 · total: 44 · cross-check coverage: 14/44.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the only repo consulted: this synthesis read the lane and refuter text, ran `git branch/status/worktree list` and one `kb-query` here; the lanes cite PR #422 and issues #301, #401, #414, #417, #421, #426–#434 of this repo via `gh`. No other repo's source, docs or issues were consulted by this synthesis.
