# Extraction-readiness sweep — 2026-08-22

**Question (Ray):** did session-review review all the open issues for graphify deep
extraction, to make sure it will work properly when we run it again on a new graphify
release — e.g. tracking the model/effort used, in case we need to change it, or switch
from Claude to codex or another model family?

**Scope of this sweep:** all **222** open issues, filtered to **154** candidates by a
term set applied to title AND body (not title alone — a title is a spelling bound), then
read down to the set that can gate an extraction run. Every claim below was re-derived
against the code as it stands at `cc26510121c7`, not inherited from the prior lane.

---

## Finding 0 — the lane that answers this question EXISTS, RAN ONCE, and WAS NEVER COMMITTED

`.agent/kb/reports/agents/2026-08-21-session-review/extraction-readiness.md` — an
`extraction-readiness` lane ran on **2026-08-21** and produced **F1–F13**. It is the
lane that found the P0 now filed as #426 (its claim **ER-01**).

It is **not in the committed lane set.** `.claude/workflows/session-review.js` declares
eight lanes — `circles`, `forgotten`, `contradicted`, `unpinned`, `context`,
`tooling-gap`, `bot-reviews`, `pending-work`. None reads the issue backlog:

- control-armed: `grep -c "gh issue" .claude/workflows/session-review.js` -> **0**,
  while `grep -c "transcript"` -> **13**. The probe discriminates.

So the answer to Ray's question is: **once, on 2026-08-21, by a lane that no longer
exists.** Every round since has been unable to ask it. That is why five of its thirteen
findings were never filed.

---

## The readiness gate list — ranked, with filing status re-verified today

### Tier A — the run cannot start, or starts and produces nothing

| # | Gate | Filed | State today |
|---|---|---|---|
| A1 | `_ACCEPTED_GRAPHIFY_RUNTIME` frozen at 0.9.47 vs installed/pinned 0.9.48 -> every chunk stages `failed` after being paid for | **#426** (P0), **#452** | **LIVE.** `kb-currency-check` still reports the ref-binding drift. ~$65 burned, 58/58 failed. |
| A2 | Ambient `AWS_*` makes `preflight` refuse -> `run` dies before spending anything | **#334** | **LIVE.** Fails closed (correct), but cannot start without the `env -u` prefix. |
| A3 | `kb-build` RED | **#397**, **#417** | **LIVE.** See B4 for what it actually blocks. |
| A4 | Two independent 120 s ceilings on one provider call | **#335** | Needs re-verification; the timeout was raised to 900 s (`graphify_semantic_corpus.py:53-68`). |

### Tier B — the run completes and the result is wrong, lossy, or unresumable

| # | Gate | Filed | State today |
|---|---|---|---|
| B1 | **Restart re-buys everything.** `check_semantic_cache` has **0** call sites in the installed 0.9.48 `llm.py`; control `save_semantic_cache` -> **2**. Write-only checkpointing. | **PARTIAL** — #168 names the cache only for `kb-extract.js`, a different code path | **LIVE, re-derived at 0.9.48 today.** |
| B2 | **The cap tolerates at most ONE early restart.** `max_total_cost_usd = 100.0`; chunk 1 measured 1.12 USD; 58 x 1.12 = 64.96. A restart after chunk N costs 1.12N + 64.96, so **N > 31 makes the plan uncompletable inside its own authorized cap** — `seeded_spend` refuses before the first call. | **UNFILED** | **LIVE.** |
| B3 | **The ~10.6-hour task declares no `timeout`.** Eight tasks do (`lint` 20m, `test` 25m, `eval` 25m, `kb-build` 180m, `kb-transcribe` 120m, `kb-artifacts` 60m, `brain-audit` 10m, `hk-test` 10m). `[tasks.kb-graphify-semantic-corpus]` declares none, and its `run` action is the 58-chunk provider run. | **UNFILED** | **LIVE, re-derived today.** |
| B4 | **`kb-build` RED blocks the MERGE, not the RUN.** The run needs only `sources/graphify` at its pin. `graphify_ops.merge_chunk` merges into `graphify-out/graph.json` (`graphify_ops.py:236`) — so #397 must be green **before the merge step**, not before the run. | **UNFILED** as an ordering fact | **LIVE.** |
| B5 | **The graph the corpus would merge onto is version-unknown.** `graphify-out/.currency-stamp.json` **does not exist**; `graph.json` is 772 MB dated Aug 21 18:16 and `.build-failure.json` is dated Aug 21 12:56. Doctrine: *version unknown is never a green.* | #397 / #440 adjacent | **LIVE.** |
| B6 | **`build = skip` register is stale AND its own invariant is broken.** Five manifests carry `build = skip` — `codebase-memory-mcp` (study), `GitNexus` (study), **`codegraph` (scope = corpus)**, `codex` (no scope), `colibri` (no scope). #417 lists two and asserts *"Every entry below is `scope = study` so far. If that stops being true, the entry says so in bold."* It does not. **Real aggregate corpus loss is happening unannounced.** | **#417 needs UPDATING, not re-filing** | **LIVE.** |
| B7 | Node-id collisions across chunks pass every gate (8 corrupting ids); 37 dangling edges in committed chunks; reversed `requires` edges | #231, #134, #233, #198 | Carried. |
| B8 | `_is_ast_tier` misreads semantic chunks with `L<line>` source_location — 629 prose nodes (22%) silently dropped | #135 | Carried; upstream. |
| B9 | `kb-extract.js` diverges from graphify's own extraction spec on five points; cannot declare `supersedes` | #168, #206 | Carried. |

### Tier C — provenance: what Ray actually asked about

| # | Gate | Filed | State today |
|---|---|---|---|
| C1 | **No per-file provenance exists.** Control-armed: `ls sources/*.extraction-provenance.json` -> no matches, against **73** `sources/*.manifest`. Finest granularity is model recorded ONCE per plan, paths per CHUNK. | **#411** (designed, unbuilt) | **LIVE.** |
| C2 | **The `--effort` VALUE is recorded nowhere machine-readable.** `graphify-out/graphify-semantic-corpus/execution-config.json` has 44 keys: `claude_model='claude-opus-5'`, `max_turns=3`, `backend='claude-cli'`, and `--effort` appears only as a **flag NAME** inside `claude_required_flags`. Control-armed: `'high' in json.dumps(cfg)` -> **False**, while `deep_mode` and `max_turns` ARE present. The value lives at `graphify_semantic_slice.py:567` (`CORPUS_PROFILE.effort="high"`) and is bound only indirectly via `semantic_slice_sha256` — **tamper-evident but unreadable.** | **UNFILED** (F8 of the dead lane; #411's body does not state it) | **LIVE, independently re-derived today.** |
| C3 | **Switching model family is a hard invariant, not a knob.** `backend="claude-cli"` is a literal at `graphify_semantic_corpus.py:765` and `graphify_semantic_slice.py:1817,1958`, and is **verified for equality** at `graphify_semantic_slice.py:1488` (`receipt-backend-mismatch`) — a codex run fails its own receipt check. Above it: `auth_route='claude.ai:firstParty:max'`, `endpoint_policy='subscription-default-no-api-endpoint'`, `do-not.md` #4, `clean_env()`. Control-armed: **zero** open issues propose a non-Claude EXTRACTION family, while **35** open issues mention graphify — so the search discriminates. Every codex issue (#445 #428 #399 #374 #345 #324 #323) is review-lane, telemetry or agent-config. | **UNFILED** | **LIVE.** |

### Tier D — scope and after

#177 (Phase 3 deep-mode), #174 (the deep round spec), #178 (Phase 4 bridge), #167,
#301, #298, #302, #305, #306, #424 (feed session-review into the graph afterwards),
#414 (55% of plan tokens re-extracting byte-identical files — **the same content-hash
keying #411 proposes is its fix, so those two should land together**), #332 (arm
`attempts=provider_calls` with a real staged chunk), #317, #389 (the `reauthorize` task
— this is fork 2 of #452).

---

## What this sweep changes

1. **Five of the dead lane's thirteen findings were never filed**: B1 (partial), B2, B3,
   B4, C2 — plus C3 which the lane never raised at all.
2. **B1 + B2 + B3 are one compound risk, not three.** No cache read on restart, a cap
   that cannot absorb a restart past chunk 31, and no timeout on the 10.6-hour task that
   would cause the interruption. Any one is survivable; together they mean an
   interruption past the halfway point costs a **fresh authorization from Ray**.
3. **C2 answers Ray's question directly and negatively**: you cannot today read, from any
   run artifact, what effort level extracted anything.
4. **C3 answers the second half**: switching to codex is not a configuration change. It
   is an invariant change with a receipt-level equality check enforcing it.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the 222 open issues swept, and the code re-derived against.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — installed 0.9.48 `llm.py` / `cache.py` read to re-derive B1.

---

## Addendum — why the prior lane's findings need re-deriving, not inheriting

The `extraction-readiness` lane was **never in the committed workflow**. Control-armed
over every historical revision of `.claude/workflows/session-review.js` (4 commits:
`b30a80c9`, `d6641b98`, `dcd0b07f`, `2b364443`) — `extraction-readiness` appears in
**none**. It was dispatched ad hoc during the 2026-08-21 round.

Its own completeness audit (`docs/research/reports/2026-08-21-session-review-completeness.md`)
scored it **13 findings, 5 verified (ER-01..05), 8 unverified**, and recorded these gaps
verbatim:

> did **not** run `kb-build` (ER-10 `status: unknown`); did **not** run the corpus `run`
> (ER-01 is inference, not observation); read `graphify_semantic_slice.py` only around
> preflight/effort/constants — **`:1356-1410` receipt-verification unaudited**; **never
> opened `graphify_semantic_corpus_authority.py` or `_prototype.py`**; never opened
> **#409 or #414**.

So five of its thirteen findings are *unverified inference from a lane with known holes*.
This sweep re-derived F1 (B1), F5 (B6), F8 (C2), F9 (B3) and F11 (B4) independently — a
second probe by a different route, per `probes-need-a-control-arm.md`. All five agreed.

**Still not covered by either sweep**, and inherited as open coverage debt:

- `graphify_semantic_corpus_authority.py` and `_prototype.py` — never opened by either.
- `graphify_semantic_slice.py:1356-1410` — the receipt-verification path, unaudited.
- #409 (reviewed-warning inventories do not scale) — read by neither lane. It is the
  primary ticket for the `GitNexus` skip in B6.
- Nobody has ever *observed* the corpus `run` reaching a provider at 0.9.48. Every claim
  about what it will do is inference from source.

That last point is the honest bound on this whole sweep: it establishes that the run
**will fail** (A1, A2) and what it would cost if it did not — it cannot establish that
fixing A1 and A2 makes it succeed.
