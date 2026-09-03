# Copyright (c) 2026 Raymond Manaloto
"""Deny a raw `codex exec` and redirect it to `mise run kb-codex`.

**Why this guard exists, measured rather than argued.** `ai-cli-invocation.md`
lists four flags a codex lane needs, and every one of them was learned by a lane
failing in a way that looked like the thing under test failing:

- `--add-dir "$HOME/Library/Caches"` — without it `uv` cannot open its cache and
  every uv-backed gate exits **rc 2**, indistinguishable from the gate failing.
- `-c sandbox_workspace_write.network_access=true` — without it a fetching lane
  reports `Could not resolve host`, which `persistence-gate-retry.md` classifies
  as a TRANSIENT worth one retry. It is not transient, it is structural, and it
  cost **three** dispatches of one lane before the arms were run.
- `--dangerously-bypass-hook-trust` — without it this repo's hooks are **skipped
  silently**, because codex records trust against each hook's HASH. Measured
  2026-09-03: this repo has 3 trusted `pre_tool_use` entries and **0**
  `post_tool_use`, so the `apply_patch`→ty hook shipped in `cbc66c54` does not
  fire at all. This is the flag Ray had to point out (#672).
- `-` — the prompt comes from stdin, or a large prompt hits ARG_MAX.

A lane can be wrong by OMISSION on any of them, and the failure never says so.
One task owning the flags is the fix; this guard is what makes the task
unavoidable, because a rule that only *warns* does not work here — the
warning-only graph-first directive scored **0 compliance in 19 chances**, while
the deny that replaced it took its violations **62 → 0**.

**There is a second, unrelated reason, found while writing this.** `mise exec --
codex` resolved **0.152.1** while a bare `codex` on the same PATH resolved
**0.152.0** — the session's PATH held an install directory rather than a shim.
A task routed through mise always gets the pinned version; a bare `codex exec`
gets whatever that shell happened to bake in.

Scope is narrow on purpose, and follows `check_first`'s precedent:

- Only `exec` and `review` — the two subcommands that spend tokens and act.
- `--version`, `--help`, `mcp`, `login`, `logout` and the other introspection
  subcommands are never denied; they are how you inspect the lane.
- Anything containing `mise run kb-` is allowed outright, because the task
  itself shells out to codex.
- It TOKENISES via `check_first.segments`/`command_word` rather than
  pattern-matching, so `git commit -m "run codex exec"` is one quoted token and
  can never sit at a command position. Every confirmed false positive on this
  repo's guards has been that shape.
"""

from __future__ import annotations

from kb_setup import check_first

#: The subcommands that actually spend tokens and act on the repo. `exec` is the
#: lane; `review` is the same engine pointed at a diff (#672 U2 is deciding
#: whether it becomes the `kb-review` cold lane — either way it needs the flags).
_GUARDED_SUBCOMMANDS = frozenset({"exec", "review"})

#: Introspection: never denied, and deliberately including the whole `mcp`
#: family. `codex mcp login <name>` is the sanctioned way to authenticate a
#: server and `codex mcp list` is how you read the Auth column — a guard that
#: refused the procedure it protects would be worse than no guard, which is the
#: lesson `secret_guard`'s ALLOW set already pins with half its test file.
_INTROSPECTION = frozenset(
    {"--version", "-V", "--help", "-h", "mcp", "login", "logout", "completion", "app-server"}
)

_REMEDY = (
    "Do not run `codex {sub}` directly — use `mise run kb-codex` instead.\n"
    "\n"
    "The task owns the flags a lane cannot be right without, and each one was\n"
    "learned from a lane failing in a way that looked like something else:\n"
    '  --add-dir "$HOME/Library/Caches"          (else every uv gate exits rc 2)\n'
    "  -c sandbox_workspace_write.network_access  (else a fetch reports a fake outage)\n"
    "  --dangerously-bypass-hook-trust            (else THIS REPO'S HOOKS ARE SKIPPED,\n"
    "                                              silently — 0 trusted post_tool_use)\n"
    "  -                                          (prompt on stdin, not ARG_MAX)\n"
    "\n"
    "It also runs codex through mise, so the lane gets the PINNED version rather\n"
    "than whatever this shell's PATH baked in (measured skew: 0.152.1 vs 0.152.0).\n"
    "\n"
    '  mise run kb-codex -- "<prompt>"                 # read-only analysis\n'
    '  mise run kb-codex -- --write "<prompt>"         # workspace-write\n'
    '  mise run kb-codex -- --write --network "<...>"  # + network egress\n'
    "\n"
    "`codex --version`, `codex --help` and the whole `codex mcp` family are\n"
    "introspection and are never denied."
)


def decide(command: str) -> str | None:
    """Return the remedy when `command` runs a guarded codex subcommand, else None.

    Never raises: a crashed guard must not brick every Bash call, so the caller
    (`hook_guard`) also wraps this, and an unparsable command degrades to None
    rather than to a deny.
    """
    if not isinstance(command, str) or not command.strip():
        return None

    # The task shells out to codex itself, so anything going through it is fine.
    if "mise run kb-" in command:
        return None

    parsed = check_first.segments(command)
    if parsed is None:
        # `shlex` could not parse it. Degrade to allowing rather than denying —
        # the same trade `check_first` makes, and for the same reason: this is a
        # redirect guard, not a sandbox.
        return None

    for tokens in parsed:
        words = check_first.command_word(tokens)
        if not words or words[0] != "codex":
            continue
        rest = words[1:]
        # An introspection token ANYWHERE in this segment exempts it, judged per
        # segment so another command's `--help` cannot excuse the lane beside it.
        if any(word in _INTROSPECTION for word in rest):
            continue
        # Scan EVERY token, not just the first non-flag one.
        #
        # The first-non-flag version shipped and was defeated within minutes by
        # an ordinary invocation: `codex --cd /tmp exec "..."` reached the binary
        # undenied, because `--cd`'s VALUE (`/tmp`) is the first non-flag token
        # and `exec` was never looked at. Any value-taking flag before the
        # subcommand did it — not an evasion technique, just how people write
        # the command. 18 unit tests passed over that hole; driving the real CLI
        # found it on the second probe.
        #
        # The residual false positive is a bare token spelled exactly `exec` or
        # `review` that is NOT the subcommand — e.g. a directory argument of
        # that exact name. `shlex` has already collapsed any quoted prompt into
        # ONE token, so prose mentioning exec cannot trip it, and a path like
        # `/path/to/exec` is a different token. That residue is accepted against
        # a false NEGATIVE, which defeats the guard's entire purpose.
        hit = next((word for word in rest if word in _GUARDED_SUBCOMMANDS), None)
        if hit is not None:
            return _REMEDY.format(sub=hit)
    return None
