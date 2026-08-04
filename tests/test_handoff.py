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

from kb_setup import citations, gates, handoff

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
