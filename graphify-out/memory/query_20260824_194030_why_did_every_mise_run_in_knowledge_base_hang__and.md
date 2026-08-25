---
type: "query"
date: "2026-08-24T19:40:30.678414+00:00"
question: "Why did every mise run in knowledge-base hang, and were the project hooks broken?"
contributor: "graphify"
outcome: "corrected"
correction: "A hang at 0.0% CPU whose process tree contains ITSELF is a recursion, not a\nstall -- and the diagnosis that reaches the handoff is usually the one nobody\nran `ps -o pid,ppid` against.\n\nThe prior session recorded: \"`mise install npm:renovate@44.37.1` exits rc=0 with\nno output and installs nothing -- a silent-failure defect in mise's npm backend.\"\nEvery observable in that sentence was real. The conclusion was wrong. mise was\nnot failing silently; it was blocked on a child that was blocked on a\ngrandchild that was re-entering mise. One `ps -o pid,ppid,pgid` showed the\ninstall as its own descendant, and that single field -- PPID -- was the whole\ndiagnosis.\n\nThree durable rules fall out:\n\n1. **0.0% CPU across an entire process tree is a BLOCKING chain, not idleness.**\n   Something at the bottom is waiting, and every ancestor is waiting on it. Read\n   the ancestry before concluding anything about the top-level command.\n2. **A mise shim auto-installs.** Any tool whose native postinstall calls a\n   binary mise also shims will recurse whenever that tool is missing. The class\n   is much larger than renovate; `node-gyp` is merely the most common shimmed\n   build tool. Breaking the recursion means removing the shim from PATH for the\n   duration of the install, not changing the pin.\n3. **A workaround that works is not a diagnosis.** `MISE_DISABLE_TOOLS` made the\n   symptom go away and control-armed the finding (2.6s vs >120s), which is\n   exactly why it was persuasive enough to be written into a handoff as the\n   standing remedy. It survived into the next session as required setup for a\n   problem that a 12-second install would have ended.\n\nThe cost of the wrong diagnosis was not the hang. It was that the handoff told\nthe next session to export an env var forever, and told it the fix belonged to\nsomeone else's config -- so the actual one-command fix was outside the space the\nnext session was looking in.\n"
---

# Q: Why did every mise run in knowledge-base hang, and were the project hooks broken?

## Answer

# Why did every `mise run` in knowledge-base hang, and were the project hooks broken?

Two separate causes, one symptom. Neither was what the prior session recorded.

## 1. The mise wedge was an INFINITE RECURSION, not a silent mise no-op

`npm:renovate@44.37.1` in the user's global `~/.config/mise/config.toml` could not
finish installing. Read straight off `ps -o pid,ppid,pgid`:

    bun install renovate@44.37.1 --global --linker hoisted   (pgid 93040)
     |- bash -c "node-gyp rebuild || node suppress-error.js"  (dtrace-provider postinstall)
        |- node-gyp -> sh -c "... bash build.sh" -> node-gyp rebuild -C src
           |- bun install renovate@44.37.1 --global --linker hoisted   <- RECURSION
              |- ... the same chain again, one level deeper every ~16 minutes

`node-gyp` on PATH is a **mise shim** (`~/.local/share/mise/shims/node-gyp` ->
`~/.local/bin/mise`). A shim auto-installs missing tools before dispatching.
`npm:renovate` was missing, so every `node-gyp` call re-entered the renovate
install, whose `dtrace-provider` postinstall calls `node-gyp` again. Each level
blocks on its child, so the whole tree sat at 0.0% CPU for 1h44m -- which is why
it read as a hang rather than a loop, and why it held mise's install lock
forever. That lock is what refused `mise update-all` and cancelled the project's
SessionEnd hooks.

**Fix, with no edit to the user's config -- the pin was always fine:**

    kill -TERM -93040
    cd /tmp && PATH="<mise/shims stripped>" mise install npm:renovate@44.37.1

12.63s, rc=0, "Blocked 1 postinstall" (bun's untrusted-postinstall gate kept
node-gyp from ever running). Control arm: 2.6s WITH `MISE_DISABLE_TOOLS` vs
>120s timeout WITHOUT, before the fix; 2.5s with no workaround at all, after.

`MISE_DISABLE_TOOLS="npm:renovate"` is now dead advice.

## 2. The project hooks were never broken -- they were starved

All 7 hook commands verified live, every one far inside its declared budget:

| hook | budget | measured |
|---|---|---|
| PreToolUse `graphify hook-guard search` | 15s | 0.071s |
| PreToolUse `kb-setup hookguard` | 20s | 0.113s deny / 0.106s allow |
| PreToolUse `graphify hook-guard read` | 15s | 0.063s |
| SessionStart `kb-currency-check` | 30s | 2.5s |
| SessionStart `kb-telemetry-prune` | 30s | 0.884s |
| SessionEnd `brain-transcript-audit` | 60s | 1.089s |
| SessionEnd `kb-session-reflect` | 60s | 0.187s |

`kb-setup hookguard` was control-armed BOTH directions: denied `graphify extract .`
with the canonical task, allowed `git status --short` with zero output.

## 3. `update:check` in the global config could not fail on brew

Its description promised "exit 1 if anything is outdated", but only
`mise upgrade --dry-run-code` set the exit code; `brew outdated --json` and
`mise outdated --json` were printed and never gated. Fixed under an explicit
override, with three distinct exit codes (0 clean / 1 outdated / 2 COULD NOT
CHECK). A/B on identical stubbed input: old body rc=0, new body rc=1.

## 4. The 24 red tests were re-explained, and the ruling is being re-asked

graphify #2900 added `.html` to `_SPLITTABLE_TEXT_SUFFIXES`, so a 1,846,390-byte
excluded file that used to arrive as ONE non-splittable unit now arrives as ~93
`FileSlice` units (derived: 1,846,390 / 20,000). The guard at
`graphify_semantic_corpus.py:1392` refuses rather than under-count by (N-1).
Its own comment predicted exactly this: the invariant is "safe only because every
entry ... today is a non-splittable single-unit file."

The catalogue entry is CORRECT. The stale thing is kb_setup's own single-unit
assumption about exclusions.


## Outcome

- Signal: corrected
- Correction: A hang at 0.0% CPU whose process tree contains ITSELF is a recursion, not a
stall -- and the diagnosis that reaches the handoff is usually the one nobody
ran `ps -o pid,ppid` against.

The prior session recorded: "`mise install npm:renovate@44.37.1` exits rc=0 with
no output and installs nothing -- a silent-failure defect in mise's npm backend."
Every observable in that sentence was real. The conclusion was wrong. mise was
not failing silently; it was blocked on a child that was blocked on a
grandchild that was re-entering mise. One `ps -o pid,ppid,pgid` showed the
install as its own descendant, and that single field -- PPID -- was the whole
diagnosis.

Three durable rules fall out:

1. **0.0% CPU across an entire process tree is a BLOCKING chain, not idleness.**
   Something at the bottom is waiting, and every ancestor is waiting on it. Read
   the ancestry before concluding anything about the top-level command.
2. **A mise shim auto-installs.** Any tool whose native postinstall calls a
   binary mise also shims will recurse whenever that tool is missing. The class
   is much larger than renovate; `node-gyp` is merely the most common shimmed
   build tool. Breaking the recursion means removing the shim from PATH for the
   duration of the install, not changing the pin.
3. **A workaround that works is not a diagnosis.** `MISE_DISABLE_TOOLS` made the
   symptom go away and control-armed the finding (2.6s vs >120s), which is
   exactly why it was persuasive enough to be written into a handoff as the
   standing remedy. It survived into the next session as required setup for a
   problem that a 12-second install would have ended.

The cost of the wrong diagnosis was not the hang. It was that the handoff told
the next session to export an env var forever, and told it the fix belonged to
someone else's config -- so the actual one-command fix was outside the space the
next session was looking in.
