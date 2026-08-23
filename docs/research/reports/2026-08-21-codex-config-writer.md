# What writes `.codex/config.toml` — the answer, after eleven refuted candidates

> **Caller's annotation, 2026-08-23 — promotion, not an edit.** This report was
> written on 2026-08-21 and lived only at `.agent/codex-config-writer-answer.md`,
> which is gitignored. Four tracked issues cite the finding (#399 primary, plus
> #345, #374, #435), so it is load-bearing and a citation to a file only one
> machine can open is not a citation. Copied here verbatim under
> `agent-report-persistence.md` 1b; the `.agent/` original stays disposable.
>
> **It also retires a work item that was still on the backlog.** The 2026-08-23
> execution plan lists a `.codex/config.toml` writer-hunt lane under U7 as
> missing, because the phrase appears zero times in the plan — which is true of
> the plan and false of the world: the hunt was already discharged two days
> earlier. The general writer-attribution lane still has value; this specific
> question does not need it.
>
> **And it explains why `mise run kb-attribute-write` cannot reproduce it today.**
> The file's current mtime is `2026-08-21 16:26`, which is the investigation's own
> `git checkout --` revert, not the writer's touch. Pointed at that timestamp the
> instrument returns the reading session investigating itself — a probe aimed at a
> moment a later remediation overwrote.

---

The writer of the recurring `.codex/config.toml` mutation is the **ChatGPT desktop
app's "Import from another AI app" feature, running with "Keep imports in sync"
(autosync) enabled**. It is not any process in this machine's dev toolchain.

Evidence (Ray, 2026-08-21, from the app's own Import screen): the Import history
reads "Imported from Claude Code — Aug 21, 2026, 4:11 PM · 9 imported", and names
both files explicitly — `.claude/settings.json` as source and `.codex/config.toml`
as destination. 4:11 PM matches the file's measured mtime
`2026-08-21T21:11:12.047288+00:00` to the second.

It is a FAITHFUL COPY, not a mis-generation. The six variables
(`CLAUDE_CODE_ENABLE_TELEMETRY`, `OTEL_LOG_USER_PROMPTS`,
`OTEL_LOG_ASSISTANT_RESPONSES`, `OTEL_LOG_TOOL_DETAILS`, `OTEL_LOG_TOOL_CONTENT`,
`OTEL_LOG_RAW_API_BODIES`) already sit in `.claude/settings.json`'s `env` block,
committed deliberately in `37f6a1c5` (2026-08-17). The importer translates that
block verbatim into `.codex/config.toml`'s `[shell_environment_policy.set]`.

Three properties make it damaging rather than untidy: the destination is TRACKED,
so `git add -u`/`-A` sweeps it into unrelated PRs; AUTOSYNC means a revert is not
durable; and it presents as an unexplained mid-session mutation of a config file.

WHY ELEVEN CANDIDATE WRITERS WERE REFUTED across two prior incidents: every probe
was scoped to processes this repo runs. `kb-attribute-write` scanned one transcript
in a +/-12s window and returned only the reading session's own activity, 60 ms
AFTER the write — its own caveat ("a transcript cannot see a process spawned
earlier that wrote later") was exactly right. No transcript, `pgrep` or
lane-liveness probe can see a GUI application on a sync timer.

Mitigation in place: `.codex/config.toml` reverted to its committed state and set
`chmod 444`. Armed both directions — an append is refused on it, and the same
append succeeds on a writable file in the same tree, so the probe discriminates.
`git checkout` still works on the read-only file and preserves the mode. It is a
SPEED BUMP, NOT A GUARD: the owner can `chmod u+w` it back, and an importer
running as the same user can do the same. Do not read a quiet week as proof the
mitigation held.

The real fixes are upstream and outside this repo: turn "Keep imports in sync"
off in ChatGPT desktop, and/or have the app stop writing another tool's tracked
config. Tracked here in #399 (primary), #345, #374, #435.
