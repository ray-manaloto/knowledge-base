# Copyright (c) 2026 Raymond Manaloto
"""The zero-bash no-lint-skip check detects inline suppressions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import lint_checks
from kb_setup.result import Ok, Rc

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pytest


def _make_pkg(root: Path, body: str) -> None:
    d = root / "python" / "src" / "pkg"
    d.mkdir(parents=True)
    (d / "mod.py").write_text(body, encoding="utf-8")


def test_clean_source_passes(tmp_path: Path) -> None:
    _make_pkg(tmp_path, "x = 1\n")
    assert lint_checks.find_inline_suppressions(tmp_path) == []
    assert lint_checks.no_lint_skip(tmp_path) == 0


def test_detects_each_marker(tmp_path: Path) -> None:
    # Control arm the FAIL direction: a planted suppression must be caught. The
    # markers are CONCATENATED so their literal forms never appear in this test
    # file — otherwise no_lint_skip (and ruff RUF100) would flag this file itself.
    mark_a = "no" + "qa"
    mark_b = "type: " + "ignore"
    _make_pkg(tmp_path, "x = 1  # " + mark_a + ": E501\ny = 2  # " + mark_b + "\n")
    hits = lint_checks.find_inline_suppressions(tmp_path)
    assert {m for _, _, m in hits} == {mark_a, mark_b}
    assert lint_checks.no_lint_skip(tmp_path) == 1


def test_missing_dirs_are_ok(tmp_path: Path) -> None:
    assert lint_checks.no_lint_skip(tmp_path) == 0


# --------------------------------------------------------------------------
# The `check_no_lint_skip` boundary (§2 R5)
# --------------------------------------------------------------------------
#
# `no_lint_skip` returns an int and is asserted above; those assertions are the
# regression arm proving the Result split changed no exit code. What is NEW is
# that "found suppressions" is an `Ok` CARRYING them rather than an opaque 1 —
# and no int-returning test can fail if that distinction is lost.
#
# Markers stay concatenated here for the same reason as `test_detects_each_marker`:
# a literal in this file would make `no_lint_skip` flag the repo itself.


def test_suppressions_found_is_ok_with_findings(tmp_path: Path) -> None:
    """A gate that ran and found something SUCCEEDED — that is the whole point.

    If someone "simplifies" this to an `Err`, `no_lint_skip` still returns 1 and
    every pre-existing assertion stays green. Only this test notices.
    """
    mark = "no" + "qa"
    _make_pkg(tmp_path, "x = 1  # " + mark + ": E501\n")

    result = lint_checks.check_no_lint_skip(tmp_path)

    assert isinstance(result, Ok)
    assert result.rc is Rc.FINDINGS
    assert [marker for _p, _l, marker in result.value] == [mark]


def test_clean_source_is_ok_with_rc_ok(tmp_path: Path) -> None:
    """CONTROL ARM: `Ok` is reachable with BOTH rcs, so the test above discriminates."""
    _make_pkg(tmp_path, "x = 1\n")

    result = lint_checks.check_no_lint_skip(tmp_path)

    assert isinstance(result, Ok)
    assert result.rc is Rc.OK
    assert result.value == []


def test_the_boundary_prints_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Rendering belongs to `no_lint_skip`; the boundary only returns.

    Pinned because it is the property that makes the split worth anything: a
    boundary that prints cannot be reused by a caller wanting to render
    differently, which is exactly where §2.5's stdout sink lands.
    """
    mark = "no" + "qa"
    _make_pkg(tmp_path, "x = 1  # " + mark + ": E501\n")

    lint_checks.check_no_lint_skip(tmp_path)
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
