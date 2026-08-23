# Refutation lane — telemetry finding 3 (Class 2 unjoinable count)

CLAIM UNDER TEST: "Class 2 (a session's terminal response with no successor
request) cannot be counted exactly from the available fields; only an upper
bound of <=34 (one per conversation thread) is derivable without the forbidden
filename join or full concurrent-thread temporal reconstruction."

Source: `.agent/kb/reports/agents/2026-08-23-validation/telemetry.md`
section "Two unjoinable classes".

## Step 1 — schema of the sink (primary artifact, not the report's prose)

`.agent/telemetry/` at probe time: 4993 `*.request.json`, 4984 `*.response.json`.

Request file naming: `<uuid4>.request.json`.
Response file naming: `req_<REQUEST_ID>.response.json`.

Request top-level keys (`jq -r 'keys[]' a4d4b9d8-....request.json`):
```
betas context_management diagnostics max_tokens messages metadata model
output_config stream system thinking tools
```
Response scalar paths (`jq -r '[paths(scalars)|join(".")]|unique|.[]'`):
```
content.* id model role stop_reason type usage.*
```

FINDING A (already a defect in the judged report's REASONING, independent of
its verdict): the report names "the response filename `req_<id>.response.json`,
which the directive explicitly forbids joining on" as the one available
forward link. **That filename cannot join to a request at all.** The response
filename carries a `req_...` REQUEST id; the request JSON contains no request
id field (see key list above) and the request FILENAME is an unrelated uuid4.
Verified: response `req_011CeK88gZVfLXdaqbo8mTCt.response.json` has
`.id = msg_011CeK88hSKkzkTxBWS92vdd` -- filename id != content id, and no
request field anywhere holds `req_011CeK88gZVfLXdaqbo8mTCt`.
So the "forbidden join" escape hatch the claim is conditioned on is fictional.

## Step 2 — the sink is written by Claude Code, and REAPED by us

`python/src/kb_setup/telemetry.py:38-41` — the sink is
`OTEL_LOG_RAW_API_BODIES=file:.agent/telemetry/` (Claude Code native), reaped
oldest-first at SessionStart above a 2 GiB ceiling (`KEEP_BYTES`) and 14 days
(`KEEP_DAYS`). The directory contains ONLY `*.json` (`ls -a | grep -vc '\.json$'`
= 2, i.e. `.` and `..`) -- no index, no pairing sidecar. So the writer supplies
no request<->response mapping of any kind.

## Step 3 — FULL-CORPUS extraction (no bound, no sample)

```
cd .agent/telemetry
ls *.request.json  > /tmp/all_req.txt    # 5064
ls *.response.json > /tmp/all_resp.txt   # 5056
xargs jq -c '{f:input_filename,p:.diagnostics.previous_message_id,s:(.metadata.user_id|fromjson|.session_id)}' < /tmp/all_req.txt  > /tmp/all_req.jsonl   # 5064 lines, 0 errors
xargs jq -c '{rf:input_filename,id:.id,sr:.stop_reason,ot:.usage.output_tokens}' < /tmp/all_resp.txt > /tmp/all_resp.jsonl  # 5056 lines, 0 errors
```
jq (not grep) on purpose: the sink records this lane's OWN shell output back
into later requests, so a grep for `previous_message_id` or `req_...` matches
self-contamination inside `messages[]`. Verified: `grep -l 'req_011CeK88'
*.request.json` returns 5 files -- all of them echoes of MY earlier probe output.

GLOBAL reference graph (every session, every file, no bound):
```
requests_total            = 5064
prev_null                 =  425
prev_nonnull              = 4639
prev_nonnull_DISTINCT     = 4634      <- 5 DUPLICATE prevs exist globally
resp_total (all distinct) = 5056
referenced responses      = 4634
UNREFERENCED responses    =  422      <- global Class 2
prevs with no resp file   =    0      <- no reaper-induced dangling links
```

**The accounting identity closes EXACTLY:**
`unreferenced = null_prev - inflight + duplicate_prevs`
`422 = 425 - 8 + 5`, where `inflight = requests_total - resp_total = 5064-5056 = 8`.
This is a derivation of Class 2 from available fields alone -- no filename join,
no temporal reconstruction.

## Step 4 — the corpus falsifies "at most one terminal response per thread"

```
jq -r 'select(.p!=null)|"\(.p)\t\(.s)"' /tmp/all_req.jsonl | sort \
 | awk '{c[$1]++;s[$1]=s[$1]" "$2} END{for(k in c) if(c[k]>1) print c[k],k,s[k]}'
2 msg_011CeJ9RngvnCvMgwxedLAXx  5ec8da38... 5ec8da38...
2 msg_011CeJhJbwYoVKEta8XxFmqD  48d40647... 48d40647...
2 msg_011CeJiWSWDbbidgsNDvj7hU  48d40647... 48d40647...
3 msg_011CeHxfUXdqAN8UcsHAV584  33c070af... 33c070af... 33c070af...
```
Four response ids are referenced by 2-3 requests each (5 surplus references):
threads FORK / are retried. Each fork adds one extra tail, so the "one terminal
per thread" premise the <=34 bound rests on is false in this very corpus.
Response ids referenced by more than ONE session: **0** (checked) -- so no
cross-session chain sharing.

## Step 5 — the exact identity, re-armed on a SECOND independent snapshot

`unreferenced_responses = null_prev_requests + duplicate_prevs - (requests - responses)`

| snapshot | requests | responses | null_prev | dup | missing | identity predicts | MEASURED |
|---|---|---|---|---|---|---|---|
| 1 (00:2x) | 5064 | 5056 | 425 | 5 | 8 | **422** | **422** |
| 2 (00:34) | 5100 | 5093 | 425 | 5 | 7 | **423** | **423** |

Exact both times, on different inputs. Not a coincidental fit.
All from `.diagnostics.previous_message_id`, `.id`, `.metadata.user_id` and file
counts -- no filename join, no temporal reconstruction.

### Control arms (the set-difference probes discriminate)
```
baseline unreferenced                              = 422
after DROPPING 10 known-referenced ids from P      = 432   (expect 422+10) OK
dangling prevs baseline                            = 0
after INJECTING 1 fake msg id into P               = 1     (expect 1)      OK
```
Also: a mid-lane probe returned `nonnull=0` for a file that jq clearly filled
(4675 lines) -- a 0-byte `/tmp/r2_p.txt`. Re-run under a fresh filename gave
4675. A uniform zero was ONE broken probe, not a fact; the table above is the
re-run.

## Step 6 — the target session, re-measured (the report's 34 is already stale)

```
jq -r '.s' /tmp/all_req.jsonl | sort | uniq -c   # 8 sessions
1113 096161cc-...  (report snapshot said 975)
null_prev for 096161cc = 41   (report said 34)
non-null = 1072, distinct = 1072  -> dup = 0
```
The sink is LIVE and this validation lane is itself writing into it, so "34"
is a property of a moment, not of the session.

Applying the identity to the target session:
`Class2_target = 41 + 0 - missing_target`, `0 <= missing_target <= 7`
=> **Class2_target is in [34, 41]** -- a TWO-SIDED bound, and it collapses to an
exact equality `Class2_S = Class1_S + dup_S` at any moment where
`requests_total == responses_total` (globally observable from the same fields).

## VERDICT: REFUTED

1. The claim's stated escape hatch -- "the forbidden filename join" -- **does not
   exist**. 5056/5056 responses are named `req_<REQUEST_ID>`; 0/5064 requests are;
   no request field holds a request id. Nothing could be joined on it either way.
2. The stated rationale for the bound ("one per conversation thread") is
   **empirically false in this corpus** (4 forked prevs, 5 surplus references).
3. "only an upper bound ... is derivable" is **false**: an exact accounting
   identity over the same fields reproduces the global count to the unit on two
   independent snapshots, and yields a two-sided [34,41] interval per session,
   exact at quiescence.

## Contradiction with the other live findings

- Finding 2 rests on the SAME fictional "forbidden filename join". Not a
  contradiction with finding 3 -- a SHARED premise defect. Both should be
  re-stated as "the sink provides no forward link at all", which is stronger and
  true.
- Finding 1 (5 largest requests) is unaffected, though its "975 requests" scope
  figure has since moved to 1113 by the same live-sink drift.

## GitHub repos touched

_None -- local `.agent/telemetry/` and `python/src/kb_setup/telemetry.py` only._
