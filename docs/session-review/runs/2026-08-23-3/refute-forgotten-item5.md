# Refutation attempt — finding: directive item 5 (/clear-prep 20% dual trigger) dropped from handoff-b, no issue

Round: 2026-08-18. Lane: forgotten. Verdict so far: NOT REFUTED (all three clauses hold).

## Clause 1 — "listed as owed in handoff-a"  CONFIRMED
`.agent/plans/session-2026-08-18-a.md:124` = `## Owed, with Ray's rulings attached`
`.agent/plans/session-2026-08-18-a.md:145-146`:
  - **`/clear-prep` at 20%** — both triggers, whichever fires first (session token
    budget AND a context-window estimate). Nothing measures either today.

## Ruling exists — CONFIRMED
`docs/direction/2026-08-18-ray-directives.md:90-93` (sed -n '86,96p'):
  - **Item 5 — the `/clear-prep` trigger is BOTH, whichever fires first.** ...
    Neither may be silently dropped for being harder to measure.

## Clause 2 — "dropped from handoff-b's carried-forward owed list"  CONFIRMED
`.agent/plans/session-2026-08-18-b.md:127` = `## Owed, unchanged from the previous handoff`
Full read of all 161 lines: the section carries currency (8 pins + skillopt), the
18-name roster, two staleness gates, rumdl, gitleaks->betterleaks, mongodb/kingfisher,
the hk-builtin review workflow, kb-update agent-harness-docs. It does NOT carry item 5.
Wider token sweep (not just the original's 3 tokens):
  grep -n -i -E "owed|prep|trigger|threshold|token|session limit|smaller|task size|measure" -> 6 hits,
  none of them item 5 (line 29 is Ray's quote about clear-prep being bullet proof;
  line 75 "session limit" is about run 1's synthesis dying; line 90 is #344).
The section title itself asserts "unchanged from the previous handoff", which is false.

## Clause 3 — "no GitHub issue"  CONFIRMED, on a WIDER probe than the original
Original probe was bounded: --state open, title-only. Re-run unbounded:
  gh issue list --state all --limit 1000 (209 issues total) with title+body regex.
  Sweep A "20%|clear-prep|clear prep|context window|token budget|context budget|1M|session limit" -> 18 issues
    (#344,#333,#313,#253,#233,#207,#174,#168,#157,#154,#150,#147,#146,#145,#144,#143,#142,#12)
  Sweep B "20 ?%|20 percent|whichever fires first|dual trigger|remaining context|context remaining|token.?budget" -> only #207, #12 (unrelated)
  Sweep C "compact|threshold|directive|2026-08-18|smaller task|task size" -> 23 issues, none about the trigger
  #344 read in full: handoff DERIVATION; mentions the session limit only as an objection
  to be answered, never as a trigger to measure. #143/#150: clear-prep mechanics.

## Not-done check (would have refuted "silently dropped" as "completed")
  grep -rn -i -E "20%|20 percent|context window|remaining (context|budget|token)|whichever fires first"
    .claude/skills/clear-prep/ .claude/rules/ python/src/kb_setup/ CLAUDE.md .claude/CLAUDE.md
  -> 1 hit, md-size-budgets.md:92, unrelated (a 1%-of-context listing budget).
  No implementation exists, so the drop is not completion.

## Controls
- gh probe DISCRIMINATES: same command shape returned 18 issues incl. the three real
  clear-prep issues; sweep B on the narrow tokens returns 2. It is not an all-zeros probe.
- grep --include probe DISCRIMINATES: control `grep -rn -i -E "graph_first|hook_guard"
  --include='*.py' python/src/kb_setup/` -> 3 hits, rc=0. (First attempt with UNQUOTED
  --include='*.py' was eaten by zsh: "no matches found" — the brief's exact trap.)

## Extra probes that could have refuted, and did not
- handoff-c (`.agent/plans/session-2026-08-18-c.md`, written 12:47, later than b):
  grep -n -i -E "20%|clear-prep|context|budget|1M|window|item 5|trigger|owed" -> 5 hits,
  none item 5; its own `## 6. Owed and not done` (line 133) does not restore it.
  The drop persists past b.
- Auto-memory: `~/.claude/projects/-Users-.../memory/ray-directive-2026-08-18-currency-and-issue-sweep.md`
  grep -n -i -E "20%|clear-prep|whichever fires" -> 3 hits, all about the NEXT-TASK
  clear-prep answer; the item-5 ruling is absent there too. MEMORY.md:3's directive
  summary lists currency / roster / hk-builtin / betterleaks / zero-tolerance and omits
  item 5. So the drop is broader than handoff-b.
- MEMORY.md:1 "NEXT" list = session-review handoff run, then Phase 2 iter 2, then
  currency. Item 5 is not in it.

## Cross-check against the round's other findings
No contradiction. Finding 12 (rumdl / betterleaks / kingfisher carried verbatim a->b)
is the positive control for "selective, not wholesale" and CORROBORATES this one.
Finding 11 (directive item 6, worktree audit) is the same shape and also holds:
handoff-a:147-149 carries it, handoff-b does not.

## VERDICT: refuted = false. The finding stands on all three clauses.
Only correction: handoff-a's section is titled "Owed, with Ray's rulings attached"
(line 124), not bare "Owed"; the cited content at 145-146 is exact.
