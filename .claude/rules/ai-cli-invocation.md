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
echo "prompt" | codex exec --ephemeral --sandbox read-only -

# Implementation (with tool execution):
echo "prompt" | codex exec --full-auto --sandbox workspace-write -

# With reasoning effort override:
echo "prompt" | codex exec --ephemeral -c model_reasoning_effort="high" -

# Capture to file (for background use):
cat prompt.md | codex exec --ephemeral -o /tmp/result.md -
```

**WRONG patterns (will silently fail or hang):**

- `codex -p "prompt"` — `-p` is `--profile`, not prompt
- `codex exec "prompt"` — positional arg without the `-` stdin flag
- `codex --full-context` — flag does not exist

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
