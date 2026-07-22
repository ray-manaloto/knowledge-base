"""The zero-bash no-lint-skip check detects inline suppressions."""

from pathlib import Path

from kb_setup import lint_checks


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
