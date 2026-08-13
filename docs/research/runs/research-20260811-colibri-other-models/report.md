# Colibri non-OLMoE models for Graphify 0.9.39

**Date:** 2026-08-11

**Colibri source:** development commit [`2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b`](https://github.com/JustVugg/colibri/tree/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b)

**Host in scope:** Apple M2 Max (`Mac14,6`), 96 GiB unified memory, previously measured 715 GiB free storage

**Graphify:** 0.9.39, commit [`50556baaea803e191947fdfcc2e0c22e2d4eb74d`](https://github.com/Graphify-Labs/graphify/tree/50556baaea803e191947fdfcc2e0c22e2d4eb74d)

## Decision

**GLM-5.2 is the only non-OLMoE Colibri model that should receive a real
Graphify deep-extraction canary on this Mac.** It is the only candidate that
combines host-feasible storage and RAM with Colibri's mature OpenAI server,
multi-slot KV, tool, grammar, and Apple Metal code paths.

That is a recommendation to test, not a performance claim. No GLM weights have
been downloaded and no GLM inference has been measured on this M2 Max. The
current quality-recommended checkpoint is nearly 400 GiB, and its grouped-int4
format does not have the fully supported Metal routed-expert path used by the
published Apple benchmarks. Start with CPU and a small Graphify fixture; treat
Metal as a separate format/quality experiment.

Inkling is technically capacity-feasible only after its lossy dense-int4
conversion, but published Colibri measurements show poor novel-prompt
throughput. DeepSeek V4 Flash is not a supported macOS target. Kimi K3 exceeds
this host's available storage by roughly 2x.

## Evidence boundary

- **Measured locally:** host identity, 96 GiB memory, 715 GiB free storage,
  Graphify version, and the pinned Colibri Git commit. No non-OLMoE weights,
  conversion, server startup, or inference were run.
- **Exact current metadata:** Hugging Face repository SHAs and byte totals below
  came from each repository's first-party API with blob metadata on 2026-08-11.
- **Upstream measured:** throughput figures explicitly attributed to Colibri
  documentation were measured by its maintainers/community on other hardware.
- **Inferred:** host feasibility combines the exact repository bytes, declared
  runtime memory guidance, and measured host capacity. It is not an inference
  benchmark.

## Inventory

| Rank | Colibri family | Exact checkpoint | License | Total / active | Owner context | Current download | M2 Max 96 GiB verdict |
|---:|---|---|---|---:|---:|---:|---|
| 1 | GLM-5.2 | [`mastouri/GLM-5.2-colibri-int4-g64-with-int8-mtp@fd9b461`](https://huggingface.co/mastouri/GLM-5.2-colibri-int4-g64-with-int8-mtp/tree/fd9b461ac7cae4b921470d0db12230c6505bd03c) | MIT, inherited from Z.ai | 744B / ~40B | 1,048,576 | 429,276,218,793 B = 399.77 GiB | **Canary candidate; untested locally** |
| 2 | Inkling | [`nbeerbower/Inkling-colibri-int4@3981e65`](https://huggingface.co/nbeerbower/Inkling-colibri-int4/tree/3981e658ed68ec681554d48a62f9a29dd9e61543) | Apache-2.0 | 975B / 41B | 1,048,576 | 514,051,941,362 B = 478.75 GiB | Fits only with dense-int4 sidecar; too slow to prioritize |
| 3 | DeepSeek V4 Flash | [`deepseek-ai/DeepSeek-V4-Flash-0731@7872f01`](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731/tree/7872f01b1d1fe23eabc4c98b48bffcef5a386062) | MIT | 284B / 13B | 1,048,576 | 166,898,661,074 B = 155.44 GiB | Storage/RAM fit, but Colibri does not support macOS |
| 4 | Kimi K3 | [`moonshotai/Kimi-K3@9f62e4e`](https://huggingface.co/moonshotai/Kimi-K3/tree/9f62e4e9fffbd0a83ddd60e1c209d828994b3569) | Custom Kimi K3 License | 2.8T / 104B | 1,048,576 | 1,560,998,984,390 B = 1.420 TiB | **Impossible with current free storage** |

The sizes above include repository metadata and all repository files. Weight
payloads alone are respectively 429,255,863,080 B, 514,024,040,328 B,
166,886,535,336 B, and 1,560,936,091,448 B.

## 1. GLM-5.2

### Checkpoint and format

Colibri identifies GLM-5.2 as its reference 744B MoE, with roughly 40B active
parameters. The official [`zai-org/GLM-5.2`](https://huggingface.co/zai-org/GLM-5.2)
checkpoint is MIT-licensed BF16 and currently totals 1,506,693,036,946 bytes.
Colibri recommends the preconverted `mastouri` **int4-g64** container with an
**int8 MTP head**, avoiding an extra conversion and the simultaneous source plus
destination footprint.

The Colibri README still says "about 372 GB". The current first-party repository
API reports 429.28 GB decimal (399.77 GiB), so capacity decisions must use the
API total, not the prose estimate. This host has enough free space for one copy,
but not much room for a second full-format conversion.

The official and converted configs both declare 78 layers, 256 routed experts,
top-8 routing, and `max_position_embeddings=1048576`. Colibri serving defaults
to `CTX=4096`; GLM's `--ctx` wrapper path correctly propagates `CTX`, so a
bounded Graphify canary can explicitly choose its prompt/output envelope.

### Runtime and server maturity

- Build: `make -C c glm`; `coli` routes unrecognized/`glm_moe_dsa` configs to
  `c/colibri`.
- RAM guidance: 16 GB minimum, 24 GB comfortable. The engine keeps roughly
  9.9 GB of dense weights resident and uses remaining RAM as expert cache.
- Server: the reference and most mature family. It supports OpenAI chat and
  completions, bounded FIFO scheduling, up to 16 gateway KV slots, persistent
  contexts, model-owned stop handling, tool calls, and GLM-only grammar/schema
  drafting. Graphify 0.9.39 does not request grammar-constrained decoding, so
  JSON correctness must still be measured end to end.
- Apple: the experimental Metal backend is GLM-focused. Colibri reports 1.50
  tok/s on a 128 GB M1 Ultra and 2.06 tok/s on a 128 GB M5 Max, not this host.
  Those runs used per-row fmt2 weights.

### Known defects and caveats

- Colibri warns that older per-row int4 mirrors cost about nine percentage
  points of quality and caused the think loops/nonterminating behavior tracked
  in [issue #455](https://github.com/JustVugg/colibri/issues/455). Use g64.
- An int4 MTP head produced 0% draft acceptance
  ([issue #8](https://github.com/JustVugg/colibri/issues/8)); use the recommended
  int8 MTP head or disable MTP for the first canary.
- The Apple reports say fmt2 is a Metal-compatibility vehicle, not the quality
  recommendation; grouped g64 Metal dispatch remains associated with
  [issues #585](https://github.com/JustVugg/colibri/issues/585) and
  [#587](https://github.com/JustVugg/colibri/issues/587).
- Metal prefill changes accumulation order and can flip near-tie top tokens;
  Colibri documents CPU fallback for exact parity
  ([issue #622](https://github.com/JustVugg/colibri/issues/622)).

### Feasibility

Capacity is green; local throughput and extraction quality are untested. The
first canary should use g64, CPU, MTP off, one KV slot, Graphify concurrency 1,
a small token budget, and a real fixture with known semantic relationships.
Only after a correct result should Metal or a larger fixture be attempted.

## 2. Inkling

### Checkpoint and format

Thinking Machines' [`Inkling`](https://huggingface.co/thinkingmachines/Inkling)
is Apache-2.0, 975B total/41B active, 66 layers, 256 routed experts, top-6 plus
two shared experts, and a declared one-million-token context. The original BF16
repository at `828496ee...` is 1,904,787,129,293 bytes.

Colibri targets `nbeerbower/Inkling-colibri-int4`: int4 routed experts plus BF16
resident weights. The current repository is 478.75 GiB. Colibri does not load
the vision encoder or MTP head. The BF16 dense set is measured at 49.4 GB and
expands to about 99 GB while loading, making the unmodified CPU path unsafe on
this 96 GiB host.

`convert_inkling_dense_int4.py` creates an additional 15.3 GB int4-gs64 dense
sidecar and preserves the originals. That makes runtime memory feasible but
adds storage and introduces about 11% relative-L2 error for attention/shared
expert/dense-MLP tensors. Embed/lm-head stay int8 at about 0.9% error.

### Runtime and server maturity

- Build: pure CPU or CUDA. The Inkling documentation does not claim a supported
  Apple Metal execution path.
- RAM: about 120 GB without the dense sidecar; about 25 GB minimum with it.
  Each expert cache slot is about 28 MB per layer.
- Server: arch-aware Inkling chat template, streaming/nonstreaming OpenAI chat,
  text and optional audio. The shared gateway enforces one KV slot for non-GLM
  engines and rejects tool calls/grammar.
- Context: upstream one million; Colibri serving defaults to `CTX_MAX=8192`.
  At this commit `coli serve --ctx` does not translate to Inkling's `CTX_MAX`,
  so a larger explicit context requires the environment variable directly.

### Performance and feasibility

Colibri's published 187 GB DDR5 + RTX A6000 measurements report 0.17 tok/s on
a novel prompt with overfit pins and 0.25 tok/s steady-state after diverse
warming. On a 25 GB host it warns of tens of seconds per token. A 96 GiB cache
would help, but there is no same-Mac measurement and no reason to spend a
478.75 GiB download before testing GLM's much more mature path.

## 3. DeepSeek V4 Flash

Colibri's pinned documentation names
`deepseek-ai/DeepSeek-V4-Flash-0731`, not the separate unsuffixed repository.
The 0731 checkpoint is MIT, 284B/13B active, 43 layers, 256 routed experts,
top-6, and a one-million-token owner context. It needs no conversion: routed
experts remain native FP4 and dense tensors FP8 E4M3 with UE8M0 scales.

The current exact download is 155.44 GiB. Colibri documents about 6.27 GiB of
dense tensors, a 1.06 GiB resident BF16 output head, 16 GB minimum RAM and 22
GB comfortable. This Mac easily meets those capacities.

It is nevertheless not a candidate: the source documentation explicitly lists
x86-64/aarch64 **Linux and Windows/MSYS2**, not macOS. Server maturity is also
behind GLM: greedy decoding, exactly one KV slot, full request re-prefill, and
explicit rejection of tools and grammar. Colibri defaults to `CTX=4096`; its
wrapper does propagate `--ctx` for this family. DSpark/MTP are implemented but
off because a real multi-turn run showed rejected-state replay dominating and
a 14-token answer taking 495 seconds.

Do not substitute [`DeepSeek-V4-Flash@60d8d70`](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash/tree/60d8d70770c6776ff598c94bb586a859a38244f1)
without compatibility work: it is a different 46-shard repository, while the
pinned Colibri documentation and validation target the 48-shard 0731 model.

## 4. Kimi K3

Moonshot's [`Kimi-K3`](https://huggingface.co/moonshotai/Kimi-K3) uses a custom
Kimi K3 License. The model card declares 2.8T total/104B active, 93 layers, 896
experts, top-16 plus two shared experts, native MXFP4 weights/MXFP8 activations,
and a one-million-token context.

The original checkpoint is also the Colibri runtime checkpoint: routed experts
stay byte-identical native MXFP4, while BF16 dense tensors are quantized at
load. The exact repository is 1.420 TiB, more than double this host's free
storage. Colibri's optional repack remains about 1.50 TB decimal at int8 or
1.48 TB at int4 and requires source plus destination during conversion, so it
does not solve capacity.

Kimi support is CPU plus optional Vulkan, explicitly no CUDA/Metal. Serving
supports its native XTML chat template and streaming/nonstreaming OpenAI chat,
but one KV slot and no gateway tools or image content. Upstream declares one
million tokens; Colibri serving defaults to `K3_MAXT=8192`, and `--ctx` is not
translated to `K3_MAXT` at this commit. Flat quantile-balanced routing also
limits cache effectiveness; Colibri reports about 9.4 seconds/token after
direct-I/O optimization on its measured system.

Kimi is rejected by hard storage capacity before performance or Graphify
quality is considered.

## Recommendation: exact next canary

Use the quality-recommended GLM-5.2 g64/int8-MTP repository at the exact SHA
above. Do not start with an Apple fmt2 conversion merely to reproduce a Metal
number: that changes the quality variable the Graphify experiment is meant to
measure.

The acceptance sequence should be:

1. Verify the repository's current 399.77 GiB requirement and preserve at least
   conversion/log/output headroom.
2. Run `coli doctor --deep` before loading.
3. Start CPU-only, `MTP=0`, one KV slot, short explicit `CTX`, output cap at or
   below 1024, and Graphify concurrency 1.
4. Run the same small real-code fixture and semantic assertions used for the
   OLMoE canary. Require valid JSON, no dropped semantic chunks, nonzero
   `INFERRED` edges, and manual correctness review.
5. Record prompt tokens, completion tokens, prefill time, decode tok/s, peak
   RSS, and wall time. A successful transport response is not a quality pass.
6. Only then compare CPU with a separately identified Metal-compatible format;
   do not conflate format loss with backend speed.

## Primary sources

- Colibri: [README](https://github.com/JustVugg/colibri/blob/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b/README.md), [API](https://github.com/JustVugg/colibri/blob/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b/docs/api.md), [Metal](https://github.com/JustVugg/colibri/blob/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b/docs/metal.md), [Inkling](https://github.com/JustVugg/colibri/blob/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b/docs/inkling.md), [Kimi K3](https://github.com/JustVugg/colibri/blob/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b/docs/kimi_k3.md), [DeepSeek V4](https://github.com/JustVugg/colibri/blob/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b/docs/deepseek-v4.md), [`coli`](https://github.com/JustVugg/colibri/blob/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b/c/coli), and [gateway](https://github.com/JustVugg/colibri/blob/2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b/c/openai_server.py).
- Model owners: [GLM-5.2](https://huggingface.co/zai-org/GLM-5.2), [Inkling](https://huggingface.co/thinkingmachines/Inkling), [Kimi K3](https://huggingface.co/moonshotai/Kimi-K3), and [DeepSeek V4 Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash).
- Exact current runtime repositories and revisions are linked in the inventory
  table. Their Hugging Face first-party API blob metadata is the source of the
  byte totals.
