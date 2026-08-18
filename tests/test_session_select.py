# Copyright (c) 2026 Raymond Manaloto
"""`kb_setup.session_select` — which transcripts a run covers, and by which clock.

EVERY TEST BUILDS ITS OWN TRANSCRIPT DIR. None reads the real one: it holds 238
files and ~300 MB, its contents change while the suite runs, and a test that
passes because this machine happens to have a session from today is a test that
could only pass here. `a-test-must-own-its-own-environment.md`.

The one thing a fixture cannot fake is `st_birthtime`, which is set by the
filesystem at creation and not settable through `os.utime`. So the
birthtime-vs-content cross-check is driven from the CONTENT side — write a
first-record timestamp that disagrees with creation time by more than the slack
and assert the record says `content`. That is the direction that actually
happened in the wild (3 of 238 real transcripts), and it is the one a test can
construct honestly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from kb_setup import session_select as ss
from kb_setup.generated.session_select import ResolvedBy, TimeSource
from kb_setup.result import Err, Ok, Rc


def _transcript(directory: Path, session_id: str, *, first_timestamp: str | None = None) -> Path:
    """One transcript whose header mirrors a real one.

    The first two records of a real transcript are `mode` and `permission-mode`
    and carry NO timestamp — measured, and the reason `_HEADER_LINES` is 20
    rather than 1. Reproducing that here is what makes the parser's bound a
    tested property instead of a guess.
    """
    path = directory / f"{session_id}.jsonl"
    lines = [
        json.dumps({"type": "mode", "sessionId": session_id}),
        json.dumps({"type": "permission-mode", "sessionId": session_id}),
    ]
    if first_timestamp is not None:
        lines.append(json.dumps({"type": "system", "timestamp": first_timestamp}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo root whose transcript dir is real, populated and ours."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    repo.mkdir()
    directory = home / ".claude" / "projects" / ss.brain.encode_cwd(repo)
    directory.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    monkeypatch.delenv("HOME", raising=False)
    return repo


def _dir(repo: Path) -> Path:
    return ss.transcript_dir(repo)


def test_started_at_prefers_the_transcripts_own_clock_when_they_disagree(project: Path) -> None:
    """The 119.6-hour case, from the side a test can construct.

    A resumed session's FILE says when it began; the filesystem says when the
    file was made. When they disagree beyond the slack the file wins, and the
    record must SAY so — a figure that travels without its condition survives
    review and is still wrong where it is used.
    """
    _transcript(
        _dir(project),
        "aaaaaaaa-0000-0000-0000-000000000001",
        first_timestamp="2020-01-01T00:00:00Z",
    )
    (record,) = ss.records(_dir(project))
    assert record.time_source is TimeSource.content
    assert record.started_at.startswith("2020-01-01")


def test_started_at_uses_birthtime_when_the_two_agree(project: Path) -> None:
    """The control arm for the test above: no disagreement, no override.

    Without this, a module that ALWAYS preferred content would pass the
    disagreement test — a check that can only produce one answer.

    On a filesystem WITHOUT `st_birthtime` the honest answer is `mtime`, and
    the expectation says so. This test used to assert `birthtime`
    unconditionally and passed on such hosts anyway — because the fallback
    mislabelled its clock, which is exactly the defect the mtime test below
    now pins.
    """
    path = _transcript(_dir(project), "aaaaaaaa-0000-0000-0000-000000000002")
    has_birthtime = getattr(path.stat(), "st_birthtime", None) is not None
    (record,) = ss.records(_dir(project))
    assert record.time_source is (TimeSource.birthtime if has_birthtime else TimeSource.mtime)


def test_the_mtime_last_resort_says_mtime_not_birthtime(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No birthtime, no content timestamp — the fallback must NAME its clock.

    It reported itself as `birthtime` until 2026-08-18: the one clock it did
    not use, on exactly the record whose reader most needs to distrust mtime.
    `st_birthtime` cannot be unset on a filesystem that has it, so it is hidden
    by wrapping `stat` — the same one-direction constraint the module docstring
    already concedes for the cross-check tests.
    """
    _transcript(_dir(project), "aaaaaaaa-0000-0000-0000-000000000005")
    real_stat = Path.stat

    class _NoBirthtime:
        def __init__(self, inner: os.stat_result) -> None:
            self._inner = inner

        def __getattr__(self, name: str) -> object:
            if name == "st_birthtime":
                raise AttributeError(name)
            return getattr(self._inner, name)

    monkeypatch.setattr(Path, "stat", lambda self, **kw: _NoBirthtime(real_stat(self, **kw)))
    (record,) = ss.records(_dir(project))
    assert record.time_source is TimeSource.mtime
    assert record.started_at == record.last_written


def test_records_sort_by_start_not_by_mtime(project: Path) -> None:
    """Sorting by mtime is the same defect as filtering by it.

    An old session touched a moment ago must NOT come back as the newest — that
    is precisely the reopened-subagent case that makes `--last N` pick the wrong
    files.
    """
    directory = _dir(project)
    old = _transcript(
        directory, "aaaaaaaa-0000-0000-0000-00000000000a", first_timestamp="2020-01-01T00:00:00Z"
    )
    _transcript(
        directory, "aaaaaaaa-0000-0000-0000-00000000000b", first_timestamp="2026-01-01T00:00:00Z"
    )
    os.utime(old, (2_000_000_000, 2_000_000_000))  # touched far in the future

    ordered = [r.session_id for r in ss.records(directory)]
    assert ordered[0].endswith("000b"), "an mtime-touched old session sorted first"


def test_an_empty_resolution_refuses_rather_than_returning_nothing(project: Path) -> None:
    """`[]` with rc 0 is how a review silently covers nothing.

    `Rc.NOT_RUN`, not `FINDINGS` and not `OK` — the question was asked and no
    session answered it, which is a third state.
    """
    _transcript(
        _dir(project),
        "aaaaaaaa-0000-0000-0000-000000000003",
        first_timestamp="2026-01-01T00:00:00Z",
    )
    result = ss.resolve(["--since", "2030-01-01"], project)
    assert isinstance(result, Err)
    assert result.rc is Rc.NOT_RUN
    assert "transcript(s) were examined" in result.message, "a refusal must say what it looked at"


def test_an_unknown_session_id_never_returns_a_partial_list(project: Path) -> None:
    """Returning the ids that DID resolve is how a review covers less than asked."""
    good = "aaaaaaaa-0000-0000-0000-000000000004"
    _transcript(_dir(project), good, first_timestamp="2026-01-01T00:00:00Z")
    result = ss.resolve(["--sessions", good, "bbbbbbbb-0000-0000-0000-000000000000"], project)
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert "bbbbbbbb" in result.message


def test_a_missing_transcript_dir_names_the_path_it_derived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A wrong cwd produces a plausible directory that does not exist.

    Printing the DERIVED path is what makes that visible instead of looking like
    a round with no sessions.
    """
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "nowhere"))
    result = ss.resolve(["--last", "1"], tmp_path / "repo")
    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert "projects" in result.message


@pytest.mark.parametrize(
    ("args", "why"),
    [
        ([], "no selector"),
        (["--current", "--last", "2"], "two selectors"),
        (["--until", "2026-01-01"], "--until without --since"),
        (["--since", "not-a-date"], "unparsable bound"),
        (["--last", "0"], "--last must be positive"),
        (["--last"], "flag with no value"),
        (["--sessions", "../../etc/passwd"], "path traversal is not an id"),
        (["--nope"], "unknown flag"),
        # A repeated flag OVERWROTE the earlier value until 2026-08-18, so
        # `--sessions a --sessions b` reviewed only b — a silently narrowed
        # scope, which is the partial-list defect above in flag form.
        (
            [
                "--sessions",
                "aaaaaaaa-0000-0000-0000-000000000001",
                "--sessions",
                "aaaaaaaa-0000-0000-0000-000000000002",
            ],
            "repeated --sessions",
        ),
        (["--last", "2", "--last", "9"], "repeated --last"),
        (["--since", "2026-01-01", "--since", "2026-02-01"], "repeated --since"),
        (
            ["--since", "2026-01-01", "--until", "2026-02-01", "--until", "2026-03-01"],
            "repeated --until",
        ),
    ],
)
def test_a_malformed_request_is_rejected(args: list[str], why: str) -> None:
    result = ss.parse(args)
    assert isinstance(result, Err), f"accepted a bad request: {why}"
    assert result.rc is Rc.BAD_REQUEST


def test_a_valid_request_parses(project: Path) -> None:
    """The control arm for the table above — it must be able to say yes."""
    for args in (
        ["--current"],
        ["--last", "3"],
        ["--since", "2026-01-01", "--until", "2026-02-01"],
    ):
        assert isinstance(ss.parse(args), Ok), f"rejected a valid request: {args}"


def test_current_falls_back_and_says_it_fell_back(project: Path) -> None:
    """No graph-first state means the fallback route, REPORTED as such.

    A resolution nobody can audit afterwards is the shape this module replaces.
    """
    _transcript(
        _dir(project),
        "aaaaaaaa-0000-0000-0000-000000000005",
        first_timestamp="2026-01-01T00:00:00Z",
    )
    result = ss.resolve(["--current"], project)
    assert isinstance(result, Ok)
    assert result.value.resolved_by is ResolvedBy.newest_birthtime
    caveat = result.value.caveat
    assert isinstance(caveat, str)
    assert "fell back" in caveat


def test_current_prefers_the_graph_first_state_and_caveats_a_disagreement(project: Path) -> None:
    """Two interleaved sessions: hook traffic wins, and the conflict is reported."""
    directory = _dir(project)
    older = "aaaaaaaa-0000-0000-0000-000000000006"
    newer = "aaaaaaaa-0000-0000-0000-000000000007"
    _transcript(directory, older, first_timestamp="2026-01-01T00:00:00Z")
    _transcript(directory, newer, first_timestamp="2026-06-01T00:00:00Z")
    state = project / ".agent" / "state" / "graph-first"
    state.mkdir(parents=True)
    (state / f"{older}.queried").write_text("", encoding="utf-8")

    result = ss.resolve(["--current"], project)
    assert isinstance(result, Ok)
    assert result.value.sessions[0].session_id == older, "the hook-traffic route must win"
    assert result.value.resolved_by is ResolvedBy.graph_first_state
    caveat = result.value.caveat
    assert isinstance(caveat, str)
    assert "interleaving" in caveat


def test_the_window_is_echoed_even_for_a_non_time_selector(project: Path) -> None:
    """A consumer must distinguish 'no window asked' from 'window matched nothing'."""
    _transcript(
        _dir(project),
        "aaaaaaaa-0000-0000-0000-000000000008",
        first_timestamp="2026-01-01T00:00:00Z",
    )
    result = ss.resolve(["--last", "1"], project)
    assert isinstance(result, Ok)
    assert result.value.window.since is None
    assert result.value.window.until is None


def test_the_output_round_trips_through_the_generated_contract(project: Path) -> None:
    """The JSON is a cross-surface contract — decoding it back is the arm.

    `forbid_unknown_fields` on the generated Struct means a field this module
    invents but the schema does not declare fails HERE rather than silently
    reaching the workflow.
    """
    import msgspec

    _transcript(
        _dir(project),
        "aaaaaaaa-0000-0000-0000-000000000009",
        first_timestamp="2026-01-01T00:00:00Z",
    )
    result = ss.resolve(["--last", "1"], project)
    assert isinstance(result, Ok)
    encoded = msgspec.json.encode(result.value)
    back = msgspec.json.decode(encoded, type=type(result.value))
    assert back.schema_version == 1
    assert back.sessions[0].session_id.endswith("0009")


def test_a_window_bound_and_a_start_are_comparable_as_strings(project: Path) -> None:
    """The cold lane's P1: `_window` compares ISO strings, so widths must match.

    `_iso` emitted microseconds and `_normalise` emitted none, and
    `"...T00:00:00.123456Z" >= "...T00:00:00Z"` is FALSE because `.` sorts below
    `Z`. A session starting inside the first second of the window was silently
    excluded — the exact silent-loss shape this module refuses everywhere else.

    Everyday use hides it: `--since 2026-08-18` against a session that began at
    16:33 compares fine. Only a start in the bound's own second exposes it, which
    is why no existing test found it.
    """
    bound = ss._normalise("2026-08-18")
    assert bound is not None
    assert len(bound) == len(ss._iso(1_787_000_000.123456))

    _transcript(
        _dir(project),
        "aaaaaaaa-0000-0000-0000-00000000000c",
        first_timestamp="2026-03-01T00:00:00.5Z",
    )
    result = ss.resolve(["--since", "2026-03-01T00:00:00Z"], project)
    assert isinstance(result, Ok), "a session starting 0.5s into the window was dropped"
    assert result.value.sessions[0].session_id.endswith("000c")
