# Telemetry lane — 2026-08-23 validation

Scope: session_id `096161cc-2a22-4b34-ad40-168e202bd37f` (the session under
review), via `.agent/telemetry/*.request.json` `.metadata.user_id` (a JSON
string containing `session_id`).

## Sink inventory (live — states the count actually seen at each step)

- At lane start: `ls *.request.json | wc -l` = **4922**.
- During the `jq` extraction pass (`jq -c '{f: input_filename, uid: .metadata.user_id}' *.request.json`): **4926** request objects were captured (sink grew mid-pass — this is expected, the sink is written by the live session, including this validation lane itself).
- At time of writing this line: `ls *.request.json | wc -l` = **4969**, `ls *.response.json | wc -l` = **4964**. All figures below are computed against the **4926-request snapshot** unless stated otherwise.
- Total `.agent/telemetry/` size: **2.5G** (`du -sh .`).

## Control arm (probes-need-a-control-arm)

Before trusting the session-id join, ran it against a KNOWN-absent id first
(control: `grep -c '096161cc...' <arbitrary single request file>` → 0 — the
probe can say "not present"), then against the full corpus:

```
jq -r '.session' /tmp/sess_map.jsonl | grep -c '096161cc-2a22-4b34-ad40-168e202bd37f'
# => 975
```

975 > 0, so the probe discriminates. Distribution across ALL session ids seen
in the 4926-request snapshot (top 8, `sort | uniq -c | sort -rn`):

```
 975 096161cc-2a22-4b34-ad40-168e202bd37f   <- session under review
 940 5ec8da38-160b-4594-9560-c07a86b46f27
 934 8282c59c-47d3-4a50-a397-9d35246bf447
 617 48d40647-9738-4086-ab85-4eb80bd870bc
 595 33c070af-6dee-476f-8d5e-226912f416b7
 425 4fb0210a-c2ec-47ff-a8e0-9a1b58edada5
 407 672f23a4-61dc-4e30-af59-21a860699ed6
  33 4f9e2dd5-e8e8-4de8-a53b-c7efdff2e29d
```

Sum of the non-target ids = **3951**; 975 + 3951 = 4926, accounts for every
request in the snapshot. The other 6 ids are **other, unrelated concurrent
sessions on this machine** — not subagents of the reviewed session (see
attribution finding below); this is not itself a defect, just scope.

## Attribution finding — subagents DO share the parent session_id

The directive asked whether the 22 `session-review` workflow agents' requests
matched the parent session id or carried their own. Evidence for "same id":

1. Within the 975 target-session requests, `.model` mixes **claude-opus-5**
   (455), **claude-sonnet-5** (291), and **claude-fable-5** (229) — three
   different models under ONE session_id, consistent with a multi-agent
   fan-out sharing one id rather than one model doing everything serially.
2. `.diagnostics.previous_message_id == null` (a fresh conversation thread)
   occurs **34 times** within the 975 target requests — far more than the 1
   expected for a single linear conversation, consistent with ~22 parallel
   subagent threads + the main thread + a handful of shorter side-lanes all
   sharing the parent session_id.
3. **Direct, live confirmation**: this very validation lane (itself a
   subagent spawned inside session `096161cc-...`, confirmed by its own
   scratchpad path containing that same UUID) has its own most-recent
   requests already landing in the sink under `session_id=096161cc-...`
   (checked via `ls -t *.request.json | head -3`, each resolved via
   `jq -r '.metadata.user_id | fromjson | .session_id'`, all three =
   `096161cc-2a22-4b34-ad40-168e202bd37f`).

**Conclusion: subagents inherit the parent session_id; they do not get their
own.** This means a per-session usage total (below) legitimately captures
subagent cost too — good for cost accounting, but means the 975-request /
34-thread count cannot itself distinguish "the 22 review agents" from "the
main thread" or from this validation run's own lanes without a further
signal (none of the extracted fields separates it further; unverified beyond
this).

## Per-request field mix (target session, 975 requests)

```
effort:   570 high, 400 xhigh, 5 medium
thinking: 975 adaptive (100%)
model:    455 opus-5, 291 sonnet-5, 229 fable-5
```

## Top-5 largest requests (O(n^2) context-resend check)

By raw file byte size (`stat -f %z`), all five are `claude-fable-5` /
`effort=xhigh`, growing message count in lockstep with size — the resend
pattern the directive named:

| file | bytes | messages | effort |
|---|---|---|---|
| 0aba7a05… | 1,572,273 | 605 | xhigh |
| 5f968055… | 1,568,094 | 602 | xhigh |
| 760cc6ae… | 1,561,929 | 599 | xhigh |
| 381906a8… | 1,557,931 | 596 | xhigh |
| b3b945ab… | 1,553,795 | 593 | xhigh |

~4,000 bytes/message added per turn, ~1.55–1.57 MB at the top — smaller than
the ~1.17 MB/request figure cited elsewhere in this repo's memory, but same
shape (linear growth with turn count, all in the fable-5 architect thread).
Total bytes across all 975 target-session request files: **538,480,378
(≈513.5 MB)**.

## Token usage (session total, via the sanctioned prev-chain join)

**Join method** (exactly as specified): built a `{response.id: response}` map
from all 4942 responses seen at join time (`jq -s 'map({(.id):.})|add'`), then
joined each target request's `diagnostics.previous_message_id` against it.
**All 941 non-null `previous_message_id` values joined successfully — 0
failures.** No duplicate `prev` values (verified: `sort | uniq -d` on the 941
prev ids = 0 lines), so the join is a clean 1:1 chain with no double-counting.

**Two unjoinable classes, counted separately, per the directive:**

- **Class 1 — `previous_message_id == null`** (first request of a
  conversation thread): **34** of 975 target requests.
- **Class 2 — the last response of a session** (no successor request):
  **could not be counted precisely from the available fields.** The sink
  gives only a *backward* link (request → preceding response); there is no
  forward link from a response to the request that produced it, other than
  the response filename `req_<id>.response.json`, which the directive
  explicitly forbids joining on. A response becomes "known to belong to this
  session" only by being referenced as someone's `prev` — which by
  construction excludes exactly the terminal response of each thread. Upper
  bound: **≤ 34** (at most one terminal response per conversation thread,
  possibly fewer if a thread is mid-stream and its last response hasn't been
  produced yet). Reported as **unverified beyond this bound** rather than
  guessed.

**Sum over the 941 joined responses** (each response's `usage` counted once,
since no duplicates):

| field | sum |
|---|---|
| input_tokens | 46,790 |
| output_tokens | 840,206 |
| cache_creation_input_tokens | 4,478,225 |
| cache_read_input_tokens | 181,846,049 |
| **all four combined** | **187,211,270** |

`stop_reason` on the 941 joined responses: 924 `tool_use`, 17 `end_turn`.

**Caveat on what this pairing actually measures**, stated plainly because it
matters for anyone reusing this join: `request.prev → response` links a
request to the **response immediately BEFORE it**, i.e. the previous turn's
output — not "this request's own response." There is no available field that
identifies which request produced a given response (that would require
either the forbidden filename join, or reconstructing full per-thread
temporal order across ~34 interleaved concurrent threads, which was judged
out of scope for this pass). This does **not** affect the token-usage total
above (every response in the session — except each thread's one terminal
response — is counted exactly once via this backward link, regardless of
which request "owns" it). It DOES affect any finding that tries to correlate
a **request's own** effort setting with **its own** response's shape — see
next section.

## xhigh/max effort calls followed by a trivial response

Using the same backward-link caveat (this reports "requests immediately
following a trivial reply", not "xhigh requests whose own response was
trivial" — the latter is not derivable without the forbidden join):

**12 of 975** target-session requests at `effort=xhigh` immediately follow a
response with `stop_reason=end_turn` and `output_tokens<200` (range 22–190
tokens). Example: `0c12ab6d…` (next request effort=xhigh, preceding response
output_tokens=40, stop_reason=end_turn). Full list of 12 file ids is in the
raw jq output; not reproduced here per the "no message content, report only
extracted fields" rule — these are just filenames + numeric fields, so listing them is fine, omitted here for brevity only.

## Large requests vs. cache_read_input_tokens

The 5 largest target requests (table above) all have healthy preceding-response
`cache_read_input_tokens` in the **525,292–543,207** range — cache is being
used, not a cold-cache-every-turn pattern.

Across ALL 941 joined pairs, only **7** have `cache_read_input_tokens == 0`,
and every one of them has a low message count (`nmsg` 4–5) — consistent with
a fresh subagent thread's first couple of turns (expected cold cache at
conversation start), not a repeated cache-miss pathology on a long-running
thread.

## GitHub repos touched

_None — this lane read only local `.agent/telemetry/` and `.claude/projects/`
transcript metadata, no external repo content._

## COVERAGE

- **Reached and analysed**: full session-id attribution + control arm (all
  4926 requests in the snapshot); full per-request field extraction for all
  975 target-session requests (model/effort/thinking/nmsg/syslen/ntools/byte
  size); the top-5-by-size context-resend check; the prev-chain join for all
  941 non-null-prev target requests (0 join failures, 0 duplicate prev
  values) and its token-usage sums; the null-prev count (34); the
  cache_read_input_tokens==0 sweep across all 941 joined pairs; the
  xhigh/max-then-trivial-response sweep across all 941 joined pairs; the
  subagent-session-id attribution question, resolved with live self-evidence.
- **Opened but did not finish**: exact count of Class 2 (terminal responses
  with no successor request) — bounded at ≤34, not resolved precisely,
  because the sink provides no non-filename link from a response to its
  producing request; a true request→own-response pairing (needed to correctly
  attribute effort to output shape, rather than the backward "preceding
  response" pairing used above) was judged unreachable within this lane's
  budget without either the forbidden filename join or full per-thread
  temporal reconstruction across ~34 concurrent threads.
- **Never reached**: per-response `output_tokens_details` / `server_tool_use`
  / `inference_geo` / `iterations` / `speed` breakdown beyond the four summed
  token counts (available in the raw `resp.usage` objects captured to
  `/tmp/target_full_join.json`, not further analysed here); no attempt to
  separately quantify which of the 34 threads correspond specifically to the
  22 `session-review` workflow agents vs. the main thread vs. this
  validation run's own lanes (no field in the sink distinguishes them beyond
  the shared session_id, noted above as a limit of the schema, not of this
  pass); did not examine `.response.json` files beyond the 4942 captured in
  the id→record map at join time (sink grew to 4964 by report time — the
  delta is newer traffic from this same still-running session and was not
  re-joined).
