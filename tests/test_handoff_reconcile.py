# Copyright (c) 2026 Raymond Manaloto
"""`kb_setup.handoff_reconcile` — a handoff that dropped the previous backlog.

ARMED ON THE REAL PAIR. `.agent/plans/session-2026-08-18-b.md` (hand-written)
and the DEFECTIVE generated handoff it was compared against are the documents
that motivated this module; the losses between them were established by hand
before any of this code existed.

THE FIXTURE IS FROZEN UNDER `docs/`, AND THAT MATTERS. Pointing this at the live
`.agent/plans/session-2026-08-18-c.md` worked for exactly as long as that file
stayed broken. The composer was then fixed and the handoff regenerated — and the
regression test went red because the regenerated document CARRIES the items it
was asserting were dropped. Failing for the best possible reason is still
failing, and a regression test whose fixture is a file the round keeps rewriting
is measuring the round rather than the code. So the broken version is preserved
at `docs/session-review/runs/2026-08-18-2/`, which also makes it TRACKED — the
one real-pair fixture that survives a fresh clone.

`.agent/` is gitignored, so the tests still touching it skip in a fresh clone.
That is a real coverage bound and it is why the synthetic tests below are not
redundant: they carry the same claims in a form CI could run, and the real-pair
tests prove the synthetic ones are not lying about the shape of an actual
handoff.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import handoff
from kb_setup import handoff_reconcile as hr

REPO = Path(__file__).resolve().parents[1]

#: The hand-written handoff whose backlog was dropped. Gitignored (`.agent/`).
PREVIOUS = REPO / ".agent" / "plans" / "session-2026-08-18-b.md"

#: The DEFECTIVE generated handoff, preserved under `docs/` when the composer
#: was fixed — so this fixture is TRACKED and survives a fresh clone, unlike the
#: `.agent/` original it was copied from. It is also frozen: the live
#: `session-2026-08-18-c.md` has since been regenerated and now CARRIES these
#: items, which would make a test pointed at it fail for the best possible
#: reason. Freezing the evidence is what keeps the regression test honest.
GENERATED = (
    REPO / "docs" / "session-review" / "runs" / "2026-08-18-2" / "handoff-c-before-reconcile-fix.md"
)

#: The handoff the FIXED composer produced, for the end-to-end arm below.
REGENERATED = REPO / ".agent" / "plans" / "session-2026-08-18-c.md"

real_pair = pytest.mark.skipif(
    not (PREVIOUS.is_file() and GENERATED.is_file()),
    reason="the hand-written half lives under gitignored .agent/",
)

regenerated = pytest.mark.skipif(
    not REGENERATED.is_file(),
    reason="the regenerated handoff lives under gitignored .agent/",
)


@real_pair
def test_the_known_losses_are_found() -> None:
    """The four established by hand before this module existed.

    Each was verified with a plain `grep -c` against the generated handoff
    returning 0 while the same grep against `-b.md` returned non-zero — the
    control arm is that the same probe discriminates, not that one side is empty.
    """
    gone = hr.dropped(
        PREVIOUS.read_text(encoding="utf-8"),
        GENERATED.read_text(encoding="utf-8"),
        previous_name=PREVIOUS.name,
    )
    named = {t.lower() for d in gone for t in d.commitment.tokens}
    for token in ("agent-harness-docs", "proseexclude", "newermt", "kb-handoff-check"):
        assert token in named, f"known loss not reported: {token}"


@real_pair
def test_a_handoff_does_not_drop_itself() -> None:
    """THE control arm. Compared with itself, every commitment is carried.

    Without this the suite above could pass on a module that reports everything
    as dropped — which is the shape of a check that can only fail.
    """
    text = PREVIOUS.read_text(encoding="utf-8")
    assert hr.dropped(text, text, previous_name="self") == []


@real_pair
def test_the_gate_fails_the_generated_handoff_and_says_why() -> None:
    """End-to-end through the real gate, not through `dropped` alone.

    `handoff.check` passed this document at 20 OK / 0 broken while it was missing
    seven owed items — a validator nothing calls is not a gate, and neither is one
    wired to the wrong entry point.

    This drives `check_handoff`, which is the CLI path ONLY. The claim this
    docstring first made — "the function kb-handoff-check and kb-ship actually
    run" — was half wrong: `kb-ship` gates through `check_for_branch`, a
    different function that did not reconcile at all. Both are now wired and
    `test_check_for_branch_reconciles_too` covers the other one.
    """
    result = handoff.check_handoff([str(GENERATED)], REPO)
    assert isinstance(result, handoff.Ok)
    reconcile = [f for f in result.value.findings if f.check == "reconcile"]
    assert reconcile, "the gate ran no reconciliation at all"
    assert any(f.verdict is handoff.Verdict.FAIL for f in reconcile), (
        "a dropped COMMITMENT must FAIL, or the gate cannot block a ship"
    )
    assert any(f.verdict is handoff.Verdict.AMBIGUOUS for f in reconcile), (
        "a dropped GOTCHA must be reported without failing"
    )
    detail = next(f.detail for f in reconcile if f.verdict is handoff.Verdict.FAIL)
    for word in ("CARRIED", "DONE", "DROPPED"):
        assert word in detail, f"the remedy must name {word}; a refusal without one is a wall"


# ── the synthetic half: the same claims, runnable in a fresh clone ──────────

_OWED = """# handoff

## Owed and not done

- `kb-update -- agent-harness-docs` is 82 commits behind.
- rumdl use-or-remove. Ship `betterleaks` in parallel.

## Things that will bite you

1. `find -newermt` returns nothing on BSD.
"""


def test_a_commitment_named_anywhere_in_the_new_handoff_is_carried() -> None:
    """Matching is by NAME, not by phrasing — two agents word it differently."""
    new = "# next\n\n## Owed\n\n- still chasing agent-harness-docs, and betterleaks.\n"
    gone = hr.dropped(_OWED, new, previous_name="prev.md")
    named = {t.lower() for d in gone for t in d.commitment.tokens}
    assert "agent-harness-docs" not in named
    assert "newermt" in named, "the untouched gotcha must still be reported"


def test_a_weak_token_cannot_vouch_for_a_strong_one() -> None:
    """The false-CARRIED direction, which is the silent one.

    `kind = docs` yields `docs`, a word every handoff contains. If that cleared
    its sentence, the `agent-harness-docs` commitment beside it would pass
    unnamed — which is exactly what happened on the real pair mid-development.
    """
    previous = "# h\n\n## Owed\n\n- `kb-update -- agent-harness-docs`: a `kind = docs` source.\n"
    gone = hr.dropped(
        previous, "# next\n\n## Owed\n\n- we wrote some docs today.\n", previous_name="p"
    )
    assert gone, "a commitment was cleared by the word 'docs'"


def test_a_bullets_wrapped_continuation_is_one_commitment() -> None:
    """A hard-wrapped bullet is one item, not two — noise switches gates off."""
    previous = (
        "# h\n\n## Owed\n\n"
        "- **`kb-update -- agent-harness-docs`** is 82 commits behind and is NOT\n"
        "  a one-liner — `mise.toml:507` needs a host-agent pass.\n"
    )
    gone = hr.dropped(previous, "# next\n\nnothing carried.\n", previous_name="p")
    assert len(gone) == 1, f"expected one commitment, got {[d.commitment.tokens for d in gone]}"


def test_a_prose_paragraph_is_split_per_sentence() -> None:
    """The opposite error, and the one that made the gate go quiet.

    This repo's owed sections are not always lists. Folded whole, one surviving
    token vouches for every commitment in the paragraph — so a paragraph naming
    `skillopt` and `agent-harness-docs` must owe both independently.
    """
    previous = (
        "# h\n\n## Owed\n\n"
        "Currency, all 8 pins behind, `skillopt` NOT CHECKED. "
        "`kb-update -- agent-harness-docs` is 82 commits behind.\n"
    )
    gone = hr.dropped(previous, "# next\n\n`skillopt` is still not checked.\n", previous_name="p")
    named = {t.lower() for d in gone for t in d.commitment.tokens}
    assert "agent-harness-docs" in named, "the second sentence was vouched for by the first"


def test_only_owed_and_gotcha_sections_are_read() -> None:
    """Narrative prose is out of scope; that is what the owed section is for."""
    previous = "# h\n\n## What shipped\n\n- `kb-update -- agent-harness-docs` landed.\n"
    assert hr.dropped(previous, "# next\n\nunrelated.\n", previous_name="p") == []


def test_severity_splits_commitments_from_gotchas() -> None:
    assert hr.is_commitment("Owed and not done")
    assert hr.is_commitment("THE NEXT TASK — Ray's words")
    assert not hr.is_commitment("Things that will bite you")


def test_no_earlier_handoff_is_unverifiable_not_a_pass(tmp_path: Path) -> None:
    """A check that never asked the question has not answered it."""
    plans = tmp_path / ".agent" / "plans"
    plans.mkdir(parents=True)
    only = plans / "session-2026-01-01-a.md"
    only.write_text("# h\n\n## Owed\n\n- `something`\n", encoding="utf-8")
    done = hr.reconcile(tmp_path, only, only.read_text(encoding="utf-8"))
    assert done.previous is None
    assert done.checked == 0


def test_a_sub_heading_does_not_end_the_owed_section() -> None:
    """The 43% silent miss: a `###` under `## Owed` used to exit scope.

    Measured across the 14 real handoffs on disk, before/after this fix, by
    counting commitments: 6->9, 9->13, 10->20, 8->9, 7->19, 6->16. The worst was
    checking SEVEN of nineteen commitments and reporting a clean pass — the
    false-CARRIED class this module's own docstring calls strictly worse.
    """
    previous = (
        "# h\n\n## Owed and not done\n\n"
        "- `first-thing` is owed.\n\n"
        "### A sub-heading, which used to end the section\n\n"
        "- `second-thing` is also owed.\n\n"
        "## What shipped\n\n- `third-thing` landed.\n"
    )
    named = {
        t.lower()
        for d in hr.dropped(previous, "# next\n", previous_name="p")
        for t in d.commitment.tokens
    }
    assert "first-thing" in named
    assert "second-thing" in named, "the sub-heading ended the owed section"
    assert "third-thing" not in named, "a non-owed section leaked into scope"


def test_an_issue_ref_does_not_match_a_longer_number() -> None:
    """`#66` must not be cleared by `#663` — the silent direction again.

    A NAME may legitimately appear inside a longer name, so name matching stays a
    substring test. A number may not, so issue refs get a boundary. Both halves
    are asserted, because fixing one direction and breaking the other is how this
    module's token rule went wrong twice already.
    """
    assert not hr._names("we closed #663 today", "#66")
    assert hr._names("we closed #66 today", "#66")
    assert hr._names("mise run kb-update -- agent-harness-docs", "agent-harness-docs")


def test_check_handoff_reports_reconcile_in_a_fresh_clone(tmp_path: Path) -> None:
    """End-to-end through the CLI path, WITHOUT the gitignored real pair.

    The only e2e arm was `@real_pair`-skipped, so deleting the wiring line left
    the fresh-clone suite green — a validator nothing calls, in a module written
    about exactly that. (Advisor review, JOB 1 finding 3.)
    """
    plans = tmp_path / ".agent" / "plans"
    plans.mkdir(parents=True)
    import os

    old, new = plans / "session-2026-01-01-a.md", plans / "session-2026-01-02-b.md"
    old.write_text("# h\n\n## Owed and not done\n\n- `kb-update -- agent-harness-docs`\n", "utf-8")
    new.write_text("# h\n\n- **branch**: `x`\n\n## Owed\n\n- nothing carried.\n", "utf-8")
    for i, p in enumerate((old, new)):
        os.utime(p, (1_700_000_000 + i * 60, 1_700_000_000 + i * 60))

    result = handoff.check_handoff([str(new)], tmp_path)
    assert isinstance(result, handoff.Ok)
    fails = [f for f in result.value.findings if f.check == "reconcile"]
    assert any(f.verdict is handoff.Verdict.FAIL for f in fails), (
        "the CLI path ran no reconciliation"
    )


def test_check_for_branch_reconciles_too(tmp_path: Path) -> None:
    """The path `kb-ship` ACTUALLY runs — which bb19a0ec wrongly claimed it did.

    `pr.py` gates through `check_for_branch`, not `check_handoff`. Reconcile was
    wired only into the latter, so the commit message's "that blocks kb-ship"
    was false when written and no test could have caught it: the only e2e arm
    went through the path that already worked.
    """
    plans = tmp_path / ".agent" / "plans"
    plans.mkdir(parents=True)
    import os

    old, new = plans / "session-2026-01-01-a.md", plans / "session-2026-01-02-b.md"
    old.write_text("# h\n\n## Owed and not done\n\n- `kb-update -- agent-harness-docs`\n", "utf-8")
    new.write_text("# h\n\n- **branch**: `feat/x`\n\n## Owed\n\n- nothing carried.\n", "utf-8")
    for i, p in enumerate((old, new)):
        os.utime(p, (1_700_000_000 + i * 60, 1_700_000_000 + i * 60))

    got = handoff.check_for_branch(tmp_path, "feat/x")
    assert got.coverage is handoff.Coverage.BROKEN, "kb-ship's path did not reconcile"
    assert any(f.check == "reconcile" for f in got.findings)

    # The SKIP still bounds it: a handoff naming another branch never reaches here.
    skipped = handoff.check_for_branch(tmp_path, "feat/other")
    assert skipped.coverage is not handoff.Coverage.BROKEN


def test_the_previous_handoff_is_strictly_older(tmp_path: Path) -> None:
    """Not merely 'not the target' — otherwise an older target reconciles FORWARD.

    Checking yesterday's handoff would then compare it against today's and report
    every item today ADDED as a loss.
    """
    plans = tmp_path / ".agent" / "plans"
    plans.mkdir(parents=True)
    older, newer = plans / "session-a.md", plans / "session-b.md"
    for i, p in enumerate((older, newer)):
        p.write_text("# h\n", encoding="utf-8")
        import os

        os.utime(p, (1_700_000_000 + i * 60, 1_700_000_000 + i * 60))
    assert hr.previous_handoff(tmp_path, newer) == older
    assert hr.previous_handoff(tmp_path, older) is None


@real_pair
@regenerated
def test_the_fixed_composer_carries_what_the_broken_one_dropped() -> None:
    """The other half of the arm: the FIX, measured on its own output.

    `bc02fc96` gave the handoff composer the previous handoff and required a
    CARRIED / DONE / DROPPED verdict per item. This asserts the regenerated
    document actually names what the pre-fix one silently lost — which is a
    claim about the WORKFLOW, not about this module, and is exactly the claim a
    passing gate could otherwise hide. `a-clean-mutation-sweep-is-about-tests`:
    the gate going quiet is not evidence the generator improved; this is.
    """
    gone = hr.dropped(
        PREVIOUS.read_text(encoding="utf-8"),
        REGENERATED.read_text(encoding="utf-8"),
        previous_name=PREVIOUS.name,
    )
    still_missing = {t.lower() for d in gone for t in d.commitment.tokens}
    assert "agent-harness-docs" not in still_missing, (
        "the regenerated handoff dropped the item the fix exists to carry"
    )


def test_a_mixed_case_identifier_matches_a_handoff_that_names_it() -> None:
    """The cold lane's P1, and a regression my own test could not see.

    `dropped()` lowercases the haystack once; `_names` must lower the token to
    match. Extracting `_names` from an inline `t.lower() in haystack` dropped
    that call, so every camelCase or PascalCase identifier — `proseExclude`, a
    class name, a `--someFlag` — failed against a handoff that named it
    perfectly and was reported DROPPED forever.

    The reason this needed an outside reviewer: `test_the_known_losses_are_found`
    asserts `proseexclude` IS in the dropped set, and it kept PASSING — for the
    wrong reason. A test that agrees with a bug is invisible to a mutation sweep,
    because the bug and the assertion agree about the answer.
    """
    previous = "# h\n\n## Owed\n\n- keep `proseExclude` in `hk.pkl`.\n"
    carried = "# next\n\n## Owed\n\n- `proseExclude` is still set.\n"
    assert hr.dropped(previous, carried, previous_name="p") == []

    absent = "# next\n\n## Owed\n\n- unrelated.\n"
    assert hr.dropped(previous, absent, previous_name="p"), "the control arm: it must still fire"
