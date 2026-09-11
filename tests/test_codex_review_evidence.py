# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.codex_review_evidence` — #750 Phase 1.

Every fixture JSONL shape here was copied from REAL rollouts on this machine
(2026-09-10, codex-cli 0.154.0) — a completed review, an aborted one (the
model-rejected-by-the-API arm from the advisor's own live measurement), and
the exact `session_meta`/`turn_context` field nesting. This is not guessed
from the Rust source; it is what the installed CLI actually wrote to disk.
Every FAIL arm below has its matching PASS arm, per
`probes-need-a-control-arm.md`.
"""

from __future__ import annotations

import json
import stat
import threading
import time
from pathlib import Path

import pytest
from kb_setup import codex_review_evidence as ev
from kb_setup.currency import sync

_PARENT = "01a08cab-2bee-7af3-94f4-dea1e867d769"


def _attempt(
    tmp_path: Path,
    *,
    output_path: Path | None,
    codex_home: Path | None = None,
    requested_model: str | None = None,
) -> ev.CodexAttempt:
    return ev.CodexAttempt(
        attempt_id="test-attempt",
        codex_home=str(codex_home if codex_home is not None else tmp_path / "codex-home"),
        cli_version="0.154.0",
        requested_model=requested_model,
        requested_effort="xhigh",
        base_ref="HEAD~1",
        subprocess_rc=0,
        timed_out=False,
        output_path=output_path,
    )


def _banner(path: Path, session_id: str = _PARENT, *, styled: bool = False) -> None:
    """Write a `--output` tee whose shape matches the real CLI banner."""
    key = "\x1b[1msession id:\x1b[0m" if styled else "session id:"
    path.write_text(
        f"OpenAI Codex v0.154.0\n--------\nmodel: gpt-6-astra\n{key} {session_id}\n--------\n",
        encoding="utf-8",
    )


def _session_meta_line(*, parent: str, source: object, child_id: str = "child-1") -> str:
    return json.dumps(
        {
            "type": "session_meta",
            "payload": {
                "session_id": "irrelevant",
                "id": child_id,
                "parent_thread_id": parent,
                "cwd": "/repo",
                "originator": "codex_exec",
                "cli_version": "0.154.0",
                "source": source,
                "thread_source": "subagent",
            },
        }
    )


def _turn_context_line(model: str | None, *, effort: str = "xhigh") -> str:
    payload: dict[str, object] = {"turn_id": "t1", "root_turn_id": "r1", "effort": effort}
    if model is not None:
        payload["model"] = model
    return json.dumps({"type": "turn_context", "payload": payload})


def _task_complete_line(*, last_agent_message: str | None, error: dict[str, object] | None) -> str:
    payload: dict[str, object] = {
        "type": "task_complete",
        "turn_id": "t1",
        "last_agent_message": last_agent_message,
    }
    if error is not None:
        payload["error"] = error
    return json.dumps({"type": "event_msg", "payload": payload})


def _write_child(
    sessions_root: Path,
    filename: str,
    lines: list[str],
) -> Path:
    path = sessions_root / "2026" / "09" / "10" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _completed_child(
    sessions_root: Path,
    *,
    parent: str = _PARENT,
    filename: str = "rollout-child-1.jsonl",
    model: str = "gpt-6-astra",
) -> Path:
    """A rollout matching the REAL successful-review shape measured this session."""
    return _write_child(
        sessions_root,
        filename,
        [
            _session_meta_line(parent=parent, source={"subagent": "review"}),
            _turn_context_line(model),
            _task_complete_line(last_agent_message="NO FINDINGS", error=None),
        ],
    )


# ---------------------------------------------------------------------------
# capture_attempt
# ---------------------------------------------------------------------------


def test_capture_attempt_reads_codex_home_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_HOME", "/custom/codex/home")
    monkeypatch.setattr(sync, "observed_version", lambda *_a, **_kw: "0.154.0")
    attempt = ev.capture_attempt(
        requested_model="gpt-5.6-sol",
        requested_effort="xhigh",
        base_ref="origin/main",
        subprocess_rc=0,
        timed_out=False,
        output_path=None,
    )
    assert attempt.codex_home == "/custom/codex/home"
    assert attempt.cli_version == "0.154.0"
    assert attempt.attempt_id  # non-empty


def test_capture_attempt_falls_back_to_home_codex_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTROL ARM: never hardcoded, but a sane default when genuinely unset."""
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(sync, "observed_version", lambda *_a, **_kw: "")
    attempt = ev.capture_attempt(
        requested_model=None,
        requested_effort=None,
        base_ref="origin/main",
        subprocess_rc=0,
        timed_out=False,
        output_path=None,
    )
    assert attempt.codex_home == str(Path.home() / ".codex")
    assert attempt.cli_version == "unknown"


# ---------------------------------------------------------------------------
# resolve_reviewer_model — collection-time gaps
# ---------------------------------------------------------------------------


def test_no_output_flag_is_unavailable(tmp_path: Path) -> None:
    attempt = _attempt(tmp_path, output_path=None)
    result = ev.resolve_reviewer_model(attempt)
    assert isinstance(result, ev.Unavailable)
    assert result.reason is ev.UnavailableReason.no_output_flag


def test_output_flag_present_is_the_control_for_the_gap_above(tmp_path: Path) -> None:
    sessions_root = tmp_path / "codex-home" / "sessions"
    _completed_child(sessions_root)
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt)
    assert isinstance(result, ev.Resolved)


def test_a_banner_with_no_session_id_line_is_unavailable(tmp_path: Path) -> None:
    banner = tmp_path / "banner.txt"
    banner.write_text("nothing useful here\n", encoding="utf-8")
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt)
    assert isinstance(result, ev.Unavailable)
    assert result.reason is ev.UnavailableReason.banner_session_id_unavailable


def test_a_styled_banner_line_still_parses(tmp_path: Path) -> None:
    """ANSI-styled output must not defeat the banner parse."""
    sessions_root = tmp_path / "codex-home" / "sessions"
    _completed_child(sessions_root)
    banner = tmp_path / "banner.txt"
    _banner(banner, styled=True)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt)
    assert isinstance(result, ev.Resolved)
    assert result.record.parent_session_id == _PARENT


def test_missing_codex_home_sessions_dir_is_unavailable(tmp_path: Path) -> None:
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner, codex_home=tmp_path / "does-not-exist")
    result = ev.resolve_reviewer_model(attempt)
    assert isinstance(result, ev.Unavailable)
    assert result.reason is ev.UnavailableReason.codex_home_unresolvable


# ---------------------------------------------------------------------------
# resolve_reviewer_model — the join itself
# ---------------------------------------------------------------------------


def test_zero_matching_children_is_unavailable(tmp_path: Path) -> None:
    sessions_root = tmp_path / "codex-home" / "sessions"
    # A child that exists but binds to a DIFFERENT parent — proves the scan
    # discriminates rather than matching anything under sessions/.
    _completed_child(sessions_root, parent="some-other-parent-id")
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Unavailable)
    assert result.reason is ev.UnavailableReason.no_matching_child_rollout


def test_a_matching_child_with_the_wrong_source_does_not_count(tmp_path: Path) -> None:
    """The right parent, the wrong source.

    Binding is BOTH parent_thread_id AND source == {"subagent": "review"} —
    an ordinary `exec` child with the right parent must not match.
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    _write_child(
        sessions_root,
        "rollout-not-review.jsonl",
        [_session_meta_line(parent=_PARENT, source="exec"), _turn_context_line("gpt-6-astra")],
    )
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Unavailable)
    assert result.reason is ev.UnavailableReason.no_matching_child_rollout


def test_two_matching_children_is_ambiguous_not_a_guess(tmp_path: Path) -> None:
    sessions_root = tmp_path / "codex-home" / "sessions"
    _completed_child(sessions_root, filename="rollout-child-1.jsonl", model="gpt-5.6-sol")
    _completed_child(sessions_root, filename="rollout-child-2.jsonl", model="gpt-6-astra")
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Unavailable)
    assert result.reason is ev.UnavailableReason.ambiguous_child_rollout


def test_one_matching_child_among_several_others_resolves(tmp_path: Path) -> None:
    """CONTROL ARM for both gaps above: the scan is selective, not just strict."""
    sessions_root = tmp_path / "codex-home" / "sessions"
    _completed_child(sessions_root, parent="unrelated-1", filename="rollout-a.jsonl")
    _completed_child(sessions_root, parent="unrelated-2", filename="rollout-b.jsonl")
    _completed_child(
        sessions_root, parent=_PARENT, filename="rollout-real.jsonl", model="gpt-5.6-sol"
    )
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Resolved)
    assert result.record.resolved_model == "gpt-5.6-sol"


def test_a_delayed_child_resolves_within_the_retry_budget(tmp_path: Path) -> None:
    """Real persistence lag.

    The child file does not exist yet when resolution starts, and appears a
    moment later. Uses a real background thread and a real filesystem write
    — not a mocked clock.
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    # The ROOT exists already (codex creates it on first use); only the
    # specific rollout FILE is what a real review's persistence lag delays.
    sessions_root.mkdir(parents=True)
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)

    def _write_late() -> None:
        time.sleep(0.15)
        _completed_child(sessions_root)

    threading.Thread(target=_write_late, daemon=True).start()
    result = ev.resolve_reviewer_model(attempt, attempts=10, delay=0.05)
    assert isinstance(result, ev.Resolved)


# ---------------------------------------------------------------------------
# resolve_reviewer_model — the resolved child's own content
# ---------------------------------------------------------------------------


def test_zero_turn_context_records_is_unavailable(tmp_path: Path) -> None:
    sessions_root = tmp_path / "codex-home" / "sessions"
    _write_child(
        sessions_root,
        "rollout-child-1.jsonl",
        [_session_meta_line(parent=_PARENT, source={"subagent": "review"})],
    )
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Unavailable)
    assert result.reason is ev.UnavailableReason.no_turn_context


def test_a_turn_context_with_no_model_field_is_unavailable(tmp_path: Path) -> None:
    """A REALISTIC mutation, not a renamed definition.

    The turn_context record exists but its `model` key is simply absent —
    must not default to the requested or banner model.
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    _write_child(
        sessions_root,
        "rollout-child-1.jsonl",
        [
            _session_meta_line(parent=_PARENT, source={"subagent": "review"}),
            _turn_context_line(None),
        ],
    )
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner, requested_model="gpt-5.6-sol")
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Unavailable)
    assert result.reason is ev.UnavailableReason.missing_model_field


def test_a_later_turn_changing_model_is_recorded_not_dropped(tmp_path: Path) -> None:
    """FAIL-arm 'lane/model agreement'.

    Reading only the FIRST turn would report the wrong model here.
    `turn_models` must carry both, and `resolved_model` must be the LAST one.
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    _write_child(
        sessions_root,
        "rollout-child-1.jsonl",
        [
            _session_meta_line(parent=_PARENT, source={"subagent": "review"}),
            _turn_context_line("gpt-5.6-sol"),
            _turn_context_line("gpt-6-astra"),
        ],
    )
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Resolved)
    assert result.record.turn_models == ["gpt-5.6-sol", "gpt-6-astra"]
    assert result.record.resolved_model == "gpt-6-astra"


def test_requested_and_banner_model_are_never_substituted(tmp_path: Path) -> None:
    """The requested model, banner and turn_context all disagree.

    The requested model is `gpt-5.6-sol`; the banner (parent) is astra by
    construction; the REAL turn_context says something else again. Only the
    turn_context value may ever become `resolved_model`.
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    _completed_child(sessions_root, model="a-third-completely-different-model")
    banner = tmp_path / "banner.txt"
    _banner(banner)  # banner always says "gpt-6-astra" per _banner()
    attempt = _attempt(tmp_path, output_path=banner, requested_model="gpt-5.6-sol")
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Resolved)
    assert result.record.resolved_model == "a-third-completely-different-model"
    assert result.record.requested_model == "gpt-5.6-sol"


# ---------------------------------------------------------------------------
# review completion — measured against the REAL shape, both directions
# ---------------------------------------------------------------------------


def test_a_completed_review_is_recorded_complete(tmp_path: Path) -> None:
    sessions_root = tmp_path / "codex-home" / "sessions"
    _completed_child(sessions_root)
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Resolved)
    assert result.record.review_completion is ev.ReviewCompletion.complete


def test_an_api_rejected_review_is_recorded_aborted(tmp_path: Path) -> None:
    """A review the API rejected outright.

    The REAL bogus-slug shape measured this session: `last_agent_message` is
    null and an `error` object is present.
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    _write_child(
        sessions_root,
        "rollout-child-1.jsonl",
        [
            _session_meta_line(parent=_PARENT, source={"subagent": "review"}),
            _turn_context_line("definitely-not-a-real-model-xyz"),
            _task_complete_line(
                last_agent_message=None,
                error={"message": '{"type":"error","status":400,...}'},
            ),
        ],
    )
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(
        tmp_path, output_path=banner, requested_model="definitely-not-a-real-model-xyz"
    )
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Resolved)
    assert result.record.review_completion is ev.ReviewCompletion.aborted
    # The model was still faithfully recorded, even though the review failed —
    # model-observed and review-happened are two independent facts.
    assert result.record.resolved_model == "definitely-not-a-real-model-xyz"


def test_no_task_complete_event_at_all_is_unknown_not_complete(tmp_path: Path) -> None:
    """A rollout that trails off with no terminal event at all.

    MEASURED, not assumed: a real successful-looking rollout on this host
    trailed off with no `task_complete` event at all (persistence lag). That
    must read as `unknown`, never silently as `complete`.
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    _write_child(
        sessions_root,
        "rollout-child-1.jsonl",
        [
            _session_meta_line(parent=_PARENT, source={"subagent": "review"}),
            _turn_context_line("gpt-6-astra"),
        ],
    )
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Resolved)
    assert result.record.review_completion is ev.ReviewCompletion.unknown


# ---------------------------------------------------------------------------
# resolver failure — a real I/O error, not a renamed definition
# ---------------------------------------------------------------------------


def test_an_unreadable_sessions_dir_is_a_typed_error(tmp_path: Path) -> None:
    """A genuinely unreadable sessions directory is a typed Error, not a guess.

    A REAL permission failure via chmod — not a mocked exception — so this
    proves the resolver's own `except OSError` path, not a mock's promise
    that it would.
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    sessions_root.mkdir(parents=True)
    (sessions_root / "2026").mkdir()
    original_mode = sessions_root.stat().st_mode
    sessions_root.chmod(0)
    try:
        banner = tmp_path / "banner.txt"
        _banner(banner)
        attempt = _attempt(tmp_path, output_path=banner)
        result = ev.resolve_reviewer_model(attempt, attempts=2, delay=0)
        assert isinstance(result, ev.Error)
        assert result.kind is ev.ErrorKind.resolver_io_error
    finally:
        sessions_root.chmod(stat.S_IMODE(original_mode) | stat.S_IRWXU)


def test_a_readable_sessions_dir_is_the_control_for_the_permission_arm(tmp_path: Path) -> None:
    sessions_root = tmp_path / "codex-home" / "sessions"
    _completed_child(sessions_root)
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    assert isinstance(result, ev.Resolved)


# ---------------------------------------------------------------------------
# build_record / receipt_reference / persist
# ---------------------------------------------------------------------------


def test_receipt_reference_is_the_attempt_id_only_when_resolved(tmp_path: Path) -> None:
    sessions_root = tmp_path / "codex-home" / "sessions"
    _completed_child(sessions_root)
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=1, delay=0)
    record = ev.build_record(attempt, result)
    assert ev.receipt_reference(record) == attempt.attempt_id


@pytest.mark.parametrize(
    "result",
    [
        ev.Unavailable(ev.UnavailableReason.no_output_flag, "x"),
        ev.Error(ev.ErrorKind.resolver_io_error, "x"),
    ],
)
def test_receipt_reference_is_model_unverified_otherwise(
    tmp_path: Path, result: ev.ReviewEvidenceResult
) -> None:
    attempt = _attempt(tmp_path, output_path=None)
    record = ev.build_record(attempt, result)
    assert ev.receipt_reference(record) == "model-unverified"


def test_diagnostics_are_bounded(tmp_path: Path) -> None:
    """Matches `schemas/codex-review-evidence.schema.json`'s `diagnostics.maxLength`."""
    attempt = _attempt(tmp_path, output_path=None)
    huge = "x" * 100_000
    record = ev.build_record(attempt, ev.Unavailable(ev.UnavailableReason.no_output_flag, huge))
    assert record.diagnostics is not None
    assert len(record.diagnostics) <= 4096


def test_persist_is_atomic_and_readable_back(tmp_path: Path) -> None:
    attempt = _attempt(tmp_path, output_path=None)
    record = ev.build_record(attempt, ev.Unavailable(ev.UnavailableReason.no_output_flag, "x"))
    path = ev.persist(tmp_path, record)
    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists(), "the .tmp file must be renamed away"
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["attempt_id"] == attempt.attempt_id
    assert reloaded["outcome"] == "unavailable"


def test_evidence_path_sanitizes_the_attempt_id(tmp_path: Path) -> None:
    path = ev.evidence_path(tmp_path, "../../etc/passwd")
    assert ".." not in path.name
    assert path.parent == tmp_path / ev.EVIDENCE_DIR


# ---------------------------------------------------------------------------
# capture_and_persist — the one broad catch, end to end
# ---------------------------------------------------------------------------


def test_capture_and_persist_never_raises_on_an_unanticipated_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE OUTAGE ARM for this module's own inner guard.

    An exception from a function this module calls but does not control must
    be caught here, reported, and never propagate.
    """

    def _boom(*_a: object, **_kw: object) -> None:
        raise RuntimeError("simulated: something this module did not anticipate")

    monkeypatch.setattr(ev, "capture_attempt", _boom)
    result = ev.capture_and_persist(
        tmp_path,
        requested_model=None,
        requested_effort=None,
        base_ref="origin/main",
        subprocess_rc=0,
        timed_out=False,
        output_path=None,
    )
    assert result is None
    assert "evidence capture failed unexpectedly" in capsys.readouterr().err


def test_capture_and_persist_writes_a_record_on_the_ordinary_path(tmp_path: Path) -> None:
    """CONTROL ARM: the ordinary (no failure) path actually persists."""
    result = ev.capture_and_persist(
        tmp_path,
        requested_model=None,
        requested_effort=None,
        base_ref="origin/main",
        subprocess_rc=0,
        timed_out=False,
        output_path=None,
    )
    assert result is not None
    assert result.outcome is ev.OutcomeKind.unavailable
    assert ev.evidence_path(tmp_path, result.attempt_id).exists()


# --- cold antigravity review of 3cc9c93a: two folds of "unreadable" into "absent"


def test_an_unreadable_tee_is_an_error_not_an_absent_flag(tmp_path: Path) -> None:
    """🔴 A tee we were told to read and could not is NOT `--output` being omitted.

    The first version folded them and defended the fold in its docstring:
    *"an unreadable tee is `Unavailable`, not `Error`"*. Two different facts:

        --output never passed    -> we did not ASK. Nothing is wrong.
        --output passed, EACCES  -> we asked and the environment refused.

    Phase 1's whole job is to record accurately so Phase 2 can decide what to
    gate on, and an `Unavailable` count poisoned with environment faults is
    exactly what would make that later decision wrong.

    A REAL `chmod 0`, not a mocked raise — the mock would only prove the mock.
    """
    banner = tmp_path / "banner.txt"
    _banner(banner)
    original_mode = banner.stat().st_mode
    banner.chmod(0)
    try:
        attempt = _attempt(tmp_path, output_path=banner)
        result = ev.resolve_reviewer_model(attempt, attempts=2, delay=0)
        assert isinstance(result, ev.Error), f"expected Error, got {type(result).__name__}"
        assert result.kind is ev.ErrorKind.resolver_io_error
        assert "could not read the tee" in result.diagnostics
    finally:
        banner.chmod(stat.S_IMODE(original_mode) | stat.S_IRUSR | stat.S_IWUSR)


def test_a_readable_tee_with_no_session_id_is_still_unavailable(tmp_path: Path) -> None:
    """The CONTROL for the arm above — without it, that test cannot discriminate.

    A tee that reads fine and simply holds no `session id:` line is a genuine
    `Unavailable`. If this also returned `Error` the distinction would be
    cosmetic, and the fix would have traded one conflation for its mirror.
    """
    banner = tmp_path / "banner.txt"
    banner.write_text("OpenAI Codex v0.154.0\nno session line here\n", encoding="utf-8")
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=2, delay=0)
    assert isinstance(result, ev.Unavailable), f"expected Unavailable, got {type(result).__name__}"
    assert result.reason is ev.UnavailableReason.banner_session_id_unavailable


def test_an_unreadable_candidate_is_an_error_not_zero_children(tmp_path: Path) -> None:
    """🔴 Skipping an unreadable candidate turns a fault into an ordinary absence.

    `except OSError: continue` meant that if the ONE matching child could not be
    read, the scan reported "zero children found" — indistinguishable from a
    review that genuinely never wrote one. Same class as the `rglob` hazard the
    preflight in this very function exists for.

    A real `chmod 0` on the child file, with the directory left readable so the
    scan reaches it and fails at the OPEN rather than at the listing.
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    _write_child(
        sessions_root,
        "rollout-child-1.jsonl",
        [
            _session_meta_line(parent=_PARENT, source={"subagent": "review"}),
            _turn_context_line("gpt-5.6-sol"),
        ],
    )
    child = next(sessions_root.rglob("rollout-*.jsonl"))
    original_mode = child.stat().st_mode
    child.chmod(0)
    try:
        banner = tmp_path / "banner.txt"
        _banner(banner)
        attempt = _attempt(tmp_path, output_path=banner)
        result = ev.resolve_reviewer_model(attempt, attempts=2, delay=0)
        assert isinstance(result, ev.Error), f"expected Error, got {type(result).__name__}"
        assert result.kind is ev.ErrorKind.resolver_io_error
    finally:
        child.chmod(stat.S_IMODE(original_mode) | stat.S_IRUSR | stat.S_IWUSR)


# --- round 2 of the cold review: the fixes from round 1 reviewed as new code ---


def test_an_unrelated_unreadable_rollout_does_not_block_the_real_match(
    tmp_path: Path,
) -> None:
    """🔴 THE OVER-CORRECTION. Round 1's fix raised on ANY unreadable candidate.

    `$CODEX_HOME/sessions/` accumulates years of rollouts. One stale unreadable
    file anywhere under it aborted every scan forever — so the fix that closed a
    false absence opened a permanent outage. "Trades one failure for its mirror" is
    a fix shape this repo lists, and it was named in the very commit that
    shipped it, which is what makes this the most important test in the file.

    A genuine match plus an unrelated unreadable neighbour must still resolve.
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    _write_child(
        sessions_root,
        "rollout-child-1.jsonl",
        [
            _session_meta_line(parent=_PARENT, source={"subagent": "review"}),
            _turn_context_line("gpt-5.6-sol"),
        ],
    )
    _write_child(sessions_root, "rollout-stale-old.jsonl", ['{"type":"session_meta"}'])
    stale = sessions_root.rglob("rollout-stale-old.jsonl").__next__()
    original_mode = stale.stat().st_mode
    stale.chmod(0)
    try:
        banner = tmp_path / "banner.txt"
        _banner(banner)
        attempt = _attempt(tmp_path, output_path=banner, requested_model="gpt-5.6-sol")
        result = ev.resolve_reviewer_model(attempt, attempts=2, delay=0)
        assert isinstance(result, ev.Resolved), (
            f"one unreadable NEIGHBOUR must not block a real match, got {type(result).__name__}"
        )
        assert result.record.resolved_model == "gpt-5.6-sol"
    finally:
        stale.chmod(stat.S_IMODE(original_mode) | stat.S_IRUSR | stat.S_IWUSR)


def test_zero_hits_with_an_unreadable_path_is_error_not_absence(tmp_path: Path) -> None:
    """The other half: absence is only absence when nothing was skipped.

    Zero matches AND something unreadable means the scan did not establish
    absence — it may have skipped the very file it was looking for. That is
    `Error`, never the `Unavailable` that asserts "we looked and found nothing".
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    _write_child(sessions_root, "rollout-other.jsonl", ['{"type":"session_meta"}'])
    other = sessions_root.rglob("rollout-other.jsonl").__next__()
    original_mode = other.stat().st_mode
    other.chmod(0)
    try:
        banner = tmp_path / "banner.txt"
        _banner(banner)
        attempt = _attempt(tmp_path, output_path=banner)
        result = ev.resolve_reviewer_model(attempt, attempts=2, delay=0)
        assert isinstance(result, ev.Error), f"expected Error, got {type(result).__name__}"
        assert result.kind is ev.ErrorKind.resolver_io_error
    finally:
        other.chmod(stat.S_IMODE(original_mode) | stat.S_IRUSR | stat.S_IWUSR)


def test_a_genuinely_empty_scan_is_still_an_ordinary_absence(tmp_path: Path) -> None:
    """CONTROL for the two arms above — without it neither can discriminate.

    Zero matches with NOTHING unreadable is a real `Unavailable`. If this also
    returned `Error`, the fix would have traded the old conflation for its
    mirror a second time.
    """
    sessions_root = tmp_path / "codex-home" / "sessions"
    _write_child(sessions_root, "rollout-other.jsonl", ['{"type":"session_meta"}'])
    banner = tmp_path / "banner.txt"
    _banner(banner)
    attempt = _attempt(tmp_path, output_path=banner)
    result = ev.resolve_reviewer_model(attempt, attempts=2, delay=0)
    assert isinstance(result, ev.Unavailable), f"expected Unavailable, got {type(result).__name__}"
    assert result.reason is ev.UnavailableReason.no_matching_child_rollout


def test_an_empty_error_object_is_not_read_as_success() -> None:
    """`bool({})` is False, so an empty error object read as "no error".

    A failure wearing a success shape — the one direction completion must never
    get wrong. Round 1 raised only the empty-MESSAGE half of this and I judged
    it minor; the empty-ERROR half is the dangerous one and round 2 found it.
    """
    records = [
        {
            "type": "event_msg",
            "payload": {"type": "task_complete", "last_agent_message": "done", "error": {}},
        }
    ]
    assert ev._completion(records) is ev.ReviewCompletion.aborted


def test_a_completed_review_with_an_empty_message_is_not_aborted() -> None:
    """The mirror, and the control: `bool("")` is False too.

    A review that completed and returned an empty message must not read as
    `aborted`. Testing only the arm above would let `has_message = False`
    unconditionally pass.
    """
    records = [
        {
            "type": "event_msg",
            "payload": {"type": "task_complete", "last_agent_message": "", "error": None},
        }
    ]
    assert ev._completion(records) is ev.ReviewCompletion.complete
