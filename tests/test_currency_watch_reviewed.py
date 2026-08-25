# Copyright (c) 2026 Raymond Manaloto
"""`kb-setup currency watch-reviewed` (#486) — the local-watch gate made falsifiable.

Gate 5's second half used to ask a human "N local watch item(s) must be re-probed
against this release. Done?" with no way to answer it — a hand-appended prose note
in `currency.toml`, read by nothing, indistinguishable whether it was written for
this release or six releases ago. This module pins the fix in every layer it
touches: the reviewed-record store (`issues`), the gate that consults it
(`decide._gate_local`), the CLI surface that writes it (`run.watch_reviewed` +
`cli._currency`), and the committed report that must be able to SHOW a clearance
(`report._watch_table`).

The one test that matters most is `test_a_record_at_an_older_version_leaves_the_gate_open`
— a suite without it has not tested the feature, only the plumbing around it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import cli
from kb_setup.currency import config, issues, report, run
from kb_setup.currency.decide import GATES, decide
from kb_setup.currency.issues import Observation, Reviewed
from kb_setup.currency.sync import OK, Finding, SyncStatus
from kb_setup.currency.upstream import UpstreamStatus

# ------------------------------------------------------------- decide() fixtures ----


def _sync(pinned: str = "0.9.25") -> SyncStatus:
    return SyncStatus(
        tool="graphify",
        pinned=pinned,
        resolved=pinned,
        findings=(
            Finding("pin", OK, "pinned"),
            Finding("resolution", OK, "reaches the pin"),
            Finding("build-stamp", OK, "built by the pin"),
        ),
    )


def _upstream(latest: str = "0.9.26") -> UpstreamStatus:
    return UpstreamStatus(latest=latest, github_tag=f"v{latest}", notes="Routine fixes.")


_LOCAL = Observation(key="local:schema-gap", state="local", title="re-probe on each bump")
_LOCAL_2 = Observation(key="local:other-gap", state="local", title="a second local finding")


# ---------------------------------------------------- decide._gate_local, widened ----
#
# The four gate-behaviour tests section 5 of the spec names as the minimum bundle.


def test_a_local_item_with_no_record_leaves_the_gate_open() -> None:
    verdict = decide(
        sync=_sync(), upstream=_upstream(), moved=(), observations=(_LOCAL,), reviewed={}
    )
    assert not verdict.auto_apply
    assert any(a.gate == GATES[4] for a in verdict.ambiguities)
    # Control arm: the default (no `reviewed` argument at all) behaves identically
    # — every EXISTING caller of `decide` keeps today's behaviour unchanged.
    default_verdict = decide(sync=_sync(), upstream=_upstream(), moved=(), observations=(_LOCAL,))
    assert not default_verdict.auto_apply
    assert any(a.gate == GATES[4] for a in default_verdict.ambiguities)


def test_a_record_at_the_target_version_clears_the_item() -> None:
    reviewed = {"local:schema-gap": Reviewed(key="local:schema-gap", version="0.9.26", at="d")}
    verdict = decide(
        sync=_sync(),
        upstream=_upstream("0.9.26"),
        moved=(),
        observations=(_LOCAL,),
        reviewed=reviewed,
    )
    assert verdict.auto_apply
    assert verdict.ambiguities == ()


def test_a_record_at_an_older_version_leaves_the_gate_open() -> None:
    """THE invariant. A record stamped at an older release must not clear a newer target."""
    reviewed = {"local:schema-gap": Reviewed(key="local:schema-gap", version="0.9.25", at="d")}
    verdict = decide(
        sync=_sync(),
        upstream=_upstream("0.9.26"),
        moved=(),
        observations=(_LOCAL,),
        reviewed=reviewed,
    )
    assert not verdict.auto_apply
    assert any(a.gate == GATES[4] for a in verdict.ambiguities)


def test_two_local_items_one_recorded_one_not_still_stops() -> None:
    reviewed = {"local:schema-gap": Reviewed(key="local:schema-gap", version="0.9.26", at="d")}
    verdict = decide(
        sync=_sync(),
        upstream=_upstream("0.9.26"),
        moved=(),
        observations=(_LOCAL, _LOCAL_2),
        reviewed=reviewed,
    )
    assert not verdict.auto_apply
    ambiguity = next(a for a in verdict.ambiguities if a.gate == GATES[4])
    # Only the un-cleared item survives into the question — partial clearing.
    assert "1 local watch item" in ambiguity.question
    assert "local:other-gap" in ambiguity.detail
    assert "local:schema-gap" not in ambiguity.detail


def test_a_v_prefixed_record_clears_the_bare_target_and_vice_versa() -> None:
    """Decoration aside, `v0.9.26` and `0.9.26` name the same release."""
    reviewed = {"local:schema-gap": Reviewed(key="local:schema-gap", version="v0.9.26", at="d")}
    verdict = decide(
        sync=_sync(),
        upstream=_upstream("0.9.26"),
        moved=(),
        observations=(_LOCAL,),
        reviewed=reviewed,
    )
    assert verdict.auto_apply


# ------------------------------------------------------------------ issues.py ----


def test_load_reviewed_round_trips_through_record_reviewed(tmp_path: Path) -> None:
    path = issues.record_reviewed(
        tmp_path, "graphify", Reviewed(key="local:x", version="0.9.26", at="2026-08-25", note="n")
    )
    assert path.name == "graphify-watch-reviewed.json"
    loaded = issues.load_reviewed(tmp_path, "graphify")
    assert loaded == {
        "local:x": Reviewed(key="local:x", version="0.9.26", at="2026-08-25", note="n")
    }


def test_load_reviewed_is_empty_on_a_missing_or_corrupt_store(tmp_path: Path) -> None:
    assert issues.load_reviewed(tmp_path, "graphify") == {}
    (tmp_path / "graphify-watch-reviewed.json").write_text("not json", encoding="utf-8")
    assert issues.load_reviewed(tmp_path, "graphify") == {}


def test_record_reviewed_merges_rather_than_overwrites_other_keys(tmp_path: Path) -> None:
    issues.record_reviewed(tmp_path, "graphify", Reviewed(key="local:a", version="0.9.25", at="d1"))
    issues.record_reviewed(tmp_path, "graphify", Reviewed(key="local:b", version="0.9.25", at="d1"))
    loaded = issues.load_reviewed(tmp_path, "graphify")
    assert set(loaded) == {"local:a", "local:b"}
    # Re-recording one key does not disturb the other's stored claim.
    issues.record_reviewed(tmp_path, "graphify", Reviewed(key="local:a", version="0.9.26", at="d2"))
    loaded = issues.load_reviewed(tmp_path, "graphify")
    assert loaded["local:a"].version == "0.9.26"
    assert loaded["local:b"].version == "0.9.25"


def test_cleared_for_compares_parsed_releases_not_strings() -> None:
    reviewed = {"k": Reviewed(key="k", version="v0.9.26", at="d")}
    assert issues.cleared_for(reviewed, "k", "0.9.26")
    assert not issues.cleared_for(reviewed, "k", "0.9.27")


def test_cleared_for_fails_closed_on_unparsable_or_empty_input() -> None:
    """The assumption row: do not rely on `same_release`'s own fallback — arm it here."""
    garbled = {"k": Reviewed(key="k", version="not-a-version", at="d")}
    assert not issues.cleared_for(garbled, "k", "0.9.26")
    clean = {"k": Reviewed(key="k", version="0.9.26", at="d")}
    assert not issues.cleared_for(clean, "k", "")  # empty target
    assert not issues.cleared_for(clean, "k", "not-a-version")  # unparsable target
    assert not issues.cleared_for({}, "k", "0.9.26")  # no record at all
    empty_version = {"k": Reviewed(key="k", version="", at="d")}
    assert not issues.cleared_for(empty_version, "k", "0.9.26")


# --------------------------------------------------------- run.watch_reviewed ----


def _repo(tmp_path: Path, *, with_local_watch: bool = True) -> Path:
    (tmp_path / "mise.toml").write_text('[tools]\n"pipx:graphifyy" = "0.9.25"\n', encoding="utf-8")
    watch_block = (
        '\n[[tool.graphify.watch]]\nkind = "local"\nref = "schema-gap"\n'
        'note = "labelling still broken"\n'
        if with_local_watch
        else ""
    )
    (tmp_path / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'artifact = "graphify-out/graph.json"\n'
        'stamp = "graphify-out/.currency-stamp.json"\n' + watch_block,
        encoding="utf-8",
    )
    artifact = tmp_path / "graphify-out" / "graph.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text('{"nodes": []}', encoding="utf-8")
    return tmp_path


def _store_path(root: Path) -> Path:
    return root / report.REPORT_DIR / "graphify-watch-reviewed.json"


def test_watch_reviewed_records_a_valid_claim(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    rc = run.watch_reviewed(root, only="graphify", ref="schema-gap", version="0.9.26")
    assert rc == 0
    loaded = issues.load_reviewed(root / report.REPORT_DIR, "graphify")
    assert loaded["local:schema-gap"].version == "0.9.26"


def test_watch_reviewed_refuses_a_ref_matching_no_local_item(tmp_path: Path) -> None:
    """A recorded clearance for a key nothing observes could never be checked again."""
    root = _repo(tmp_path)
    rc = run.watch_reviewed(root, only="graphify", ref="no-such-ref", version="0.9.26")
    assert rc == 2
    assert not _store_path(root).exists()


def test_watch_reviewed_refuses_when_the_tool_has_no_local_watch_items(tmp_path: Path) -> None:
    root = _repo(tmp_path, with_local_watch=False)
    rc = run.watch_reviewed(root, only="graphify", ref="schema-gap", version="0.9.26")
    assert rc == 2
    assert not _store_path(root).exists()


def test_watch_reviewed_refuses_a_dangling_tool_rather_than_reading_it_as_absent(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    rc = run.watch_reviewed(root, only="", ref="schema-gap", version="0.9.26")
    assert rc == 2
    assert not _store_path(root).exists()


def test_watch_reviewed_refuses_a_dangling_version_rather_than_recording_empty(
    tmp_path: Path,
) -> None:
    """An empty version would compare equal to nothing and could never clear a gate.

    But a wrongly-filed record is still wrong, so this refuses rather than writing one.
    """
    root = _repo(tmp_path)
    rc = run.watch_reviewed(root, only="graphify", ref="schema-gap", version="")
    assert rc == 2
    assert not _store_path(root).exists()


def test_watch_reviewed_refuses_an_unparsable_version(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    rc = run.watch_reviewed(root, only="graphify", ref="schema-gap", version="not-a-version")
    assert rc == 2
    assert not _store_path(root).exists()


def test_watch_reviewed_refuses_an_unknown_tool(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    rc = run.watch_reviewed(root, only="no-such-tool", ref="schema-gap", version="0.9.26")
    assert rc == 2
    assert not _store_path(root).exists()


# --------------------------------------------------- cli._currency dispatch ----


def test_cli_currency_dispatches_watch_reviewed_with_every_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: dict[str, object] = {}

    def _fake(
        repo_root: Path, *, only: str = "", ref: str = "", version: str = "", note: str = ""
    ) -> int:
        calls.update(repo_root=repo_root, only=only, ref=ref, version=version, note=note)
        return 0

    monkeypatch.setattr(run, "watch_reviewed", _fake)
    rc = cli._currency(
        tmp_path,
        [
            "watch-reviewed",
            "--tool",
            "graphify",
            "--ref",
            "schema-gap",
            "--version",
            "0.9.26",
            "--note",
            "re-probed, still broken",
        ],
    )
    assert rc == 0
    assert calls == {
        "repo_root": tmp_path,
        "only": "graphify",
        "ref": "schema-gap",
        "version": "0.9.26",
        "note": "re-probed, still broken",
    }


def test_cli_currency_watch_reviewed_rejects_a_value_that_is_itself_a_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--tool --version 1.2.3` must not read `only` as the literal string "--version"."""

    def _must_not_run(*_args: object, **_kwargs: object) -> int:
        pytest.fail("must not reach watch_reviewed")

    monkeypatch.setattr(run, "watch_reviewed", _must_not_run)
    rc = cli._currency(
        tmp_path, ["watch-reviewed", "--tool", "--version", "1.2.3", "--ref", "schema-gap"]
    )
    assert rc == 2


def test_cli_currency_registers_ref_and_note_as_value_flags(tmp_path: Path) -> None:
    """Without `--ref`/`--note` in `value_flags`, their VALUE is misread as the mode.

    This is `mise-tasks-only.md`'s MISSING-1: omitting a value-taking flag from
    that set breaks invocation outright, before the command's own logic ever runs.
    """
    root = _repo(tmp_path)
    rc = cli._currency(
        root,
        [
            "watch-reviewed",
            "--tool",
            "graphify",
            "--ref",
            "schema-gap",
            "--version",
            "0.9.26",
        ],
    )
    assert rc == 0
    assert _store_path(root).exists()


# ------------------------------------------------------- report._watch_table ----


def test_watch_table_shows_a_clearance_distinctly_from_a_stale_one() -> None:
    """A stale clearance must not read as clean in the committed, reviewed evidence."""
    reviewed = {
        "local:cleared": Reviewed(key="local:cleared", version="0.9.26", at="2026-08-25"),
        "local:stale": Reviewed(key="local:stale", version="0.9.20", at="2026-01-01"),
    }
    observations = (
        Observation(key="local:cleared", state="local", title="a"),
        Observation(key="local:stale", state="local", title="b"),
        Observation(key="local:unreviewed", state="local", title="c"),
    )
    table = report._watch_table(observations, (), reviewed, "0.9.26")
    assert "cleared @ 0.9.26" in table
    assert "STALE @ 0.9.20" in table
    lines = table.splitlines()
    unreviewed_row = next(line for line in lines if "local:unreviewed" in line)
    assert unreviewed_row.rstrip("|").rstrip().endswith("—")


def test_watch_table_with_no_reviewed_argument_behaves_as_before() -> None:
    """Control arm: every existing caller (no `reviewed` passed) keeps working."""
    observations = (Observation(key="local:x", state="local", title="a"),)
    table = report._watch_table(observations, ())
    assert "local:x" in table


# --------------------------------------------------------- config.ToolSpec.watch ----


def test_a_local_watch_item_is_reachable_by_ref_through_toolspec(tmp_path: Path) -> None:
    """Ground the CLI-layer ref match against the real config loader, not a fixture."""
    root = _repo(tmp_path)
    spec = config.load(root)[0]
    local_items = [item for item in spec.watch if item.kind != "issue"]
    assert [item.ref for item in local_items] == ["schema-gap"]
    assert local_items[0].key == "local:schema-gap"
