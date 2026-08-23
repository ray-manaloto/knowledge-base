# Refutation lane — telemetry finding #2 (backward-link-only)

CLAIM: "The sink's request->response join (via previous_message_id) is a BACKWARD
link only ... correlating a request's OWN effort with its OWN response's output
shape is not derivable from the specified fields without the explicitly-forbidden
filename join."
EVIDENCE OFFERED: "Request JSON keys observed: betas, context_management,
diagnostics, max_tokens, messages, metadata, model, output_config, stream, system,
thinking, tools — no request-id field exists to match against a response's
req_<id>.response.json filename or its .id field."

## STATUS: evidence FALSIFIED (in progress on the conclusion)

### P0 — the offered evidence is a BOUNDED probe (top-level keys only)

The key list is top-level only. `system[0].text` contains an
`x-anthropic-billing-header` line carrying **`cc_prev_req=req_<id>`** — a
request-id token in exactly the `req_…` id-space of the response FILENAMES.

Probe:
```
cd .agent/telemetry
f=$(ls -t *.request.json | sed -n '3p')
jq -r '.system[0].text' "$f" | tr '\n' '\036' | grep -o '[^\036]*cc_prev_req[^\036]*'
# => x-anthropic-billing-header: cc_version=2.1.241.033; cc_entrypoint=cli;
#    cch=00000; cc_is_subagent=true; cc_prev_req=req_011CeK8NogG4SrjC27QzJczN;
```

Control arm (the probe can return the other answer): a request whose
`diagnostics.previous_message_id` is null carries the SAME header line **without**
`cc_prev_req`:
```
NULLPREV=10e61958-adcf-4bf9-9ece-bdf66570df94.request.json
x-anthropic-billing-header: cc_version=2.1.241.033; cc_entrypoint=cli; cch=00000; cc_is_subagent=true;
```

### The req-id names a real response file, 30/30

For the 30 most recent requests: `req_${cc_prev_req}.response.json` EXISTS and its
`.id` equals that request's `diagnostics.previous_message_id` — 30/30
`SAME_AS_PREV_MSG`, 0 MISSING. So the sink DOES expose a request-id ↔
response-filename correspondence in a field. The finding's sentence "no request-id
field exists to match against a response's `req_<id>.response.json` filename" is
false as stated.

### Side effects on OTHER claims in the same report
- `cc_is_subagent=true` is a field in the sink that distinguishes subagent traffic.
  The telemetry report's COVERAGE section says "no field in the sink distinguishes
  them beyond the shared session_id" — that is falsified by the same probe.
- `metadata.user_id` also carries `parent_session_id` alongside `session_id`.

### Still to settle: does cc_prev_req yield a genuine FORWARD link?

## VERDICT: REFUTED — the forward join IS derivable from the specified fields

### Corpus-wide prevalence (with control arms)
```
grep -l 'cc_prev_req='            *.request.json | wc -l   => 4999
grep -l 'cc_next_req='            *.request.json | wc -l   =>    0   <- CONTROL (bogus token, same shape)
grep -l 'x-anthropic-billing-header' *.request.json | wc -l=> 5107   <- CONTROL (known-present)
ls *.request.json | wc -l                                  => 5107
```
4999 of 5107 carry it; the 108 without it are the null-`previous_message_id`
thread heads (verified on `10e61958-…`, which has the header but no `cc_prev_req`).
The probe discriminates in both directions.

### The construction (fields only: `messages`, `system`, `output_config.effort`, `model`)
1. **Thread membership** — hash `.messages[0:10]`. Three concurrently-live
   threads at nmsg=40 in the 60 newest requests separated cleanly:
   `f62e7445…`, `b075bbbc…`, `78456182…`; each n=43 successor matched exactly one.
2. **Order within a thread** — `.messages | length`, which steps +3 per turn
   (22,25,28,…,70 for thread `f62e7445`, 17 requests, no gaps).
3. **Forward edge** — request[k]'s OWN response file =
   `req_{cc_prev_req(request[k+1])}.response.json`.

### End-to-end demonstration (thread f62e7445, own-effort ↔ own-response)
```
REQUEST_FILE  nmsg  eff   OWN_RESP   out_tok/stop/model
e6efe82f      22    high  011CeK8G   454/tool_use/claude-opus-5
dda91088      25    high  011CeK8H   335/tool_use/claude-opus-5
214d103b      28    high  011CeK8L   2109/tool_use/claude-opus-5
d6744c64      31    high  011CeK8N   306/tool_use/claude-opus-5
afca46e9      34    high  011CeK8P   517/tool_use/claude-opus-5
7d50bc40      37    high  011CeK8R   329/tool_use/claude-opus-5
57a69c80      40    high  011CeK8R   694/tool_use/claude-opus-5
53879dee      43    high  011CeK8S   3495/tool_use/claude-opus-5
89ff4e63      46    high  011CeK8W   308/tool_use/claude-opus-5
```

### Independent validation of the pairing — `tool_use` block id identity
F = `57a69c80…` (nmsg 40); forward candidate own-response =
`req_011CeK8RUq2B6rd4nPZHfpWz.response.json`; successor G = `53879dee…` (nmsg 43).

```
forward resp blocks : [{"t":"thinking"},{"t":"tool_use","id":"toolu_01GQTTRpfCBCfMxShZ5tDKe2","n":"Bash"}]
G.messages[40]      : [{"t":"thinking"},{"t":"tool_use","id":"toolu_01GQTTRpfCBCfMxShZ5tDKe2","n":"Bash"}]   <- IDENTICAL
```
**Negative control (the probe can say "wrong pairing"):** the BACKWARD response
`req_011CeK8RBdB4cjUWaN56SMjM` carries `toolu_01FRqBTDpHjr1faUAXiYmgni`, which
lands at `G.messages[37]`, NOT `[40]`. So the tool_use-id check distinguishes the
correct forward pairing from the backward one.

(Raw SHA of `.content` differs between response and replayed message — the request
strips signature/cache_control envelope fields — which is why the check is on
block type + `tool_use.id`, not on the raw blob.)

### Why the original probe could only have produced its answer
It enumerated **top-level key NAMES only**. Two of the keys it itself lists —
`system` and `messages` — are where the join keys live (`cc_prev_req=req_<id>` in
`system[0].text`; `tool_use.id` / `tool_result.tool_use_id` in `messages`). A
key-name enumeration cannot see a value, so it could not have returned anything
but "no request-id field". Classic bounded probe.

### Contradiction with the OTHER live findings this round
- **Finding 3 (Class 2 ≤34, "cannot be counted exactly")** rests on this same
  premise ("no forward link"). With threads reconstructible from
  `.messages[0:10]` + `.messages|length`, each thread's LAST request is
  identifiable, and Class 2 is countable rather than only boundable. Finding 3 is
  undermined by the same refutation, not independent of it.
- **Finding 1 (O(n^2) resend)** is consistent with, not contradicted by, this
  lane: the +3-messages-per-turn / monotone-size structure is exactly what makes
  the prefix-hash thread reconstruction work.

### Two further claims in the parent telemetry report falsified by the same probe
- "no field in the sink distinguishes [subagents] beyond the shared session_id" —
  the same header carries **`cc_is_subagent=true`**.
- `metadata.user_id` carries **`parent_session_id`** alongside `session_id`.

## GitHub repos touched

_None._
