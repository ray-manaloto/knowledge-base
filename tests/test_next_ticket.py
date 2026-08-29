# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.next_ticket` — the tracked chain reader (#574).

No network, no `gh`: `_gh` is the ONE substituted seam, and it is substituted
at the SUBPROCESS boundary — a `(rc, stdout+stderr string)` pair, exactly what
`subprocess.run` would hand back. `_parse_lookup` (the classifier) always runs
for real on that string, per the spec's own "a successful parse is not a
successful lookup" requirement: a fake that returned an already-parsed mapping
would let every assertion below pass while never exercising the classifier at
all. Chain files are real files under `tmp_path`, read by the real `tomllib`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import next_ticket
from kb_setup.next_ticket import Blocked, CouldNotAsk, IssueInfo, Ready, StaleChain
from kb_setup.result import Err, Ok, Rc, exit_code

if TYPE_CHECKING:
    import pytest


def _write_chain(tmp_path: Path, tickets: list[dict[str, object]]) -> Path:
    """Write a `[[ticket]]` TOML file matching §3's shape."""
    lines: list[str] = []
    for t in tickets:
        lines.append("[[ticket]]")
        lines.append(f"issue = {t['issue']}")
        lines.append(f'title = "{t["title"]}"')
        lines.append(f"blockers = {t.get('blockers', [])}")
    path = tmp_path / "chain.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _alias(number: int) -> str:
    return f"{next_ticket._ALIAS_PREFIX}{number}"


def _stub(monkeypatch: pytest.MonkeyPatch, rc: int, out: str) -> None:
    monkeypatch.setattr(next_ticket, "_gh", lambda _args, _root: (rc, out))


def _issue_json(number: int, state: str, title: str = "") -> str:
    """One `repository.<alias>` node, in the real production alias scheme."""
    return f'"{_alias(number)}": {{"number": {number}, "state": "{state}", "title": "{title}"}}'


# --------------------------------------------------------------------------
# §5 — the first entry with all blockers closed is reported ready, even when
# an earlier entry is blocked
# --------------------------------------------------------------------------


def test_first_ready_entry_wins_even_when_an_earlier_one_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _write_chain(
        tmp_path,
        [
            {"issue": 1, "title": "Blocked one", "blockers": [100]},
            {"issue": 2, "title": "Ready one", "blockers": [101]},
        ],
    )
    body = (
        "{"
        + _issue_json(1, "OPEN")
        + ", "
        + _issue_json(2, "OPEN")
        + ", "
        + _issue_json(100, "OPEN")
        + ", "
        + _issue_json(101, "CLOSED")
        + "}"
    )
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert "READY — #2 Ready one" in result.value
    assert str(chain) in result.value


def test_the_first_ready_entry_wins_over_a_later_also_ready_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two entries are BOTH individually ready — file order must still decide.

    Without this, a scan that happens to find the later one first (or any
    order-independent selection) passes every other test in this file while
    reporting the wrong ticket.
    """
    chain = _write_chain(
        tmp_path,
        [
            {"issue": 1, "title": "First, also ready", "blockers": [100]},
            {"issue": 2, "title": "Second, also ready", "blockers": [101]},
        ],
    )
    body = (
        "{"
        + _issue_json(1, "OPEN")
        + ", "
        + _issue_json(2, "OPEN")
        + ", "
        + _issue_json(100, "CLOSED")
        + ", "
        + _issue_json(101, "CLOSED")
        + "}"
    )
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("READY — #1 First, also ready")


def test_a_blockerless_entry_still_gets_looked_up_for_its_own_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ticket with no blockers still needs `gh` — for its OWN state (D1/D2, #574).

    The prior behaviour (`_gh` never called, `tickets[0]` reported READY on
    blockers alone) is what let a CLOSED ticket that was never removed from the
    chain read READY forever. `_gh` must now be reachable, and reporting it must
    reflect the tracker's answer for the ticket's own issue.
    """
    chain = _write_chain(tmp_path, [{"issue": 1, "title": "No blockers", "blockers": []}])
    body = "{" + _issue_json(1, "OPEN") + "}"
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("READY — #1 No blockers")


# --------------------------------------------------------------------------
# §5 — nothing ready: the first BLOCKED entry is reported with its open
# blockers named, and no later unblocked entry is reported instead
# --------------------------------------------------------------------------


def test_nothing_ready_reports_the_first_blocked_entry_not_a_less_blocked_later_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A closest-to-ready heuristic would wrongly pick B over A.

    Entry A has TWO open blockers, entry B has only ONE. The spec requires A,
    unconditionally, because A is first.
    """
    chain = _write_chain(
        tmp_path,
        [
            {"issue": 1, "title": "First, more blocked", "blockers": [100, 102]},
            {"issue": 2, "title": "Second, less blocked", "blockers": [101]},
        ],
    )
    body = (
        "{"
        + _issue_json(1, "OPEN")
        + ", "
        + _issue_json(2, "OPEN")
        + ", "
        + _issue_json(100, "OPEN", "blocker A")
        + ", "
        + _issue_json(101, "OPEN", "blocker B")
        + ", "
        + _issue_json(102, "CLOSED", "blocker C")
        + "}"
    )
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("BLOCKED — #1 First, more blocked")
    assert "#2" not in result.value.split("\n")[0]
    assert "- #100 blocker A" in result.value
    # #102 is closed — it must not be listed as an open blocker.
    assert "#102" not in result.value


# --------------------------------------------------------------------------
# §5 — the tool refuses to NAME an entry the tracker says is CLOSED, rather
# than skipping past it: the check fires only on the entry about to be
# reported (the READY candidate, or the BLOCKED fallback's `tickets[0]`),
# never by scanning the rest of the chain for other closed entries
# --------------------------------------------------------------------------


def test_a_closed_ready_candidate_is_reported_stale_chain_not_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1 is CLOSED (never removed) and would otherwise be the READY candidate.

    #2 is a perfectly good READY entry right behind it — the tool must NOT
    quietly report #2 instead. That would make a forgotten removal harmless,
    which removes the only pressure keeping the chain file honest.
    """
    chain = _write_chain(
        tmp_path,
        [
            {"issue": 1, "title": "Done, never removed", "blockers": []},
            {"issue": 2, "title": "Would also be ready", "blockers": []},
        ],
    )
    body = "{" + _issue_json(1, "CLOSED") + ", " + _issue_json(2, "OPEN") + "}"
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("STALE CHAIN — #1 Done, never removed is CLOSED")
    assert str(chain) in result.value
    assert "remove it, then re-run" in result.value
    # #2 legitimately appears in the preview line (it's the real next-ready
    # entry once #1 is removed) — what must never happen is #2 on the NAMING
    # line, i.e. #2 quietly substituted as the reported entry.
    assert "#2" not in result.value.split("\n")[0]


def test_a_closed_blocked_fallback_is_reported_stale_chain_not_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is ready; `tickets[0]` (the BLOCKED fallback) is itself CLOSED."""
    chain = _write_chain(
        tmp_path,
        [
            {"issue": 1, "title": "Done, never removed", "blockers": [100]},
            {"issue": 2, "title": "Also blocked", "blockers": [101]},
        ],
    )
    body = (
        "{"
        + _issue_json(1, "CLOSED")
        + ", "
        + _issue_json(2, "OPEN")
        + ", "
        + _issue_json(100, "OPEN", "blocker A")
        + ", "
        + _issue_json(101, "OPEN", "blocker B")
        + "}"
    )
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("STALE CHAIN — #1 Done, never removed is CLOSED")
    assert "BLOCKED" not in result.value


def test_a_closed_entry_that_is_never_the_naming_candidate_goes_unmentioned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1 is CLOSED but has an open blocker, so the walk never tries to name it.

    Proves the check is lazy, not a scan: #1's CLOSED state is never even
    consulted, and #2 is reported cleanly READY with no mention of #1 at all.
    """
    chain = _write_chain(
        tmp_path,
        [
            {"issue": 1, "title": "Closed but still blocked", "blockers": [100]},
            {"issue": 2, "title": "Ready", "blockers": []},
        ],
    )
    body = (
        "{"
        + _issue_json(1, "CLOSED")
        + ", "
        + _issue_json(2, "OPEN")
        + ", "
        + _issue_json(100, "OPEN", "still open")
        + "}"
    )
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("READY — #2 Ready")
    assert "STALE" not in result.value
    assert "#1" not in result.value


# --------------------------------------------------------------------------
# §preview — STALE CHAIN's "next after removal" line previews what the tool
# would report once the stale entry is gone, without a second lookup (#574
# follow-up). Never a skip: the state stays STALE CHAIN either way.
# --------------------------------------------------------------------------


def test_preview_names_the_next_ready_entry_after_the_stale_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _write_chain(
        tmp_path,
        [
            {"issue": 1, "title": "Done, never removed", "blockers": []},
            {"issue": 2, "title": "Next task", "blockers": []},
        ],
    )
    body = "{" + _issue_json(1, "CLOSED") + ", " + _issue_json(2, "OPEN") + "}"
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("STALE CHAIN — #1 Done, never removed is CLOSED")
    assert "next after removal: #2 Next task" in result.value


def test_preview_of_a_closed_candidate_matches_what_a_second_run_actually_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[#1 CLOSED, #2 CLOSED, #3 OPEN] — the review's own discriminating fixture.

    An earlier version of the preview CHASED past #2 (also closed) to name #3
    — a real second run, on the chain with #1 actually removed, reports
    `STALE CHAIN — #2`, not `#3`. The preview must agree with the next run,
    so it names #2 with a note instead. Proved two ways: the preview text
    directly, and a genuine second `evaluate()` call against the cleaned-up
    chain (same tracker state — removing #1 from the FILE never changes any
    issue's tracker state).
    """
    chain = _write_chain(
        tmp_path,
        [
            {"issue": 1, "title": "Done, never removed", "blockers": []},
            {"issue": 2, "title": "Also done, never removed", "blockers": []},
            {"issue": 3, "title": "Real next task", "blockers": []},
        ],
    )
    body = (
        "{"
        + _issue_json(1, "CLOSED")
        + ", "
        + _issue_json(2, "CLOSED")
        + ", "
        + _issue_json(3, "OPEN")
        + "}"
    )
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    first_run = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(first_run, Ok)
    assert first_run.value.startswith("STALE CHAIN — #1 Done, never removed is CLOSED")
    preview = "next after removal: #2 Also done, never removed — also CLOSED, remove it too"
    assert preview in first_run.value
    assert "#3" not in first_run.value

    cleaned = _write_chain(
        tmp_path,
        [
            {"issue": 2, "title": "Also done, never removed", "blockers": []},
            {"issue": 3, "title": "Real next task", "blockers": []},
        ],
    )
    body2 = "{" + _issue_json(2, "CLOSED") + ", " + _issue_json(3, "OPEN") + "}"
    out2 = f'{{"data": {{"repository": {body2}}}}}'
    _stub(monkeypatch, 0, out2)

    second_run = next_ticket.evaluate(cleaned, tmp_path)

    assert isinstance(second_run, Ok)
    assert second_run.value.startswith("STALE CHAIN — #2 Also done, never removed is CLOSED")


def test_preview_reports_nothing_ready_after_cleanup_when_none_remain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _write_chain(
        tmp_path,
        [
            {"issue": 1, "title": "Done, never removed", "blockers": []},
            {"issue": 2, "title": "Still blocked", "blockers": [100]},
        ],
    )
    body = (
        "{"
        + _issue_json(1, "CLOSED")
        + ", "
        + _issue_json(2, "OPEN")
        + ", "
        + _issue_json(100, "OPEN", "blocker A")
        + "}"
    )
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("STALE CHAIN — #1 Done, never removed is CLOSED")
    assert "next after removal: nothing ready after cleanup" in result.value


def test_preview_is_computed_for_the_fallback_naming_candidate_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback-path STALE CHAIN carries a preview too.

    `tickets[0]`, everything blocked — always "nothing ready after cleanup"
    here, since the fallback is reached only when EVERY entry has an open
    blocker.
    """
    chain = _write_chain(
        tmp_path,
        [
            {"issue": 1, "title": "Done, never removed", "blockers": [100]},
            {"issue": 2, "title": "Also blocked", "blockers": [101]},
        ],
    )
    body = (
        "{"
        + _issue_json(1, "CLOSED")
        + ", "
        + _issue_json(2, "OPEN")
        + ", "
        + _issue_json(100, "OPEN", "blocker A")
        + ", "
        + _issue_json(101, "OPEN", "blocker B")
        + "}"
    )
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("STALE CHAIN — #1 Done, never removed is CLOSED")
    assert "next after removal: nothing ready after cleanup" in result.value


# --------------------------------------------------------------------------
# §5 — a failed or unparsable lookup produces could-not-ask, not nothing-ready
# --------------------------------------------------------------------------


def test_a_nonzero_rc_produces_could_not_ask_not_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _write_chain(tmp_path, [{"issue": 1, "title": "T", "blockers": [100]}])
    _stub(monkeypatch, 1, "gh: could not connect to api.github.com")

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("COULD NOT ASK")
    assert "BLOCKED" not in result.value
    # The REASON must survive, not just the fact of failure. rc != 0 is the
    # most likely real failure — no network, expired auth, a rate limit — and
    # `_gh` merges stderr into `out` so it can be reported. Without this
    # assertion the branch can silently regress to a bare "gh exited 1", which
    # is what it did until the cold review of a43afc22 caught it.
    assert "could not connect to api.github.com" in result.value


def test_an_unparsable_body_produces_could_not_ask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _write_chain(tmp_path, [{"issue": 1, "title": "T", "blockers": [100]}])
    _stub(monkeypatch, 0, "not json at all")

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("COULD NOT ASK")


# --------------------------------------------------------------------------
# §5 — rc 0 with a parseable body carrying an `errors` key produces
# could-not-ask: the §4 fixture, verbatim (aliases "a"/"z" as illustrated
# there, tested directly against the classifier at the subprocess boundary)
# --------------------------------------------------------------------------

#: The exact partial-failure response measured in §4, reassembled as one JSON
#: string (the line break in the spec is prose wrapping, not file content —
#: whitespace between JSON tokens carries no meaning).
_SPEC_4_FIXTURE = (
    '{"data":{"repository":{"a":{"number":574,"state":"OPEN"},"z":null}},'
    '"errors":[{"type":"NOT_FOUND","path":["repository","z"]}]}'
)


def test_the_section_4_fixture_produces_could_not_ask() -> None:
    lookup = next_ticket._parse_lookup(0, _SPEC_4_FIXTURE, {"a": 574, "z": 999999})

    assert lookup.states is None
    assert "999999" in lookup.detail


def test_errors_key_present_is_could_not_ask_even_when_every_alias_resolved() -> None:
    """`errors` present is its OWN trigger, not derived from a missing node.

    Every requested alias here resolves to a perfectly valid state, so a
    classifier that checked only per-alias state (and never the top-level
    `errors` key) would wrongly report a result.
    """
    body = (
        '{"data": {"repository": {"a": {"number": 1, "state": "OPEN", "title": "x"}}}, '
        '"errors": [{"type": "SOMETHING_ELSE"}]}'
    )

    lookup = next_ticket._parse_lookup(0, body, {"a": 1})

    assert lookup.states is None


def test_an_empty_errors_array_is_not_its_own_trigger() -> None:
    """`"errors": []` is NOT the same as `errors` present with content (P3, #574).

    `_errors_detail`'s docstring used to claim "present at all" is the trigger,
    which an empty array contradicts — `not []` is `True`, so the check already
    falls through to the per-alias state. Every alias resolves here, so the
    lookup must succeed despite the (empty) `errors` key being present.
    """
    body = (
        '{"data": {"repository": {"a": {"number": 1, "state": "OPEN", "title": "x"}}}, '
        '"errors": []}'
    )

    lookup = next_ticket._parse_lookup(0, body, {"a": 1})

    assert lookup.states is not None
    assert lookup.states[1].state == "OPEN"


# --------------------------------------------------------------------------
# §5 — rc 0 with a `null` state for a requested issue produces could-not-ask
# --------------------------------------------------------------------------


def test_a_null_state_with_no_errors_key_still_produces_could_not_ask() -> None:
    """No `errors` key at all — the INDEPENDENT null-state trigger.

    Not a side effect of the errors-key check above.
    """
    body = '{"data": {"repository": {"i577": null}}}'

    lookup = next_ticket._parse_lookup(0, body, {"i577": 577})

    assert lookup.states is None
    assert "577" in lookup.detail


# --------------------------------------------------------------------------
# §5 — a NOT_FOUND for one alias names that issue number in the OUTPUT
# --------------------------------------------------------------------------


def test_a_not_found_blocker_names_its_issue_number_in_the_rendered_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _write_chain(tmp_path, [{"issue": 1, "title": "T", "blockers": [577]}])
    out = (
        '{"data": {"repository": {"' + _alias(577) + '": null}}, '
        '"errors": [{"type": "NOT_FOUND", "path": ["repository", "' + _alias(577) + '"]}]}'
    )
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("COULD NOT ASK")
    assert "#577" in result.value
    assert "NOT_FOUND" in result.value
    assert str(chain) in result.value


# --------------------------------------------------------------------------
# §5 — a blocker that is not an entry in the chain file still resolves
# --------------------------------------------------------------------------


def test_an_out_of_chain_blocker_still_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """999 blocks #1 but has no `[[ticket]]` entry of its own in this file."""
    chain = _write_chain(tmp_path, [{"issue": 1, "title": "T", "blockers": [999]}])
    out = (
        '{"data": {"repository": {'
        + _issue_json(1, "OPEN")
        + ', "'
        + _alias(999)
        + '": {"number": 999, "state": "CLOSED", "title": "elsewhere"}}}}'
    )
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("READY — #1 T")


def test_an_out_of_chain_blocker_still_open_reports_its_title(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chain = _write_chain(tmp_path, [{"issue": 1, "title": "T", "blockers": [999]}])
    out = (
        '{"data": {"repository": {'
        + _issue_json(1, "OPEN")
        + ', "'
        + _alias(999)
        + '": {"number": 999, "state": "OPEN", "title": "outside the chain"}}}}'
    )
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("BLOCKED — #1 T")
    assert "- #999 outside the chain" in result.value


# --------------------------------------------------------------------------
# §5 — a malformed or missing chain file exits with the bad-request code,
# naming the path
# --------------------------------------------------------------------------


def test_a_missing_chain_file_is_bad_request_and_names_the_path(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.toml"

    result = next_ticket.evaluate(missing, tmp_path)

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert str(missing) in result.message


def test_a_malformed_toml_file_is_bad_request_and_names_the_path(tmp_path: Path) -> None:
    bad = tmp_path / "chain.toml"
    bad.write_text("this is not [ valid toml", encoding="utf-8")

    result = next_ticket.evaluate(bad, tmp_path)

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert str(bad) in result.message


def test_a_chain_file_with_no_ticket_entries_is_bad_request(tmp_path: Path) -> None:
    empty = tmp_path / "chain.toml"
    empty.write_text("# nothing here\n", encoding="utf-8")

    result = next_ticket.evaluate(empty, tmp_path)

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST


def test_a_ticket_with_a_non_integer_issue_is_bad_request(tmp_path: Path) -> None:
    path = tmp_path / "chain.toml"
    path.write_text('[[ticket]]\nissue = "574"\ntitle = "T"\nblockers = []\n', encoding="utf-8")

    result = next_ticket.evaluate(path, tmp_path)

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST


# --------------------------------------------------------------------------
# render() — pure, and each state names itself on the first line
# --------------------------------------------------------------------------


def test_render_ready_names_the_issue_title_and_chain_path(tmp_path: Path) -> None:
    chain = tmp_path / "chain.toml"

    text = next_ticket.render(Ready(574, "Chain the handoff"), chain)

    assert text.startswith("READY — #574 Chain the handoff")
    assert str(chain) in text


def test_render_blocked_lists_every_open_blocker(tmp_path: Path) -> None:
    chain = tmp_path / "chain.toml"
    outcome = Blocked(
        575,
        "Prototype: packages",
        (IssueInfo(569, "OPEN", "Delete the code-generator wrapper"),),
    )

    text = next_ticket.render(outcome, chain)

    assert text.startswith("BLOCKED — #575 Prototype: packages")
    assert "- #569 Delete the code-generator wrapper" in text


def test_render_stale_chain_names_the_issue_and_says_remove_it(tmp_path: Path) -> None:
    chain = tmp_path / "chain.toml"
    outcome = StaleChain(569, "Delete the code-generator wrapper", "#570 The research CLI")

    text = next_ticket.render(outcome, chain)

    assert text.startswith("STALE CHAIN — #569 Delete the code-generator wrapper is CLOSED")
    assert str(chain) in text
    assert "remove it, then re-run" in text
    assert "next after removal: #570 The research CLI" in text
    assert "BLOCKED" not in text
    assert "READY" not in text


def test_render_could_not_ask_names_the_chain_path_and_says_re_derive(tmp_path: Path) -> None:
    chain = tmp_path / "chain.toml"

    text = next_ticket.render(CouldNotAsk("gh exited 1"), chain)

    assert text.startswith("COULD NOT ASK — gh exited 1")
    assert str(chain) in text
    assert "re-derive" in text


# --------------------------------------------------------------------------
# check_next_ticket / main — the CLI boundary
# --------------------------------------------------------------------------


def test_unexpected_arguments_are_refused(tmp_path: Path) -> None:
    result = next_ticket.check_next_ticket(["bogus"], tmp_path)

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST


def test_main_prints_the_value_and_exits_ok(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "docs" / "roadmap").mkdir(parents=True)
    chain = tmp_path / next_ticket.DEFAULT_CHAIN
    chain.write_text('[[ticket]]\nissue = 1\ntitle = "T"\nblockers = []\n', encoding="utf-8")
    body = "{" + _issue_json(1, "OPEN") + "}"
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    rc = next_ticket.main([], tmp_path)

    assert rc == exit_code(Ok("x"))
    out = capsys.readouterr().out
    assert "READY — #1 T" in out


def test_main_prints_to_stderr_and_exits_bad_request_on_a_bad_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = next_ticket.main(["bogus"], tmp_path)

    assert rc == int(Rc.BAD_REQUEST)
    err = capsys.readouterr().err
    assert "kb-next-ticket:" in err
