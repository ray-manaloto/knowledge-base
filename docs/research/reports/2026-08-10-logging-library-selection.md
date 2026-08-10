# Logging library selection — the six candidates, decided on §2.5's own axis

**Date:** 2026-08-10 · **Requirements:** R1, R3, R7, R8, R10, R12 ·
**Supersedes as the single source:** the scattered verdicts in
`2026-08-09-d20-structlog-stdlib-architecture.md` and
`2026-08-09-r1-r12-answers.md`.

## Why this document exists

Asked whether the contenders were documented and why structlog won, the honest
answer was **no**. Six logging libraries are ingested as `sources/`, and before
this document only three had any verdict at all:

| candidate | verdict on record before today | where |
|---|---|---|
| structlog | recommended, three legs verified | D20 report |
| logbook | evaluated structurally | D20 report |
| picologging | dead by three liveness instruments | R1–R12 answers |
| **loguru** | **none** — D20 says outright it was not evaluated | — |
| **logly** | **none** — liveness screen only | manifest comment |
| **logxide** | **none** — liveness screen only | manifest comment |

So structlog had not *won* anything; it was the only candidate tried. Three of
six had never been evaluated on merit. This document evaluates all six against
one axis, and that axis is not a matter of taste — it is the §2.5 ruling.

## The decisive axis, stated before the evidence

§2.5 ruled: **one structured event stream with a human-rendering stdout sink.**
Under that ruling the sink layer renders **product** — `kb-check`'s summary
table, `kb-gates`' report, `kb-session-reflect`'s report. Therefore:

> **Whoever owns the sink layer owns the shape of every report this repo
> prints.**

That converts a library preference into a testable question: *does adopting this
library put our report rendering inside a third-party (or non-Python) component?*
A library that owns its sinks is not disqualified for being bad — it is
disqualified for taking custody of the thing §2.5 says we render.

The second axis is this repo's own dependency posture. `pyproject.toml` declares
`dependencies = []`, and **`kb-setup` is consumed by the sibling dotfiles repo as
a SHA-pinned git dependency**. Any runtime dependency added here is *exported*.
The file already reasons about exactly this for `trafilatura`; D20 never weighed
it.

## Liveness — measured, and the pins are not the story

R10 wants commits within the last month. Every manifest pin was checked against
upstream HEAD via the GitHub API, because a stale *pin* would be indistinguishable
from a stale *project* — the false negative this repo's rules exist to prevent.

| candidate | pinned commit | upstream HEAD | identical? | R10 |
|---|---|---|---|---|
| structlog | 2026-08-06 `ab24a26` | 2026-08-06 | ✅ | **PASS** (4 days) |
| logly | 2026-08-07 `5d3f95d` | 2026-08-07 | ✅ | **PASS** (3 days) |
| logbook | 2026-08-05 `d3d6972` | 2026-08-05 | ✅ | **PASS** (5 days) |
| logxide | 2026-07-14 `136f7a4` | 2026-07-14 | ✅ | **MARGINAL** (27 days) |
| loguru | 2026-06-13 `2a17be7` | 2026-06-13 | ✅ | **FAIL** (58 days) |
| picologging | 2025-06-18 `deaee6e` | 2025-06-17 | ✅ | **FAIL** (~14 months) |

**Every pin equals upstream HEAD.** That is the control arm: the six verdicts
describe the projects, not this repo's ingestion date. picologging's death is
confirmed rather than inherited from the earlier report.

## Architecture — who owns the sink layer

Read from the pinned source tree, not from docs pages.

**structlog** — `src/structlog/`: `processors.py`, `stdlib.py`, `dev.py`,
`contextvars.py`, `tracebacks.py`, `testing.py`, `twisted.py`. Every module is
event-shaping or integration. **There is no transport or sink module at all.**
`stdlib.py`'s `ProcessorFormatter` (degree 37 in the graph, in the `JSONRenderer`
community) is a first-class bridge, not an escape hatch.
→ **We own the sink layer.**

**loguru** — `loguru/`: `_handler.py`, `_file_sink.py`, `_simple_sinks.py`,
`_colorizer.py`, `_filters.py`, `_string_parsers.py`. A complete logging system
with its own sink abstraction; its stdlib direction is an `InterceptHandler` that
absorbs stdlib records *into* loguru.
→ **The library owns the sink layer.**

**logbook** — `src/logbook/queues.py` alone defines **14** transport classes
(`RedisHandler`, `ZeroMQHandler`, `MultiProcessingHandler`,
`ThreadedWrapperHandler`, …). A handler *stack* that owns its transport.
→ **The library owns the sink layer.**

**logly** — 15 Rust crates: `sink`, `format`, `color`, `rotate`, `network`,
`compress`, `concurrency`, … The Python side (`logger.add(...)`,
`integrations/stdlib.InterceptHandler`) is a binding over them.
→ **The sink layer is in Rust.** Rendering `kb-gates`' table would mean
rendering it through a Rust sink crate.

**logxide** — `compat_handlers.py`, `interceptor.py`, `module_system.py`,
`fast_logger_wrapper.py`. A *near*-drop-in stdlib replacement with a Rust core:
same API, faster engine. Structurally this is not a competitor to
structlog+stdlib at all — it is a potential accelerator *underneath* it.

**stdlib `logging`** — handlers and `Formatter` are ours to subclass.
→ **We own the sink layer.**

## The two disqualifications that came from the candidates' own words

**logxide disqualifies itself on precisely our design point.** From its own
README, verbatim:

> It's a **near**-drop-in, not a strict one: some advanced stdlib behaviors
> differ (flush now drains/waits, `LogRecord`/`Logger` can't be subclassed,
> **custom `Formatter` subclasses fall back to a slower path**).

D20's design *is* a custom `Formatter` subclass in `kb_setup`. logxide degrades
exactly the case §2.5 makes central, and forbids `LogRecord` subclassing. Its
README also records that **Python 3.15 is unsupported** pending a `pyo3` ABI fix
— a compiled extension is a forward-compatibility liability for a dependency
this repo *exports* to dotfiles, on a project already at `requires-python >=3.14`.

**logly exports pydantic.** Its `pyproject.toml` declares
`dependencies = ["pydantic>=2.12.5", ...]`. Adopting it would make the first
entry in this repo's empty `dependencies` list a transitive pydantic — pushed
onto dotfiles, which resolves its own tree. That is a large export for a project
at PyPI **0.2.2** with **★379**.

Neither disqualification is a judgement about quality. Both are direct
consequences of §2.5's ruling and this repo's consumer contract.

## The logbook row that D20 got wrong — refuted by measurement today

D20's comparison table gave logbook exactly one winning row: R12 process
offload, where `MultiProcessingHandler`/`Subscriber` are *provided* and stdlib is
*an assembly*. D20 flagged it explicitly as **not measured**. It is measured now.

| arm | what ran | result |
|---|---|---|
| **CONTROL** — logbook's designed topology (parent `mp.Queue`, `mp.Process` children) | `control_arm.py` | **4/4 records collected** |
| xdist, naive — each worker builds its own `mp.Queue()` | `pytest -n 4` | **0 records** reach the controller |
| xdist + `SyncManager` shared queue (the assembly) | `pytest -n 4` | **8 records: 4 logbook + 4 stdlib**, all four workers attributed `gw0`–`gw3` |

**Cause:** pytest-xdist workers are **execnet** subprocesses, not `multiprocessing`
children, so a per-worker `mp.Queue()` has no shared endpoint. logbook's
purpose-built pair does not bridge that gap.

**Consequence:** under this repo's actual test topology, logbook needs the *same*
manager assembly stdlib needs — and once that assembly exists, stdlib's
`QueueHandler` delivers identically. **logbook's only winning row is void.**

Two details worth keeping:

- The control arm is what makes the negative believable. The probe produces
  records in logbook's designed topology, so "0 under xdist" is a measurement
  rather than a broken harness.
- The first xdist run returned **rc=3** with 0 records — a missing
  `import logging.handlers` in the probe's own conftest. Reading the rc rather
  than the record count is what stopped a broken probe being written up as a
  finding. Had the count alone been trusted, this document would have reported
  the right verdict for the wrong reason.
- Incidental but load-bearing for any adoption: logbook puts a **dict** on the
  queue (`export_record()`); stdlib puts a real `LogRecord`. logbook needs a
  rehydration step stdlib does not.

## The decision table

| | structlog + stdlib | loguru | logbook | logly | logxide | stdlib alone |
|---|---|---|---|---|---|---|
| **who owns report rendering** | **us** | library | library | **Rust crate** | us (degraded) | **us** |
| R10 liveness | PASS (4d) | **FAIL (58d)** | PASS (5d) | PASS (3d) | MARGINAL (27d) | n/a |
| exported runtime deps | **none** on py≥3.11 | none on py≥3.7/non-win32 | `typing-extensions` | **pydantic** | none | **none** |
| compiled extension | no | no | optional (Rust) | **yes** | **yes** (no py3.15) | no |
| R7 thread offload | `QueueListener` (measured) | own `enqueue=True` | `ThreadedWrapperHandler` | Rust | stdlib | `QueueListener` |
| R12 process offload under xdist | manager assembly | — | **manager assembly (refuted as "provided")** | — | — | manager assembly |
| custom `Formatter` subclass | first-class | n/a | n/a | n/a | **slow path** | first-class |
| event layer (binding, processors) | **structlog** | own | own | own | none (stdlib API) | **hand-written** |

## Recommendation

**structlog as the event layer, stdlib as the sink layer.** It is the only
candidate that leaves report rendering in `kb_setup` *and* passes R10 *and*
exports nothing on py≥3.11.

The remaining live question is narrow, and it is the one worth stating plainly:
**structlog versus stdlib alone.** They are identical on every row above except
the last. structlog's earned value is the processor pipeline and
`contextvars` binding — the part that would otherwise be hand-written, which
`use-tool-builtins.md` names as the failure mode. Its cost is one pure-python,
zero-dependency package becoming the first entry in an empty `dependencies` list
that dotfiles inherits.

**Ranking, with the reason each one loses:**

1. **structlog + stdlib** — wins the decisive axis, exports nothing.
2. **stdlib alone** — same axis, same export cost; loses only by making us
   hand-write the event layer.
3. **logxide** — not a rival; a possible later accelerator *under* stdlib.
   Blocked today by the `Formatter`-subclass slow path and the py3.15 gap.
4. **logbook** — sound library; owns the sink layer, and its one differentiating
   row was refuted above.
5. **loguru** — sound library; owns the sink layer, and fails R10 at 58 days.
6. **logly** — owns the sink layer *in Rust* and exports pydantic. Ruled out on
   both of this repo's constraints at once.

## What this document does NOT establish

- **It does not measure throughput or latency for any candidate.** §2.6i already
  recorded that this repo's ceiling is not throughput, so no benchmark was run;
  the ranking rests on custody, liveness and export cost, not speed. logly's and
  logxide's performance claims are neither confirmed nor denied here.
- **It does not evaluate loguru's or logly's feature sets on merit.** Both were
  ruled out by the sink-custody axis before features mattered. If §2.5's ruling
  were ever revisited, both re-enter contention and would need a real read.
- **The xdist measurement is about pytest-xdist's execnet worker model**, not
  about `multiprocessing` generally. logbook's component works correctly in the
  topology it was designed for — that is the control arm, not a caveat.
- **`ProcessorFormatter`'s degree-37 reading is inherited** from the D20 report's
  graph query, not re-derived here.

## GitHub repos touched

- [hynek/structlog](https://github.com/hynek/structlog) — recommended event layer; module list and liveness read at the pinned commit.
- [Delgan/loguru](https://github.com/Delgan/loguru) — evaluated on merit for the first time; sink custody + R10.
- [getlogbook/logbook](https://github.com/getlogbook/logbook) — `queues.py` transport stack; its R12 row measured and refuted.
- [microsoft/picologging](https://github.com/microsoft/picologging) — liveness confirmed dead against upstream HEAD.
- [muhammad-fiaz/logly](https://github.com/muhammad-fiaz/logly) — Rust sink crates; pydantic export.
- [Indosaram/logxide](https://github.com/Indosaram/logxide) — near-drop-in stdlib replacement; self-disqualifying README.
- [pytest-dev/pytest-xdist](https://github.com/pytest-dev/pytest-xdist) — the execnet worker model the R12 probe measured against.
