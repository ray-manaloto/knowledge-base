# Copyright (c) 2026 Raymond Manaloto
"""Contract tests for the `aggregated-research` console-script entry point."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec
from kb_setup.generated.research_record import AdapterRecord
from kb_setup.research import cli, trackers

if TYPE_CHECKING:
    import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "research"
NOW = datetime(2026, 8, 28, 2, 7, 38, tzinfo=UTC)
REPO_JDX = "jdx/hk"

type Reply = str | tuple[int, str, str]
type Runner = Callable[[tuple[str, ...]], tuple[int, str, str]]


def _repo_argv(repo: str) -> tuple[str, ...]:
    return "api", f"repos/{repo}"


def _search_argv(repo: str, kind: str, term: str | None) -> tuple[str, ...]:
    query = f"repo:{repo} is:{kind}"
    if term is not None:
        query = f"{query} {term}"
    return "api", "-X", "GET", "search/issues", "-f", f"q={query}"


def _stub_gh(monkeypatch: pytest.MonkeyPatch, responses: dict[tuple[str, ...], Reply]) -> None:
    def _fake(argv: tuple[str, ...]) -> tuple[int, str, str]:
        reply = responses[argv]
        if isinstance(reply, tuple):
            return reply
        return 0, (FIXTURES / reply).read_text(encoding="utf-8"), ""

    monkeypatch.setattr(trackers, "_run_gh", _fake)


def _fix_now(monkeypatch: pytest.MonkeyPatch) -> None:
    original = trackers.search

    def _fixed(repo: str, term: str, *, run: Runner) -> trackers.Result[AdapterRecord]:
        return original(repo, term, run=run, now=NOW)

    monkeypatch.setattr(trackers, "search", _fixed)


def test_trackers_verb_prints_the_record_unchanged(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression arm: the `trackers` verb must match `kb-setup research-trackers`."""
    term = "gitleaks"
    _stub_gh(
        monkeypatch,
        {
            _repo_argv(REPO_JDX): "jdx-repo.json",
            _search_argv(REPO_JDX, "pr", term): "jdx-gitleaks-pr.json",
        },
    )
    _fix_now(monkeypatch)

    returncode = cli.main(["trackers", REPO_JDX, term])
    captured = capsys.readouterr()

    assert returncode == 0
    assert captured.out.startswith('{\n  "adapter": "trackers"')


def test_trackers_verb_out_writes_file_and_prints_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if `--out` is ignored: no file, and stdout would carry the JSON instead."""
    term = "gitleaks"
    out_path = tmp_path / "r" / "x.json"
    _stub_gh(
        monkeypatch,
        {
            _repo_argv(REPO_JDX): "jdx-repo.json",
            _search_argv(REPO_JDX, "pr", term): "jdx-gitleaks-pr.json",
        },
    )
    _fix_now(monkeypatch)

    returncode = cli.main(["trackers", REPO_JDX, term, "--out", str(out_path)])
    captured = capsys.readouterr()

    assert returncode == 0
    assert out_path.exists()
    msgspec.json.decode(out_path.read_bytes(), type=AdapterRecord)
    assert captured.out == f"[aggregated-research] wrote {out_path}\n"
    assert captured.err == ""


def test_trackers_verb_bad_request_never_writes_out_path(tmp_path: Path) -> None:
    """Fails if a bad-request result still writes PATH — that would look like a record."""
    out_path = tmp_path / "y.json"

    returncode = cli.main(["trackers", "not-a-repo", "x", "--out", str(out_path)])

    assert returncode == 2
    assert not out_path.exists()


def test_unknown_verb_is_rejected_before_dispatch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fails if an unknown verb falls through to kb_setup.cli instead of being rejected here."""
    returncode = cli.main(["bogus"])
    captured = capsys.readouterr()

    assert returncode == 2
    assert captured.err == "aggregated-research: unknown verb 'bogus'\n"
    assert captured.out == ""


def test_no_verb_prints_usage_naming_every_verb(capsys: pytest.CaptureFixture[str]) -> None:
    """Fails if usage stops naming `trackers` (e.g. an empty verb list)."""
    returncode = cli.main([])
    captured = capsys.readouterr()

    assert returncode == 0
    assert "trackers" in captured.out
