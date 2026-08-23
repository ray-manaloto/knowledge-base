# Copyright (c) 2026 Raymond Manaloto
"""`kb_setup.session_review_archive` — the tracked-archive task's tests.

EVERY TEST BUILDS ITS OWN `repo_root` UNDER `tmp_path`. None reads the real
`docs/session-review/runs/` tree: it is committed evidence from real rounds,
mutating it here would corrupt history, and a test that depends on today's
real run count is a test that could only pass here
(`a-test-must-own-its-own-environment.md`).

NO WALL CLOCK. `--date` is always passed explicitly, or a fixture supplies
`run_meta.sessions[].started_at` and the default-date path is exercised
against THAT — never `datetime.now()`.

FORMATTER-HOSTILE FIXTURE CONTENT proves the copy is really verbatim: a
line-leading `#123` (a reference a formatter would turn into a heading), two
trailing spaces (a formatter strips them), a triple space inside what looks
like a table cell, and a line-leading `1)` list marker. None of these is a
real English misspelling — `typos` scans `tests/**` (`hk.pkl` proseExclude
does not cover it) and this repo has twice had a fixture "corrected" into
uselessness, so any word-shaped token here is assembled at runtime rather
than spelled as a dictionary word.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import session_review_archive as archive_mod

if TYPE_CHECKING:
    # `pytest` has no RUNTIME use in this file (no fixtures, no
    # `pytest.mark.*`, no `pytest.raises`) — only as `capsys`/`monkeypatch`
    # parameter annotations, which `from __future__ import annotations` defers
    # to strings. ruff's TC002 is right to ask for this.
    import pytest

_WEIRD_TOKEN = "rec" + "ieve"  # word-shaped, never spelled as a real word — see module docstring
_FORMATTER_HOSTILE_BODY = (
    "# Circles\n\n"
    "#123 was re-litigated three times.  \n"  # line-leading ref + two trailing spaces
    "| a | b |\n"
    "|---|---|\n"
    "| x |   y |\n"  # triple space inside a cell
    f"1) first {_WEIRD_TOKEN}\n"  # line-leading list marker
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "docs" / "session-review" / "runs").mkdir(parents=True)
    return repo


def _write_report_dir(
    repo: Path, name: str, *, synthesis: str | None = _FORMATTER_HOSTILE_BODY
) -> Path:
    report_dir = repo / ".agent" / "kb" / "reports" / name
    report_dir.mkdir(parents=True)
    if synthesis is not None:
        (report_dir / "session-review-synthesis.md").write_text(synthesis, encoding="utf-8")
    return report_dir


def _bare_result(*, lanes: list[str], report_dir: str, handoff_out: str | None = None) -> dict:
    return {
        "lanes": [{"lane": lane, "findings": 1, "coverage": {}} for lane in lanes],
        "confirmed": [{"claim": "c1", "lane": lanes[0]}],
        "refuted": [],
        "unverified": [],
        "not_triaged": [],
        "report": "the synthesis text",
        "synthesis_ran_on": "fable/high",
        "artifacts": {
            "report_dir": report_dir,
            "synthesis": f"{report_dir}/session-review-synthesis.md",
            "handoff_out": handoff_out,
            "lane_reports": [f"{report_dir}/{lane}.md" for lane in lanes],
            "refute_reports_expected": [],
            "refute_glob": f"{report_dir}/refute-*.md",
        },
        "run_meta": {
            "output": "report",
            "lanes": lanes,
            "sessions": [{"path": "/x.jsonl", "started_at": "2026-08-23T10:00:00.000000Z"}],
            "directive": None,
            "handoffs": [],
            "max_refuters": 11,
        },
    }


def _envelope(result: dict) -> dict:
    return {
        "agentCount": 7,
        "logs": [],
        "result": result,
        "summary": "ok",
        "workflowProgress": [],
        "totalTokens": 12345,
        "totalToolCalls": 42,
    }


def _write_run_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _dest_of(outcome: archive_mod.ArchiveOutcome) -> str:
    """Narrow `outcome.dest: str | None` to `str` for the type checker.

    `ty` does not narrow an attribute expression across an `assert obj.attr is
    not None` the way it narrows a local variable, so every test that turns a
    successful outcome's `dest` into a path goes through this rather than
    repeating an assert `ty` cannot use.
    """
    assert outcome.dest is not None
    return outcome.dest


def test_archive_refuses_when_no_synthesis_exists_and_writes_nothing(tmp_path: Path) -> None:
    """No synthesis on disk is THE contract this module enforces (rc 2, no dir)."""
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1", synthesis=None)
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is not None
    assert "no synthesis" in outcome.refusal
    assert outcome.dest is None
    assert list((repo / "docs" / "session-review" / "runs").iterdir()) == []


def test_archive_refuses_when_dest_already_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_next_run_name` always picks a FRESH `<date>-<n>` by construction.

    A real collision only happens on a race between two archivers computing
    the same name. Simulated here by pinning the name `_write` targets and
    pre-creating it — the same shape a race would produce, deterministically.
    """
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)
    existing = repo / "docs" / "session-review" / "runs" / "2026-08-23-1"
    existing.mkdir()
    monkeypatch.setattr(archive_mod, "_next_run_name", lambda *_args: "2026-08-23-1")

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is not None
    assert "already exists" in outcome.refusal
    # The pre-existing directory is untouched — nothing was written into it.
    assert list(existing.iterdir()) == []


def test_archive_refuses_when_a_copy_fails_mid_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_stage` raises `OSError` on a copy failure, by its own docstring.

    `_write` must convert that into a refusal (rc 2) rather than let it
    propagate as an uncaught traceback out of `archive()`. Also asserts the
    `.archive-*` staging directory is not left behind.
    """
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)
    monkeypatch.setattr(
        archive_mod,
        "_copy_verbatim",
        lambda *_a: (_ for _ in ()).throw(OSError("disk gremlin")),
    )

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is not None
    assert "staging failed" in outcome.refusal
    assert "disk gremlin" in outcome.refusal
    assert outcome.dest is None
    runs_root = repo / "docs" / "session-review" / "runs"
    assert list(runs_root.iterdir()) == [], "no dest dir AND no .archive-* leftover"


def test_archive_refuses_when_given_handoff_path_does_not_exist(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo,
        run_json=run_json,
        report_dir=None,
        handoff=repo / "nope.md",
        date="2026-08-23",
    )
    assert outcome.refusal is not None
    assert "does not exist" in outcome.refusal
    assert list((repo / "docs" / "session-review" / "runs").iterdir()) == []


def test_archive_copies_reports_verbatim_byte_for_byte(tmp_path: Path) -> None:
    """Byte-equality against formatter-hostile content is the arm.

    A re-encode or a `rumdl fmt`-shaped rewrite would change ANY of the four
    hostile tokens, so this fails if the copy stops being verbatim.
    """
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is None
    dest = repo / _dest_of(outcome)
    copied = (dest / "session-review-synthesis.md").read_bytes()
    assert copied == _FORMATTER_HOSTILE_BODY.encode("utf-8")


def test_relative_or_absolute_handles_a_report_dir_outside_the_repo(tmp_path: Path) -> None:
    """`--report-dir` accepts any absolute path, inside the repo or outside it.

    `_abs` never requires it stay inside the repo, and a scratchpad path is a
    realistic input. `Path.relative_to` raises `ValueError` for a path outside
    `repo_root`; `_relative_or_absolute` must record the absolute form instead
    of raising.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "scratchpad" / "reports"
    assert archive_mod._relative_or_absolute(outside, repo) == str(outside)


def test_relative_or_absolute_prefers_the_relative_form_inside_the_repo(tmp_path: Path) -> None:
    """The control arm for the outside-the-repo test above.

    A path genuinely inside `repo_root` still gets the shorter, portable
    relative form — the absolute-path fallback must not swallow the common
    case too.
    """
    repo = tmp_path / "repo"
    inside = repo / ".agent" / "kb" / "reports" / "r1"
    assert archive_mod._relative_or_absolute(inside, repo) == ".agent/kb/reports/r1"


def test_archive_with_a_report_dir_outside_the_repo_does_not_raise(tmp_path: Path) -> None:
    """End-to-end version of the two unit tests above.

    A `--report-dir` outside `repo_root` must archive successfully rather
    than crash on `run.json`'s `report_dir` field.
    """
    repo = _repo(tmp_path)
    outside_report_dir = tmp_path / "scratchpad" / "reports"
    outside_report_dir.mkdir(parents=True)
    (outside_report_dir / "session-review-synthesis.md").write_text("s", encoding="utf-8")
    result = _bare_result(lanes=["circles"], report_dir=str(outside_report_dir))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo,
        run_json=run_json,
        report_dir=outside_report_dir,
        handoff=None,
        date="2026-08-23",
    )
    assert outcome.refusal is None
    written = json.loads((repo / _dest_of(outcome) / "run.json").read_text(encoding="utf-8"))
    assert written["archive"]["report_dir"] == str(outside_report_dir)


def test_archive_copies_the_handoff_when_given(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)
    handoff_src = repo / ".agent" / "plans" / "session-2026-08-23-a.md"
    handoff_src.parent.mkdir(parents=True)
    handoff_src.write_text("- **branch**: `x`\n", encoding="utf-8")

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=handoff_src, date="2026-08-23"
    )
    assert outcome.refusal is None
    assert "handoff.md" in outcome.files_written
    dest = repo / _dest_of(outcome)
    assert (dest / "handoff.md").read_bytes() == handoff_src.read_bytes()


def test_archive_globs_refute_reports_rather_than_trusting_expected_names(tmp_path: Path) -> None:
    """Refuters write free-form filenames — the archive must glob, not guess."""
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    (report_dir / "refute-circles-oddly-named.md").write_text("verdict", encoding="utf-8")
    (report_dir / "refute-second.md").write_text("verdict2", encoding="utf-8")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is None
    assert "refute-circles-oddly-named.md" in outcome.files_written
    assert "refute-second.md" in outcome.files_written


def test_archive_warns_when_report_dir_is_the_shared_root(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report_dir = repo / ".agent" / "kb" / "reports" / "agents"
    report_dir.mkdir(parents=True)
    (report_dir / "session-review-synthesis.md").write_text("body", encoding="utf-8")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is None
    assert any("#431" in w for w in outcome.warnings)


def test_archive_records_missing_lane_reports_without_failing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(
        lanes=["circles", "forgotten"], report_dir=str(report_dir.relative_to(repo))
    )
    run_json = _write_run_json(repo / "run.json", result)
    # Neither circles.md nor forgotten.md exists — a lane can be listed in
    # `result.lanes` and still have left no report (an interrupted lane).

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is None
    assert set(outcome.missing) == {"circles.md", "forgotten.md"}


def test_archive_records_an_auto_detected_handoff_that_is_missing(tmp_path: Path) -> None:
    """`result.artifacts.handoff_out` names a path that was never written.

    A report-mode run whose return still carries a stale or hypothetical
    `handoff_out`, or a composer that died before writing, both look like
    this. It must NOT refuse the archive — only a `--handoff` explicitly
    passed and missing refuses — but it must be RECORDED, not silently
    dropped.
    """
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(
        lanes=["circles"],
        report_dir=str(report_dir.relative_to(repo)),
        handoff_out=".agent/plans/session-2026-08-23-a.md",
    )
    run_json = _write_run_json(repo / "run.json", result)
    # No file written at .agent/plans/session-2026-08-23-a.md.

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is None
    assert any("handoff_out" in m and "session-2026-08-23-a.md" in m for m in outcome.missing)
    dest = repo / _dest_of(outcome)
    assert not (dest / "handoff.md").exists()
    written = json.loads((dest / "run.json").read_text(encoding="utf-8"))
    assert any("handoff_out" in m for m in written["archive"]["missing"])


def test_archive_default_date_from_run_meta_sessions_started_at(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(repo, run_json=run_json, report_dir=None, handoff=None, date=None)
    assert outcome.refusal is None
    assert Path(_dest_of(outcome)).name == "2026-08-23-1"


def test_archive_refuses_when_no_date_and_sessions_are_bare_strings(tmp_path: Path) -> None:
    """A bare-string session (`s.path || s`) carries no `started_at` at all."""
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    result["run_meta"]["sessions"] = ["/some/transcript.jsonl"]
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(repo, run_json=run_json, report_dir=None, handoff=None, date=None)
    assert outcome.refusal is not None
    assert "--date" in outcome.refusal


def test_archive_refuses_a_date_that_would_escape_the_runs_directory(tmp_path: Path) -> None:
    """`--date` becomes a directory name, and an unvalidated one is dangerous.

    `../../scratch` would let `plan.dest` escape `docs/session-review/runs/`
    entirely, and the escape would only surface AFTER the rename succeeded
    (too late). Refused up front, nothing written.
    """
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="../../scratch"
    )
    assert outcome.refusal is not None
    assert "YYYY-MM-DD" in outcome.refusal
    assert not (tmp_path / "scratch").exists()
    assert list((repo / "docs" / "session-review" / "runs").iterdir()) == []


def test_archive_refuses_a_date_with_the_wrong_digit_widths(tmp_path: Path) -> None:
    """`2026-8-23` (single-digit month) is not `YYYY-MM-DD` and must refuse.

    The control arm for the traversal test above, proving `_DATE` actually
    discriminates rather than accepting everything.
    """
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-8-23"
    )
    assert outcome.refusal is not None
    assert "YYYY-MM-DD" in outcome.refusal


def test_archive_accepts_a_well_formed_date(tmp_path: Path) -> None:
    """The control arm's control arm: a well-formed `--date` must still work."""
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is None
    assert Path(_dest_of(outcome)).name == "2026-08-23-1"


def test_archive_next_run_number_increments_for_same_date(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "docs" / "session-review" / "runs" / "2026-08-23-1").mkdir()
    (repo / "docs" / "session-review" / "runs" / "2026-08-23-2").mkdir()
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is None
    assert Path(_dest_of(outcome)).name == "2026-08-23-3"


def test_archive_accepts_the_envelope_input_shape(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", _envelope(result))

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is None
    written = json.loads((repo / _dest_of(outcome) / "run.json").read_text(encoding="utf-8"))
    assert written["archive"]["input_shape"] == "envelope"


def test_archive_accepts_the_bare_input_shape(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is None
    written = json.loads((repo / _dest_of(outcome) / "run.json").read_text(encoding="utf-8"))
    assert written["archive"]["input_shape"] == "bare"


def test_archive_refuses_when_run_json_is_not_a_recognised_shape(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    run_json = _write_run_json(repo / "run.json", {"unrelated": True})

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is not None
    assert "not a recognised workflow return" in outcome.refusal


def test_archive_refuses_run_json_with_invalid_utf8_bytes(tmp_path: Path) -> None:
    """Invalid UTF-8 makes `json.loads` raise a BARE `UnicodeDecodeError`.

    Verified, never wrapped into a `JSONDecodeError` — which is not caught by
    an `except json.JSONDecodeError`. Both subclass `ValueError`; this must
    reach the SAME refusal contract as a bad-JSON `--run-json`, not an
    uncaught traceback.
    """
    repo = _repo(tmp_path)
    run_json = repo / "run.json"
    run_json.write_bytes(b"\xff\xfe{")

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23"
    )
    assert outcome.refusal is not None
    assert "not valid JSON" in outcome.refusal
    assert outcome.dest is None


def test_archive_dry_run_writes_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    outcome = archive_mod.archive(
        repo, run_json=run_json, report_dir=None, handoff=None, date="2026-08-23", dry_run=True
    )
    assert outcome.refusal is None
    assert not (repo / _dest_of(outcome)).exists()
    runs_root = repo / "docs" / "session-review" / "runs"
    assert list(runs_root.iterdir()) == []


def test_main_cli_dry_run_says_readme_was_not_regenerated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A dry run writes NOTHING, README included — say so, don't claim a write.

    `_preview` never calls `regenerate_readme`, so the summary must not claim
    "regenerated (0 row(s))", which reads as a successful no-op write rather
    than as "did not run".
    """
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    rc = archive_mod.main(["--run-json", str(run_json), "--date", "2026-08-23", "--dry-run"], repo)
    assert rc == 0
    out = capsys.readouterr().out
    assert "would write" in out
    assert "not regenerated (dry run)" in out
    assert "regenerated (0 row(s))" not in out


def test_main_cli_writes_and_returns_rc_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1")
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    rc = archive_mod.main(["--run-json", str(run_json), "--date", "2026-08-23"], repo)
    assert rc == 0
    out = capsys.readouterr().out
    assert "wrote" in out
    assert (repo / "docs" / "session-review" / "runs" / "2026-08-23-1" / "run.json").is_file()


def test_main_cli_refuses_and_returns_rc_2_with_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)
    report_dir = _write_report_dir(repo, "r1", synthesis=None)
    result = _bare_result(lanes=["circles"], report_dir=str(report_dir.relative_to(repo)))
    run_json = _write_run_json(repo / "run.json", result)

    rc = archive_mod.main(["--run-json", str(run_json), "--date", "2026-08-23"], repo)
    assert rc == 2
    err = capsys.readouterr().err
    assert "REFUSED" in err
    assert "no synthesis" in err


def test_main_cli_needs_run_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = archive_mod.main([], tmp_path)
    assert rc == 2
    assert "--run-json" in capsys.readouterr().err


def test_regenerate_readme_handles_the_new_envelope_shape(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    run_dir = repo / "docs" / "session-review" / "runs" / "2026-08-23-1"
    run_dir.mkdir()
    (run_dir / "session-review-synthesis.md").write_text("s", encoding="utf-8")
    payload = _envelope(_bare_result(lanes=["circles", "forgotten"], report_dir="x"))
    (run_dir / "run.json").write_text(json.dumps(payload), encoding="utf-8")

    rows = archive_mod.regenerate_readme(repo)
    assert rows == 1
    readme = (repo / "docs" / "session-review" / "README.md").read_text(encoding="utf-8")
    assert "2026-08-23-1" in readme
    assert "circles,forgotten" in readme
    assert "report" in readme  # run_meta.output


def test_regenerate_readme_handles_the_old_outcome_findings_shape(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    run_dir = repo / "docs" / "session-review" / "runs" / "2026-08-18-1"
    run_dir.mkdir()
    old_shape = {
        "finished_at_utc": "2026-08-18T15:23:40Z",
        "run_id": "wf_x",
        "journal_path": "/x",
        "config_digest": {},
        "outcome": {
            "status": "completed",
            "agents": 23,
            "synthesis_ran_on": "fable/high",
            "confirmed": 1,
            "refuted": 13,
            "unverified": 0,
            "not_triaged": 17,
            "lanes_that_did_not_return": ["bot-reviews"],
        },
        "lanes": [{"lane": "circles", "findings": 9, "coverage": {}}],
        "findings": {"confirmed": [], "refuted": [], "not_triaged": []},
    }
    (run_dir / "run.json").write_text(json.dumps(old_shape), encoding="utf-8")

    rows = archive_mod.regenerate_readme(repo)
    assert rows == 1
    readme = (repo / "docs" / "session-review" / "README.md").read_text(encoding="utf-8")
    assert (
        "| [2026-08-18-1](runs/2026-08-18-1/) | ? | circles | 1 | 13 | 17 | 0 | 23 | ? | — | — |"
        in readme
    )


def test_regenerate_readme_handles_a_dir_with_no_run_json(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    run_dir = repo / "docs" / "session-review" / "runs" / "2026-08-18-2"
    run_dir.mkdir()
    (run_dir / "handoff-c-before-reconcile-fix.md").write_text("x", encoding="utf-8")

    rows = archive_mod.regenerate_readme(repo)
    assert rows == 1
    readme = (repo / "docs" / "session-review" / "README.md").read_text(encoding="utf-8")
    assert "[2026-08-18-2](runs/2026-08-18-2/)" in readme
    # Every count column is unreadable for this shape.
    assert "| ? | ? | ? | ? | ? | ? | ? |" in readme


def test_regenerate_readme_emits_a_question_mark_row_for_invalid_utf8(tmp_path: Path) -> None:
    """`_readme_row`'s contract is NEVER RAISE, even on invalid UTF-8 bytes.

    A `run.json` with invalid UTF-8 must not abort `regenerate_readme` for
    every OTHER run in the directory — it degrades to a `?` row for that one
    dir, same as a corrupted or absent `run.json`.
    """
    repo = _repo(tmp_path)
    runs_root = repo / "docs" / "session-review" / "runs"
    bad_dir = runs_root / "2026-08-23-1"
    bad_dir.mkdir()
    (bad_dir / "run.json").write_bytes(b"\xff\xfe{")
    good_dir = runs_root / "2026-08-24-1"
    good_dir.mkdir()

    rows = archive_mod.regenerate_readme(repo)
    assert rows == 2
    readme = (repo / "docs" / "session-review" / "README.md").read_text(encoding="utf-8")
    assert "[2026-08-23-1](runs/2026-08-23-1/)" in readme
    assert "| ? | ? | ? | ? | ? | ? | ? |" in readme


def test_regenerate_readme_sorts_by_name_and_skips_archive_temp_dirs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    runs_root = repo / "docs" / "session-review" / "runs"
    (runs_root / "2026-08-23-1").mkdir()
    (runs_root / "2026-08-18-1").mkdir()
    (runs_root / ".archive-abc123").mkdir()  # a leftover temp dir from a killed run

    archive_mod.regenerate_readme(repo)
    readme = (repo / "docs" / "session-review" / "README.md").read_text(encoding="utf-8")
    assert readme.index("2026-08-18-1") < readme.index("2026-08-23-1")
    assert ".archive-" not in readme


def test_regenerate_readme_sorts_run_numbers_numerically_not_lexicographically(
    tmp_path: Path,
) -> None:
    """`sorted(iterdir())` sorts PATHS as strings — the exact defect this pins.

    That put `-10` before `-2` within one date. `-1` must lead, `-2` second,
    `-10` last, for the SAME date.
    """
    repo = _repo(tmp_path)
    runs_root = repo / "docs" / "session-review" / "runs"
    (runs_root / "2026-08-23-10").mkdir()
    (runs_root / "2026-08-23-2").mkdir()
    (runs_root / "2026-08-23-1").mkdir()

    archive_mod.regenerate_readme(repo)
    readme = (repo / "docs" / "session-review" / "README.md").read_text(encoding="utf-8")
    pos_1 = readme.index("2026-08-23-1]")
    pos_2 = readme.index("2026-08-23-2]")
    pos_10 = readme.index("2026-08-23-10]")
    assert pos_1 < pos_2 < pos_10, "run numbers must sort numerically within one date"


def test_regenerate_readme_with_no_runs_at_all_is_still_valid(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    rows = archive_mod.regenerate_readme(repo)
    assert rows == 0
    readme = (repo / "docs" / "session-review" / "README.md").read_text(encoding="utf-8")
    assert "No runs archived" in readme
