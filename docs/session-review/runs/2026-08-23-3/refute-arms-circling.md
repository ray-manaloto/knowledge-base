# Refutation lane: "kb-arms specs converged by re-running (46 invocations / 11 specs)"

Status: COMPLETE, 2026-08-18. Verdict: **NOT refuted in substance; every headline
NUMBER except one is wrong** (46→43, 11→12, ~4.2→3.6; the x7 worst case is exact).

## Method

Two independent probes of the same fact, cross-checked:

1. The lane's own evidence (`scratchpad/cmds/{A18,B,C,D,E,F,G}.txt`,
   `bash-commands.tsv`) — line-level grep + eye classification of every line
   containing `mise run kb-arms`.
2. An independent JSON parse of every in-window transcript
   (`~/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/*.jsonl`,
   mtime >= 2026-08-17): walk `message.content[]` for `tool_use` blocks with
   `name=="Bash"`, count shell lines whose stripped form starts with
   `mise run kb-arms` (or follows `;`/`&&`), and inspect the PREVIOUS line of
   every multiline hit to separate a heredoc-quoted command from a chained real
   run (script: `scratchpad/count_arms.py` + two inline context dumps).

Token-spelling arms run: `kb-setup arms` (13 rows — ALL pgrep/ps/until liveness
probes + one `--help`; zero direct invocations), `run -q kb-arms` / `mise exec
… kb-arms` / `kb_setup.arms` (1 row, prose in a directive-writing heredoc).
Negative controls: F/fb633adf has 0 kb-arms at substring level while
`grep -l kb-arms *.jsonl` matches 31 files, and the six small in-window
sidechain transcripts (7-26 KB) have 0 kb-arms with real content confirmed
(`sessionId` grep 14/16 hits) — the zeros discriminate.

## The re-derived count (per transcript, Bash tool_use only)

| session | transcript | invocations | specs |
|---|---|---|---|
| B | de3c5d58 | **4** | corpus-runner-findings x4 (3 standalone + 1 CHAINED after the suites→NODE-ID spec edit, cmd#141 L18) |
| C | 2bf99e26 | **1** | adapter-refusal-wiring x1 |
| D | c03754a0 | **3** | extraction-warning x3 (2 runs + 1 compound dry-run) |
| E | 49e2cc30 | **12** | assemble x3 · corpus-merge x3 · boundary x2 · inference-ceiling x4 |
| F | fb633adf | **0** | — |
| G | 6b974f05 | **9** | spend-and-output-caps x4 · review-round1-fixes x5 |
| A18 | 52f5798a | **14** | check-first x4 · f328 x3 · **corpus-chunk1 x7** (2 dry + 5 runs; cmd#246 chained after spec append `prev: EOF`, cmd#249 chained after re-derive edit `prev: PY`) |
| (current) | f1d1c0cf | 1 | check-first-separator-hang x1 — the review session's own bot-triage arm, outside the round tabulation |

**ROUND TOTAL: 43 invocations / 12 specs = 3.58/spec** (window-complete: 44/13).
Of the 43, **9 are `--dry-run` validations** (D1, G3, A18x5) → 34 mutation
sweeps ≈ 2.8/spec.

## Verdict per claim

| finding claim | verdict | evidence |
|---|---|---|
| 46 invocations | **WRONG — 43.** 48 lines contain the substring; 5 are prose-only carriers (review-report echo B#122 "It independently re-ran `mise run kb-arms` (10/10 died…)", prompt B#145, report B#162, commit messages B#202/A18#26). 48−2=46 suggests the lane excluded only two of the five. | per-transcript parse above |
| 11 specs | **WRONG — 12.** adapter-refusal-wiring (session C, 1 invocation, converged FIRST run — c handoff: "this round used kb-arms properly") is missing; dropping the one no-circle spec inflates the average. | 2bf99e26 parse; c handoff:86,109-115,225-226 |
| ~4.2 runs/spec | **WRONG — 3.6** (2.8 excluding dry-runs, which are the designed pre-run validation, not convergence re-runs) | arithmetic above |
| worst corpus-chunk1 x7 | **EXACT.** I first classified cmd#249 as prose and was wrong — the dry-run is chained AFTER the closing `PY` of the spec-edit heredoc. | A18 context dump, `prev: PY` / `prev: EOF` |
| extra runs attributed by handoffs to defects in the ARMS | **CONFIRMED VERBATIM** at all three cites: d:195-211 ("both failures were defects in MY arms" — dup plugin.json fixture rows; `test_query_with_stderr_is_incomplete` did not exist), e:150-155 ("this round had five [inert mutants]… all defects in MY arms… plus one CONTROL BROKEN"), a18:166-168 ("5/5, after kb-arms refused two anchors a refactor had moved") — corroborated in-transcript by cmd#249's own comment: "RE-DERIVED after the ledger-record refactor moved this line; kb-arms refused the previous anchor". | Read of the three handoffs |
| classes recurring across B, D, E, G, A18 | **4 of 5 legs hold.** B ✓ (handoff b item 3: a `suites` FILE entry "breaks the CONTROL"; the transcript shows spec edit → immediate re-run). D, E, A18 ✓. **G is the weak leg**: handoff g attributes its kb-arms activity to three TESTS that could not fail ("the FIX was right and the TEST was decoration") — kb-arms WORKING, not defective arms; only its third item ("a control arm could not reach its own control") reads spec-side. | b:153-160; g:84-89 |

## The probe defect (both directions)

The lane's `uniq -c` over substring-extracted command text cannot distinguish an
invocation from a QUOTATION of one inside a heredoc — review reports, prompts,
and commit messages quote the exact command, redirect and `| tail -N` included.
That is the already-documented pattern-matching-cannot-see-quoting class
(the #337 guard was rewritten to tokenise for exactly this). My first eye-pass
made the INVERSE error twice (B#141, A18#249 classified as prose when a real run
is chained after the heredoc delimiter) — caught only by inspecting the
line-before-the-match in the raw transcript. Neither direction is visible to a
substring probe.

## Also of note (out of the finding's frame)

- Review lanes re-ran specs INSIDE `codex exec`, invisible to any Bash count:
  B round-2 codex re-ran corpus-runner-findings (10/10 died), C's cold reviewer
  re-ran adapter-refusal end-to-end (4/4). True execution count > 43.
- The handoffs the finding cites frame several re-runs as the harness EARNING
  value ("A real coverage gap, invisible without running the sweep", d:204;
  "caught by kb-arms and none by reading", g:84) — the "circles" framing and the
  sources' own framing point opposite ways on the same events.

## Internal contradictions

- The finding's "11 specs" contradicts its own cited uniq-c evidence table,
  which lists 12 distinct spec paths (adapter-refusal-wiring included, from C.txt).
- Its "46" contradicts session e's own `kb-session-reflect` self-measure
  ("`mise run kb-arms … | tail` x12"), which pins E=12; with every per-session
  count pinned by the transcript parse, no assignment sums to 46.

## GitHub repos touched

_None._

## COVERAGE

- REACHED AND ANALYSED: Ray's 2026-08-18 directive in full (incl. addendum +
  clear-prep rulings); all 7 round handoffs in full (b, c, d, e, f, g, a18);
  all 7 cmds/*.txt evidence files; bash-commands.tsv; JSON-parsed all 7 round
  transcripts + the current session + the 6 small sidechains for kb-arms Bash
  tool_use (every multiline hit context-inspected); spelling variants armed.
- OPENED BUT NOT FINISHED: nothing.
- NEVER REACHED: the 5 out-of-window transcripts (correctly out of scope); the
  arms logs themselves (arms2-5.log — per-run pass/fail detail beyond what the
  handoffs state was not needed for the count or the attribution); lane-internal
  kb-arms executions inside codex (counted as noted, not enumerated).
