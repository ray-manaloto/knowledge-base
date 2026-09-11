---
type: "query"
date: "2026-09-11T10:11:06.875252+00:00"
question: "How do we clear the version drift and automate the graphify fork rebase?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do we clear the version drift and automate the graphify fork rebase?

## Answer

# Clearing the version drift + automating the graphify fork rebase (2026-09-11)

Four `/grilling` rounds settled a SERIAL plan: drift sweep -> logging contract +
rule + gate -> build `kb-fork-rebase` (#728 scope only) -> the AUTOMATION performs
0.9.57 -> 0.9.58 -> the 382-site logging sweep.

## What was established, each control-armed

**graphify 0.9.58 adds an implicit `claude-cli` fallback.** `llm.py:3513`,
`if not backend and _claude_cli_available(): backend = "claude-cli"` (+49/-0).
`kb-label` runs `graphify label .` with no `--backend`, so a task advertised as
"deterministic, no-LLM" acquires an LLM call. Counts 0 @0.9.57 -> 2 @0.9.58,
control `generate_community_labels` 3 in both. NO opt-out flag exists, and
`--backend ""` fails too (`not ""` is True). FIXED: an opt-in `hide_claude_cli`
PATH strip, scoped to the label path so the SANCTIONED claude-cli extraction
backend still resolves. 4/4 mutation arms died, control held.

**The currency sweep CANNOT self-apply, by any documented route.** "auto-applying
(6/6 gates)" is a VERDICT LABEL, not an action: `run()` never calls apply
(`decide.py:580` `auto_apply` means "qualifies"). Worse, the skill's documented
command `mise run kb-currency -- --tool <name> apply` silently dispatches back to
`run`, because `[tasks.kb-currency]` hardcodes the mode and `apply` becomes an
ignored trailing positional (`cli.py:934-946`). `grep 'currency apply' mise.toml`
-> 0: no task reaches it. Reproduced live on three tools across two runs.

**Three more bumps are not what they look like.** skillopt `93bdf3d7 -> v0.2.0` is
a 42-day DOWNGRADE (pin 2026-08-13, tag 2026-07-02). mise has a live three-way
divergence (floor 2026.9.0 / manifest v2026.9.4 / binary 2026.9.5) while
`currency.toml:37` claims they agree. hk writes its version in EIGHT places
across three files, of which TWO are factual comments that a find-and-replace
would falsify (`hk.pkl:308` and `:338` — the lane found only the first).

**Function hooks: shipped, off, and they fail silently.** Present in the installed
2.1.268 binary; no `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` in either settings file.
An empirical probe loaded correctly (`fnhook-probe@inline` in the session's plugin
list), the tool fired (`caller: {type: "direct"}`), and the hook did nothing with
NO error anywhere — the "skipped, not failed closed" failure mode, demonstrated.
The `prepend` tier that would make them non-skippable is managed-only and
unreachable here (`do-not.md:123`), verified two ways.

**A clean baseline exists**: `kb-build` rc=0, 472,069 nodes / 1,115,223 edges,
prose graph 11,330, 0 hyperedges lost — established BEFORE anything moved.


## Outcome

- Signal: useful