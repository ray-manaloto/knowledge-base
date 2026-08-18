# refute-circles — ExitPlanMode churn finding

Transcript: /Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/f1d1c0cf-43e1-4aea-b777-1faefbce022c.jsonl (4,219,367 bytes, 1502 lines)

## Offered probe REPRODUCES exactly

10 rows, sizes 7554/8594/15009/18591/18436/24934/17782/24510/24550/13033
first 2026-08-18T12:31:42.057Z, last 2026-08-18T14:38:44.980Z => 2h07m02s. CONFIRMED.

## Tool-call arithmetic

- whole-file tool_use count = **204**, not 203 (jq: select(.type=="assistant")|(.message.content//[])[]|select(.type=="tool_use")|.name | wc -l)
- in window [12:31:42, 14:38:45) = **85** CONFIRMED
- before window = 81; after = 38; 81+85+38 = 204
- 85/204 = 41.7% -> "42%" holds; the DENOMINATOR 203 is off by one.

## What REPRODUCES (not disputed)

- 10 ExitPlanMode calls, exact byte-lengths and timestamps as offered.
- 12:31:42.057Z -> 14:38:44.980Z = 2h07m02s.
- 85 tool calls inside the window (awk on jq tsv).
- 7554 -> 24934 = 3.30x; cut to 17782; regrew to 24550; cut to 13033. Two expand/contract cycles.
- plan7 carries the verbatim heading `# Cut, on the advisor's argument` (scratchpad/plan7.md:271).
- token counts per plan (control: `session-review` present in ALL 10, `zzzqqqnonexistent` 0 in all 10):
  clear-prep first appears plan4 (12:56) 9 hits; `tune` first plan5 (13:02) 12 hits; both collapse at plan7 (13:32) to 2 and 1, both 0 in plan10.
- 12:56:12 -> 13:32:36 = 36m24s; 21 tool calls on a half-open window (22 inclusive of both ExitPlanMode endpoints, 20 exclusive).

## What FAILS

1. **"4 revisions AFTER plan #1" is 5.** Plans strictly between 12:31:42 and the
   13:18:30.717Z Agent launch: 12:42:06, 12:48:49, 12:56:12, 13:02:44, 13:11:23.
2. **The 203 denominator is measured from INSIDE a live, growing session.**
   Same jq, three times: 204 (09:5x), 206 (10:0x), file 4,219,367 -> 4,503,244 bytes,
   1502 -> 1523 lines, during this verification. 85/206 = 41.3% and still falling.
3. **The advisor cut FOUR items, not two** — plan7.md:274-278 lists Tune,
   `mode:'handoff'`, "Retry-a-dead-lane one tier down", "Closed-issue false-positive calibration".
4. **"were built" is false.** All 22 Edit/Write in the whole 2h07m window target
   `/Users/rmanaloto/.claude/plans/can-we-update-the-optimized-sky.md` (+1 scratchpad html).
   Zero implementation files touched. Nothing was built.
5. **"discarded work" is contradicted by the plan's own disposition text.**
   `mode:'handoff'` -> "**file as an issue**"; Tune -> "Keep `lanes.toml` + recorded yields;
   revisit at >=3 runs". `lanes.toml` (introduced BY the Tune branch at plan5) survives in
   plans 7/8/9 (4/4/3 hits). Converted, not discarded.
6. **The "circles" frame omits exogenous drivers.** User interrupt at
   2026-08-18T13:02:49.744Z `[Request interrupted by user for tool use]` (1 occurrence in file;
   control `zzzqqqnonexistent` = 0), then a NEW USER REQUIREMENT at 13:06:14 ("stored in git ...
   datetime timestamp with nanosecond precision and the git sha"). plan6 is the ONLY plan
   containing `nanosecond` (2) and `git sha` (2); `ledger` goes 0/0/0/0/6/9 across plans 1-6.
   The largest single jump (18436 -> 24934) is that requirement, not circling.
7. **Attributing all 21 calls in 12:56-13:32 to the two items is unmeasured** — that window
   contains the kb-advisor launch (13:18:30, critiquing the WHOLE plan), 2 AskUserQuestion calls,
   and shared-plan-file edits.

VERDICT: refuted = true. Headline arithmetic reproduces; the derived claims do not.

## Contradictions inside the finding set

- **Denominator disagrees three ways for ONE file.** `circles.md:57,99,287` says
  **203** tool calls; `refute-circles-deliverable-never-read.md:52` says
  "(1,530 lines, all **207** tool_use entries)"; my two runs of the same jq gave
  **204** then **206**. The file is the CURRENT session's live transcript
  (scratchpad path = f1d1c0cf-…), so every total is a snapshot of an unfinished
  session. No arm can rescue this figure; only the in-window 85 is stable.
- **circles.md's own Limitations section retracts the scope-item claim**
  (`circles.md:509-511`, verbatim): "The 10 `ExitPlanMode` payloads — I measured
  their lengths and first lines only; I did not diff consecutive plans, so 'what
  specifically was added then cut' is **inferred from titles + the advisor's
  stated verdict, not from a text diff**." I diffed them; the inference was wrong
  in three places (4 cuts not 2, dispositions were "file as an issue" / "revisit
  at >=3 runs", `lanes.toml` survived).
- **circles.md is internally inconsistent on the revision count**: `circles.md:70-76`
  calls the 13:18:30 critique "4 plan revisions after the first ExitPlanMode" while
  the same paragraph names the pre-critique peak as "plan #6 (24,934)". #6 is five
  revisions after #1.
