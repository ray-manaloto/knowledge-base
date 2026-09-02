# AI CLI Invocation Policy

> **This rule is deliberately EAGER (no `paths:` frontmatter).** It guards an
> *action* — invoking an external AI CLI from Bash — not a file. Path-scoped
> rules "trigger when Claude **reads** files matching the pattern", and no glob
> predicts the moment you are about to shell out to `codex`. In dotfiles it was
> path-scoped until 2026-07-20, which meant it could only fire by accident: a
> session invoked `codex exec "prompt"` positionally (the documented-wrong
> form), wasted a probe on the resulting stdin hang, and only saw the rule
> *afterwards*. See `md-size-budgets.md` § "Scoping: the trigger test" —
> behaviour-triggered rules stay eager.

When calling external AI CLIs from Bash, you MUST use the correct invocation
patterns. Incorrect flags waste tokens and cause silent failures or hangs.

## Which lanes exist here

`mise.toml` pins **`codex`** (OpenAI, GPT-5.6 Sol) and **`antigravity-cli`**
(Google, exposes `agy`). **`grok` is NOT installed** — do not write a fallback
that assumes it. Auth is per-user; mise manages the binaries, not the
credentials. Routing doctrine lives in
`.claude/skills/orchestrator-routing/SKILL.md` and is grounded in this repo's
own graph (`mise run kb-query -- "<routing question>"`).

**`codex` may ALSO do the corpus's LLM work — as graphify's `openai-cli`
BACKEND, never as a lane.** `claude-cli` and `openai-cli` (which shells
`codex exec`) are the two sanctioned extraction backends (`do-not.md` #4; Ray,
2026-08-25), selected only by an explicit `--backend` through
`mise run kb-graphify-native-extract`; graphify's `detect_backend()` never
auto-selects either. `agy` is not a backend. Key-detected backends stay stripped.

## Codex CLI

```bash
# Research/debate (no tool execution, fast):
echo "prompt" | codex exec --sandbox read-only -

# Implementation (with tool execution):
echo "prompt" | codex exec --sandbox workspace-write --add-dir "$HOME/Library/Caches" -

# Implementation that must reach the NETWORK (git ls-remote, kb-update, kb-build,
# gh, any fetch) — add the network flag as well:
echo "prompt" | codex exec --sandbox workspace-write \
  --add-dir "$HOME/Library/Caches" \
  -c sandbox_workspace_write.network_access=true -

# With reasoning effort override:
echo "prompt" | codex exec -c model_reasoning_effort="high" -

# Capture to file (for background use):
cat prompt.md | codex exec -o /tmp/result.md -
```

**`--add-dir "$HOME/Library/Caches"` IS MANDATORY on any lane that runs a gate**
(2026-09-01). `workspace-write` makes only the workspace writable, and uv's cache
lives outside it — so `uv run …` and every uv-backed `mise run …` dies with
`Failed to initialize cache at ~/Library/Caches/uv`, **exit 2**, which reads in a
transcript exactly like the task under test failing.

Two-armed, measured on codex-cli 0.152.0 against `mise run kb-context`:
`codex exec -s workspace-write` -> **rc=2**, the cache error;
the same call plus `--add-dir "$HOME/Library/Caches"` -> **rc=0**, clean output.

This **refutes the standing note** that a codex lane cannot run this repo's gates
at all (memory `codex-lane-cannot-write-agents-or-run-uv-gates`, measured
2026-08-30 through the fable-orchestrator lane wrapper). The uv half was a
missing flag, not a sandbox wall. The `.agents/` half of that note is untouched
and still stands.

**`workspace-write` ALSO BLOCKS NETWORK EGRESS, and that is the second wall**
(2026-09-01). It is a separate mechanism from the write sandbox, so `--add-dir`
does nothing for it — `-c sandbox_workspace_write.network_access=true` is the
switch. Two-armed on codex-cli 0.152.0, `git ls-remote github.com`:
without the flag -> **rc 128**, `fatal: unable to access …: Could not resolve
host: github.com`; with it -> **rc 0**, the tag SHA.

**The failure mode is what makes this expensive**, not the flag. `Could not
resolve host` is the exact signature `persistence-gate-retry.md` classifies as a
TRANSIENT worth one retry. It is not transient here — it is permanent and
structural — so a lane told to "retry once on a network signature" retries,
fails identically, and reports a network outage that does not exist. It cost
**three** dispatches of one lane before the arms were run: the first blamed a
preflight, the second a transient, the third retried the transient and got the
same rc twice. The tell is the disagreement: the same command from an ordinary
shell returns rc 0. **When a lane reports a network failure, run the command
outside the lane before believing it.**

Consequence for routing: **any lane that fetches — `kb-update`, `kb-build`,
`gh`, `git ls-remote`, `mise install`, a doc fetch — needs the network flag, or
it cannot do its job at all.** A read-only analysis lane does not.

**`--full-auto` WAS IN THIS BLOCK AND DOES NOT EXIST.** On codex-cli 0.152.0 it
hard-errors — `error: unexpected argument '--full-auto' found` — so every lane
that followed this rule literally failed at its first call. It is not in
`codex exec --help`. The nearest live flags are `--approve-for-me` (route
approvals through automatic review under the workspace-write sandbox) and
`--dangerously-bypass-approvals-and-sandbox` (no sandbox at all; for externally
sandboxed environments only). This is the second time a flag documented here
aged out silently, which is why the Reference section below says to re-probe the
CLI rather than trust this file.

**`--ephemeral` IS NO LONGER IN THESE PATTERNS** (2026-09-01, Ray). It means
"run without persisting session files to disk", and a lane that persists nothing
cannot be reviewed afterwards — `mise run kb-session-search` (agentsview) reads
`~/.codex/sessions/`, so an ephemeral lane is invisible to it by construction.
Control-armed: with the flag, 0 new session files; without it, +1 at ~104 KB.

Two things this does NOT change, both read from `codex exec --help`: `--ephemeral`
governs persistence ONLY — sandbox, auth and ARG_MAX are separate mechanisms — so
dropping it weakens no isolation. And `resume --last` picks "the most recent
RECORDED session", so ephemeral lanes were never resumable; this adds that.

The cost it DOES carry: lane runs now compete for `resume --last`. Use
`codex exec resume <session-id>`. `--thread-source` is not the mitigation — on
0.151.0 it accepts an invalid value without error, labels the file, and still
leaves the run newest for `--last`.

**WRONG patterns (will silently fail or hang):**

- `codex -p "prompt"` — `-p` is `--profile`, not prompt
- `codex exec "prompt"` — positional arg without the `-` stdin flag
- `codex --full-context` — flag does not exist
- `codex exec --full-auto …` — **removed upstream**; hard-errors on 0.152.0
- `codex exec -s workspace-write …` for anything that runs a gate — **no
  `--add-dir`, so uv cannot open its cache and the gate exits 2**, which looks
  identical to the gate failing

The trailing `-` means "read prompt from stdin". Always pipe prompts via stdin
to avoid ARG_MAX limits on large prompts.

## Antigravity CLI (`agy`)

Drive it through the `antigravity` plugin's skills (`antigravity:delegate`,
`antigravity:review`, `antigravity:research`) rather than hand-rolling flags —
the plugin owns the invocation shape and the cost discipline. Verify the lane
is live with `antigravity:setup` before relying on it.

## Gemini CLI (only if a session has one)

```bash
echo "prompt" | gemini -o text --approval-mode yolo -p ""
# macOS without an API key (avoids Keychain prompts):
echo "prompt" | env GEMINI_FORCE_FILE_STORAGE=true gemini -o text --approval-mode yolo -p ""
```

**WRONG:** `gemini "prompt"` — no headless flag, hangs on interactive input.

## Background Mode Warning

Claude Code's `run_in_background` does NOT reliably capture streaming stdout
from these CLIs. For background tasks use file-based capture
(`codex exec -o /tmp/result.md`), or run in the foreground with an adequate
timeout. See `long-running-command-hangs.md`.

## Reference

**The patterns above ARE the reference — there is no script to consult.**
These flags change between releases, which is how the wrong forms above got
documented in the first place. When a pattern here looks wrong, **re-probe the
CLI itself** (`codex exec --help`, `agy --help`) rather than hunting for a
canonical script, and update this file with what you find.
