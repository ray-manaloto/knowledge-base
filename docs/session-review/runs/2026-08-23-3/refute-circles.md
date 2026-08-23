# Refutation attempt — lane `circles`, finding 1 (premise-gate / Decision 9 / U8b0)

Session under review: f74823ff-3ee4-4b02-a2af-11106a762c9f (SHA at time of writing: see git HEAD 34bc4557)

## Verdict so far: MECHANISM CONFIRMED, could not refute

### Probe 1 — is row 9 typed `A`? CONFIRMED
`scratchpad/spec-u8b0-workflow-lint-gate.md:140` (heading `## 7. PREMISES` at :121):
`| 9 | A | option (d) is achievable at all. The architect could NOT verify that the runtime accepts a result delivered by any means other than a top-level `return`, and holds this only because decision 9 pinned it. This is the assumption your dissent licence is pointed at | assumption, stated |`

### Probe 2 — does the gate escalate ONLY on E rows / SECURITY TIER? CONFIRMED
`premise-gate.sh:160-197`. Trigger regexes, verbatim from the script:
- E scan: `^[^A-Za-z]*E(missions?|MISSIONS?|[0-9]+[a-z]*)?([^A-Za-z0-9]|$)`
- sec scan: `^[^A-Za-z]*security[-_[:space:]]+tier([^a-zA-Z0-9]|$)`
`[ "$trigger" -eq 1 ] || exit 0` — no other path reaches the PREMISES-VERIFIED demand.
Header :46-52 confirms the E scan is UNSCOPED (whole prompt), so this is the widest possible
reading of the trigger — it cannot be a scoping bound hiding a row.

### Probe 3 — did ANY of the round's five specs carry an E row? ZERO. Control-armed.
Ran the gate's own two regexes over all five specs:
```
spec-corpus-scope-sanitise.md            E_rows=0  SECTIER=0
spec-u0-toml-manifest-approver-rev2.md   E_rows=0  SECTIER=0
spec-u0-toml-manifest-approver.md        E_rows=0  SECTIER=0
spec-u4b-review-lane-pin-gate.md         E_rows=0  SECTIER=0
spec-u8b0-workflow-lint-gate.md          E_rows=0  SECTIER=0
```
A uniform negative across 5 probes is the shape that is usually ONE BROKEN PROBE, so armed it:
control file with `| 4 | E | …`, `E1a  emission row`, `Emissions: something`, `| 9 | A | …`,
`E2E test harness`, `en route prose` -> matched lines 1,2,3 ONLY (the three true E-shapes),
correctly exempting the A row, `E2E` and `en route`. Security regex matched
`SECURITY TIER: 2` and `_SECURITY TIER_`, correctly rejecting the mid-prose
"this is NOT a security tier change". THE PROBE DISCRIMINATES; the zero is real.

### Probe 4 — semantic cross-check (2nd route, not the regex)
All five specs DO carry a PREMISES heading (`:132`, `:226`, `:129`, `:105`, `:121`), so gate
check 1 passed for all five and only the escalation path stayed dark. Row types read by eye:
u0 rev1 = 14x L/I + 1x A (row 15); u8b0 = 6L/2I/1A (row 9); corpus-scope-sanitise = 11 L/I + 1 A;
u4b = 8 L/I + 1 A. **Every spec ends in exactly one A row, and no spec has an E row.**
Two independent routes agree.


### P4 — the run's OWN output, from the round's transcript (primary, not derived)
`grep -oE '.{80}repaid.{0,120}' ~/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/f74823ff-3ee4-4b02-a2af-11106a762c9f.jsonl`

Pass 1 (verbatim, the run's printed summary):
```
chunk_total 26 · completed 20 · failed 6 · repaid 0 · skipped 0 · halted ""
spend_usd $20.864456   (33% of the $63 cap)
```
Pass 2 (cumulative, verbatim tool stdout):
```
"chunk_total":26,"completed":4
"failed":4
"halted":""
"repaid":18
"skipped":0
"spend_usd":41.77706500000001
=== failed ordinals ===
"ordinal":26,"reasons":["chunk-stage-unverifiable: chunk-receipt-incomplete", ...]
```
`repaid: 18` is therefore MEASURED, not inferred.

### P5 — CONTROL ARM: the same arithmetic on the pass that had repaid=0
Sum of the 22 chunk artifacts written during pass 1 = **$20.864456499** against the run's
own reported pass-1 `spend_usd` **$20.864456** — delta **5e-07**, i.e. residual ZERO.
The identical subtraction on pass 2 gives residual **$17.020547** (40.74% of $41.777065).
So the probe discriminates: it returns "no double-spend" on a pass that had none, and
$17.02 on the pass that had 18 repaid chunks.

### P6 — reconciling the charge count
pass 1 = 22 charges ($20.864456), pass 2 = 23 charges ($20.912609); 22+23 = **45** = the
ledger's `charges`. Pass 2's 23 reached chunks = 4 new + 18 repaid + 1 unverifiable
(ordinal 26, whose stage dir was ALSO paid for in pass 1); the other 3 pass-2 failures
never reached `_dispose` and were never charged.

## VERDICT: NOT REFUTED — and the finding UNDERSTATES

- 18 repaid: measured, verbatim, from the run's own summary.
- $17.06: a DERIVED estimate (18 x $0.948/chunk, per `circles.md:89` which writes it as
  "≈ $17.06"). The MEASURED residual is **$17.020547**; the finding is high by $0.04 (0.2%)
  and drops the "≈". 40.74% -> "41%" is correct.
- **19**, not 18, previously-paid chunks were re-charged (ordinal 26 too), and 19 of 45
  charges produced no new artifact. The finding is conservative in the direction that
  matters.
- "documented in the code that did it": CONFIRMED at the charge site itself —
  `python/src/kb_setup/graphify_semantic_corpus_run.py:1226-1233` ("a chunk that was
  already staged is paid for again (graphify serves nothing from cache on this entry
  point)") and `:889-897` ("There is deliberately no 'resumed' (free) disposition ...
  every already-staged chunk is paid for again"), plus
  `graphify_semantic_corpus_authority.py:350-353` and
  `graphify_semantic_corpus.py:3511`.

## Cross-check against the other live findings
- **#41** is the closest probe of the same fact and AGREES on the money ($17.020547,
  40.7%) while DISAGREEING on the count (19 charges vs 18 chunks) and on attributability.
  Both derive the residual by subtraction; #41 is the more precise statement of the same
  measurement. Not a contradiction — a rounding/《which unit》difference.
- **#40** and **#47** corroborate the mechanism and the per-chunk figures
  ($0.6134470 for 0012, $0.6450125 for 0026 — read verbatim from
  `chunks/0012|0026/adapter-metadata.json`).
- Nothing in the set contradicts the finding.

### Probe 5 — gate scans the PROMPT, not the spec file. Re-ran on the real prompts.
The spec file is only a proxy; `premise-gate.sh:137` reads `.tool_input.prompt`. Extracted all
five `codex-implementer` dispatch prompts from the transcript and re-ran both regexes:
```
10:54:16.858Z U8b0    prompt_lines=34  E_rows=0 SECTIER=0 PREMISES_heading=0
10:54:36.164Z U8b0    prompt_lines=34  E_rows=0 SECTIER=0 PREMISES_heading=1
14:23:38.869Z U0      prompt_lines=54  E_rows=0 SECTIER=0 PREMISES_heading=1
16:17:33.992Z corpus  prompt_lines=42  E_rows=0 SECTIER=0 PREMISES_heading=1
16:43:54.099Z U4b     prompt_lines=39  E_rows=0 SECTIER=0 PREMISES_heading=1
```

### Probe 6 — REPLAYED THE REAL GATE BINARY against the five real prompts
```
2026-08-23T10:54:16.858Z  rc=2  Blocked: implementer-lane spec has no PREMISES block
2026-08-23T10:54:36.164Z  rc=0
2026-08-23T14:23:38.869Z  rc=0
2026-08-23T16:17:33.992Z  rc=0
2026-08-23T16:43:54.099Z  rc=0
```
Exactly reproduces the transcript's own hook outcomes (the 10:54:16 dispatch really was
`is_error=True` with that message; retried 20s later with a PREMISES heading added).
Gate copy verified non-ambiguous: cache and marketplace copies are byte-identical
(sha256 `c2cf959b…`), only version 1.21.0 exists.

### Probe 7 — MUTATION ARM: is the verification path live, or dead code?
Took the REAL allowed u8b0 prompt and appended ONE E row:
```
base              rc=0   (allowed — as it happened)
+ "E lint_rc <- the gate's exit code; 0 or 1; bounded; no PII"   rc=2  BLOCKED:
    "this spec triggers premise verification (a line anywhere in the prompt whose first
     letter is a capital E row-marker …)"
+ that E row AND "PREMISES-VERIFIED: /tmp/report.md"             rc=0   (allowed)
```
**The escalation path is LIVE and would have fired had row 9 been typed E instead of A.**
That is the finding's exact mechanism, proven by mutation on the real artifact.

### Probe 8 — the three re-litigations, from the tool's own `header` field
18 AskUserQuestion calls in the session; exactly three carry header `U8b0`:
- `10:02:16.510Z` "U8b0 — decision 9 picked (d) … How do you want it handled?"
- `12:48:11.005Z` "Decision 9 pinned option (d), which the lane has now proven impossible. What replaces it?"
- `14:24:07.230Z` "Now that you've seen the diagram: decision 9 pinned option (d), which is proven impossible. What replaces it?"
All three name "decision 9" literally. CONFIRMED.

### Probe 9 — premise-verifier count
Exactly ONE `fable-orchestrator:premise-verifier` dispatch all session:
`10:52:49.874Z | Verify U0 spec premises`. On U0. No E row existed in any spec, so the gate
could not have demanded it -> it was voluntary. CONFIRMED.

### Probe 10 — the timing arithmetic
Session min/max timestamp: `2026-08-23T09:43:00.457Z` -> `2026-08-23T18:05:22.502Z` = **8h22m22s**.
First U8b0 ask `10:02:16.510Z` -> BUILT `16:02:54.143Z` = **6h00m38s**. Both figures CONFIRMED (6.01h of 8.37h).
Corroborating anchors all exist verbatim: dissent `12:45:56.085Z` ("U8b0: dissent — option (d) is
provably impossible"), respec SendMessage `15:40:47.368Z`, BUILT `16:02:54.143Z` (commit `e4d3d27a`).

## WHAT I DID REFUTE: "waved through" is FALSE
The A row was not waved through. Three separate controls fired on it:
1. **It was escalated to the maintainer at `10:02:16.510Z`**, with `Switch to (a) wrap-at-lint-time`
   marked **(Recommended)** and a `Probe the runtime first, then decide` option that would have
   settled it empirically in minutes. The maintainer answered **"Dispatch (d) to codex anyway"**.
2. **The spec explicitly armed the dissent licence on that exact row** — row 9's own text ends
   "This is the assumption your dissent licence is pointed at" (spec:140).
3. **The dissent fired and worked**: `12:45:56.085Z`, "option (d) is provably impossible".
So the causal story "the gate's A-row escape hatch let it through unchallenged" is incomplete:
the architect identified the risk, recommended against it, offered a cheap empirical probe, and
was overridden. The gate finding stands; the word "waved through" does not.

## Caveat on the 6h00m: elapsed span, not exclusive cost
122 of the session's 393 tool_use calls (31%) fall inside the 6.01h window, and the window
contains demonstrably parallel work (the corpus resume, the premise-u0 verifier at 10:52,
the U0 implementer dispatch at 14:23). "Cost 6h00m" is wall-clock span with concurrency,
not 6h of exclusive effort.

## Contradiction / overlap with other findings in the set
- **Finding 8 OVERLAPS finding 1 (not a contradiction, but costs are NOT additive).**
  Finding 8's "two decisions asked bare, refused with a request for an explainer, then re-asked"
  are: (i) U8b0 `12:48:11` -> answer *"Can you visually show what it is doing now and why ot is
  failing … Use visuall artifact skills"* -> re-ask `14:24:07` "Now that you've seen the diagram";
  and (ii) Chunks 12/26 `15:43:08` -> *"Explain it to me with eli5 first"* -> `15:45:28`.
  So finding 1's THIRD re-litigation IS finding 8's first pair. Summing them double-counts.
- **Finding 11 independently REPRODUCED by me this lane.** I typed
  `python3 - <<PY … PY 2>/dev/null || uv run python …` and the hook denied it outright.
  The `||` fallback does not exempt the shape. Confirms finding 11 at first hand.
- No finding in the set contradicts finding 1.

## Verdict: refuted = FALSE. Every mechanical assertion verified against primary artifacts,
with a discriminating control arm and a live mutation arm. Only the characterization
"waved through" is refuted.

## GitHub repos touched
_None._ (All artifacts local: the fable-orchestrator plugin cache, the session transcript,
and the session scratchpad.)
