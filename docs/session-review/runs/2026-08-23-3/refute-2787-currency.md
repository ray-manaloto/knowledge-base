# Refutation lane: "graphify #2787 / PR #2794 untracked in currency.toml"

Verdict so far: **NOT REFUTED — CONFIRMED**, every citation checked out and my own
probes reproduce the absence with live control arms.

## Probes run (2026-08-18, working tree = docs-directive-addendum, clean)

1. `grep -nE '2787|2794' currency.toml` → **rc=1** (no hits).
   Control arms in the SAME file, same command shape: `2484` → 2 hits;
   `kind = "issue"` enumeration → refs 2484, 2485, 2551, 2308, 2101, 2086, 1653,
   1824 (currency.toml:516-553). The probe discriminates; no token-spelling bound
   (refs are bare digit strings, digits grep matches any spelling).
2. Subject-spelling check (is the SAME issue tracked under a prose ref?):
   `grep -nEi 'query.budget|truncat|silent.loss|0\.9\.46' currency.toml` → rc=1,
   against control `graphify` → 109 hits. Not tracked under a prose name either.
   File is 1553 lines; issue-watch grep covered ALL of it (line numbers up to 1159
   returned), not just the 906-line first page.
3. **All 5 worktrees** (`git worktree list`): each `<wt>/currency.toml` → rc=1 for
   `2787|2794`, control `kind = "issue"` count 9-10 per file. No worktree carries
   the fix uncommitted.
4. `git log --all -S2787 --oneline -- currency.toml` → empty (no commit on ANY ref
   ever added it). Control arm pending: `-S2484` (expect ≥1 commit).
5. `grep -rn '2787|2794' docs/currency/` → rc=1 — even the committed 0.9.46 run
   report `docs/currency/runs/2026-08-17-graphify.md` never names it, matching
   F1's own "cross-checked against the 0.9.46 currency run: still absent".

## Citations verified verbatim

- Handoff f (`.agent/plans/session-2026-08-17-f.md:147-149`): "Also
  filed-but-not-tracked: graphify issue #2787 may have been fixed by PR #2794 —
  Ray flagged it, currency.toml watches 8 graphify issues and 2787 is not among
  them (control-armed: 2787 → 0 hits, 2076 → 18)." Also f:228: owed follow-up
  "resolve #2787/#2794".
- Handoff g (`session-2026-08-17-g.md:61-62`): "graphify #2787 / PR #2794 is
  unresolved and untracked in currency.toml."
- Handoff 18-a (`session-2026-08-18-a.md:149-150`): "Still owed from 2026-08-17:
  … graphify #2787 / PR #2794 is untracked in currency.toml."
- Review F1 (`.agent/kb/reports/agents/2026-08-17-session-review.md:186-200`):
  Ray's verbatim flag (transcript eb35109b, 2026-08-17T02:24:19Z), "Status: not
  tracked anywhere. Cheapest possible moment to fix is now, mid-resync."

## Provenance nuance (not a refutation)

Ray's verbatim flag lives in transcript `eb35109b` — the file just OUTSIDE the
sweep's mtime window (Aug 16 21:36 local ≈ 2026-08-17T02:24Z UTC, consistent).
The finding says "Ray flagged it in session f"; strictly, handoff f RECORDS the
flag and the review report attributes the quote to eb35109b. Same fact either way.

## Not discharged elsewhere (all probes completed 2026-08-18)

- Directive `docs/direction/2026-08-18-ray-directives.md` read IN FULL: names the
  18-name roster, the 8-pin sweep, the graphify 0.9.46 gate — nothing tracks or
  discharges 2787/2794; the addendum's roster/status table never mentions it.
- `git log --all -S2787 -- currency.toml` → empty across ALL refs; control
  `-S2484` → `27bf6910` (the commit that added 2484), so -S discriminates.
- Both stashes (the 2026-08-13 codex-era currency WIPs — the "backup" era):
  `git show stash@{0,1}:currency.toml | grep -cE '2787|2794'` → 0 each.
- UPSTREAM STATE, which STRENGTHENS the "owed": issue #2787 is **OPEN**
  ("detect() writes converted sidecars into the scanned tree; cache_root does
  not redirect them") and PR #2794 is **OPEN, mergedAt null — NOT merged**. The
  "may have been fixed by PR #2794" question is still live, not moot; 0.9.46 did
  not ship it.
- KB issue tracker: `gh issue list --search 2787 --state all` → only #289
  ("Restore kb-build after strict Graphify source-detection preflight"), whose
  BODY has 0 hits (control 'raphify' → 4) — the match is one passing mention in a
  COMMENT ("Graphify-Labs/graphify#2787. The cleanliness check now ignores
  UNTRACKED…"). A comment mention is not tracking; F1's "not tracked anywhere" is
  fractionally softened, the finding under test not at all.

## Contradiction with other findings in the set

None: handoffs f, g, 18-a, review F1, the committed 0.9.46 currency report, and
my fresh probes all agree — absent and owed. Second routes (worktrees, all git
refs, stashes, docs/currency/, KB issues) agree with the first.

## VERDICT: NOT REFUTED — CONFIRMED

The original probe (`grep -n 2787 currency.toml` → rc=1) was NOT a
one-faced coin: the same shape finds 2484/2076 in the same file, there is no
spelling bound (refs are bare digits, matched in any rendering), no display or
depth bound (my re-probe covered the full 1553-line file, all refs, all
worktrees, both stashes), and the rc=1 is a real grep miss on a local file, not
a redirect/parse artifact.

## COVERAGE

- REACHED AND ANALYSED: currency.toml (lines 1-906 read + unbounded greps over
  all 1553 lines: issue-ref enumeration, subject-term and digit greps with
  controls); the 2026-08-18 directive IN FULL; handoffs f, g, 18-a IN FULL;
  review F1 (report lines 185-214); git history of currency.toml across ALL refs;
  all 5 worktrees; both stashes; docs/currency/ recursively; upstream
  #2787/#2794 via gh; KB issue search + #289 body and comments.
- OPENED, NOT FINISHED: currency.toml lines 907-1553 (grep-covered, not
  line-read); `2026-08-17-session-review.md` (read only the F1/F2 region of 554
  lines).
- NEVER REACHED: handoffs b/c/d/e (the flag entered the record at f; a discharge
  there would be overridden by the later f/g/18-a restatements, and the absence
  itself is machine-verified in the present, so they cannot flip the verdict);
  the .jsonl transcripts (the Ray-flag quote was taken from the review report,
  not re-derived from eb35109b); no kb-query graph pass.

