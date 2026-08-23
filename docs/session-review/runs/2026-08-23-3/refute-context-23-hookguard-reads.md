# Refutation lane — finding [context] #23

CLAIM (verbatim): "Phase 2 token burn driven by large graphify reads (58× hook-guard
search, 5× hook-guard read) despite identical assistant output volume across both phases"
EVIDENCE OFFERED: "63/64 hook calls are graphify operations. Both Phase 1 & 2 have 261
assistant messages of exactly 10 chars each. Phase 2 consumed 7.6× Phase 1 tokens with no
proportional message increase."

VERDICT: **REFUTED** on all three legs.

Artifact: `/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/5ec8da38-160b-4594-9560-c07a86b46f27.jsonl`
(1,555 records, `16:57:19.287Z` → `18:17:09.869Z`). It is the ONLY candidate: the two
prior sessions today end at `16:54:36Z` (33c070af) and `14:33:38Z` (672f23a4), so neither
can contain the claimed `17:18:24Z` phase boundary.

## Leg 1 — "hook-guard search/read" are NOT reads. They are the PreToolUse GUARD firing.

Every occurrence of the string in the transcript is the `command` field of a hook
attachment, verbatim (line 92, `2026-08-22T17:00:57.578Z`):

    "attachment": {"type": "hook_success", "hookName": "PreToolUse:Bash",
      "hookEvent": "PreToolUse",
      "stdout": "{\"hookSpecificOutput\":{...\"additionalContext\":\"MANDATORY:
                 graphify-out/graph.json exists. You MUST run `graphify query ...`\"}}",
      "exitCode": 0,
      "command": "mise exec -C \"${CLAUDE_PROJECT_DIR:-.}\" -- graphify hook-guard search",
      "durationMs": 132}

That is the graph-first nudge — a fixed ~260-byte string, 132 ms — not a graph read, not a
file read, and nothing "large". Measured totals over the whole session (my `an6.py`):

| hook command | firings | stdout bytes |
|---|---|---|
| `… graphify hook-guard search` | 75 | — |
| `… graphify hook-guard read` | 7 | — |
| all hooks, phase 1 (<17:18:24Z) | 10 | 4,940 |
| all hooks, phase 2 | 86 | 22,095 |

**Phase-2 hook stdout totals 22,095 bytes ≈ 5.5K tokens** against phase-2
`cache_creation_input_tokens` of **996,619** — 0.55%. It cannot "drive" anything.
(The lane's 58/5 are the same counters read earlier in the session; by 18:17 they are 75/7.)

## Leg 2 — "identical assistant output volume across both phases" is false by ~30×

Split at the claimed `17:18:24Z` boundary (`an2.py`, cross-checked against a raw
`grep -c '"type":"assistant"'` = 327, identical to the parsed 327):

| | phase 1 | phase 2 | ratio |
|---|---|---|---|
| assistant records | 22 | 305 | 13.9× |
| `output_tokens` | 7,396 | 220,305 | **29.8×** |
| tool_use calls | 14 | 194 | 13.9× |
| `cache_creation_input_tokens` | 273,119 | 996,619 | 3.6× |
| `cache_read_input_tokens` | 2,602,653 | 79,224,242 | 30.4× |

The claimed 7.6× token burn is *smaller* than the 13.9× turn growth and the 29.8× output
growth. There is no unexplained burn to attribute to graphify; phase 2 simply did 14×
more turns. "No proportional message increase" is the exact opposite of what is recorded.

**"261 assistant messages of exactly 10 chars each" in BOTH phases is arithmetically
impossible**: the whole file holds 327 assistant records (261+261 = 522), and the count of
assistant text blocks of length exactly 10 is **0 in phase 1 and 0 in phase 2**
(length histogram: phase 1 `{0:19, 56:1, 795:1, 659:1}`, phase 2 `{0:295, 56:2, 96:1, …}`).
At any plausible lane-run cutoff the session had 240 (18:05) / 247 (18:07) assistant
records — never 261 per phase. Note 261 IS a real number in this repo: it is the total
top-level tool-call count for a DIFFERENT session (6ae19ff6) in
`.agent/kb/reports/agents/context.md` Finding 4. An inherited number, not a measurement.

## Leg 3 — what actually carried the bytes was git/gh/grep, not graphify

Largest tool results in the session (`an7.py`), whole-session total 256,994 bytes:

    23741 ph2 Bash: git show 98b116fd --stat | head -30; … git show 98b116fd -- .mcp.json
    14522 ph1 Bash: cat .agent/plans/session-2026-08-22-b.md
     9862 ph2 Bash: grep -rn "\.mcp\.json" --include=…
     8611 ph2 Bash: gh release view v2.1.239 …
     7035 ph2 Bash: git add python/src/kb_setup/context_usage.py …

Commands/paths mentioning `graphify` at all account for 53,981 of 256,994 bytes (21.0%),
i.e. ~13.5K tokens — 1.4% of phase-2 `cache_creation`. Meanwhile ALL tool results in the
session (256,994 bytes ≈ 64K tokens) are ~6% of phase-2 new input tokens. The burn is
cumulative turn-history replay (79.2M cache reads over 305 turns), which is exactly what
the prior round's own context lane concluded for session 6ae19ff6
(`.agent/kb/reports/agents/context.md`, Finding 4: "the raw-read volume was not the driver
of the blowout … dominated by cumulative turn history").

Also: `Grep` was called **0** times this session; there were no "searches" by the model to
be large. The 148 phase-2 Bash calls produced 206,918 bytes total — 1.4 KB average.

## Control arms

1. Token spelling: raw `grep -c` on the transcript → `hook_guard` 9, `hook-guard` 82
   (75 search + 7 read), `hookguard` 0, control `graphify` 426. The spelling that matters
   is the hyphenated one and I counted it directly, so the 0 for `hook_guard`-in-tool-input
   is not a spelling bound.
2. Wrong artifact: the same probes on 33c070af → 68 search / 2 read, on 672f23a4 →
   108 search / 2 read, i.e. the probe returns DIFFERENT numbers per transcript, and
   neither of those files spans 17:18:24Z.
3. Two routes for the assistant count: JSON parse = 327, raw `grep -c '"type":"assistant"'`
   = 327. (The spaced variant `'"type": "assistant"'` = 0, which is why the unspaced form
   is the right control.)
4. The phase-split probe CAN show equality — it just doesn't here: it reported equal 0
   counts for the 10-char bucket in both phases while reporting 22 vs 305 records, so it
   discriminates in both directions.

## Cross-finding contradiction

Finding **#22** ("compaction event at 17:18:24Z") is the premise this finding's phase split
rests on, and the sibling refuter of #25 measured `isCompactSummary` = 0 in this same
transcript plus a `total_tokens` counter RESET at `17:15:02.857Z`
(14,858,403 → 15,000,000). My own record-type census agrees: the transcript contains no
`summary`-type record (types: mode/permission-mode/system/custom-title/agent-name/
queue-operation/attachment/user/file-history-snapshot/last-prompt/atis-latch/assistant/
file-history-delta/bridge-session). **The phase boundary is a non-event**, so "Phase 2"
is just "the rest of the session".

## GitHub repos touched

_None._
