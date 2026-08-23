# Session-review synthesis — 2026-08-23 validation run (session `096161cc-2a22-4b34-ad40-168e202bd37f`)

Synthesist: kb-synthesist (combines; does not research or verify). One lane ran
(`telemetry`, PARTIAL). Every number below is either **inherited** from a lane /
refuter report (labelled) or **re-derived once by this synthesis** (labelled, with
its command). Written 2026-08-23; the sink it describes is LIVE, so every count is
a property of a moment.

## 0. Tally — read this before the ranking

| category | count |
|---|---|
| CONFIRMED | **0** |
| REFUTED | **3** (all three findings the lane produced) |
| UNVERIFIED (cross-check did not return) | 0 |
| NOT TRIAGED (budget ran out) | 0 |
| lanes PARTIAL | 1 of 1 (`telemetry`) |
| lanes that did not return | 0 |

The refuter ran (3 refutations with probes and control arms), so this is not the
"zero refuted ⇒ verifier did not run" case. It is the opposite degenerate case:
**100% of what the lane reported was refuted**, and the three refutations were
written by separate refuter agents whose own numbers disagree with each other
(§4). The honest state of this run is: the lane's *method* is defective; the
refuters found the correct instruments; nobody has yet produced a CONFIRMED
figure about the session.

Graph-first: `mise run kb-query -- "telemetry sink request response
previous_message_id" --prose --idf` returned 20 ranked hits (Agent-SDK
cost-tracking docs, secrets-evidence notes) and nothing about this sink's schema.
Control arm: same command shape, non-empty ranked result — the query works; the
sink lives under gitignored `.agent/telemetry/` and was never ingested, so its
schema is genuinely absent from the corpus, not mis-spelled.

## 1. Ranked — by cost of leaving it unfixed

The top items are the **circles**: failure shapes this repo has already recorded
and that recurred here, in some cases inside the refutations themselves.
Bookkeeping is visibly below the line.

### 1. A key-NAME enumeration read as "the field does not exist" — twice in one run, and it reached the handoff  (CIRCLE: one-armed probe / spelling bound)

- Finding 2 (lane): "no request-id field exists" from `jq keys[]` on the request
  top level. REFUTED by refuter-2: `system[0].text` carries
  `x-anthropic-billing-header: … cc_prev_req=req_<id>`, the same id-space as
  `req_<id>.response.json` — a complete forward join from fields alone
  (thread = hash `.messages[0:10]`, order = `.messages|length` stepping +3,
  request[k]'s OWN response = `req_{cc_prev_req(request[k+1])}.response.json`),
  validated by tool_use block-id identity with a negative arm (backward response
  lands at `messages[37]`, forward at `[40]`).
- **Refuter-3 made the SAME error one report later**: its defect (1) — "the
  request JSON carries no request-id field at all … so the response filename
  cannot join to a request by filename OR by field, in either direction" — is the
  identical top-level-keys argument, and it is contradicted by refuter-2's probe.
  The narrow statement that survives is "no request carries its *own* id"; the
  broad "no filename join in either direction" is false. Refuter-3's points (2)
  and (3) do not depend on (1) and stand.
- The handoff (`.agent/kb/reports/agents/2026-08-23-validation/handoff.md`
  items 3 and 4) carries both claims side by side, contradicting each other.
- Cost of leaving it: the `telemetry` lane brief in
  `.claude/workflows/session-review.js` will re-derive "no forward join" on every
  future run, and the #411 per-call attribution instrument stays unbuildable
  from a lane that thinks the join is impossible. **Fix first:** the lane prompt
  (handoff item 77 already lists the content) — do not add a tool.
- Status carried: refuter-2's join is a refuter measurement, re-validated by two
  arms, NOT independently confirmed by a third agent. Treat as *strong lead,
  unconfirmed*.

### 2. Live-sink snapshot figures reported as properties of the session  (CIRCLE: inherited number / "a number invalidated by the commit that writes it")

- Every quantitative figure the lane produced drifted before the refuter read
  it: "the 5 largest" ranked 22–26 (inherited: sink 4926→4995 requests);
  "975 target requests" → 1113; "Class 2 ≤ 34" → 41 null-prev. The lane is ONE
  of the writers into the sink it measures (its own jq output echoes back into
  later requests — refuter-3 caught `grep -l 'req_011CeK88'` returning 5 files,
  all echoes of the lane's own shell).
- Re-derived by this synthesis at write time:
  `ls *.request.json | wc -l` = **5153**, `*.response.json` = **5148**,
  null-`previous_message_id` requests = **428** — i.e. the refuters' 5064/5107/
  5135 and 425 are already stale too.
- Cost: any figure copied from this run into a ticket, `docs/`, or MEMORY.md is
  wrong on arrival. **Fix first:** the lane must print the sink count beside
  every figure (the lane's own "Sink inventory" section does this for the
  header and then stops), and a probe over the sink must pin a file LIST at
  start (`ls > list; xargs jq … < list`), as refuter-3 did.

### 3. Selection-ordered data read as a time series  (CIRCLE: a probe that can only pass)

- Finding 1 "top 5 by size … no drop" — sorting by the measured quantity makes
  monotonicity certain; refuter-1 showed the same procedure returns "no drop" on
  a series that contains a −629,215 B drop (control arm), and the mtime-ordered
  pass over identical data returns 5 drops. Also a unit error (~4 KB per
  REQUEST, three messages per request ⇒ ~1.3–2.0 KB/msg; OLS over 250 points
  2033 B/msg, 307 KB constant).
- The *underlying* linear-per-request resend growth is real but supported only
  by the 250-point series the lane did not run; the remedy the lane pointed at
  (tiering/pruning the long architect thread — already tracked by this repo)
  stays valid, the number attached to it does not. Carry: **refuted as stated,
  mechanism real, magnitude unconfirmed**.
- Cost: moderate — a 2–3× overstated growth rate feeds a cost model (#411) that
  Ray already capped on re-derived numbers (cap 140→63 was exactly this lesson).

### 4. `previous_message_id == null` is NOT a thread start — and the three refuters disagree on what it IS

- Refuter-1: 13 null-prev fable-5 requests have nmsg 636/532/1/504/…/656 — a
  null prev at message 656 is not a new conversation. Refuter-3: threads
  fork/retry (4 response ids referenced by 2–3 requests). Both undermine the
  "≤34, one per thread" rationale AND the parent report's "34 threads"
  attribution.
- Refuter-2 said the 108 requests lacking `cc_prev_req` "are precisely the
  null-previous_message_id thread heads". **Re-derived by this synthesis**
  (`grep -L 'cc_prev_req=' *.request.json` = 108; all 108 have null prev; but
  null-prev total = 428): the implication holds one way only — every
  no-`cc_prev_req` request is null-prev, but **320 null-prev requests DO carry
  `cc_prev_req`**. So `cc_prev_req` and `previous_message_id` are two different
  links, and "null prev = head" is wrong by 320 out of 428. Handoff item 3
  repeats the "precisely" phrasing — the propagation this repo's
  *a-wrong-fact-I-authored-propagates-too* memory is about.
- Cost: every per-thread count (threads, Class 1, Class 2, "34") is built on this
  premise. Unsettled; see §4.

### 5. Class 2 is derivable, and the lane reported it as only boundable

- Refuter-3's identity `unreferenced = null_prev + dup_prevs − (requests −
  responses)` closed to the unit on two independent snapshots (422/422,
  423/423) with both directions armed (drop 10 ids → +10; inject a fake id →
  dangling=1). Two-sided bound [34, 41] for the target session; exact when
  requests == responses. Inherited, two-arm-verified by its author, not
  confirmed by a second agent.
- Cost: low-moderate — the lane's "not attempted given lane budget" was a
  budget answer to a question with a two-line arithmetic answer.

--- below this line: bookkeeping ---

### 6. Duplicate refutation file
`refute-telemetry.md` is byte-identical to `refute-telemetry-class2.md`
(handoff: `cmp` identical). `mise run kb-session-review-archive` copies every
`refute-*.md`; delete one or keep both knowingly.

### 7. Corpus loop not closed
No `kb-remember` since 03:26Z (handoff item 76). The instruments found here
(`cc_prev_req`, `cc_is_subagent`, `parent_session_id`, the Class 2 identity,
jq-never-grep for ids, mtime-not-size ordering) are exactly the durable lessons
`kb-remember` + `kb-reflect` exist for. Existing tasks; no new tool.

### 8. Two adjacent parent-report claims falsified in passing (refuter-2)
"no field distinguishes subagent traffic" — `cc_is_subagent=true` does;
"`metadata.user_id` carries only session_id" — it also carries
`parent_session_id`. Neither was a ranked finding; both were COVERAGE prose, and
both are now wrong in a tracked-adjacent report.

## 2. Refuted findings — whole, attributed, with the refutation

| # | lane | claim (short) | refuted by | status carried forward |
|---|---|---|---|---|
| F1 | telemetry | 5 largest requests show O(n²) resend, ~4 KB/msg, no drop | refuter-1: unit error (per-request vs per-message, 2.0–2.9×); "no drop" tautological under size-sort (control: size-sorted top-5 on a series with a −629 KB drop returns monotone); top-5 displaced to ranks 22–26; 12-message window cannot separate growth shapes | REFUTED as stated; linear-per-request growth real (OLS n=250), magnitude unconfirmed |
| F2 | telemetry | sink has only a backward join; own-effort↔own-response not derivable without a "forbidden filename join" | refuter-2: `cc_prev_req=req_<id>` in `system[0].text` (4999/5107 at its snapshot; control bogus `cc_next_req=` → 0, known header → 5107/5107); forward join demonstrated end-to-end with tool_use-id identity, negative arm on backward pairing | REFUTED; forward join = strong lead, one-refuter-verified |
| F3 | telemetry | Class 2 only boundable ≤34 without the filename join or temporal reconstruction | refuter-3: (1) the filename escape hatch "fictional" — **this part is itself contradicted by refuter-2**, see §1.1; (2) ≤34 rationale false (forks: 4 prev ids referenced 2–3×); (3) exact identity closes on two snapshots; 34 is a live-sink moment (41 later, 428 null-prev corpus-wide now) | REFUTED; identity = strong lead; refuter-3 (1) overstated |

A refuted finding is evidence about the probe: all three lane probes share one
defect class — reading a bound (top-level keys, top-5-by-size, a single
snapshot) as the whole.

## 3. Lane coverage — PARTIAL, and what it never reached

**`telemetry` — PARTIAL.** Reached (inherited from the lane's own statement):
session-id attribution over 4926 requests (975 target), per-request field
extraction, the backward `previous_message_id` join (941/941), null-prev count
(34), cache-miss sweep (7), xhigh-then-trivial sweep (12).

Opened, not finished: exact Class 2 (refuter-3 later showed it was two lines
of arithmetic away).

**Never reached — and still unexamined by anyone:**
- per-response `output_tokens_details` / `server_tool_use` / `inference_geo` /
  `iterations` / `speed` breakdown (captured, not analysed);
- the 22 session-review workflow agents vs the main thread vs this run's own
  lanes — the lane said "no field supports that split"; refuter-2 found
  `cc_is_subagent` + `parent_session_id`, but **nobody has run the split**;
- responses beyond the 4942 captured at join time (the delta was never re-joined;
  the sink is at 5148 responses as this is written);
- the forward join was demonstrated on ONE thread (`f62e7445`, 17 requests) and
  ONE request pairing — not run across the session.

An interrupted lane reads exactly like a finished one: the lane's 12 "xhigh
then trivial response" hits and 7 cache-miss hits are BACKWARD pairings and were
labelled as such by the lane; they are not the own-response figures #411 wants,
and no such figures exist yet.

## 4. What this review itself got wrong or could not settle

1. **The refuters contradict each other and this synthesis could only partly
   adjudicate.** Refuter-2 "108 without `cc_prev_req` = precisely the null-prev
   heads" vs refuter-3 "425 null-prev". Re-derived once here: 108 ⊂ 428 — the
   "precisely" is wrong by 320. What those 320 requests ARE (retries? resumed
   threads? subagent spawns carrying a parent's header?) this synthesis did not
   and must not determine; it is the open question under every thread count.
2. **Refuter-3's defect (1) was accepted into the handoff unchallenged** (item
   4 "a filename join was never possible in either direction") one line after
   item 3 says the opposite. This synthesis ranks refuter-2 as correct on the
   strength of its three arms and refuter-3's reliance on the key-name
   enumeration, but that is a judgment between two refuters, not a third
   measurement.
3. **Nothing here is CONFIRMED.** The forward join, the Class 2 identity, and
   the 2033 B/msg slope are each one refuter's two-arm result. A synthesis that
   ranked them as findings would be doing what the lane did — promoting a
   single-agent number. They are ranked here as *leads with the best evidence in
   the run*.
4. **Every count in this report is stale by construction** — re-derived at
   write time to 5153/5148/428/108, and the sink kept writing during the probe
   (this synthesis's own jq run is in it now).
5. **The lane's PARTIAL "never reached" list was written by the lane**, so it
   bounds only what the lane knew to look for; refuter-2's subagent split and
   the 320-null-prev-with-`cc_prev_req` class were outside its list entirely.
   Expect the next run's refuter to extend it again.
6. The graph was queried first and could not help (schema not ingested); this
   synthesis then read the telemetry dir directly. That is the right order, but
   the sink's schema should reach the corpus (`kb-remember` of the instruments,
   §1.7) so the next lane does not rediscover `cc_prev_req` by grep.

## 5. Existing tools to FIX first (no new automation)

1. `.claude/workflows/session-review.js` — the `telemetry` lane prompt: pin a
   file list at start; order by mtime, never by size; per-message = per-request
   ÷ messages-added; forward join via `cc_prev_req`; `cc_is_subagent` /
   `parent_session_id` for the subagent split; null-prev ≠ head (and ≠
   no-`cc_prev_req`); the Class 2 identity; jq never grep for ids; print the
   sink count beside every figure.
2. `mise run kb-remember` + `kb-reflect` — record the instruments above (the
   round's loop is open since 03:26Z).
3. `mise run kb-session-review-archive` — already archives; decide the
   duplicate `refute-telemetry.md` before it runs.
4. `handoff.md` items 3/4 — reconcile the contradiction before the handoff is
   read as authority (it already is, per MEMORY.md's "the sink HAS a forward
   join" line, which also carries the 108-heads phrasing).

## GitHub repos touched

_None._ — every input was a local lane/refuter report under
`.agent/kb/reports/agents/2026-08-23-validation/` plus one re-derivation over
`.agent/telemetry/`; no upstream source or docs site was consulted.
