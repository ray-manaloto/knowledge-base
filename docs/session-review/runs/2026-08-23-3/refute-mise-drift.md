# Lane: refute-mise-drift — attempt to refute the mise-version-drift finding

Reviewed commit context: branch docs-directive-addendum, main 2b364443. Date 2026-08-18.

FINDING UNDER TEST: mise runs 2026.8.8 vs currency expected=2026.8.3 and
sources/mise.manifest v2026.8.3; five unreviewed releases; engine's cached
"upstream 2026.8.6 as of 2026-08-16" is behind the running binary.

## Probes so far

1. `mise --version` (2026-08-18) -> `2026.8.8 macos-arm64 (2026-08-17)`.
   `which -a mise` -> single real binary `/Users/rmanaloto/.local/bin/mise`
   (three PATH hits, all the same path; plus a shell function wrapper). No
   shadow-copy ambiguity: the version probe reaches the only mise on the host.
2. currency.toml:598 `expected = "2026.8.3"` under `[tool.mise]` (line 596).
   CONFIRMED. Comment block explains: self-managed, no mise_key, a [tools] pin
   was tried and reverted because it blinds the check.
3. sources/mise.manifest:23 `ref = v2026.8.3`, commit dd76a503. CONFIRMED.
   (NOTE: stale header comment at manifest line 8 says "pinned here: 2026.8.0" —
   a doc-drift defect inside the manifest, but the ref/commit are the pin.)
4. kb-query --prose for currency/mise: TRUNCATED result, not evidence either way.

## Still to probe

- kb-currency-check rows (mise: version, mise: manifest)
- the "upstream had 2026.8.6 as of 2026-08-16" cache location + content
- handoffs' sighting of 2026.8.6
- do releases 2026.8.4..2026.8.8 all exist upstream (the "five" count)
- docs/currency/ - was any of 8.4-8.8 reviewed?
- Ray directive read in full
