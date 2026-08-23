# Refutation probe — "lane circles" finding 1 (corpus-run enablement loop)

Verifier lane: refute-circles-corpus-loop (2026-08-18). Verdict: **NOT REFUTED —
CONFIRMED**, every load-bearing figure re-derived independently. Two precision
notes, neither changing substance or direction.

## Verdict per element

| claim | verdict | evidence |
|---|---|---|
| 23 plan / 15 verify / 9 run invocations | **CONFIRMED, twice-derived** | (a) `grep -c 'kb-graphify-semantic-corpus -- <sub>' cmds/{B,C,D,E,F,G,A18}.txt` reproduces plan 6/4/0/3/0/4/6, verify 5/3/0/5/0/0/2, run 0/0/0/5/0/0/4; (b) independent raw-.jsonl recount (`recount_corpus.py`, Bash tool_use ONLY, regex `kb-graphify-semantic-corpus\s+--\s+(plan|verify|run)\b`, all 14 in-window transcripts) → GRAND plan=23 verify=15 run=9, per-file identical, sidechain=0, D/F/CUR/6-small=0 |
| the counts are invocations, not prose | **CONFIRMED** | matched lines are real commands (`env -u AWS_* mise run kb-graphify-semantic-corpus -- verify …`); D raw has 15 prose mentions vs 0 invocations (the original lane's own control, re-armed) — the method discriminates |
| citing only B/C/E/G/A18 was a bound? | **NO** | D.txt and F.txt exist and count 0/0/0 each; the 6 small transcripts and CUR also 0. Omission was correct, not a blind spot |
| >=11 stated re-plans | **CONFIRMED** | b:133 "re-planned and re-authorized four times", e:122 "Re-planned and re-authorized **twice**", g:95 "The plan was re-planned FIVE times" = 11; a:99-101 restates "five times". Cited lines drift <=1 (b:132/e:123 vs actual 133/122); g:95 exact |
| 7 mv-asides of the plan dir | **CONFIRMED count; label 5/7 strict** | 7 mv commands touching `graphify-semantic-corpus` (C1/E3/G1/A18-2). Note: A18's 2 move `graphify-out/graphify-semantic-corpus-chunks/` (evidence), not the plan dir. Against that, **17 `rm -rf` asides** of the plan dir chained before re-plans — aside churn is UNDERstated. My first probe had a token-spelling bound (required the task token `kb-…`; the dir has no `kb-` prefix) and found 2; the corrected probe found 7 |
| 4 blockers, serial | **CONFIRMED** | 8192 cap: e:64-77 (measured 31,887-token need, API quote, control-armed); O_NOFOLLOW/$TMPDIR 58/58 markers: e:112-117, still blocking at g:51-54, shipped #338; cumulative cap: absent per e:55-60, built #336 (g:21-26), REBUILT durable #339 (a:57, a:66-72) = "built twice"; scope drift: a:73-76 (61/109 nodes to 26 phantom files, nondeterministic). Serial E → F/G → A18, each surfacing only after the previous cleared |
| ~28h then RE-SCOPED | **CONFIRMED** | first corpus tool_use 2026-08-17T03:01:57Z → last 2026-08-18T07:27:40Z = 28h26m (my timestamps); circles.md's ~27h40m is summed session time — both land on ~28h. RE-SCOPE: directive 225-233 verbatim ("the 5-file chunking may be wrong… SUPERSEDED for the run itself"), a:78-82 |
| 0 of 58 chunks merged | **CONFIRMED** | a:75-76 both chunk-1 runs REFUSED by the staging gate; `ls sources/extractions/ | grep -i graphify` → only `graphify-2026-08-06-docs.json`, committed `d5da30c7` (#197, pre-round; control: dir holds 25 chunks); `graphify-out/graphify-semantic-corpus/` (mtime Aug 18 02:27) holds only plan artifacts; the `-chunks` evidence dir is moved to A18's scratchpad (a:110-114, matches the 2 A18 mv commands) |
| chunk-1 $1.32 at 0.9.45, re-buy owed after the bump | **CONFIRMED** | directive:228 "(measured 1.32 USD/chunk x 58)" = ~$77; a:63-65 ledger `{"total_usd":1.3249605,"charges":1}`, explicitly superseding the inherited $1.12/~$65 estimate (e:59, f:58); pin is still `graphifyy[all]==0.9.45` (pyproject.toml:32) with 0.9.46 mandated (directive:24, 60-65), and a:94-98: committed evidence must be RE-RUN at the new version. Precision: a's bite 2 names the SLICE receipt; the chunk-1 re-proof follows from the same 0.9.45-evidence coupling + the re-scope. Same class, both owed |

## Could the original probe only have produced its answer? No.

- The grep had opposite-answer capacity: it produced 0 for D/F and nonzero for
  the rest; my independent recount found 0 in 8 of 14 files.
- The `-- run` anchor is immune to the `mise run` substring trap.
- Mentions were excluded by construction (extracted tool_use commands), armed by
  the D 15-mentions/0-invocations control.

## Contradictions with other findings in the set

**None found.** The only cross-artifact numeric tension is chunk-1 cost $1.12
(session-E measurement, quoted in `2026-08-17-session-review.md:66-67` and
`forgotten-cap-hunt.md:81-87`) vs $1.32 — resolved INSIDE the record: a:65 marks
the ~$65/$1.12 figure inherited-and-superseded; the directive carries $1.32 as
measured. The sibling `refute-lane-circles.md` tests finding 2 (review
treadmill); its A18 report inventory does not touch finding 1.

## COVERAGE

- REACHED AND ANALYSED: all 7 cmds/*.txt (counts + matched-line inspection); all
  14 in-window raw transcripts via streamed tool_use recount (counts, sidechains,
  timestamps, mv/rm sweeps); all 7 handoffs b–g + 2026-08-18-a IN FULL; the
  2026-08-18 directive IN FULL; circles.md + refute-lane-circles.md; pyproject
  pin; sources/extractions/ + graphify-out/ disk state with control arms;
  targeted $1.12/count grep across sibling lane reports.
- OPENED, NOT FINISHED: the sibling lane reports other than circles/refute
  (grepped for contradicting figures only, not read line-by-line).
- NEVER REACHED: raw verification of the "7 'plan already exists' refusals"
  sub-count (23 raw string occurrences across transcripts confirm the refusal
  class exists; per-event count not derived — it is not in the finding under
  test); per-invocation rc of each of the 23 plan calls (denied-vs-ran split).
