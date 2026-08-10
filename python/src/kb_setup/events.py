# Copyright (c) 2026 Raymond Manaloto
"""§2.5's event stream — one structured stream, rendered for humans by a sink.

WHAT RAY RULED, 2026-08-09: *one structured event stream with a human-rendering
stdout sink*, not *reports become log lines*. Most of this repo's ~455
`print`/`sys.std*` sites are the PRODUCT — `kb-check`'s summary, `kb-gates`'
report, `kb-currency`'s run log — read by humans and in places parsed by
machines. They become events; a dedicated sink renders them as the text that is
read today.

THE ARCHITECTURE, and where each half is decided. `structlog` is the event layer
(a processor pipeline producing an event dict, then handing off); **stdlib owns
the sink layer**, which is what keeps report rendering inside `kb_setup` where
it is reviewed like any other module. That choice is not a preference — it is
the decisive axis in
`docs/research/reports/2026-08-10-logging-library-selection.md`, which evaluated
all six ingested candidates: whoever owns the sink layer owns the shape of every
report this repo prints.

WHY `text` IS A FIELD, stated plainly because it looks like a shortcut and is
not. Every emit carries both named fields AND the human line as rendered today,
and the stdout sink prints that line verbatim. This is what makes converting a
progressive printer **behaviour-preserving**: recipe rule 2 keeps a conversion
from changing behaviour precisely so the pre-existing exit-code assertions stay
a valid regression arm, and the same argument applies to output. A conversion
that also reworded every line would destroy the only evidence that it changed
nothing.

So `text` is the CURRENT rendering, not the event's meaning. The fields are the
event's meaning, and they are what R9 queries. A later renderer can compose from
fields and drop `text`; nothing outside this module and `sinks.py` should read
it.

WHAT THIS BUYS THAT `print` COULD NOT — the three concrete cases, each measured
rather than argued:

- **R9.** `kb-build` exited **0**, printed *"0 dangling, 0 malformed"*, and
  buried **1,024** node-loss warnings in the same stdout (#231). Under one
  stream with levels, "did this run emit anything at WARNING or above?" is
  :func:`Tally.above` rather than a grep nobody runs.
- **R12.** Under `mise run test`'s `-n auto` every worker writes to one stdout,
  so a table and a warning interleave with no attribution. An event carries a
  worker field; a `print` cannot.
- **R7.** Serialisation moves off the calling thread via stdlib's
  `QueueListener`, which IS the logging thread — measured, with a control arm,
  in the D20 report.
"""

from __future__ import annotations

import contextlib
import logging
import logging.handlers
import os
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from structlog.typing import EventDict, Processor

#: The logger every `kb_setup` event travels on. One name, so a consumer
#: attaches one handler and sees the whole stream.
LOGGER_NAME = "kb_setup"

#: The event-dict key carrying the line a human reads. See the module docstring:
#: this is the CURRENT rendering, not the event's meaning.
TEXT_KEY = "text"

#: The event-dict key carrying the short machine name (`land.await`, `gate.pass`).
EVENT_KEY = "event"


class Level(IntEnum):
    """Event levels, aliased to stdlib's so a handler needs no translation.

    Named here rather than reused directly so the vocabulary this repo actually
    emits is visible in one place — and so `WARNING` means one thing: *the run
    continued, and something happened that a verification pass must see*. That
    is R9's subject, and it is the level `zero-skip-policy.md` forbids
    dismissing.
    """

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR


@dataclass(slots=True)
class Tally:
    """How many events were emitted at each level during one run.

    **This is R9's mechanism, not bookkeeping.** A gate that exits 0 having
    buried a thousand warnings is the failure this whole section exists to
    close; `above(Level.WARNING)` is the assertion that catches it, and it is
    only expressible because every stream is one stream.
    """

    counts: dict[Level, int] = field(default_factory=dict)

    def record(self, level: Level) -> None:
        """Fold one event into the tally."""
        self.counts[level] = self.counts.get(level, 0) + 1

    def above(self, level: Level = Level.WARNING) -> int:
        """How many events were at or above `level`."""
        return sum(n for lvl, n in self.counts.items() if lvl >= level)

    def summary(self) -> str:
        """A one-line census, for a task that wants to state what it emitted."""
        if not self.counts:
            return "no events"
        parts = [f"{lvl.name.lower()}={self.counts[lvl]}" for lvl in sorted(self.counts)]
        return " ".join(parts)


class _TallyProcessor:
    """A structlog processor that counts events and passes them through unchanged.

    A processor rather than a handler because it must see EVERY event, including
    ones a handler's level filter would drop — a tally that only counts what was
    printed cannot answer "was anything suppressed".
    """

    def __init__(self, tally: Tally) -> None:
        self._tally = tally

    def __call__(self, _logger: object, method_name: str, event_dict: EventDict) -> EventDict:
        """Count, then hand the event on untouched."""
        name = method_name.upper()
        if name == "WARN":
            name = "WARNING"
        # A level this repo does not name is not worth failing an emit over —
        # the event still travels; only the tally skips it.
        with contextlib.suppress(KeyError):
            self._tally.record(Level[name])
        return event_dict


def worker_id() -> str | None:
    """This pytest-xdist worker's id (`gw0`), or `None` outside a parallel run.

    Read from the environment rather than from a pytest fixture so that ordinary
    (non-test) code carries the field too, and so nothing here imports pytest.
    `PYTEST_XDIST_WORKER` is set by xdist in each worker process; under a serial
    run it is absent, and the field is then omitted rather than emitted empty.
    """
    return os.environ.get("PYTEST_XDIST_WORKER")


def _processors(tally: Tally) -> list[Processor]:
    """The processor pipeline, in the order the event passes through it."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        _TallyProcessor(tally),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]


def configure(*, tally: Tally | None = None) -> Tally:
    """Wire the event layer onto stdlib's logger. Idempotent; returns the tally.

    Deliberately does NOT attach a handler: this module owns the EVENT layer and
    `sinks.py` owns where events go. Keeping the two apart is the whole point of
    picking an event library that ships no sinks — a caller that wants events in
    a file, in a queue, and on stdout attaches three handlers and changes nothing
    here.
    """
    counter = tally if tally is not None else Tally()
    structlog.configure(
        processors=_processors(counter),
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logging.getLogger(LOGGER_NAME).setLevel(logging.DEBUG)
    return counter


def emit(event: str, text: str, *, level: Level = Level.INFO, **fields: object) -> None:
    """Emit one event: a machine name, the human line, and named fields.

    `text` is what the stdout sink prints today, byte-for-byte what the `print`
    it replaced produced. `fields` are what R9 queries. Both, every time — an
    event with no fields is a log line with extra steps, and one with no text
    silently changes a report.
    """
    logger = structlog.get_logger(LOGGER_NAME)
    worker = worker_id()
    if worker is not None:
        fields.setdefault("worker", worker)
    logger.log(int(level), event, **{TEXT_KEY: text}, **fields)


def say(event: str, text: str, **fields: object) -> None:
    """Emit at INFO — ordinary progress and product."""
    emit(event, text, level=Level.INFO, **fields)


def warn(event: str, text: str, **fields: object) -> None:
    """Emit at WARNING — the run continued, and a verification pass must see this.

    This is the level R9 exists for. Reach for it whenever the old code would
    have printed something a reader could scroll past.
    """
    emit(event, text, level=Level.WARNING, **fields)


def fail(event: str, text: str, **fields: object) -> None:
    """Emit at ERROR — the thing being reported did not work."""
    emit(event, text, level=Level.ERROR, **fields)
