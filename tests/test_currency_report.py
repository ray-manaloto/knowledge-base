"""kb_setup.currency.report + .issues — step 6's committed record and step 4's diff.

The cadence rule (landing row always, detail page only when the run has content)
is the part worth pinning down: it is the difference between a log that stays
readable and one nobody opens.
"""

import json

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
