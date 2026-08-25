# Long-Running Commands: Never Run Blind — Bound Every Run

Any command that can block on network, IO, a lock, or a prompt MUST be
run with a hard time bound and an observable log. Never start a
potentially-slow command and then wait on it indefinitely.

## Why this rule exists

A `hk run pre-commit --all` invocation once hung at **0% CPU with no child
processes for ~7 hours** before it was noticed. hk has no native timeout, so
nothing aborted it. Worse, it had been launched as `hk ... 2>&1 | tail -40`, so
when it was finally killed the pipeline reported **exit 0** (tail's exit code)
— masking the fact that the gate never actually passed. Two traps in one
incident: unbounded wait + pipe-masked exit code.

## The slow commands in THIS repo

| Command | Why it is slow | How to bound it |
|---|---|---|
| `mise run kb-build` | clones every `sources/*.manifest` at its pinned SHA, then AST-extracts | run it in the foreground and read its progress output; it is deterministic and resumable |
| `mise run kb-add -- <url>` | network fetch into `raw/` | short; a hang means the URL, not the tool |
| `mise run kb-transcribe -- <audio>` | local faster-whisper over a full recording | minutes to tens of minutes; expect it |
| the `kb-extract` workflow fan-out | N Claude subagents | see `agent-report-persistence.md` rule 3 — incremental writes, so a death is partial not total |
| `mise run kb-artifacts` | regenerates every derived view (wiki/graphml/svg/…) | run it alone, not inside another gate |
| `mise run lint` | hk, which has NO timeout of its own | see rule 1 |

## Rules

1. **Prefer `mise run lint` / `mise run test` over raw tool invocations.**
   `mise run lint` runs the **read-only** `hk run check --all` — identical to
   what a reviewer runs, with no silent source rewriting (the fix path is
   `mise run fmt` → `hk fix`). hk itself has no `--timeout` flag, no `timeout`
   step key, and no `HK_*` timeout env var, so a hard bound has to come from
   outside it.

   **"Outside it" has a name, and it is native.** A mise task carries a
   `timeout` key (`task_props.timeout` in the pinned `sources/mise/schema/
   mise-task.json`), so `[tasks.lint]` can bound the hk run that hk cannot bound
   itself. This distinction is worth stating because the sentence above is
   routinely read one clause too wide: **hk** has no timeout; the **mise task
   wrapping hk** does. Same shape as `timeout` — `depends` runs in parallel,
   `wait_for` orders a task only when the other is also running, and
   `-c/--continue-on-error` finishes everything and still reports each failure's
   own exit code. All four were probed against the INSTALLED 2026.8.3, not read
   off a docs page (#248).

   The one thing mise will not give you is **structured** per-task results — `-o`
   offers only human formats — which is why `kb_setup.gates` still owns the
   fan-out that writes `.agent/kb/gates/gates-<sha>.json`.

2. **For any command expected to exceed ~30s, never wait blind.** Either
   bound it with a timeout, or run it in the background and monitor its
   log with a count-diff loop rather than a fixed sleep. Two log files matter
   here: hk writes to `~/.local/state/hk/hk.log`, mise to
   `~/.local/state/mise/mise.log`.

   **The harness caps a single Bash call at ~600s regardless of a larger
   `timeout` argument.** A long in-turn poll loop therefore gets killed at 10
   minutes. Poll in *successive* calls instead of one long one.

   **Do NOT `&`-detach a local `mise run`.** A backgrounded local task gets
   reaped when the turn goes idle — that killed a 20-minute image pull in the
   sibling repo. Use the harness background run (which stays tracked) plus
   in-turn polling. Backgrounding stays correct for *remote* waits
   (`gh pr checks --watch`), which run on GitHub's infrastructure.

3. **Preserve real exit codes — never `cmd 2>&1 | tail -N` to capture.**
   Bash returns the *last* pipeline command's exit code (tail's `0`),
   silently swallowing the upstream failure or kill.

   **For a CHECK, the answer is a task, not a redirect: `mise run kb-check --
   <paths>`** (ruff + format + ty + those paths' own tests, real exit codes) or
   `mise run kb-gates` for the ship gates. Both are python holding a real
   `returncode`, with nothing in between to discard it. The redirect form
   (`cmd > /tmp/out.log 2>&1; echo "rc=$?" >> /tmp/out.log`, then read the file)
   remains correct for a command **no task owns** — a `git`, a `gh`, a one-off.

   Two reasons the redirect stopped being the headline advice. It is shell
   logic, recommended by the repo whose first invariant is `zero-bash-logic`;
   and the escape hatch beside it did not work here at all — **`${PIPESTATUS[0]}`
   is a BASH array**, while this shell is zsh, which spells it `pipestatus` and
   indexes from **1**. Armed both directions in zsh 5.9: the bash form returns
   `''` for a failing gate *and* a passing one, so it cannot discriminate. If
   you must pipe, `${pipestatus[1]}`.

   The habit is measurable and was measured: **35 gate invocations piped into
   `head`/`tail` in one session** (2026-08-08), every one discarding the gate's
   rc — because no task answered "are these two files clean?" until `kb-check`.

3a. **`timeout` DOES NOT EXIST ON macOS, and reaching for it is now DENIED**
   (`kb_setup.absent_binary`, Ray's ruling 2026-08-18). Neither `timeout` nor
   `gtimeout` resolves here — control-armed, `command -v` returns 1 for both
   while `perl` returns `/usr/bin/perl`. That matters far more than a missing
   convenience: the shell answers `command not found` with **rc 127**, which
   lands in a transcript looking exactly like the command under test failing.
   It cost a near-false *"codex unavailable"* — a conclusion about a paid
   external service drawn from a probe that never ran, which is
   `probes-need-a-control-arm.md` rule 4 in its most literal form.

   Bound the run instead, in this order: **the Bash tool's own `timeout`
   parameter** (milliseconds — the native mechanism, and `use-tool-builtins.md`
   says reach for it first); **a mise task's `timeout` key** for anything
   recurring; `perl -e 'alarm shift @ARGV; exec @ARGV' <secs> <cmd> …` for a
   one-off.

   **Why a deny and not this paragraph.** It *was* this paragraph — it reached a
   handoff's own "things that will bite you" list, written by the session it bit,
   and was walked into again. Same measurement as every other guard here: the
   warning-only graph-first rule scored 0 compliance in 19 chances; the deny that
   replaced it took its violations 62 → 0. The guard is host-conditional
   (`shutil.which`), so on a machine where `timeout` exists it is silently inert,
   and `command -v timeout` / `which timeout` are never denied — they are the
   control arm.

4. **A stalled process is a hang — kill it, don't keep waiting.** A
   process sitting at 0% CPU with no children for minutes is wedged
   (blocked on a lock, stdin, or a dead socket), not working. Kill it
   (and its process group), then diagnose from the log tail. Re-running
   under a timeout is cheaper than waiting on a corpse.

4a. **0% CPU WITH a deep child chain is a BLOCKING CHAIN, and it may be a
   RECURSION — read `ps -o pid,ppid` before diagnosing.** Rule 4's signature is
   "no children"; the opposite case reads identically at the top and is a
   different bug. On 2026-08-24 `npm:renovate@44.37.1` made every `mise run`
   here hang. It was recorded as *"mise exits rc=0 and installs nothing — a
   silent-failure defect in mise's npm backend"*, and every observable in that
   sentence was real. One PPID column refuted it: the install was **its own
   descendant**. `node-gyp` on PATH is a **mise shim**, and a shim auto-installs
   missing tools, so `dtrace-provider`'s `node-gyp` postinstall re-entered the
   very install it was part of — one level deeper every ~16 minutes, every level
   blocked on its child, the whole tree at 0.0% CPU. It held mise's install lock,
   which is what starved this repo's SessionEnd hooks into `Hook cancelled`.

   The fix was 12.63 s and touched no pin: kill the process **group**
   (`kill -TERM -<pgid>`), then reinstall with the shim dir stripped from PATH.
   The class is larger than renovate — **any** npm-backend tool whose native
   postinstall calls a binary mise also shims recurses this way while it is
   missing. And note what the wrong diagnosis cost: it was not the hang, it was
   a handoff instructing the next session to export `MISE_DISABLE_TOOLS` forever
   and to treat the fix as someone else's, which put the real one-command remedy
   outside the space that session was searching. **A workaround that works is not
   a diagnosis** — `MISE_DISABLE_TOOLS` even control-armed the finding (2.6 s vs
   >120 s), which is exactly what made it persuasive enough to be written down.

5. **hk specifics.** hk parallelises via per-file read/write locks *within* a
   run. Two log lines look alarming and are not the same thing:
   - `failed to get write locks …` is **DEBUG-level and non-fatal** — a retry
     from whole-repo hygiene steps contending over the first file
     alphabetically. It appears on runs that finish fine.
   - `waiting for <dep>` **is** the wedge. hk never releases a dependent whose
     dependency FAILED, so `depends` + `fail_fast = false` deadlocks. Order
     steps with `exclusive = true` instead; this repo's `hk.pkl` already does,
     and says so.

   **A scary log line adjacent to a hang is not the hang** — confirm a suspect
   by removing it and re-probing.

6. **When lint hangs, ask the narrower gate — `mise run kb-check -- <paths>`.**
   It runs ruff, format, ty and those paths' own tests in seconds, returns a
   real exit code, and never lies about your own code. Then grep the lint output
   for a `❯ <step>` with no matching `✔ <step>` — that names the wedged step
   without reading the whole debug log.

   This rule said *"run the underlying tool DIRECTLY: `uv run ruff check`"* until
   2026-08-18, which **the hook denies** — `kb_setup.check_first` redirects
   exactly that string, so an agent following rule 6 was stopped by a guard rule
   3 of this same file describes. Probed both ways:
   `check_first.decide("uv run ruff check")` returns the redirect,
   `check_first.decide("mise run kb-check -- <path>")` returns `None`. A rule
   instructing a denied command is unfollowable, and it is worse than a missing
   rule because it reads as authority. (Cold review of `c27bddf60480`, P2.)

## Applies to

`hk` (use `mise run lint`), `mise install`, every `kb-*` task, `graphify`
invocations inside those tasks, `gh` waits (use `--watch`, see
`gh-cli-watch.md`), and any other network- or IO-bound command an agent or
human launches in this repo.

## See also

- `gh-cli-watch.md` — sibling rule: use `--watch`, never sleep-poll.
- `verify-before-advancing.md` — evidence discipline: read the real `rc`.
- `mise-tasks-only.md` — the canonical task for each workflow.
