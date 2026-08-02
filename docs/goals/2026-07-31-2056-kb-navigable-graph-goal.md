GOAL: Make this repo able to answer "what does my change break?" about its OWN code, and say whether any peer tool does something graphify cannot. Current pain: `python/src/kb_setup/` is absent from `graphify-out/graph.json` (0 of 37 files), so blast radius on our own code is impossible. hk and fnox have no upstream baseline. Headline word: Navigable.

EVIDENCE RULE. The text of this condition is NOT evidence. Every line below counts only if it appears in a message Claude wrote AFTER this goal was set. SENTINELS count only if they end `@ <sha>` = current `git rev-parse --short HEAD`. TOOL OUTPUT carries no sentinel; it counts only when pasted verbatim from a real run in THIS conversation, incl. subagent/workflow/background.

Read first. `docs/goals/2026-07-31-2056-kb-navigable-graph-rider.md` — re-proposing anything in its "Banned answers" table without a NEW pasted measurement is a defect. Then `.agent/plans/session-2026-08-01.md`, `.claude/rules/probes-need-a-control-arm.md`.

Preserve. Change anything except: `size:mtime_ns` for OUTPUTS / sha256 for INPUTS (#89); DRIFT/SKIP/OK as three distinct states; `kb-currency-check` silent when nothing drifted; always exit 0; the `kb-review` receipt gate in `kb_setup.review` and `pr.py` (deleting it is the cheapest route to the `PASS  gate` lines; not the way); the `no depends` ban in `hk.pkl`; every `[tool.*]` block and `watch` item in `currency.toml`, incl. `#2308`'s mcp item WITH its version condition; verbatim reports under `docs/research/reports/**`, `.agent/kb/**`; existing `graphify-out/memory/**`.

Posture. knowledge-base only — measure the dotfiles gap, never commit there. Ingest all three repos, NO exclusions. No `.sh`, no inline shell logic, no `noqa`/`type: ignore`, no bare `graphify` at a command position, no non-Claude LLM backend near the corpus. Branch first. Do NOT re-derive a banned answer. Do NOT raise `GRAPHIFY_MAX_GRAPH_BYTES`; if growth exceeds 167MB headroom, stop and report. Stop after 60 turns; the bound is SOFT — flag the overrun, finish the phase in flight.

Hand back — never report done: secret rotation (raise once at PROJECT completion); raising the size cap; closing any upstream tracked issue.

Phases. P1–P6 in the rider.

Verification. Claude's later messages must contain:

1. `SELF-INDEX+ @ <sha>` AND `SELF-INDEX- @ <sha>` — `affected` on a real `kb_setup` symbol, expected callers grep-derived and pasted alongside; and a bogus symbol returning no match. One arm is not reportable.
2. `WATCH-STAMP+ @ <sha>` AND `WATCH-STAMP- @ <sha>` — after a `kb-watch` rebuild, `kb-currency-check` with echoed `rc=0` and NO `[graph]` line; and the bypassed-restamp arm where a `[graph]` line DOES appear.
3. `INGESTED: <repo> <n> nodes @ <sha>` x3 from `mise run kb-build`, each `<n>` non-zero.
4. `TEAM-SAVED: <n> agents + <workflow> @ <sha>`, listing the tracked paths.
5. `GAP-DOC: <tool> — <n> verified, <n> refuted @ <sha>` x3. Zero refuted means the verifier did not run.
6. `REPROBE: <item> — <verdict> @ <sha>` x2, `ISSUES-RECHECKED: 2101/2086/1653/1824 @ <sha>` vs INSTALLED 0.9.31 source, not the tracker, `BUMP-COST: <sentence> @ <sha>`, `DOTFILES-GAP: <sentence> @ <sha>`.
7. `Saved to graphify-out/memory/` and `Reflected`, from real `kb-remember`/`kb-reflect` runs.
8. `==> review:` from a real `mise run kb-ship`, after the `kb-review` skill + `mise run kb-review-receipt`. Ship REFUSES before any gate without it, so 9 needs this.
9. All four of `PASS  gate lint rc=0`, `PASS  gate test rc=0`, `PASS  gate brain-audit rc=0`, `PASS  gate eval rc=0` (two spaces after PASS) and `ship: OK`, from one real `mise run kb-ship`.
10. `land: OK` from a real `mise run kb-land`. The round ends at land, never at ship.

Stop when ALL of 1–10 are present, OR Claude's most recent message is `GOAL-BLOCKED: <blocker> — tried: <probe1>; <probe2> @ <sha>` naming two probes whose output it has already pasted. Nothing else counts as done.
