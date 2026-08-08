# Colibri local-LLM evaluation — does it remove the graphify agent-work token cost?

**Date**: 2026-08-07 · **Session**: 2026-08-07-h · **Branch**: `feat/colibri-local-llm-source`
**Question asked** (Ray, at the `-g` clear-prep): colibri runs a model locally and free —
does that let us stop worrying about token usage in the graphify agent work?

**Answer: not as `/Users/rmanaloto/agy-graphify-research` implements it — that pipeline
never invoked an LLM at all. But the underlying idea is sound and has a much shorter
path than that repo takes, because graphify already supports it natively.**

---

## 1 — The decisive finding: the "5-model bake-off" never ran a model

`/Users/rmanaloto/agy-graphify-research/docs/colibri_v1_5_model_grading_report.md`
grades five colibri models and reports each at **110 nodes, 90 edges, 75.68/100**.
Five models spanning **7B to 2.8T parameters** scoring identically to two decimal
places is not a result; it is a signature.

### The control arm

`graphify-out/models/<model>/` holds each arm's output. Comparing them directly:

| artifact | glm-5.2 | olmoe-7b | verdict |
|---|---|---|---|
| `graph.json` | `d5c79da7677ee5d20dc49687dbfad668` | `d5c79da7677ee5d20dc49687dbfad668` | **identical** |
| `cypher.txt` | `02672dc2cf56a8a05b9dc3b8f5008975` | `02672dc2cf56a8a05b9dc3b8f5008975` | **identical** |
| `graph.graphml` | `eebbd1dcbc51201489759cff220d297f` | `eebbd1dcbc51201489759cff220d297f` | **identical** |
| `GRAPH_REPORT.md` | `773a1a7b…` | `0cb57751…` | differs |

All five models produce byte-identical graphs. `GRAPH_REPORT.md` is the only
file that differs, and the entire diff is **four lines**:

```
1c1
< # Graph Report - colibri-glm-5.2  (2026-08-06)
---
> # Graph Report - colibri-olmoe-7b  (2026-08-06)
```

The title echoing the model name back. Nothing else in the pipeline saw a model.

### Corroborating evidence, all independent of the md5s

- **Latency 0.027–0.043 s** per whole-repo extraction. No local inference of any
  size runs in 27 ms; that is regex speed.
- **`inferred_edges: 0, rationale_edges: 0, similar_edges: 0`** in
  `benchmark_summary.json` for every arm. The semantic layer — the only thing an
  LLM would contribute — is empty in all five.
- **No model weights exist on this machine.** `find ~ -name '*.gguf'` → 0 hits;
  the only match for `*colibri*model*` is the grading report itself.
- **Nothing was listening on port 8080** (`lsof -nP -iTCP:8080 -sTCP:LISTEN` → empty).
- **`~/.graphify/config.json` does not exist**, so `ColibriConfig` fell back to its
  dataclass defaults, where `model_path = ""`. The auto-launch path would have
  invoked `python3 openai_server.py --port 8080` with no `--model` argument.

### The mechanism

`src/agy_graphify/colibri_extractor.py:113`:

```python
async def call_colibri_api(self, prompt: str) -> dict[str, Any]:
    if not self.is_server_running():
        logger.info("Colibri HTTP server offline - returning heuristic graph payload.")
        return self._fallback_heuristic_extraction(prompt)
```

`_fallback_heuristic_extraction` (`:143-210`) is a ~65-line scanner that walks the
prompt's lines looking for `startswith(("class ", "def ", "async def "))` and
`startswith(("# ", "## ", "### "))`, emitting `defines_symbol` and
`contains_section` edges. That is the entire "knowledge graph".

Two further bounds compound it:

- it parses **the prompt**, and the prompt truncates file content to
  `content[:4000]` (`:104`) — anything past ~4 KB of a file is invisible;
- `extract_directory` caps the run at **`files[:20]`** (`:267`, comment: *"Limit
  batch for safety"*). 110 nodes across a whole repo is that cap, not a corpus.

**The fallback is silent and returns success.** `logger.info`, not `warning`; no
non-zero exit; the report renders. This is `a-task-that-exits-0-passes-every-check`
and `loss-happens-past-the-gate` in one artifact — the repo's own 124/124 test
suite and `agy-verify: allow` are all green over it, because none of them asks
whether an LLM was reached.

## 2 — Colibri itself is real; the integration is what failed

This must not be read as "colibri doesn't work". Querying our own graph
(colibri v1.5.0 was ingested this branch, 3,997 nodes) returns a genuine
C/Metal MoE inference engine: `expert_load_impl()`, `spec_decode()`,
`run_serve()`, `run_serve_mux()`, `mux_submit()`, `qt_from_disk()`, plus
`quant.h`, `tok.h`, `grammar.h`, `route_trace.h`. The five "model names" in
`SUPPORTED_COLIBRI_MODELS` are colibri's supported **architectures**, each with
its own translation unit — `inkling.c`, `olmoe.c` appear as distinct communities.

The failure is entirely in `agy-graphify-research`'s wrapper, which never had
weights to load and degraded silently instead of saying so.

## 3 — The short path the research repo missed

Colibri ships `c/openai_server.py` — an **OpenAI-compatible** HTTP server,
default port 8080. graphify's own `--help` (`__main__.py:598`) says:

```
vLLM, LM Studio): set OPENAI_BASE_URL (e.g. http://localhost:8080/v1)
```

and `llm.py:150` names the same family — *"(llama.cpp, vLLM, LM Studio, ...)"*.
graphify's `openai` backend already speaks to any OpenAI-compatible local
endpoint. The research repo's `ColibriExtractor` is a from-scratch
reimplementation of a path graphify has had since 0.8.40
(`use-tool-builtins.md` — and the reimplementation is strictly worse: no AST, a
4 KB truncation, a 20-file cap, and a silent no-LLM fallback graphify does not have).

**So the viable shape is: run colibri's `openai_server.py`, point
`OPENAI_BASE_URL` at it, and let graphify's existing backend do the work. No
new extractor code.**

## 4 — Why that is an INVARIANT change, not a config change

`do-not.md` #4 and `kb_setup.graphify_env.clean_env()` strip every non-Claude
backend trigger from every graphify subprocess. `OPENAI_API_KEY` is in
`_STRIP_BACKEND_ENV` (`graphify_env.py:42`), so `detect_backend()` cannot select
`openai` today, and enabling colibri means deliberately passing a backend
trigger through `extra=`.

One detail worth recording: **`OPENAI_BASE_URL` is not itself in the strip list**
— only `OPENAI_API_KEY` is. That is not a hole: `detect_backend()` selects
`openai` on the *key*, so a stray base URL alone changes nothing. The invariant
fails closed. But it does mean the invariant currently rests on one name, and
any change here should say so explicitly.

**This is a decision for Ray, not a config edit an agent should make.**

## 5 — What it would and would not save

The token cost being targeted is **host-agent prose extraction** — the
`kb-extract` Workflow fan-out. Scope check against what the corpus actually is:

- **AST extraction is already free.** `kb-build` clones at the pinned SHA and
  parses locally, no LLM, for every `sources/*.manifest`. The colibri source
  (3,997 nodes) cost zero tokens to ingest. Nothing to save there.
- **`kb-label` is already free** — deterministic hub labels, no LLM.
- The **only** paid path is semantic extraction of prose/media. That is where a
  local model would substitute, and it is the path with the highest quality
  sensitivity in the corpus.

So the ceiling on the saving is "the prose extraction budget", and the price is
substituting an unmeasured local model for Claude on the one path where
extraction quality determines what every future session can retrieve. Given
memory record `newer-is-not-richer` (2 of 6 re-extractions were regressions, and
a successful merge ships a regression silently), that trade needs a measured
arm before it is taken — not the one the research repo produced.

## 6 — Recommendation

1. **Do not adopt `agy-graphify-research`'s pipeline or its grading report.** The
   report's numbers are an artifact of a silent fallback and should not be
   carried into any decision here (`probes-need-a-control-arm.md` rule 6 — an
   inherited number is not a measurement).
2. **Keep the colibri source pin** (`sources/colibri.manifest` @ v1.5.0). It cost
   nothing, it is real, and it is what let this evaluation query the engine
   rather than guess at it.
3. **If the local-LLM path is pursued**, do it as `OPENAI_BASE_URL` → colibri's
   `openai_server.py` against graphify's existing `openai` backend, with real
   weights present, and *first* prove the server answers — the single control arm
   the research repo never ran. Treat it as an amendment to `do-not.md` #4.
4. **Before any of that**, measure the thing being optimised: what the prose
   extraction path actually costs per round. The saving may be smaller than the
   quality risk.

## GitHub repos touched

- [JustVugg/colibri](https://github.com/JustVugg/colibri) — the local inference engine
  under evaluation; already pinned at v1.5.0 in `sources/colibri.manifest`.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — read the
  installed 0.9.35 `llm.py` / `__main__.py` for native local-endpoint support, and
  the v0.9.36 release notes.
