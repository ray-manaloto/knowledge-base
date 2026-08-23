# Lane: refute-auto-memory-pin-figure

Finding under test: auto-memory (MEMORY.md bullet "4 of 14 pins" + currency-tracks-half-the-pins.md) still propagates a pin-coverage figure the 2026-08-18 directive refuted (9-of-18 roster; currency.toml now 12 [tool.*] sections).

## Probes (as run)

1. docs/direction/2026-08-18-ray-directives.md:185-195 (read IN FULL): CONFIRMED — "defines **12** `[tool.*]` sections (graphify, ffmpeg, mise, claude-code, hk, fnox, doppler, skillopt, uv, ruff, ty, codex)", "**9 of the 18** in Ray's roster are ALREADY tracked", and "An earlier draft of this line said 'tracks 4 of ~14 pins', inherited from a work-memory note and never re-derived — the cold lane caught it".
2. grep -c '^\[tool\.' currency.toml = 12 (2026-08-18); grep -n '^\[' listing shows the 12 are exactly the 12 top-level [tool.X] headers (lines 12,564,596,810,1176,1286,1328,1358,1436,1447,1461,1473) — nested [[tool.X.watch]]/[[tool.X.ref_binding]] start with '[[' and do NOT match, so the count is not inflated. Probe discriminates.
3. ~/.claude/.../memory/currency-tracks-half-the-pins.md: front-matter modified 2026-08-06T21:51:36Z, mtime Aug 6 16:51:36; description line 3 = "currency.toml deep-tracks only 4 of 14 mise pins"; body lines 12-16 = 7 [tool.*] blocks / 14 mise pins / numerator 4. CONFIRMED as the finding describes. No post-08-06 correction in the file.
4. MEMORY.md (mtime Aug 18 03:01:27) line 110: "- **Currency + plugins** — [4 of 14 pins](currency-tracks-half-the-pins.md) · ..." CONFIRMED still present.
5. Refuting probe attempted: grep -ln '9 of the 18|9-of-18|12 \[tool' over ~/.claude/.../memory/*.md → rc=1, NOTHING carries the corrected figure. Control arm: same shape grep for '4 of 14|4 of ~14' → 4 files (MEMORY.md, currency-tracks-half-the-pins.md, a-tool-bump-must-advance-its-manifest.md, ray-directive-2026-08-18-currency-and-issue-sweep.md). The grep discriminates.
6. git show 3d957f15 (the cold-lane fix): touched docs/direction/... + two graphify-out/memory query files only — NOT the ~/.claude auto-memory store. The correction never reached auto-memory.
