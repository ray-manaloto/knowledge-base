---
type: "query"
date: "2026-09-11T10:11:11.676270+00:00"
question: "Does an armed COUNT establish a mechanism?"
contributor: "graphify"
outcome: "corrected"
correction: "An armed COUNT is not an armed MECHANISM, and the gap between them cost this\nround two wrong reports and one wrong decision.\n\nThe counts were right: `_claude_cli_available` 0 -> 2 across the graphify bump,\ncontrol-armed against a symbol present in both. From that I reported \"0.9.58\nreplaces our deterministic labeller\". Reading the CALL PATH refuted it:\n`cli.py:2237-2268` computes `label_communities_by_hub` first and unconditionally\nat BOTH versions, and the LLM only OVERRIDES where it returns a real name. The\nbase is never lost; 0.9.58 ADDS an unrequested call. Ray had already ruled on the\nwrong framing and had to re-decide.\n\nThe same shape twice more in one session: the `settings.json` predicate looked\nlike the fix until reading the guard showed all 8 predicates feed a markdown\nBUDGET calculator; and `hooks.md:767`'s `agent_id` was read as settling the\nagent/interactive split for FUNCTION hooks when it documents CLASSIC ones.\n\nRay's ruling, verbatim option: \"Verify the mechanism end to end before telling\nme.\" Before reporting a blocker, trace far enough to say what breaks AND what\nsurvives — and confirm every option offered is implementable, because an option\nlist containing an infeasible choice spends the user's decision twice.\n"
---

# Q: Does an armed COUNT establish a mechanism?

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

- Signal: corrected
- Correction: An armed COUNT is not an armed MECHANISM, and the gap between them cost this
round two wrong reports and one wrong decision.

The counts were right: `_claude_cli_available` 0 -> 2 across the graphify bump,
control-armed against a symbol present in both. From that I reported "0.9.58
replaces our deterministic labeller". Reading the CALL PATH refuted it:
`cli.py:2237-2268` computes `label_communities_by_hub` first and unconditionally
at BOTH versions, and the LLM only OVERRIDES where it returns a real name. The
base is never lost; 0.9.58 ADDS an unrequested call. Ray had already ruled on the
wrong framing and had to re-decide.

The same shape twice more in one session: the `settings.json` predicate looked
like the fix until reading the guard showed all 8 predicates feed a markdown
BUDGET calculator; and `hooks.md:767`'s `agent_id` was read as settling the
agent/interactive split for FUNCTION hooks when it documents CLASSIC ones.

Ray's ruling, verbatim option: "Verify the mechanism end to end before telling
me." Before reporting a blocker, trace far enough to say what breaks AND what
survives — and confirm every option offered is implementable, because an option
list containing an infeasible choice spends the user's decision twice.
