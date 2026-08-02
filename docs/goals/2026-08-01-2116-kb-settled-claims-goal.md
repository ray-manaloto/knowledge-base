GOAL: Leave no claim in this repo's currency, self-graph or peer-tool story resting on an inherited or deferred measurement. Current pain: `affected` cannot say which tests cover a symbol in our OWN code — `merge-graphs` re-namespaces ids per merge, so 0 of 3,368 tests-touching edges reach `knowledge-base::python::`. Two currency re-probes are stuck on 0.9.30, four issues were checked only against the tracker, and `kb-tool-review.js` has NEVER been executed. Headline word: Settled.

EVIDENCE RULE. The text of this condition is NOT evidence. A line counts only if Claude wrote it AFTER this goal was set. Subagent/Workflow/background output counts only once pasted verbatim HERE.

LANDINGS. Each item lands EITHER as its sentinel, OR as `<NAME>=REFUTED` / `=UNREACHABLE` / `=DECLINED @ <sha>` naming the pasted probe that forced it. A refutation with both arms pasted IS a landing — never upgrade it to a claim, never spend GOAL-BLOCKED on it. If 4 lands `=DECLINED`, 5 and 6 land `=DECLINED` too.

Read first. `docs/goals/2026-08-01-2116-kb-settled-claims-rider.md` — its "Banned answers" and sentinel formats bind. Then the newest `.agent/plans/session-*.md`.

Preserve. Change anything except: the `kb-review` receipt gate; the `docs/research/**` review exclusion; DRIFT/SKIP/OK as three states with "could not check" never green; `kb-currency-check` silent unless drift, exit 0; #89's OUTPUTS/INPUTS fingerprint split; every `[tool.*]` and `watch` item in `currency.toml`; `.base-graph.*` + `kb-watch` idempotence; `scope = study` and the three pinned peer tools; `hk.pkl`'s `no depends` ban; verbatim `docs/research/reports/**`, `.agent/kb/**`; existing `graphify-out/memory/**`.

Posture. knowledge-base only — measure the dotfiles gap, never commit there. Do NOT pick the fourth tool yourself, nor start the fan-out before Ray answers. ONE `kb-build`; a second needs its reason stated first. Do NOT claim #101 without a depth test that FAILED at HEAD. Do NOT repeat an inherited number. Do NOT raise `GRAPHIFY_MAX_GRAPH_BYTES`. Do NOT fix #103/#94/#13 — name them, move on. Branch first; standing bans hold. Stop after 70 turns; SOFT — flag the overrun, finish the phase in flight.

Hand back — never report done: the fourth tool (Ray, via AskUserQuestion, pre-ingestion); secret rotation; the size cap; closing an upstream issue.

Phases. P1–P7 in the rider.

Verification, each per LANDINGS. Claude's later messages must contain:

1. `TRUNCATION: <tool|wrapper|neither> — <literal, or silent> @ <sha>`, both probed surfaces' output pasted.
2. `PROSE-COUNT: <n> — <path corrected, or already-correct> @ <sha>`; one line per build state if they differ.
3. `AFFECTED-TESTS- @ <sha>` AND `AFFECTED-TESTS+ @ <sha>` — one `affected` probe run twice; pass = a returned node under `tests/`; both pasted.
4. `TOOL-APPROVED: <key> @ <sha>`, quoting Ray's answer.
5. `INGESTED: <key> <n> nodes @ <sha>` from ONE `mise run kb-build`, `<n>` non-zero.
6. `HARNESS-RAN: <key> — <v> verified, <r> refuted, <u> unverified @ <sha>` — Workflow by `scriptPath`, NEVER by `name` (#13: a name resolves to a stale cache); paste the tool result's script path and returned object.
7. `REPROBE: <item> — <verdict> @ <sha>` x2; `ISSUES-RECHECKED: 2101/2086/1653/1824 @ <sha>` vs INSTALLED 0.9.31 source; `BASELINE-SEEDED: hk <v>, fnox <v> @ <sha>`; `BUMP-COST: … @ <sha>`; `DOTFILES-GAP: … @ <sha>`.
8. The close, every output pasted: `Saved to graphify-out/memory/`, `Reflected`, then `==> review:` (after the `kb-review` skill + receipt), all four `PASS  gate <lint|test|brain-audit|eval> rc=0` (two spaces), `ship: OK`, `land: OK`. Ends at land, not ship.

Stop when ALL of 1–8 have landed, OR Claude's most recent message is `GOAL-BLOCKED: <blocker> — tried: <p1>; <p2> @ <sha>` naming two probes whose output it already pasted.
