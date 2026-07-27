"""Tests for `kb_setup.goal` — the mechanical half of the goal+rider checks.

EVERY CHECK IS ARMED IN BOTH DIRECTIONS. A checker verified only on the good
document is decoration: it would pass a goal with no headline word, no turn
bound, and pre-satisfiable sentinels, and report "all OK" while doing so. So for
each check there is a pass arm and a fail arm, and the fail arm mutates the thing
that check actually looks at — not something adjacent to it.

The regression that motivates the sentinel tests is real: the first version of
`_SENTINEL_RE` matched any ALL-CAPS run, so `PASS` (from the literal expected
output `PASS  gate lint rc=0`) and `S105` (a ruff rule code) were reported as
sentinels missing their sha. It fired on the first real document it saw. Both
of those are pinned below as negative cases.
"""

from __future__ import annotations

from pathlib import Path

from kb_setup import goal
from kb_setup.goal import Verdict

# A minimal goal that passes every mechanical check. Each test mutates ONE thing.
_GOOD = """GOAL: Establish why the thing does the thing. Current pain: `foo.py:12`
prints nonsense. Headline word: Legible.

Read first. `docs/goals/x-rider.md`, `.claude/rules/probes-need-a-control-arm.md`.

Preserve. Change anything except: the archived reports under `docs/research/**`.

Posture. No dotfiles port. No inline shell. No commits on `main`. Not a refactor.
Stop after 25 turns.

Verification. The transcript must contain `REDACT-ARM+ @ <sha>` and
`HANDBACK: rotation — Ray @ <sha>`, plus the literal `PASS  gate lint rc=0`.

Stop when those lines are present.
"""

_GOOD_RIDER = """# Rider

Serves `docs/goals/2026-07-27-1702-kb-x-goal.md`.

### P1 — ground
### P2 — probe
### P3 — land

## Out of scope

Everything else.
"""


def _verdict(findings: list[goal.Finding], check: str) -> Verdict:
    """The verdict for ``check`` — FAIL wins when a check emits several findings."""
    hits = [f.verdict for f in findings if f.check == check]
    assert hits, f"no finding named {check!r}"
    if Verdict.FAIL in hits:
        return Verdict.FAIL
    return Verdict.WARN if Verdict.WARN in hits else Verdict.OK


def test_the_good_goal_passes_everything() -> None:
    """The pass arm. Without it, every fail arm below could be a broken fixture."""
    findings = goal.check_goal(_GOOD)
    failed = [f for f in findings if f.verdict is Verdict.FAIL]
    assert not failed, f"unexpected FAIL: {[(f.check, f.detail) for f in failed]}"


def test_an_oversized_goal_fails() -> None:
    """The cap `/goal` itself enforces — over it, the harness simply refuses."""
    assert _verdict(goal.check_goal(_GOOD + "x" * goal.GOAL_CHAR_CAP), "char-cap") is Verdict.FAIL


def test_the_cap_counts_characters_not_bytes() -> None:
    """CONTROL ARM for the em-dash trap.

    `wc -c` over-counts and would send you trimming a goal that already fits. A
    text of exactly the cap in CHARACTERS passes even though its byte length is
    larger.
    """
    text = "—" * goal.GOAL_CHAR_CAP  # 3 bytes each, 1 character each
    assert len(text.encode()) > goal.GOAL_CHAR_CAP
    assert _verdict([goal._check_char_cap(text)], "char-cap") is not Verdict.FAIL


def test_a_missing_section_fails() -> None:
    assert (
        _verdict(goal.check_goal(_GOOD.replace("Preserve.", "Whatever.")), "required-sections")
        is Verdict.FAIL
    )


def test_no_headline_word_fails() -> None:
    """If you cannot name one word, the scope is more than one round."""
    assert (
        _verdict(goal.check_goal(_GOOD.replace("Headline word: Legible.", "")), "headline-word")
        is Verdict.FAIL
    )


def test_two_headline_words_fail() -> None:
    """CONTROL ARM on the other side: the check must catch too many, not just none."""
    two = _GOOD.replace("Stop when those", "Headline word: Second.\n\nStop when those")
    assert _verdict(goal.check_goal(two), "headline-word") is Verdict.FAIL


def test_a_sentinel_without_a_sha_fails() -> None:
    """THE subtle one.

    A sentinel with no run-specific value sits in the transcript from turn 0,
    because the condition itself is the first turn's directive.
    """
    bare = _GOOD.replace("`REDACT-ARM+ @ <sha>`", "`REDACT-ARM+`")
    assert _verdict(goal.check_goal(bare), "sentinel-format") is Verdict.FAIL


def test_quoted_tool_output_is_not_mistaken_for_a_sentinel() -> None:
    """REGRESSION ARM: quoted tool output is not a sentinel.

    `PASS` and `S105` are strings the agent quotes BACK from a tool, already
    run-specific because the tool produced them. Flagging them as sentinels
    missing a sha was a false positive on the first real document.
    """
    findings = goal.check_goal(_GOOD + "\nAlso `PASS  gate test rc=0` and ruff `S105`.\n")
    assert _verdict(findings, "sentinel-format") is Verdict.OK


def test_a_verdict_bearing_adjective_warns() -> None:
    """WARN not FAIL — the word may sit in prose where it decides nothing."""
    assert (
        _verdict(
            goal.check_goal(_GOOD.replace("Legible.", "Legible. Make it good.")), "adjective-scan"
        )
        is Verdict.WARN
    )


def test_no_turn_bound_fails() -> None:
    """Nothing else bounds a goal run — not met means another turn, forever."""
    assert (
        _verdict(goal.check_goal(_GOOD.replace("Stop after 25 turns.", "")), "turn-bound")
        is Verdict.FAIL
    )


def test_a_posture_without_negations_warns() -> None:
    """Posture is a fence, and a fence is made of negations."""
    weak = _GOOD.replace(
        "Posture. No dotfiles port. No inline shell. No commits on `main`. Not a refactor.",
        "Posture. Alpha tier. Stop after 25 turns.",
    )
    assert _verdict(goal.check_goal(weak), "posture-fence") is Verdict.WARN


def test_a_missing_preserve_list_fails() -> None:
    """A missing Preserve list fails.

    Without it the cheapest way to satisfy the metric is to delete what the round
    exists to protect.
    """
    assert (
        _verdict(goal.check_goal(_GOOD.replace("Preserve.", "Notes.")), "preserve-list")
        is Verdict.FAIL
    )


def test_a_bad_filename_fails_and_a_good_one_passes(tmp_path: Path) -> None:
    """Both arms in one test, because the schema is the whole point of the check."""
    bad = tmp_path / "my-goal.md"
    good = tmp_path / "2026-07-27-1702-kb-redaction-legibility-goal.md"
    assert _verdict(goal.check_goal(_GOOD, bad), "naming-schema") is Verdict.FAIL
    assert _verdict(goal.check_goal(_GOOD, good), "naming-schema") is Verdict.OK


def test_a_goal_with_no_rider_fails_the_pair_check(tmp_path: Path) -> None:
    """Always a pair.

    The cap sends detail to the rider, so a missing rider means the phases and
    out-of-scope list have nowhere to live.
    """
    g = tmp_path / "2026-07-27-1702-kb-x-goal.md"
    g.write_text(_GOOD, encoding="utf-8")
    assert _verdict(goal.check_pair(g), "pair") is Verdict.FAIL


def test_a_present_rider_passes_the_pair_check(tmp_path: Path) -> None:
    """CONTROL ARM: the pair check must be able to return OK.

    Otherwise it is a check that can only fail.
    """
    g = tmp_path / "2026-07-27-1702-kb-x-goal.md"
    g.write_text(_GOOD, encoding="utf-8")
    (tmp_path / "2026-07-27-1702-kb-x-rider.md").write_text(_GOOD_RIDER, encoding="utf-8")
    findings = goal.check_pair(g)
    assert _verdict(findings, "pair") is Verdict.OK
    assert _verdict(findings, "rider-phases") is Verdict.OK
    assert _verdict(findings, "rider-cites-goal") is Verdict.OK


def test_a_rider_that_does_not_cite_its_goal_fails() -> None:
    assert (
        _verdict(
            goal.check_rider(_GOOD_RIDER.replace("-goal.md", "-something.md")), "rider-cites-goal"
        )
        is Verdict.FAIL
    )


def test_a_rider_without_out_of_scope_warns() -> None:
    """The overflow valve that stops a round widening under pressure."""
    assert (
        _verdict(
            goal.check_rider(_GOOD_RIDER.replace("## Out of scope", "## Notes")),
            "rider-out-of-scope",
        )
        is Verdict.WARN
    )


def test_the_report_names_its_own_advisory_nature() -> None:
    """A reader must not mistake a clean report for a passing gate."""
    out = goal.render(goal.check_goal(_GOOD))
    assert "advisory" in out
    assert "read the report, not the rc" in out


def test_main_always_returns_zero_even_on_a_broken_goal(tmp_path: Path) -> None:
    """Advisory by construction.

    A goal document is authored input, not repo source; a WARN-level heuristic
    must never be able to block a PR.
    """
    assert goal.main(["--text", "this is not a goal at all"], tmp_path) == 0
