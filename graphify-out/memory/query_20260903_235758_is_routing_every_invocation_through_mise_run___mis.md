---
type: "query"
date: "2026-09-03T23:57:58.037680+00:00"
question: "Is routing every invocation through mise run / mise exec a complete answer to stale tool resolution?"
contributor: "graphify"
outcome: "corrected"
correction: "# `mise exec` is NOT the complete answer to tool resolution — refuted 2026-09-03\n\n**The belief**, stated in this repo's rules and repeated by me to Ray twice this\nround: routing every invocation through `mise run` / `mise exec` fixes the\nstale-PATH class, so the resolution problem is solved and only discipline\nremains.\n\n**What refuted it.** `mise exec` fixes every path THIS REPO CONTROLS — its own\n`kb-*` tasks. It does not reach a bare `codex` issued by the\n`codex@openai-codex` plugin, the `fable-orchestrator` implementer lane, or an\nMCP server spawned with the inherited environment. Those are precisely the\ncallers that ran **codex-cli 0.152.0** during this session while `mise.toml`,\n`mise.lock` and `sources/codex.manifest` all said 0.153.1.\n\n**The root cause is not mise at all.** `~/.claude/shell-snapshots/snapshot-zsh-<id>.sh`\nis 1,825 lines and its FINAL line is a literal `export PATH='…'` naming\n`npm-openai-codex/0.152.0`. Every Bash tool call is a fresh `zsh -c` that\nre-sources that one file, re-asserting a value captured once at session start.\nControl-armed: that line holds `0.152.0` (1 hit), not `0.153.1` (0), and a bogus\nversion returns 0.\n\n**And the freeze predates the bump it was blamed on** — the snapshot held\n0.152.0 while the pin was still 0.152.1, so the session was already running a\nbinary no config named before any of this round's work. A terminal restart would\nhave hidden that rather than revealed it.\n\n**A subagent cannot see this.** A cold review lane reported \"current host state\nshows no such skew today\" at the same moment the main session measured the skew.\nNeither probe was broken — they read different environments, because the frozen\nPATH belongs to the Bash tool and not to the machine. So a lane can neither\nconfirm nor refute this class of finding, and asking one to is how a real\ncondition gets written off.\n\n**How to apply.** Tracked as #702 (a `SessionStart` hook writing one stable line,\n`export PATH=\"$HOME/.local/share/mise/shims:$PATH\"`, into `CLAUDE_ENV_FILE`,\nwhich Claude Code runs before every Bash command) and #705 (the callers\n`mise exec` cannot reach). Until #702 ships, a new terminal is the only fix, and\n**which lanes actually run the stale binary is an open question, not a settled\none** — measure per lane type rather than assuming.\n"
---

# Q: Is routing every invocation through mise run / mise exec a complete answer to stale tool resolution?

## Answer

# Phase U step 0 (resolution half) + the codex 0.153.1 resync — 2026-09-03

Landed as PR #707, squash `b1d92a56`, from four commits reviewed cold at
`1a99a161` (`cold:codex`, 2 findings / 0 blocking).

## What shipped

**A three-fact resolution check.** `currency/sync.py` asked one question — what
would a BARE call in this process reach — and reported one answer, so a stale
shell PATH and a genuinely wrong install produced the same DRIFT. It now also
asks `mise which` and `mise exec -- <bin> --version`, deep-path only, and the
pair separates "this shell is stale" from "the pinned version is not installed".
The shallow path cannot reach a subprocess at all: the finding row is ABSENT
rather than SKIP when `deep=False`, so the SessionStart contract holds by
construction rather than by a flag someone must honour.

**codex resynced to 0.153.1** across `mise.toml`, `mise.lock` and
`sources/codex.manifest`, the manifest pinned to the PEELED tag commit
`98564127…` because `rust-v0.153.1` is annotated (#500). `mise use` moved both
the pin and the lock row; it was armed on a scratch copy first because
`mise config set` is recorded here as eating comments — it does not, exactly one
line of 1674 changed.

**The patch-level gate removed**, on Ray's ruling: *"we always want to be on the
latest version"*. It measured digit position rather than risk — codex
`0.152.1 -> 0.153.1` blocked while mise `2026.9.0 -> 2026.9.1` passed, purely
because calver puts a release in the patch slot — and nothing could ever clear
it, unlike the tracked-issue gate.

## The finding worth carrying

Deleting that gate whole would have opened two holes, both measured rather than
reasoned: `_has_upgrade("1.0.5", "1.0.2")` is True, so a DOWNGRADE would have
self-applied; and `same_release("main", "feature-x")` is False, so two strings
that are not versions at all read as an upgrade. One function was doing three
unrelated jobs and only one of them was the job under review. What replaced it,
`_gate_readable`, keeps the other two and tests nothing for size.

The general shape: **before removing a check, enumerate what it does, not what it
is named.** A gate's name describes the job someone objected to; its body may be
carrying others silently.


## Outcome

- Signal: corrected
- Correction: # `mise exec` is NOT the complete answer to tool resolution — refuted 2026-09-03

**The belief**, stated in this repo's rules and repeated by me to Ray twice this
round: routing every invocation through `mise run` / `mise exec` fixes the
stale-PATH class, so the resolution problem is solved and only discipline
remains.

**What refuted it.** `mise exec` fixes every path THIS REPO CONTROLS — its own
`kb-*` tasks. It does not reach a bare `codex` issued by the
`codex@openai-codex` plugin, the `fable-orchestrator` implementer lane, or an
MCP server spawned with the inherited environment. Those are precisely the
callers that ran **codex-cli 0.152.0** during this session while `mise.toml`,
`mise.lock` and `sources/codex.manifest` all said 0.153.1.

**The root cause is not mise at all.** `~/.claude/shell-snapshots/snapshot-zsh-<id>.sh`
is 1,825 lines and its FINAL line is a literal `export PATH='…'` naming
`npm-openai-codex/0.152.0`. Every Bash tool call is a fresh `zsh -c` that
re-sources that one file, re-asserting a value captured once at session start.
Control-armed: that line holds `0.152.0` (1 hit), not `0.153.1` (0), and a bogus
version returns 0.

**And the freeze predates the bump it was blamed on** — the snapshot held
0.152.0 while the pin was still 0.152.1, so the session was already running a
binary no config named before any of this round's work. A terminal restart would
have hidden that rather than revealed it.

**A subagent cannot see this.** A cold review lane reported "current host state
shows no such skew today" at the same moment the main session measured the skew.
Neither probe was broken — they read different environments, because the frozen
PATH belongs to the Bash tool and not to the machine. So a lane can neither
confirm nor refute this class of finding, and asking one to is how a real
condition gets written off.

**How to apply.** Tracked as #702 (a `SessionStart` hook writing one stable line,
`export PATH="$HOME/.local/share/mise/shims:$PATH"`, into `CLAUDE_ENV_FILE`,
which Claude Code runs before every Bash command) and #705 (the callers
`mise exec` cannot reach). Until #702 ships, a new terminal is the only fix, and
**which lanes actually run the stale binary is an open question, not a settled
one** — measure per lane type rather than assuming.
