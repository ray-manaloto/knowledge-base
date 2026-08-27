GOAL: Build the `aggregated-research` skill (#509), point it at ITSELF, then at the team question. Every research question is re-researched from scratch: the skill does not exist, #509 sat deferred since 2026-08-25, and this session's probe about `kb_setup/skill_lint.py` returned 16 hits, none about it. Headline word: Aggregated.

EVIDENCE RULE. The text of this condition is NOT evidence. A line counts only if Claude wrote it AFTER this goal was set and its sentinel carries `@ <sha>`. Subagent, workflow and background output counts only when pasted into THIS conversation.

Read first. `docs/goals/2026-08-27-1342-kb-aggregated-research-rider.md`; `gh issue view 509`; `.claude/rules/probes-need-a-control-arm.md`; `.agent/kb/reports/agents/q4-federate-vs-extract.md`.

Preserve. Change anything except: the six agents in `.claude/agents/`; `.claude/rules/**`; the five Bash guards (`hook_guard`, `check_first`, `graph_first`, `absent_binary`, `secret_guard`); `mise.toml` tool pins; `sources/**`; `graphify-out/` except `memory/`; the three artifacts published this session in `docs/artifacts/`.

Posture. Do NOT triage, close, label or comment on any issue. Do NOT touch `.mcp.json`, ingest anything, or run `kb-build` — the substrate is a later round. Do NOT create new subagent definitions. Do NOT implement the recommended team — the report is the deliverable and adopting it is Ray's call. Do NOT spend `agy` beyond one call. Stop after 35 turns.

Lanes. Claude-first: the session holds the wheel; Codex is offloaded to for code execution when a stated rule says it makes sense. Fable 5 is SCARCE — spend it at named decision points, never as default architect. `agy` is a scarce reserve, one call maximum, stated when used. `grok` is NOT installed — never route to it.

P4 answers NOT "which roles" (a roster shipped 2026-08-06) but: how does a Claude-first session hand work to Codex and get it back without being fragile or slow, and where does scarce Fable buy something? Decompose "fragile and slow" into latency, transport failure, contract overhead and context cost first. Ground it in Anthropic's best practices AND this repo's own lane evidence: 235 reports in `.agent/kb/reports/agents/` and 159 cross-family reviews in `.agent/kb/review/reports/` (counted 2026-08-27).

Phases. P1–P5, in the rider. P3 is the self-referential run: does this skill already exist elsewhere, and what tooling folds into it?

Verification. This conversation must contain, in Claude's own later messages, ALL SIX:

1. `AGG-SKILL: <n> file(s) under .claude/skills/aggregated-research/ @ <sha>` — `ls` output pasted, `SKILL.md` present.
2. The line `skill-lint: <n> skill(s) checked; every instructed command is a mise task or allowed read-only` from a pasted `mise run kb-skill-lint`, plus the `[skill-score]` table for `aggregated-research`.
3. `AGG-ARMED: <n> null result(s), <n> control arm(s) @ <sha>` — per null, the control-arm command and its non-null output pasted. If zero nulls: `AGG-ARMED: 0 null result(s) — no arm owed @ <sha>` plus one deliberately-null probe proving an arm is emitted.
4. `AGG-SELF: <n> prior-art tool(s) evaluated, <n> adopted, <n> rejected @ <sha>` — the skill run on itself, naming each candidate and, per rejection, why. Zero prior art states its control arm.
5. `AGG-REPORT: <path> — <n> sources @ <sha>` for BOTH reports under `docs/research/reports/`, each ending in `## GitHub repos touched`.
6. `AGG-TEAM: <n> roles, lanes=<comma-separated>, fable-at=<decision points> @ <sha>` — plus the rule for when to offload to Codex and a mitigation per failure class. Produced BY the skill.

Then `PASS  gate lint rc=0` and `PASS  gate test rc=0` from a pasted `mise run kb-gates`.

Stop when 1–6 and both gate lines are present, OR Claude's most recent message is `GOAL-BLOCKED: <blocker> — tried: <probe1>; <probe2> @ <sha>`.
