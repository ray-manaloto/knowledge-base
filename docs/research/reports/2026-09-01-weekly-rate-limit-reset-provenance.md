# Claude Code weekly rate-limit reset provenance (Phase N0e)

Date researched: 2026-09-01

## Scope and evidence discipline

This is a read-only research lane. I changed no tracked file; the only file I
wrote was this report. No commit or pull request was created. At lane start,
pre-existing working-tree changes were present in `.claude/CLAUDE.md`,
`.claude/rules/ai-cli-invocation.md`, and two untracked HTML artifacts under
`docs/artifacts/`; they were not modified. By the final check, concurrent work
had also changed `currency.toml`, `sources/anthropic-sdk-python.manifest`, and
`sources/claude-code.manifest`, and added another untracked HTML artifact. Those
changes were not made or modified by this lane.

The repository graph was queried first, twice, using `mise run kb-query`. Both
queries failed closed with exit code 3 because Graphify returned incomplete,
truncated results. Both runs also emitted:

- `mise WARN tool purgatory cleanup failed: Operation not permitted (os error 1)`
- a note that the graph uses the pre-#1504 node-ID scheme and should be rebuilt
  with `graphify extract --force` for path-qualified IDs
- an explicit warning that the truncated prefix is not evidence of absence

Therefore the graph is unavailable as authority for this question. The findings
below use the repository transcript-search task and direct source inspection as
fallback authority.

## Transcript-search method and bounds

### Required task and environment failure

I invoked `mise run kb-session-search` with every requested spelling:
`rate limit`, `rate_limits`, `resets_at`, `weekly reset`, `/usage`, `seven_day`,
and `statusline rate`; I also tried the RE2 pattern
`(?i)(weekly reset|seven_day|resets_at|statusline.{0,40}rate)`. Every invocation
included `--include-children`. None used `--since` or a project filter.

The first calls could not sync because this lane cannot write AgentsView's
default `~/.agentsview/debug.log` or `serve.log`. Setting
`AGENTSVIEW_DATA_DIR=/Users/rmanaloto/Library/Caches/kb-n0e-agentsview` fixed
that path problem, but the sandbox then denied every loopback port in
127.0.0.1:8080-8179. With `AGENTSVIEW_NO_DAEMON=1`, a full direct sync succeeded,
but `kb-session-search`'s search phase still refused with:

> fatal: daemon autostart is disabled; direct SQLite reads are not supported for
> this command.

Thus no zero-result output from the repository wrapper is used as evidence.
This is an environment-forced fallback, not a successful task result.

### Fresh index and read-only fallback

The pinned AgentsView 0.41.1 binary performed a fresh foreground scan with
daemon autostart disabled. It discovered 6,789 sessions and reported 6,769
synced. The progress stream was output-truncated, but its terminal report
retained these parser qualifications:

- 10,389 fields had control characters stripped.
- Six `gen_metadata without usage` anomalies occurred, all for Antigravity
  sources (one `antigravity`, five `antigravity-cli`), not Claude/Codex.
- The sync summary printed `Database: 3721 sessions, 433730 messages`, but an
  immediate read-only SQL census of the resulting database returned 6,769
  sessions and 539,032 messages. This internal summary mismatch is retained as
  version/tool drift; the SQL census is the actual database state searched.

The fallback searched the normalized `messages`, `tool_calls.input_json`, and
`tool_calls.result_content` columns directly in read-only SQLite mode. For the
two requested agents it covered 5,802 sessions / 483,135 messages: 2,120 Claude
and 3,682 Codex, including 2,949 child sessions and 180 automated sessions.
Those rows report zero malformed lines and zero truncated sessions. The 425
rows in AgentsView's `skipped_files` table all belong to other agent families;
none point under `~/.claude` or `~/.codex`.

There was no time, date, project, agent-kind, interactive-only, or child-session
bound. The literal result counts were:

| Pattern | Matching records | Distinct Claude/Codex sessions |
| --- | ---: | ---: |
| `rate limit` | 3,213 | 1,114 |
| `rate_limits` | 624 | 184 |
| `resets_at` | 192 | 62 |
| `weekly reset` | 32 | 7 |
| `/usage` | 2,449 | 750 |
| `seven_day` | 114 | 28 |
| `statusline rate` | 4 | 2 |

The repository wrapper always supplies a result limit: 50 by default and 500
maximum (`python/src/kb_setup/agentsview.py:239-253`). It also forwards
`--include-children` and, unless explicitly narrowed, adds one-shot and
automated sessions (`python/src/kb_setup/agentsview.py:206-231`). I requested
500 on the later calls. `rate limit` and `/usage` exceed
that bound, and `rate_limits` exceeds it at record level, so a wrapper result
would not prove exhaustive matches for those broad forms. The direct SQL counts
above do not have that result-row bound. The current Phase N0e prompt itself
contains every target spelling, so current-session hits were excluded when
selecting the prior conclusion.

### Control arms

- The transcript investigation produced positive historical matches, so it does
  not make the negative claim that no prior session discussed the subject.
- For the narrower `~/.claude` active-state search, the target spelling group
  `seven_day|five_hour|resets_at|rate_limits|weekly_all|unified-7d` returned no
  active core state file after excluding transcripts, history, backups,
  file-history, plugins, and the stale `.omc` snapshot. The identical search
  shape for known-present `statusLine` found `settings.json`,
  `statusline.mjs`, and `subagent-statusline.sh` (plus plans/transcripts).
- For the OpenTelemetry documentation, the target spelling group
  `rate_limits|seven_day|resets_at|unified-7d` returned zero lines. The identical
  file/search shape for known-present `claude_code.token.usage` found lines 476,
  1160, 1177, and 1187. This controls the claim that the documented OTel schema
  has no reset timestamp.

## Prior-session conclusion

Yes. The definitive prior work is Claude session
`f7719b2d-29cc-4acd-9599-e177ae307572`, started 2026-08-14 with cwd
`/Users/rmanaloto/.claude`; transcript:
`~/.claude/projects/-Users-rmanaloto--claude/f7719b2d-29cc-4acd-9599-e177ae307572.jsonl`.

The session first concluded, incorrectly, that no local source existed. It
inspected the retired OMC implementation, then successfully called
`GET https://api.anthropic.com/api/oauth/usage` with a Claude OAuth token and
the `anthropic-beta: oauth-2025-04-20` header (message ordinals 548-556;
transcript line 2092). A live response contained
`seven_day.resets_at = 2026-08-19T12:00:00.199960+00:00` (transcript line 2237).
It built a background API/cache subsystem around that result.

The user then asked whether a complete statusline schema existed. Reading the
official schema revealed the missing conditional field. The first live probe
still appeared negative because it was captured before the first API response
(`total_api_duration_ms: 0`). A longer live probe captured a post-response
render and proved the payload contained the same rate-limit values (message
ordinals 674-684).

The final conclusion, quoted from assistant message ordinal 704 / transcript
line 2552, was:

> **`rate_limits` ships in the payload** — I built ~60 lines of Keychain reads,
> API calls, cache files, locks and background refreshes for data Claude Code
> was already handing me.

That session then removed the credential/network/cache implementation and
reported zero remaining network, credential, cache, or background-process
references. Its important caveat was that rate limits are blank until the
session's first API response and are exposed by this contract only for eligible
subscription contexts.

Earlier corroborating work exists:

- Claude child session `agent-a746e415ea73d1219` and sibling
  `agent-ab19e034a765ba68c` (2026-08-05) found the bundled construction of the
  statusline `rate_limits` object, including `seven_day.resets_at`.
- The 2026-09-01 session `91a91cb9-3eb4-4457-b40c-c7c9d7defef8` rediscovered
  that Ray's script reads the field, but stopped at “rendered, not persisted.”
  It did not recover the August session's stronger conclusion until this lane.

## Current implementation verification

I read `~/.claude/statusline.sh` in full (296 lines), read-only. The three given
facts are correct, with these exact current lines:

1. The script consumes the entire render payload from stdin at
   `~/.claude/statusline.sh:14`. Its one `jq` extraction spans `:29-74`.
   `rl5`/`rl5r` and `rl7`/`rl7r` are declared at `:34-35`, populated from the
   five-hour fields at `:63-64` and the seven-day fields at `:65-66`.
2. The header says it reads only stdin plus one Git call at
   `~/.claude/statusline.sh:2`, and “No plugin, no network, no credentials, no
   cache, no background processes” at `:3`. Full-file inspection found no
   persistence path; the payload is used for string rendering and discarded.
3. Rate-limit rendering begins at `~/.claude/statusline.sh:229-230`. Both
   windows are iterated at `:241-255`. The reset countdown is gated by
   `if (( _int >= 50 ))` at `:251` and appended only at `:252-253`. The
   percentage remains visible below 50%; only the countdown is suppressed.

The current official statusline source independently documents that Claude Code
sends fields via stdin (`sources/claude-code-docs/content/en/docs/claude-code/statusline.md:168-194`),
that `rate_limits` is conditional and stale windows are dropped (`:320-331`),
and that the seven-day `resets_at` is Unix epoch seconds (`:808-814`).

## Ways the reset time can be obtained

### 1. `/usage` and host UI — supported, human-facing

`/usage` is the supported direct answer. The CLI error guide says it shows plan
limits and when they reset
(`sources/claude-code-docs/content/en/docs/claude-code/errors.md:506-515`). The
VS Code Account & usage dialog explicitly shows the session/week bars and how
long until each resets (`.../vs-code.md:160-164`). Once a limit is exhausted,
the CLI's limit message itself shows the reset (`.../errors.md:491-502`).

Reachability: a human can invoke/read these interactive surfaces. A normal
conversation agent cannot dispatch the host TUI's slash command; it can ask the
human to run `/usage`, or an explicitly authorized UI-control lane could operate
the host. `/usage` is not an agent-readable file/API surface by itself.

### 2. Statusline stdin payload — supported, programmatic but ephemeral

After the first API response, eligible Claude.ai subscriber sessions receive
`rate_limits.seven_day.resets_at` as Unix epoch seconds on every applicable
statusline invocation. Claude Code also re-runs the statusline when the stored
window reaches `resets_at`
(`sources/claude-code-docs/content/en/docs/claude-code/statusline.md:139-152`).

Reachability: the configured statusline process can read it directly. A human
can see what that process renders. The conversation agent cannot recover a past
stdin frame unless the process deliberately persists or exposes it. Ray's
current script does neither, and hides only the countdown below 50% usage.

### 3. Authenticated usage endpoint — works, but is an internal/credentialed route

The August session empirically proved that
`GET https://api.anthropic.com/api/oauth/usage` returns `five_hour` and
`seven_day` objects with `resets_at`. The vendored HTTP-spec research also marks
that endpoint runtime-confirmed
(`sources/claude-code-http-spec/archive/ALL-API-ENDPOINTS.md:456-465`).

Reachability: a human or an explicitly authorized program/agent with the Claude
OAuth credential and network access can call it. A normal repo agent should not:
this repository's secret guard forbids credential extraction, and the endpoint
is not presented here as a stable public automation API. The prior statusline
implementation used it only temporarily and then deleted that subsystem once
the payload route was proven.

### 4. Messages API response headers — real, but below the normal agent surface

The vendored runtime testing observed
`anthropic-ratelimit-unified-5h-reset` and
`anthropic-ratelimit-unified-7d-reset` on Messages API responses
(`sources/claude-code-http-spec/archive/ENDPOINT-TESTING-REPORT.md:186-200,
289-312`). These are the raw request-response route from which a host client can
obtain the exact reset without `/usage` or a statusline.

Reachability: a custom authenticated client, gateway, proxy, or harness that
receives raw response headers can read them. Claude Code consumes the headers
internally, but does not expose them as ordinary Bash/tool input to the
conversation agent. The header research is a vendored reverse-engineering
artifact rather than a promised public Claude Code agent interface, so names
should be reverified across versions before building a durable integration.

### 5. `~/.claude` files — no current authoritative reset file

The documented `stats-cache.json` holds aggregate token/cost history, and
`usage-data/` holds `/insights` reports, not subscription reset timestamps
(`sources/claude-code-docs/content/en/docs/claude-code/claude-directory.md:1548-1558,
1628-1636`). Neither path exists on this machine at the time of this lane.

A controlled active-state search found no current core file containing the
reset keys. One exception is historical only:
`~/.claude/.omc/state/hud-stdin-cache.json`, modified 2026-08-14 17:25 local,
contains the old payload for session `f7719b2d-...` including old five-hour and
seven-day resets. It is exactly the retired OMC-era snapshot from the prior
work, is stale, and is not updated by today's statusline. Transcripts,
`history.jsonl`, backups, and file-history contain discussions or old code, not
the live reset value.

Reachability: an agent can read those files if policy permits, but none yields
the current reset. A stale snapshot is provenance evidence, not a current data
route.

### 6. OpenTelemetry — not a reset-time route in the documented schema

Claude Code's documented OTel metrics cover session count, lines, PRs, commits,
cost, tokens, edit decisions, and active time
(`sources/claude-code-docs/content/en/docs/claude-code/monitoring-usage.md:467-478`).
The API-error event exposes status code and request IDs but not quota headers
(`:690-712`). Even `OTEL_LOG_RAW_API_BODIES` exports request/response **bodies**,
not response headers (`:740-772`). The controlled search described above found
no `rate_limits`, `seven_day`, `resets_at`, or unified-7d field in the complete
monitoring document.

Reachability: if OTel is configured, a human or agent with access to the
collector can analyze the documented usage/cost/activity data, but cannot read
the weekly reset from that schema. This repo enables telemetry and detailed
content flags but does not set an exporter in that file
(`.claude/settings.json:5-10`). A live check of
localhost:4317 was inconclusive because the sandbox denied the socket operation,
so this lane does not claim whether an exporter configured elsewhere is active.

## Definitive answer

Claude Code learns the weekly reset from its authenticated usage/quota response
and hands the normalized value to eligible sessions as
`rate_limits.seven_day.resets_at` in the JSON sent to the configured statusline
command after the first API response. That is the already-worked-out answer.

For a human, run `/usage` (or use the VS Code Account & usage dialog); those are
the supported surfaces and show the time remaining/reset. For a program, read
the statusline stdin field. Ray's current statusline already does that, but it
does not persist the payload and hides the reset countdown while weekly usage
is below 50%, so an ordinary conversation agent cannot recover today's current
timestamp from disk. Raw Messages API unified 7-day headers and the authenticated
`/api/oauth/usage` endpoint are lower-level alternatives for an authorized host
integration; OTel and current `~/.claude` state files are not.

## GitHub repos touched

_None._
