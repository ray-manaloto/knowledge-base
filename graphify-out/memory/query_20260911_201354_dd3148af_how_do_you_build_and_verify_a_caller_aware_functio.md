---
type: "query"
date: "2026-09-11T20:13:54.355161+00:00"
question: "How do you build and verify a caller-aware function-hook guard, and what can codex rollouts prove about lane configuration?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you build and verify a caller-aware function-hook guard, and what can codex rollouts prove about lane configuration?

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

- Signal: useful