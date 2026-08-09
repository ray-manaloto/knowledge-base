# D20 verified: structlog as an event layer over stdlib's sink layer

**Date:** 2026-08-09 · **Requirements:** R1, R3, R7 · **Depends on:** §2.5's
ruling (one event stream with a human-rendering stdout sink).

The parallel `dotfiles` session's **D20** proposes `structlog` + stdlib
`ProcessorFormatter` + `QueueHandler`/`QueueListener`, with a framing correction:

> *"structlog vs loguru is NOT the axis."* structlog is an **event layer** (a
> processor pipeline producing an event dict, then handing off); loguru is a
> **complete logging system with its own sinks**. The sink layer is a separate
> decision, and stdlib already owns it.

R11 requires this be **tested here, not inherited**. All three of `structlog`,
`loguru` and `logbook` were ingested on 2026-08-09, so the first two legs are
graph-answerable; the third is stdlib and needed a probe.

## Leg 1 — the event layer exists and is the entry point

`graphify explain "wrap_logger"`:

```
Node:      wrap_logger()
Source:    src/structlog/_config.py L155
Community: BindableLogger
Degree:    16
```

## Leg 2 — the stdlib bridge exists, and is not a peripheral

`graphify explain "ProcessorFormatter"`:

```
Node:      ProcessorFormatter
Source:    src/structlog/stdlib.py L1012
Community: JSONRenderer
Degree:    37
```

**Degree 37 is the load-bearing part of that read.** A bridge nobody uses would
be a leaf; 37 connections and membership in the `JSONRenderer` community says
this is a first-class path through the library, not an escape hatch. That is a
claim about *structure* the graph can make and a docs page cannot.

## Leg 3 — the offload is real, and control-armed

R7 wants serialisation moved off the calling thread. `QueueHandler` +
`QueueListener` is stdlib, so it is **not** in the corpus, and asserting its
behaviour from recollection would be the inherited-number failure
(`probes-need-a-control-arm.md` rule 6). Probed directly:

| arm | handler ran on | verdict |
|---|---|---|
| `QueueHandler` → `QueueListener` | tid `6112407552` | **offloaded** (main was `8526766464`) |
| **CONTROL** — same handler, no queue | tid `8526766464` | ran on the main thread |

The control is what makes this evidence: the probe can produce both answers, so
"different thread" is a measurement rather than a hope. The message was also
delivered intact, so the offload is not silently dropping records.

## What this means for §2.5's ruling

§2.5 was answered on 2026-08-09 as **one structured event stream with a
human-rendering stdout sink**. D20 is precisely that shape, and the three legs
map onto the requirements without a gap:

| requirement | what serves it |
|---|---|
| **R1** — async, structured, multiple formats via sinks | structlog's processor pipeline produces the event; stdlib handlers are the sinks |
| **R3** — output that must reach stdout gets its own dedicated sink | a stdlib handler with `ProcessorFormatter` rendering the event dict as today's tables |
| **R7** — offload serialisation to the logging thread | `QueueListener` — **`QueueListener` IS the logging thread**, measured above |

So the answer to R7's "offload to the logging thread" is not a library feature to
shop for; it is a stdlib handler this repo can adopt today.

## Where the framing correction earns its keep

"structlog vs loguru" being the wrong axis is not a stylistic point. Under §2.5's
ruling the sink layer has to render **product** — `kb-check`'s summary table,
`kb-gates`' report — so whoever owns the sink layer owns the shape of every
report this repo prints. If that is loguru's own sink system, the rendering is
inside a third-party library; if it is stdlib, it is a `Formatter` subclass in
`kb_setup`. The second is the repo's existing pattern (logic in a module, a seam
in config).

`logbook`, ingested because the dotfiles session found it and this repo's sweep
missed it, is a **third** architecture — a handler *stack* rather than a
processor pipeline or an owned-sink system. It was not evaluated here; it is in
the graph, and it is the obvious thing to compare against before this is settled.

## `logbook` — the third architecture, now evaluated

Listed above as unevaluated; done here, because it is the candidate this repo's
own sweep missed and the dotfiles session supplied (§2.6j).

**The contrast is structural and citable, not a matter of taste.**

`logbook` ships an entire transport layer. `src/logbook/queues.py` defines
**14 classes**:

```
RedisHandler            MessageQueueHandler      ZeroMQHandler
ThreadController        SubscriberBase           MessageQueueSubscriber
ZeroMQSubscriber        MultiProcessingHandler   MultiProcessingSubscriber
ExecnetChannelHandler   ExecnetChannelSubscriber TWHThreadController
ThreadedWrapperHandler  GroupMember
```

`structlog` has **no equivalent module at all**. Its package is `processors.py`,
`stdlib.py`, `dev.py`, `contextvars.py`, `tracebacks.py`, `testing.py` — every
one of them event-shaping or integration. That is D20's framing correction
confirmed by structure rather than by assertion: **structlog is an event layer,
full stop**, and logbook is a complete system that owns its own transport.

`ThreadedWrapperHandler` (`queues.py:668`, degree 15) is logbook's answer to R7's
offload — the direct counterpart of stdlib's `QueueListener`.

### The R12 consequence, which is the part that matters here

Under `mise run test`'s `-n auto`, **every pytest worker is a separate process**.
logbook ships `MultiProcessingHandler` / `MultiProcessingSubscriber` as a
purpose-built pair for exactly that topology. stdlib can do it too — a
`QueueHandler` over a `multiprocessing.Queue` — but that is an assembly, not a
provided component.

So the trade is not "logbook has more features". It is:

| | structlog + stdlib | logbook |
|---|---|---|
| event layer | structlog processors | logbook's own |
| sink layer | **stdlib handlers** — a `Formatter` subclass in `kb_setup` | logbook handler stack |
| thread offload | `QueueListener` (measured above) | `ThreadedWrapperHandler` |
| **process** offload | assemble from `QueueHandler` + `multiprocessing.Queue` | **`MultiProcessingHandler`/`Subscriber`, provided** |
| who owns report rendering | this repo | the library |

Under §2.5's ruling the last row is decisive, and it points at structlog+stdlib:
the sink renders **product**, so rendering belongs in `kb_setup` where it is
reviewed like any other module. The R12 row points the other way, and is the
strongest argument logbook has.

**Not measured:** whether `MultiProcessingHandler` actually behaves correctly
under `pytest-xdist`'s specific worker model. That is a probe, not a read, and it
should be run before the R12 row is given any weight — this section establishes
that the component exists and is aimed at the right problem, nothing more.

## What this does NOT establish

- **It does not choose the wire format.** R7's "modern efficient message formats"
  is a separate decision, and the msgspec `Path` cost measured in
  `2026-08-09-msgspec-extra-fields-r11.md` (523 annotations, 87% of modules)
  bears on it directly.
- **It does not measure throughput or latency**, only that the offload occurs.
  Nothing here says the queue is fast enough, and nothing here needed to —
  §2.6i already recorded that this repo's ceiling is not throughput.
- **It does not evaluate `logbook` or re-evaluate `loguru` on merit.** Both are
  in the graph precisely so that can be done with citations.
- **`QueueListener` was probed on the interpreter `uv run` resolves**, not under
  `-n auto` with 12 workers. Given §2.6g's finding that parallel execution
  invalidates timing assertions, any *performance* claim about this path must be
  re-measured under the real concurrency, not extrapolated from this probe.

## GitHub repos touched

- [hynek/structlog](https://github.com/hynek/structlog) — `wrap_logger`,
  `ProcessorFormatter`; read via the graph at the pinned commit.
- [Delgan/loguru](https://github.com/Delgan/loguru) — named in the framing
  correction; not evaluated here.
- [getlogbook/logbook](https://github.com/getlogbook/logbook) — named as the
  unevaluated third architecture.
