"""Tests for the `kb-setup review-receipt` command.

Split from `test_review.py` because the CLI is where two of this feature's
defects lived, and neither was reachable from the module tests: the writer
defaulted `--blocking` to 0 behind a reader that rejects a missing count, and
`"--5".lstrip("-").isdigit()` let a negative reach `int()`. A module test
suite green over both is why `verify-before-advancing.md` asks for the
module's own tests rather than the suite total.

Every FAIL arm here has its PASS arm, and vice versa.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import cli, review

_ALL_LANES = "standards,spec,cold:codex,silent-failure"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo root whose HEAD and merge-base are stubbed to fixed values."""
    monkeypatch.setattr(review, "head_sha", lambda _root: "a" * 40)
    monkeypatch.setattr(review, "base_sha", lambda _root, _fp, **_kw: "b" * 40)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _reports(repo_root: Path, *lanes: str) -> None:
    """Write a non-empty report for each named lane."""
    for lane in lanes:
        path = review.report_path(repo_root, "a" * 40, lane)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("NO FINDINGS", encoding="utf-8")


def _run(repo_root: Path, *args: str) -> int:
    """Invoke the review-receipt subcommand the way the mise task does."""
    return cli.main(["review-receipt", *args])


def test_writes_a_receipt_for_head(repo: Path) -> None:
    """The PASS arm: all four lanes accounted for, with reports on disk."""
    _reports(repo, "standards", "spec", "cold", "silent-failure")
    assert _run(repo, "--lanes", _ALL_LANES, "--blocking", "0", "--findings", "3") == 0

    data = json.loads(review.receipt_path(repo, "a" * 40).read_text(encoding="utf-8"))
    assert data["sha"] == "a" * 40
    assert data["fixed_point_sha"] == "b" * 40
    assert data["findings"] == 3


def test_blocking_is_required(repo: Path) -> None:
    """Omitting `--blocking` must refuse, not silently mean zero.

    The reader rejects a MISSING blocking count as ambiguity rather than
    consent. Defaulting it here handed that fail-closed reader a fail-open
    writer — the one field that gates was the one nobody had to state.
    """
    _reports(repo, "standards", "spec", "cold", "silent-failure")
    assert _run(repo, "--lanes", _ALL_LANES) == 2
    assert not review.receipt_path(repo, "a" * 40).exists()


def test_blocking_zero_stated_explicitly_passes(repo: Path) -> None:
    """CONTROL ARM: the refusal above is about absence, not about the value."""
    _reports(repo, "standards", "spec", "cold", "silent-failure")
    assert _run(repo, "--lanes", _ALL_LANES, "--blocking", "0") == 0


@pytest.mark.parametrize("bad", ["-5", "--5", "1.5", "one", "", "²"])
def test_non_integer_blocking_is_refused(repo: Path, bad: str) -> None:
    """`--5` is the interesting one: `.lstrip("-").isdigit()` accepted it.

    `²` is the second: `"²".isdigit()` is True but `int("²")` raises, so the
    guard whose comment says it prevents a ValueError used to raise one.
    """
    _reports(repo, "standards", "spec", "cold", "silent-failure")
    assert _run(repo, "--lanes", _ALL_LANES, "--blocking", bad) == 2


@pytest.mark.parametrize(
    "args",
    [
        ("--blocking", "2", "--blocking", "0"),
        ("--blocking", "0", "--blocking", "2"),
    ],
)
def test_a_repeated_flag_is_refused_rather_than_resolved(repo: Path, args: tuple[str, ...]) -> None:
    """Stating one flag twice must refuse, not silently keep whichever came first.

    `_opt` returns the FIRST occurrence, so both orderings below quietly recorded
    a number other than what the command line reads as — a one-token way to
    misstate the field that actually gates. Both orderings are parametrized
    because keeping the LAST would be an equally wrong fix that only one of them
    would catch.
    """
    _reports(repo, "standards", "spec", "cold", "silent-failure")
    assert _run(repo, "--lanes", _ALL_LANES, *args) == 2
    assert not review.receipt_path(repo, "a" * 40).exists()


def test_dangling_fixed_point_flag_is_refused(repo: Path) -> None:
    """`--fixed-point` with no value must refuse, not silently mean `main`.

    `_opt` returns its default when a flag is LAST, so the command line said one
    thing and the receipt recorded another — the same class as the repeated-flag
    hole, on the field that says WHAT was reviewed.
    """
    _reports(repo, "standards", "spec", "cold", "silent-failure")
    assert _run(repo, "--lanes", _ALL_LANES, "--blocking", "0", "--fixed-point") == 2
    assert not review.receipt_path(repo, "a" * 40).exists()


@pytest.mark.parametrize("empty", ["", "   ", "\t"])
def test_an_explicitly_empty_fixed_point_is_refused(
    repo: Path, capsys: pytest.CaptureFixture[str], empty: str
) -> None:
    """`--fixed-point ""` must refuse too — the guard tested the wrong thing.

    The dangling case above and this one are one defect with two spellings, and
    only the first was closed. `_opt` returns its DEFAULT (None) for a flag with
    no following token, but returns the token itself — `""` — when the token is
    present and empty. The guard asked `is None`, so the empty spelling sailed
    through and `or "main"` substituted a base the command line never stated: a
    one-token way to make the receipt say something other than what it reads as,
    which is exactly the hole `114adce` closed for repeated flags. (#55)

    **The message is asserted, not just the exit code, and that is the whole
    point of this test.** Measured while writing it: with the guard reverted to
    its pre-fix form, the two whitespace spellings still exited 2 — refused
    downstream by `_check_identity`'s "names no fixed point" on a `.strip()`ed
    field, several layers past the guard under test. An rc-only assertion would
    have gone green on a mutation that restores the defect, which is a probe
    passing for a reason other than the one it claims
    (`probes-need-a-control-arm.md`). Pinning the CLI's own wording is what makes
    all three spellings actually exercise the guard.
    """
    _reports(repo, "standards", "spec", "cold", "silent-failure")
    rc = _run(repo, "--lanes", _ALL_LANES, "--blocking", "0", "--fixed-point", empty)
    assert rc == 2
    assert "--fixed-point needs a value" in capsys.readouterr().err
    assert not review.receipt_path(repo, "a" * 40).exists()


def test_a_stated_fixed_point_is_still_accepted(repo: Path) -> None:
    """CONTROL ARM — the refusals above are about the missing value, not the flag."""
    _reports(repo, "standards", "spec", "cold", "silent-failure")
    assert _run(repo, "--lanes", _ALL_LANES, "--blocking", "0", "--fixed-point", "main") == 0


def test_lanes_is_required(repo: Path) -> None:
    """A receipt naming no lane is not a receipt."""
    assert _run(repo, "--blocking", "0") == 2


def test_invented_lane_is_refused_before_any_write(repo: Path) -> None:
    """A refused receipt must leave NOTHING on disk.

    "no review yet" and "a review that failed" should not look the same to the
    next reader, so validation happens before the write.
    """
    assert _run(repo, "--lanes", "placeholder", "--blocking", "0") == 2
    assert not review.receipt_path(repo, "a" * 40).exists()


def test_partial_lane_coverage_is_refused(repo: Path) -> None:
    """Naming one lane must not buy a pass for the other three."""
    _reports(repo, "standards")
    assert _run(repo, "--lanes", "standards", "--blocking", "0") == 2


def test_claimed_lane_without_a_report_is_refused(repo: Path) -> None:
    """The widest hole: full coverage claimed in one command, no lane run."""
    _reports(repo, "standards", "spec", "cold")  # silent-failure has no report
    assert _run(repo, "--lanes", _ALL_LANES, "--blocking", "0") == 2
    assert not review.receipt_path(repo, "a" * 40).exists()


def test_justified_skip_needs_no_report(repo: Path) -> None:
    """A lane that legitimately does not apply owes no report."""
    _reports(repo, "standards", "spec")
    rc = _run(
        repo,
        "--lanes",
        "standards,spec",
        "--skipped",
        "cold:not-applicable-docs-only,silent-failure:not-applicable-docs-only",
        "--blocking",
        "0",
    )
    assert rc == 0


def test_not_yet_run_skip_is_refused(repo: Path) -> None:
    """CONTROL ARM for the test above — a gap is not a justification."""
    _reports(repo, "standards", "spec")
    rc = _run(
        repo,
        "--lanes",
        "standards,spec",
        "--skipped",
        "cold:not-yet-run,silent-failure:not-yet-run",
        "--blocking",
        "0",
    )
    assert rc == 2


def test_blocking_findings_refuse_the_receipt(repo: Path) -> None:
    """An unresolved blocking finding must not be recordable as a pass."""
    _reports(repo, "standards", "spec", "cold", "silent-failure")
    assert _run(repo, "--lanes", _ALL_LANES, "--blocking", "1") == 2


def test_unreadable_head_refuses(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No HEAD, no receipt — `head_sha` returns "" when git cannot be read."""
    monkeypatch.setattr(review, "head_sha", lambda _root: "")
    assert _run(repo, "--lanes", _ALL_LANES, "--blocking", "0") == 2


def test_documented_report_filename_is_the_one_the_gate_reads(repo: Path) -> None:
    """The filename in SKILL.md must be the filename `_missing_reports` looks for.

    Spelled out LITERALLY rather than built with `report_path`, because every
    other test here builds its fixtures through that function and so inherits
    whatever normalisation it applies. That is a tautological probe: it cannot
    detect a doc-vs-code divergence in the very function it calls.

    It was not hypothetical. `_safe()` stripped non-alphanumerics, so the gate
    hunted for `review-<sha>-silentfailure.md` while every doc said
    `review-<sha>-silent-failure.md` — a reviewer following the skill verbatim
    left a real report the gate called missing. Two independent lanes found it;
    this suite could not.
    """
    sha = "a" * 40
    reports = repo / ".agent/kb/review/reports"
    reports.mkdir(parents=True, exist_ok=True)
    for lane in ("standards", "spec", "cold", "silent-failure"):
        (reports / f"review-{sha}-{lane}.md").write_text("NO FINDINGS", encoding="utf-8")

    assert _run(repo, "--lanes", _ALL_LANES, "--blocking", "0") == 0


def test_unresolvable_fixed_point_is_refused(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A base that never resolved is "could not check", not "clean".

    `base_sha` returns "" when `git merge-base` fails, so `--fixed-point no-such-ref`
    (a typo or a deleted branch) recorded an empty base and passed — a green receipt for a range the
    lanes could not have diffed.
    """
    monkeypatch.setattr(review, "base_sha", lambda _root, _fp, **_kw: "")
    _reports(repo, "standards", "spec", "cold", "silent-failure")
    assert _run(repo, "--lanes", _ALL_LANES, "--blocking", "0", "--fixed-point", "no-such-ref") == 2
