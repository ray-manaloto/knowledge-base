# Refutation lane — "session used pgrep/ps for subagent liveness 7x instead of ListAgents"

Session under review: `6ae19ff6-2b88-4aea-8fa7-c0430395e2da` (main transcript,
`/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/6ae19ff6-2b88-4aea-8fa7-c0430395e2da.jsonl`).

## Probe 1 — tool-name census (control-armed)

    grep -o '"type":"tool_use","id":"[^"]*","name":"[^"]*"' $T | sed ... | sort | uniq -c

    91 Bash / 42 Edit / 36 SendUserMessage / 19 Agent / 16 Write / 15 Read /
     8 SendMessage / 5 AskUserQuestion / 3 ToolSearch / 3 Skill / 1 Workflow /
     1 TaskOutput / 1 ListAgents / 1 ExitPlanMode

Control: `"name":"Bash"` -> 91 (probe discriminates). Spelling arm: `listagents`
case-insensitive -> 1; `list agents` (space) -> 0. So the "ListAgents = 1" half of
the claim is NOT a token-spelling artefact. `"name":"Task"` -> 0; the dispatch tool
here is named `Agent` (19 = the 19 subagents).

## Probe 2 — the seven ps/pgrep Bash calls (verbatim, with timestamps)

Extracted by walking every Bash tool_use in order (no head/limit bound):
IDX 40 07:48:24.294Z, 41 07:48:35.692Z, 50 08:24:34.467Z, 57 12:45:04.856Z,
71 13:24:19.394Z, 82 14:32:30.846Z, 83 14:32:43.816Z.
(The finding's indices 39/40/49/56/70/81/82 are the same seven, 0-based.)

Count and timestamps: CONFIRMED.

## Probe 3 — WHAT the seven probes asked (Bash `description` + output)

    07:48:24  "Settle Lane 1: tree state, commit, surviving codex processes"
    07:48:35  "Check whether the surviving codex-companion shell is a live writer"
    08:24:34  "Settle Lane 2: tree, commit, processes, CLAUDE.md budget, timeout count"
    12:45:04  "Settle Lane 1 round 2 and check the stderr WARNING end-to-end"
    13:24:19  "Settle Lane 3: tree, commit, processes"
    14:32:30  "Settle Lane 2 round 2: tree, commit, processes, suppression removed"
    14:32:43  "Identify the unexpected codex exec process (parent chain, cwd)"

Every one greps `codex exec` / `codex-companion` in the **OS process table**.
Outputs: 07:48:24 -> PID 63983, a `/bin/zsh -c … CODEX_COMPANION_SESSION_ID=…`
plugin shell; 14:32:30 -> PID 65731
`/Applications/ChatGPT.app/Contents/Resources/codex exec --json …`; 14:32:43
resolved its parent chain 65731 -> 27620 SkyComputerUseService -> 26470
ChatGPT.app. 08:24 / 12:45 / 13:24 returned EMPTY.

None of these is an Agent-tool subagent. `pkill`/`kill` appears **0** times.

## Probe 4 — what ListAgents actually returns (CONTROL ARM)

Same-repo session `6b974f05…` (the ORIGIN session of the memory lesson),
2026-08-18T01:19:45Z:

    Subagents (1):
      a112075dddf3e153e  ·  fable-orchestrator:codex-reviewer  ·  running  ·  started 11m ago
    Peer sessions (38): …

So the probe discriminates: ListAgents CAN show a running subagent. Its two
sections are **Subagents** and **Peer sessions** — it enumerates no OS
processes, and therefore cannot answer "is a `codex exec` process still alive in
this checkout".

## Probe 5 — the seven probes are MANDATED, verbatim, by the loaded skill

`~/.claude/plugins/marketplaces/fable-orchestrator/skills/orchestration/SKILL.md:147`:

> "Before dispatching anything else to that tree or trusting your own
> verification of it: check `git status` / `git log` for surprises, check for
> surviving lane processes (`pgrep -f 'grok --prompt-file'`,
> `pgrep -f 'codex exec'`), and group-kill anything found via its process GROUP
> … On git-mutating lanes this re-check applies to EVERY settlement, clean
> reports included."

`Skill(fable-orchestrator:orchestration)` was invoked at 06:19:57.365Z — 88 min
before the first probe. The seven commands are that checklist, in that order.

## Probe 6 — the session's REAL liveness misjudgements used neither pgrep nor a codex lane

All 8 `SendMessage` calls are "your final report did not reach me" resends, to
explore-corpus-core, explore-slice-env, pv-lane1/2/3, pv-lane1r2/2r2/3r2.
**Zero codex-lane* targets.** Those were driven by idle notifications
(finding 6), not by any process probe.

## Verdict: REFUTED
