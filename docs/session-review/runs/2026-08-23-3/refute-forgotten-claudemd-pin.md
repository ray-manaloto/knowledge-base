# Refutation attempt — [forgotten] CLAUDE.md:177 pin is stale (0.9.45 vs 0.9.48)

Verdict: **NOT REFUTED**. Confirmed at HEAD `e82708d9`, and the "carried" half is
stronger than the finding states.

## The probe (could return either answer)

```
grep -n "graphifyy" CLAUDE.md pyproject.toml
CLAUDE.md:177:| `pyproject.toml` | The ONE Python config and Graphify owner: exact `graphifyy[all]==0.9.45` + `msgspec==0.21.1`, … |
pyproject.toml:32:  "graphifyy[all]==0.9.48",
```

`sed -n '177p' CLAUDE.md` and `sed -n '32p' pyproject.toml` reproduce the same two
lines verbatim, so the line numbers in the finding are exact.

## Control arms (the probe discriminates)

- A: `grep -n "0\.9\.48" CLAUDE.md` -> rc=1 (absent — no second, corrected copy).
- B: same grep shape, `pyproject.toml` + `.claude/skills/graphify/.graphify_version`
  -> rc=0, both `0.9.48`. The pattern CAN match 0.9.48.
- C: `grep -n "0\.9\.45" pyproject.toml` -> rc=1. The stale token is not present
  on the pin side.
- Runtime cross-route: `mise exec -- graphify --version` -> `graphify 0.9.48`,
  agreeing with pyproject and disagreeing with CLAUDE.md. Two independent routes,
  same answer.
- Graph arm: `mise run kb-query -- "which file is the Graphify owner and what
  version is pinned" --prose --idf` returned 20 rows, all from ingested upstream
  corpus (`graphify/README.md`, `sources/media/…`) and none from this repo's own
  `CLAUDE.md` — `--prose` strips `_origin=ast` and this repo's authored root docs
  are not the corpus. Non-answer, not evidence either way; recorded so it is not
  mistaken for a miss.

## The "carried across 3+ rounds" half is UNDERSTATED, not overstated

Pin history on `pyproject.toml:32` vs `CLAUDE.md` at the same commits:

| commit | date | pyproject | CLAUDE.md |
|---|---|---|---|
| `d937841d` currency sweep 2026 08 18 (#375) | 2026-08-18 | `0.9.46` | `0.9.45` |
| `71cccbb0` currency sweep 2026 08 19c (#398) | 2026-08-19 | `0.9.47` | `0.9.45` |
| `8929d47f` graphify corpus 0947 (#422) | 2026-08-21 | `0.9.48` | `0.9.45` |

Commands: `git log --oneline -S"graphifyy[all]==0.9.4X" -- pyproject.toml` for
X in 6/7/8, then `git show <sha>:pyproject.toml | grep -n graphifyy` and
`git show <sha>:CLAUDE.md | grep -o 'graphifyy\[all\]==[0-9.]*'`.
`git log --oneline -S"graphifyy[all]==0.9.45" -- CLAUDE.md` -> `dcd0b07f`
(docs directive addendum, #347) is the last time that literal moved in CLAUDE.md.

So the divergence opened on **2026-08-18** and survived **three** separate pin
bumps. "3+ rounds" is true and conservative.

## Handoff citations check out

- `.agent/plans/session-2026-08-22.md:68` — states the pair explicitly, "measured
  today; msgspec agrees on both sides, isolating the defect".
- `.agent/plans/session-2026-08-22.md:91` — "§1.4 … CLAUDE.md 0.9.45 row) —
  **CARRIED**, not started; the CLAUDE.md row re-verified stale today."
- `.agent/plans/session-2026-08-22-b.md:163` — "§5 `CLAUDE.md:177` says
  `graphifyy[all]==0.9.45` vs `pyproject.toml:32` `0.9.48`".

HEAD advanced during this session (`dfaa5d75` -> `e82708d9`, two commits incl.
`4f2193e9` currency resync) and neither commit touched the row.

## Relation to the rest of the set

Finding **#17** ([contradicted] lane) asserts the same fact via a different lens
("the ONE Python config" label vs a stale restatement), and says "at least 4 prior
handoffs" where this one says "3+ rounds". Both are consistent with the measured
2026-08-18 origin; they corroborate rather than contradict. No other finding in
the set claims the row is current.

One adjacent caveat, not a refutation: MEMORY.md's standing lesson "the graphify
bump is not one line — 4 places, one is EVIDENCE" is about bumping the TOOL. Here
the tool is already at 0.9.48 everywhere measurable (`pyproject.toml:32`, both
`.graphify_version` stamps, the installed runtime); only the CLAUDE.md prose
restatement lags, so the "trivial one-line fix" characterisation holds for THIS
item. `git grep "0\.9\.4[5-9]"` over tracked non-`sources`/`graphify-out` paths
shows every other surviving `0.9.45` is in a historical artifact
(`docs/direction/2026-08-17-*`, `docs/research/reports/2026-08-17-*`,
`currency.toml` re-probe narrative) where the old figure is correct as a record.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under audit.
