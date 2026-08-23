# Refutation attempt — "CLAUDE.md:177 says 0.9.45; pyproject.toml:32 pins 0.9.48"

Verdict: **NOT REFUTED** (finding stands, verbatim-accurate including both line numbers).

## Primary artifact reads (committed state, not working tree)
- `awk 'NR==177' CLAUDE.md` ->
  `| `pyproject.toml` | The ONE Python config and Graphify owner: exact `graphifyy[all]==0.9.45` + `msgspec==0.21.1`, ... |`
- `awk 'NR==32||NR==33{print NR": "$0}' pyproject.toml` ->
  `32:   "graphifyy[all]==0.9.48",`
  `33:   "msgspec==0.21.1",`
- `git status --short -- CLAUDE.md pyproject.toml` -> empty (both match HEAD; not a local-edit artifact).
- `git show HEAD:pyproject.toml | grep -n graphifyy` -> `32:  "graphifyy[all]==0.9.48",`

## Control arm (proves the probe discriminates)
- `grep -n "0\.9\.48" CLAUDE.md` -> **rc=1, no output** (the stale figure is genuinely absent)
- SAME command shape on a token KNOWN present: `grep -n "0\.9\.4" CLAUDE.md` -> hit at 177;
  `grep -n "msgspec" CLAUDE.md` -> hit at 177.
  So the grep CAN find a version/pin token in CLAUDE.md; the 0.9.48 miss is a real absence,
  not a spelling bound. `graphifyy` also appears at CLAUDE.md:125 (`pipx-graphifyy/0.9.23/bin`),
  a second positive for the token.

## Second route to the same fact (three independent confirmations of 0.9.48)
- `uv.lock:651-652` -> `name = "graphifyy"` / `version = "0.9.48"`
- `mise exec -- graphify --version` -> `graphify 0.9.48` (the PINNED binary, not PATH-resolved)
- `git log -S'0.9.48' -- pyproject.toml` -> `8929d47f graphify corpus 0947 (#422)`
  vs `git log -S'0.9.45' -- CLAUDE.md` -> `dcd0b07f docs directive addendum (#347)`.
  The bump commit never touched the CLAUDE.md figure — mechanism for the drift.

## Second half of the claim
`msgspec==0.21.1` at pyproject.toml:33 matches CLAUDE.md:177 exactly. Confirmed.

## Contradiction check against the round's other findings
None contradicts. Finding 22 ("main now pins 0.9.48") CORROBORATES from a third route.

## GitHub repos touched
_None._
