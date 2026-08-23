# Refutation lane: "#328 auto-closed by the #338 squash with remaining work unchecked"

Lane: refute-328-autoclose. Date: 2026-08-18. Task: try to refute the finding.

## VERDICT: NOT REFUTED — CONFIRMED on every load-bearing element, and SHARPENED

The close was not merely mechanical — it was triggered by the very sentence
written to prevent it.

### Confirmed, with the probe that could have said otherwise

1. **State**: `gh issue view 328 --json state,stateReason,closedAt` →
   `CLOSED / COMPLETED / 2026-08-18T04:33:32Z`. (Would have read OPEN had it
   been reopened — the probe discriminates.)
2. **Mechanism**: closed event carries
   `commit_id 791f53c2b33476c8a7817f7a3d4243ae3357a26d` (the #338 squash);
   PR #338 `mergedAt 2026-08-18T04:33:31Z`, merger sortakool (Raymond
   Manaloto). **Merge→close gap is one second** — mechanical, not a click.
   Timeline (`gh api .../issues/328/timeline`) has **no `connected` event** —
   no manual PR↔issue link, so not a deliberate closure.
3. **THE SHARPENING**: `git show -s --format=%B 791f53c2 | grep -n 328` →
   line 69: **"Does NOT close #328."** That is the only keyword-adjacent
   `#328` reference in the message (line 1 `fix 328` has no `#`; lines 27/30
   have no adjacent keyword). GitHub's closing-keyword parser is lexical and
   negation-blind: `close #328` inside "Does NOT close #328" auto-closes on
   landing on the default branch. **The sentence recording the intent to keep
   the issue open is what closed it.** (Exact-trigger attribution is
   high-confidence inference — GitHub does not expose which text matched — but
   it is the only candidate present in commit message or PR body.)
4. **Last comment**: exactly 1 comment (sortakool, 2026-08-17T15:43Z), titled
   "Partly fixed ... **and it does not close**", ending `### Remaining work`
   with three unchecked `- [ ]`; boxes 1 and 2 carry "Ray ruled" verbatim
   ("reviewed CLASS with the count reported"; "count them all, then decide").
5. **Invariant 3 live probe**: `mise run kb-currency-check` (2026-08-18, this
   lane) → "graphify: build-stamp — artifacts have never been stamped —
   rebuild pending" and "[graph] no graph has been built here yet (no build
   stamp) — run `mise run kb-build`". Remainder box 3 is still owed TODAY;
   the graph is not currently reproducible from committed inputs. Handoffs
   c:35-39 and d:109 use the same invariant-3 framing.
6. **"Never noticed"**: linear scan (`scan328.py`, scratchpad) over the four
   post-close transcripts: 6b974f05 (the merge session, ended 21:42 PDT;
   close was 21:33:32 PDT) — 755 '328' occurrences, **0** within ±70 chars of
   any 'clos'; 52f5798a (ended 03:07 Aug 18, wrote handoff a) — 617/0;
   d1e6ab78 0/0; 7604bd97 0/0. **Positive control fired** on a synthetic
   "#328 was auto-closed" line, so the scanner discriminates. Bound declared:
   ±70-char window, substring 'clos'.
   Handoff `session-2026-08-18-a.md` (written 03:07 Aug 18, 5.5h post-close)
   never mentions the issue; its "Owed" list carries currency/roster/rumdl/
   betterleaks/kingfisher/20%-trigger/worktree-audit but **none of the three
   #328 remainders**. MEMORY.md still says "#328 PARKED (ef3f04d6)".

### Two precision notes (do not change the verdict)

- **"Every handoff said '#328 stays OPEN'" is inflated.** Verbatim in exactly
  TWO of seven: d:271, e:199. b: zero mentions; c: pre-work ("NEXT TASK —
  #328"); f:9-10 / g:12,50: branch "untouched"/pending; a: silent. The
  substance survives — every handoff that speaks to the state treats it as
  open, and none records the close — but the finding's "every" overstates.
- **"No open tracker for two of the three remainders" needs its footnote.**
  #289 (OPEN, "Restore kb-build after strict Graphify source-detection
  preflight") plausibly tracks remainder 3 — its required outcome includes "a
  complete, warning-reviewed build receipt ... over the 71-source corpus" and
  its last comment tracks progress ("Preflight half is done — merged as
  #330"). #131 (OPEN, zero-node warnings) is ADJACENT to remainder 1 but its
  last activity is the 0.9.40 era and it does not carry Ray's reviewed-CLASS
  ruling; the #328 census effectively answered #131's question. Remainder 2
  (corpus-wide #2551 count) has no open issue — upstream #2551 is only a
  `currency.toml` watch. So "two of three" is the right arithmetic under the
  ruling-bearing reading, with #131 as partial credit on remainder 1. No
  successor issue exists: highest open issue is #335 (2026-08-17).

### Contradictions with other findings

None found in any probed artifact. Handoffs d/e, MEMORY.md ("PARKED"), the
squash commit's own "Does NOT close #328", and the issue comment all agree the
issue was meant to stay open — which corroborates rather than contradicts.
The only tensions are the two precision notes above, both in the finding's
WORDING, not its substance.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issue #328/#289/#131 state, PR #338 merge metadata, timeline events

## COVERAGE

- **Reached and analysed**: issue #328 (state, events, timeline, sole comment);
  PR #338 (merge metadata, body); squash commit 791f53c2 full message; open
  issue list (all 90 titles); #289 and #131 bodies + comments; all seven
  handoffs read IN FULL (b, c, d, e, f, g, 2026-08-18-a);
  docs/direction/2026-08-18-ray-directives.md in full; kb-currency-check live;
  4 post-close transcripts scanned for close-awareness with a fired control;
  MEMORY.md claims cross-checked.
- **Opened but not finished**: none.
- **Never reached**: transcripts older than the close (not needed — the claim
  is about post-close noticing); the graphify corpus graph for this question
  (one kb-query ran, returned nothing relevant — the issue tracker is not
  ingested, expected); re-running `kb-build` itself (expensive; the live
  currency probe already answers the reproducibility question).
