# tooling-gap lane — session 096161cc (2026-08-23, 871 lines, single transcript)

Scope: the ONE transcript named in the brief. 50 Bash calls total (`jq` count),
0 hook denials, 0 raw heredoc-imports-of-kb_setup (control-armed: `grep -n '<<'`
does match on this file when a heredoc is present — it found the two git-commit
heredocs at cmd #34/#67 — so the 0-count for `kb_setup` heredocs is a real
negative, not a broken grep).

## FINDING 1 (cost_rank 1) — PR bot-comment reading is a documented, recurring,
un-automated discipline; issue #462 already specs the fix and is still OPEN

This session (cmd #25, #26) hand-built a 3-call `gh api` chain — issue
comments, PR reviews, inline review comments, each with a hand-written `--jq`
projection — then assembled a report by hand into
`.agent/kb/reports/pr-463-bots-read-20260823T0310Z.md` via a `{ … } > "$OUT"`
heredoc-shaped block. This is not a one-off: the handoff that started the
session (`.agent/plans/session-2026-08-22-f.md:15`) NAMES this as a standing
discipline — "Read the bots BY BODY (`updated_at` / body hash — #462:
Repowise and CodeRabbit edit in place; a comment COUNT sees nothing)".

`gh issue view 462` (confirmed OPEN, labels `needs-triage,directive`) already
specs the exact module this session re-implemented by hand: *"A `kb_setup.pr`
reader for bot comments keyed on `(comment id, updated_at | sha256(body))` …
`kb-land` reads and prints every bot's CURRENT verdict at land time … the
receipt/land log records the body hashes it read, so 'we actioned all their
comments' is a checkable claim, not a recollection."* `python/src/kb_setup/pr.py`
has no such reader — confirmed by `grep -n 'gh api\|pulls/.*comments\|reviews'
python/src/kb_setup/pr.py` returning nothing, and `def ` listing in that file
shows no comment/review-reading function.

So the sequence is: #462 filed (a prior session, itself triggered by the SAME
by-hand read on PR #459) → still open → this session did the identical by-hand
read a second time, on a different PR, producing the identical shaped report.
The cost is not just this session's ~10 tool calls; it is that #462's own
acceptance criteria ("a count-based probe in the same run reports 0 — the two
disagree, which is the defect made visible") describes exactly the failure
mode a hand-rolled ad-hoc read cannot self-check, because there is no
`bots.json` last-seen map for it to diff against.

- **remedy**: implement #462 as specced — `kb_setup.pr.bot_comments(pr)` +
  `.agent/kb/pr/<n>/bots.json` last-seen map + a `kb-land`-time print, backed
  by a `mise run kb-pr-bots -- <PR#>` task (or fold the read into `kb-land`
  itself, per #462 item 2). This is not a "propose a new task" finding — the
  ticket already exists and already names the shape; the finding is that it
  keeps getting worked around by hand instead of built.
- **control arm**: `grep -n 'gh api\|pulls/.*comments\|reviews' python/src/kb_setup/pr.py`
  → 0 hits, vs. the same grep against `python/src/kb_setup/gates.py` (which
  DOES own its domain) returning its gate-runner functions — the grep
  discriminates; the absence in `pr.py` is real, not a spelling miss.

## FINDING 2 (cost_rank 2) — posting per-comment replies + a disposition
summary is a SECOND hand-rolled gh-api workflow, not covered by #462 at all

Once the bodies were read, this session (cmd #127) defined a throwaway bash
function `reply() { printf '%s' "$2" > "$SP/reply-$1.md"; gh api -X POST
"$R/$1/replies" -F body=@"$SP/reply-$1.md" --jq '.id'; }` and called it 8 times
(cmd #128–135) with hand-written comment IDs and hand-written bodies, then
(cmd #147) issued a 9th `gh api -X POST … /issues/463/comments` for a
disposition summary comment. This is the same shape #462 addresses for
*reading* but #462's spec (re-read above) never mentions *replying* or
*posting the disposition* — so even a full implementation of #462 would leave
this half by hand.

- **remedy**: extend the same `kb_setup.pr` module (or a sibling
  `kb_setup.pr_bots`) with a `reply(pr, comment_id, body)` /
  `reply_batch(pr, {comment_id: body, …})` and a `post_disposition(pr, body)`
  wrapped in a `mise run kb-pr-reply` task, so a reply round is one command
  fed a small mapping file instead of a hand-defined shell function reinvented
  each time it's needed.
- **evidence**: `grep -n 'replies\|POST' python/src/kb_setup/pr.py` → no hits
  (checked as part of the same `def ` listing above).

## FINDING 3 (cost_rank 1, tied with #1) — kb-session-reflect, the tool this
brief says should be catching exactly this, reported "nothing" this round

This session ran `mise run kb-distill` and `mise run kb-session-reflect`
(cmd #158) as the closing step. `kb-session-reflect`'s own output (captured
via the tool_result for that call) says, verbatim:

```
## Hand-rolled work a mise task already owns

_nothing — every step went through its task_
```

and its "Sequential calls that want ONE wrapper" section lists only
`mise run kb-*` task-name sequences (`kb-handoff-check -> kb-currency-check`,
`lint -> lint`, etc.) — it never surfaces the two `gh api` chains in Findings
1–2 above, even though they are the most clearly repeating, most clearly
un-owned shapes in the whole transcript (one of them tied to an OPEN ticket
that literally describes them). Its "Command shapes repeated inside ONE
session" list is built from normalized shapes (`N`/`Q`/`P` placeholders for
numbers/quoted-strings/paths) which matches things like
`mise run lint N>&N | grep -E Q ; echo Q` (found 2x) but cannot match the
`gh api …/pulls/463/comments --jq '…'` calls because each one's URL, `--jq`
filter, and body differ per call — the STRUCTURE repeats, the TEXT does not,
and the detector appears to key on text-shape only.

This is precisely the complaint the brief quotes Ray making twice: *"i
shouldnt be the one catching this. the session review workflow should have
been flagging this."* It happened again, inside the very tool built to answer
that complaint, in the same session that used the tool.

- **remedy**: this is a defect in `kb_setup.session_reflect`'s shape-matching,
  not (only) a missing task. It needs a `gh api` / `gh pr` specific detector —
  e.g. group Bash commands by `(command_word, first two path segments of the
  API URL)` rather than by full normalized text — so that a sequence of
  differently-parameterized `gh api repos/…/pulls/…/comments` calls is
  recognized as one repeating shape even though no two calls are textually
  identical. Until that detector exists, `kb-session-reflect`'s "nothing"
  verdict cannot be trusted for exactly the class of hand-rolled work (API
  read/write loops with per-call-varying arguments) that costs the most when
  missed.
- **evidence**: tool_result for `toolu_01LWUEVNuLvxSqi9UB4BYgn9` (the
  `kb-distill`/`kb-session-reflect` call), full text captured above; cross-
  checked against the 9 `gh api` invocations enumerated in Findings 1–2
  (`grep -c 'gh api' bash_cmds.txt` → 4 lines containing `gh api`, one of
  which — cmd #127's `reply()` definition plus its 8 call sites — expands to
  8 further POSTs not separately visible as distinct Bash calls since they
  ran inside one shell function invoked 8 times in cmd #128-135, each its own
  Bash tool call).

## FINDING 4 (cost_rank 4, weaker evidence — orientation duplication) —
cmd #5 and #6 re-derive the same facts twice, ~seconds apart

cmd #5 and cmd #6 are both large `&&`/`;` chains checking: `git rev-parse
--short=12` across `HEAD origin/corpus-gate-bundle-rebased main origin/main`,
receipt-file existence for two specific SHAs (`d85f2835`, `85201adb`),
gates-file existence, `claude --version`, a `grep` for
`_CURRENT_CLAUDE_VERSION` in `graphify_semantic_slice.py`, branch listing, and
worktree listing. cmd #6 repeats the ref-resolution and receipt/gates checks
from cmd #5 nearly verbatim (adding only a fallback "NO receipt for …"
message) — the second call produced no new information cmd #5 hadn't already
surfaced for the git-refs/receipts/gates portion.

Neither `uv run kb-setup session-state` (cmd #4) nor `mise run kb-handoff-check`
(cmd #7) — both run adjacent to this pair — cover receipt-existence-for-a-
named-SHA, gates-existence-for-a-named-SHA, or the installed `claude` binary
version; confirmed via `grep -n 'receipt\|gates\|claude.*version' python/src/kb_setup/session_state.py`
turning up only doc-comment mentions, no such check.

This is weaker evidence than Findings 1–3: `mise-tasks-only.md` explicitly
allows ad-hoc `git status`/`gh pr view`/single greps as "ordinary
diagnostics", and this pair IS diagnostic in nature. It is flagged only
because of the exact-duplication (cmd #6 re-running cmd #5's git-ref and
receipt checks with no new inputs) — a cheap thing to have skipped, and a
recurring verification need (does the receipt on file actually cover the SHA
a handoff claims it does?) that `kb-handoff-check`/`kb-session-state` seem
like the natural home for but do not yet cover.

- **remedy**: NOT a new task. Extend `kb-handoff-check` (or `session-state`)
  with an optional `--verify-sha <sha>` that reports receipt+gates existence
  for a named commit plus the resolved refs, so this two-call pattern
  collapses into the one call that was already running right next to it.
  Low priority relative to Findings 1–3.

## Observed but NOT reported as a gap (checked, found adequately covered)

- `pipestatus` usage (cmd #19, #32, #33, #101, #154): every `| tail`/`| grep`
  pipe in this transcript correctly reads `${pipestatus[1]}` (zsh spelling),
  matching `long-running-command-hangs.md` rule 3 exactly — no violation to
  report.
- Backup-branch cleanup (cmd #150–151: diffing `corpus-gate-bundle-0821` /
  `corpus-gate-bundle-rebased-pre0823` against `main`, then `git branch -D`):
  occurs once in this transcript (n=1). Per the brief's "propose nothing a
  single existing task already does" instruction, and given only one
  occurrence here, this is NOT reported as an automation candidate — noted
  only as something to watch if it recurs.
- No hook denials fired this session (`permissionDecision` count 0), and no
  raw `graphify` invocation, blanket `git add`, hand-chained ruff/ty, or
  secret-printing command was attempted — all guarded surfaces this session
  touched were used correctly.

## GitHub repos touched

_None._ (No external repo research this session — orientation, review-fix,
PR-bot handling, and clear-prep only, all within this repo.)
