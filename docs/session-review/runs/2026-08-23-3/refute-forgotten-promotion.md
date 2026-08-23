# Refute lane — "round-2 cold-review residuals live only in gitignored .agent/"

## Probes run (as of 2026-08-21, branch corpus-gate-bundle-0821, HEAD b30a80c9)

1. `ls -la .agent/kb/reports/agents/` → cold-review-lane1.md (19,025 B, Aug 21 03:02),
   -lane2.md (22,010 B, 03:42), -lane3.md (21,802 B, 08:41), -round2.md (24,763 B, 09:57). Present.
2. `git check-ignore -v .agent/kb/reports/agents/cold-review-round2.md`
   → `.gitignore:150:.agent/` rc=0.
   CONTROL: same command on `docs/research/reports/2026-08-21-session-review-synthesis.md` → rc=1.
   Probe discriminates; the four files ARE gitignored.
3. The finding's OWN probe is token-spelling-bounded:
   `git ls-files docs/research/reports/ | grep -i cold-review` → rc=1 (0 hits), BUT this repo's
   promoted-review naming convention is `review-<sha>-cold.md` (agent-report-persistence rule 1),
   which can never contain the substring "cold-review".
   CONTROL: `git ls-files | grep -i cold` → 20 tracked files, incl.
   docs/research/reports/2026-08-05-graphify-0934-review/review-*-cold.md.
   So the offered probe could only have returned 0 regardless of promotion.
4. Re-probed WITHOUT that bound, at content level:
   `git grep -n 'Cold review — commit' -- .` → 4 tracked hits, all older rounds
   (review-5204e57-cold.md, review-ea6ab63-cold.md, review-navigable-round1/2-cold.md).
   ZERO for this round's SHAs. CONTROL passes (finds the older promoted copies).
   `git grep -c -E 'a67cbac4|d8114ab1|ebcf9fcb|3d9bb3ff|c720f1c9'` → only arms toml + 3 source
   files, no report copy.
   ⇒ the "never promoted" half SURVIVES a de-bounded probe.

## 5. The "ONLY durable record" clause — PARTIALLY refuted

- GitHub issue **#434** (created 2026-08-21T15:50:55Z) reproduces ONE residual in
  full — quoting `cold-review-round2.md:42-81` P2-1/P2-2 verbatim — so that residual
  IS durably recorded off-machine. #432 and #433 also cite the gitignored report paths.
  Probe: `gh issue list --state open --limit 100 --json number,title,body --jq
  '.[] | select((.body+.title)|test("cold-review-(lane|round)"))'` → 432, 433, 434.
- Tracked `docs/direction/2026-08-21-ray-directives.md` (addendum) names round 3 as
  "one bounded codex lane for the truth/correctness residuals plus the two cheap design
  fixes — lowercase proxy names in the refusal/exemption sets, a typed CLI refusal
  instead of a traceback". So two residuals are named in a TRACKED file.
- BUT the truth/correctness residuals are NOT recorded anywhere durable and are live at HEAD:
  - round2 **P2-5**: `git grep -n 'pinned 0.9.45'` → graphify_semantic_corpus.py:922,
    graphify_semantic_corpus_run.py:31, :104, :890 (four labels under a 0.9.48 pin).
  - round2 **P2-4**: docs/agents/evidence/issue-301/prototype-corrected-launcher.py:269
    still calls the 2-arg `stage_chunk`.
  - No open issue names either: `gh issue list … test("0\\.9\\.45|stage_chunk|…")` →
    #426 (_ACCEPTED_GRAPHIFY_RUNTIME), #421 (uv.lock reason / baseline counts), neither.
- No committed work-memory entry covers this round's cold reviews: newest tracked
  `graphify-out/memory/` file is `query_20260821_040445_…` (before the round-2 reviews at 09:57);
  `git status --short graphify-out/memory` → 0 untracked.

## 6. No promoted copy exists, tracked OR untracked
`git ls-files --others --exclude-standard docs/research/reports/` → 0.
CONTROL: created `docs/research/reports/ctrl_probe_tmp.md` → detected; removed.
(A first control using a dot-prefixed name was silently eaten by
`~/.gitignore_global:5:._*` — itself an instance of a bounded probe.)

## Verdict
**NOT refuted** on its load-bearing content. The offered probe was defective
(token-spelling bound), but a de-bounded probe returns the same answer.
One clause overclaims: "the only durable record" is false for the proxy-frozenset
residual (#434) and for the two design fixes (tracked directive); it is true for the
truth/correctness residuals, which are the bulk of round 3's scope.

## GitHub repos touched
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issue and git history probes.
