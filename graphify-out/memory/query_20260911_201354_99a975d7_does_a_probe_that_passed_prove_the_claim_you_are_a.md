---
type: "query"
date: "2026-09-11T20:13:54.989144+00:00"
question: "Does a probe that passed prove the claim you are about to publish from it?"
contributor: "graphify"
outcome: "corrected"
correction: "A BOUNDED PROBE IS THE SHAPE THAT KEEPS PRODUCING CONFIDENT WRONG ANSWERS, and\nfive of them landed in one session — four of mine, one from a lane citing the\nvery rule it broke.\n\n1. I proved \"worktrees inherit the flag\" with `git worktree add --detach $WT HEAD`\n   — a worktree of the commit that HAS the flag. `origin/main` has 0. A real\n   worktree branches from main and lacks the FILE. True as run, false as stated.\n2. I reported \"agentsview can verify hook denials — YES\" from a SUBSTRING search\n   that matched my own documentation: 17 hits, anchored 0, and the count grew\n   while we talked because the conversation was being ingested.\n3. I reported 0 of 300 rollouts carrying a `turn_context` because I read `type`\n   from the payload when it sits at top level. The real figure is ~150.\n4. I framed reduced effort as a policy breach. `xhigh` is a DEFAULT; effort comes\n   from the lane assignment. Only the sandbox finding is an unambiguous breach.\n5. A lane's `most_common(12)` hid 3 of 14 buckets — including a second\n   `danger-full-access` row — while citing `probes-need-a-control-arm.md` rule 3,\n   which says display bounds count.\n\nWhat actually caught them, every time: a SECOND READER checking one thing. Astra\ncaught the bucket arithmetic with no file access at all, just by asking whether\nthe printed buckets summed to the stated total.\n\nThree habits earned, each cheap:\n- ASSERT THE MECHANISM LOADED in the same run. Three void arms this session\n  looked exactly like results; the load assertion is what separated them.\n- PICK A TARGET THE ACTOR WILL NOT REFUSE. A lane declined to edit\n  `.claude/settings.json` and the unchanged file read as a successful deny;\n  `mise.toml` is ordinary work and made the arm valid.\n- NAME THE DENOMINATOR. A rate without it is uninterpretable — `danger-full-access`\n  is 8.6% per session or 7.9% per record, and a `turn_context` is per TURN.\n"
---

# Q: Does a probe that passed prove the claim you are about to publish from it?

## Answer

Two programmes were settled and one live policy breach was found.

FUNCTION HOOKS. The blocker was a module that REFUSED TO LOAD because it imported
`node:fs`; a hooks module may import only relative paths and "claude-code". It is
logged at ERROR but surfaced via `$.ui.log`, invisible without `--debug-file`.
The enable gate is four terms, and a tracked `.claude/settings.json` `env` block
sets it in time — verified with the variable absent from the process. The lane
discriminator is `e.agentId` (camelCase); the classic hook spells it `agent_id`,
and a guard reading the wrong one allows everything silently and CANNOT fail
closed, because absence is the allow signal. `on(event, matcher, hook)` is real:
`{tool:"Edit"}` fires on Edit only, which is the #92533 mitigation. The hook body
must be declared at module top level. `$.process.run(argv, {cwd, stdin})` works,
reaches uv, costs ~175ms, and does not re-enter the hook chain — the `stdin`
option is what lets a thin TS shell hand a payload to the existing python
unchanged. Worktree authority belongs to the DESTINATION path, not the caller's
cwd. Function hooks are Claude-only: codex runs `.codex/hooks.json`, so a TS
rewrite duplicates rather than moves, which is why the policy stays python.

A ZERO-COST PROOF THE FLAG IS ON: the bundled `plugin-authoring` skill appears in
the skill listing ONLY when function hooks are enabled. Control-armed against a
skill present either way. It is in every session's own transcript.

CODEX LANE CONFIGURATION IS AUDITABLE, RETROACTIVELY. `~/.codex/sessions/**/*.jsonl`
carries `type: "turn_context"` with `model`, `effort` and `sandbox_policy.type`.
No wrapper, no upstream feature. 151 of 300 newest rollouts carry one; the rest
are UNKNOWN, never compliant-by-default. `turn_context.model` is the REQUESTED
slug — a bogus slug was recorded verbatim — so it answers "configured as declared",
never "which model served the tokens". Auditing it found 13 sessions at
`danger-full-access`, which `do-not.md` #13 forbids (#767).

AGENTSVIEW. Ownership belongs in dotfiles, not a dedicated repo: the effort gap
closes with a PIN BUMP, not a codebase, and dotfiles already owns the agent CLIs.
Its schema has `model` (8 columns) but NO column for effort, sandbox or provider,
out of 483. The effort feature is upstream PR #1677, merged 2026-09-10, in no
release yet — so file nothing; bump and let the documented full resync populate it.


## Outcome

- Signal: corrected
- Correction: A BOUNDED PROBE IS THE SHAPE THAT KEEPS PRODUCING CONFIDENT WRONG ANSWERS, and
five of them landed in one session — four of mine, one from a lane citing the
very rule it broke.

1. I proved "worktrees inherit the flag" with `git worktree add --detach $WT HEAD`
   — a worktree of the commit that HAS the flag. `origin/main` has 0. A real
   worktree branches from main and lacks the FILE. True as run, false as stated.
2. I reported "agentsview can verify hook denials — YES" from a SUBSTRING search
   that matched my own documentation: 17 hits, anchored 0, and the count grew
   while we talked because the conversation was being ingested.
3. I reported 0 of 300 rollouts carrying a `turn_context` because I read `type`
   from the payload when it sits at top level. The real figure is ~150.
4. I framed reduced effort as a policy breach. `xhigh` is a DEFAULT; effort comes
   from the lane assignment. Only the sandbox finding is an unambiguous breach.
5. A lane's `most_common(12)` hid 3 of 14 buckets — including a second
   `danger-full-access` row — while citing `probes-need-a-control-arm.md` rule 3,
   which says display bounds count.

What actually caught them, every time: a SECOND READER checking one thing. Astra
caught the bucket arithmetic with no file access at all, just by asking whether
the printed buckets summed to the stated total.

Three habits earned, each cheap:
- ASSERT THE MECHANISM LOADED in the same run. Three void arms this session
  looked exactly like results; the load assertion is what separated them.
- PICK A TARGET THE ACTOR WILL NOT REFUSE. A lane declined to edit
  `.claude/settings.json` and the unchanged file read as a successful deny;
  `mise.toml` is ordinary work and made the arm valid.
- NAME THE DENOMINATOR. A rate without it is uninterpretable — `danger-full-access`
  is 8.6% per session or 7.9% per record, and a `turn_context` is per TURN.
