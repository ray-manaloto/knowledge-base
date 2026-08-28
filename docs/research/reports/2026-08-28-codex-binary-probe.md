# codex binary probe — untested primitives

Installed: `codex-cli 0.150.1` (`mise exec -- codex --version`).
Working dir: throwaway scratchpad, never the repo.

## Answer

All four flags/subcommands exist AND were exercised live on `codex-cli 0.150.1` (not just read from `--help`); three of four behaved as the handoff hoped, one did not:

1. **`--output-schema` WORKS** — a 1-key required-int schema produced exactly `{"answer":4}`, both to `-o <file>` and in the stdout transcript. Validated as correct, not just non-erroring.
2. **`resume --last` WORKS, including across a hard kill** — recalled a told fact after a clean exit, AND recalled both a remembered number and mid-task progress after the process was SIGTERM'd 4s into a turn (no `-o` file was ever written by the killed run, so the recall came only from persisted session state, not a completed output).
3. **`--json` JSONL carries NO timestamps** — none of `thread.started`/`item.completed`/`turn.started`/`turn.completed` (incl. the final `usage` line) carry a timestamp/ts/time/created_at field on this version. Control-armed: the same grep found the always-present `"type"` key on every line, so this is a real absence, not a broken probe. **If the handoff's plan needs a per-event clock from `--json`, that plan does not hold on 0.150.1 — an external wall-clock wrapper is required instead.**
4. **`mcp-server` exists and answers a real MCP `initialize` handshake** — full JSON-RPC round trip in well under 8s, correct `protocolVersion`/`capabilities`/`serverInfo`. **But stderr says it is DEPRECATED and will be removed in a future release** — anything built on it should target `app-server` instead (exists per `--help`, `[experimental]`, not itself executed here — see Not measured).

## Per-question table

| # | Question | Exists (flag/subcommand)? | Executed here? | Result | rc | seconds | evidence |
|---|---|---|---|---|---|---|---|
| 1 | `--output-schema <file>` returns validated JSON | YES (`codex exec --help`) | YES | `-o out1.txt` wrote exactly `{"answer":4}` matching the 1-key required-int schema; stdout log's final `codex` turn shows the same JSON | 0 | 9 | `run1.log`, `out1.txt`, `schema1.json` (all under scratchpad `codex-probe/`) |
| 2 | `exec resume --last` restores killed-run state | YES (`codex exec --help` → `resume` subcommand) | YES | Two arms: (a) clean run told a code word, `resume --last` in a fresh process correctly recalled it, same session id. (b) SIGTERM'd a run mid-turn (killed 4s in, while it was counting 1-50 after being told a number; `wait` rc=143, no `-o` file ever written), then `resume --last` correctly recalled BOTH the number and what it had been doing when killed | 0 (both) | 9, 7 | `run2a.log`/`out2a.txt`, `run2c.log` (kill evidence, rc 143), `run2d.log`/`out2d.txt` |
| 3 | `--json` JSONL carries usable timestamps | YES (`codex exec --help`) | YES | NO timestamp/ts/time/created_at field on any of 6 event lines (`thread.started`, 2×`item.completed` for warnings, `turn.started`, `item.completed` agent_message, `turn.completed`+usage). Control arm: grep for the always-present `"type"` key found all 6 lines, so the grep/probe itself works — the absence is real, not a broken probe | 0 | 13 | `run3.jsonl` |
| 4a | `codex mcp-server` subcommand exists | YES (`codex --help`) | YES | ran it; started, read stdin, replied, exited on stdin EOF | 0 | ~1 (within 8s bound) | `mcp_out.jsonl` |
| 4b | `codex app-server` subcommand exists | YES (`codex --help`, marked `[experimental]`) | NOT executed (not asked to; existence only claimed via `--help`) | | | | `help-top.txt` |
| 4c | `codex mcp-server` answers MCP `initialize` over stdio | n/a | YES | sent one JSON-RPC `initialize` line via stdin, got back a well-formed MCP initialize result: `protocolVersion":"2025-06-18"`, `capabilities:{tools:{listChanged:true}}`, `serverInfo:{name:"codex-mcp-server",version:"0.150.1"}`. **stderr also warns `codex mcp-server` is DEPRECATED and will be removed in a future release** | 0 | <8 | `mcp_out.jsonl`, `mcp_err.log`, `init.jsonl` |

## Every null with its arm

- **Q3, `--json` timestamps: absent.** Arm: `grep -oE '"(timestamp|ts|time|created_at|created|at)"[^,}]*' run3.jsonl` → 0 matches, across all 6 lines including the final `turn.completed` usage line. Control: `grep -oE '"type":"[a-z._]*"' run3.jsonl` on the SAME file and SAME command shape → 6/6 lines matched (`thread.started`, `error`×2, `turn.started`, `agent_message`, `turn.completed`), proving the grep mechanism works on this exact file — the absence is in the data, not the probe.

## Not measured

- **`codex app-server` was not executed** — only confirmed present in `codex --help` (marked `[experimental]`). The task's four questions didn't require exercising it (only `mcp-server`'s initialize handshake was asked for); flagging so nobody reads "exists" as "executed" for this one row.
- **Schema *enforcement* under a violating model response was not tested** — only the positive case (model complied) was run. Whether `--output-schema` actively re-prompts/repairs/errors on a genuinely non-conforming completion is unverified; only "the happy path produces schema-conforming output" is confirmed.
- **`resume --last` was tested only for facts inside the SAME session's turn history**, not for restoring in-flight tool-call/sandbox state (no shell command was mid-execution at kill time, only text generation was). Whether a killed run resumes a partially-applied file edit or a running subprocess is unmeasured.
- **No cross-process concurrent `mcp-server` client test** — only one client, one request, one reply were exercised; multi-request or long-lived-connection behavior is unmeasured.

## GitHub repos touched

_None._
