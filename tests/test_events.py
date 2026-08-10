# Copyright (c) 2026 Raymond Manaloto
"""Tests for §2.5's event stream and its sinks."""

from __future__ import annotations

import io
import json
import logging
import logging.handlers
import queue
from typing import TYPE_CHECKING

import pytest
from kb_setup import events
from kb_setup.events import Level, Tally, configure, emit, fail, say, warn
from kb_setup.sinks import EventQueueHandler, HumanSink, JsonlSink, stdout_sink

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _configured() -> None:
    """Every test gets a freshly-wired event layer."""
    configure()


def _buf() -> io.StringIO:
    """A buffer to point a sink at instead of the terminal."""
    return io.StringIO()


# --- the property the whole conversion rests on --------------------------------


def test_text_is_rendered_verbatim() -> None:
    """A converted `print` must produce a byte-identical line.

    Otherwise the existing assertions about what a task prints stop being a
    regression arm — recipe rule 2, applied to output rather than exit codes.
    """
    buf = _buf()
    with stdout_sink(stream=buf, offload=False):
        say("land.merge", "==> merging PR #42 pinned to abc123def456")
    assert buf.getvalue() == "==> merging PR #42 pinned to abc123def456\n"


def test_fields_ride_alongside_the_text() -> None:
    """The line is unchanged; the structure is what R9 queries."""
    buf = _buf()
    with stdout_sink(stream=buf, offload=False):
        say("land.merge", "==> merging PR #42", pr=42, oid="abc123")
    assert buf.getvalue().strip() == "==> merging PR #42"


def test_warning_is_marked_so_it_cannot_be_scrolled_past() -> None:
    """R9's subject: kb-build buried 1,024 of these in an rc=0 run."""
    buf = _buf()
    with stdout_sink(stream=buf, offload=False):
        warn("build.node_loss", "node X is minted by two different files")
    assert buf.getvalue().startswith("WARNING: ")


def test_error_is_marked() -> None:
    buf = _buf()
    with stdout_sink(stream=buf, offload=False):
        fail("merge.refused", "to_json refused (shrink guard #479)")
    assert buf.getvalue().startswith("ERROR: ")


def test_info_is_not_decorated() -> None:
    """kb-gates' report must look exactly as it does now."""
    buf = _buf()
    with stdout_sink(stream=buf, offload=False):
        say("gate.pass", "  lint         PASS")
    assert buf.getvalue() == "  lint         PASS\n"


# --- R9: the tally is the assertion a buried warning fails ---------------------


def test_tally_counts_by_level() -> None:
    tally = configure()
    buf = _buf()
    with stdout_sink(stream=buf, offload=False):
        say("a", "one")
        warn("b", "two")
        fail("c", "three")
    assert tally.above(Level.WARNING) == 2
    assert tally.above(Level.ERROR) == 1


def test_tally_is_zero_on_a_clean_run() -> None:
    """CONTROL ARM: the tally must be able to report nothing, or it proves nothing."""
    tally = configure()
    buf = _buf()
    with stdout_sink(stream=buf, offload=False):
        say("a", "one")
        say("b", "two")
    assert tally.above(Level.WARNING) == 0


def test_tally_counts_events_a_handler_would_filter() -> None:
    """A tally that only counts what PRINTED cannot answer 'was anything suppressed'."""
    tally = configure()
    buf = _buf()
    with stdout_sink(stream=buf, offload=False):
        logging.getLogger(events.LOGGER_NAME).setLevel(logging.ERROR)
        warn("suppressed", "not printed")
    assert tally.above(Level.WARNING) == 1


def test_tally_summary_reads() -> None:
    tally = configure()
    buf = _buf()
    with stdout_sink(stream=buf, offload=False):
        warn("a", "one")
    assert "warning=1" in tally.summary()
    assert Tally().summary() == "no events"


# --- the JSONL sink: R9's queryable surface ------------------------------------


def test_jsonl_sink_writes_one_object_per_event(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    buf = io.StringIO()
    with stdout_sink(stream=buf, jsonl_path=path, offload=False):
        warn("build.node_loss", "node X minted twice", node="X", source_file="a.py")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["event"] == "build.node_loss"
    assert rows[0]["node"] == "X"
    assert rows[0]["level"] == "warning"


def test_jsonl_makes_the_r9_question_a_filter(tmp_path: Path) -> None:
    """'Did this run emit anything at WARNING or above' over a real file."""
    path = tmp_path / "events.jsonl"
    buf = io.StringIO()
    with stdout_sink(stream=buf, jsonl_path=path, offload=False):
        say("ok", "0 dangling, 0 malformed")
        warn("loss", "1,024 nodes minted twice")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    loud = [r for r in rows if r["level"] in {"warning", "error"}]
    assert len(loud) == 1
    assert loud[0]["event"] == "loss"


# --- R7: the offload, and that it loses nothing --------------------------------


def test_offload_delivers_every_record() -> None:
    """QueueListener IS the logging thread (R7). It must drain before we look."""
    buf = io.StringIO()
    with stdout_sink(stream=buf, offload=True):
        for i in range(50):
            say("bulk", f"line {i}")
    assert buf.getvalue().count("line ") == 50


def test_queue_handler_keeps_the_event_dict_intact() -> None:
    """The defect this override exists for, armed directly.

    Stdlib's `QueueHandler.prepare()` replaces `record.msg` with a formatted
    STRING. Through it, the listener hands ProcessorFormatter a `str` and the
    render raises inside the logging machinery — which swallows handler errors,
    so the symptom is missing output rather than a traceback. Asserting on the
    type is the arm; the two offload tests below would also fail, but only after
    the fact and without naming the cause.
    """
    record = logging.LogRecord(
        events.LOGGER_NAME, logging.INFO, "", 0, {"event": "e", "text": "t"}, (), None
    )
    prepared = EventQueueHandler(queue.Queue(-1)).prepare(record)
    assert isinstance(prepared.msg, dict), "stringified — ProcessorFormatter cannot read this"

    stdlib_prepared = logging.handlers.QueueHandler(queue.Queue(-1)).prepare(record)
    assert isinstance(stdlib_prepared.msg, str), "CONTROL: stdlib is expected to stringify"


def test_offload_installs_a_queue_handler() -> None:
    """What THIS module owns: with `offload`, the logger's handler is the queue.

    Scoped deliberately. That the QueueListener runs on another thread is
    stdlib's behaviour and was measured with a control arm in the D20 report;
    re-asserting it here would be testing CPython. What is ours is the wiring —
    and that the tail of the stream survives it, which the next test covers.
    """
    logger = logging.getLogger(events.LOGGER_NAME)
    buf = io.StringIO()
    with stdout_sink(stream=buf, offload=True):
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.handlers.QueueHandler)


def test_offload_drains_before_the_file_closes(tmp_path: Path) -> None:
    """An offloaded run must not lose its tail.

    The bug this ordering nearly shipped: flushing before the listener drains
    writes nothing to the JSONL sink and looks perfectly fine on stdout.
    """
    path = tmp_path / "events.jsonl"
    buf = io.StringIO()
    with stdout_sink(stream=buf, jsonl_path=path, offload=True):
        for i in range(25):
            warn("bulk", f"line {i}", i=i)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 25, "the tail of an offloaded run was lost"


# --- the sink must not drop what it does not recognise -------------------------


def test_a_plain_stdlib_record_still_renders() -> None:
    """A third-party library's warning must survive — dropping it is the R9 defect."""
    record = logging.LogRecord("somelib", logging.WARNING, "", 0, "disk almost full", (), None)
    assert HumanSink().format(record) == "WARNING: disk almost full"


def test_an_event_with_no_text_falls_back_to_its_fields() -> None:
    """The direction of travel: a caller that stopped hand-writing lines."""
    record = logging.LogRecord(
        "kb_setup", logging.INFO, "", 0, {"event": "gate.pass", "gate": "lint", "rc": 0}, (), None
    )
    rendered = HumanSink().format(record)
    assert rendered.startswith("gate.pass")
    assert "gate=lint" in rendered
    assert "rc=0" in rendered


def test_jsonl_renders_an_unrecognised_record_too() -> None:
    record = logging.LogRecord("somelib", logging.ERROR, "", 0, "boom", (), None)
    row = json.loads(JsonlSink().format(record))
    assert row["level"] == "error"
    assert row["text"] == "boom"


# --- handler hygiene: the suite runs under -n auto -----------------------------


def test_handlers_are_restored_on_exit() -> None:
    """A leaked handler under -n auto is a duplicated line with no obvious owner."""
    logger = logging.getLogger(events.LOGGER_NAME)
    before = list(logger.handlers)
    buf = io.StringIO()
    with stdout_sink(stream=buf, offload=False):
        say("x", "y")
    assert logger.handlers == before


def test_handlers_are_restored_after_an_exception() -> None:
    logger = logging.getLogger(events.LOGGER_NAME)
    before = list(logger.handlers)
    buf = io.StringIO()

    def _boom() -> None:
        with stdout_sink(stream=buf, offload=False):
            say("x", "y")
            raise RuntimeError

    with pytest.raises(RuntimeError):
        _boom()
    assert logger.handlers == before


# --- R12: worker attribution ---------------------------------------------------


def test_worker_field_is_added_under_xdist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Under -n auto every worker writes to one stdout; an event says which."""
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")
    path_buf = io.StringIO()
    with stdout_sink(stream=path_buf, offload=False):
        emit("t", "hello", level=Level.INFO)
    assert events.worker_id() == "gw3"


def test_worker_field_is_omitted_when_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTROL ARM: absent rather than emitted empty."""
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    assert events.worker_id() is None
