"""kb_setup.currency.report + .issues — step 6's committed record and step 4's diff.

The cadence rule (landing row always, detail page only when the run has content)
is the part worth pinning down: it is the difference between a log that stays
readable and one nobody opens.
"""

import json
from datetime import UTC, datetime

from kb_setup.currency import config, issues, report
from kb_setup.currency.decide import Ambiguity, Verdict
from kb_setup.currency.issues import Observation
from kb_setup.currency.sync import DRIFT, OK, Finding, SyncStatus
from kb_setup.currency.upstream import UpstreamStatus


def _record(*, drifted=False, latest="", moved=(), ambiguities=()) -> report.RunRecord:
    findings = (Finding("pin", OK, "pinned 0.9.25"),)
    if drifted:
        findings = (*findings, Finding("resolution", DRIFT, "PATH reaches 0.9.23"))
    status = SyncStatus(tool="graphify", pinned="0.9.25", resolved="0.9.25", findings=findings)
    verdict = Verdict(
        tool="graphify",
        current="0.9.25",
        latest=latest,
        auto_apply=False,
        gates_passed=(),
        ambiguities=ambiguities,
    )
    return report.RunRecord(
        tool="graphify",
        sync=status,
        upstream=UpstreamStatus(pypi_latest=latest or "0.9.25"),
        observations=(),
        moved=moved,
        verdict=verdict,
    )


# -------------------------------------------------------------- cadence ----


def test_clean_run_writes_a_row_but_no_detail_page(tmp_path) -> None:
    landing, detail = report.write_run(tmp_path, _record())
    assert detail is None
    assert landing.exists()
    assert "graphify" in landing.read_text(encoding="utf-8")


def test_run_with_drift_writes_a_detail_page(tmp_path) -> None:
    _, detail = report.write_run(tmp_path, _record(drifted=True))
    assert detail is not None
    body = detail.read_text(encoding="utf-8")
    assert "PATH reaches 0.9.23" in body


def test_available_upgrade_earns_a_detail_page(tmp_path) -> None:
    _, detail = report.write_run(tmp_path, _record(latest="0.9.26"))
    assert detail is not None


def test_moved_issue_earns_a_detail_page(tmp_path) -> None:
    moved = (Observation(key="issue:#2101", state="closed"),)
    _, detail = report.write_run(tmp_path, _record(moved=moved))
    assert detail is not None


# --------------------------------------------------------- landing page ----


def test_rows_accumulate_newest_first(tmp_path) -> None:
    report.write_run(tmp_path, _record())
    report.write_run(tmp_path, _record(latest="0.9.26"))
    lines = (tmp_path / report.REPORT_DIR / report.LANDING).read_text(encoding="utf-8").splitlines()
    rows = [line for line in lines if line.startswith("| 20")]
    assert len(rows) == 2
    # The most recent run is inserted directly under the header rule.
    assert "0.9.26" in rows[0]


def test_two_runs_on_one_day_do_not_clobber_each_other(tmp_path) -> None:
    _, first = report.write_run(tmp_path, _record(drifted=True))
    _, second = report.write_run(tmp_path, _record(drifted=True))
    assert first is not None
    assert second is not None
    assert first != second
    assert first.exists()
    assert second.exists()


def test_detail_page_carries_wikilinks_for_graph_ingestion(tmp_path) -> None:
    """Wikilinks are what make this log queryable once ingested."""
    _, detail = report.write_run(tmp_path, _record(drifted=True))
    assert detail is not None
    assert "[[tool-currency-log]]" in detail.read_text(encoding="utf-8")


def test_generated_markdown_has_no_consecutive_blank_lines(tmp_path) -> None:
    """The generator must satisfy the repo's own markdown gate.

    rumdl MD012 rejects consecutive blank lines, so a template that emits them
    makes EVERY future run fail `mise run lint` — a report nobody can commit.
    Checked in both shapes: with and without an ambiguity section.
    """
    for record in (_record(drifted=True), _record(latest="0.9.26")):
        _, detail = report.write_run(tmp_path, record)
        assert detail is not None
        assert "\n\n\n" not in detail.read_text(encoding="utf-8")


def test_interview_answers_are_rendered_into_the_page(tmp_path) -> None:
    ambiguity = Ambiguity(gate="patch-level bump", question="Adopt 0.10.0?", detail="minor bump")
    record = _record(latest="0.10.0", ambiguities=(ambiguity,))
    answered = report.RunRecord(
        tool=record.tool,
        sync=record.sync,
        upstream=record.upstream,
        observations=record.observations,
        moved=record.moved,
        verdict=record.verdict,
        answers=(("patch-level bump", "Hold until the schema change is reviewed"),),
    )
    _, detail = report.write_run(tmp_path, answered)
    assert detail is not None
    assert "Hold until the schema change is reviewed" in detail.read_text(encoding="utf-8")


# ---------------------------------------------------------- issue diffs ----


def test_state_change_is_detected(tmp_path) -> None:
    previous = {"issue:#2101": Observation(key="issue:#2101", state="open", updated_at="t1")}
    current = (Observation(key="issue:#2101", state="closed", updated_at="t2"),)
    assert issues.changes(current, previous) == current


def test_unchanged_issue_is_not_reported(tmp_path) -> None:
    same = Observation(key="issue:#2101", state="open", updated_at="t1", comments=3)
    assert issues.changes((same,), {"issue:#2101": same}) == ()


def test_first_ever_observation_is_not_a_change(tmp_path) -> None:
    """A first run must not report every tracked issue as having moved."""
    current = (Observation(key="issue:#2101", state="open"),)
    assert issues.changes(current, {}) == ()


def test_errored_observation_never_counts_as_movement(tmp_path) -> None:
    """Rate-limited or offline runs must not manufacture movement."""
    previous = {"issue:#2101": Observation(key="issue:#2101", state="open")}
    errored = (Observation(key="issue:#2101", error="rate limited"),)
    assert issues.changes(errored, previous) == ()


def test_errored_observation_preserves_its_previous_baseline(tmp_path) -> None:
    """A transient failure must not ERASE the baseline it could not refresh.

    Dropping the entry entirely would make the next run see no previous value,
    treat the item as first-ever-observed, and report NO change even if the issue
    had moved — hiding exactly one real change, at the worst possible moment.
    """
    good = (Observation(key="issue:#2101", state="open", updated_at="t1"),)
    issues.save_current(tmp_path, "graphify", good)

    # A later run where the fetch failed.
    errored = (Observation(key="issue:#2101", error="rate limited"),)
    issues.save_current(tmp_path, "graphify", errored)

    kept = issues.load_previous(tmp_path, "graphify")
    assert kept["issue:#2101"].updated_at == "t1"

    # And the run after that still detects the real movement.
    moved = (Observation(key="issue:#2101", state="closed", updated_at="t2"),)
    assert issues.changes(moved, kept) == moved


def test_watch_item_removed_from_config_is_pruned(tmp_path) -> None:
    """State must not accumulate entries for items no longer tracked."""
    issues.save_current(tmp_path, "graphify", (Observation(key="issue:#1", state="open"),))
    issues.save_current(tmp_path, "graphify", (Observation(key="issue:#2", state="open"),))
    assert set(issues.load_previous(tmp_path, "graphify")) == {"issue:#2"}


def test_failed_step4_lookup_earns_a_detail_page(tmp_path) -> None:
    """A run where every issue lookup errored must not look like a clean run."""
    record = _record()
    with_errors = report.RunRecord(
        tool=record.tool,
        sync=record.sync,
        upstream=record.upstream,
        observations=(Observation(key="issue:#2101", error="rate limited"),),
        moved=(),
        verdict=record.verdict,
    )
    _, detail = report.write_run(tmp_path, with_errors)
    assert detail is not None


def test_errored_observations_are_not_written_as_the_new_baseline(tmp_path) -> None:
    """Storing an error would make the NEXT successful run look like movement."""
    observations = (
        Observation(key="issue:#2101", state="open", updated_at="t1"),
        Observation(key="issue:#2086", error="rate limited"),
    )
    path = issues.save_current(tmp_path, "graphify", observations)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert "issue:#2101" in stored
    assert "issue:#2086" not in stored


def test_local_watch_items_observe_without_network(tmp_path) -> None:
    """A local finding has no upstream to read but must still be carried."""
    item = config.WatchItem(kind="local", ref="schema-gap", note="labelling still broken")
    observed = issues.observe(item, default_repo="")
    assert observed.state == "local"
    assert observed.error == ""


def test_round_trip_through_saved_state(tmp_path) -> None:
    observations = (Observation(key="issue:#2101", state="open", updated_at="t1", comments=2),)
    issues.save_current(tmp_path, "graphify", observations)
    loaded = issues.load_previous(tmp_path, "graphify")
    assert issues.changes(observations, loaded) == ()


def test_a_pipe_in_any_cell_cannot_corrupt_the_table(tmp_path) -> None:
    """One `|` silently splits a cell into two columns and wrecks the table.

    These cells carry upstream-controlled text — issue titles, `gh` error
    strings, filesystem paths — so the escaping is not hypothetical hygiene.
    """
    verdict = Verdict(
        tool="evil|tool",
        current="a|b",
        latest="",
        auto_apply=False,
        gates_passed=(),
        ambiguities=(),
    )
    report.append_row(
        tmp_path, when=datetime(2026, 7, 24, tzinfo=UTC), verdict=verdict, detail=None
    )
    line = next(
        line
        for line in (tmp_path / report.LANDING).read_text(encoding="utf-8").splitlines()
        if "evil" in line
    )
    assert line.replace(r"\|", "").count("|") == 5


def test_a_pipe_in_a_finding_detail_is_escaped(tmp_path) -> None:
    record = _record(drifted=True)
    piped = SyncStatus(
        tool="graphify",
        pinned="0.9.25",
        resolved="0.9.25",
        findings=(Finding("resolution", DRIFT, "reached /a|b/graphify"),),
    )
    with_pipe = report.RunRecord(
        tool=record.tool,
        sync=piped,
        upstream=record.upstream,
        observations=record.observations,
        moved=record.moved,
        verdict=record.verdict,
    )
    _, detail = report.write_run(tmp_path, with_pipe)
    assert detail is not None
    row = next(
        line for line in detail.read_text(encoding="utf-8").splitlines() if "resolution" in line
    )
    assert row.replace(r"\|", "").count("|") == 4


def test_degraded_success_does_not_wipe_the_baseline(tmp_path) -> None:
    """A 200 whose body lacks `state` is not a good reading.

    It parses cleanly and yields blanks, so keying carry-forward on `error` alone
    let it overwrite a good baseline, report a spurious "issue moved", and then
    report it a SECOND time on the next healthy run — because the baseline it
    compared against had been wiped by the first.
    """
    good = Observation(key="issue:#1653", state="open", updated_at="t1")
    issues.save_current(tmp_path, "graphify", (good,))

    degraded = Observation(key="issue:#1653", state="", updated_at="")
    assert not degraded.usable
    assert issues.changes((degraded,), issues.load_previous(tmp_path, "graphify")) == ()
    issues.save_current(tmp_path, "graphify", (degraded,))

    kept = issues.load_previous(tmp_path, "graphify")
    assert kept["issue:#1653"].state == "open"

    # A genuine close is still detected afterwards — control arm.
    closed = (Observation(key="issue:#1653", state="closed", updated_at="t2"),)
    assert issues.changes(closed, kept) == closed


def test_a_response_without_state_is_reported_as_an_error(monkeypatch) -> None:
    """`observe` must name a degraded success rather than return silent blanks."""
    import subprocess

    class _Res:
        returncode = 0
        stdout = '{"state":null,"updated_at":null,"comments":null,"title":null}'
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: _Res())
    observed = issues.observe(config.WatchItem(kind="issue", ref="1653"), default_repo="o/r")
    assert observed.error
    assert not observed.usable


def test_missing_config_says_so_instead_of_passing_silently(tmp_path, capsys) -> None:
    """Silence is this design's definition of "clean", so it must never mean "absent".

    A renamed config, a wrong `-C` in the hook, or a consumer repo copying the
    hook without the config would otherwise disable the check forever while
    looking green — the top-level "check that can only pass".
    """
    from kb_setup.currency import run as currency_run

    assert currency_run.check(tmp_path) == 0
    assert "did NOT run" in capsys.readouterr().err


def test_unknown_tool_filter_is_an_error_not_silence(tmp_path, capsys) -> None:
    """A typo'd --tool matched nothing and exited 0 with no output."""
    from kb_setup.currency import run as currency_run

    (tmp_path / "mise.toml").write_text('[tools]\nx = "1"\n', encoding="utf-8")
    (tmp_path / "currency.toml").write_text(
        '[tool.graphify]\nmise_key = "pipx:graphifyy"\n', encoding="utf-8"
    )
    assert currency_run.check(tmp_path, only="graphifyy") == 2
    assert "unknown tool" in capsys.readouterr().err


# -------------------------------------------- partial upstream readings ----


def test_a_partial_upstream_read_is_not_rendered_as_reachable_yes() -> None:
    """`reachable` and `error` are not opposites — a partial read sets BOTH.

    `probe()` returns `reachable=True` with `error` set when PyPI answered but a
    GitHub release lookup failed. The report used to print a bare `Reachable:
    yes` over a real `gh api ... exited 1`, publishing a clean bill of health
    for a question that was only half asked.
    """
    line = report._reachable_line(
        UpstreamStatus(pypi_latest="0.9.26", reachable=True, error="gh api ... exited 1")
    )
    assert line != "yes"
    assert "gh api ... exited 1" in line


def test_a_fully_clean_upstream_read_still_says_yes() -> None:
    """Control arm: the line must not have become unconditionally hedged."""
    assert report._reachable_line(UpstreamStatus(pypi_latest="0.9.26")) == "yes"


def test_an_unreachable_upstream_still_says_no() -> None:
    status = UpstreamStatus(reachable=False, error="pypi lookup failed")
    assert report._reachable_line(status).startswith("**no**")


def test_a_200_with_null_metadata_is_rejected_not_recorded(monkeypatch) -> None:
    """`updated_at` and `comments` are DIFFED, so a null in either is unread.

    Only `state` used to be validated. A 200 carrying `state="open"` with a null
    `updated_at` parsed to a blank string with no error, counted as usable,
    overwrote a good baseline, and reported "moved" — then reported it a SECOND
    time on the next healthy run, because the value it should have compared
    against had already been wiped.
    """
    monkeypatch.setattr(
        issues,
        "_fetch_issue",
        lambda _r, _n: ({"state": "open", "updated_at": None, "comments": None}, ""),
    )
    item = config.WatchItem(kind="issue", ref="2101", repo="o/r")
    observed = issues.observe(item, default_repo="o/r")
    assert observed.error
    assert not observed.usable


def test_a_complete_200_is_still_recorded(monkeypatch) -> None:
    """Control arm: the guard must not reject healthy readings.

    `comments: 0` is the trap in the other direction — a legitimate value that a
    truthiness check would have thrown away.
    """
    monkeypatch.setattr(
        issues,
        "_fetch_issue",
        lambda _r, _n: ({"state": "open", "updated_at": "2026-07-22T00:00:00Z", "comments": 0}, ""),
    )
    item = config.WatchItem(kind="issue", ref="2101", repo="o/r")
    observed = issues.observe(item, default_repo="o/r")
    assert not observed.error
    assert observed.usable
    assert observed.comments == 0
