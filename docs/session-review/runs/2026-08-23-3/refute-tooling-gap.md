# Refutation attempt — tooling-gap finding (20% context threshold / clear-prep)

CLAIM: "Session context (Fable-5, 1M-class window) crossed the 200,000-token 20%
threshold at 06:23:23Z, ~15 minutes into a 9.5h session, and no /clear-prep
proposal was ever raised by the assistant — Ray had to volunteer it himself at
15:06:04Z, 8h43m later."

Transcript: /Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/6ae19ff6-2b88-4aea-8fa7-c0430395e2da.jsonl
(2879 lines at probe time; the reviewed session IS the current one, still appending.)

## Probe 1 — the crossing timestamp (line number is off by one, fact holds)
Evidence said "line 363". Line 363 is an `attachment` with usage=null.
The usage block is LINE 364.
  sed -n '364p' | jq -> ts 2026-08-21T06:23:23.244Z, type assistant, isSidechain false,
  input+cache_creation+cache_read = 200224
Full main-chain trace: ...199279 (06:23:12) -> 199307 (06:23:18) -> 200224 (06:23:23).
=> 06:23:23.244Z IS the first main-chain turn at/over 200,000. VERIFIED.

## Probe 2 — control arm on isSidechain (does the file mix in subagent contexts?)
  grep -c '"isSidechain"'      -> 2023
  grep -c '"isSidechain":true' -> 0
No sidechain turns in this file, so the 200,224 is orchestrator context, not a
subagent's. (This was the most likely way the number could have been wrong.)

## Probe 3 — does "20% context" mean 20% USED or 20% REMAINING?
Primary artifact, Ray verbatim:
  docs/direction/2026-08-18-ray-directives.md:32
  "> and we need to start getting ready to run /clear-prep once the context is
   at 20% (which right now is 200K tokens)"
=> 20% USED = 200K. The finding's reading is Ray's own. The "20% remaining"
   reinterpretation (which would have flipped the whole finding) is REFUTED.

## Probe 4 — was a clear-prep proposal raised earlier? (in progress)
  grep -ci variants: clear-prep 39 | clear_prep 3 | clearprep 0 | "clear prep" 0 | /clear 47
  control arm: kb-review -> 31 hits in same file, so the grep discriminates.
  Assistant-authored mention BEFORE the crossing: line 203, 06:15:51.580Z —
  a SendUserMessage quoting the handoff's sequence ("implement after `/clear`")
  and listing "#401 clear-prep wiring" as OWED. NOT a proposal to clear now.

## Probe 4 (concluded) — no earlier proposal, across 5 spellings + 18 phrases
Assistant-authored `/clear` mentions before 15:06 are lines 203 (06:15:51.580Z),
314 (06:20:50), 472 (06:34:36), 622 (06:44:32). Read verbatim, ALL FOUR are the
same quotation of Ray's standing 2026-08-21 instruction:
  "Ray's standing instruction (docs/direction/2026-08-21): *\"report + file issues
   now, implement after `/clear`\"* — this session is that implementation round."
i.e. describing this session as the POST-/clear round. None proposes clearing now.

Broad context-language sweep (whole file, counts):
  'context is getting full' 3 | 'context window' 5 | 'context left' 0 |
  'context remaining' 0 | 'running low on context' 0 | 'auto-compact' 0 |
  'autocompact' 0 | 'compact' 4 | 'context budget' 2 | 'context usage' 0 |
  'token budget' 0 | 'context limit' 0 | 'context threshold' 0 | '20% context' 17
Every hit for '20% context', 'context window', 'context budget' and
'context is getting full' is at line >= 2533 (>= 15:06:04.550Z). The only
pre-15:06 hit in the whole sweep is 'compact' at line 66 (06:13:11, a tool
result, unrelated). CONTROL ARM: 'kb-review' -> 31 hits, '20% context' -> 17
hits in the same file with the same command shape, so the grep discriminates.

## Probe 5 — did any earlier AskUserQuestion offer a clear option?
  jq over tool_use name=="AskUserQuestion" -> 5 calls total:
  06:15:58.595Z "Orientation is done. What should this session start on?"
  06:31:40.112Z "G2 — the slice's evidence binding lags at v0.9.45 BY DESIGN..."
  08:29:54.628Z "Lane 2 added a pyproject.toml per-file-ignore (PLR0913...)"
  14:59:40.974Z "The round-2 cold review (Opus, by ref) found residuals..."
  15:09:40.436Z "Session-review preflight — the selector resolves the window..."
None of the four pre-15:06 asks mentions context. VERIFIED.

## Probe 6 — is the "1M-class window" premise sound?
  max prompt total = 794,037 @ 15:42:12.423Z, model claude-fable-5, and
  'auto-compact'/'autocompact' -> 0 hits, so the session was never compacted.
  => the window is >= ~794K. 1M-class holds; 200K is ~20%.
  models seen in file: claude-fable-5 (only).

## Probe 7 — is line 2533 really Ray, or a tool result? (it is BOTH)
It is Ray's AskUserQuestion ANSWER, carried as a tool_result:
  "The user answered: \"...\"=\"/clear-prep\n\noption 1 on new session after /clear\n\n
   context is getting full. But, run session-review workflow: ...
   - should have triggered or requested a /clear-prep to have been run since we
     went over the 20% context of current model"
The finding's subject corroborates the finding in his own words.

## Probe 8 — semantics control (the vector most likely to flip this)
  docs/direction/2026-08-18-ray-directives.md:32 (Ray verbatim)
  "> and we need to start getting ready to run /clear-prep once the context is
   at 20% (which right now is 200K tokens)"
20% USED = 200K. Not 20% remaining. The flip is unavailable.

## Arithmetic
session start 06:08:40.927Z -> crossing 06:23:23.244Z = 14m42s ("~15 minutes") OK
crossing 06:23:23.244Z -> Ray 15:06:04.550Z = 8h42m41s ("8h43m") OK

## VERDICT: refuted = FALSE. Two cosmetic corrections only.
1. "line 363" -> the usage block is LINE 364; 363 is an `attachment`, usage null.
2. "540 assistant usage blocks" -> 550 at my probe time (the reviewed session is
   the CURRENT one and the file is still appending; not an error when measured).
3. Nuance worth carrying, not a refutation: the assistant DID put `/clear` on
   screen four times before 06:45, but only as a quotation of the standing
   instruction, never as a proposal at the threshold.

## Contradictions with the other live findings: NONE found
#23 (/clear-prep at 15:06:16.698Z, ~8h58m in) — start 06:08:40 -> 8h57m36s, agrees.
#25, #26, #27, #31 all corroborate. Flag only: #23 says "/clear-prep called" while
#31 says that Skill() call was REFUSED by the harness — "called" is not "ran".

## Scope note (not a refutation)
This is a RE-occurrence of an already-filed issue, not a novel gap:
  docs/research/reports/2026-08-21-session-review-synthesis.md:721
  "| **#354 / #218** | The 20%-context `/clear-prep` trigger is unimplementable as
   worded; the eager-context cap | OPEN — **needs Ray's ruling, see §6** |"
  ibid:825 "#354 found it unimplementable as worded (crossed 58 minutes in,
   before the round's first commit). Ray has restated it three times."
So the durable fact is stronger than the finding states: the same threshold was
crossed 58 min in on a PRIOR round and 15 min in on this one.

## GitHub repos touched

_None._
