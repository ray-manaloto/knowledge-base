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
   step key, and no `HK_*` timeout env var, so if you need a hard bound put one
   outside it.

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
   silently swallowing the upstream failure or kill. Redirect to a file
   (`cmd > /tmp/out.log 2>&1; echo "rc=$?" >> /tmp/out.log`) and read the
   file + the recorded `rc`. Trust file content, not a piped tail.

4. **A stalled process is a hang — kill it, don't keep waiting.** A
   process sitting at 0% CPU with no children for minutes is wedged
   (blocked on a lock, stdin, or a dead socket), not working. Kill it
   (and its process group), then diagnose from the log tail. Re-running
   under a timeout is cheaper than waiting on a corpse.

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

6. **When lint hangs, run the underlying tool DIRECTLY.** `uv run ruff check`
   takes seconds and never lies about your own code. Then grep the lint output
   for a `❯ <step>` with no matching `✔ <step>` — that names the wedged step
   without reading the whole debug log.

## Applies to

`hk` (use `mise run lint`), `mise install`, every `kb-*` task, `graphify`
invocations inside those tasks, `gh` waits (use `--watch`, see
`gh-cli-watch.md`), and any other network- or IO-bound command an agent or
human launches in this repo.

## See also

- `gh-cli-watch.md` — sibling rule: use `--watch`, never sleep-poll.
- `verify-before-advancing.md` — evidence discipline: read the real `rc`.
- `mise-tasks-only.md` — the canonical task for each workflow.
