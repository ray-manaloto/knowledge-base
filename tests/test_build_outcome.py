# Copyright (c) 2026 Raymond Manaloto
"""#397: `kb-build`'s outcome must survive the run that produced it.

The module's own read/write behaviour is covered here; the two CONSUMERS —
`currency.sync` and `currency.staleness` — are armed in their own suites, since
what matters there is the sentence a reader ends up seeing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Never

import pytest
from kb_setup import build_outcome, cli


def test_a_failing_build_records_and_a_succeeding_one_clears(tmp_path, monkeypatch) -> None:
    """The wiring, not the module: `_build_checked` is the only entry point.

    Armed in both directions on purpose. A recorder verified only on the failure
    path leaves the far worse bug uncovered — a stale record outliving a build
    that has since succeeded, which reports a DEFECT that no longer exists.
    """
    from kb_setup import graph, graphify_health

    def _boom(_root: Path) -> Never:
        raise SystemExit("Graphify detect preflight failed for 1 source(s)")

    monkeypatch.setattr(graph, "build", _boom)
    with pytest.raises(SystemExit):
        cli._build_checked(tmp_path)

    recorded = build_outcome.read(tmp_path)
    assert recorded is not None
    assert recorded.stage == "build"
    assert "detect preflight failed" in recorded.summary
    assert recorded.failed_at

    monkeypatch.setattr(graph, "build", lambda _root: None)
    monkeypatch.setattr(graphify_health, "require_complete", lambda _receipt: None)
    assert cli._build_checked(tmp_path) == 0
    assert build_outcome.read(tmp_path) is None


def test_a_systemexit_is_recorded_even_though_it_is_not_an_exception(tmp_path, monkeypatch):
    """`graph.build` refuses with SystemExit, which `except Exception` misses.

    This is the realistic break: catching `Exception` here would leave the single
    most common failure — the detect preflight refusal #397 was filed from —
    unrecorded, and the check would go on saying "never run".
    """
    from kb_setup import graph

    monkeypatch.setattr(graph, "build", lambda _root: (_ for _ in ()).throw(SystemExit("refused")))
    with pytest.raises(SystemExit):
        cli._build_checked(tmp_path)
    assert build_outcome.read(tmp_path) is not None


def test_recording_never_replaces_the_failure_it_records(tmp_path, monkeypatch) -> None:
    """An unwritable `graphify-out/` must not convert a build failure into an IO one."""

    def _no_write(*_args: object, **_kwargs: object) -> Never:
        raise OSError("read-only filesystem")

    monkeypatch.setattr(build_outcome.Path, "write_text", _no_write)
    build_outcome.record_failure(tmp_path, "build", "SystemExit: refused")
    assert build_outcome.read(tmp_path) is None


def test_reading_fails_closed_on_a_record_it_cannot_parse(tmp_path) -> None:
    """A corrupt record still means a build ran and failed.

    Degrading to None would restore exactly the confusion this module removes,
    and would do it silently.
    """
    path = build_outcome.record_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    for corrupt in ("{not json", "[]", '"a string"', "null"):
        path.write_text(corrupt, encoding="utf-8")
        failure = build_outcome.read(tmp_path)
        assert failure is not None, corrupt
        assert build_outcome.describe(tmp_path)

    # CONTROL ARM: the same reader returns None when the file is genuinely absent.
    path.unlink()
    assert build_outcome.read(tmp_path) is None
    assert build_outcome.describe(tmp_path) is None


def test_the_recorded_timestamp_is_timezone_aware(tmp_path) -> None:
    """A naive timestamp raises the moment anything subtracts an aware one from it."""
    from datetime import datetime

    build_outcome.record_failure(tmp_path, "build", "boom")
    payload = json.loads(build_outcome.record_path(tmp_path).read_text())
    assert datetime.fromisoformat(payload["failed_at"]).tzinfo is not None


def test_a_pathological_summary_is_bounded(tmp_path) -> None:
    """A detect dump is ~900 chars PER SOURCE; 73 of them must not become the record."""
    build_outcome.record_failure(tmp_path, "build", "x" * 50_000)
    failure = build_outcome.read(tmp_path)
    assert failure is not None
    assert len(failure.summary) == build_outcome._MAX_SUMMARY
