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


def test_regenerate_readme_with_no_runs_at_all_is_still_valid(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    rows = archive_mod.regenerate_readme(repo)
    assert rows == 0
    readme = (repo / "docs" / "session-review" / "README.md").read_text(encoding="utf-8")
    assert "No runs archived" in readme
