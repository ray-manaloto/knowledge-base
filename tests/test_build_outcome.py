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


def test_an_unreadable_record_fails_closed_on_more_than_bad_json(tmp_path, monkeypatch) -> None:
    """A PermissionError is a record we could not READ, not one that is absent.

    The first version caught every `OSError` and returned None, so a record whose
    permissions changed fell back to "never run" — failing OPEN against this
    module's own stated contract, in the one direction it exists to prevent.
    (Cold lane, P2.)
    """
    path = build_outcome.record_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")

    real = Path.read_text

    def _denied(self: Path, *args: str | None, **kwargs: str | None) -> str:
        if self == path:
            raise PermissionError("denied")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _denied)
    assert build_outcome.read(tmp_path) is not None
    assert build_outcome.describe(tmp_path)


def test_a_missing_record_is_still_absent_not_unreadable(tmp_path) -> None:
    """FileNotFoundError must remain the ONE OSError that means "absent".

    Control arm for the test above: without it, a `read` that returned a
    BuildFailure for everything would pass that test and still be broken.
    """
    assert build_outcome.read(tmp_path) is None
    assert build_outcome.describe(tmp_path) is None


def test_a_failed_write_says_so_on_stderr(tmp_path, monkeypatch, capsys) -> None:
    """Swallowed, but never silent.

    Without a diagnostic the record fails to write, every later check reports
    "never run", and nothing anywhere says why — the exact ambiguity this module
    removes, restored by its own error path. (Cold lane, P2.)
    """

    def _no_write(*_args: object, **_kwargs: object) -> Never:
        raise OSError("read-only filesystem")

    monkeypatch.setattr(build_outcome.Path, "write_text", _no_write)
    build_outcome.record_failure(tmp_path, "build", "SystemExit: refused")

    assert build_outcome.read(tmp_path) is None
    err = capsys.readouterr().err
    assert "could not record the build failure" in err
    assert "read-only filesystem" in err


def test_an_interrupt_is_not_reported_as_a_defect(tmp_path, monkeypatch) -> None:
    """Ctrl-C leaves no stamp, but it is not a defect and a re-run may well work.

    Both halves matter: calling an interrupt "never run" is a lie, and calling it
    a DEFECT that "will fail again" is a different lie. (Cold lane, P2.)
    """
    from kb_setup import graph

    def _interrupt(_root: Path) -> Never:
        raise KeyboardInterrupt

    monkeypatch.setattr(graph, "build", _interrupt)
    with pytest.raises(KeyboardInterrupt):
        cli._build_checked(tmp_path)

    recorded = build_outcome.read(tmp_path)
    assert recorded is not None
    assert recorded.stage == build_outcome.INTERRUPTED

    described = build_outcome.describe(tmp_path)
    assert described is not None
    assert described.kind == build_outcome.INTERRUPTED
    assert "INTERRUPTED" in described.text
    assert "DEFECT" not in described.text
    assert "will fail again" not in described.text

    # CONTROL ARM: a real build failure in the same repo still says DEFECT, so
    # this test discriminates on the stage rather than on the wording softening
    # for everything.
    build_outcome.record_failure(tmp_path, "build", "SystemExit: refused")
    other = build_outcome.describe(tmp_path)
    assert other is not None
    assert other.kind == build_outcome.FAILED
    assert "DEFECT" in other.text


def test_a_successful_build_supersedes_a_record_it_could_not_delete(tmp_path) -> None:
    """The MIRROR of this module's first defect, found by the cold lane (round 2, P1).

    `clear()` is best-effort, and once the record outranked the stamp, a
    `clear()` that failed left a SUCCESSFUL build reporting a DEFECT forever with
    no path back. Comparing against the stamp's own `built_at` self-heals, which
    is why the supersession lives in `describe` rather than in `clear`.
    """
    build_outcome.record_failure(tmp_path, "build", "SystemExit: refused")
    failure = build_outcome.read(tmp_path)
    assert failure is not None

    # CONTROL ARM: an OLDER stamp must NOT supersede — otherwise this test would
    # pass for a `describe` that ignored the record whenever any stamp existed,
    # which is the original P1 in a new coat.
    assert build_outcome.describe(tmp_path, stamp_built_at="2001-01-01T00:00:00+00:00")
    assert build_outcome.describe(tmp_path, stamp_built_at="") is not None

    later = "2099-01-01T00:00:00+00:00"
    assert build_outcome.describe(tmp_path, stamp_built_at=later) is None


def test_supersession_refuses_to_act_on_a_timestamp_it_cannot_trust(tmp_path) -> None:
    """Ambiguity keeps REPORTING the failure — the two errors are not symmetric.

    Wrongly ignoring a live failure reports OK for a broken build, which is #397
    itself. Wrongly keeping a stale record reports a defect that one successful
    build clears. So every unreadable form must fall on the reporting side —
    including a NAIVE datetime, which would otherwise raise on comparison and
    abort the whole check rather than answer it.
    """
    build_outcome.record_failure(tmp_path, "build", "SystemExit: refused")
    for untrusted in ("", "not-a-timestamp", "2099-01-01T00:00:00", "2099-01-01"):
        assert build_outcome.describe(tmp_path, stamp_built_at=untrusted) is not None, untrusted


def test_a_failed_clear_says_so(tmp_path, monkeypatch, capsys) -> None:
    """A surviving record now outranks the stamp, so failing to remove one matters."""
    build_outcome.record_failure(tmp_path, "build", "SystemExit: refused")

    def _cannot(*_args: object, **_kwargs: object) -> Never:
        raise PermissionError("cannot remove")

    monkeypatch.setattr(build_outcome.Path, "unlink", _cannot)
    build_outcome.clear(tmp_path)
    assert "could not clear the stale build-failure record" in capsys.readouterr().err


def test_a_broken_stderr_never_replaces_the_build_exception(tmp_path, monkeypatch) -> None:
    """`print` can raise — a BrokenPipeError IS an OSError.

    `record_failure` runs inside an `except` while a build exception is already
    propagating, so a raise here would REPLACE that exception with an unrelated
    IO one and hide why the build actually failed. (Cold lane round 2, P2.)
    """

    def _no_write(*_args: object, **_kwargs: object) -> Never:
        raise OSError("read-only filesystem")

    def _broken_print(*_args: object, **_kwargs: object) -> Never:
        raise BrokenPipeError("stderr is gone")

    monkeypatch.setattr(build_outcome.Path, "write_text", _no_write)
    monkeypatch.setattr("builtins.print", _broken_print)

    # Must not raise. Before the fix this propagated BrokenPipeError.
    build_outcome.record_failure(tmp_path, "build", "SystemExit: refused")


def test_supersession_needs_about_a_second_because_built_at_truncates(tmp_path) -> None:
    """The stated CONDITION, pinned so nobody rediscovers it as a bug.

    A stamp's `built_at` is written with `timespec="seconds"`, so it truncates
    DOWN by up to a second while `failed_at` keeps microseconds. Under a strict
    `>` that means a stamp from the SAME second does not supersede. Harmless for
    a build that takes minutes — and it is exactly what a compressed probe shows,
    which is the probe's artifact and not this function's defect.
    """
    build_outcome.record_failure(tmp_path, "build", "SystemExit: refused")
    failure = build_outcome.read(tmp_path)
    assert failure is not None

    from datetime import datetime, timedelta

    failed = datetime.fromisoformat(failure.failed_at)
    same_second = failed.replace(microsecond=0).isoformat(timespec="seconds")
    next_second = (failed + timedelta(seconds=1)).isoformat(timespec="seconds")

    assert build_outcome.describe(tmp_path, stamp_built_at=same_second) is not None
    assert build_outcome.describe(tmp_path, stamp_built_at=next_second) is None


def test_the_failed_message_does_not_overclaim_the_next_attempt(tmp_path) -> None:
    """The prose fix: a persisted record never re-tests its own cause.

    Before this fix `describe()` unconditionally asserted "re-running
    `mise run kb-build` will fail again" from a note this function never
    re-tests — a claim a real record kept making on every session start for
    three days after the file it named had already stopped existing. `DEFECT`
    must still be said (control arm, same as the existing interrupt test's);
    the unconditional future claim must not, and the message must say the
    record does not re-test its own cause so a reader knows to just re-run it.
    """
    build_outcome.record_failure(tmp_path, "build", "SystemExit: refused")
    described = build_outcome.describe(tmp_path)
    assert described is not None
    assert described.kind == build_outcome.FAILED
    assert "DEFECT" in described.text
    assert "will fail again" not in described.text
    assert "does not re-test its own cause" in described.text


def test_undecodable_bytes_do_not_escape_the_reader(tmp_path) -> None:
    """A decode error must not escape the reader; `UnicodeError` is no `OSError`.

    `except OSError` around `read_text` therefore let a decode error propagate
    out of `read()` and abort the whole currency check rather than answer it —
    reproduced with invalid UTF-8 before the fix. Same class as the diagnostic
    that could replace the build exception, through a door the first fix missed.
    """
    path = build_outcome.record_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe\x00not utf-8 \xc3\x28")

    failure = build_outcome.read(tmp_path)
    assert failure is not None, "must fail CLOSED, not raise and not report absent"
    assert build_outcome.describe(tmp_path) is not None

    # CONTROL ARM: valid UTF-8 in the same slot still parses normally, so this
    # is discriminating on decodability and not on the reader being inert.
    build_outcome.record_failure(tmp_path, "build", "SystemExit: refused")
    good = build_outcome.read(tmp_path)
    assert good is not None
    assert good.stage == "build"


def test_a_non_ascii_summary_is_recorded_not_raised(tmp_path) -> None:
    """A build exception can carry a non-ASCII path or message; it round-trips.

    What this does NOT prove, stated because the arm settled it: that the
    explicit `encoding="utf-8"` on the WRITE is load-bearing. `json.dumps`
    defaults to `ensure_ascii=True`, so this module's payload is always pure
    ASCII however exotic the summary — `"refusé"` serialises as `"refus\u00e9"`
    — and a mutation writing as `ascii` SURVIVED because it genuinely cannot
    fail. The read half IS reachable (a record corrupted by something else) and
    is armed separately. The encoding argument stays regardless: it costs
    nothing and takes the locale out of a decision it has no business making.
    """
    build_outcome.record_failure(tmp_path, "build", "SystemExit: refusé — Ünicode ✗ 日本語")
    failure = build_outcome.read(tmp_path)
    assert failure is not None
    assert "refusé" in failure.summary
    assert "日本語" in failure.summary
