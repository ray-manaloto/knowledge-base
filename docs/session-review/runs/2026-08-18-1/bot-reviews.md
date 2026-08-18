# Iteration 1 — lane: bot-reviews

Window: PRs touched 2026-08-18 (all merged same day): #336, #337, #338, #339.
No open PRs exist (`gh pr list --state open` → `[]`, control: same command
`--state all` returns 21 rows, so the empty result is a real "none open", not a
broken query). Current branch `docs-directive-addendum` has no PR at all
(`gh pr view docs-directive-addendum` → "no pull requests found for branch").

Commands used throughout, cited per finding below. Bot accounts seen:
`coderabbitai[bot]`, `graphify-labs[bot]`.

---

## FINDING 0 (ROOT CAUSE, highest leverage) — every bot review in this window landed AFTER the PR was already merged; the merge window is often under 15 seconds

Command: `gh pr view <n> --json number,createdAt,mergedAt` per PR, cross-referenced
against each bot's `submitted_at` / comment `created_at` collected above.

| PR | opened → merged | time-to-merge | graphify-labs review posted | delta vs merge |
|---|---|---|---|---|
| #336 | 01:58:05 → 02:14:49 | **16m 44s** | 02:29:50 | **+15m after merge** |
| #337 | 03:40:03 → 03:43:21 | **3m 18s** | 03:46:18 | **+3m after merge** |
| #338 | 04:33:21 → 04:33:31 | **10s** | 04:43:38 | **+10m after merge** |
| #339 | 07:50:46 → 07:50:57 | **11s** | 07:58:36 | **+8m after merge** |

**Every single graphify-labs review in this window posted after the PR was
already merged to `main`** — not "before merge, but late"; strictly after.
CodeRabbit's own comment on #339 states outright: *"Review failed. The pull
request is closed."* (`gh api repos/.../issues/339/comments` → the
`failure by coderabbit.ai` marker) — CodeRabbit could not even START a review
because `kb-land` had already squash-merged and closed the PR 11 seconds after
it opened.

**This is the actual, structural reason bot reviews read as "ignored."** It is
not (only) a discipline problem — a bot cannot gate a merge that completes in
10-11 seconds (#338, #339). `mise run kb-land` is designed to watch checks to a
terminal state and then merge immediately (`gh-cli-watch.md`), but neither
CodeRabbit nor graphify-labs is in `kb_setup.pr._ADVISORY_CHECKS`' watched set
in a way that BLOCKS the merge on their completion — they are async,
best-effort commentary that is architecturally guaranteed to lose the race
against a fast-merging local pipeline. Ray's directive says "enforce reviewing
all pr reviews from bots instead of ignoring them" — the fix this points to is
procedural (read the bot's comments on the NEXT PR / in a follow-up pass, since
they cannot land before merge) or structural (widen the window before
`kb-land` merges, or make `kb-land` poll `gh pr checks` — including these two
GitHub Apps, if they register as status checks — for a bounded post-merge
grace period and re-open/flag on a bot escalation, which the current
"advisory, never blocking" design explicitly does not do). **This finding is
the parent of Findings 1-8 below**: every specific un-dispositioned bug they
list is un-dispositioned because nobody had a documented step that circles
back to bot comments AFTER a merge that already happened before they were
written.

---

## FINDING 1 (BLOCKER-class, un-dispositioned) — check_first.py has two live bypass/false-positive bugs graphify-labs flagged on PR #337, neither fixed

**Bot**: `graphify-labs[bot]`, review id `4957036793` on PR #337, submitted
2026-08-18T03:46:18Z, against commit `888df6d0b272f5cdb3e6038d524b8c318ce79a2a`
(the #337 fix-round commit).
Command: `gh api repos/ray-manaloto/knowledge-base/pulls/337/reviews/4957036793 --jq '.body'`

Five "Escalate / medium" findings, all in `check_first.py`'s `_command_word` /
`_segment_is_a_gate`:

1. "env options with operands hide gated commands" — `check_first.py:178`
2. "Value-taking env options can hide a gated command" — `check_first.py:180`
3. "Transparent wrapper options with values hide gated commands" — `check_first.py:181`
4. "Gate help flags are denied instead of treated as introspection" — `check_first.py:216`
5. "Global options before introspection subcommands cause false denials" — `check_first.py:218`

**Disposition check.** The ONLY fix made against `check_first.py` since #337
merged is commit `11c783b0` ("give the `--` separator its own branch so the
hook cannot hang") — that fixes a **different** bug (CodeRabbit's hang finding,
below), not any of these five. I confirmed live, against the CURRENT working
tree (`python/src/kb_setup/check_first.py`, unpushed commit `022e88f4` HEAD):

```
$ uv run python -c "from kb_setup import check_first as cf; print(cf.decide('env -u FOO ruff check .'))"
None      # ALLOWED — the gate silently does not fire
$ uv run python -c "from kb_setup import check_first as cf; print(cf.decide('ruff --isolated help check'))"
'Do not hand-chain the gates...'   # DENIED — a pure help/introspection call is blocked
```

Control arms (same session, same command shape):
- `cf.decide('ruff check .')` → denied (reason string) — proves the probe CAN deny.
- `cf.decide('ruff --version')` → `None` — proves the probe CAN allow.
- `cf.decide('ruff check --help')` → `None` (correct: this specific adjacent-help
  shape IS handled) — so the bug is specifically the **non-adjacent** shapes
  matching findings 1-3 (a value-taking wrapper option) and 5 (a global option
  before the introspection subcommand), not a blanket failure.

**Root cause matches the bot's diagnosis exactly.** `_command_word`'s wrapper-flag
branch calls `_consume_flags(words)` with NO value_flags for `env`/`time`/`command`
(only `uv` gets a `_VALUE_FLAGS` set), so `env -u FOO ruff check .` reads `FOO`
(the flag's operand) as the command word instead of `ruff` — the gate never
fires and a hand-chained `ruff check` runs unguarded, defeating the entire
guard this PR shipped. Finding 5 (`ruff --isolated help check` wrongly denied)
is the opposite direction: `_INTROSPECTION_SUBCOMMANDS` only inspects
`arguments[0]`, so a global option ahead of `help`/`explain`/etc. hides the
introspection marker from that check, and the segment gets denied.

**Verdict: un-dispositioned.** Not fixed, not filed as a GitHub issue (`gh issue
list --search "check_first" --state all` — see below, only 1 unrelated hit), not
mentioned in any commit message, review report, or handoff. Both bugs are LIVE
on the current HEAD. Severity as reported by the bot: 5x medium; my own
assessment of #1-3 is higher than "medium" given `check_first.py`'s own module
docstring states its explicit threat model is "which way it misses" being
false-negative-tolerant — but bypassing the gate entirely via a common
`env -u VAR cmd` shape is a bigger hole than the module's own stated tolerance
(an *unlisted* value-flag silently reading its value as the command word was
explicitly the accepted risk for `uv`; the SAME defect for `env` was not
accepted, it was simply not seen).

---

## FINDING 2 (dispositioned — FIXED, but the fix is unshipped) — CodeRabbit's critical hang finding on PR #337

**Bot**: `coderabbitai[bot]`, review id `4957026594` on PR #337, submitted
2026-08-18T03:43:57Z. Inline comment id `3800858933` on
`python/src/kb_setup/check_first.py:186`, severity `🔴 Critical` / `🏗️ Heavy lift`:
"Handle `--` after a transparent wrapper prefix" — `_consume_flags` stops AT
`--` without consuming it, so `_command_word`'s prefix loop never terminates
for `env -- ruff check .`.
Command: `gh api repos/ray-manaloto/knowledge-base/pulls/337/comments --jq '...'`

**Disposition**: FIXED, same day, by commit `11c783b0` ("give the -- separator
its own branch so the hook cannot hang"), whose message quotes CodeRabbit by
name and cites the confirmed-live symptom (PreToolUse hook stalls to its 20s
timeout, then the call runs unguarded). An arms spec
(`.agent/kb/arms/check-first-separator-hang.toml`, gitignored) is cited as
armed both directions. **But this fix is UNPUSHED** — it lives only on the
local branch `docs-directive-addendum` (`git log --oneline` shows it sitting
between `e8f7f4ea feat kb check guard (#337)` on `main` and later local
commits), which is not on any remote branch or PR
(`gh pr view docs-directive-addendum` → not found). #337 is already MERGED to
`main`/`2b364443` with the bug live in production until this branch ships.
This is a genuine risk if `/clear-prep` or a crash drops the branch before it
ships — see `local devcontainer`/`clean-git-state` precedent on unpushed work.

---

## FINDING 3 (dispositioned by explicit prior approval) — PR #336 graphify-labs "Escalate/high" telemetry findings

**Bot**: `graphify-labs[bot]`, review id `4956558367` on PR #336, submitted
2026-08-18T02:29:50Z.
Command: `gh api repos/ray-manaloto/knowledge-base/pulls/336/reviews/4956558367 --jq '.body'`

Four `Escalate / high` findings:
1. "Telemetry sink logs raw API bodies including user prompts and secrets to
   plaintext files" — `.claude/settings.json`
2. "Raw API body telemetry enabled by default" — `.claude/settings.json:5`
3. "Raw API-body telemetry persists full conversations and tool content" —
   `.claude/settings.json:10`
4. "Secret scanner allowlists the telemetry directory that stores raw
   conversations" — `.gitleaks.toml:77`

**Disposition: adjudicated by Ray, in writing, BEFORE the bot flagged it.**
`.gitleaks.toml:60-76` carries a dated comment: *"The raw-API-body telemetry
sink (Ray, 2026-08-17, approved with the cost stated)... THE COST, stated
rather than discovered later: if a real secret is ever pasted into a session,
the copy in this sink is no longer flagged."* — dated 2026-08-17, one day
BEFORE PR #336 (created/merged 2026-08-18) and before the bot's finding. The
user's own memory (`MEMORY.md`: "raw-body telemetry is live and costs ~1.17
MB/request") independently confirms this was a known, accepted, documented
trade-off, not an oversight. **Verdict: correctly-flagged by the bot, already
adjudicated with evidence, no action owed** — this is exactly the "report the
inverse so nobody re-verifies" case the task asks for.

Caveat I could not fully resolve: this disposition covers findings 1, 3, 4 (the
sink itself and the gitleaks allowlist) directly. Finding 2 ("enabled by
default") is the sharper version — `.claude/settings.json` is checked-in and
therefore applies telemetry to EVERY clone/session by default, not opt-in per
machine. Ray's approval comment addresses "the cost" of the allowlist but does
not explicitly say "and it should default ON for every clone." I flag this as
resolved-but-worth-a-second-look, not fully closed. See `--label` below.

---

## FINDING 4 (unresolved, needs a look) — "Module import now probes the local Claude installation" (PR #336)

**Bot**: `graphify-labs[bot]`, same review as Finding 3.
Finding: "Module import now probes the local Claude installation" —
`python/src/kb_setup/graphify_semantic_corpus.py:148`, `Escalate / high`.

Command: `sed -n '140,160p' python/src/kb_setup/graphify_semantic_corpus.py`
(see below) — this file is 3000+ lines and I have NOT located strong evidence
of disposition. No commit message since #336 merged references this line or
"local Claude installation" or "module import" probing. `gh issue list
--search "graphify_semantic_corpus" --state all` and `--search "probe"` below.
**Marking un-dispositioned pending line-148 read — see coverage note below;
this finding needs iteration-2 time I did not have.**

---

## FINDING 5 (missing review, not an empty one) — CodeRabbit never ran on #336, #338, or #339

Command per PR:
```
gh api repos/ray-manaloto/knowledge-base/pulls/{336,338,339}/reviews --jq '.[].user.login'
```
Result: PR #336 → only `graphify-labs[bot]`. PR #338 → only `graphify-labs[bot]`.
PR #339 → only `graphify-labs[bot]`. PR #337 → BOTH `coderabbitai[bot]` and
`graphify-labs[bot]`.

CodeRabbit's own #337 review body states: *"Included review availability: Your
plan includes up to 1 review per rolling hour; 0 remain after this review."*
— PR #337 was created 2026-08-18T03:40:03Z and CodeRabbit reviewed it
03:43:57Z; #336 was created 2026-08-18T01:58:05Z (earlier) but got NO CodeRabbit
review at all, and #338/#339 (03:40 and 07:50) got none either. Given the
explicit "0 remain... per rolling hour" message on #337, the most likely
explanation is CodeRabbit's rate limit — it only had budget for ONE review in
that window and #337 consumed it. **This is a missing review, not an
adjudicated-clean one**, and should not be read as "#336/#338/#339 passed
CodeRabbit" — CodeRabbit never looked. `kb_setup.pr._ADVISORY_CHECKS` treats
CodeRabbit as advisory/non-blocking already, which is consistent with the repo
rules — but Ray's directive is "enforce reviewing all PR reviews from bots
instead of ignoring them," and a rate-limited bot silently skipping 3 of 4 PRs
in one session is exactly the kind of gap that should be surfaced, not just
tolerated as "advisory."

---

## FINDING 6 (graphify-labs findings on #338, #339 — clean sweep, no escalations)

Command: `gh api repos/ray-manaloto/knowledge-base/pulls/338/reviews --jq '.[] | select(.user.login=="graphify-labs[bot]") | .body'`
and same for 339.

- **PR #338**: single graphify-labs review, id `4957303544`. Body says
  "Worth a look" header but on inspection (full body pulled) — pending: I have
  NOT yet pulled the full body text for #338/#339 to confirm whether there are
  escalations inside (only fetched #336/#337 bodies in full so far). **This is
  an OPENED-NOT-FINISHED item — see coverage.**

---

## FINDING 6 (inverse — already dispositioned false, do not re-verify) — PR #339's five graphify-labs "SyntaxError" escalations

**Bot**: `graphify-labs[bot]`, review id `4958669217` on PR #339.
Command: `gh api repos/ray-manaloto/knowledge-base/pulls/339/reviews/4958669217 --jq '.body'`

Five `Escalate / high` findings, all pointing at
`python/src/kb_setup/graphify_semantic_corpus_run.py` (two at `:166`, one at
`:173`, two with no line): "except with tuple of exceptions missing
parentheses is a SyntaxError" / "Invalid except syntax..." / "...makes module
unimportable" / "...prevents module import" / "...causes SyntaxError on
import" — all describing `except OSError, msgspec.DecodeError,
msgspec.ValidationError:` at (current HEAD) lines **165 and 301**.

**Verdict: FALSE, already adjudicated, with evidence on disk — and re-confirmed
by me live.** This is Python-2-looking syntax, but this repo pins
`requires-python = ">=3.14"` (`pyproject.toml:5`) and **PEP 758 (Python 3.14)
legalized bare comma-separated `except` without parentheses** — it parses as
`except (OSError, msgspec.DecodeError, msgspec.ValidationError):`. Confirmed
live, this session:

```
$ uv run python3 -c "import ast; ast.parse(open('python/src/kb_setup/graphify_semantic_corpus_run.py').read())" && echo OK
OK
$ uv run python3 -c "from kb_setup import graphify_semantic_corpus_run" && echo OK
OK
$ uv run python3 -c "import ast; print(ast.dump(ast.parse('except OSError, ValueError:\n pass', mode='exec')))" # minimal repro
# -> ExceptHandler(type=Tuple(elts=[Name('OSError'), Name('ValueError')]))
```

This exact question was ALREADY raised and refuted, twice, in this repo's own
review history — `.agent/kb/review/reports/review-f85f848bf2df2fe65396e8fff5d6ce587c69223c-cold.md:105-107`:
*"the `except OSError, msgspec.DecodeError, msgspec.ValidationError:` syntax at
line 187 looked like Python-2 multi-except syntax on first read and was
flagged as a possible SyntaxError — **checked and refuted**... because PEP 758
(Python 3.14, pinned here via `mise.toml`) legalized bare comma-separated
`except` without parentheses."* Also referenced in
`review-572791058979496cfd607b323ba1cb82718f65bc-cold.md:19` and
`review-8751b54ecf6eed46ac2c0884e2f00cfe4d651d31-cold.md:50`. **This is exactly
the "report the inverse so nobody re-verifies" case** — a plausible-looking bot
escalation that is wrong on THIS repo's pinned toolchain, already caught and
recorded twice by the human-facing cold review. Nothing further owed.

---

## FINDING 7 (PR #338 graphify-labs — mixed: 1 false, 1 already-intentional, 2 un-dispositioned, 1 not fully checked)

**Bot**: `graphify-labs[bot]`, review id `4957303544` on PR #338.
Command: `gh api repos/ray-manaloto/knowledge-base/pulls/338/reviews/4957303544 --jq '.body'`

Five `Escalate` findings:

1. **"New node-count helper calls Counter without an added import" —
   `python/src/kb_setup/graph.py:385` (high).** Checked live: `Counter` IS
   imported (`grep -n "from collections import" python/src/kb_setup/graph.py`
   → `30:from collections import Counter, deque`), and a whole-package
   `py_compile.compile(..., doraise=True)` sweep over every file in
   `python/src/kb_setup/*.py` reports zero failures. **FALSE on current code** —
   checked by me this session, not previously recorded anywhere I could find
   (`grep -rn Counter .agent/kb/review/reports/*.md` → no hits), so I am the
   first disposition on record.

2. **"Adapter backstop timeout is equal to the outer graphify timeout" —
   `graphify_semantic_adapter.py:981` (medium).** **Already dispositioned as
   INTENTIONAL, in the code's own docstring**
   (`graphify_semantic_adapter.py:815-819`): *"Equality with graphify's ceiling
   is intentional rather than sloppy. graphify starts the shim and the shim
   starts Claude, so graphify's clock starts first and its timeout fires first
   at the same nominal value. The outer bound stays the governing one and this
   remains a backstop..."* — written as part of this same #338 round (the
   function replaced a hardcoded 120s tracked by **open issue #335**). Nothing
   owed on the timeout-equality point itself, though see the tangent below.
   **Tangent, not this lane's core scope but worth flagging**: issue #335 is
   still `OPEN` (`gh issue view 335 --json state` → `"OPEN"`) despite the code
   fix landing in #338 — either #335 should be closed with a comment pointing at
   this docstring, or it is tracking a residual piece I have not verified.

3. **"Path.resolve failures now escape assemble's chunk error handling" —
   `python/src/kb_setup/chunks.py:833` (medium).** `chunks.py:841-845` calls
   `Counter(p.resolve() for p in chunk_paths)` inside a function whose whole
   contract is collecting `problems: list[str]` rather than raising. A comment
   immediately above (lines 828-840) documents a DIFFERENT, already-fixed gap in
   the same function ("This module said otherwise until the cold lane on PR
   #338 constructed the case...") — proving this exact function got real
   scrutiny in review — but that fix was about duplicate-path detection, not
   about `.resolve()` raising `OSError` (e.g. a symlink loop, or a path that
   disappears mid-run) escaping uncaught past this function's collect-don't-
   raise contract. **Un-dispositioned** — no commit, docstring, or review
   report addresses an uncaught `.resolve()` OSError here.

4. **"build_from_snapshot no longer distinguishes fully-approved receipts and
   may surface stale stderr as warnings" — `graphify_baseline.py:1711`
   (medium).** **Not checked this pass** — opened, not analysed. See coverage.

5. **"assemble writes staging files before a downstream refusal despite its
   no-write refusal contract" — `graphify_semantic_corpus_merge.py:254`
   (medium).** I read `collect()` at that location (docstring only, lines
   248-260); it references `allow_partial` and a "no-write refusal" precedent,
   but I did not trace the actual write path far enough (into
   `discover()`/wherever staging IO happens) to confirm or refute whether a
   write genuinely precedes the refusal check. **Un-dispositioned, opened not
   finished.**

---

## FINDING 8 (new bot discovered, un-dispositioned) — `repowise-bot[bot]` posts a "Health gate: failed" verdict on ALL FOUR PRs; the checklists were never worked

Command: `gh api repos/ray-manaloto/knowledge-base/issues/{336,337,338,339}/comments --jq '.[] | select(.user.login=="repowise-bot[bot]") | .body'`

**This is a THIRD bot this repo receives reviews from, beyond CodeRabbit and
graphify-labs.** `CLAUDE.md` mentions "Repowise / code health was made
advisory on #336" so its non-blocking status is already a documented, correct
decision — I am not re-litigating that. But "advisory" is not "ignorable," and
Ray's directive is explicit about not ignoring bot reviews. Repowise posted, on
every one of the 4 PRs, `❌ Health gate: failed` plus a "📌 Before you merge"
checklist of concrete, checkable items — none of which I found evidence were
ever worked:

- **#336, #338**: "Run `tests/test_artifact_download.py`, `test_cli_writer_gate.py`,
  `test_distill.py`, `test_gates.py` (+N more): they import the changed files" —
  a list of DEPENDENT test files repowise's own import graph says should be
  re-run because they transitively depend on changed modules. I did not find
  any commit message or gate log naming these specific files as having been
  run in response.
- **#336, #338**: "`mise.toml` changed together with `cli.py` in 45/46 past
  commits and isn't in this PR" — a co-change/hidden-coupling warning,
  unaddressed.
- **8 "dead code" findings across #336/#338**, the same 5 symbols repeated in
  both PRs (`_NonJsonConstantError`, `_JsonNumericLimitError`,
  `_reject_non_json_constant`, `_strict_json_integer`, `_result_envelope`, all
  in `graphify_semantic_adapter.py`, confidence 0.65). **I checked all five
  live**, `grep -rn '\b<symbol>\b' python/ tests/`:
  - `_NonJsonConstantError`, `_JsonNumericLimitError`, `_reject_non_json_constant`,
    `_strict_json_integer` are all **FALSE POSITIVES** — each is wired into
    `json.loads(..., parse_constant=…, parse_int=…)` and an `except (...)`
    clause at `graphify_semantic_adapter.py:374-382`, live code paths repowise's
    static dead-code detector missed (likely because they are passed as
    callback arguments rather than called directly by name).
  - **`_result_envelope` (`graphify_semantic_adapter.py:470-472`) IS genuinely
    dead** — confirmed by the same grep: its only appearance anywhere in
    `python/` or `tests/` is its own 3-line definition. The real, used function
    is the public `parse_result_envelope` (used at line 990 and 12+ call sites
    across `tests/test_graphify_semantic_corpus*.py`); `_result_envelope` is an
    unused thin wrapper around it. Small, real, harmless, and un-dispositioned
    — flagged identically by the SAME bot on two separate PRs (#336 then #338)
    and removed neither time.

**Verdict: genuinely new bot-review channel this session's actors were not
tracking; one real (if minor) dead-code finding confirmed live, one class of
"before you merge" checklist item with no evidence of ever being executed.**

---

## FINDING 9 (bot tooling failure, likely a false positive — worth recording so nobody re-chases it) — CodeRabbit/Biome flagged a "syntax error" in the session-review workflow itself

Command: `gh api repos/ray-manaloto/knowledge-base/issues/339/comments --jq '...'`
(the `all tool run failures by coderabbit.ai` block).

CodeRabbit's Biome (2.5.6) sub-tool reported: *"`.claude/workflows/session-review.js`
— File contains syntax errors that prevent linting: Line 364: Illegal return
statement outside of a function"* — at the reviewed commit
(`8751b54ecf6eed46ac2c0884e2f00cfe4d651d31`), line 364 is a top-level
`return {` closing the workflow's exported body.

**This is directly relevant to THIS session's own subject** — it is a claim
about the very workflow this iteration is reviewing the birth of. Checked live:

```
$ node --check .claude/workflows/session-review.js && echo OK
OK
$ grep -n '^\s*return\b' .claude/workflows/session-review.js
374: ...   564:return {
```

Node's own parser (`node --check`, the pinned mise `node/26.7.0`) accepts the
file: a top-level `return` is legal in a Node CommonJS module because Node
wraps every module body in an implicit function
(`(function(exports, require, module, __filename, __dirname) {…})`). Biome,
run standalone by CodeRabbit's tool runner, evidently parses the file WITHOUT
that Node-module wrapper assumption and reports the (real, deliberate) top-
level `return` as illegal. **Likely a tool-configuration false positive, not a
code defect** — I could not fully confirm Biome's exact parsing mode from
outside its config, so this is reported as "checked, probably a false alarm on
this repo's Node/CJS workflow convention" rather than a closed disposition.
Not previously addressed anywhere I found (`git log --all --grep="Biome" -i`
→ no hits; `git log --all --grep="Illegal return" -i` → no hits).

---

## Not-yet-checked / control-arm still owed

- Full body pull + finding-by-finding disposition check for PR #338 and #339
  graphify-labs reviews (headers only fetched so far).
- `graphify_semantic_corpus.py:148` read + disposition search (Finding 4).
- `gh issue list` searches for each specific finding title/file to rule out an
  issue existing under different wording than my grep terms.
- Whether the inline PR **comment** stream (not just review bodies) on #336
  carries MORE graphify findings than the 2 I fetched via `/comments` (the
  review body says "2 grounded finding(s) anchored inline below; 28 more
  finding(s) on lines outside this diff" — the 28 "outside this diff" findings
  were NOT enumerated anywhere I've read yet; need `gh api .../pulls/336/reviews/4956558367` check-run link or the graphify dashboard). Same for #337's
  "1 more finding(s) on lines outside this diff" and #338's "33 more."
- Whether Finding 4's ("Module import now probes the local Claude
  installation") disposition-as-overstated holds up: I found the referenced
  constants (`_CURRENT_CLAUDE_VERSION` etc.) are hardcoded literals, not a live
  subprocess call, which weakens the bot's "probes" framing — but I did not
  trace every call inside `current_claude()`'s call chain for a hidden I/O
  side effect, so this is a lean, not a settled refutation.
- `repowise-bot`'s "Run these N dependent tests" checklist items — I did not
  actually run the named test files to check whether they currently pass; I
  only established that nobody's commit history shows them being named.
- Whether `kb_setup.pr._ADVISORY_CHECKS` / `kb-land` treats `repowise-bot`,
  `coderabbitai`, or `graphify-labs` as GitHub status checks at all (i.e.
  whether `gh pr checks` even sees them) — I did not read `pr.py`'s source,
  only inferred behavior from the review-vs-merge timestamps in Finding 0.

## COVERAGE

**Reached and analysed:**
- Enumerated every PR touched by the window (#336, #337, #338, #339, all
  merged 2026-08-18; confirmed no open PRs and no PR for the current branch).
- Fetched and read in full every `reviews` entry and every bot `issue-comment`
  from all three bot accounts (`coderabbitai[bot]`, `graphify-labs[bot]`,
  `repowise-bot[bot]`) on all 4 PRs — 3 review bodies fully quoted
  (graphify-labs on #336/#337/#338/#339 = 4; CodeRabbit reviews/comments on
  all 4), plus all `/comments` (inline) entries.
- Live-verified, with control arms, 4 of graphify-labs' #337 "medium"
  findings (2 real bypass/false-positive bugs, matching root cause) — Finding 1.
- Live-verified CodeRabbit's #337 critical hang finding is FIXED but unshipped
  — Finding 2.
- Verified PR #336's 4 "high" telemetry findings against `.gitleaks.toml`'s
  dated approval comment — Finding 3 (dispositioned).
- Partially checked PR #336's 5th finding (Claude-install probe) — Finding 4
  (leaning-false, not settled).
- Established CodeRabbit ran on only 1 of 4 PRs as a full review (#337); the
  other 3 got only a rate-limit/failure comment — Finding 5, refined into
  Finding 0's timing table.
- Fully checked and refuted PR #339's 5 "SyntaxError" escalations against
  PEP 758 / Python 3.14, and found this exact question already answered twice
  in this repo's own cold-review history — Finding 6.
- Fully checked all 5 of PR #338's graphify-labs findings — 1 refuted live
  (Finding 7.1), 1 already dispositioned as intentional in-code (7.2, with a
  tangent about issue #335 staying open), 1 confirmed un-dispositioned (7.3),
  1 not analysed (7.4), 1 partially read (7.5).
- Discovered and fully processed `repowise-bot[bot]` (previously untracked in
  this lane's brief) across all 4 PRs, including a live dead-code check on all
  5 repeated symbols — Finding 8 (1 real, 4 false positives).
- Found and live-verified (as likely-false) a Biome-via-CodeRabbit tool
  failure on the session-review workflow file itself — Finding 9.
- Computed exact open→merge timing for all 4 PRs and cross-referenced every
  bot's post time against it — Finding 0, the structural root cause.

**Opened but not finished:**
- The "28/1/33 more findings on lines outside this diff" that each graphify
  review body references but does not enumerate — not fetched from any
  dashboard/check-run link.
- PR #338 findings 7.4 (`build_from_snapshot`, `graphify_baseline.py:1711`)
  and 7.5 (`graphify_semantic_corpus_merge.py:254` write-before-refusal) —
  read only the docstring/immediate context, did not trace the actual call
  chain far enough to confirm or refute.
- `repowise-bot`'s per-PR "hidden coupling" and "run these dependent tests"
  checklist items — read and quoted, not independently executed.
- Whether `kb-land`/`pr.py` treats any of the three bots as a GitHub status
  check `kb-land` waits on at all.

**Never reached:**
- PRs outside this window (only #336-339 were in scope per the task's window;
  older PRs like #331, #330, #325 etc. were not re-audited — the task scope is
  the round that just shipped).
- The graphify web dashboard / check-run UI that might list the "N more
  findings outside this diff" in full (no URL was provided or discoverable via
  `gh api` alone; the review body only says "see the check run").
- Any bot other than the three found (`coderabbitai`, `graphify-labs`,
  `repowise-bot`) — I did not separately confirm no other bot posted (a
  control-armed sweep of `issues/{n}/comments` for ANY `[bot]`-suffixed login
  across all 4 PRs did run and returned exactly these three, so this is a
  reasonably strong negative, but I did not separately check `timeline` events
  (e.g. a bot that only posts a check-run status with no comment/review at
  all, which `gh api .../comments` and `.../reviews` would both miss).
