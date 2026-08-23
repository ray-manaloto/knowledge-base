# Refutation attempt — [context] finding: 20% threshold crossed 06:23:23Z, nothing proposed /clear-prep

Transcript: /Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/6ae19ff6-2b88-4aea-8fa7-c0430395e2da.jsonl
(2879 records; 550 assistant msgs with .message.usage; `jq -r '.isSidechain // "absent"' | sort | uniq -c` => 2879 absent, i.e. NO sidechain rows mixed in — subagent usage is in the subagents/ subdir, so the trajectory is main-chain only.)

## Probe 1 — reproduce the crossing, two independent metrics

ctx_in  = input + cache_creation + cache_read      (what is actually sent = context size)
ctx_all = ctx_in + output

06:21:22.407Z  198198 / 198655
06:23:09.815Z  198887 / 199142
06:23:12.765Z  199279 / 199334
06:23:18.122Z  199307 / 199563
06:23:23.244Z  200224 / 200494   <-- FIRST >= 200,000 on BOTH metrics
06:23:27.197Z  200603 / 200711
06:26:06.132Z  202337 / 202565

max ctx_all over ALL 59 usage rows strictly before 06:23:23.244Z = 199,563 (at 06:23:18.123Z) -> no earlier crossing that later dipped.

## Probe 2 — session start / never-compacted

first user record: 2026-08-21T06:08:39.811Z `<command-name>/clear</command-name>` (+ caveat at 06:08:40.927Z)
=> claimed start 06:08:40Z is right; 06:23:23.244 - 06:08:40.927 = 14m42s ("~15 minutes" OK).
`grep -c isCompactSummary` => 0; `jq 'select(.type=="summary")' | wc -l` => 0. Never compacted.
Peak ctx_all = 794,070 at 15:42:12Z with no compaction => the window is >= ~794k, i.e. 1M-class, NOT 200k.

## Probe 3 — what the orchestrator was doing at the crossing turn

06:23:18.123Z assistant TOOL:ToolSearch
06:23:23.274Z assistant TOOL:TaskOutput          <- the crossing request
06:23:27.221Z assistant TEXT:"Still waiting on the two Explore agents' reports; nothing new to report yet."
=> "early planning/polling on Explore agents" confirmed.

## Probe 4 — the NEGATIVE half, token-spelling broadened + control-armed

jq over ALL 550 assistant records with .timestamp < 15:06:00, matching
  compact|context window|context budget|context is|20% |context threshold|/clear\b   (case-insensitive)
=> 4 hits: 06:15:51, 06:20:50, 06:34:36, 06:44:32. Read all four: every one QUOTES Ray's older
   standing line *"report + file issues now, implement after /clear"* or lists "#401 clear-prep wiring"
   as owed work. None proposes clearing/compacting now.
Spellings also swept over the whole file: clear-prep(39 lines) clear_prep(3) clearprep(0) /clear(47) compact(4).
Every clear-prep mention before 15:06:04Z is tool_result text from prior-session docs (handoff, directive file,
skill_listing attachment) — timestamps 06:12:54, 06:13:11, 06:13:15, 06:14:23, 06:15:51, 06:20:02.
CONTROL ARM: same jq shape, term known present ("kb-check"), same pre-15:06 window => 32 hits.
So the probe discriminates; the zero is real.

## Probe 5 — the threshold's denominator (the one real refutation avenue)

"20%" could have meant 20% REMAINING (=> clear at ~800k, which would make nothing owed at 06:23Z).
Ray's own verbatim words close it:
  docs/direction/2026-08-18-ray-directives.md:32  "run /clear-prep once the context is at 20% (which right now is 200K tokens)"
  docs/direction/2026-08-19-ray-directives.md:300 "not hitting over 20% of context (200K for opus 5 in this session's model)"
  docs/direction/2026-08-21-ray-directives.md:107 "should have triggered or requested a /clear-prep ... since we went over the 20% context of current model"
  docs/direction/2026-08-21-ray-directives.md:117 "**a /clear-prep should have been requested when context passed 20% of the model's window** — recorded as a standing expectation."
=> 20% = 200K USED of a 1M window. The finding uses Ray's own threshold and arithmetic.

## Cross-check against the other findings in the set

- #27 ("ended at 783,653 tokens"): reproduces EXACTLY off the same trajectory, ctx_in at 15:39:52.260Z = 783653. Same metric definition. Agrees.
- #30: same fact, other lane. 15:06:04Z - 06:23:23Z = 8h42m41s ~ its "8h43m later". Agrees (it is a duplicate, not a contradiction).
- #23 ("/clear-prep called at 15:06:16.698Z"): matches the first assistant clear-prep record at 15:06:16.698Z. Agrees.
No finding in the set contradicts this one.

## VERDICT: NOT REFUTED. Every component reproduces; the denominator survives its own adversarial reading.
