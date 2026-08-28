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

import pytest
from kb_setup import next_ticket
from kb_setup.next_ticket import Blocked, CouldNotAsk, IssueInfo, Ready
from kb_setup.result import Err, Ok, Rc, exit_code


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
    body = "{" + _issue_json(100, "OPEN") + ", " + _issue_json(101, "CLOSED") + "}"
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
    body = "{" + _issue_json(100, "CLOSED") + ", " + _issue_json(101, "CLOSED") + "}"
    out = f'{{"data": {{"repository": {body}}}}}'
    _stub(monkeypatch, 0, out)

    result = next_ticket.evaluate(chain, tmp_path)

    assert isinstance(result, Ok)
    assert result.value.startswith("READY — #1 First, also ready")


def test_a_trivially_ready_entry_needs_no_lookup_at_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When NOTHING in the chain has a blocker, `_gh` must never be called."""
    chain = _write_chain(tmp_path, [{"issue": 1, "title": "No blockers", "blockers": []}])

    def boom(_args: object, _root: object) -> tuple[int, str]:
        pytest.fail("_gh was called with no blockers anywhere in the chain")

    monkeypatch.setattr(next_ticket, "_gh", boom)

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
        '{"data": {"repository": {"'
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
        '{"data": {"repository": {"'
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
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "docs" / "roadmap").mkdir(parents=True)
    chain = tmp_path / next_ticket.DEFAULT_CHAIN
    chain.write_text('[[ticket]]\nissue = 1\ntitle = "T"\nblockers = []\n', encoding="utf-8")

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
