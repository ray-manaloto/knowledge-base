# Copyright (c) 2026 Raymond Manaloto
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

from conftest import handoff_lead as _lead
from kb_setup import citations, gates, handoff
from kb_setup.result import Err, Ok, Rc, exit_code

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


def test_an_absent_marker_on_an_ambiguous_citation_fails(tmp_path: Path):
    """`` `SKILL.md` (absent) `` where seven real files match is not absent.

    The marker's whole defence is that it is checked both ways, and treating
    every non-RESOLVED state as "confirmed absent" quietly handed AMBIGUOUS —
    which means the citation matches SEVERAL real files — the same pass as a
    genuine miss. That is the mute button the both-ways rule exists to prevent.
    """
    root = _repo(tmp_path, {"a/S.md": "x\n", "b/S.md": "y\n"})
    (f,) = _fails(handoff.check(root, "see `S.md` (absent) now\n"))
    assert "resolves" in f.detail


def test_an_absent_marker_on_an_unverifiable_citation_stays_unverifiable(tmp_path: Path):
    """We cannot confirm the marker either — saying OK would claim we had."""
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    findings = handoff.check(root, "see `graphify/serve.py` (absent) now\n")
    assert [f.verdict for f in findings] == [handoff.Verdict.UNVERIFIABLE]


def test_a_reversed_line_range_fails(tmp_path: Path):
    """`file.md:20-10` is a transposed-digit typo — this tool's whole subject.

    Both ends sat inside the file, and the only checks were `start < 1` and
    `end > total`, so the one arrangement that cannot describe a real range
    passed as verified.
    """
    root = _repo(tmp_path, {"docs/a.md": "1\n2\n3\n4\n5\n"})
    (f,) = _fails(handoff.check(root, "see `docs/a.md:4-2`\n"))
    assert "range" in f.detail


def test_an_ordinary_line_range_still_passes(tmp_path: Path):
    """Control arm for the test above."""
    root = _repo(tmp_path, {"docs/a.md": "1\n2\n3\n4\n5\n"})
    assert _fails(handoff.check(root, "see `docs/a.md:2-4`\n")) == []


def test_a_zero_line_reference_fails(tmp_path: Path):
    """`path:0` — the other half of the bounds check, previously untested."""
    root = _repo(tmp_path, {"docs/a.md": "1\n2\n3\n"})
    assert _fails(handoff.check(root, "see `docs/a.md:0`\n")) != []


def test_the_report_names_every_verdict_even_at_zero(tmp_path: Path):
    """The summary's contract is that no state is indistinguishable from zero.

    Asserting only `"1 OK"` let a renderer that drops zero-valued counts pass
    while breaking exactly the property the counts exist to provide.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    report = handoff.render(handoff.check(root, "see `docs/a.md`\n"), source="h.md")
    for word in ("OK", "ambiguous", "unverifiable", "broken"):
        assert word in report


# ------------------------------------------------------- gate claims ----
#
# #147. The one check in `/clear-prep` step 6 that had nothing durable to read:
# the record #146 writes is what these read it against.
#
# The split that decides everything here is FAIL vs UNVERIFIABLE. A claim the
# record CONTRADICTS is wrong and exits 1; a claim the record cannot speak to —
# because there is none at that commit, or none for that gate — is unverifiable
# and exits 0. Collapsing the second into the first would make the checker fail
# on every fresh clone, since `.agent/` is machine-local and a clone has no
# records at all. Collapsing it the other way would make a missing record read
# as a pass, which is the false green the ticket exists to prevent.

_GATE_MISE = "".join(
    f"[tasks.{t}]\nrun = 'true'\n" for t in ("kb-build", "lint", "test", "kb-gates", "lint-docs")
)

_A = "a" * 40
_B = "b" * 40


def _gate_repo(tmp_path: Path, rows: list[gates.GateResult] | None = None, sha: str = _A) -> Path:
    """A fixture repo whose `mise.toml` declares gates, plus one gate record."""
    (tmp_path / "mise.toml").write_text(_GATE_MISE, encoding="utf-8")
    if rows is not None:
        gates.record(tmp_path, rows, sha=sha)
    return tmp_path


def _row(
    task: str, rc: int | None = 0, sha: str | None = _A, *, dirty: bool | None = False
) -> gates.GateResult:
    return gates.GateResult(task, rc, sha, "t", dirty=dirty)


def _gate_findings(root: Path, text: str) -> list[handoff.Finding]:
    return [f for f in handoff.check(root, text) if f.check == "gate"]


def test_a_gate_claim_the_record_confirms_passes(tmp_path: Path):
    """Criterion 2, and the positive control for every failure below."""
    root = _gate_repo(tmp_path, [_row("lint")])
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n")
    assert f.verdict is handoff.Verdict.OK


def test_a_gate_claim_the_record_contradicts_fails(tmp_path: Path):
    """The claim says green, the record says red. The record wins."""
    root = _gate_repo(tmp_path, [_row("lint", rc=1)])
    (f,) = _fails(_gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n"))
    assert "rc=1" in f.detail


def test_a_gate_recorded_as_not_run_never_passes_a_claim(tmp_path: Path):
    """`rc: null` is "no result was produced" — it is not a pass (#146)."""
    root = _gate_repo(tmp_path, [_row("lint", rc=None, sha=None, dirty=None)])
    (f,) = _fails(_gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n"))
    assert "no result" in f.detail


def test_a_claim_with_no_record_at_that_commit_is_unverifiable_not_wrong(tmp_path: Path):
    """Criterion 4. A fresh clone has no records; that is not evidence of a lie."""
    root = _gate_repo(tmp_path)
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n")
    assert f.verdict is handoff.Verdict.UNVERIFIABLE
    assert _fails(_gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n")) == []


def test_a_record_at_a_different_commit_does_not_vouch_for_the_claim(tmp_path: Path):
    """Criterion 3 and 5 — the REJECTING direction, at the file level.

    `lint rc=0` is recorded, truthfully, at another commit. A checker that
    searched for "a record saying lint passed" would pass this, and that is
    exactly the stale exit code vouching for code it never saw.
    """
    root = _gate_repo(tmp_path, [_row("lint", sha=_B)], sha=_B)
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n")
    assert f.verdict is not handoff.Verdict.OK
    assert _B[:12] in f.detail


def test_a_row_recorded_against_a_different_commit_fails(tmp_path: Path):
    """Criterion 3 at its sharpest: the FILE is this commit's, the ROW is not.

    #146 reads HEAD per gate, so an amend mid-run leaves a row bound to another
    commit inside a record keyed to this one. That row's exit code is about code
    the claimed commit never contained, and nothing but this check can see it.
    """
    root = _gate_repo(tmp_path, [_row("lint", sha=_B)])
    (f,) = _fails(_gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n"))
    assert _B[:12] in f.detail


def test_a_claim_naming_no_commit_is_unverifiable(tmp_path: Path):
    """Most historical handoffs claim `lint rc=0` and name no commit at all."""
    root = _gate_repo(tmp_path, [_row("lint")])
    (f,) = _gate_findings(root, "- `mise run lint` rc=0\n")
    assert f.verdict is handoff.Verdict.UNVERIFIABLE
    assert "no commit" in f.detail


def test_a_claim_whose_block_names_two_commits_is_ambiguous(tmp_path: Path):
    root = _gate_repo(tmp_path, [_row("lint")])
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}` and `{_B[:7]}`: `mise run lint` rc=0\n")
    assert f.verdict is handoff.Verdict.AMBIGUOUS


def test_a_gate_the_record_does_not_cover_is_unverifiable(tmp_path: Path):
    """`lint-docs` is a real task and is not in `GATE_TASKS`; that is not a defect."""
    root = _gate_repo(tmp_path, [_row("lint")])
    findings = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint-docs` rc=0\n")
    assert [f.verdict for f in findings] == [handoff.Verdict.UNVERIFIABLE]


def test_a_claim_recorded_over_a_dirty_tree_is_reported_but_does_not_fail(tmp_path: Path):
    """The gate ran, and it did not run on that commit. A caveat, not a lie.

    Gating before you commit is the normal rhythm here, so FAIL would be a
    false-positive machine — and silence would let "green at `<sha>`" stand for
    a tree that was never `<sha>`.
    """
    root = _gate_repo(tmp_path, [_row("lint", dirty=True)])
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n")
    assert f.verdict is handoff.Verdict.AMBIGUOUS
    assert "uncommitted" in f.detail


def test_a_claim_whose_row_could_not_read_head_is_unverifiable(tmp_path: Path):
    """The gate ran and is bound to no commit, so it can vouch for none."""
    root = _gate_repo(tmp_path, [_row("lint", sha=None)])
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n")
    assert f.verdict is handoff.Verdict.UNVERIFIABLE
    assert "bound to no commit" in f.detail


def test_an_unreadable_record_is_unverifiable(tmp_path: Path):
    root = _gate_repo(tmp_path)
    path = root / gates.GATES_DIR / f"gates-{_A}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n")
    assert f.verdict is handoff.Verdict.UNVERIFIABLE
    assert "could not read" in f.detail


def test_a_runner_claim_passes_when_every_recorded_gate_passed(tmp_path: Path):
    """`mise run kb-gates` **rc=0** asserts something about the whole record."""
    root = _gate_repo(tmp_path, [_row("lint"), _row("test")])
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run kb-gates` **rc=0**\n")
    assert f.verdict is handoff.Verdict.OK


def test_a_runner_claim_fails_when_a_recorded_gate_did_not_pass(tmp_path: Path):
    root = _gate_repo(tmp_path, [_row("lint"), _row("test", rc=1)])
    (f,) = _fails(_gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run kb-gates` **rc=0**\n"))
    assert "test" in f.detail


def test_a_runner_claim_fails_when_a_gate_was_never_reached(tmp_path: Path):
    """A `--stop` record is partial by construction; unreached is not neutral."""
    root = _gate_repo(tmp_path, [_row("lint"), _row("test", rc=None, sha=None, dirty=None)])
    assert _fails(_gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run kb-gates` **rc=0**\n"))


def test_a_runner_claim_of_failure_is_checked_too(tmp_path: Path):
    """Control arm: rc=1 claimed over an all-green record is also a mismatch."""
    root = _gate_repo(tmp_path, [_row("lint"), _row("test")])
    assert _fails(_gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run kb-gates` **rc=1**\n"))


def test_a_runner_claim_of_failure_passes_when_a_gate_failed(tmp_path: Path):
    root = _gate_repo(tmp_path, [_row("lint"), _row("test", rc=1)])
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run kb-gates` **rc=1**\n")
    assert f.verdict is handoff.Verdict.OK


def test_a_runner_claim_over_an_empty_record_is_unverifiable(tmp_path: Path):
    """Zero gates all passed, vacuously. Reading that as green is the false one."""
    root = _gate_repo(tmp_path, [])
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run kb-gates` **rc=0**\n")
    assert f.verdict is handoff.Verdict.UNVERIFIABLE


def test_a_token_that_is_not_a_declared_task_is_not_a_gate_claim(tmp_path: Path):
    """`timeout 60 …` returns rc=127` — real prose, and a claim about nothing."""
    root = _gate_repo(tmp_path, [_row("lint")])
    assert _gate_findings(root, "- `timeout 60 x` returns rc=127 on macOS\n") == []


def test_a_broken_gate_claim_exits_one(tmp_path: Path, capsys):
    """The exit code, end to end — the property the whole check is for."""
    root = _gate_repo(tmp_path, [_row("lint", rc=1)])
    (root / ".agent" / "plans").mkdir(parents=True, exist_ok=True)
    (root / ".agent" / "plans" / "session-x.md").write_text(
        f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n", encoding="utf-8"
    )
    assert handoff.main([], root) == 1
    assert "gate" in capsys.readouterr().out


def test_an_unverifiable_gate_claim_exits_zero(tmp_path: Path, capsys):
    """Control arm for the exit code: reported, and not a failure."""
    root = _gate_repo(tmp_path)
    (root / ".agent" / "plans").mkdir(parents=True, exist_ok=True)
    (root / ".agent" / "plans" / "session-x.md").write_text(
        f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n", encoding="utf-8"
    )
    assert handoff.main([], root) == 0
    assert "gate" in capsys.readouterr().out


def test_an_unreached_gate_is_not_described_as_a_tree_of_unknown_cleanliness(tmp_path: Path):
    """A row padded as "not run" carries `dirty: null` because nothing was asked.

    Reading that as "could not tell whether the tree was clean" describes a gate
    that never happened. Reachable on any `--stop` record, which is what the ship
    path writes every time — so this is the common case, not an edge one.
    """
    root = _gate_repo(tmp_path, [_row("lint", rc=1), _row("test", rc=None, sha=None, dirty=None)])
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run kb-gates` **rc=1**\n")
    assert f.verdict is handoff.Verdict.OK
    assert "clean" not in f.detail


def test_the_absent_marker_hint_is_not_printed_for_a_gate_failure(tmp_path: Path):
    """The hint teaches `` `path` (absent) ``, which a gate claim cannot carry.

    The arm fired on ANY failure, so once gate claims could fail, a run whose
    only defect was `lint rc=0` advised the reader to mark a path absent —
    unactionable advice attached to a finding it has nothing to do with.
    """
    root = _gate_repo(tmp_path, [_row("lint", rc=1)])
    report = handoff.render(
        handoff.check(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n"), source="h.md"
    )
    assert "(absent)" not in report


def test_the_absent_marker_hint_is_still_printed_for_a_path_failure(tmp_path: Path):
    """Control arm: scoping the hint must not delete it.

    `docs/a.md` has to EXIST for `docs/gone.md` to be a MISSING rather than an
    UNVERIFIABLE — without a real `docs/`, the citation reads as a claim about
    another repo and never reaches the FAIL this arm is about.
    """
    root = _gate_repo(tmp_path)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "a.md").write_text("x\n", encoding="utf-8")
    report = handoff.render(handoff.check(root, "see `docs/gone.md`\n"), source="h.md")
    assert "(absent)" in report


# ------------------------------------ cold-lane round 1 (#147) ----
#
# Five findings, every one of the same shape: a FALSE claim judged `OK` by the
# tool built to stop exactly that. None was caught by the 19 mutation arms,
# because an arm proves the claims you thought of.


def test_a_runner_claim_of_a_refused_run_is_not_confirmed_by_a_record(tmp_path: Path):
    """`kb-gates` exits 2 when it REFUSES, and a refusal writes no record.

    The comparison asked `(claim.rc == 0) == (unpassed == 0)`, making every
    non-zero claim equivalent — so a record of a completed run with a failed
    gate confirmed `rc=2`, a run that by the runner's own contract never
    happened.
    """
    root = _gate_repo(tmp_path, [_row("lint", rc=1)])
    (f,) = _fails(_gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run kb-gates` **rc=2**\n"))
    assert "refused" in f.detail


def test_a_runner_claim_of_one_is_still_confirmed_by_a_failed_gate(tmp_path: Path):
    """Control arm: tightening the comparison must not reject the real rc=1."""
    root = _gate_repo(tmp_path, [_row("lint", rc=1)])
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run kb-gates` **rc=1**\n")
    assert f.verdict is handoff.Verdict.OK


def test_a_duplicate_row_is_reported_rather_than_silently_resolved(tmp_path: Path):
    """`kb-gates -- lint lint` is accepted, so two rows for one task is reachable.

    The lookup returned the FIRST, so the second was invisible — and picking the
    row that agrees with the claim is precisely the failure this module exists
    to remove.
    """
    root = _gate_repo(tmp_path, [_row("lint", rc=0), _row("lint", rc=1)])
    (f,) = _gate_findings(root, f"- Gates on `{_A[:7]}`: `mise run lint` rc=0\n")
    assert f.verdict is handoff.Verdict.AMBIGUOUS
    assert "2 rows" in f.detail


def test_a_row_with_an_empty_sha_is_unbound_at_the_point_of_use():
    """`""` is falsy AND is not None, so it passed the drift and unbound checks.

    Asserted on `_judge` with a HAND-BUILT row, because everything above it
    normalises the input away. The first version of this test went through
    `gates.record()` -> `find_record` -> `_parse`, which turns `"" -> None` at
    read time — so `_judge_rows` never saw an empty string and the test passed
    identically with the pre-fix `r.sha is None` predicate restored. It asserted
    nothing, while its own docstring claimed it was hand-built on purpose.

    Confirmed by mutation before and after: reverting the predicate leaves the
    old form green and fails this one. (Cold lane round 2 — the fix surviving
    inside its own fix, in the test rather than in the code.)
    """
    row = gates.RecordedGate(task="lint", rc=0, sha="", dirty=False)
    record = gates.Record(sha=_A, path=Path("gates-x.json"), gates=(row,))
    f = handoff._judge(citations.GateClaim("lint", 0, (_A[:7],), 1), record)
    assert f.verdict is handoff.Verdict.UNVERIFIABLE
    assert "bound to no commit" in f.detail


def test_a_row_with_a_real_sha_is_bound_at_the_point_of_use():
    """Control arm: the point-of-use guard must not call every row unbound."""
    row = gates.RecordedGate(task="lint", rc=0, sha=_A, dirty=False)
    record = gates.Record(sha=_A, path=Path("gates-x.json"), gates=(row,))
    f = handoff._judge(citations.GateClaim("lint", 0, (_A[:7],), 1), record)
    assert f.verdict is handoff.Verdict.OK


# ------------------------------------------- mistyped extensions (#154) ----
#
# The gap: `mise.tomlx` exited 0 with `0 OK, 0 ambiguous, 0 unverifiable, 0
# broken`, while the control arm — a STEM typo, `citation.py` for
# `citations.py` — was caught and exited 1. A false negative in exactly the class
# the checker exists for. Every promotion arm below is paired with the silence
# arm that proves the mechanism can still say nothing.


def test_a_mistyped_extension_is_a_broken_citation(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    (f,) = _fails(handoff.check(root, "see `mise.tomlx` here\n"))
    assert f.claim == "mise.tomlx"
    assert f.line == 1
    assert "mise.toml" in f.detail


def test_an_unknown_but_valid_extension_is_still_not_reported(tmp_path: Path):
    """THE arm criterion 2 asks for, paired with the one above.

    `notes.org` names a real file whose extension is simply not in the
    allowlist. It was silent before this change and must stay silent after it,
    or the fix has bought a true positive at the price of the posture that makes
    the checker trustworthy.
    """
    root = _repo(tmp_path, {"notes.org": "x\n", "notes.md": "y\n"})
    findings = handoff.check(root, "see `notes.org` here\n")
    assert [f for f in findings if f.claim == "notes.org"] == []


def test_a_module_attribute_reference_is_still_not_reported(tmp_path: Path):
    """The 278-occurrence class the original mechanism would have promoted.

    Under the stem probe #154 first specified, `gates.record` resolved uniquely
    to `gates.py` and would have been reported. Nothing here may report it.
    """
    root = _repo(tmp_path, {"python/src/kb_setup/gates.py": "x\n"})
    findings = handoff.check(root, "see `gates.record` and `gates.RUNNER_TASK`\n")
    assert findings == []


def test_a_mistyped_extension_naming_nothing_real_is_not_reported(tmp_path: Path):
    """One edit from a known extension is not enough — the repair must resolve."""
    root = _repo(tmp_path, {"other.md": "x\n"})
    assert handoff.check(root, "see `codegraph.db` here\n") == []


def test_a_mistyped_extension_marked_absent_is_accepted(tmp_path: Path):
    """A handoff quoting the typo ON PURPOSE can say so, exactly like a path.

    This is not hypothetical: the handoff that filed #154 quotes `mise.tomlx` in
    prose as the example, and is the one occurrence the corpus measurement found.
    """
    root = _repo(tmp_path, {"mise.toml": _MISE})
    assert _fails(handoff.check(root, "the example `mise.tomlx` (absent) above\n")) == []


def test_a_mistyped_extension_that_resolves_after_repair_still_exits_1(tmp_path: Path):
    """The reproduction from the ticket, end to end at the exit code."""
    root = _repo(tmp_path, {"h.md": "see `mise.tomlx`\n"})
    assert handoff.main([str(root / "h.md")], root) == 1


def test_the_ticket_reproduction_exits_0_before_and_after_for_the_control(tmp_path: Path):
    """The ticket's own control arm: a STEM typo was already caught.

    Kept as a regression guard on the pairing, not on the new code — if this
    ever stops failing, the comparison the ticket rests on has gone stale.
    """
    root = _repo(tmp_path, {"h.md": "see `python/src/kb_setup/citation.py`\n"})
    (root / "python" / "src" / "kb_setup").mkdir(parents=True)
    (root / "python" / "src" / "kb_setup" / "citations.py").write_text("x\n", encoding="utf-8")
    assert handoff.main([str(root / "h.md")], root) == 1


def test_a_mistyped_extension_is_reported_as_a_path_check(tmp_path: Path):
    """So the `(absent)` hint in `render` applies to it — it is a path claim.

    `_PATH_CHECKS` scopes that hint, and a new check name would silently drop
    the one finding whose reader most needs to know the marker exists.
    """
    root = _repo(tmp_path, {"mise.toml": _MISE})
    (f,) = _fails(handoff.check(root, "see `mise.tomlx`\n"))
    assert f.check in handoff._PATH_CHECKS


def test_an_absent_marker_on_a_typo_that_actually_resolves_fails(tmp_path: Path):
    """The marker must be FALSIFIABLE here, exactly as it is for every other path.

    It was not. Routing a marked candidate through `resolve_extension_typo` gave
    it two exits — None and MISSING — and `_check_absent_marker` maps MISSING to
    OK, so the entire input space produced "no finding" or "OK" and no input
    could make the marker fail. Paste `(absent)` beside a real typo and it was
    silenced forever.

    Worse than the abstraction: `render` prints "the marker is checked both ways,
    so it cannot hide a real miss" on these findings by design, so the tool
    advertised a promise that was false for this one check.
    (Silent-failure lane, F1.)
    """
    root = _repo(tmp_path, {"notes.pyy": "x\n", "notes.py": "y\n"})
    (f,) = _fails(handoff.check(root, "see `notes.pyy` (absent) here\n"))
    assert "marked" in f.detail


def test_an_absent_marker_on_a_genuine_typo_is_still_accepted(tmp_path: Path):
    """Control arm: making the marker falsifiable must not break its real use."""
    root = _repo(tmp_path, {"mise.toml": _MISE})
    assert _fails(handoff.check(root, "the example `mise.tomlx` (absent) above\n")) == []


# ------------------------------------------------- the branch a handoff is for ----
#
# #149. `kb-ship` refuses a branch whose handoff has broken citations, and SKIPS
# — explicitly, never silently — when no handoff describes the current branch.
# The skip is the load-bearing half: measured on 2026-08-03, the newest handoff
# described the session that STARTED the work rather than the one shipping it,
# and without the branch match the gate would have blocked a healthy PR.


def _plans(root: Path, files: dict[str, tuple[str, int]]) -> Path:
    """Write `.agent/plans/<name>` for each `{name: (body, mtime)}`.

    mtime is explicit because selection is by mtime, and two files written in
    the same test run can land in the same clock tick — a tie the sort would
    break arbitrarily, giving a test that passes on one machine.
    """
    plans = root / ".agent" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    for name, (body, mtime) in files.items():
        path = plans / name
        path.write_text(body, encoding="utf-8")
        os.utime(path, (mtime, mtime))
    return plans


def test_the_recorded_branch_is_the_first_one_the_lead_names():
    assert handoff.recorded_branch(_lead("feat/x")) == "feat/x"


def test_the_first_of_two_branches_in_one_lead_wins():
    """A real handoff row names the branch, then names another in an aside.

    Without a lead that mentions two, "first wins" is unfalsifiable — the last
    would pass every single-mention case identically.
    """
    text = (
        "# H\n\n| branch | `main` (the round's branch `feat/settled-claims` is merged) |\n\n## D\n"
    )
    assert handoff.recorded_branch(text) == "main"


def test_a_handoff_that_names_no_branch_records_none():
    assert handoff.recorded_branch("# Session handoff\n\nall done.\n\n## Detail\n") is None


def test_a_branch_named_only_after_the_lead_is_not_recorded():
    """The bound, asserted rather than assumed — see `citations.document_lead`."""
    text = "# H\n\nnothing here\n\n## Detail\n\nbranch `feat/late`\n"
    assert handoff.recorded_branch(text) is None


def test_an_older_handoff_for_this_branch_is_masked_by_a_newer_one(tmp_path: Path):
    """NEWEST-ONLY. Only the newest handoff can speak, matching or not.

    This asserted the opposite for one round — that the scan should reach past a
    newer handoff for another branch and check this branch's own. Measured over
    the real 35-handoff corpus, that reading refuses **8 of the 21 branches**
    they record, every one on a handoff 1-7 days stale whose cited paths have
    since been deleted by unrelated commits. It relocates the harm #149 exists to
    remove rather than removing it, and `.agent/plans/` is append-only, so it
    grows. The criterion was amended on the issue.

    The BROKEN handoff here is the older one for `work`, so a scan would refuse
    and newest-only skips — the two readings are distinguishable by this fixture,
    which is the point of building it this way round.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    _plans(
        root,
        {
            "session-2026-01-01.md": (_lead("work", "see `docs/gone.md`\n"), 1),
            "session-2026-01-02.md": (_lead("other", "see `docs/a.md`\n"), 2),
        },
    )
    got = handoff.check_for_branch(root, "work")
    assert got.coverage is handoff.Coverage.SKIPPED
    assert got.findings == ()
    assert "session-2026-01-02.md" in got.summary
    assert "other" in got.summary


def test_the_newest_of_several_handoffs_for_one_branch_wins(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    _plans(
        root,
        {
            "session-2026-01-01.md": (_lead("work", "see `docs/gone.md`\n"), 1),
            "session-2026-01-02.md": (_lead("work", "see `docs/a.md`\n"), 2),
        },
    )
    got = handoff.check_for_branch(root, "work")
    assert got.coverage is handoff.Coverage.OK
    assert got.source == "session-2026-01-02.md"


def test_a_matching_handoff_with_a_broken_citation_is_broken(tmp_path: Path):
    """Criterion 3 — this is what refuses the push."""
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    _plans(root, {"session-2026-01-01.md": (_lead("work", "see `docs/gone.md`\n"), 1)})
    got = handoff.check_for_branch(root, "work")
    assert got.coverage is handoff.Coverage.BROKEN
    assert [f.claim for f in got.findings if f.verdict is handoff.Verdict.FAIL] == ["docs/gone.md"]


def test_a_matching_handoff_whose_findings_are_only_advisory_is_ok(tmp_path: Path):
    """The strict/advisory split #145 draws, reaching the ship gate unchanged.

    An UNVERIFIABLE gate claim is reported and must not refuse a push: `.agent/`
    is machine-local, so a record's absence is normal rather than a defect.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    _plans(root, {"session-2026-01-01.md": (_lead("work", "`mise run lint` **rc=0**\n"), 1)})
    got = handoff.check_for_branch(root, "work")
    assert got.coverage is handoff.Coverage.OK
    assert handoff.Verdict.UNVERIFIABLE in {f.verdict for f in got.findings}


def test_no_handoff_for_this_branch_is_skipped_and_says_so(tmp_path: Path):
    """Criteria 2 and 4 — the SKIP is REPORTED, and never reads as a pass."""
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    _plans(root, {"session-2026-01-01.md": (_lead("other", "see `docs/a.md`\n"), 1)})
    got = handoff.check_for_branch(root, "work")
    assert got.coverage is handoff.Coverage.SKIPPED
    assert "SKIP" in got.summary
    assert "work" in got.summary
    assert got.source == ""


def test_a_newest_handoff_recording_no_branch_is_skipped_naming_that(tmp_path: Path):
    """6 of 35 committed handoffs record no branch — the message must differ.

    "records no branch" and "records `other`" are different reasons to skip, and
    only the first tells a reader the fix is to write the branch into the lead.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    _plans(root, {"session-2026-01-01.md": ("# H\n\nnothing here\n\n## D\n", 1)})
    got = handoff.check_for_branch(root, "work")
    assert got.coverage is handoff.Coverage.SKIPPED
    assert "records no branch" in got.summary


def test_a_broken_handoff_for_another_branch_does_not_refuse(tmp_path: Path):
    """Criterion 5 — the regression guard for the measured 2026-08-03 case.

    The only handoff on disk is BROKEN and describes a different branch. It must
    produce a skip, not a refusal, or the gate blocks a healthy PR.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    _plans(root, {"session-2026-01-01.md": (_lead("older", "see `docs/gone.md`\n"), 1)})
    got = handoff.check_for_branch(root, "work")
    assert got.coverage is handoff.Coverage.SKIPPED
    assert got.findings == ()


def test_a_newest_handoff_that_cannot_be_read_is_skipped_not_raised(tmp_path: Path):
    """The `OSError` arm — reachable, and it was the one guard no arm could kill.

    A cold lane deleted the whole try/except and every test still passed. The
    reaching case it constructed is a DIRECTORY where the newest handoff should
    be, which an interrupted checkout or a stray `mkdir` produces. Without the
    guard this raises `IsADirectoryError` up through `_handoff_holds` and
    `ship_main`, so `mise run kb-ship` dies with a traceback instead of
    reporting a clean SKIP — a gate that crashes is not a gate that refuses.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    plans = root / ".agent" / "plans"
    plans.mkdir(parents=True)
    (plans / "session-2026-01-01.md").mkdir()
    got = handoff.check_for_branch(root, "work")
    assert got.coverage is handoff.Coverage.SKIPPED
    assert "could not be read" in got.summary
    assert got.findings == ()


def test_no_handoffs_at_all_is_skipped(tmp_path: Path):
    root = _repo(tmp_path)
    got = handoff.check_for_branch(root, "work")
    assert got.coverage is handoff.Coverage.SKIPPED
    assert "SKIP" in got.summary


def test_an_unreadable_branch_is_skipped_rather_than_matched(tmp_path: Path):
    """None means git could not be asked (#144) — it is not a branch to match on."""
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    _plans(root, {"session-2026-01-01.md": (_lead("work", "see `docs/gone.md`\n"), 1)})
    got = handoff.check_for_branch(root, None)
    assert got.coverage is handoff.Coverage.SKIPPED
    assert got.findings == ()
    # The SUMMARY, not just the state. Without the guard this still skips — no
    # handoff records `None` — but it would say "none of the 1 handoff(s)
    # records branch `None`", which reads as a checked answer about a branch
    # nobody is on. The guard exists for the sentence, so the sentence is what
    # this asserts; asserting only SKIPPED made the guard unfalsifiable.
    assert "could not be read" in got.summary
    assert "None" not in got.summary


def test_the_ok_summary_names_the_handoff_and_its_counts(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    _plans(root, {"session-2026-01-01.md": (_lead("work", "see `docs/a.md`\n"), 1)})
    got = handoff.check_for_branch(root, "work")
    assert "session-2026-01-01.md" in got.summary
    assert "work" in got.summary


# --------------------------------------------------- elided report claims ----
#
# #148. `_check_elided` is the only check whose citations `path_citations`
# refuses by construction, so every test here would have passed vacuously before
# the extractor existed — the control arm for that is
# `test_an_elided_citation_is_checked_at_all` below, which asserts a finding is
# produced rather than merely that none failed.

_REPORTS = ".agent/kb/review/reports"
_AGENTS = ".agent/kb/reports/agents"


def test_an_elided_citation_is_checked_at_all(tmp_path: Path):
    """Control arm: prove the check RUNS before trusting any pass below.

    Asserts a finding exists for the token, not just that nothing failed. A
    check that extracts nothing produces no failures either, and the two are
    indistinguishable from `_fails(...) == []` alone.
    """
    root = _repo(tmp_path, {f"{_REPORTS}/review-abc1234def-cold.md": "x\n"})
    findings = handoff.check(root, f"see `{_REPORTS}/review-abc1234…-cold.md`\n")
    assert [f.check for f in findings] == ["elided"]


def test_an_elided_report_citation_that_resolves_does_not_fail(tmp_path: Path):
    root = _repo(tmp_path, {f"{_REPORTS}/review-abc1234def-cold.md": "x\n"})
    assert _fails(handoff.check(root, f"see `{_REPORTS}/review-abc1234…-cold.md`\n")) == []


def test_an_elided_report_citation_with_no_report_fails(tmp_path: Path):
    """THE TICKET: a report that was never written must not pass as one that was."""
    root = _repo(tmp_path, {f"{_REPORTS}/review-abc1234def-cold.md": "x\n"})
    (f,) = _fails(handoff.check(root, f"see `{_REPORTS}/review-deadbee…-cold.md`\n"))
    assert f.check == "elided"
    assert "nothing matches" in f.detail


def test_an_elided_citation_naming_a_lane_that_never_ran_fails(tmp_path: Path):
    """The sha is real and the LANE is not — a sha-only check would wave this through."""
    root = _repo(tmp_path, {f"{_REPORTS}/review-abc1234def-cold.md": "x\n"})
    assert len(_fails(handoff.check(root, f"see `{_REPORTS}/review-abc1234…-spec.md`\n"))) == 1


def test_a_lane_variant_is_stripped_when_matching_a_lane_report(tmp_path: Path):
    """Criterion 3: a lane RECORDED with a variant must not look like one that never ran.

    `kb_setup.review.report_path` strips the `:variant` when it WRITES the file,
    so a handoff citing the lane as recorded (`cold:codex`) names a filename that
    can never exist. Without the strip this is a confident false accusation
    against a lane whose report is on disk — the direction #145 calls fatal.
    """
    root = _repo(tmp_path, {f"{_REPORTS}/review-abc1234def-cold.md": "x\n"})
    assert _fails(handoff.check(root, f"see `{_REPORTS}/review-abc1234…-cold:codex.md`\n")) == []


def test_a_stripped_variant_does_not_excuse_a_lane_with_no_report(tmp_path: Path):
    """The other arm of the strip: it repairs the SPELLING, it does not vouch.

    Without this, `strip_lane_variant` could be implemented as "drop everything
    after the last `-`" and every lane would resolve to every report.
    """
    root = _repo(tmp_path, {f"{_REPORTS}/review-abc1234def-cold.md": "x\n"})
    text = f"see `{_REPORTS}/review-abc1234…-spec:codex.md`\n"
    assert len(_fails(handoff.check(root, text))) == 1


def test_a_report_on_disk_that_nothing_mentions_is_not_a_finding(tmp_path: Path):
    """Criterion 4, second half. The check reads the handoff; it never audits the dir."""
    root = _repo(
        tmp_path,
        {
            f"{_REPORTS}/review-abc1234def-cold.md": "x\n",
            f"{_REPORTS}/review-abc1234def-spec.md": "y\n",
            f"{_AGENTS}/nobody-mentions-me.md": "z\n",
        },
    )
    findings = handoff.check(root, f"see `{_REPORTS}/review-abc1234…-cold.md`\n")
    assert _fails(findings) == []
    assert len(findings) == 1


def test_an_elided_citation_marked_absent_and_absent_is_ok(tmp_path: Path):
    root = _repo(tmp_path, {f"{_REPORTS}/review-abc1234def-cold.md": "x\n"})
    findings = handoff.check(root, f"see `{_REPORTS}/review-deadbee…-cold.md` (absent)\n")
    assert _fails(findings) == []


def test_an_elided_citation_marked_absent_that_resolves_fails(tmp_path: Path):
    """Both arms: the marker cannot be a mute button here either."""
    root = _repo(tmp_path, {f"{_REPORTS}/review-abc1234def-cold.md": "x\n"})
    (f,) = _fails(handoff.check(root, f"see `{_REPORTS}/review-abc1234…-cold.md` (absent)\n"))
    assert "resolves" in f.detail


def test_an_elided_citation_into_another_repo_is_reported_but_does_not_fail(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    findings = handoff.check(root, "see `graphify/src/wat…er.py`\n")
    assert _fails(findings) == []
    assert [f.verdict for f in findings] == [handoff.Verdict.UNVERIFIABLE]


def test_a_repaired_lane_citation_cannot_match_outside_the_report_directory(tmp_path: Path):
    """THE CLASS THAT TOOK THREE ROUNDS TO CLOSE — a repaired token going hunting.

    `resolve_elided` matches a bare filename against every basename in the repo,
    so ANY repair landing on a real file anywhere is a false green. Two rounds
    narrowed which citations got repaired and neither asked where the repaired
    token would then be looked up:

    * round 1 — `review-gu…:draft.md` found `review-guide-notes.md`;
    * round 2, after the lane-suffix guard — `review-check…-spec:draft.md`
      found `review-checklist-for-spec.md`.

    Both are asserted here rather than only the latest, because the fix is
    supposed to close the mechanism and not just the newest instance of it.
    """
    root = _repo(
        tmp_path,
        {
            "review-guide-notes.md": "unrelated\n",
            "review-checklist-for-spec.md": "unrelated\n",
            f"{_REPORTS}/review-abc1234def-cold.md": "a real report\n",
        },
    )
    for token in ("review-gu…:draft.md", "review-check…-spec:draft.md"):
        fails = _fails(handoff.check(root, f"see `{token}`\n"))
        assert len(fails) == 1, token
        assert "nothing matches" in fails[0].detail

    # CONTROL: the real citation still resolves, so the fix did not simply
    # refuse everything — which would pass every assertion above for free.
    assert _fails(handoff.check(root, "see `review-abc1234…-cold:codex.md`\n")) == []


def test_an_unrelated_file_inside_the_report_directory_is_not_a_match(tmp_path: Path):
    """The narrower half: even inside REPORT_DIR, the sha must still match.

    Anchoring the repair to the directory is necessary, not sufficient — the
    cold lane noted a file living in `REPORT_DIR` that merely ends in a lane
    suffix would also match if the sha portion were ignored.
    """
    root = _repo(tmp_path, {f"{_REPORTS}/review-checklist-for-spec.md": "unrelated\n"})
    (f,) = _fails(handoff.check(root, "see `review-abc1234…-spec:draft.md`\n"))
    assert "nothing matches" in f.detail


# --------------------------------------------------------------------------
# The `check_handoff` boundary (§2 R5)
# --------------------------------------------------------------------------
#
# `main` returns an int and the tests above assert 0/1/2 on it. What none of
# them can see is which KIND of outcome produced the code: this is the one
# converted module that reaches all three `Rc` codes, and a bare int cannot
# distinguish "the checker ran and contradicted a claim" from "the checker
# could not find anything to check".


def test_handoff_a_contradicted_claim_is_ok_with_findings(tmp_path: Path):
    """A FAIL is the checker DOING ITS JOB, so it is `Ok(rc=FINDINGS)`, not `Err`.

    `docs/a.md` is in the fixture on purpose: without a real `docs/` entry the
    citation is UNVERIFIABLE ("may name another repo") and exits 0, which is
    what the first draft of this test asserted FINDINGS against. Same fixture
    requirement as `test_a_citation_about_this_repo_that_is_wrong_still_fails`.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n", "h.md": "see `docs/nope.md`\n"})

    result = handoff.check_handoff([str(root / "h.md")], root)

    assert isinstance(result, Ok)
    assert result.rc is Rc.FINDINGS
    assert [f.claim for f in result.value.findings if f.verdict is handoff.Verdict.FAIL] == [
        "docs/nope.md"
    ]


def test_handoff_a_clean_handoff_is_ok_with_rc_ok(tmp_path: Path):
    """CONTROL ARM: `Ok` is reachable with BOTH rcs, so the test above discriminates."""
    root = _repo(tmp_path, {"docs/a.md": "x\n", "h.md": "see `docs/a.md`\n"})

    result = handoff.check_handoff([str(root / "h.md")], root)

    assert isinstance(result, Ok)
    assert result.rc is Rc.OK


def test_handoff_a_missing_target_is_a_bad_request(tmp_path: Path):
    """A named path that is not a file is the CALLER's error — `Rc.BAD_REQUEST`.

    Distinct from `skill_lint`'s `Rc.NOT_RUN` for a glob matching nothing: there
    the request was fine and the gate still never looked; here the request
    itself cannot be honoured and the caller fixes it by asking differently.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n"})

    result = handoff.check_handoff([str(root / "nope.md")], root)

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert "no such file" in result.message


def test_handoff_no_handoff_at_all_is_a_bad_request(tmp_path: Path):
    """The other BAD_REQUEST route: no argument, and nothing under .agent/plans/."""
    root = _repo(tmp_path, {"docs/a.md": "x\n"})

    result = handoff.check_handoff([], root)

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST


def test_handoff_boundary_prints_nothing(tmp_path: Path, capsys):
    """Rendering belongs to `main`; the boundary only returns.

    Armed on the FINDINGS path — a boundary that merely forgot to print its
    failures would pass a clean-input version of this test.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n", "h.md": "see `docs/nope.md`\n"})

    handoff.check_handoff([str(root / "h.md")], root)
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""


def test_handoff_int_wrapper_is_exit_code_of_boundary(tmp_path: Path):
    """The equivalence that makes the split safe, on all three outcomes."""
    root = _repo(tmp_path, {"docs/a.md": "x\n", "ok.md": "see `docs/a.md`\n"})
    (root / "bad.md").write_text("see `docs/nope.md`\n", encoding="utf-8")

    for args in ([str(root / "ok.md")], [str(root / "bad.md")], [str(root / "gone.md")]):
        assert handoff.main(args, root) == exit_code(handoff.check_handoff(args, root))


# --------------------------------------------------------- HEAD claims ----
#
# The sixth check, and the only one about the handoff ITSELF. Every arm below
# uses the `git` fixture rather than a bare tmp_path, because the question is
# ancestry and a directory has none. The five states share one shape so that a
# verdict difference is visibly the STATE's doing and not the fixture's.


def _head_findings(root: Path, sha: str) -> list[handoff.Finding]:
    text = f"# Session handoff\n\n- **branch**: `work`\n- **HEAD**: `{sha}`\n\n## Detail\n"
    return [f for f in handoff.check(root, text) if f.check == "head"]


def test_a_head_claim_naming_the_current_commit_is_ok(commit_file, tmp_path: Path):
    """Positive control for every HEAD arm below — without it they prove nothing."""
    sha = commit_file("docs/a.md")

    got = _head_findings(tmp_path, sha)

    assert [f.verdict for f in got] == [handoff.Verdict.OK]


def test_a_head_claim_behind_by_only_exempt_paths_is_ambiguous_not_broken(
    commit_file, tmp_path: Path
):
    """THE RECURRING CASE: the handoff names its own closing commit's parent.

    `/clear-prep` writes the handoff at step 4b and commits the `kb-remember`
    output at step 5, so the recorded HEAD is that commit's parent every round.

    AMBIGUOUS rather than FAIL because `review.EXEMPT_PATHS` is exactly the set
    that cannot invalidate a receipt or a gate result — and because a check that
    blocks a ship over a `kb-remember` file is one people route around.
    """
    sha = commit_file("docs/a.md")
    commit_file("graphify-out/memory/query_20260822_x.md")

    got = _head_findings(tmp_path, sha)

    assert [f.verdict for f in got] == [handoff.Verdict.AMBIGUOUS]
    assert "closing artifacts" in got[0].detail


def test_a_head_claim_behind_by_reviewed_work_fails(commit_file, tmp_path: Path):
    """The arm that proves the test above is not just "behind is always AMBIG".

    Same shape, same distance behind — only the PATH of the later commit differs.
    """
    sha = commit_file("docs/a.md")
    commit_file("python/src/kb_setup/thing.py")

    got = _head_findings(tmp_path, sha)

    assert [f.verdict for f in got] == [handoff.Verdict.FAIL]
    assert "python/src/kb_setup/thing.py" in got[0].detail


def test_a_head_claim_mixing_exempt_and_reviewed_paths_fails(git, commit_file, tmp_path: Path):
    """One reviewed path is enough. A delta is exempt only if ALL of it is.

    Without this arm the exempt branch could be reached by an `any()` and the
    two tests above would both still pass.
    """
    sha = commit_file("docs/a.md")
    (tmp_path / "graphify-out" / "memory").mkdir(parents=True, exist_ok=True)
    (tmp_path / "graphify-out" / "memory" / "q.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "python").mkdir(parents=True, exist_ok=True)
    (tmp_path / "python" / "thing.py").write_text("x\n", encoding="utf-8")
    git("add", "--", "graphify-out/memory/q.md", "python/thing.py")
    git("commit", "-q", "-m", "both")

    got = _head_findings(tmp_path, sha)

    assert [f.verdict for f in got] == [handoff.Verdict.FAIL]


def test_a_head_claim_on_another_line_of_history_is_unverifiable(git, commit_file, tmp_path: Path):
    """A squash-merge, a rebase or a branch switch — the ORDINARY end state.

    `kb-land` squash-merges, so after it every handoff for the landed branch
    names a commit `main` does not descend from. Calling that wrong would train
    readers to ignore the check, which this module's header warns against.
    """
    git("checkout", "-q", "-b", "other")
    elsewhere = commit_file("docs/other.md")
    git("checkout", "-q", "work")
    commit_file("docs/a.md")

    got = _head_findings(tmp_path, elsewhere)

    assert [f.verdict for f in got] == [handoff.Verdict.UNVERIFIABLE]


def test_a_head_claim_naming_no_such_commit_fails(commit_file, tmp_path: Path):
    """A sha nobody can look up is a broken citation, the same class as a path."""
    commit_file("docs/a.md")

    got = _head_findings(tmp_path, "0" * 40)

    assert [f.verdict for f in got] == [handoff.Verdict.FAIL]


def test_a_stale_head_claim_makes_the_run_exit_1(commit_file, tmp_path: Path):
    """The strict/advisory split, end to end: STALE is wrongness, so it exits 1.

    Asserted at `main` rather than inferred from the verdict, because the exit
    code is what `kb-ship` reads.
    """
    sha = commit_file("docs/a.md")
    commit_file("python/thing.py")
    body = f"# Session handoff\n\n- **branch**: `work`\n- **HEAD**: `{sha}`\n\n## Detail\n"
    (tmp_path / "h.md").write_text(body, encoding="utf-8")

    assert handoff.main([str(tmp_path / "h.md")], tmp_path) == 1
