# The lanes: prompts, fallback, receipt

## Standards — `general-purpose`

```text
Review the diff `git diff <FIXED>...HEAD` in this repository.
Commits: <git log --oneline output>

Standards sources, read them all: <the rule-file paths gathered in step 3> and CLAUDE.md.
Smell baseline (you have no other access to it): <paste references/smell-baseline.md in full>

Report, per file/hunk:
(a) every place the diff violates a DOCUMENTED standard — cite the rule file and
    the specific rule;
(b) any baseline smell — name it and quote the hunk.

Distinguish hard violations (a documented standard breached) from judgement
calls (every baseline smell is one). A documented repo standard overrides the
baseline. Skip anything `mise run lint` already enforces.

Cite file:line for every finding. A finding you cannot cite, label `unverified`
and keep — do not drop it and do not promote it.

Under 400 words. Do not edit any file.
```

## Spec — `general-purpose`

```text
Review the diff `git diff <FIXED>...HEAD` in this repository.
Commits: <git log --oneline output>

The spec this change is meant to implement: <path(s), or the fetched issue body>

Report:
(a) requirements the spec asked for that are missing or only partial;
(b) behaviour in the diff nobody asked for (scope creep);
(c) requirements that look implemented but where the implementation looks wrong.

Quote the spec line for each finding, and cite file:line in the diff.

Under 400 words. Do not edit any file.
```

If no spec was found, skip this lane and record `spec:no-spec-available` in the
receipt's skipped list. Reviewing against an invented spec is worse than not
reviewing: it produces findings that look grounded and are not.

## Cold — `fable-orchestrator:codex-reviewer`

**By ref, and cold.** Hand it the range and nothing else:

```text
Review <FIXED>...HEAD in this repository. Read the diff yourself.
Return a findings list: severity, a one-line claim, and file:line for each.
Cite every claim or label it unverified.
```

Do **not** tell it what the change was for. That is the point of the lane — a
reviewer given the design intent confirms the happy path, which is the failure
mode a second lens exists to break. It shares no weights with Claude, so its
blind spots are different ones.

### The fallback chain — loud at every step

| Step | Lane | Family |
|---|---|---|
| 1 | `fable-orchestrator:codex-reviewer` | OpenAI (GPT-5.6 Sol) — cross-family |
| 2 | `antigravity:review` / `antigravity-delegate` | Google (Gemini 3.x) — cross-family |
| 3 | a Claude Opus subagent | **same family as the author** |

Step 3 is a real fallback and never a silent one. Record it as
`cold:claude-fallback-SAME-FAMILY` in the receipt. A same-family cold read still
catches things — a fresh context with no design intent is worth something — but
it is not the cross-family check the lane is named for, and a receipt that
implies otherwise is a lie told to a future reader.

Both CLIs are pinned in `mise.toml` (`codex`, `antigravity-cli`) and auth is
per-user, so "installed" is not "authenticated". The plugin agents return a
structured error rather than substituting themselves; treat that error as
"advance the chain", not as "no findings".

## Silent failures — `pr-review-toolkit:silent-failure-hunter`

Give it the same range. It looks for swallowed exceptions, bare `except`,
fallbacks that mask a real error, and error paths that log-and-continue where
they should fail.

Two things in this repo are **deliberate** and must not be reported as findings
— check the reasoning is intact rather than flagging the shape:

- `kb_setup.hook_guard` **fails open on its own errors.** A crashed PreToolUse
  guard must not brick every Bash call. That is a documented trade, not a
  swallowed error.
- `kb_setup.pr.checks_state` **fails closed on an unparsable payload.** Output
  it cannot parse means the question was never asked, which must never authorise
  a merge.

They point opposite directions on purpose. A lens that flags either one has
found the shape and missed the reasoning; a lens that finds one of them
*inverted* has found a real defect.

## The receipt

`.agent/kb/review/receipt-<sha>.json`, written by
`mise run kb-review-receipt`:

```json
{
  "sha": "9521853...",
  "written_at": "2026-07-28T02:14:09Z",
  "fixed_point": "main",
  "lanes_ran": ["standards", "spec", "cold:codex", "silent-failure"],
  "lanes_skipped": [],
  "findings": 3,
  "blocking": 0
}
```

`lanes_skipped` entries carry their reason —
`cold:not-applicable-docs-only`, `spec:no-spec-available`,
`cold:claude-fallback-SAME-FAMILY`. **A skip with no reason is not a skip, it is
a gap**, and `kb-ship` rejects a receipt containing one.

**A lane claimed as RUN must have left a report** at
`.agent/kb/review/reports/review-<sha>-<lane>.md`, non-empty. Without that the
whole receipt was honor-system: one command with four lane names minted full
coverage having run nothing, which is the widest form of a hole whose narrower
forms had already been closed twice. It raises the bar rather than proving
anything — a stub file still passes — but the honest path is now the easy one.

**Only two skip reasons excuse a lane**: `not-applicable-<why>` and
`no-spec-available`. `not-yet-run` is a **gap** and is rejected, which is what
the paragraph above already said and the first version of the gate did not
enforce.

**The lane set is CLOSED** (`kb_setup.review.LANES`), and all four must be
accounted for — each either ran or was skipped with a reason. Both halves of
that matter, and the first draft had neither: the gate only checked that
`lanes_ran` was non-empty, so `--lanes placeholder --blocking 0` satisfied it,
and `--lanes standards` quietly bought a pass for three lanes that never ran.

That hole was found by the **cold lane, reviewing this feature's own first
commit** — after the module's unit tests were green over it. It is the argument
for the lane, arrived at by accident rather than by construction, so it is
recorded here rather than smoothed away.

## Spawning: prefer an UNNAMED subagent

A *named* teammate needs a tmux pane, and panes run out — measured at 18 open,
most of them finished agents whose panes persist. Two lanes failed to spawn that
way on the first real run, and `tmux kill-pane` is not always permitted.

An **unnamed** `Agent` call runs in the background without a pane and is the
default here. For the cold lane there is a second route that needs no agent at
all: drive the CLI directly, per `ai-cli-invocation.md` —

```bash
cat prompt.txt | codex exec --ephemeral --sandbox read-only -
```

Record that variant honestly as `cold:codex-cli-direct`: same model and the same
coldness, but not the plugin agent, so it lacks the plugin's structured-error
fallback and a hang shows up as a hang.

**A lane that could not be spawned is `not-yet-run`, never `not-applicable`.**
The first is a gap; the second is a judgement that the lane had nothing to say.
Writing the second when you mean the first is how a receipt reports coverage it
does not have.

`blocking > 0` fails the ship gate. Everything else is reported and does not
block — the review's job is to put findings in front of a human, not to
adjudicate taste.

The receipt is gitignored. It proves *this machine* reviewed *this commit*, and
an amend or rebase moves the SHA and invalidates it — correctly, because the
reviewed bytes are gone.
