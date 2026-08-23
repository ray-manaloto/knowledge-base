# Refutation lane: "CLAUDE.md pins graphify at 0.9.44 while the repo uses 0.9.45"

Verdict: **NOT REFUTED — CONFIRMED by five independent routes.** The original probe
(`grep -n graphifyy` over both files) is a probe that CAN discriminate and did: it returned
two different versions from two files, and every alternate route agrees with it.

## Probes run (all 2026-08-18, this lane)

1. Working tree (branch `docs-directive-addendum`): `grep -n graphifyy CLAUDE.md pyproject.toml`
   → CLAUDE.md:177 `exact graphifyy[all]==0.9.44` · pyproject.toml:32 `"graphifyy[all]==0.9.45",`.
2. Main (`git show main:CLAUDE.md|main:pyproject.toml`): identical — not a branch skew. main=2b364443.
3. Installed truth: `uv.lock` → `name = "graphifyy" / version = "0.9.45"`; and the 2026-08-18
   `kb-currency-check` recorded in `docs/direction/2026-08-18-ray-directives.md:61` reads the pin as
   0.9.45 ("graphify 0.9.45 -> 0.9.46"). So "a version the repo does not use" is accurate.
4. History, with control arms:
   - `git log -S "graphifyy[all]==0.9.45" -- CLAUDE.md` → EMPTY. Control: same shape with
     `==0.9.44` → bc79cfa0. CLAUDE.md NEVER said 0.9.45.
   - The 0.9.45 bump commit `ed20a77d` (#331, 2026-08-17 07:03) touched pyproject.toml,
     currency.toml, uv.lock, docs/currency/**, tests — **not CLAUDE.md** (full --stat read).
5. Gate coverage: currency.toml's 8 `[[tool.graphify.ref_binding]]` rows (lines 145–196) target only
   `graphify_baseline.py`, `graphify_semantic_corpus.py`, `graphify_semantic_slice.py`,
   `sources/graphify.dispositions.json`. **No row reaches CLAUDE.md**, so the drift is structurally
   invisible to `kb-currency-check`. (Control: `grep -n CLAUDE currency.toml` does hit other, unrelated lines.)

## The timeline is sharper than the finding: this is the SECOND lag of the same line

- `f131ea1c` (2026-08-12, #280) introduced the restatement into CLAUDE.md as `0.9.42`.
- `98b116fd` (2026-08-15 22:18, #325 "resync every pin to 0.9.44") touched CLAUDE.md but left this
  line at 0.9.42 — the follow-up doc-sync `bc79cfa0` (2026-08-16 01:06, #327) moved it 0.9.42→0.9.44.
- `ed20a77d` (2026-08-17 07:03, #331) moved pyproject to 0.9.45 and no commit since has touched the
  CLAUDE.md line. The 0.9.44-era lag got its cleanup PR; the 0.9.45 one never did.

## One precision caveat (does not refute)

- CLAUDE.md does not *pin*; pyproject.toml is the pin, CLAUDE.md:177 *restates* it. Same defect class
  ("a revision that tracks the pin without being one" — the twelve-places memory's own shape).
- Whether CLAUDE.md:177 is counted inside the memory's "TWELVE/THIRTEEN places" is UNVERIFIED: the
  memory file body (`a-revision-is-restated-in-twelve-places.md`) says twelve and enumerates only
  code/artifact sites; MEMORY.md's index line says THIRTEEN; neither enumerates CLAUDE.md. "Missed
  the auto-loaded doc" is true as an outcome regardless.

## Contradictions in the set: NONE — two sibling probes AGREE

- `.agent/kb/reports/agents/unpinned.md:70` — "Root CLAUDE.md still says 'exact graphifyy[all]==0.9.44' — stale vs pyproject 0.9.45".
- `.agent/kb/reports/agents/contradicted.md:44-45` — same claim, same anchors.
- `deterministic-reviewers-2026-08-17.md:157` shows the resync session's heredoc (`OLD_REF, NEW_REF = "v0.9.44", "v0.9.45"`)
  editing `graphify_baseline.py` — corroborates the resync's scope was code files, not CLAUDE.md.
- grep of all other reports in `.agent/kb/reports/agents/` for `0.9.44` found no report asserting the files agree.

## Relevance clause verified too

The 0.9.46 bump is owed (directive line 24 "right now the latest version is 0.9.46"; handoff f "Ray's
ruling: bump now — not started"; handoff g "still deferred"; handoff 2026-08-18-a "graphify 0.9.45→0.9.46"
under Owed), and the bump procedure is exactly a restated-revision sweep ("the revision lives in
THIRTEEN places", "the graphify bump is four coupled places"). A stale restatement in the auto-loaded
doc is live input to that sweep.

## COVERAGE

- **Reached and analysed**: CLAUDE.md + pyproject.toml (working tree AND main), uv.lock, git history
  of both files (-S both directions with controls), bump commit ed20a77d --stat, resync commits
  98b116fd/bc79cfa0/f131ea1c, currency.toml ref_binding block (lines 143–200), the twelve-places
  memory file, docs/direction/2026-08-18-ray-directives.md IN FULL, all 7 mandated handoffs IN FULL
  (b,c,d,e,f,g,2026-08-18-a), sibling lane reports greped for the claim (all 9 files that mention
  0.9.44/0.9.45), one kb-query (graph-first toll; TRUNCATED, not load-bearing).
- **Opened but not finished**: none.
- **Never reached**: the .jsonl transcripts themselves (not needed — the claim is about repo file
  state, verified directly); the exact identity of the "13th place" in MEMORY.md's THIRTEEN
  (labelled unverified above); a live `mise run kb-currency-check` re-run (its 2026-08-18 output is
  already recorded verbatim in the directive doc I read).
