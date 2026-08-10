# Copyright (c) 2026 Raymond Manaloto
"""§2.5's sink layer — where events go, and how a human reads them.

**This module is the reason the library choice went the way it did.** Under
§2.5's ruling the sink renders PRODUCT — `kb-gates`' report, `kb-check`'s
summary, `kb-land`'s progress — so whoever owns the sink layer owns the shape of
every report this repo prints. structlog ships no sinks at all, which is what
lets this be a `logging.Formatter` subclass in `kb_setup`, reviewed like any
other module, rather than configuration inside a third-party library. The
six-way comparison is in
`docs/research/reports/2026-08-10-logging-library-selection.md`.

TWO SINKS, and they are not variations on one thing:

- :class:`HumanSink` renders the line a person reads. Today that is the event's
  `text` verbatim, which is what makes converting a progressive printer
  behaviour-preserving — see `events.py` on why `text` exists.
- :class:`JsonlSink` renders the whole event dict, one JSON object per line.
  This is the R9 surface: *"did this run emit anything at WARNING or above, and
  what was it?"* becomes a filter over a file rather than a grep over prose
  nobody kept.

THE OFFLOAD (R7) IS STDLIB, AND IT WAS MEASURED. `QueueHandler` +
`QueueListener` move formatting off the calling thread; the D20 report probed it
with a control arm (handler ran on tid X, control on the main thread) rather
than asserting it. **`QueueListener` IS the logging thread** R7 asks for — not a
library feature to shop for.

WHAT THE xdist PROBE ADDED, 2026-08-10. pytest-xdist workers are `execnet`
subprocesses, not `multiprocessing` children, so a per-worker queue has no
shared endpoint and nothing reaches the controller — measured at 0 records, with
a control arm proving the probe could produce the other answer. Crossing that
boundary needs a manager-shared queue, for stdlib and logbook alike. Until
something needs it, each process renders its own stream and events carry a
`worker` field so the lines can be told apart (`events.worker_id`).
"""

from __future__ import annotations

import contextlib
import json
import logging
import logging.handlers
import queue
import sys
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import structlog

from kb_setup.events import EVENT_KEY, LOGGER_NAME, TEXT_KEY, Level

if TYPE_CHECKING:
    from collections.abc import Iterator
    from os import PathLike
    from typing import IO

    from structlog.typing import EventDict, Processor

#: Event-dict keys the human renderer never prints as fields — they are either
#: the rendering itself or stdlib bookkeeping the line already conveys.
_NOT_FIELDS = frozenset({TEXT_KEY, EVENT_KEY, "level", "logger", "timestamp"})


class HumanSink(logging.Formatter):
    """Render one event as the line a person reads.

    **Prefers the event's `text` verbatim.** That is deliberate and it is the
    load-bearing property of this whole conversion: a boundary whose `print` is
    replaced by an `emit` carrying the same string produces byte-identical
    output, so every pre-existing assertion about what a task prints stays a
    valid regression arm (recipe rule 2). A conversion that also reworded its
    output would have destroyed the only evidence that it changed nothing.

    An event with no `text` falls back to the machine name plus its fields,
    which is what a caller that has *stopped* hand-writing lines gets for free.
    That fallback is the direction of travel; `text` is where this repo is
    today.

    WARNING and above are prefixed, because R9's whole subject is a warning that
    a reader scrolls past. Nothing else is decorated: `kb-gates`' report must
    look exactly as it does now.
    """

    #: What marks a line that a verification pass must not skip.
    PREFIXES: ClassVar[dict[Level, str]] = {
        Level.WARNING: "WARNING: ",
        Level.ERROR: "ERROR: ",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Render `record` as today's human line."""
        event = _event_dict(record)
        text = event.get(TEXT_KEY)
        body = text if isinstance(text, str) else _describe(event)
        prefix = self.PREFIXES.get(_level_of(record), "")
        return f"{prefix}{body}"


class JsonlSink(logging.Formatter):
    """Render the whole event as one JSON object per line — the R9 surface.

    Separate from :class:`HumanSink` rather than a flag on it, because the two
    answer different questions and a run usually wants both attached at once:
    the human stream on stdout, this one to a file a later pass can filter.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Render `record` as one JSON line."""
        event = _event_dict(record)
        event.setdefault("level", _level_of(record).name.lower())
        return json.dumps(event, default=str, ensure_ascii=False)


def _event_dict(record: logging.LogRecord) -> dict[str, object]:
    """The structlog event dict behind a `LogRecord`, however it arrived.

    A record reaching a handler through `ProcessorFormatter.wrap_for_formatter`
    carries the dict on `record.msg`. A record from ordinary stdlib logging (a
    third-party library, or `kb_setup` code not yet converted) does not — and
    must still render rather than crash, because a sink that only works for
    events it recognises would silently drop exactly the third-party warnings
    R9 exists to surface.
    """
    payload = getattr(record, "msg", None)
    if isinstance(payload, dict):
        return dict(payload)
    return {EVENT_KEY: record.name, TEXT_KEY: record.getMessage()}


def _level_of(record: logging.LogRecord) -> Level:
    """`record`'s level as a :class:`Level`, defaulting to INFO if unnamed."""
    try:
        return Level(record.levelno)
    except ValueError:
        return Level.INFO


def _describe(event: dict[str, object]) -> str:
    """Fallback rendering for an event carrying no `text`."""
    name = event.get(EVENT_KEY, "event")
    fields = " ".join(f"{k}={v}" for k, v in event.items() if k not in _NOT_FIELDS)
    return f"{name} {fields}".strip()


class EventQueueHandler(logging.handlers.QueueHandler):
    """A `QueueHandler` that does NOT stringify the event dict on the way in.

    **R7's offload and structlog's event dict do not compose out of the box, and
    this is the seam where they collide.** Stdlib's `QueueHandler.prepare()`
    deliberately calls `record.getMessage()` and replaces `record.msg` with the
    formatted string — its docstring says why: the queue may cross a *process*
    boundary, where an arbitrary payload might not pickle.

    That is the right default and the wrong one here. Everything on this queue
    crosses a *thread* boundary in one process, so nothing needs pickling — and
    stringifying first means the listener hands `ProcessorFormatter` a `str`,
    which raises `AttributeError: 'str' object has no attribute 'copy'` inside
    the logging machinery. Logging swallows handler errors, so the visible
    symptom is **silently missing output**, not a traceback in the caller.

    Found by the offload tests rather than by reading: the D20 report verified
    `QueueListener` moves work off the calling thread, which is true, and says
    nothing about what survives the trip.

    Keeping the record intact is what the stdlib docs prescribe for an
    in-process queue. If a queue here ever does span processes, this override is
    exactly the thing that must be revisited — which is why it is a named class
    with this docstring rather than a lambda.
    """

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        """Hand the record on untouched, event dict and all."""
        return record


class _StdStreamHandler(logging.StreamHandler):
    """A stream handler that resolves `sys.stdout`/`sys.stderr` AT EMIT TIME.

    **Not a nicety — the default sink is unusable without it.** A plain
    `StreamHandler(sys.stdout)` captures the stream object when it is
    constructed. The default handlers are attached once, lazily, to a
    process-global logger, so the very first `emit` in a process pins whatever
    `sys.stdout` was at that moment for the rest of the run.

    Under pytest that is fatal and confusing: `capsys` replaces `sys.stdout` per
    test, so every later test's output goes to the FIRST test's buffer and every
    later assertion sees an empty capture. Three `launch` tests failed this way
    with their output plainly visible in the log capture — which reads as "the
    sink is broken" rather than "the sink is writing somewhere else".

    The same trap exists outside tests wherever `sys.stdout` is rebound
    (`contextlib.redirect_stdout`, a REPL, a wrapper script).
    """

    def __init__(self, name: str) -> None:
        super().__init__()
        self._stream_name = name

    @property
    def stream(self) -> IO[str]:
        """The CURRENT `sys.stdout`/`sys.stderr`, looked up per record."""
        return getattr(sys, self._stream_name)

    @stream.setter
    def stream(self, _value: IO[str]) -> None:
        """Ignore `StreamHandler.__init__`'s assignment; the property decides."""


#: Marks a handler as one of OURS. `events._ensure_sink` looks for this rather
#: than for "any handler at all" — see :func:`is_sink` for why that distinction
#: is load-bearing.
_SINK_MARKER = "_kb_setup_sink"


def is_sink(handler: logging.Handler) -> bool:
    """Whether `handler` is one of this module's, rather than someone else's.

    **"The logger has handlers" is NOT "a sink is attached", and reading it that
    way cost four failing tests.** pytest's logging plugin attaches its own
    `LogCaptureHandler` to any logger it captures — which, because
    `events.configure()` sets this logger to DEBUG, is this one. A lazy sink
    guarded on `if logger.handlers` therefore saw pytest's listeners, concluded
    output was already handled, and attached nothing: every converted boundary
    went silent, with its lines plainly visible in pytest's *log* capture and
    absent from stdout.

    That is a probe that could only answer one way. Marking our own handlers
    makes the question answerable: *is one of MINE attached?*
    """
    return getattr(handler, _SINK_MARKER, False) is True


def _wire(handler: logging.Handler, formatter: logging.Formatter) -> logging.Handler:
    """Wire `formatter` onto `handler` through structlog's bridge.

    `ProcessorFormatter` is the bridge D20 verified is first-class rather than
    an escape hatch (degree 37, in structlog's `JSONRenderer` community). It is
    what lets an event produced by the processor pipeline be rendered by a
    stdlib `Formatter` — which is the entire architecture in one line.
    """
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(processors=[_render_with(formatter)]))
    setattr(handler, _SINK_MARKER, True)
    return handler


def _handler(stream: IO[str], formatter: logging.Formatter) -> logging.Handler:
    """A handler on an explicit, fixed stream (a test buffer, or the JSONL file)."""
    return _wire(logging.StreamHandler(stream), formatter)


def _render_with(formatter: logging.Formatter) -> Processor:
    """Adapt one of this module's `Formatter`s into a structlog renderer."""

    def render(_logger: object, _name: str, event_dict: EventDict) -> str:
        record = event_dict.get("_record")
        level = getattr(record, "levelno", logging.INFO)
        shim = logging.LogRecord(
            name=LOGGER_NAME,
            level=level,
            pathname="",
            lineno=0,
            msg=event_dict,
            args=(),
            exc_info=None,
        )
        return formatter.format(shim)

    return render


class _MaxLevel(logging.Filter):
    """Admit only records strictly below `ceiling` — the stdout half of the split."""

    def __init__(self, ceiling: int) -> None:
        super().__init__()
        self._ceiling = ceiling

    def filter(self, record: logging.LogRecord) -> bool:
        """True when this record belongs on the lower stream."""
        return record.levelno < self._ceiling


def default_handlers() -> list[logging.Handler]:
    """The stdout/stderr pair an unconfigured caller gets — `print` parity.

    Public because `events._ensure_sink` attaches it lazily: an `emit` must
    write something without any setup, exactly as the `print` it replaced did.
    """
    return _human_handlers(None)


def _human_handlers(stream: IO[str] | None) -> list[logging.Handler]:
    """The human sink, split across stdout and stderr the way the old code was.

    **This split is behaviour preservation, not a feature.** Before the
    conversion, every refusal and diagnostic in `kb_setup` was a
    `print(..., file=sys.stderr)` while reports and tables went to stdout. If
    every event now landed on stdout, a caller redirecting the two streams
    separately would silently see different output — a behaviour change smuggled
    inside a refactor, which is what recipe rule 2 exists to prevent.

    So the mapping is: **WARNING and above to stderr, everything else to
    stdout**. That is also the ordinary convention, which is why it costs
    nothing to adopt — but the reason it is here is the old streams.

    An explicit `stream` (a test buffer) takes BOTH halves, so a test can assert
    on one string without caring which stream a line would have used in
    production.
    """
    if stream is not None:
        return [_handler(stream, HumanSink())]
    out = _wire(_StdStreamHandler("stdout"), HumanSink())
    out.addFilter(_MaxLevel(logging.WARNING))
    err = _wire(_StdStreamHandler("stderr"), HumanSink())
    err.setLevel(logging.WARNING)
    return [out, err]


@contextlib.contextmanager
def stdout_sink(
    *,
    stream: IO[str] | None = None,
    jsonl_path: str | PathLike[str] | None = None,
    offload: bool = True,
) -> Iterator[logging.Logger]:
    """Attach the human sink (and optionally a JSONL sink) for the duration.

    A context manager rather than a `configure()` call because a sink that is
    never detached leaks handlers across a test session — and this repo runs its
    suite under `-n auto`, where a leaked handler in one worker is a duplicated
    line with no obvious owner.

    `offload=True` puts a `QueueHandler` in front and runs the real handlers on a
    `QueueListener` thread — R7, measured in the D20 report. It is the default
    because that is what R7 asks for; pass `offload=False` when a caller needs
    the write to have happened by the time `emit` returns (a test asserting on
    captured output, most often).
    """
    logger = logging.getLogger(LOGGER_NAME)
    with contextlib.ExitStack() as stack:
        handlers: list[logging.Handler] = _human_handlers(stream)
        if jsonl_path is not None:
            opened = stack.enter_context(Path(jsonl_path).open("a", encoding="utf-8"))
            handlers.append(_handler(opened, JsonlSink()))

        listener: logging.handlers.QueueListener | None = None
        attached: list[logging.Handler]
        if offload:
            pending: queue.Queue[logging.LogRecord] = queue.Queue(-1)
            listener = logging.handlers.QueueListener(
                pending, *handlers, respect_handler_level=True
            )
            listener.start()
            attached = [EventQueueHandler(pending)]
        else:
            attached = handlers

        previous = list(logger.handlers)
        previous_propagate = logger.propagate
        logger.handlers = attached
        logger.propagate = False
        try:
            yield logger
        finally:
            # ORDER IS LOAD-BEARING, and it is spelled out rather than left to
            # ExitStack's LIFO because getting it subtly wrong loses the tail of
            # every offloaded run: stop the listener so the queue DRAINS into the
            # handlers, only then flush them, and only then let the stack close
            # the file. A flush before the drain writes nothing and looks fine.
            logger.handlers = previous
            logger.propagate = previous_propagate
            if listener is not None:
                listener.stop()
            for handler in handlers:
                handler.flush()
