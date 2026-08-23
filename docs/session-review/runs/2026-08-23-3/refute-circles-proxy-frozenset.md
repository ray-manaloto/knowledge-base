# Refutation attempt — circles finding #2 (four-name proxy frozenset)

CLAIM: "One four-name proxy frozenset was decided, warned about, reversed, re-broken
and is STILL open — five passes across three rounds — because a reviewer overturned an
explicitly-recorded design decision and the reversal was never armed against the case
that motivated the original decision."

## Chain verified so far (all primary artifacts, read directly)

- frozenset IS four names: `python/src/kb_setup/graphify_semantic_slice.py:176-183`
  (HTTP_PROXY, HTTPS_PROXY, ALL_PROXY, NO_PROXY). CONFIRMED.
- original decision recorded: `.agent/kb/specs/spec-lane1-slice-reattest-and-scrub.md`
  "Scrub scope, decided not accidental … the scrub removes those too (on a proxied host
  a loud refusal becomes a run with the proxy stripped …)". CONFIRMED.
- warned: `pv-lane1.md` M10 (LOW) — but its ASK was "Worth one sentence in the new
  function's docstring so the behaviour is a decision rather than a side effect."
- cold-review-lane1.md:164-179 P2-4 — its ask was ALSO documentation: "Not a defect on
  this host — an unstated consequence, and the docstring currently reads as if it had
  been considered and bounded." NO behavioural reversal was requested by the reviewer.
- the reversal was ordered by the ARCHITECT, not the reviewer:
  `.agent/kb/specs/spec-lane1-round2.md:14` (b) "The proxy names are NOT scrubbed (P2-4)
  … After this round: `scrub_route_overrides` removes every `_ROUTE_OVERRIDE_NAMES`
  member EXCEPT those four".
- re-broken: cold-review-round2.md:42-81 P2-1 (refusal reachable, uncaught ValueError)
  and P2-2 (uppercase-only). CONFIRMED.
- STILL open: `.agent/kb/specs/spec-round3-DRAFT.md` item 9 carries BOTH ebcf P2-2 and
  ebcf P2-1. CONFIRMED.

## The clause under attack: "the reversal was never armed"

COUNTER-EVIDENCE FOUND (two independent routes):
1. `tests/test_graphify_semantic_slice.py:314-347`
   `test_scrub_route_overrides_excludes_proxy_configuration` plants ALL FOUR proxy names
   (a simulated proxied host) + AWS_REGION, asserts scrub removes only AWS_REGION, the
   four survive verbatim, AND `route_override_names(env)` still returns exactly the four
   — i.e. the refusal input is armed for the proxied-host case.
2. ebcf9fcb commit body: "Verified live: with HTTP_PROXY set, `kb-setup
   graphify-semantic-slice preflight` still raises 'forbidden routing environment names:
   HTTP_PROXY' (uncaught, as before …)".

Next: run that live probe myself, with a control arm.

## VERDICT: REFUTED (mechanism), phenomenon partly confirmed

### 1. "the reversal was never armed against the case that motivated the original decision" — REFUTED, three routes

Route A — an automated test exists AND discriminates (mutation-proven).
`tests/test_graphify_semantic_slice.py:314-347` plants all four proxy names (the
proxied-host case) and asserts scrub leaves them while `route_override_names` still
returns all four.
Mutation (realistic revert of the reversal — delete the `if name not in
_ROUTE_OVERRIDE_PROXY_NAMES` clause at graphify_semantic_slice.py:858-860, bytes
confirmed changed at that line via `git diff --numstat` = 1 insertion / 3 deletions):
```
uv run pytest tests/…::test_scrub_route_overrides_excludes_proxy_configuration
  MUTANT rc=1  FAILED at tests/test_graphify_semantic_slice.py:335
  RESTORED rc=0 (green)
```

Route B — live end-to-end probe, control-armed, reproduced by me (not inherited):
```
HTTP_PROXY=http://proxy.example:8080 uv run kb-setup graphify-semantic-slice preflight
  rc=1  ValueError: forbidden routing environment names: HTTP_PROXY
        (graphify_semantic_slice.py:1028, via semantic_main:2135)
CONTROL, no proxy:              rc=0, full preflight JSON emitted
CONTROL, lowercase http_proxy:  rc=0  (P2-2 confirmed independently)
MUTANT (reversal reverted) + HTTP_PROXY: rc=0, stderr "…scrubbed … HTTP_PROXY"
```
The probe discriminates in both directions, and the mutant reproduces exactly the
pre-reversal behaviour the original decision wanted.

Route C — the implementer armed it by hand and recorded it: ebcf9fcb commit body,
"Verified live: with HTTP_PROXY set, `kb-setup graphify-semantic-slice preflight` still
raises 'forbidden routing environment names: HTTP_PROXY' (uncaught, as before …)".

TRUE residue (much narrower than the claim): there is no automated test of the CLI
EXIT-CODE / typed-refusal path — which is cold-review-round2 P2-1's own wording ("no
test covers the proxied-host path"), i.e. a missing typed refusal, not a missing arm.

### 2. "because a reviewer overturned an explicitly-recorded design decision" — REFUTED

Neither reviewer asked for a behavioural reversal; both asked for a DOCSTRING.
- pv-lane1.md:75-76 M10, rated **LOW**: "Worth one sentence in the new function's
  docstring so the behaviour is a decision rather than a side effect."
- cold-review-lane1.md:176-179 P2-4: "**Not a defect on this host** — an unstated
  consequence, and the docstring currently reads as if it had been considered and
  bounded." No remedy naming the scrub is present in P2-4.

The reversal was ordered by the **architect**, in `.agent/kb/specs/spec-lane1-round2.md:14`
(b): "After this round: `scrub_route_overrides` removes every `_ROUTE_OVERRIDE_NAMES`
member EXCEPT those four". The named actor in the finding is wrong, and the remedy that
follows from it ("stop reviewers overturning recorded decisions") would be aimed one
layer away from the decision that actually flipped.

### 3. "re-broken" — REFUTED for both cited round-2 findings

- P2-1 (uncaught ValueError on a proxied host) is **pre-existing at the base commit**:
  `git show 8929d47f:…graphify_semantic_slice.py | grep -c scrub_route_overrides` → the
  scrub does not exist at 8929d47f, so preflight refused proxies there too. The architect
  ruled it out of scope IN ADVANCE (spec-lane1-round2.md:14: "pre-existing; do not change
  it in this round, state it in the docstring") and ebcf9fcb's body records it
  ("uncaught, as before — this round does not add a try/except"). A recorded, ordered
  deferral is not a re-break.
- P2-2 (lowercase spelling) was **never** in `_ROUTE_OVERRIDE_NAMES` at any revision:
  lowercase count = 0 at 8929d47f / a67cbac4 / ebcf9fcb / HEAD; control `"HTTP_PROXY"`
  = 1 at 8929d47f, so the probe discriminates. cold-review-round2 says so itself: "the
  lowercase spelling was never scrubbed (nothing changed for it) and is also never
  refused." It is a pre-existing gap surfaced while reading the exemption.

### 4. Counts

- "four-name": CONFIRMED (graphify_semantic_slice.py:176-183).
- "STILL open": CONFIRMED — spec-round3-DRAFT.md item 9 carries both ebcf P2-1 and P2-2.
- "five passes across three rounds": the artifact trail shows **eight** touches across
  **two executed rounds plus one planned** (spec-lane1 §4 · pv-lane1 M10 · a67cbac4
  docstring · cold-review-lane1 P2-4 · spec-lane1-round2 (b) · ebcf9fcb ·
  cold-review-round2 P2-1/P2-2 · spec-round3-DRAFT item 9). The finding's own count
  undercounts the passes and overcounts the completed rounds; the direction of the error
  makes the circling worse, so this is not a refutation of the phenomenon.

### Contradiction with other findings in the set
None found. Finding 10 ("kb-arms sweeps unrunnable ⇒ arms hand-derived") is CONSISTENT
with the true residue here (no kb-arms spec row for the exemption) and does NOT support
"never armed" — ebcf9fcb ran four hand arms, and the exemption's own test discriminates
under the mutation I ran.

## GitHub repos touched

_None._
