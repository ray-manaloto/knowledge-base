# colibri hardware preflight / capability planning — does it exist?

**Date:** 2026-08-07
**Question:** Does colibri (or its tooling) provide a way to check this Mac's
hardware and decide whether a given model can be run, or is worth downloading?
**Sources:** PRIMARY ONLY — the pinned colibri **v1.5.0** clone at
`sources/colibri/` (gitignored, re-cloned from `sources/colibri.manifest`) plus
this repo's knowledge graph. No blog posts, no secondary write-ups.

All `file:line` citations below are relative to
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/colibri/`.

---

## Headline answer

**Yes — but it is a POST-download tool, not a pre-download one.**

| Question | Answer |
|---|---|
| Is there a hardware-aware planner? | **YES** — `coli plan`, implemented in `c/resource_plan.py` (749 lines) |
| Is there a readiness/preflight diagnostic? | **YES** — `coli doctor` (`c/doctor.py`, 594 lines), with `--deep` |
| Does it detect RAM / cores / disk on macOS? | **YES** — verified by running it on this machine (below) |
| Does it detect the M2 Max GPU? | **NO** — `discover_gpus()` is NVIDIA-then-AMD only; returns `[]` here |
| Can it tell me, *before downloading*, which models fit? | **NO** — every path calls `analyze_model()`, which requires the weights already on disk |
| Does anything read the README's per-model disk/RAM table programmatically? | **NO** — it is docs-only |

So: **given 96 GB RAM and ~481 GB free, there is no colibri command that will
list which models are runnable.** The closest thing is
`python3 tools/download_glm52.py --check` (GLM-5.2 only, disk-only). A ~10-line
wrapper closing the gap is specced at the end.

---

## 1. Method — the graph first (house rule)

Orientation was done with graphify before any grep, per this repo's
`PreToolUse` mandate.

1. `mise run kb-query -- "hardware aware planner RAM VRAM budget detection"` →
   rc=0, `850 nodes found`, truncated to 62 by the ~2000-token budget. The
   aggregate graph spans every source, so most hits were noise
   (`codex-rs/**`, `backend/app/channels/**`, `skillopt_sleep/**`). One hit was
   colibri's: `NODE .test_cuda_dense_uses_vram() [src=c/tests/test_inefficiency.py]`.
2. The decisive orientation was `graphify explain "resource_plan.py"` (read-only,
   allowed direct). It returned the whole planner in one shot:

```
Node: resource_plan.py
  ID:        colibri::c_resource_plan
  Source:    c/resource_plan.py L1
  Community: build_plan          Degree: 22
  --> build_plan()          c/resource_plan.py:L523
  --> analyze_model()       c/resource_plan.py:L37
  --> memory_available()    c/resource_plan.py:L79
  --> discover_gpus()       c/resource_plan.py:L230
  --> physical_cpu_count()  c/resource_plan.py:L329
  --> cpu_socket_count()    c/resource_plan.py:L443
  --> _auto_tune()          c/resource_plan.py:L459
  --> environment_for_plan() c/resource_plan.py:L663
  --> format_plan()         c/resource_plan.py:L711
  --> ssd_probe_state()     c/resource_plan.py:L180
  <-- c/doctor.py            [imports_from] c/doctor.py:L11
  <-- c/tests/test_resource_plan.py [imports_from]
  <-- c/tests/test_doctor.py [imports_from]
```

Everything below verifies that map against the source bytes.

---

## 2. What EXISTS

### 2.1 `coli` is a Python launcher with 11 subcommands

`c/coli` is **not** a compiled binary despite the exec bit —
`file c/coli` → `Python script text executable, Unicode text, UTF-8 text`.
Its docstring (`c/coli:1-16`) is the authoritative subcommand list:

```
c/coli:5    coli chat                 interactive chat (loads the model once)
c/coli:6    coli serve                OpenAI-compatible HTTP API (persistent engine)
c/coli:7    coli run "prompt"         one-shot generation
c/coli:9    coli info                 model, RAM, disk, and configuration status
c/coli:10   coli plan                 Disk / RAM / VRAM resource plan
c/coli:11   coli mirror               Plan, stage, or verify a learned partial mirror
c/coli:12   coli doctor               installation and execution-plan diagnostics
c/coli:13   coli bench [task...]      quality benchmarks (MMLU/HellaSwag/...)
c/coli:14   coli convert              convert GLM-5.2-FP8 to int4, one shard at a time
c/coli:15   coli build                build the engine
```

Dispatch table: `c/coli:1412-1413`
(`{"build":cmd_build,"info":cmd_info,"plan":cmd_plan,"mirror":cmd_mirror,"doctor":cmd_doctor,"tune":cmd_tune,…}`).
Subparsers registered at `c/coli:1338-1349`.

So the lead "`coli info` prints engine ready ✓" is confirmed
(`c/coli:713`: `row("engine", "ready ✓" if os.path.exists(GLM) else "not built (coli build)")`)
— **and `plan` / `doctor` / `mirror` are the three that actually answer the
hardware question.**

### 2.2 `coli plan` — the hardware-aware planner (README:122 lead, RESOLVED)

The README claim at **README.md:122**:

> | A hardware-aware planner can approach each machine's best configuration
> automatically | RAM/VRAM budgets and several backends are detected today |
> compare the generated plan with a controlled parameter sweep … |

is implemented by `build_plan()` at **c/resource_plan.py:523**. Confirmed
consumers:

- `c/coli:722-738` — `cmd_plan()`; `from resource_plan import build_plan, format_plan`,
  `plan=build_plan(a.model,ram,ctx,devices,vram,policy=a.policy)`; `--json` dumps
  the raw dict (`c/coli:734`).
- `c/coli:415,427` — `cmd_chat`/run path applies the plan via
  `environment_for_plan()` when `--auto-tier` is passed (`c/coli:1316`).
- `c/doctor.py:11,487` — doctor builds the same plan.
- `c/coli:778-781` — `cmd_tune` builds it too.

**Docs cross-check** (`docs/quickstart.md:190-191`):

```
COLI_MODEL=/nvme/glm52_i4 ./coli doctor   # read-only check: is everything ready?
COLI_MODEL=/nvme/glm52_i4 ./coli plan     # shows where the model will live (RAM/disk/GPU)
```

and `README.md:546`:
`├── resource_plan.py      RAM/VRAM planner behind `coli plan` and `coli doctor``.

### 2.3 What the planner actually detects

| Fact | Function | Line | macOS mechanism |
|---|---|---|---|
| Available RAM | `memory_available()` | `c/resource_plan.py:79` | `vm_stat` reclaimable pages (`:126-135`), falling back to `sysctl -n hw.memsize` (`:137`) |
| Physical cores | `physical_cpu_count()` | `:329` | `sysctl -n hw.physicalcpu` (`:367-374`) |
| CPU sockets | `cpu_socket_count()` | `:443` | — |
| Free disk | inline in `build_plan` | `:534-535` | `shutil.disk_usage(info["path"]).free`, `500 GB` fallback on `OSError` (`:537`) |
| GPUs / VRAM | `discover_gpus()` | `:230` | **NVIDIA `nvidia-smi` then AMD ROCm only** (`:232-236`) |
| SSD speed | `ssd_probe_state()` | `:180` | reads a **cached** `.coli_ssd` F_NOCACHE measurement the C engine wrote; never re-measured here (`:654-657`) |
| Model geometry | `analyze_model()` | `:37` | parses **every safetensors header** on disk + `config.json` |

### 2.4 Live evidence — it runs correctly on this Mac

Exact command run from `sources/colibri/c/`:

```
python3 -c "
import sys, shutil; sys.path.insert(0,'.')
import resource_plan as rp
print('memory_available =', round(rp.memory_available()/1e9,1), 'GB')
print('physical_cpu_count =', rp.physical_cpu_count())
print('cpu_socket_count =', rp.cpu_socket_count())
print('discover_gpus =', rp.discover_gpus())
print('disk free (cwd) =', round(shutil.disk_usage('.').free/1e9,1), 'GB')
"
```

Output:

```
memory_available = 27.8 GB
physical_cpu_count = 12
cpu_socket_count = 1
discover_gpus = []
disk free (cwd) = 516.3 GB
```

Three things this proves, all of them load-bearing:

1. **The detection primitives work on Darwin.** Cores (12) and disk (516 GB) are
   correct. This is the control arm for every negative below: the module imports
   and executes here, so a `[]` from `discover_gpus()` is an *answer*, not a
   failure to ask.
2. **`memory_available()` returns 27.8 GB, not 96 GB.** By design — the darwin
   branch sums only `Pages free + inactive + speculative + purgeable`
   (`c/resource_plan.py:128-131`), i.e. *reclaimable without swapping*, matching
   the C engine's `compat_meminfo`. `build_plan` then takes
   `int(available_memory * 0.88)` (`:546`) → a RAM budget of roughly **24 GB, not
   84 GB**, on a 96 GB machine. **Practical consequence: always pass `--ram 80`
   (or `COLI_RAM`) on this Mac**, or the plan will size the warm expert cache
   from whatever was momentarily free and badly under-use the box. The override
   is honoured at `:546` (`ram_gb * GB if ram_gb > 0`).
3. **The M2 Max GPU is invisible to the planner** — see §3.2.

### 2.5 `coli doctor` — the readiness gate, and the closest thing to a verdict

`run_doctor()` at `c/doctor.py:406` emits these check ids (grep of `_check("`):

`model.path` · `model.config` · `model.tokenizer` · `storage.persistence` ·
`engine.binary` · `accelerator.cuda` · `model.shards` · `storage.disk` ·
`memory.ram` · `placement.plan` · `storage.ssd_probe`, plus `model.index`,
`storage.mirror`, `model.container` under `--deep` (`c/doctor.py:557-573`).

The two that answer "can this machine run it":

```python
c/doctor.py:494   disk_status = "warn" if disk["available_bytes"] < GB else "pass"
c/doctor.py:500-506
        if not available_memory:
            ram_status, ram_summary = "warn", "available RAM could not be measured"
        elif ram["budget_bytes"] > available_memory:
            ram_status, ram_summary = "fail", "planned RAM budget exceeds available memory"
        elif ram["cache_slots_per_layer"] < 1:
            ram_status, ram_summary = "fail", "RAM budget cannot hold one expert slot per sparse layer"
        else:
            ram_status, ram_summary = "pass", "RAM budget is viable"
```

`exit_code()` (`c/doctor.py:593`) returns `1` only when
`report["status"] == "error"`. `--json` is supported (`c/coli:755,765`).

**Note the `storage.disk` threshold is 1 GB, not "does the model fit".** It
checks free space for *runtime state*, and it runs against a model directory
that already contains the weights. It is not a download-sizing check.

### 2.6 `coli mirror plan` — real free-space arithmetic, still post-download

`c/tools/mirror_plan.py` does projected-free-space reasoning:

```
c/tools/mirror_plan.py:213  free = shutil.disk_usage(existing_parent(mirror)).free
c/tools/mirror_plan.py:222-223  elif free - remaining < reserve:  reason = "free_space_reserve"
c/tools/mirror_plan.py:236-239  "free_bytes": free, "projected_free_bytes": free - remaining
```

Invoked from `c/coli:1296` (`mirror_plan.py <action>`), actions
`plan|stage|verify` (`c/coli:1343`). But it plans a *second copy of an
already-downloaded model* across drives — it needs the source model present.

### 2.7 `tools/download_glm52.py --check` — the ONLY genuine pre-download check

This is the closest thing in the repo to "should I download this":

```python
c/tools/download_glm52.py:32-40
def check():
    info = HfApi().repo_info(REPO, revision=REVISION, files_metadata=True)
    tot = sum((s.size or 0) for s in info.siblings)
    sts = [s for s in info.siblings if s.rfilename.endswith(".safetensors")]
    free = shutil.disk_usage(os.path.dirname(DEST) or "/").free
    print(f"repo: {REPO}")
    print(f"  total files: {len(info.siblings)} ({len(sts)} safetensors shards)")
    print(f"  total size: {human(tot)}")
    print(f"  free space in {DEST}: {human(free)}")
    print(f"  {'OK: enough space' if free > tot*1.05 else 'WARNING: not enough space'}")
```

Documented in its own docstring (`c/tools/download_glm52.py:14`):
`python3 tools/download_glm52.py --check    # solo stima spazio e conteggio file, niente download`.

Limits, all of them material:

- **Hardcoded to one repo** — `REPO = "zai-org/GLM-5.2-FP8"` (`:20`). Nothing
  parameterises it for Inkling / Kimi K3 / DeepSeek V4 / OLMoE.
- **Disk only.** It never calls `memory_available()`. A machine with 481 GB free
  and 4 GB of RAM gets "OK: enough space".
- **Not a `coli` subcommand** — it is not in the dispatch table at `c/coli:1412`.
- **Requires `huggingface_hub`** (`:18`) and a network round-trip.

---

## 3. What does NOT exist — each with its control arm

### 3.1 No pre-download "which models fit this machine" command

**Claim:** every planner/doctor path requires the weights already on disk.

**Evidence, not a grep:** `build_plan()` unconditionally calls
`info = analyze_model(model)` at `c/resource_plan.py:529`, and `analyze_model`
(`:37-45`) raises immediately without local files:

```python
c/resource_plan.py:39-45
    config_path = model / "config.json"
    if not config_path.is_file():
        raise ValueError(f"missing config.json: {model}")
    ...
    shards = sorted(model.glob("*.safetensors"))
    if not shards:
        raise ValueError(f"no safetensors shards: {model}")
```

It then walks *every shard's* tensor headers (`:46-53`) and stats every shard
(`:62`). `cmd_plan` (`c/coli:724-732`) and `cmd_info` (`c/coli:690`) both
`sys.exit` outright when `--model` is absent. There is no `--model-type`,
`--hypothetical`, or size-table mode.

### 3.2 No Apple-GPU / Metal VRAM discovery in the planner

**Control arm first:** `grep -c "subprocess.run" c/resource_plan.py` → **7**, and
`grep -c "nvidia-smi" c/resource_plan.py` → **4**. So a grep for a
subprocess-based detector in this file *can* return hits — the probe
discriminates.

**Target:** `grep -rn "system_profiler\|SPDisplaysDataType\|recommendedMaxWorkingSetSize\|apple\|Apple" c/resource_plan.py`
→ exactly **one** hit, and it is a comment about CPU cores, not GPUs:

```
c/resource_plan.py:369  # Apple Silicon hw.physicalcpu counts P+E cores with no SMT sibling to
```

`discover_gpus()` is exhaustively two branches:

```python
c/resource_plan.py:230-236
def discover_gpus():
    devices = _discover_nvidia_gpus()
    if devices:
        return devices
    return _discover_amd_gpus()
```

Live confirmation on this M2 Max: `discover_gpus() == []`. Downstream, `safe_vram`
stays 0, `vram_budget = 0`, `vram_experts = 0` (`c/resource_plan.py:566-574`), and
`format_plan` prints the literal line **`VRAM   no NVIDIA device detected · CPU
path`** (`c/resource_plan.py:730`).

**Related dead branch (worth flagging upstream):** `_auto_tune()` takes a
`plan_has_metal` parameter (`c/resource_plan.py:459`) whose only use is the OMP
spin-wait suppression at `:504-506`. `build_plan` passes it **hardcoded `False`**
at `:622`, and `grep -rn "plan_has_metal" c/` returns only those three lines —
definition, use, and the hardcoded `False`. On an Apple-Silicon Mac running the
Metal backend, that tuning decision can never fire from `coli plan`.

### 3.3 Nothing reads the README hardware table programmatically

**Control arm:** `grep -rln "resource plan" .` (excluding `graphify-out/`) →
6 files (`CHANGELOG.md`, `docker/Dockerfile.slim`, `docs/SETTINGS.md`, `c/coli`,
`docs/ENVIRONMENT.md`, `c/tests/test_deepseek_v4.c`). The grep shape works.

**Target 1 — does code read README.md?** `grep -rn "README" c/ colibri/` → 4 hits,
**all comments**:

```
c/coli:146                    # Parameter counts are the roster's, i.e. the README's, so the two cannot drift
c/Makefile:164                #   clean. See backend_loader.c and README "cuda-dll" below.
c/tools/efficiency.py:182     # a 10x margin. Tune per-host via env if needed (documented in README).
c/tests/test_inefficiency.py:6  CUDA_DLL=1 (see tests/README_efficiency.md for the build command).
```

No file open, no parse.

**Target 2 — are the table's numbers in code?**
`grep -rni "167\|372\|469\|1\.6 *TB" c/*.py c/coli` → **zero hits**, under the
control arm above.

**The "roster" at `c/coli:146` is a red herring** — I chased it and it is
display-only:

```python
c/coli:149-155
_BANNER_MODELS = (
    ("deepseek_v4", "DeepSeek V4 Flash", "284B"),
    ("inkling",     "Inkling",           "975B"),
    ("kimi",        "Kimi K3",           "2.8T"),
    ("olmoe",       "OLMoE",             "7B"),
    ("glm",         "GLM-5.2",           "744B"),
)
```

Parameter counts for the banner line, keyed on `config.json`'s `model_type`
(`model_banner_line`, `c/coli:157-203`) — **no disk figure, no RAM figure**, and it
too only runs once a model directory exists (`c/coli:167-172` returns the generic
tagline otherwise).

The README table itself is at `README.md:369-375`, inside a blockquote that exists
precisely because readers conflated the models
([issue #191](https://github.com/JustVugg/colibri/issues/191), cited at
`README.md:367`). It is **prose for humans**.

### 3.4 `coli info` prints no RAM row on macOS

Not asked, but it falsifies the natural fallback ("just run `coli info`"):

```python
c/coli:704-709
    try:
        mi=open('/proc/meminfo').read()
        tot=int(re.search(r'MemTotal:\s+(\d+)',mi).group(1))/1e6
        av=int(re.search(r'MemAvailable:\s+(\d+)',mi).group(1))/1e6
        row("RAM", f"{tot:.0f} GB total · {av:.1f} GB available")
    except Exception: pass
```

`/proc/meminfo` does not exist on Darwin, so the bare `except Exception: pass`
**silently drops the RAM row**. `coli info` on this Mac shows model/shards/disk/engine
and no memory line — even though `resource_plan.memory_available()`, sitting in the
same directory, handles Darwin correctly (`c/resource_plan.py:122-141`). `cmd_info`
simply never imports it. That is a genuine upstream inconsistency, cheap to fix.

---

## 4. The practical answer for THIS machine

> **96 GB unified memory, 12 cores, ~481 GB free (measured 516.3 GB at `sources/colibri/c`).**

**There is no colibri command that will answer "which models can I run?" before
downloading.** What you can do, in order of effort:

1. **Arithmetic against `README.md:369-375`** (the numbers are docs-only, so this
   is a human step):

   | Model | Disk needed | Fits in ~481 GB? | RAM needed | Fits in 96 GB? |
   |---|---|---|---|---|
   | OLMoE | ~4 GB | yes | 8 GB | yes |
   | DeepSeek V4 Flash | ~167 GB | yes | 16 GB min / 22 comfortable | yes |
   | GLM-5.2 | ~372 GB | yes, ~109 GB to spare | 16 min / 24 comfortable | yes |
   | Inkling | ~469 GB | **marginal** — ~12 GB headroom | 25 GB (int4 dense container) | yes |
   | Kimi K3 | ~1.6 TB | **no** | 32 GB+ | yes |

   RAM is never the binding constraint on this box; **disk is**, and only for
   Inkling and Kimi K3.

2. **`GLM_DIR=/path python3 c/tools/download_glm52.py --check`** — the only real
   preflight, GLM-5.2-FP8 only, disk only, needs `huggingface_hub` and network.

3. **After downloading, `coli doctor --json` is the authoritative verdict** —
   `memory.ram` goes `fail` on "planned RAM budget exceeds available memory" or
   "RAM budget cannot hold one expert slot per sparse layer" (`c/doctor.py:500-506`).
   Pass `--ram 80` so the budget comes from your 96 GB rather than from whatever
   `vm_stat` happened to call reclaimable.

### What a ~10-line pre-download wrapper would need to read

Nothing exotic — the pieces all exist, they are just never composed:

```python
import shutil, sys; sys.path.insert(0, "<clone>/c")
from resource_plan import memory_available          # c/resource_plan.py:79  (darwin-correct)
import subprocess
total_ram = int(subprocess.run(["sysctl","-n","hw.memsize"],capture_output=True,text=True).stdout)
free_disk = shutil.disk_usage(DEST).free
# remote size, generalising c/tools/download_glm52.py:33-34 beyond its hardcoded REPO:
from huggingface_hub import HfApi
size = sum((s.size or 0) for s in HfApi().repo_info(REPO, files_metadata=True).siblings)
# verdict: size * 1.05 <= free_disk  AND  ram_min_for(REPO) <= total_ram
```

Three gaps it closes, each traceable to a line above:

1. **A model→requirements table in code.** Today it lives only in `README.md:369-375`;
   `_BANNER_MODELS` (`c/coli:149-155`) is the obvious place to add `disk_bytes` and
   `ram_min_bytes` alongside the parameter count — the comment at `c/coli:146`
   already asserts that table and the README "cannot drift apart quietly", so
   extending it keeps that property.
2. **Total RAM, not reclaimable RAM.** `memory_available()` deliberately returns
   reclaimable (27.8 GB here); a *capability* question wants `hw.memsize`
   (96 GB). Both are one `sysctl` apart at `c/resource_plan.py:137`.
3. **Parameterising `REPO`** — `c/tools/download_glm52.py:20` is a hardcoded
   constant; everything else in `check()` is already model-agnostic.

---

## 5. Summary table

| Capability | Exists? | Where | Needs weights on disk? |
|---|---|---|---|
| Hardware-aware RAM/VRAM/disk tier planner | ✅ | `coli plan` → `c/resource_plan.py:523` | **yes** |
| Readiness diagnostic with pass/warn/fail | ✅ | `coli doctor` → `c/doctor.py:406` | **yes** |
| Deep tensor/shard/index/mirror preflight | ✅ | `coli doctor --deep` → `c/doctor.py:177` | **yes** |
| Auto-apply the plan to the run | ✅ | `--auto-tier` → `c/coli:1316`, `environment_for_plan` `c/resource_plan.py:663` | yes |
| Mirror free-space projection | ✅ | `c/tools/mirror_plan.py:213-239` | yes |
| Pre-download disk-space check | ⚠️ GLM-only | `c/tools/download_glm52.py:32-40` | no |
| Pre-download RAM check | ❌ | — | — |
| "Which models fit this machine" | ❌ | — | — |
| Apple/Metal GPU + VRAM discovery | ❌ | `discover_gpus()` `c/resource_plan.py:230` is NVIDIA/AMD only | — |
| macOS RAM row in `coli info` | ❌ | `/proc/meminfo` only, swallowed by `except` `c/coli:704-709` | — |
| Code reading the README requirements table | ❌ | docs-only, `README.md:369-375` | — |

---

## 6. Note on the second project

`/Users/rmanaloto/agy-graphify-research/` was **not** consulted for any claim in
this report. The brief flagged it as a toy experiment whose claims should be
treated with suspicion, and every question here was answerable from colibri's own
pinned source, so no secondary evidence was admitted.

---

## GitHub repos touched

- [JustVugg/colibri](https://github.com/JustVugg/colibri) — the pinned v1.5.0 clone at `sources/colibri/`; the entire subject of this report (`c/resource_plan.py`, `c/doctor.py`, `c/coli`, `c/tools/mirror_plan.py`, `c/tools/download_glm52.py`, `README.md`, `docs/quickstart.md`, `docs/tuning.md`, `docs/ENVIRONMENT.md`). Issue #191 referenced only as cited inside `README.md:367`, not fetched.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the tool used to orient (`mise run kb-query`, `graphify explain`); no source read.
