---
type: "query"
date: "2026-08-21T21:27:35.530077+00:00"
question: "What writes the six OTEL variables into .codex/config.toml, and why did eleven candidate writers get refuted?"
contributor: "graphify"
outcome: "corrected"
correction: "An unattributed write to a tracked file is NOT evidence that some process on the\ntoolchain did it. Before spending another reproduction round on candidate writers,\nask what is OUTSIDE the candidate set — a GUI app, a sync daemon, a background\nservice, another machine — because a transcript-based attribution tool can only\never see processes that appear in transcripts, and it says so itself.\n"
---

# Q: What writes the six OTEL variables into .codex/config.toml, and why did eleven candidate writers get refuted?

## Answer

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


## Outcome

- Signal: corrected
- Correction: An unattributed write to a tracked file is NOT evidence that some process on the
toolchain did it. Before spending another reproduction round on candidate writers,
ask what is OUTSIDE the candidate set — a GUI app, a sync daemon, a background
service, another machine — because a transcript-based attribution tool can only
ever see processes that appear in transcripts, and it says so itself.
