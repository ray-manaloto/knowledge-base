# Refute lane — "9 of 18 roster deps untracked violates the 2026-08-18 one-sweep ruling"

## Arithmetic half — CONFIRMED (could not refute)

Probe: `grep -n '^\[' currency.toml` (unbounded, all TOML tables, not just `^\[tool\.`)
-> 12 top-level `[tool.X]` tables: graphify ffmpeg mise claude-code hk fnox doppler
skillopt uv ruff ty codex. The rest are `[[tool.X.watch]]` / `[[tool.graphify.ref_binding]]`
sub-arrays. So the "only 12 tracked" figure survives a widened probe.

Roster, exact lines (probe `grep -n -E '^> (- |  - )' docs/direction/2026-08-18-ray-directives.md`):
112 uv · 113 hk · 114 github:agent-sh/agnix · 115 fnox · 116 doppler · 117 antigravity-cli
· 118 codex · 120 anthropic · 121 graphifyy · 122 msgspec · 123 skillopt
· 124 datamodel-code-generator · 125 ruff · 126 ty · 127 structlog · 128 trafilatura
· 129 pytest · 130 pytest-xdist  => **18 names, lines 112-130**.

Token-spelling control on the 9 alleged-missing (case-insensitive, whole file):
agnix 0 · antigravity 0 · msgspec 0 · datamodel 0 · structlog 0 · trafilatura 0
· pytest 0 · xdist 0 — against controls codex 16, ruff 13. Probe discriminates.
`anthropic` returns 9 hits but ALL are claude-code prose / `ANTHROPIC_*` env names
(currency.toml:814,849,919,949,1101,1104,1105,1109,1138) — no `[tool.anthropic]`.
graphifyy is tracked under the spelling `[tool.graphify]` (currency.toml:12), so it
is correctly NOT counted as missing.

=> 9 tracked of 18, 9 missing. The list of 9 is right.

## Citation defect in the finding (minor)

The finding cites `:118-130` as the range that "names 18 roster members". 118-130 holds
only 12 (codex + the 11 pyproject entries). The first six (uv, hk, agnix, fnox, doppler,
antigravity-cli) are at 112-117 — OUTSIDE the cited bound. The range is a display bound
that undercounts its own claim by 6.

## Normative half — REFUTED

Ray's addendum opens (line 108, verbatim): "add this to what needs to be handled in
**the next session after running /clear**", and line 111: "these need to be added ...
**if they have not been added already**". That is queued work with an explicit
future trigger, not a standing state the current tree can be in violation of.

The "ALL ... in one sweep" ruling the finding invokes is a DIFFERENT list.
docs/direction/2026-08-18-ray-directives.md:98-101: "Item 10 — currency means
**ALL EIGHT pins**, in one sweep". Eight, from the earlier directive body — not the
18-name addendum, which arrived later ("same day, after PR #339 landed", line 105).
The finding welds the addendum's 18 names onto the body's 8-pin sweep ruling.

## The refuting probe — "NOT tracked" is false for 2 of the 9

`python/src/kb_setup/currency/broad.py:1-18` (docstring, verbatim):

> "The broad sweep — `mise outdated` for every tool NOT deep-tracked.
>  The deep engine (steps 1-6) gives a handful of tools full due-diligence. But a
>  repo pins dozens more, and **Ray wants the daily signal to keep covering them**
>  (decided 2026-07-24): deep due-diligence on the fast-movers, a broad
>  `mise outdated --bump` table on the rest, merged into one report."

So `currency.toml` is the DEEP-tracked list, not the tracked list. The broad table
is the other half of the same report, and `render_broad(..., exclude=<deep keys>)`
exists precisely so a tool appears in exactly one of the two.

Ran the underlying probe (`mise outdated --bump --json`, rc=0, 8 keys):

```
uv 0.12.3 -> 0.12.5
hk 1.54.1 -> 1.55.0
conda:ffmpeg 8.1.2 -> 9.0.1
rumdl v0.2.52 -> 0.2.55
github:agent-sh/agnix 0.46.0 -> 0.49.0
fnox 1.32.0 -> 1.33.1
doppler 3.76.1 -> 3.76.5
antigravity-cli 1.1.11 -> 1.1.14
```

**`github:agent-sh/agnix` and `antigravity-cli` are both there**, with live drift
verdicts. They are covered by this repo's currency machinery today. The finding
counted them as untracked because it probed `currency.toml` only — an artifact
bound, not the mechanism.

Control arm on this probe: the same command surfaces `uv`/`hk`/`fnox`/`doppler`,
which ARE deep-tracked, so it is not a list of untracked things; and it returns
nothing for `anthropic`/`msgspec`/`pytest`, which are pyproject deps mise never
installs. The probe discriminates.

## What survives

7, not 9, have NO currency coverage of any kind — the pyproject ones:
anthropic, msgspec, datamodel-code-generator, structlog, trafilatura, pytest,
pytest-xdist. Confirmed by: no `uv tree --outdated` / `--outdated` anywhere in
`python/src/kb_setup/` (0 hits; control `mise outdated` in broad.py -> hit), and
no Renovate config in this repo (unbounded `find . -iname '*renovate*'` -> one
hit, `docs/research/reports/2026-08-06-renovate-recon.md`, which is recon of
**dotfiles'** `renovate.json`; a `-maxdepth 3` version of that find returned
NOTHING — the bound would have hidden the only hit).

Independent corroboration for one of the 7: **issue #329** states verbatim
"`datamodel` appears in neither `mise.toml` nor `currency.toml`". Second route,
same answer — not a contradiction, a confirmation.

## Verdict: REFUTED

- the count is wrong (7 uncovered, not 9);
- the ruling it invokes is a different list (the 8 stale pins, all already tracked);
- the roster is Ray's own explicitly-deferred "next session" item, hedged with
  "if they have not been added already" — so the present tree is not in violation.
