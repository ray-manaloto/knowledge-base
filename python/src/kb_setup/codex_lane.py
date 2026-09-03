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

#: The subcommands that spend the subscription, edit the tree, or route around
#: the guard stack. Codex 0.152.1 has **28**; these are the ones where being
#: wrong costs money, files, or the guards themselves.
#:
#: Ray's constraint (2026-09-03): *"we only have a chatgpt/codex subscription
#: plan (so only cli) / we cant use or have access to anything that requires an
#: api key"*. So this set is scoped to CLI subcommands reachable on a
#: subscription. Guarding one we cannot run costs nothing — the guard simply
#: never fires — while missing one we CAN run is the failure this exists to stop.
#:
#: - `exec` `review` `resume` `fork` `queue` `cloud` — spend the subscription and
#:   need all four flags. `resume`/`fork` matter as much as `exec`: a resumed
#:   lane without `--dangerously-bypass-hook-trust` runs with the guard stack
#:   SILENTLY OFF, which is the exact defect #672 was filed for.
#: - `apply` — literally `git apply` onto the working tree. Nothing in this repo
#:   or in dotfiles guards destructive git today (measured 2026-09-03), so this
#:   is the only thing standing in front of it.
#: - `sandbox` — runs arbitrary commands, which routes around EVERY Bash guard
#:   here (`check_first`, `graph_first`, `secret_guard`, `inplace_edit`,
#:   `stage_explicitly`). Denied here as the immediate remedy; the general class
#:   — a command-running wrapper defeats a command-inspecting guard — is filed
#:   separately rather than being recorded as solved by this one line.
_GUARDED_SUBCOMMANDS = frozenset(
    {"exec", "review", "resume", "fork", "queue", "cloud", "apply", "sandbox"}
)

#: A help/version FLAG exempts the segment outright — asking a guarded
#: subcommand for its usage spends nothing.
_HELP_FLAGS = frozenset({"--help", "-h", "--version", "-V"})

#: Introspection SUBCOMMANDS: never denied. `codex mcp login <name>` is the
#: sanctioned way to authenticate a server and `codex mcp list` is how you read
#: the Auth column — a guard that refused the procedure it protects would be
#: worse than no guard, the lesson `secret_guard`'s ALLOW set pins with half its
#: test file.
#:
#: 🔴 `app-server` WAS IN THIS SET AND DID NOT BELONG. Its own help says *"Run
#: the app server or related tooling"* — it starts a daemon, it does not report
#: state. Combined with the old rule that an introspection token ANYWHERE in a
#: segment exempted the whole segment, `codex app-server exec …` sailed past.
#: That was a hole of my own making, found by enumerating the real subcommand
#: list rather than by any test. Both halves are fixed: `app-server` is no
#: longer introspection, and exemption is now decided by the SUBCOMMAND POSITION
#: rather than by any token happening to appear.
_INTROSPECTION_SUBCOMMANDS = frozenset(
    {"mcp", "login", "logout", "completion", "agents", "doctor", "features", "help"}
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
        # A help/version FLAG exempts the segment: asking a guarded subcommand
        # for its usage spends nothing. Judged per segment, so another command's
        # `--help` cannot excuse the lane beside it.
        if any(word in _HELP_FLAGS for word in rest):
            continue
        # Find the FIRST token that is a known subcommand, guarded or not, and
        # let that one decide. Scanning all tokens rather than taking the first
        # non-flag one is deliberate: `codex --cd /tmp exec "..."` reached the
        # binary undenied under the first-non-flag rule, because `--cd`'s VALUE
        # (`/tmp`) was read as the subcommand and `exec` was never looked at.
        # Any value-taking flag before the subcommand did it — not an evasion
        # technique, just how people write the command. 18 unit tests passed over
        # that hole; driving the real CLI found it on the second probe.
        #
        # Deciding on the FIRST known subcommand rather than on "is any guarded
        # word present" is what closes the second hole: `codex app-server exec`
        # used to be exempted by `app-server`, and `codex mcp list` must stay
        # allowed. First-wins gives both the right answer without a special case.
        #
        # The residual false positive is a bare token spelled exactly like a
        # subcommand that is NOT one — a directory argument named `exec`, say.
        # `shlex` has already collapsed any quoted prompt into ONE token, so
        # prose mentioning exec cannot trip it, and `/path/to/exec` is a
        # different token. That residue is accepted against a false NEGATIVE,
        # which defeats the guard's entire purpose.
        known = _GUARDED_SUBCOMMANDS | _INTROSPECTION_SUBCOMMANDS
        hit = next((word for word in rest if word in known), None)
        if hit in _GUARDED_SUBCOMMANDS:
            return _REMEDY.format(sub=hit)
    return None
