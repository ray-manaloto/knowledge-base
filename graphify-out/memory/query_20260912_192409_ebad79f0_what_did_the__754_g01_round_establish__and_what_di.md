---
type: "query"
date: "2026-09-12T19:24:09.227417+00:00"
question: "What did the #754 G01 round establish, and what did its own audit find wrong with it?"
contributor: "graphify"
outcome: "corrected"
correction: "**The belief overturned: that a green gate, a passing probe and a measured number\nare evidence. In this round each was refuted while looking correct.**\n\nFive of the round's own claims were refuted by review, not by me:\n\n1. **A gate green only because of WHERE it ran.** `kb-mod-runtime-check` depended\n   on `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, injected by the harness into a Claude\n   Code session and set nowhere in the repo. It had 11/11 gates and 11/11 arms.\n   **An arms sweep is a claim about the TESTS; it cannot see a missing premise.**\n\n2. **Three consecutive fixes to one defect, each broken differently.** Fixed\n   `/tmp` path -> `mktemp -d` (unguessable, so a dead lane's verdict is\n   unfindable — defeating the file's stated purpose) -> a name/session-keyed path\n   (measured: concurrent siblings SHARE the scratchpad, `$TMPDIR` and the session\n   id) -> a `${VAR:?}` guard inside a `\\` continuation (became positional\n   arguments; the guard never fired and the redirect was orphaned). Only the\n   third was caught by running `zsh -n` instead of reading.\n\n3. **An inherited number published inside the audit commissioned to find them.**\n   I told every lane a six-word `kb-recall-work` query returns 0. Re-measured: 49,\n   never zero. The mechanism was real; the figure was repeated, not derived.\n\n4. **A probe that ran and an output nobody opened — twice.** Phase-0\n   `kb-recall-work` NAMED the tracked report containing three findings I then\n   reported as new. The tool worked; I read the summary counts.\n\n5. **My own verification probe was wrong too**, flagging five files as broken\n   because the assignment line also contained a use of the variable.\n\n**The operative rule: a disagreement between two probes is the cheapest defect\ndetector available, and in this round the broken side was mine every time.**\nThree separate lane disagreements each found a real bug that neither probe found\nalone. Corollary, learned again: run a claim's command OUTSIDE the lane before\nbelieving a lane's failure — `graphify-out/memory/query_20260901_235935_…` had\nrecorded exactly that eleven days earlier, and it went unread.\n"
---

# Q: What did the #754 G01 round establish, and what did its own audit find wrong with it?

## Answer

# Round kb-20260911.004 — #754 G01, and a session-wide audit that found the round's own defects

## What shipped

`4cdd8bfb` — `kb-mod-runtime-check`: generates the function-hook declarations at
the INSTALLED Claude Code and reconciles them against a contract MECHANICALLY
DERIVED from `register.ts`. 11/11 gates, 11/11 arms died, control held.

`c33a1fb5` — the P1 fix for that gate, the lane-scratch fix, nine directives
recorded verbatim, and 19 research reports promoted into tracked `docs/`.

## The finding that matters most

**A gate can be green because of WHERE it ran.** `kb-mod-runtime-check` passed
only inside a Claude Code session: `/plugin-types` does not exist without
`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, declared in `.claude/settings.json` and
injected by the harness, and set in NEITHER the task NOR the module. Stripped,
the gate returned rc 1 reading "the runtime contract regressed" when the truth
was "the question was never asked" — a MISCLASSIFICATION, not merely a false red.

The commit that shipped it claimed the gate "needs the BINARY, never credentials".
Incomplete: the binary AND the feature flag.

## What the round established, measured

- The function-hooks migration is VIABLE: `anthropics/claude-code#92533` is
  specific to `tool.call` on Bash; `tool.check` fires on Bash, denies with our
  own reason, and leaves worktree isolation intact — four arms, positive control.
  Verdict nonetheless: not worth building today.
- `next.origin` is host-set and unforgeable (`claude-code.d.ts:3841-3846`), so
  tier-based authority is real enforcement, not decoration.
- The tool event family is exactly five; `tool.result` DOES NOT EXIST, and a hook
  registered on it reads "clean" — a non-existent event and a safe event are
  indistinguishable to a passthrough probe.
- Codex lanes CANNOT query the graph (#778) — four of four failed on a mise
  sandbox permission error and silently fell back to grepping. That is the
  mechanical cause of the "agents grep instead of query" complaint.
- Every harness-derived identity a lane can read about itself is SHARED with
  concurrent siblings — scratchpad path, `$TMPDIR`, `$CLAUDE_CODE_SESSION_ID`,
  measured with an echo control. Only the caller can allocate a unique path.
- `kb-advisor` has NO Write tool; the work-memory recommending it as the durable
  substitute was wrong when written.
- The 283 "lost" Claude sessions survive in agentsview's archive, control-armed.

## The round's own accounting

147 findings inventoried; 20 had a durable home, 127 did not. 19 reports were
promoted to `docs/research/reports/2026-09-12-function-hooks-round/` in response.


## Outcome

- Signal: corrected
- Correction: **The belief overturned: that a green gate, a passing probe and a measured number
are evidence. In this round each was refuted while looking correct.**

Five of the round's own claims were refuted by review, not by me:

1. **A gate green only because of WHERE it ran.** `kb-mod-runtime-check` depended
   on `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, injected by the harness into a Claude
   Code session and set nowhere in the repo. It had 11/11 gates and 11/11 arms.
   **An arms sweep is a claim about the TESTS; it cannot see a missing premise.**

2. **Three consecutive fixes to one defect, each broken differently.** Fixed
   `/tmp` path -> `mktemp -d` (unguessable, so a dead lane's verdict is
   unfindable — defeating the file's stated purpose) -> a name/session-keyed path
   (measured: concurrent siblings SHARE the scratchpad, `$TMPDIR` and the session
   id) -> a `${VAR:?}` guard inside a `\` continuation (became positional
   arguments; the guard never fired and the redirect was orphaned). Only the
   third was caught by running `zsh -n` instead of reading.

3. **An inherited number published inside the audit commissioned to find them.**
   I told every lane a six-word `kb-recall-work` query returns 0. Re-measured: 49,
   never zero. The mechanism was real; the figure was repeated, not derived.

4. **A probe that ran and an output nobody opened — twice.** Phase-0
   `kb-recall-work` NAMED the tracked report containing three findings I then
   reported as new. The tool worked; I read the summary counts.

5. **My own verification probe was wrong too**, flagging five files as broken
   because the assignment line also contained a use of the variable.

**The operative rule: a disagreement between two probes is the cheapest defect
detector available, and in this round the broken side was mine every time.**
Three separate lane disagreements each found a real bug that neither probe found
alone. Corollary, learned again: run a claim's command OUTSIDE the lane before
believing a lane's failure — `graphify-out/memory/query_20260901_235935_…` had
recorded exactly that eleven days earlier, and it went unread.
