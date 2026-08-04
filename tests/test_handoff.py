"""Tests for the handoff checker (kb_setup.handoff).

Drives the public entry points — `check` and `main` — against a temporary
fixture repo, the same seam every other `kb_setup` CLI module is tested at. No
monkeypatching of internals: what is under test is the observable result (the
findings and the exit code), not which helper produced them.

The load-bearing split is the exit code. #145 is strict about wrongness and
advisory about ambiguity, so "a missing path exits 1" and "an ambiguous
filename exits 0" are asserted separately and neither is inferred from the
other.
"""

from __future__ import annotations

import os
from pathlib import Path

from kb_setup import handoff

_MISE = "[tasks.kb-build]\nrun = 'true'\n[tasks.lint]\nrun = 'true'\n"


def _repo(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """A fixture repo with a mise.toml declaring `kb-build` and `lint`."""
    (tmp_path / "mise.toml").write_text(_MISE, encoding="utf-8")
    for rel, body in (files or {}).items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return tmp_path


def _fails(findings: list[handoff.Finding]) -> list[handoff.Finding]:
    return [f for f in findings if f.verdict is handoff.Verdict.FAIL]


# ------------------------------------------------------------- paths ----


def test_a_cited_path_that_exists_produces_no_failure(tmp_path: Path):
    """Positive control for every path failure below."""
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    assert _fails(handoff.check(root, "see `docs/a.md`\n")) == []


def test_a_cited_path_that_does_not_exist_fails(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    (f,) = _fails(handoff.check(root, "see `docs/b.md`\n"))
    assert f.claim == "docs/b.md"
    assert f.line == 1
    assert "no such path" in f.detail


def test_an_ambiguous_bare_filename_is_reported_but_does_not_fail(tmp_path: Path):
    root = _repo(tmp_path, {"docs/README.md": "x\n", "python/README.md": "y\n"})
    findings = handoff.check(root, "see `README.md`\n")
    assert _fails(findings) == []
    assert [f.verdict for f in findings if f.claim == "README.md"] == [handoff.Verdict.AMBIGUOUS]


def test_a_citation_about_another_repo_is_reported_but_does_not_fail(tmp_path: Path):
    """`graphify/serve.py` is a claim about a repo this checker cannot see."""
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    findings = handoff.check(root, "see `graphify/serve.py` upstream\n")
    assert _fails(findings) == []
    assert [f.verdict for f in findings] == [handoff.Verdict.UNVERIFIABLE]


def test_a_citation_about_this_repo_that_is_wrong_still_fails(tmp_path: Path):
    """Control arm for the test above: same shape, first segment exists here."""
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    assert _fails(handoff.check(root, "see `docs/nope/x.md` here\n")) != []


def test_main_exits_0_when_the_only_finding_is_unverifiable(tmp_path: Path):
    root = _repo(tmp_path, {"h.md": "see `graphify/serve.py`\n"})
    assert handoff.main([str(root / "h.md")], root) == 0


def test_paths_inside_a_fenced_example_are_not_checked(tmp_path: Path):
    """An example block is illustration; its paths need not exist."""
    root = _repo(tmp_path)
    assert _fails(handoff.check(root, "```bash\ncat docs/`nope.md`\n```\n")) == []


# --------------------------------------------------------- file:line ----


def test_a_line_reference_inside_the_file_produces_no_failure(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "1\n2\n3\n"})
    assert _fails(handoff.check(root, "see `docs/a.md:2`\n")) == []


def test_a_line_reference_past_the_end_of_the_file_fails(tmp_path: Path):
    """The defect this ticket exists for: `:1836` written for `:1830`."""
    root = _repo(tmp_path, {"docs/a.md": "1\n2\n3\n"})
    (f,) = _fails(handoff.check(root, "see `docs/a.md:9`\n"))
    assert "3 lines" in f.detail


def test_the_far_end_of_a_line_range_is_checked_too(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "1\n2\n3\n"})
    assert _fails(handoff.check(root, "see `docs/a.md:2-9`\n")) != []


def test_a_line_reference_whose_file_is_missing_fails_naming_the_file(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    (f,) = _fails(handoff.check(root, "see `docs/gone.md:2`\n"))
    assert "docs/gone.md" in f.claim


def test_a_line_reference_to_an_ambiguous_bare_name_does_not_fail(tmp_path: Path):
    """Ambiguity is ambiguity whichever check meets it first."""
    root = _repo(tmp_path, {"a/N.md": "1\n", "b/N.md": "1\n"})
    assert _fails(handoff.check(root, "see `N.md:1`\n")) == []


# -------------------------------------------------------------- tasks ----


def test_a_declared_task_produces_no_failure(tmp_path: Path):
    root = _repo(tmp_path)
    assert _fails(handoff.check(root, "run `mise run kb-build` first\n")) == []


def test_an_undeclared_task_fails(tmp_path: Path):
    root = _repo(tmp_path)
    (f,) = _fails(handoff.check(root, "run `mise run kb-nonesuch` first\n"))
    assert f.claim == "kb-nonesuch"
    assert "mise.toml" in f.detail


# ----------------------------------------------------- absent marker ----


def test_a_path_marked_absent_that_is_absent_produces_no_failure(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    text = "the hardcoded `docs/agents/issue-tracker.md` (absent) it looks for\n"
    assert _fails(handoff.check(root, text)) == []


def test_a_path_marked_absent_that_actually_resolves_fails(tmp_path: Path):
    """The marker is checked in BOTH directions, which is what stops it silencing.

    If `(absent)` only ever suppressed findings it would be a mute button: an
    author could paste it beside anything. Because a marked citation that
    resolves is itself a failure, the marker can only be applied to a path that
    really is missing — so it cannot be used to hide a real miss.
    """
    root = _repo(tmp_path, {"docs/here.md": "x\n"})
    (f,) = _fails(handoff.check(root, "see `docs/here.md` (absent) now\n"))
    assert "marked" in f.detail


# ------------------------------------------------------- exit codes ----


def test_main_exits_1_on_a_real_miss(tmp_path: Path):
    root = _repo(tmp_path, {"h.md": "see `docs/gone.md`\n", "docs/a.md": "x\n"})
    assert handoff.main([str(root / "h.md")], root) == 1


def test_main_exits_0_when_everything_holds(tmp_path: Path):
    root = _repo(tmp_path, {"h.md": "see `mise.toml`\n"})
    assert handoff.main([str(root / "h.md")], root) == 0


def test_main_exits_0_when_the_only_finding_is_ambiguous(tmp_path: Path):
    root = _repo(tmp_path, {"h.md": "see `R.md`\n", "a/R.md": "x\n", "b/R.md": "x\n"})
    assert handoff.main([str(root / "h.md")], root) == 0


def test_main_exits_2_on_a_target_that_does_not_exist(tmp_path: Path):
    """A malformed request is not a finding — same split the skill scorer draws."""
    root = _repo(tmp_path)
    assert handoff.main([str(root / "nope.md")], root) == 2


def test_main_with_no_argument_checks_the_newest_session_plan(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    plans = root / ".agent" / "plans"
    plans.mkdir(parents=True)
    (plans / "session-2026-01-01.md").write_text("see `mise.toml`\n", encoding="utf-8")
    newest = plans / "session-2026-01-02.md"
    newest.write_text("see `docs/gone.md`\n", encoding="utf-8")
    # mtime decides, so make the intended target unambiguously newer.
    os.utime(plans / "session-2026-01-01.md", (1, 1))
    os.utime(newest, (2, 2))
    assert handoff.main([], root) == 1


def test_main_exits_2_when_there_is_no_handoff_to_check(tmp_path: Path):
    root = _repo(tmp_path)
    assert handoff.main([], root) == 2


# ---------------------------------------------------------- reporting ----


def test_the_report_names_the_claim_its_line_and_what_was_found(tmp_path: Path):
    """Criterion: fixing a finding should need no further investigation."""
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    findings = handoff.check(root, "\n\nsee `docs/gone.md`\n")
    report = handoff.render(findings, source="h.md")
    assert "docs/gone.md" in report
    assert ":3" in report
    assert "no such path" in report


def test_the_report_counts_every_verdict_even_when_clean(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    report = handoff.render(handoff.check(root, "see `docs/a.md`\n"), source="h.md")
    assert "1 OK" in report
