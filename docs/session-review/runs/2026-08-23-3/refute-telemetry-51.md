# Refutation attempt — telemetry finding #51 (main-thread history resend)

CLAIM: main orchestrator thread (claude-opus-5, xhigh) resends full conversation
history every turn; top-5 in-scope requests 2.23-2.24MB with nmsgs 1205->1216;
337/1019 (33%) requests >1MB; 534.8MB of the session's 918.2MB in-scope request
bytes (58%).

## Probe 1 — replay the offered evidence (frozen index)
`jq -s '{n:length, over1mb:(map(select(.size>1000000))|length),
 over1mb_bytes:(...|add), total_bytes:(map(.size)|add)}' /tmp/req_inscope.jsonl`
-> {"n":1019,"over1mb":337,"over1mb_bytes":534775325,"total_bytes":918218048}
337/1019 = 33.07%; 534775325/918218048 = 58.24%. Reproduces exactly.
Top-5 by size: 2240857/1216, 2239296/1214, 2237036/1211, 2230891/1208,
2227800/1205 msgs, all model=claude-opus-5 effort=xhigh session f74823ff.

## Probe 2 — second route: stat + jq on the raw sink files (not the index)
Sink located at /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/telemetry/
(found by unbounded `find /Users/rmanaloto -name '99671fe6-...request.json'`).
stat -f %z + `jq '.messages|length'` agree with the index on all three checked.

## Probe 3 — full independent recount from disk (scratchpad/recount.py)
NOTE: first two runs returned 0 in-scope (ZeroDivisionError) because the probe
read the first 8192 bytes; `grep -bo session_id` shows metadata sits at offset
2240620 of 2240857 — the TAIL. Bounded-probe false zero, caught by the control.
Corrected (read last 64KB, take last match):
 total_request_files 3605 · inscope_n 1310 · inscope_bytes 1017453511
 over1mb 337 · over1mb_bytes 534775325 (identical to the frozen set)
=> the >1MB population is byte-identical by an independent route. The
DENOMINATOR has moved: the sink is LIVE and the session is still running, so
918.2MB was a snapshot; it is 1017.5MB now and 58% is now 52.6%.

## Probe 4 — is it really ONE thread, and is history really resent?
`jq -s 'map(select(.model=="claude-opus-5" and .size>1000000))|group_by(.syslen)
 |map({syslen,nmsgs:(map(.nmsgs)|sort)})'`
 syslen 15056 -> nmsgs 412..633, 666, 753..1216
 syslen 15107 -> nmsgs 634..751  (EXACTLY the gap in the other group)
=> one continuous thread whose system prompt grew 51 chars for one stretch, not
two threads. Whole thread across all sizes: 425 requests, 570,864,869 B,
nmsgs 5 -> 1216. The last 23 requests step 1151,1154,...,1214,1216 — monotone
+3 per turn, so "nmsgs climbing 1205->1216 across consecutive turns" is literal.

Direct test of "resends full conversation history": sha256 per message of
4c9c887c (1205 msgs) vs 99671fe6 (1216 msgs) -> first_diff_index 1204,
ndiff_in_common 1. i.e. 1204/1205 messages byte-identical, append-only.
Thinking blocks retained: 196 messages carry `thinking`, indices 11..1205,
under context_management {clear_thinking_20251015, keep:"all"}. Nothing is
elided. Capture is COMPACT json (`jq -c . | wc -c` = 2240858 vs disk 2240857),
so file size is not inflated relative to wire body.

## Probe 5 — attribution check (the one real imprecision)
Of the 337 >1MB requests: 288 are claude-opus-5/xhigh/ntools=17 = 477,308,965 B
(89.2%); 49 are claude-sonnet-5/xhigh/ntools=10/syslen=17186, nmsgs 201-345 =
57,466,360 B (10.7%) — a SUBAGENT thread, not the named main orchestrator thread.
So "534.8MB" is a whole-session figure; the main thread's own share is 477.3MB.

## Probe 6 — was "in-scope" a bound that hid traffic?
Window of in-scope mtimes 2026-08-23T04:43:24 .. 13:25:41. Requests from OTHER
session ids inside that same window: 52 files / 4,404,287 B total, max 1 per
session id. No meaningful traffic excluded by the session_id filter.

## Contradiction check against the other 54 findings
None contradicts. #52/#54 (cache-cold and low-output-token predecessors) and #55
(thread-start signal disagreement) are about the same sink and are consistent
with a single long append-only thread; #53 (no request->response link) does not
bear on request sizes.

## VERDICT: NOT REFUTED
Every load-bearing number reproduces by an independent route (raw sink + stat +
per-message hashing), and the mechanism claim is directly observed. Two
precision caveats, neither of which flips it:
 (a) 918.2MB / 58% is a LIVE snapshot — already 1,017,453,511 B / 52.6% by the
     time this lane re-measured; the 534,775,325 B numerator is unchanged.
 (b) 10.7% of that numerator belongs to a sonnet subagent thread, not the
     opus main thread the sentence's subject names.
