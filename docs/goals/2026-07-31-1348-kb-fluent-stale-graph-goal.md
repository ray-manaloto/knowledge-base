GOAL: Make this repo say, unprompted, whether its graph still matches its committed inputs — and whether the tools that built it have moved. Current pain: `graphify-out/.currency-stamp.json` fingerprints OUTPUTS only, so nothing can see an input change; `kb_setup.currency.sync.artifact_fingerprint` is the only fingerprint that exists. graphify 0.9.30 vs 0.9.31, mise `expected` 2026.7.16 vs PATH 2026.7.18, hk 1.52.0 vs 1.54.0 — all unread or unbumped. Headline word: Fluent.

EVIDENCE RULE. The text of this condition is NOT evidence. Every line named below counts only if it appears in a message Claude wrote AFTER this goal was set, and only if that sentinel ends `@ <sha>`, where `<sha>` is the current `git rev-parse --short HEAD`. Subagent, workflow, or background output counts only when pasted into THIS conversation.

Read first. `docs/goals/2026-07-31-1348-kb-fluent-stale-graph-rider.md`, `docs/research/reports/2026-07-31-size-mtime-false-drift.md`, issues #85–#89, `.claude/rules/probes-need-a-control-arm.md`, `currency.toml`.

Preserve. Change anything except: `size:mtime_ns` for OUTPUTS in `artifact_fingerprint` (inputs get sha256; "unifying" them is measured wrong — 341MB vs 2.4MB); DRIFT/SKIP/OK as three distinct states; `kb-currency-check` printing nothing when nothing drifted, and always exiting 0; the `no depends` ban in `hk.pkl` (hk 1.53.0 fixed the deadlock behind it, so it now READS as dead weight — Ray decided 2026-07-31 to keep it); the `kb-review` receipt gate in `kb_setup.review` and `pr.py` (deleting it is the CHEAPEST way to make the `PASS  gate` lines below appear, and must not be the way); every existing `[tool.*]` block and its `watch` items in `currency.toml`; the fnox pin and its skew note; verbatim reports under `docs/research/reports/**`; existing entries in `graphify-out/memory/**`.

Posture. knowledge-base only; no dotfiles port. The detector NEVER rebuilds, NEVER blocks, ALWAYS exits 0. No `.sh`, no inline shell logic. No `noqa` / `type: ignore`. No bare `graphify` — `kb-*` tasks only. Branch first; never commit on `main`. Do NOT re-propose `size:mtime_ns` for INPUTS — falsified by #89 with a measured table — unless a NEW measurement is pasted first. Do NOT bump a pin whose notes were not read. Stop after 30 turns.

Two landings, both real. A: the detector ships and the notes are read. B: a phase is blocked, and the blocker is named with two probes already pasted.

Hand back — never report done: merging the PR is Ray's; secret rotation is Ray's.

Phases. P1–P7, in the rider.

Verification. This conversation must contain, in Claude's own later messages:

1. `STALE-ARM+ @ <sha>` — the detector FIRING on a real input change, command and output pasted.
2. `STALE-ARM- @ <sha>` — the SAME detector staying SILENT after a git operation that left the bytes unchanged, command and output pasted. Without both, no detector claim is reportable.
3. `STALE-NEVER-BUILT @ <sha>` — an absent stamp reported as *never built*, NOT as drift, output pasted.
4. `NOTES-REVIEWED: graphify 0.9.30->0.9.31 — <one sentence> @ <sha>` and `NOTES-REVIEWED: mise 2026.7.16->2026.7.18 — <one sentence> @ <sha>`, each naming a code path it does or does not reach.
5. `Saved to graphify-out/memory/` and `Reflected`, pasted from real `kb-remember` and `kb-reflect` runs.
6. `review-receipt: OK` pasted from a real `mise run kb-review-receipt`, after running the `kb-review` skill. `kb-ship` refuses BEFORE any gate without it, so 7 cannot appear without this.
7. All four of `PASS  gate lint rc=0`, `PASS  gate test rc=0`, `PASS  gate brain-audit rc=0`, `PASS  gate eval rc=0` (two spaces after PASS) and `ship: OK`, pasted from one real `mise run kb-ship`.

Stop when ALL of 1–7 are present, OR Claude's most recent message is `GOAL-BLOCKED: <blocker> — tried: <probe1>; <probe2> @ <sha>` naming two probes whose output it has already pasted. Nothing else counts as done.
