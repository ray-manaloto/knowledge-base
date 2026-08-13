---
type: "query"
date: "2026-08-11T13:45:26.316036+00:00"
question: "Why was Colibri rejected for Graphify deep extraction, and should that decision change after primary-source research?"
contributor: "graphify"
outcome: "corrected"
correction: "# Colibri compatibility with Graphify 0.9.39 deep extraction\n\n**Date:** 2026-08-11\n\n**Status:** complete; source-verified, no model weights downloaded\n\n**Scope:** `JustVugg/colibri` as a local OpenAI-compatible backend for\n`Graphify-Labs/graphify` 0.9.39 deep semantic extraction on the target M2 Max,\n96 GB unified-memory Mac\n\n**Source policy:** upstream repositories, releases, pull requests, issues, and\nmodel/runtime source only; no secondary sources\n\n## Decision\n\n**The prior rejection stands for adoption, but its rationale must be corrected.**\n\nThe original five-model result did not reject a functioning Colibri inference\npipeline. It rejected an invalid experiment: no model server or weights were\npresent, the wrapper silently fell back to a small heuristic scanner, and all\nfive supposedly different model arms produced byte-identical graph artifacts.\nThat evidence says nothing about Colibri model quality or speed.\n\nCurrent upstream evidence nevertheless does not make Colibri an adoption-ready\nGraphify 0.9.39 backend:\n\n1. The released Colibri v1.5.0 cannot expose OLMoE, the only small and\n   hardware-easy model, through `coli serve`. OLMoE launcher support and then\n   the persistent server protocol landed only on the unreleased `dev` branch in\n   [PR #881](https://github.com/JustVugg/colibri/pull/881) and\n   [PR #886](https://github.com/JustVugg/colibri/pull/886).\n2. The unreleased OLMoE server is hard-capped at 4,096 total tokens by a fixed\n   attention score buffer. Graphify defaults to 60,000 input tokens per chunk\n   and requests up to 16,384 output tokens, so the defaults are structurally\n   incompatible.\n3. OLMoE's server rejects grammar-backed `response_format`, and Graphify's\n   ordinary OpenAI path does not send `response_format` anyway. Colibri's GLM\n   grammar mechanism is speculative acceleration, not constrained decoding: it\n   verifies drafts but does not force valid JSON.\n4. The larger model families fit 96 GB only by streaming hundreds of gigabytes\n   of experts from disk. Primary Apple-Silicon measurements range from 0.15\n   tok/s on an M1 Max 32 GB to roughly 0.87-2.06 tok/s on newer 128 GB Max\n   machines under model- and cache-specific tuning. There is no primary M2 Max\n   96 GB result, and the cache behavior is nonlinear, so interpolating a precise\n   number would be dishonest. The available measurements are already far below\n   a practical full-corpus deep-extraction rate.\n5. No primary benchmark establishes that the 7B/1B-active OLMoE model preserves\n   Graphify's rationale nodes, evidence binding, cross-file edges, and deep-mode\n   architectural inferences. Compatibility is not quality evidence.\n\n**Smallest correct next step:** do not adopt Colibri or download a 167-469 GB\nmodel. If local inference is still worth testing, run one bounded canary with\nthe unreleased OLMoE server on a small, scored prose fixture. Treat that as an\nAPI/quality experiment, not a replacement decision.\n\n## Exact versions and refs\n\n| Component | Ref inspected | Exact commit | Status on 2026-08-11 |\n|---|---|---|---|\n| Graphify | `v0.9.39` | [`50556baaea803e191947fdfcc2e0c22e2d4eb74d`](https://github.com/Graphify-Labs/graphify/commit/50556baaea803e191947fdfcc2e0c22e2d4eb74d) | released and pinned by the knowledge base |\n| Colibri | `v1.5.0` | [`8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc`](https://github.com/JustVugg/colibri/commit/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc) | latest release; `main` points to the same commit |\n| Colibri development | `dev` | [`2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b`](https://github.com/JustVugg/colibri/commit/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b) | unreleased; contains OLMoE server work |\n| OLMoE server merge | PR #886 | [`77619b044c32e350d43d7f8648eb4221e2f3aeb2`](https://github.com/JustVugg/colibri/commit/77619b044c32e350d43d7f8648eb4221e2f3aeb2) | merged to `dev` on 2026-08-08, not v1.5.0 |\n\nThe v1.5.0 release notes also matter operationally: the release fixed eight\nsecurity defects, so evaluating an older release to recover some historical\nbehavior is not acceptable. See the\n[v1.5.0 release](https://github.com/JustVugg/colibri/releases/tag/v1.5.0).\n\n## Why the original five-model rejection happened\n\nThe local `agy-graphify-research` wrapper had three independent fail-open\nbehaviors:\n\n- it called a local server only if a health probe succeeded, otherwise returning\n  `_fallback_heuristic_extraction()` as a successful graph;\n- its prompt truncated every file to the first 4,000 characters;\n- its directory loop processed only the first 20 files.\n\nNo model weights were present and no server listened on port 8080. The five\nmodel directories' `graph.json`, `cypher.txt`, and `graph.graphml` files were\nbyte-identical; only report titles changed. The reported 27-43 ms whole-repo\nlatencies and zero inferred/rationale/similar edges corroborate the fallback.\n\nTherefore the correct historical conclusion is:\n\n> Reject the wrapper, benchmark, and claimed model comparison because they did\n> not execute inference. Do not infer that Colibri itself was measured and\n> failed.\n\n## Graphify 0.9.39 request contract\n\nGraphify's OpenAI-compatible backend already accepts a local base URL. At the\nexact 0.9.39 commit it sends:\n\n- `POST /v1/chat/completions` through the OpenAI SDK;\n- one system message containing the extraction rules and exact graph schema;\n- one user message containing the corpus chunk;\n- `max_completion_tokens` (default 16,384), `stream: false`, and temperature;\n- no `response_format` on the built-in OpenAI path.\n\nThe relevant primary source is\n[`graphify/llm.py`](https://github.com/Graphify-Labs/graphify/blob/50556baaea803e191947fdfcc2e0c22e2d4eb74d/graphify/llm.py#L1156-L1266).\nGraphify's default semantic chunk budget is 60,000 tokens and default\nconcurrency is four; failed chunks are skipped and counted, while context or\ntruncation signals cause recursive bisection up to three levels. See\n[`extract_corpus_parallel`](https://github.com/Graphify-Labs/graphify/blob/50556baaea803e191947fdfcc2e0c22e2d4eb74d/graphify/llm.py#L2227-L2273).\n\nGraphify exposes the necessary tuning controls:\n\n- `--token-budget N`;\n- `--max-concurrency N`;\n- `GRAPHIFY_MAX_OUTPUT_TOKENS`;\n- `GRAPHIFY_API_TIMEOUT` / `--api-timeout`.\n\nA custom provider may inject a static `extra_body`, so a GLM can receive\n`response_format`. That is not equivalent to a Graphify-native schema guarantee,\nand it cannot help OLMoE because the Colibri gateway explicitly rejects grammar\npayloads for that engine.\n\n## Colibri server API and structured-output behavior\n\nColibri v1.5.0 exposes `GET /v1/models`, `GET /v1/models/{model}`,\n`POST /v1/chat/completions`, legacy `POST /v1/completions`, and\n`POST /v1/messages`. The OpenAI route supports JSON and SSE responses, usage,\n`max_tokens` and `max_completion_tokens`, temperature, top-p, stop sequences,\nand tools. It serves one generation at a time behind a bounded FIFO queue. The\nauthoritative endpoint and behavior description is\n[`docs/api.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/docs/api.md#L3-L76).\n\nThe exact `response_format` surface accepts:\n\n```json\n{\"response_format\":{\"type\":\"json_object\"}}\n{\"response_format\":{\"type\":\"json_schema\",\"json_schema\":{\"schema\":{}}}}\n{\"response_format\":{\"type\":\"gbnf\",\"grammar\":\"root ::= ...\"}}\n```\n\nThe schema or grammar is limited to 1 MiB. `max_completion_tokens` is accepted,\nthen clamped to the server operator's `--max-tokens` limit. See\n[`generation_options`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/c/openai_server.py#L1232-L1343).\n\nThis is not strict structured decoding. Colibri documents the grammar as a\n**draft source, never a sampling constraint**: model-produced tokens remain the\nauthority, and a malformed or unsupported schema merely removes the speedup.\nThe measured GLM grammar A/B on an M3 Max 128 GB improved a structured NDJSON\nworkload from 0.37 to 0.50 tok/s with byte-identical output, but free-text fields\nforce little and current-main prose-heavy windows show approximately no gain.\nSee\n[`docs/grammar-draft.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/docs/grammar-draft.md#L8-L75)\nand [PR #70](https://github.com/JustVugg/colibri/pull/70).\n\n## Model inventory and constraints\n\nThe released README's model table is the authoritative inventory for v1.5.0:\n\n| Model | Total / active parameters | Disk | RAM | Context/API/structured-output consequence |\n|---|---:|---:|---:|---|\n| OLMoE | 7B / 1B | ~4 GB | 8 GB | v1.5.0 cannot serve it; unreleased `dev` can, but hard cap is 4,096 tokens and grammar is rejected |\n| DeepSeek V4 Flash | 284B / 13B | ~167 GB | 16 GB min / 22 GB comfortable | server is greedy, one KV slot; tools and grammar rejected; a measured 14-token answer took 495 s with failed speculation economics |\n| GLM-5.2 | 744B / 40B | ~372 GB for the documented int4-g64 model | 16 GB min / 24 GB comfortable | mature server and grammar path; context defaults to 4,096 but `CTX` is configurable; throughput is the blocker |\n| Inkling | 975B / 41B | ~469 GB | 25 GB with int4 dense container; ~120 GB otherwise | grammar rejected; low-RAM mode is documented as tens of seconds/token |\n| Kimi K3 | 2.8T / 104B | ~1.6 TB | 32 GB+ | does not fit the target's practical storage envelope; grammar rejected |\n\nPrimary inventory:\n[`README.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/README.md#L359-L396).\n\n### Stable versus development OLMoE\n\nThe released README currently overstates OLMoE uniformity by saying all sibling\nengines use the same `chat`/`serve`/`web` front end. The implementation history\nshows otherwise:\n\n- [PR #881](https://github.com/JustVugg/colibri/pull/881) fixed one-shot\n  `coli run` dispatch and explicitly stated that chat/web/serve were still\n  unavailable.\n- [PR #886](https://github.com/JustVugg/colibri/pull/886) added OLMoE's\n  READY/SUBMIT/DATA/DONE protocol and verified real HTTP inference, but merged\n  only to `dev` after v1.5.0.\n- At the PR #886 merge, `olmoe.c` still caps `CTX` to 1..4096 because\n  `attention()` uses a fixed `sc[4096]` buffer. It fully re-prefills each request\n  and supports only one request in flight.\n- The development gateway explicitly rejects `response_format` grammars for\n  OLMoE because its stdin framing does not carry the grammar extension.\n\nThis makes OLMoE an unreleased compatibility experiment, not a release-pinned\ndeployment candidate.\n\n## Apple Silicon performance and resource evidence\n\nThe earlier local report's claims of 142.8 tok/s prefill, 18.4 tok/s decode,\n7 ms TTFT, and 38-52 GB peak memory are not admissible: they were not measured\nwith model weights or inference.\n\nPrimary upstream measurements establish the real order of magnitude:\n\n| Host/model/config | Measured result | Interpretation |\n|---|---:|---|\n| M1 Max 32 GB, GLM int4-g64 | 0.15 tok/s best; 24-token prefill ~115 s | working demonstration, not productive extraction; [issue #706](https://github.com/JustVugg/colibri/issues/706) |\n| M5 Max 128 GB, GLM pre-g64 tuned | about 2.0 tok/s | requires careful cache/MTP tuning; results are format- and thermal-state-specific; [issue #387](https://github.com/JustVugg/colibri/issues/387) |\n| M5 Max 128 GB, current documented GLM int4-g64 | 0.27-0.32 tok/s | Metal's routed-expert path rejects fmt=4, leaving experts on CPU; [issue #813](https://github.com/JustVugg/colibri/issues/813) |\n| M5 Max 128 GB, GLM E8/IQ3 fmt=6, `MTP=0`, explicit cache | 0.87 tok/s warm | best verified current-format workaround; Metal experts engage, but CPU attention becomes dominant; [issue #813 comment](https://github.com/JustVugg/colibri/issues/813#issuecomment-5193325122) |\n| M3 Ultra 512 GB, fully resident GLM int4-g64 | 1.36 tok/s tuned versus llama.cpp 15.1 tok/s | confirms the fmt=4 Metal dispatch gap; [issue #813](https://github.com/JustVugg/colibri/issues/813) |\n\nColibri's own API guide warns that 10-20k-token coding-agent preambles can take\nabout an hour before first output and that iterative disk-streaming agent loops\nare generally not worth the wait. Graphify is not an interactive coding agent,\nbut its default 60k-token semantic chunks are larger still. See\n[`docs/api.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/docs/api.md#L175-L192).\n\nThe target M2 Max 96 GB lies between published 32 GB and 128 GB Max results, but\nthroughput must not be linearly interpolated: expert residency, format support,\nOS page cache, MTP, Metal dispatch, and SSD state change the regime. A real-host\ncanary is required for any rate claim.\n\n## Decision matrix\n\n| Candidate | Graphify 0.9.39 API fit | Context fit | Structured JSON assistance | Target-host practicality | Quality evidence | Decision |\n|---|---|---|---|---|---|---|\n| v1.5.0 + OLMoE | **No server path** | hard 4,096 in engine | none | excellent size | none for Graphify deep extraction | **Reject** |\n| `dev` @ `2c8ce27` + OLMoE | OpenAI route works | **fails defaults**; only viable with very small chunks and output cap | gateway rejects grammar | excellent size; sequential full re-prefill | none | **Canary only** |\n| v1.5.0 + GLM int4-g64 | API works | configurable | grammar available but Graphify does not send it by default | 372 GB; current Metal expert path does not support fmt=4 | model is capable, extraction unmeasured | **Reject** |\n| v1.5.0 + GLM E8/IQ3 fmt=6 | API works | configurable; use 32k or lower on this host | grammar available through a custom provider | roughly 280 GB and 0.87 tok/s on a faster 128 GB M5 Max | extraction unmeasured | **Technically viable, operationally poor** |\n| v1.5.0 + DeepSeek V4 | API works | default 4,096; configurable | grammar/tools rejected | 167 GB; extremely slow measured path | extraction unmeasured | **Reject** |\n| v1.5.0 + Inkling | API works | default 8,192 | grammar rejected | 469 GB; tens of seconds/token in low-RAM mode | extraction unmeasured | **Reject** |\n| v1.5.0 + Kimi K3 | API works | default 8,192 | grammar rejected | 1.6 TB | extraction unmeasured | **Reject** |\n| open PR #544 Qwen3-30B-A3B | no `coli`/serve integration yet | not deployment-ready | none established | promising 30B/3B-active architecture | token-exact engine fixture only | **Watch, do not adopt** |\n\n## Bounded canary, if explicitly approved\n\nThe only proportionate experiment is OLMoE on the unreleased development commit,\nbecause it avoids a hundreds-of-gigabytes download. It must be gated as follows:\n\n1. Pin exact commit `2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b`, not moving `dev`.\n2. Build OLMoE and convert `allenai/OLMoE-1B-7B-0125-Instruct`; run `coli\n   doctor --deep` before serving.\n3. Serve with one generation at a time, 4,096 context, and a 1,024-token output\n   ceiling.\n4. Point a Graphify custom provider at `http://127.0.0.1:8000/v1`; do not add\n   `response_format`, which OLMoE rejects.\n5. Run Graphify with `--mode deep --token-budget 1000 --max-concurrency 1`,\n   `GRAPHIFY_MAX_OUTPUT_TOKENS=1024`, and an explicit API timeout.\n6. Use a small frozen prose fixture with a Claude-derived expected graph and\n   score node/edge recall, rationale capture, source/evidence binding, invalid\n   JSON rate, truncation/retry rate, and wall time. Include a no-server negative\n   control so fallback or accidental cloud routing cannot pass.\n\nPassing this canary would establish only that the small model can perform the\nfixture under constrained chunks. It would not establish full-corpus quality or\njustify changing the knowledge-base backend invariant.\n\n## Final recommendation\n\nKeep Colibri rejected for Graphify 0.9.39 production deep extraction.\n\n- **Correct the old reason:** the earlier experiment was fake inference, not a\n  model defeat.\n- **Do not use stable OLMoE:** v1.5.0 cannot serve it.\n- **Do not use large Colibri models for routine extraction:** the storage and\n  observed Apple-Silicon throughput make them operationally disproportionate.\n- **Allow one OLMoE canary only if local-token elimination remains a priority:**\n  it is the sole low-cost way to answer the currently missing quality question.\n- **Revisit after a release includes OLMoE serve plus a context-window increase,\n  or after Qwen3-30B-A3B gains released launcher/server integration and an\n  Apple-Silicon extraction benchmark.**\n\n## Verification gaps\n\n- No real Colibri weights are installed on the target host, so this pass did not\n  execute inference.\n- No primary M2 Max 96 GB Colibri benchmark exists.\n- No primary Colibri-model benchmark covers Graphify 0.9.39 deep extraction\n  fidelity.\n- OLMoE serve is unreleased and may change before the next tag.\n- Colibri's README currently describes a uniform OLMoE server surface that the\n  latest release does not contain; source and merged-PR history take precedence.\n\nThese gaps are exactly why the recommendation is reject-for-adoption and\ncanary-for-learning, rather than a categorical claim that Colibri can never be\nmade viable.\n"
source_nodes: ["colibri.c", "olmoe.c", "graphify"]
---

# Q: Why was Colibri rejected for Graphify deep extraction, and should that decision change after primary-source research?

## Answer

# Colibri compatibility with Graphify 0.9.39 deep extraction

**Date:** 2026-08-11

**Status:** complete; source-verified, no model weights downloaded

**Scope:** `JustVugg/colibri` as a local OpenAI-compatible backend for
`Graphify-Labs/graphify` 0.9.39 deep semantic extraction on the target M2 Max,
96 GB unified-memory Mac

**Source policy:** upstream repositories, releases, pull requests, issues, and
model/runtime source only; no secondary sources

## Decision

**The prior rejection stands for adoption, but its rationale must be corrected.**

The original five-model result did not reject a functioning Colibri inference
pipeline. It rejected an invalid experiment: no model server or weights were
present, the wrapper silently fell back to a small heuristic scanner, and all
five supposedly different model arms produced byte-identical graph artifacts.
That evidence says nothing about Colibri model quality or speed.

Current upstream evidence nevertheless does not make Colibri an adoption-ready
Graphify 0.9.39 backend:

1. The released Colibri v1.5.0 cannot expose OLMoE, the only small and
   hardware-easy model, through `coli serve`. OLMoE launcher support and then
   the persistent server protocol landed only on the unreleased `dev` branch in
   [PR #881](https://github.com/JustVugg/colibri/pull/881) and
   [PR #886](https://github.com/JustVugg/colibri/pull/886).
2. The unreleased OLMoE server is hard-capped at 4,096 total tokens by a fixed
   attention score buffer. Graphify defaults to 60,000 input tokens per chunk
   and requests up to 16,384 output tokens, so the defaults are structurally
   incompatible.
3. OLMoE's server rejects grammar-backed `response_format`, and Graphify's
   ordinary OpenAI path does not send `response_format` anyway. Colibri's GLM
   grammar mechanism is speculative acceleration, not constrained decoding: it
   verifies drafts but does not force valid JSON.
4. The larger model families fit 96 GB only by streaming hundreds of gigabytes
   of experts from disk. Primary Apple-Silicon measurements range from 0.15
   tok/s on an M1 Max 32 GB to roughly 0.87-2.06 tok/s on newer 128 GB Max
   machines under model- and cache-specific tuning. There is no primary M2 Max
   96 GB result, and the cache behavior is nonlinear, so interpolating a precise
   number would be dishonest. The available measurements are already far below
   a practical full-corpus deep-extraction rate.
5. No primary benchmark establishes that the 7B/1B-active OLMoE model preserves
   Graphify's rationale nodes, evidence binding, cross-file edges, and deep-mode
   architectural inferences. Compatibility is not quality evidence.

**Smallest correct next step:** do not adopt Colibri or download a 167-469 GB
model. If local inference is still worth testing, run one bounded canary with
the unreleased OLMoE server on a small, scored prose fixture. Treat that as an
API/quality experiment, not a replacement decision.

## Exact versions and refs

| Component | Ref inspected | Exact commit | Status on 2026-08-11 |
|---|---|---|---|
| Graphify | `v0.9.39` | [`50556baaea803e191947fdfcc2e0c22e2d4eb74d`](https://github.com/Graphify-Labs/graphify/commit/50556baaea803e191947fdfcc2e0c22e2d4eb74d) | released and pinned by the knowledge base |
| Colibri | `v1.5.0` | [`8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc`](https://github.com/JustVugg/colibri/commit/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc) | latest release; `main` points to the same commit |
| Colibri development | `dev` | [`2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b`](https://github.com/JustVugg/colibri/commit/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b) | unreleased; contains OLMoE server work |
| OLMoE server merge | PR #886 | [`77619b044c32e350d43d7f8648eb4221e2f3aeb2`](https://github.com/JustVugg/colibri/commit/77619b044c32e350d43d7f8648eb4221e2f3aeb2) | merged to `dev` on 2026-08-08, not v1.5.0 |

The v1.5.0 release notes also matter operationally: the release fixed eight
security defects, so evaluating an older release to recover some historical
behavior is not acceptable. See the
[v1.5.0 release](https://github.com/JustVugg/colibri/releases/tag/v1.5.0).

## Why the original five-model rejection happened

The local `agy-graphify-research` wrapper had three independent fail-open
behaviors:

- it called a local server only if a health probe succeeded, otherwise returning
  `_fallback_heuristic_extraction()` as a successful graph;
- its prompt truncated every file to the first 4,000 characters;
- its directory loop processed only the first 20 files.

No model weights were present and no server listened on port 8080. The five
model directories' `graph.json`, `cypher.txt`, and `graph.graphml` files were
byte-identical; only report titles changed. The reported 27-43 ms whole-repo
latencies and zero inferred/rationale/similar edges corroborate the fallback.

Therefore the correct historical conclusion is:

> Reject the wrapper, benchmark, and claimed model comparison because they did
> not execute inference. Do not infer that Colibri itself was measured and
> failed.

## Graphify 0.9.39 request contract

Graphify's OpenAI-compatible backend already accepts a local base URL. At the
exact 0.9.39 commit it sends:

- `POST /v1/chat/completions` through the OpenAI SDK;
- one system message containing the extraction rules and exact graph schema;
- one user message containing the corpus chunk;
- `max_completion_tokens` (default 16,384), `stream: false`, and temperature;
- no `response_format` on the built-in OpenAI path.

The relevant primary source is
[`graphify/llm.py`](https://github.com/Graphify-Labs/graphify/blob/50556baaea803e191947fdfcc2e0c22e2d4eb74d/graphify/llm.py#L1156-L1266).
Graphify's default semantic chunk budget is 60,000 tokens and default
concurrency is four; failed chunks are skipped and counted, while context or
truncation signals cause recursive bisection up to three levels. See
[`extract_corpus_parallel`](https://github.com/Graphify-Labs/graphify/blob/50556baaea803e191947fdfcc2e0c22e2d4eb74d/graphify/llm.py#L2227-L2273).

Graphify exposes the necessary tuning controls:

- `--token-budget N`;
- `--max-concurrency N`;
- `GRAPHIFY_MAX_OUTPUT_TOKENS`;
- `GRAPHIFY_API_TIMEOUT` / `--api-timeout`.

A custom provider may inject a static `extra_body`, so a GLM can receive
`response_format`. That is not equivalent to a Graphify-native schema guarantee,
and it cannot help OLMoE because the Colibri gateway explicitly rejects grammar
payloads for that engine.

## Colibri server API and structured-output behavior

Colibri v1.5.0 exposes `GET /v1/models`, `GET /v1/models/{model}`,
`POST /v1/chat/completions`, legacy `POST /v1/completions`, and
`POST /v1/messages`. The OpenAI route supports JSON and SSE responses, usage,
`max_tokens` and `max_completion_tokens`, temperature, top-p, stop sequences,
and tools. It serves one generation at a time behind a bounded FIFO queue. The
authoritative endpoint and behavior description is
[`docs/api.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/docs/api.md#L3-L76).

The exact `response_format` surface accepts:

```json
{"response_format":{"type":"json_object"}}
{"response_format":{"type":"json_schema","json_schema":{"schema":{}}}}
{"response_format":{"type":"gbnf","grammar":"root ::= ..."}}
```

The schema or grammar is limited to 1 MiB. `max_completion_tokens` is accepted,
then clamped to the server operator's `--max-tokens` limit. See
[`generation_options`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/c/openai_server.py#L1232-L1343).

This is not strict structured decoding. Colibri documents the grammar as a
**draft source, never a sampling constraint**: model-produced tokens remain the
authority, and a malformed or unsupported schema merely removes the speedup.
The measured GLM grammar A/B on an M3 Max 128 GB improved a structured NDJSON
workload from 0.37 to 0.50 tok/s with byte-identical output, but free-text fields
force little and current-main prose-heavy windows show approximately no gain.
See
[`docs/grammar-draft.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/docs/grammar-draft.md#L8-L75)
and [PR #70](https://github.com/JustVugg/colibri/pull/70).

## Model inventory and constraints

The released README's model table is the authoritative inventory for v1.5.0:

| Model | Total / active parameters | Disk | RAM | Context/API/structured-output consequence |
|---|---:|---:|---:|---|
| OLMoE | 7B / 1B | ~4 GB | 8 GB | v1.5.0 cannot serve it; unreleased `dev` can, but hard cap is 4,096 tokens and grammar is rejected |
| DeepSeek V4 Flash | 284B / 13B | ~167 GB | 16 GB min / 22 GB comfortable | server is greedy, one KV slot; tools and grammar rejected; a measured 14-token answer took 495 s with failed speculation economics |
| GLM-5.2 | 744B / 40B | ~372 GB for the documented int4-g64 model | 16 GB min / 24 GB comfortable | mature server and grammar path; context defaults to 4,096 but `CTX` is configurable; throughput is the blocker |
| Inkling | 975B / 41B | ~469 GB | 25 GB with int4 dense container; ~120 GB otherwise | grammar rejected; low-RAM mode is documented as tens of seconds/token |
| Kimi K3 | 2.8T / 104B | ~1.6 TB | 32 GB+ | does not fit the target's practical storage envelope; grammar rejected |

Primary inventory:
[`README.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/README.md#L359-L396).

### Stable versus development OLMoE

The released README currently overstates OLMoE uniformity by saying all sibling
engines use the same `chat`/`serve`/`web` front end. The implementation history
shows otherwise:

- [PR #881](https://github.com/JustVugg/colibri/pull/881) fixed one-shot
  `coli run` dispatch and explicitly stated that chat/web/serve were still
  unavailable.
- [PR #886](https://github.com/JustVugg/colibri/pull/886) added OLMoE's
  READY/SUBMIT/DATA/DONE protocol and verified real HTTP inference, but merged
  only to `dev` after v1.5.0.
- At the PR #886 merge, `olmoe.c` still caps `CTX` to 1..4096 because
  `attention()` uses a fixed `sc[4096]` buffer. It fully re-prefills each request
  and supports only one request in flight.
- The development gateway explicitly rejects `response_format` grammars for
  OLMoE because its stdin framing does not carry the grammar extension.

This makes OLMoE an unreleased compatibility experiment, not a release-pinned
deployment candidate.

## Apple Silicon performance and resource evidence

The earlier local report's claims of 142.8 tok/s prefill, 18.4 tok/s decode,
7 ms TTFT, and 38-52 GB peak memory are not admissible: they were not measured
with model weights or inference.

Primary upstream measurements establish the real order of magnitude:

| Host/model/config | Measured result | Interpretation |
|---|---:|---|
| M1 Max 32 GB, GLM int4-g64 | 0.15 tok/s best; 24-token prefill ~115 s | working demonstration, not productive extraction; [issue #706](https://github.com/JustVugg/colibri/issues/706) |
| M5 Max 128 GB, GLM pre-g64 tuned | about 2.0 tok/s | requires careful cache/MTP tuning; results are format- and thermal-state-specific; [issue #387](https://github.com/JustVugg/colibri/issues/387) |
| M5 Max 128 GB, current documented GLM int4-g64 | 0.27-0.32 tok/s | Metal's routed-expert path rejects fmt=4, leaving experts on CPU; [issue #813](https://github.com/JustVugg/colibri/issues/813) |
| M5 Max 128 GB, GLM E8/IQ3 fmt=6, `MTP=0`, explicit cache | 0.87 tok/s warm | best verified current-format workaround; Metal experts engage, but CPU attention becomes dominant; [issue #813 comment](https://github.com/JustVugg/colibri/issues/813#issuecomment-5193325122) |
| M3 Ultra 512 GB, fully resident GLM int4-g64 | 1.36 tok/s tuned versus llama.cpp 15.1 tok/s | confirms the fmt=4 Metal dispatch gap; [issue #813](https://github.com/JustVugg/colibri/issues/813) |

Colibri's own API guide warns that 10-20k-token coding-agent preambles can take
about an hour before first output and that iterative disk-streaming agent loops
are generally not worth the wait. Graphify is not an interactive coding agent,
but its default 60k-token semantic chunks are larger still. See
[`docs/api.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/docs/api.md#L175-L192).

The target M2 Max 96 GB lies between published 32 GB and 128 GB Max results, but
throughput must not be linearly interpolated: expert residency, format support,
OS page cache, MTP, Metal dispatch, and SSD state change the regime. A real-host
canary is required for any rate claim.

## Decision matrix

| Candidate | Graphify 0.9.39 API fit | Context fit | Structured JSON assistance | Target-host practicality | Quality evidence | Decision |
|---|---|---|---|---|---|---|
| v1.5.0 + OLMoE | **No server path** | hard 4,096 in engine | none | excellent size | none for Graphify deep extraction | **Reject** |
| `dev` @ `2c8ce27` + OLMoE | OpenAI route works | **fails defaults**; only viable with very small chunks and output cap | gateway rejects grammar | excellent size; sequential full re-prefill | none | **Canary only** |
| v1.5.0 + GLM int4-g64 | API works | configurable | grammar available but Graphify does not send it by default | 372 GB; current Metal expert path does not support fmt=4 | model is capable, extraction unmeasured | **Reject** |
| v1.5.0 + GLM E8/IQ3 fmt=6 | API works | configurable; use 32k or lower on this host | grammar available through a custom provider | roughly 280 GB and 0.87 tok/s on a faster 128 GB M5 Max | extraction unmeasured | **Technically viable, operationally poor** |
| v1.5.0 + DeepSeek V4 | API works | default 4,096; configurable | grammar/tools rejected | 167 GB; extremely slow measured path | extraction unmeasured | **Reject** |
| v1.5.0 + Inkling | API works | default 8,192 | grammar rejected | 469 GB; tens of seconds/token in low-RAM mode | extraction unmeasured | **Reject** |
| v1.5.0 + Kimi K3 | API works | default 8,192 | grammar rejected | 1.6 TB | extraction unmeasured | **Reject** |
| open PR #544 Qwen3-30B-A3B | no `coli`/serve integration yet | not deployment-ready | none established | promising 30B/3B-active architecture | token-exact engine fixture only | **Watch, do not adopt** |

## Bounded canary, if explicitly approved

The only proportionate experiment is OLMoE on the unreleased development commit,
because it avoids a hundreds-of-gigabytes download. It must be gated as follows:

1. Pin exact commit `2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b`, not moving `dev`.
2. Build OLMoE and convert `allenai/OLMoE-1B-7B-0125-Instruct`; run `coli
   doctor --deep` before serving.
3. Serve with one generation at a time, 4,096 context, and a 1,024-token output
   ceiling.
4. Point a Graphify custom provider at `http://127.0.0.1:8000/v1`; do not add
   `response_format`, which OLMoE rejects.
5. Run Graphify with `--mode deep --token-budget 1000 --max-concurrency 1`,
   `GRAPHIFY_MAX_OUTPUT_TOKENS=1024`, and an explicit API timeout.
6. Use a small frozen prose fixture with a Claude-derived expected graph and
   score node/edge recall, rationale capture, source/evidence binding, invalid
   JSON rate, truncation/retry rate, and wall time. Include a no-server negative
   control so fallback or accidental cloud routing cannot pass.

Passing this canary would establish only that the small model can perform the
fixture under constrained chunks. It would not establish full-corpus quality or
justify changing the knowledge-base backend invariant.

## Final recommendation

Keep Colibri rejected for Graphify 0.9.39 production deep extraction.

- **Correct the old reason:** the earlier experiment was fake inference, not a
  model defeat.
- **Do not use stable OLMoE:** v1.5.0 cannot serve it.
- **Do not use large Colibri models for routine extraction:** the storage and
  observed Apple-Silicon throughput make them operationally disproportionate.
- **Allow one OLMoE canary only if local-token elimination remains a priority:**
  it is the sole low-cost way to answer the currently missing quality question.
- **Revisit after a release includes OLMoE serve plus a context-window increase,
  or after Qwen3-30B-A3B gains released launcher/server integration and an
  Apple-Silicon extraction benchmark.**

## Verification gaps

- No real Colibri weights are installed on the target host, so this pass did not
  execute inference.
- No primary M2 Max 96 GB Colibri benchmark exists.
- No primary Colibri-model benchmark covers Graphify 0.9.39 deep extraction
  fidelity.
- OLMoE serve is unreleased and may change before the next tag.
- Colibri's README currently describes a uniform OLMoE server surface that the
  latest release does not contain; source and merged-PR history take precedence.

These gaps are exactly why the recommendation is reject-for-adoption and
canary-for-learning, rather than a categorical claim that Colibri can never be
made viable.


## Outcome

- Signal: corrected
- Correction: # Colibri compatibility with Graphify 0.9.39 deep extraction

**Date:** 2026-08-11

**Status:** complete; source-verified, no model weights downloaded

**Scope:** `JustVugg/colibri` as a local OpenAI-compatible backend for
`Graphify-Labs/graphify` 0.9.39 deep semantic extraction on the target M2 Max,
96 GB unified-memory Mac

**Source policy:** upstream repositories, releases, pull requests, issues, and
model/runtime source only; no secondary sources

## Decision

**The prior rejection stands for adoption, but its rationale must be corrected.**

The original five-model result did not reject a functioning Colibri inference
pipeline. It rejected an invalid experiment: no model server or weights were
present, the wrapper silently fell back to a small heuristic scanner, and all
five supposedly different model arms produced byte-identical graph artifacts.
That evidence says nothing about Colibri model quality or speed.

Current upstream evidence nevertheless does not make Colibri an adoption-ready
Graphify 0.9.39 backend:

1. The released Colibri v1.5.0 cannot expose OLMoE, the only small and
   hardware-easy model, through `coli serve`. OLMoE launcher support and then
   the persistent server protocol landed only on the unreleased `dev` branch in
   [PR #881](https://github.com/JustVugg/colibri/pull/881) and
   [PR #886](https://github.com/JustVugg/colibri/pull/886).
2. The unreleased OLMoE server is hard-capped at 4,096 total tokens by a fixed
   attention score buffer. Graphify defaults to 60,000 input tokens per chunk
   and requests up to 16,384 output tokens, so the defaults are structurally
   incompatible.
3. OLMoE's server rejects grammar-backed `response_format`, and Graphify's
   ordinary OpenAI path does not send `response_format` anyway. Colibri's GLM
   grammar mechanism is speculative acceleration, not constrained decoding: it
   verifies drafts but does not force valid JSON.
4. The larger model families fit 96 GB only by streaming hundreds of gigabytes
   of experts from disk. Primary Apple-Silicon measurements range from 0.15
   tok/s on an M1 Max 32 GB to roughly 0.87-2.06 tok/s on newer 128 GB Max
   machines under model- and cache-specific tuning. There is no primary M2 Max
   96 GB result, and the cache behavior is nonlinear, so interpolating a precise
   number would be dishonest. The available measurements are already far below
   a practical full-corpus deep-extraction rate.
5. No primary benchmark establishes that the 7B/1B-active OLMoE model preserves
   Graphify's rationale nodes, evidence binding, cross-file edges, and deep-mode
   architectural inferences. Compatibility is not quality evidence.

**Smallest correct next step:** do not adopt Colibri or download a 167-469 GB
model. If local inference is still worth testing, run one bounded canary with
the unreleased OLMoE server on a small, scored prose fixture. Treat that as an
API/quality experiment, not a replacement decision.

## Exact versions and refs

| Component | Ref inspected | Exact commit | Status on 2026-08-11 |
|---|---|---|---|
| Graphify | `v0.9.39` | [`50556baaea803e191947fdfcc2e0c22e2d4eb74d`](https://github.com/Graphify-Labs/graphify/commit/50556baaea803e191947fdfcc2e0c22e2d4eb74d) | released and pinned by the knowledge base |
| Colibri | `v1.5.0` | [`8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc`](https://github.com/JustVugg/colibri/commit/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc) | latest release; `main` points to the same commit |
| Colibri development | `dev` | [`2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b`](https://github.com/JustVugg/colibri/commit/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b) | unreleased; contains OLMoE server work |
| OLMoE server merge | PR #886 | [`77619b044c32e350d43d7f8648eb4221e2f3aeb2`](https://github.com/JustVugg/colibri/commit/77619b044c32e350d43d7f8648eb4221e2f3aeb2) | merged to `dev` on 2026-08-08, not v1.5.0 |

The v1.5.0 release notes also matter operationally: the release fixed eight
security defects, so evaluating an older release to recover some historical
behavior is not acceptable. See the
[v1.5.0 release](https://github.com/JustVugg/colibri/releases/tag/v1.5.0).

## Why the original five-model rejection happened

The local `agy-graphify-research` wrapper had three independent fail-open
behaviors:

- it called a local server only if a health probe succeeded, otherwise returning
  `_fallback_heuristic_extraction()` as a successful graph;
- its prompt truncated every file to the first 4,000 characters;
- its directory loop processed only the first 20 files.

No model weights were present and no server listened on port 8080. The five
model directories' `graph.json`, `cypher.txt`, and `graph.graphml` files were
byte-identical; only report titles changed. The reported 27-43 ms whole-repo
latencies and zero inferred/rationale/similar edges corroborate the fallback.

Therefore the correct historical conclusion is:

> Reject the wrapper, benchmark, and claimed model comparison because they did
> not execute inference. Do not infer that Colibri itself was measured and
> failed.

## Graphify 0.9.39 request contract

Graphify's OpenAI-compatible backend already accepts a local base URL. At the
exact 0.9.39 commit it sends:

- `POST /v1/chat/completions` through the OpenAI SDK;
- one system message containing the extraction rules and exact graph schema;
- one user message containing the corpus chunk;
- `max_completion_tokens` (default 16,384), `stream: false`, and temperature;
- no `response_format` on the built-in OpenAI path.

The relevant primary source is
[`graphify/llm.py`](https://github.com/Graphify-Labs/graphify/blob/50556baaea803e191947fdfcc2e0c22e2d4eb74d/graphify/llm.py#L1156-L1266).
Graphify's default semantic chunk budget is 60,000 tokens and default
concurrency is four; failed chunks are skipped and counted, while context or
truncation signals cause recursive bisection up to three levels. See
[`extract_corpus_parallel`](https://github.com/Graphify-Labs/graphify/blob/50556baaea803e191947fdfcc2e0c22e2d4eb74d/graphify/llm.py#L2227-L2273).

Graphify exposes the necessary tuning controls:

- `--token-budget N`;
- `--max-concurrency N`;
- `GRAPHIFY_MAX_OUTPUT_TOKENS`;
- `GRAPHIFY_API_TIMEOUT` / `--api-timeout`.

A custom provider may inject a static `extra_body`, so a GLM can receive
`response_format`. That is not equivalent to a Graphify-native schema guarantee,
and it cannot help OLMoE because the Colibri gateway explicitly rejects grammar
payloads for that engine.

## Colibri server API and structured-output behavior

Colibri v1.5.0 exposes `GET /v1/models`, `GET /v1/models/{model}`,
`POST /v1/chat/completions`, legacy `POST /v1/completions`, and
`POST /v1/messages`. The OpenAI route supports JSON and SSE responses, usage,
`max_tokens` and `max_completion_tokens`, temperature, top-p, stop sequences,
and tools. It serves one generation at a time behind a bounded FIFO queue. The
authoritative endpoint and behavior description is
[`docs/api.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/docs/api.md#L3-L76).

The exact `response_format` surface accepts:

```json
{"response_format":{"type":"json_object"}}
{"response_format":{"type":"json_schema","json_schema":{"schema":{}}}}
{"response_format":{"type":"gbnf","grammar":"root ::= ..."}}
```

The schema or grammar is limited to 1 MiB. `max_completion_tokens` is accepted,
then clamped to the server operator's `--max-tokens` limit. See
[`generation_options`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/c/openai_server.py#L1232-L1343).

This is not strict structured decoding. Colibri documents the grammar as a
**draft source, never a sampling constraint**: model-produced tokens remain the
authority, and a malformed or unsupported schema merely removes the speedup.
The measured GLM grammar A/B on an M3 Max 128 GB improved a structured NDJSON
workload from 0.37 to 0.50 tok/s with byte-identical output, but free-text fields
force little and current-main prose-heavy windows show approximately no gain.
See
[`docs/grammar-draft.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/docs/grammar-draft.md#L8-L75)
and [PR #70](https://github.com/JustVugg/colibri/pull/70).

## Model inventory and constraints

The released README's model table is the authoritative inventory for v1.5.0:

| Model | Total / active parameters | Disk | RAM | Context/API/structured-output consequence |
|---|---:|---:|---:|---|
| OLMoE | 7B / 1B | ~4 GB | 8 GB | v1.5.0 cannot serve it; unreleased `dev` can, but hard cap is 4,096 tokens and grammar is rejected |
| DeepSeek V4 Flash | 284B / 13B | ~167 GB | 16 GB min / 22 GB comfortable | server is greedy, one KV slot; tools and grammar rejected; a measured 14-token answer took 495 s with failed speculation economics |
| GLM-5.2 | 744B / 40B | ~372 GB for the documented int4-g64 model | 16 GB min / 24 GB comfortable | mature server and grammar path; context defaults to 4,096 but `CTX` is configurable; throughput is the blocker |
| Inkling | 975B / 41B | ~469 GB | 25 GB with int4 dense container; ~120 GB otherwise | grammar rejected; low-RAM mode is documented as tens of seconds/token |
| Kimi K3 | 2.8T / 104B | ~1.6 TB | 32 GB+ | does not fit the target's practical storage envelope; grammar rejected |

Primary inventory:
[`README.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/README.md#L359-L396).

### Stable versus development OLMoE

The released README currently overstates OLMoE uniformity by saying all sibling
engines use the same `chat`/`serve`/`web` front end. The implementation history
shows otherwise:

- [PR #881](https://github.com/JustVugg/colibri/pull/881) fixed one-shot
  `coli run` dispatch and explicitly stated that chat/web/serve were still
  unavailable.
- [PR #886](https://github.com/JustVugg/colibri/pull/886) added OLMoE's
  READY/SUBMIT/DATA/DONE protocol and verified real HTTP inference, but merged
  only to `dev` after v1.5.0.
- At the PR #886 merge, `olmoe.c` still caps `CTX` to 1..4096 because
  `attention()` uses a fixed `sc[4096]` buffer. It fully re-prefills each request
  and supports only one request in flight.
- The development gateway explicitly rejects `response_format` grammars for
  OLMoE because its stdin framing does not carry the grammar extension.

This makes OLMoE an unreleased compatibility experiment, not a release-pinned
deployment candidate.

## Apple Silicon performance and resource evidence

The earlier local report's claims of 142.8 tok/s prefill, 18.4 tok/s decode,
7 ms TTFT, and 38-52 GB peak memory are not admissible: they were not measured
with model weights or inference.

Primary upstream measurements establish the real order of magnitude:

| Host/model/config | Measured result | Interpretation |
|---|---:|---|
| M1 Max 32 GB, GLM int4-g64 | 0.15 tok/s best; 24-token prefill ~115 s | working demonstration, not productive extraction; [issue #706](https://github.com/JustVugg/colibri/issues/706) |
| M5 Max 128 GB, GLM pre-g64 tuned | about 2.0 tok/s | requires careful cache/MTP tuning; results are format- and thermal-state-specific; [issue #387](https://github.com/JustVugg/colibri/issues/387) |
| M5 Max 128 GB, current documented GLM int4-g64 | 0.27-0.32 tok/s | Metal's routed-expert path rejects fmt=4, leaving experts on CPU; [issue #813](https://github.com/JustVugg/colibri/issues/813) |
| M5 Max 128 GB, GLM E8/IQ3 fmt=6, `MTP=0`, explicit cache | 0.87 tok/s warm | best verified current-format workaround; Metal experts engage, but CPU attention becomes dominant; [issue #813 comment](https://github.com/JustVugg/colibri/issues/813#issuecomment-5193325122) |
| M3 Ultra 512 GB, fully resident GLM int4-g64 | 1.36 tok/s tuned versus llama.cpp 15.1 tok/s | confirms the fmt=4 Metal dispatch gap; [issue #813](https://github.com/JustVugg/colibri/issues/813) |

Colibri's own API guide warns that 10-20k-token coding-agent preambles can take
about an hour before first output and that iterative disk-streaming agent loops
are generally not worth the wait. Graphify is not an interactive coding agent,
but its default 60k-token semantic chunks are larger still. See
[`docs/api.md`](https://github.com/JustVugg/colibri/blob/8f512fc8c2f48ffa18cd624cd4a5bcaae4a4abfc/docs/api.md#L175-L192).

The target M2 Max 96 GB lies between published 32 GB and 128 GB Max results, but
throughput must not be linearly interpolated: expert residency, format support,
OS page cache, MTP, Metal dispatch, and SSD state change the regime. A real-host
canary is required for any rate claim.

## Decision matrix

| Candidate | Graphify 0.9.39 API fit | Context fit | Structured JSON assistance | Target-host practicality | Quality evidence | Decision |
|---|---|---|---|---|---|---|
| v1.5.0 + OLMoE | **No server path** | hard 4,096 in engine | none | excellent size | none for Graphify deep extraction | **Reject** |
| `dev` @ `2c8ce27` + OLMoE | OpenAI route works | **fails defaults**; only viable with very small chunks and output cap | gateway rejects grammar | excellent size; sequential full re-prefill | none | **Canary only** |
| v1.5.0 + GLM int4-g64 | API works | configurable | grammar available but Graphify does not send it by default | 372 GB; current Metal expert path does not support fmt=4 | model is capable, extraction unmeasured | **Reject** |
| v1.5.0 + GLM E8/IQ3 fmt=6 | API works | configurable; use 32k or lower on this host | grammar available through a custom provider | roughly 280 GB and 0.87 tok/s on a faster 128 GB M5 Max | extraction unmeasured | **Technically viable, operationally poor** |
| v1.5.0 + DeepSeek V4 | API works | default 4,096; configurable | grammar/tools rejected | 167 GB; extremely slow measured path | extraction unmeasured | **Reject** |
| v1.5.0 + Inkling | API works | default 8,192 | grammar rejected | 469 GB; tens of seconds/token in low-RAM mode | extraction unmeasured | **Reject** |
| v1.5.0 + Kimi K3 | API works | default 8,192 | grammar rejected | 1.6 TB | extraction unmeasured | **Reject** |
| open PR #544 Qwen3-30B-A3B | no `coli`/serve integration yet | not deployment-ready | none established | promising 30B/3B-active architecture | token-exact engine fixture only | **Watch, do not adopt** |

## Bounded canary, if explicitly approved

The only proportionate experiment is OLMoE on the unreleased development commit,
because it avoids a hundreds-of-gigabytes download. It must be gated as follows:

1. Pin exact commit `2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b`, not moving `dev`.
2. Build OLMoE and convert `allenai/OLMoE-1B-7B-0125-Instruct`; run `coli
   doctor --deep` before serving.
3. Serve with one generation at a time, 4,096 context, and a 1,024-token output
   ceiling.
4. Point a Graphify custom provider at `http://127.0.0.1:8000/v1`; do not add
   `response_format`, which OLMoE rejects.
5. Run Graphify with `--mode deep --token-budget 1000 --max-concurrency 1`,
   `GRAPHIFY_MAX_OUTPUT_TOKENS=1024`, and an explicit API timeout.
6. Use a small frozen prose fixture with a Claude-derived expected graph and
   score node/edge recall, rationale capture, source/evidence binding, invalid
   JSON rate, truncation/retry rate, and wall time. Include a no-server negative
   control so fallback or accidental cloud routing cannot pass.

Passing this canary would establish only that the small model can perform the
fixture under constrained chunks. It would not establish full-corpus quality or
justify changing the knowledge-base backend invariant.

## Final recommendation

Keep Colibri rejected for Graphify 0.9.39 production deep extraction.

- **Correct the old reason:** the earlier experiment was fake inference, not a
  model defeat.
- **Do not use stable OLMoE:** v1.5.0 cannot serve it.
- **Do not use large Colibri models for routine extraction:** the storage and
  observed Apple-Silicon throughput make them operationally disproportionate.
- **Allow one OLMoE canary only if local-token elimination remains a priority:**
  it is the sole low-cost way to answer the currently missing quality question.
- **Revisit after a release includes OLMoE serve plus a context-window increase,
  or after Qwen3-30B-A3B gains released launcher/server integration and an
  Apple-Silicon extraction benchmark.**

## Verification gaps

- No real Colibri weights are installed on the target host, so this pass did not
  execute inference.
- No primary M2 Max 96 GB Colibri benchmark exists.
- No primary Colibri-model benchmark covers Graphify 0.9.39 deep extraction
  fidelity.
- OLMoE serve is unreleased and may change before the next tag.
- Colibri's README currently describes a uniform OLMoE server surface that the
  latest release does not contain; source and merged-PR history take precedence.

These gaps are exactly why the recommendation is reject-for-adoption and
canary-for-learning, rather than a categorical claim that Colibri can never be
made viable.


## Source Nodes

- colibri.c
- olmoe.c
- graphify