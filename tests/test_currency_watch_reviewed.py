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

A cold review of the first cut (`dd90e64f`) found the release axis alone was not
enough: a `Reviewed` record bound only `(key, version)`, so rewriting a watch
item's `note` (or reusing its `ref` for a different finding) let a stale
clearance keep passing. `finding_digest` binds the record to the finding's
CONTENT too — `test_a_clearance_does_not_survive_the_notes_content_changing` is
that invariant, and it matters at least as much as
`test_a_record_at_an_older_version_leaves_the_gate_open` did the first time.
"""

from __future__ import annotations

import json
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


_SCHEMA_GAP_NOTE = "labelling still broken"
_OTHER_GAP_NOTE = "a second local finding"

_LOCAL = Observation(key="local:schema-gap", state="local", title=_SCHEMA_GAP_NOTE)
_LOCAL_2 = Observation(key="local:other-gap", state="local", title=_OTHER_GAP_NOTE)


def _reviewed_for(observation: Observation, version: str, at: str = "d") -> Reviewed:
    """A `Reviewed` record that legitimately clears `observation` at `version`.

    Binds `finding_digest` to the observation's CURRENT `title` (== the watch
    item's `note`) so every "happy path" test below exercises a record that is
    valid on both axes, the way `watch_reviewed` itself builds one.
    """
    return Reviewed(
        key=observation.key,
        version=version,
        at=at,
        finding_digest=issues.finding_digest(observation.title),
    )


# ---------------------------------------------------- decide._gate_local, widened ----
#
# The four gate-behaviour tests section 5 of the original spec names as the
# minimum bundle, plus the note-content invariant the cold review added (B1).


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
    reviewed = {_LOCAL.key: _reviewed_for(_LOCAL, "0.9.26")}
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
    """THE version invariant. A record stamped at an older release must not clear a newer target."""
    reviewed = {_LOCAL.key: _reviewed_for(_LOCAL, "0.9.25")}
    verdict = decide(
        sync=_sync(),
        upstream=_upstream("0.9.26"),
        moved=(),
        observations=(_LOCAL,),
        reviewed=reviewed,
    )
    assert not verdict.auto_apply
    assert any(a.gate == GATES[4] for a in verdict.ambiguities)


def test_a_clearance_does_not_survive_the_notes_content_changing() -> None:
    """THE finding-identity invariant (cold review B1).

    Same key, same version, a DIFFERENT note — a rewritten finding, or a `ref`
    reused for a new one — must reopen the gate exactly as if nothing had ever
    been recorded.
    """
    stale_reviewed = {_LOCAL.key: _reviewed_for(_LOCAL, "0.9.26")}
    redefined = Observation(
        key=_LOCAL.key, state="local", title="a completely different finding now"
    )
    verdict = decide(
        sync=_sync(),
        upstream=_upstream("0.9.26"),
        moved=(),
        observations=(redefined,),
        reviewed=stale_reviewed,
    )
    assert not verdict.auto_apply
    assert any(a.gate == GATES[4] for a in verdict.ambiguities)
    # Control arm: the SAME note still clears at the SAME version.
    unchanged = decide(
        sync=_sync(),
        upstream=_upstream("0.9.26"),
        moved=(),
        observations=(_LOCAL,),
        reviewed=stale_reviewed,
    )
    assert unchanged.auto_apply


def test_two_local_items_one_recorded_one_not_still_stops() -> None:
    reviewed = {_LOCAL.key: _reviewed_for(_LOCAL, "0.9.26")}
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
    """Decoration aside, `v0.9.26` and `0.9.26` name the same release — BOTH directions.

    Only the first direction was tested before (cold review, m6). The second is
    the one that actually occurs: GitHub hands back `latest` AS the tag.
    """
    reviewed_v = {_LOCAL.key: _reviewed_for(_LOCAL, "v0.9.26")}
    verdict = decide(
        sync=_sync(),
        upstream=_upstream("0.9.26"),
        moved=(),
        observations=(_LOCAL,),
        reviewed=reviewed_v,
    )
    assert verdict.auto_apply

    reviewed_bare = {_LOCAL.key: _reviewed_for(_LOCAL, "0.9.26")}
    verdict2 = decide(
        sync=_sync(),
        upstream=_upstream("v0.9.26"),
        moved=(),
        observations=(_LOCAL,),
        reviewed=reviewed_bare,
    )
    assert verdict2.auto_apply


# ------------------------------------------------------------------ issues.py ----


def test_finding_digest_is_deterministic_and_content_sensitive() -> None:
    assert issues.finding_digest("same") == issues.finding_digest("same")
    assert issues.finding_digest("a") != issues.finding_digest("b")
    assert issues.finding_digest("") != ""  # content_hash never returns an empty string


def test_load_reviewed_round_trips_through_record_reviewed(tmp_path: Path) -> None:
    record = Reviewed(
        key="local:x",
        version="0.9.26",
        at="2026-08-25",
        finding_digest=issues.finding_digest("n-note"),
        note="n",
    )
    path = issues.record_reviewed(tmp_path, "graphify", record)
    assert path.name == "graphify-watch-reviewed.json"
    loaded = issues.load_reviewed(tmp_path, "graphify")
    assert loaded == {"local:x": record}


def test_load_reviewed_is_empty_on_a_missing_or_corrupt_store(tmp_path: Path) -> None:
    assert issues.load_reviewed(tmp_path, "graphify") == {}
    (tmp_path / "graphify-watch-reviewed.json").write_text("not json", encoding="utf-8")
    assert issues.load_reviewed(tmp_path, "graphify") == {}


def test_load_reviewed_returns_empty_when_the_path_is_a_directory(tmp_path: Path) -> None:
    """A REALISTIC OSError arm (cold review, m7) — no mocking.

    A directory sits where the file should be, so `read_text()` raises
    `IsADirectoryError`.
    """
    (tmp_path / "graphify-watch-reviewed.json").mkdir()
    assert issues.load_reviewed(tmp_path, "graphify") == {}


def test_load_reviewed_refuses_a_non_dict_json_payload(tmp_path: Path) -> None:
    """The `not isinstance(raw, dict)` guard (cold review, m7), exercised directly."""
    (tmp_path / "graphify-watch-reviewed.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert issues.load_reviewed(tmp_path, "graphify") == {}


def test_load_reviewed_skips_an_entry_missing_a_version(tmp_path: Path) -> None:
    """The `value.get('version')` filter (cold review, m7), exercised directly."""
    path = tmp_path / "graphify-watch-reviewed.json"
    path.write_text(
        json.dumps(
            {
                "local:no-version": {"at": "d", "finding_digest": "x"},
                "local:good": {"version": "0.9.26", "at": "d", "finding_digest": "y"},
            }
        ),
        encoding="utf-8",
    )
    loaded = issues.load_reviewed(tmp_path, "graphify")
    assert set(loaded) == {"local:good"}


def test_record_reviewed_merges_rather_than_overwrites_other_keys(tmp_path: Path) -> None:
    issues.record_reviewed(
        tmp_path,
        "graphify",
        Reviewed(
            key="local:a", version="0.9.25", at="d1", finding_digest=issues.finding_digest("a")
        ),
    )
    issues.record_reviewed(
        tmp_path,
        "graphify",
        Reviewed(
            key="local:b", version="0.9.25", at="d1", finding_digest=issues.finding_digest("b")
        ),
    )
    loaded = issues.load_reviewed(tmp_path, "graphify")
    assert set(loaded) == {"local:a", "local:b"}
    # Re-recording one key does not disturb the other's stored claim.
    issues.record_reviewed(
        tmp_path,
        "graphify",
        Reviewed(
            key="local:a", version="0.9.26", at="d2", finding_digest=issues.finding_digest("a")
        ),
    )
    loaded = issues.load_reviewed(tmp_path, "graphify")
    assert loaded["local:a"].version == "0.9.26"
    assert loaded["local:b"].version == "0.9.25"


def test_record_reviewed_prunes_keys_absent_from_valid_keys(tmp_path: Path) -> None:
    """B1's pruning half.

    `valid_keys` removes a clearance no longer configured, the same way
    `save_current` already prunes stale observations.
    """
    issues.record_reviewed(
        tmp_path,
        "graphify",
        Reviewed(
            key="local:a", version="0.9.25", at="d1", finding_digest=issues.finding_digest("a")
        ),
    )
    issues.record_reviewed(
        tmp_path,
        "graphify",
        Reviewed(
            key="local:b", version="0.9.25", at="d1", finding_digest=issues.finding_digest("b")
        ),
        valid_keys={"local:a", "local:b"},
    )
    assert set(issues.load_reviewed(tmp_path, "graphify")) == {"local:a", "local:b"}
    # local:b has since been removed from currency.toml; this write's valid_keys
    # no longer names it, so it must be pruned even though this write is ABOUT
    # local:c, not local:b.
    issues.record_reviewed(
        tmp_path,
        "graphify",
        Reviewed(
            key="local:c", version="0.9.25", at="d2", finding_digest=issues.finding_digest("c")
        ),
        valid_keys={"local:a", "local:c"},
    )
    assert set(issues.load_reviewed(tmp_path, "graphify")) == {"local:a", "local:c"}


def test_record_reviewed_with_no_valid_keys_prunes_nothing(tmp_path: Path) -> None:
    """Control arm: omitting `valid_keys` (the default) keeps every prior entry."""
    issues.record_reviewed(
        tmp_path,
        "graphify",
        Reviewed(
            key="local:a", version="0.9.25", at="d1", finding_digest=issues.finding_digest("a")
        ),
    )
    issues.record_reviewed(
        tmp_path,
        "graphify",
        Reviewed(
            key="local:b", version="0.9.25", at="d1", finding_digest=issues.finding_digest("b")
        ),
    )
    assert set(issues.load_reviewed(tmp_path, "graphify")) == {"local:a", "local:b"}


def test_record_reviewed_refuses_rather_than_destroying_a_corrupt_store(tmp_path: Path) -> None:
    """M2: an unreadable store must not be silently overwritten with just the new record."""
    path = tmp_path / "graphify-watch-reviewed.json"
    path.write_text("not json at all", encoding="utf-8")
    with pytest.raises(issues.ReviewedStoreUnreadableError):
        issues.record_reviewed(
            tmp_path,
            "graphify",
            Reviewed(
                key="local:new", version="0.9.26", at="d", finding_digest=issues.finding_digest("x")
            ),
        )
    # The corrupt file itself is untouched — not clobbered, not "fixed".
    assert path.read_text(encoding="utf-8") == "not json at all"


def test_record_reviewed_refuses_over_a_non_dict_json_payload(tmp_path: Path) -> None:
    path = tmp_path / "graphify-watch-reviewed.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(issues.ReviewedStoreUnreadableError):
        issues.record_reviewed(
            tmp_path,
            "graphify",
            Reviewed(
                key="local:new", version="0.9.26", at="d", finding_digest=issues.finding_digest("x")
            ),
        )
    assert path.read_text(encoding="utf-8") == "[1, 2, 3]"


def test_record_reviewed_with_no_existing_file_is_unaffected(tmp_path: Path) -> None:
    """Control arm: a genuinely first-ever write must NOT be refused."""
    path = issues.record_reviewed(
        tmp_path,
        "graphify",
        Reviewed(
            key="local:new", version="0.9.26", at="d", finding_digest=issues.finding_digest("x")
        ),
    )
    assert path.exists()


def test_cleared_for_compares_parsed_releases_not_strings() -> None:
    reviewed = {
        "k": Reviewed(key="k", version="v0.9.26", at="d", finding_digest=issues.finding_digest("n"))
    }
    assert issues.cleared_for(reviewed, "k", "0.9.26", current_note="n")
    assert not issues.cleared_for(reviewed, "k", "0.9.27", current_note="n")


def test_cleared_for_fails_closed_on_unparsable_or_empty_input() -> None:
    """The assumption row: do not rely on `same_release`'s own fallback — arm it here."""
    garbled = {
        "k": Reviewed(
            key="k", version="not-a-version", at="d", finding_digest=issues.finding_digest("n")
        )
    }
    assert not issues.cleared_for(garbled, "k", "0.9.26", current_note="n")
    clean = {
        "k": Reviewed(key="k", version="0.9.26", at="d", finding_digest=issues.finding_digest("n"))
    }
    assert not issues.cleared_for(clean, "k", "", current_note="n")  # empty target
    assert not issues.cleared_for(
        clean, "k", "not-a-version", current_note="n"
    )  # unparsable target
    assert not issues.cleared_for({}, "k", "0.9.26", current_note="n")  # no record at all
    empty_version = {
        "k": Reviewed(key="k", version="", at="d", finding_digest=issues.finding_digest("n"))
    }
    assert not issues.cleared_for(empty_version, "k", "0.9.26", current_note="n")


def test_cleared_for_fails_closed_when_the_note_no_longer_matches() -> None:
    """B1's direct unit-level arm: a digest mismatch refuses regardless of version match."""
    reviewed = {
        "k": Reviewed(
            key="k", version="0.9.26", at="d", finding_digest=issues.finding_digest("original")
        )
    }
    assert issues.cleared_for(reviewed, "k", "0.9.26", current_note="original")
    assert not issues.cleared_for(reviewed, "k", "0.9.26", current_note="redefined")
    # Omitting `current_note` (the default "") must also fail closed rather than
    # coincidentally matching a record whose `finding_digest` is itself blank —
    # `finding_digest("")` is a real SHA-256 hex string, never "".
    blank_digest = {"k": Reviewed(key="k", version="0.9.26", at="d", finding_digest="")}
    assert not issues.cleared_for(blank_digest, "k", "0.9.26")


# --------------------------------------------------------- run.watch_reviewed ----


def _repo(
    tmp_path: Path, *, locals_: tuple[tuple[str, str], ...] = (("schema-gap", _SCHEMA_GAP_NOTE),)
) -> Path:
    (tmp_path / "mise.toml").write_text('[tools]\n"pipx:graphifyy" = "0.9.25"\n', encoding="utf-8")
    watch_blocks = "".join(
        f'\n[[tool.graphify.watch]]\nkind = "local"\nref = "{ref}"\nnote = "{note}"\n'
        for ref, note in locals_
    )
    (tmp_path / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'artifact = "graphify-out/graph.json"\n'
        'stamp = "graphify-out/.currency-stamp.json"\n' + watch_blocks,
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
    assert loaded["local:schema-gap"].finding_digest == issues.finding_digest(_SCHEMA_GAP_NOTE)


def test_watch_reviewed_refuses_a_ref_matching_no_local_item(tmp_path: Path) -> None:
    """A recorded clearance for a key nothing observes could never be checked again."""
    root = _repo(tmp_path)
    rc = run.watch_reviewed(root, only="graphify", ref="no-such-ref", version="0.9.26")
    assert rc == 2
    assert not _store_path(root).exists()


def test_watch_reviewed_refuses_when_the_tool_has_no_local_watch_items(tmp_path: Path) -> None:
    root = _repo(tmp_path, locals_=())
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


def test_watch_reviewed_refuses_when_the_store_is_corrupt(tmp_path: Path) -> None:
    """M2, at the CLI-facing layer: `ReviewedStoreUnreadableError` is caught and refused."""
    root = _repo(tmp_path)
    _store_path(root).parent.mkdir(parents=True, exist_ok=True)
    _store_path(root).write_text("not json", encoding="utf-8")
    rc = run.watch_reviewed(root, only="graphify", ref="schema-gap", version="0.9.26")
    assert rc == 2
    assert _store_path(root).read_text(encoding="utf-8") == "not json"


def test_watch_reviewed_prunes_a_clearance_whose_watch_item_was_removed(tmp_path: Path) -> None:
    """B1's pruning half, end to end through the CLI-facing entry point."""
    root = _repo(
        tmp_path, locals_=(("schema-gap", _SCHEMA_GAP_NOTE), ("other-gap", _OTHER_GAP_NOTE))
    )
    assert run.watch_reviewed(root, only="graphify", ref="schema-gap", version="0.9.26") == 0
    assert run.watch_reviewed(root, only="graphify", ref="other-gap", version="0.9.26") == 0
    report_root = root / report.REPORT_DIR
    assert set(issues.load_reviewed(report_root, "graphify")) == {
        "local:schema-gap",
        "local:other-gap",
    }
    # currency.toml is edited to drop "other-gap" entirely.
    _repo(root, locals_=(("schema-gap", _SCHEMA_GAP_NOTE),))
    # Re-recording schema-gap (still configured) must prune the orphaned entry.
    assert run.watch_reviewed(root, only="graphify", ref="schema-gap", version="0.9.27") == 0
    assert set(issues.load_reviewed(report_root, "graphify")) == {"local:schema-gap"}


# ------------------------------------------------ run._missing_required (m4) ----


def test_missing_required_flags_lists_only_the_absent_ones() -> None:
    """A direct unit test of the REQUIRED-flags guard, isolated from `Version.parse`.

    An empty `--version` also fails `Version.parse`, so no CALLER-level input can
    tell the two guards apart (cold review, m4) — this function-level test can.
    """
    assert run._missing_required("", "", "") == [
        "--tool <name>",
        "--ref <watch-item-ref>",
        "--version <release>",
    ]
    assert run._missing_required("graphify", "", "0.9.26") == ["--ref <watch-item-ref>"]
    assert run._missing_required("graphify", "schema-gap", "0.9.26") == []


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

    This is `mise-tasks-only.md`'s MISSING-1. The mode-detection loop only skips
    a flag's value when the value comes AFTER a RECOGNISED flag in the scan, so
    this must put every flag BEFORE the `watch-reviewed` mode token — a version
    of this test that put the mode first left the stray value at `positional[1]`,
    which nothing reads, so it passed identically with the fix reverted (cold
    review, M1). Flags-before-mode is also the form the ARMED check below
    actually exercises.
    """
    root = _repo(tmp_path)
    rc = cli._currency(
        root,
        [
            "--tool",
            "graphify",
            "--ref",
            "schema-gap",
            "--version",
            "0.9.26",
            "--note",
            "re-probed, still broken",
            "watch-reviewed",
        ],
    )
    assert rc == 0
    assert _store_path(root).exists()
    loaded = issues.load_reviewed(root / report.REPORT_DIR, "graphify")
    assert loaded["local:schema-gap"].note == "re-probed, still broken"


# ------------------------------------------------------- report._watch_table ----


def test_watch_table_shows_a_clearance_distinctly_from_a_stale_one() -> None:
    """A stale clearance must not read as clean in the committed, reviewed evidence."""
    reviewed = {
        "local:cleared": Reviewed(
            key="local:cleared",
            version="0.9.26",
            at="2026-08-25",
            finding_digest=issues.finding_digest("a"),
        ),
        "local:stale": Reviewed(
            key="local:stale",
            version="0.9.20",
            at="2026-01-01",
            finding_digest=issues.finding_digest("b"),
        ),
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


def test_watch_table_does_not_render_stale_when_the_target_is_unknown() -> None:
    """M3: `decide()` returns `latest=""` when upstream never got checked.

    That is "not checked", never "stale". Collapsing the two made a valid
    clearance render as STALE in a committed page on every run where upstream
    was down.
    """
    reviewed = {
        "local:x": Reviewed(
            key="local:x", version="0.9.26", at="d", finding_digest=issues.finding_digest("a")
        )
    }
    observations = (Observation(key="local:x", state="local", title="a"),)
    table = report._watch_table(observations, (), reviewed, "")
    assert "STALE" not in table
    assert "not checked" in table
    # Control arm: a genuine target still renders STALE when the version disagrees.
    stale_table = report._watch_table(observations, (), reviewed, "0.9.27")
    assert "STALE" in stale_table


def test_reviewed_cell_not_checked_versus_stale_versus_cleared() -> None:
    """The three-state contract directly, one call per state."""
    reviewed = {
        "k": Reviewed(key="k", version="0.9.26", at="d", finding_digest=issues.finding_digest("n"))
    }
    not_checked = report._reviewed_cell(reviewed, "k", "", current_note="n")
    assert "not checked" in not_checked
    assert "STALE" not in not_checked
    assert "cleared" not in not_checked

    stale = report._reviewed_cell(reviewed, "k", "0.9.27", current_note="n")
    assert "STALE" in stale

    cleared = report._reviewed_cell(reviewed, "k", "0.9.26", current_note="n")
    assert cleared.startswith("cleared @ 0.9.26")


def test_watch_table_with_reviewed_omitted_still_renders_every_item_unreviewed() -> None:
    """Control arm for `_watch_table`'s new parameters: omitting `reviewed` must not crash.

    It does NOT claim the table is unchanged from before #486 — it is not:
    every call now carries a sixth `reviewed` column, a real, visible change
    for every existing caller (cold review, m5). What must hold is only that a
    caller supplying nothing still gets a valid table.
    """
    observations = (Observation(key="local:x", state="local", title="a"),)
    table = report._watch_table(observations, ())
    assert "local:x" in table
    header, _rule, *data_rows = table.splitlines()
    assert header.count("|") == 7  # 6 columns -> 7 pipe separators
    assert data_rows[0].rstrip("|").rstrip().endswith("—")


# --------------------------------------------------------- config.ToolSpec.watch ----


def test_a_local_watch_item_is_reachable_by_ref_through_toolspec(tmp_path: Path) -> None:
    """Ground the CLI-layer ref match against the real config loader, not a fixture."""
    root = _repo(tmp_path)
    spec = config.load(root)[0]
    local_items = [item for item in spec.watch if item.kind != "issue"]
    assert [item.ref for item in local_items] == ["schema-gap"]
    assert local_items[0].key == "local:schema-gap"
