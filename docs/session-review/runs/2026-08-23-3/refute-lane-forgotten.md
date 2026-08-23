# Refutation lane: "lane forgotten" finding (71-manifest sweep + claude-code.manifest)

Task: refute "the 71-manifest sweep and claude-code.manifest advance fell out of
the owed chain entirely".

## Verified so far (2026-08-18, this lane)

- handoff g lines 57-59: CONFIRMED verbatim — "Still deferred by Ray,
  deliberately: the **graphify 0.9.46 bump**, the **71-manifest sweep**, and
  advancing `sources/claude-code.manifest` (2.1.226 → 2.1.234, needs a re-clone
  and re-extraction)."
- handoff 18-a Owed section (lines 124-151): carries the graphify bump (via the
  8-pin sweep) but NOT "71-manifest" or "claude-code.manifest" by those tokens.
  Read the WHOLE file (181 lines), not just 124-151: neither token appears
  anywhere in it.
- docs/direction/2026-08-18-ray-directives.md line ~188: the addendum analysis
  DOES contain `claude-code` — it is one of the 12 `[tool.*]` sections in
  currency.toml ("graphify, ffmpeg, mise, claude-code, hk, fnox, doppler,
  skillopt, uv, ruff, ty, codex"). So "contains neither" is FALSE for the token
  `claude-code`, though the MANIFEST ADVANCE is not named.

## Probes run (all 2026-08-18, this lane)

1. **THE OPPOSITE-ANSWER PROBE — `mise run kb-currency-check` (run now, rc=0):
   its FIRST drift line is exactly the "lost" item:**
   `claude-code: manifest — sources/claude-code.manifest pins v2.1.226 but the
   running version is 2.1.234 — the corpus describes code we do not run`.
   Source of that line: tracked `currency.toml:810` `[tool.claude-code]` +
   `:854` `manifest = "sources/claude-code.manifest"` (#242 CLOSED = the
   enforcement landed). Wired into EVERY session: `.claude/settings.json:51`
   SessionStart hook runs `mise run kb-currency-check`. A requirement re-announced
   by machine each session from tracked config is the opposite of "record lost".
2. **The 08-18 directive DOES contain `claude-code`** — addendum analysis,
   12-section currency.toml roster line ("graphify, ffmpeg, mise, claude-code,
   hk, fnox, doppler, skillopt, uv, ruff, ty, codex"). The finding's "contains
   neither" is a token-spelling bound: it searched `claude-code.manifest`.
3. **The 8-pin list and the claude-code manifest line come from the SAME check**
   — the 18-a Owed bullet quotes the "pin behind upstream" CATEGORY of
   kb-currency-check's output; the manifest drift is another category of the
   same output. Executing the owed currency sweep cannot miss it.
4. **Deferral origin found**: handoff f:47-48 "(Ray explicitly deferred the
   0.9.46 bump, the 71-manifest sweep and the follow-up review run BEHIND THIS
   LIST)" — sequencing, not dropping. Transcript fb633adf (Aug 17 17:28): the
   sweep was an AskUserQuestion OPTION label ("Everything in one round —
   Research, the 71-manifest sweep, the graphify bump and one kb-build
   together"); Ray chose "research first, alone", parking sweep+bump together.
   The bump IS carried in 18-a (Owed bullet 1 + bite-you #2 "its own round"
   ending in kb-build) — the sweep is coupled to that round by its own logic
   (one rebuild).
5. **Transcript 52f5798a (Aug 18 03:07, the 18-a-era session) READ handoff g's
   deferral lines** (window shows Read-numbered lines 55-62) — the deferral was
   seen, not lost to the writer.
6. **The "71" figure is stale**: `ls sources/*.manifest | wc -l` = **73**
   (2026-08-18). Restating "71-manifest sweep" verbatim would itself be the
   inherited-number failure; the durable fact is "advance every source
   manifest", and the drifted ones are machine-named (claude-code, mise) every
   session.
7. **Tracked files carry no "71-manifest"** — grep over docs/, .claude/,
   REGISTRY.md, currency.toml, CLAUDE.md → 0 (control: "graphify" hits). TRUE
   residue: the sweep token lives only in gitignored handoffs f/g + transcripts.
   But handoff g is a REQUIRED input to the session-review sweep now running
   (the workflow takes `handoffs` explicitly), so it has not fallen out of the
   owed chain — the finding itself read it there.
8. Memory dirs: no "71-manifest" (control: bare "manifest" hits 5 files).
   Issues: no "71-manifest sweep" issue; adjacent durable coverage exists —
   #225 OPEN (13 tool-tracking manifests, 5 drifted, nothing enforces),
   #184 OPEN (upgrade-everything round), #187 OPEN (re-extraction backlog
   class), #242 CLOSED (manifest-sync enforcement, landed).

## VERDICT: REFUTED as stated

- claude-code.manifest advance: decisively NOT lost — machine-carried, printed
  today, printed every SessionStart, from tracked config; directive names
  claude-code in the currency roster.
- 71-manifest sweep: token genuinely absent from 18-a + directive (finding's
  observation correct) but "fell out of the owed chain ENTIRELY / record lost"
  is false: recorded verbatim in handoff g (a required sweep input), coupled to
  the carried graphify-bump round, and its operative content (which manifests
  drifted) is machine-derived each session. NARROWER SURVIVING RESIDUE worth an
  issue: no TRACKED artifact names the all-manifests sweep; if .agent/ is
  cleaned before the sweep files issues, that one token's record dies with it
  (and its count is already stale at 73).

## Contradictions with the rest of the set

- The finding contradicts its own cited evidence (directive "contains neither"
  vs `claude-code` present in the addendum roster line).
- Any sibling finding treating the owed "currency: ALL EIGHT pins" item as the
  WHOLE currency obligation repeats the same category bound — the 8-pin list is
  one category of a two-category check whose other category names claude-code's
  manifest drift.
