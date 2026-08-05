"""kb_setup.currency.views (#182) — is each derived view describing the graph on disk?

The defect these pin down was invisible by construction. `size:mtime_ns` can only
see an output that MOVED, and a view that is stale precisely because nothing
regenerated it never moves — so `graph.graphml` and `wiki/` reported
`recorded == live` on the live corpus while describing a graph eleven hours old.

The load-bearing tests here are not "STALE is returned when the fingerprints
differ". They are:

* the FALSE-POSITIVE arm — a view written earlier than the graph BY THE SAME RUN
  must not be stale, which is what killed the clock-based first implementation;
* the DIRECTORY arm — an in-place rewrite under `wiki/` must register as a
  regeneration, with the shallow fingerprint as the control proving the deep one
  is load-bearing rather than decoration;
* the HAND-OFF arms — every state this module is deliberately SILENT about must
  be shown to be loud somewhere else in the same command's output, or the silence
  is just a missing check.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import stamps
from kb_setup.currency import config, staleness, sync, views

if TYPE_CHECKING:
    import pytest

_CURRENCY = """[tool.graphify]
mise_key = "pipx:graphifyy"
binary = "graphify"
artifact = "graphify-out/graph.json"
artifacts = [
  "graphify-out/GRAPH_REPORT.md",
  "graphify-out/graph.graphml",
  "graphify-out/wiki",
]
# Declared so the `staleness` hand-off arm below has a real verdict to assert
# against: `check_inputs` short-circuits to SKIP for a tool with no inputs, and a
# hand-off test whose other half is a no-op proves nothing.
inputs = ["sources/*.manifest"]
stamp = "graphify-out/.currency-stamp.json"
"""

#: Explicit mtimes, seconds apart, so the ORDER of writes in a test is a fact and
#: not a race with the clock's resolution. The real defect is measured in hours;
#: these only have to be distinguishable.
_T0 = 1_700_000_000
_ONE_MINUTE = 60


def _spec(repo_root: Path) -> config.ToolSpec:
    return config.load(repo_root)[0]


def _repo(tmp_path: Path, *, views_exist: bool = True) -> Path:
    """A repo with a graph, the three declared views, and a currency.toml."""
    out = tmp_path / "graphify-out"
    out.mkdir()
    (out / "graph.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
    if views_exist:
        (out / "wiki").mkdir()
        (out / "GRAPH_REPORT.md").write_text("# report v0\n", encoding="utf-8")
        (out / "graph.graphml").write_text("<graphml v0/>\n", encoding="utf-8")
        (out / "wiki" / "index.md").write_text("# wiki v0\n", encoding="utf-8")
    (tmp_path / "currency.toml").write_text(_CURRENCY, encoding="utf-8")
    return tmp_path


def _touch(path: Path, when: int) -> None:
    """Pin a path's mtime so write ORDER is deterministic, not clock-dependent."""
    os.utime(path, (when, when))


def _stamp(repo_root: Path) -> Path:
    """A bare stamp, with NO operation bracketed around it.

    This is `kb-build`: it writes the stamp having regenerated no view, so every
    view comes out with unknown provenance. Deliberately not a helper that
    certifies — a test that reached for certification by accident would be
    asserting against a state no real caller produces.
    """
    return sync.write_stamp(repo_root, _spec(repo_root), version="0.9.33")


def _regenerate(repo_root: Path, tag: str = "kb-artifacts", **files: str) -> None:
    """Model a real view-producing run: snapshot, write, restamp inside the bracket.

    The bracket is the whole mechanism (`sync.view_records`), so the tests have to
    take one exactly as `artifacts.generate` and `graphify_ops.label` do. Writing
    the files WITHOUT it is a different scenario — an unobserved change — and
    `test_an_unobserved_regeneration_is_never_certified` is the test for that.

    `files` is keyed by the view's basename, so a caller reads as the run it is
    standing in for: `_regenerate(repo, GRAPH_REPORT="…")` is a `kb-label`.
    """
    out = repo_root / "graphify-out"
    before = stamps.snapshot_views(repo_root)
    for name, text in files.items():
        path = out / "wiki" / "index.md" if name == "wiki" else out / _VIEW_FILES[name]
        path.write_text(text, encoding="utf-8")
    stamps.refresh_after_regen(repo_root, tag=tag, views_before=before)


#: basename -> the path under `graphify-out/` that `_regenerate` writes.
_VIEW_FILES = {"GRAPH_REPORT": "GRAPH_REPORT.md", "graphml": "graph.graphml"}


def _check(repo_root: Path) -> views.ViewStatus:
    return views.check_views(repo_root, _spec(repo_root))


def _stale_paths(status: views.ViewStatus) -> list[str]:
    return [line.split()[0] for line in status.stale]


# --- the states, and who owns the silence of each ----------------------------


def test_a_freshly_stamped_repo_reports_ok_and_prints_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Baseline: stamp, then immediately ask. Every view was just observed.

    A first `write_stamp` records `graph: ""` for views it has never seen change,
    so this asserts the SECOND stamp — the state a real repo reaches the first
    time `kb-artifacts` regenerates anything.
    """
    repo = _repo(tmp_path)
    _stamp(repo)
    _regenerate(repo, GRAPH_REPORT="# report v1\n", graphml="<graphml v1/>\n", wiki="# wiki v1\n")

    status = _check(repo)
    assert status.state == views.OK
    capsys.readouterr()  # discard the restamp's own line; this asserts on report()
    views.report([status])
    assert capsys.readouterr().out == ""


def test_a_stamp_predating_view_provenance_is_not_a_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A v3 stamp with no `views` key must report NOT CHECKED, never OK.

    This is every stamp that existed before #182 landed. Collapsing "the question
    was never asked" into a pass is the single failure this whole engine is
    written to avoid, and it is reachable here by one missing dict key.
    """
    repo = _repo(tmp_path)
    stamp_file = repo / "graphify-out" / ".currency-stamp.json"
    _stamp(repo)
    payload = json.loads(stamp_file.read_text(encoding="utf-8"))
    del payload["views"]
    stamp_file.write_text(json.dumps(payload), encoding="utf-8")

    status = _check(repo)
    assert status.state == views.NOT_VERIFIABLE
    assert not status.quiet
    views.report([status])
    out = capsys.readouterr().out
    assert "NOT CHECKED" in out
    # The MESSAGE, not only the state. A `stamped_views` that returned `{}`
    # instead of None still reaches NOT_VERIFIABLE — every view falls through to
    # *provenance unknown* — so a state-only assertion cannot tell the two apart.
    # The remedy is what differs, and the remedy is what a reader acts on.
    assert "carries no usable view provenance" in out
    assert "kb-artifacts" in out


def test_a_views_key_that_is_not_a_dict_is_not_a_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTROL ARM on the parse: a corrupt `views` value reports the same remedy.

    **This test was a survivor**, and how it survived is worth keeping. It
    originally asserted only `state == NOT_VERIFIABLE`, and the mutation that
    makes `stamped_views` return `{}` instead of None survived it untouched —
    because `{}` reaches NOT_VERIFIABLE too, by the per-view *provenance unknown*
    route. Same state, different message, and the test could not see the
    difference it existed to protect.

    So it asserts the REMEDY LINE. That is also the honest claim: a hand-edited
    or half-written stamp is not "predating" anything, and the wording had to
    stop diagnosing and start describing before this assertion could be true of
    both causes.
    """
    repo = _repo(tmp_path)
    stamp_file = repo / "graphify-out" / ".currency-stamp.json"
    _stamp(repo)
    payload = json.loads(stamp_file.read_text(encoding="utf-8"))
    payload["views"] = "not a mapping"
    stamp_file.write_text(json.dumps(payload), encoding="utf-8")

    status = _check(repo)
    assert status.state == views.NOT_VERIFIABLE
    assert not status.blind, "a corrupt map is one stamp-level fault, not N per-view ones"
    views.report([status])
    out = capsys.readouterr().out
    assert "carries no usable view provenance" in out
    assert "kb-artifacts" in out


def test_no_graph_is_never_built_and_staleness_owns_that_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """HAND-OFF ARM. This module is silent on a fresh clone — and something else is not.

    `views` stays quiet here deliberately: `staleness.report` already prints the
    "no graph has been built here yet" line, and two headers on one condition is
    how a reader learns to skim past both. That is only defensible while the OTHER
    reporter actually fires, so both halves are asserted together — a later change
    that silences `staleness` cannot leave this state with no reporter at all.
    """
    repo = tmp_path
    (repo / "currency.toml").write_text(_CURRENCY, encoding="utf-8")

    status = _check(repo)
    assert status.state == views.NEVER_BUILT
    assert status.quiet
    views.report([status])
    assert capsys.readouterr().out == ""

    staleness.report([staleness.check_inputs(repo, _spec(repo))])
    assert "no graph has been built here yet" in capsys.readouterr().out


def test_no_views_on_disk_is_not_ok_and_build_stamp_owns_that_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """HAND-OFF ARM. A graph with no views is NOT_GENERATED here and DRIFT there.

    Returning OK would be a false pass over a set in which nothing exists, so the
    state is distinct even though it prints nothing. The second half is the arm
    that makes the silence legitimate: `sync`'s build-stamp check reports each
    missing view loudly, with the same remedy, in the same command's output.
    """
    repo = _repo(tmp_path, views_exist=False)
    _stamp(repo)

    status = _check(repo)
    assert status.state == views.NOT_GENERATED
    assert status.quiet
    views.report([status])
    assert capsys.readouterr().out == ""

    finding = sync._check_stamp(repo, _spec(repo), "0.9.33")
    assert finding.status == sync.DRIFT
    assert "graphify-out/graph.graphml (missing)" in finding.detail


def test_a_tool_with_no_declared_views_skips(tmp_path: Path) -> None:
    """CONTROL ARM: nothing declared is not-applicable, never a finding."""
    (tmp_path / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'artifact = "graphify-out/graph.json"\n'
        'stamp = "graphify-out/.currency-stamp.json"\n',
        encoding="utf-8",
    )
    assert _check(tmp_path).state == views.SKIP


# --- the defect itself -------------------------------------------------------


def test_a_graph_rewritten_without_regenerating_the_views_makes_them_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE #182 DEFECT. `kb-merge`/`kb-label` move the graph and leave the views.

    Before this check, every row read `recorded == live` and the command was
    silent. The remedy line must say `kb-artifacts` and NOT `kb-build`:
    `artifacts.generate` has one caller and a rebuild does not reach it, so
    printing "or rebuild" would hand the reader an instruction that cannot repair
    what it is reporting.
    """
    repo = _repo(tmp_path)
    _stamp(repo)
    _regenerate(repo, GRAPH_REPORT="# report v1\n", graphml="<graphml v1/>\n", wiki="# wiki v1\n")

    # ...and now ONLY the graph moves, exactly as a merge-only run leaves it.
    (repo / "graphify-out" / "graph.json").write_text(
        json.dumps({"nodes": [{"id": "new"}]}), encoding="utf-8"
    )

    status = _check(repo)
    assert status.state == views.STALE
    assert len(status.stale) == 3

    views.report([status])
    out = capsys.readouterr().out
    assert "derived views describe an earlier graph" in out
    assert "mise run kb-artifacts" in out
    assert "rebuild" not in out


def test_a_view_written_before_the_graph_by_the_same_run_is_not_stale(
    tmp_path: Path,
) -> None:
    """THE FALSE-POSITIVE ARM — the measurement that replaced the clock.

    `graphify label` writes GRAPH_REPORT.md and THEN graph.json. Measured live:
    12:12:07 and 12:12:25, 18.7 s apart, in one run, with `graph.graphml` eleven
    hours behind both. An ordering rule ("older than the graph ⇒ stale") flags the
    report and the graphml identically and cannot tell them apart, because a run
    writes its outputs in some order and the primary is not always last.

    Here the report is pinned a full minute OLDER than the graph and must come out
    FRESH, while the untouched graphml comes out stale — the two verdicts an
    ordering rule provably cannot separate. If this test ever passes for the wrong
    reason, it is because a clock crept back in.
    """
    repo = _repo(tmp_path)
    out = repo / "graphify-out"
    _stamp(repo)
    # A `kb-artifacts` run first, so all three views have KNOWN provenance —
    # otherwise they are merely unobserved, and the arm would pass without ever
    # distinguishing a fresh view from a stale one.
    _regenerate(repo, GRAPH_REPORT="# report v0\n", graphml="<graphml v0/>\n", wiki="# wiki v0\n")

    # The label run: report first, graph second, then the restamp — all inside
    # one bracket, which is what a real `graphify_ops.label` takes.
    before = stamps.snapshot_views(repo)
    (out / "GRAPH_REPORT.md").write_text("# report v1 (this label)\n", encoding="utf-8")
    _touch(out / "GRAPH_REPORT.md", _T0)
    (out / "graph.json").write_text(json.dumps({"nodes": [{"id": "labelled"}]}), encoding="utf-8")
    _touch(out / "graph.json", _T0 + _ONE_MINUTE)
    stamps.refresh_after_regen(repo, tag="kb-label", views_before=before)

    status = _check(repo)
    assert status.state == views.STALE
    stale_paths = _stale_paths(status)
    assert "graphify-out/GRAPH_REPORT.md" not in stale_paths, (
        "the report was regenerated BY this run and is older only in wall-clock terms"
    )
    assert "graphify-out/graph.graphml" in stale_paths
    assert "graphify-out/wiki" in stale_paths


def test_a_first_observation_records_unknown_provenance_not_the_current_graph(
    tmp_path: Path,
) -> None:
    """A view seen for the first time must not be certified against today's graph.

    "This file exists" is not evidence about which graph produced it. Recording
    the current fingerprint here would hand a brand-new stamp a clean pass over
    views of entirely unknown provenance — and it is the tempting shortcut,
    because it makes the first run look tidy.
    """
    repo = _repo(tmp_path)
    _stamp(repo)

    recorded = sync.stamped_views(sync.read_stamp(repo, _spec(repo)))
    assert recorded is not None
    assert {v["graph"] for v in recorded.values()} == {""}

    status = _check(repo)
    assert status.state == views.NOT_VERIFIABLE
    assert len(status.blind) == 3


def test_the_remedy_clears_the_message_on_a_first_ever_views_map(tmp_path: Path) -> None:
    """THE BOOTSTRAP ARM — found live, after the honest-but-wrong version shipped.

    On the first stamp to carry a views map there is no previous map to diff
    against, so a full `mise run kb-artifacts` — the very remedy the check prints
    — regenerated all three views and left every one reading *provenance
    unknown*. It ran, it exited 0, it re-stamped, and the message did not change.

    **A remedy that does not clear the message it prints is the signal-rot this
    whole check exists to fix**, so the arm is not "the flag is honoured" but
    "one run of the printed command is enough". A second `kb-artifacts` would
    have cleared it via the identity diff, which is exactly the wrong bar: it
    costs minutes.
    """
    repo = _repo(tmp_path)
    _stamp(repo)
    assert _check(repo).state == views.NOT_VERIFIABLE  # the state this test is about

    _regenerate(repo, GRAPH_REPORT="# r\n", graphml="<g/>\n", wiki="# w\n")

    assert _check(repo).state == views.OK


def test_a_restamp_that_did_not_regenerate_the_views_certifies_nothing(tmp_path: Path) -> None:
    """CONTROL ARM: the same call without the flag must leave provenance unknown.

    `kb-merge`, `kb-label` and `kb-build` all reach `restamp_artifacts` and none of
    them regenerates a view. If the flag defaulted the other way — or were ignored
    — every one of them would certify views it never touched, which is the false
    pass the whole design is arranged to make impossible.
    """
    repo = _repo(tmp_path)
    spec = _spec(repo)
    sync.write_stamp(repo, spec, version="0.9.33")

    sync.restamp_artifacts(repo, spec)

    assert _check(repo).state == views.NOT_VERIFIABLE


def test_an_unobserved_regeneration_is_never_certified(tmp_path: Path) -> None:
    """THE COLD-LANE FINDING (round 1, P2): a false pass, reproduced then closed.

    `refresh_after_regen` is best-effort and swallows its own failures, so a
    `kb-artifacts` run can regenerate every view and leave the stamp describing
    the OLD ones. The first implementation then certified any view whose identity
    merely differed from the stamp — so the next `kb-merge`, which rewrites
    graph.json and restamps, certified all three against a graph they PREDATE.
    `check_views` returned OK.

    The bracket is what closes it: a view is certified only when it changed
    between the caller's own snapshot and now. A change that happened outside any
    bracket is `""` — unknown, loud, and never a pass.
    """
    repo = _repo(tmp_path)
    out = repo / "graphify-out"
    spec = _spec(repo)
    _stamp(repo)
    _regenerate(repo, GRAPH_REPORT="# r\n", graphml="<g/>\n", wiki="# w\n")
    assert _check(repo).state == views.OK

    # kb-artifacts regenerates the views; its best-effort restamp fails silently.
    for name, text in (("GRAPH_REPORT.md", "# r2\n"), ("graph.graphml", "<g2/>\n")):
        (out / name).write_text(text, encoding="utf-8")
    (out / "wiki" / "index.md").write_text("# w2\n", encoding="utf-8")

    # kb-merge: rewrites the graph, regenerates no view, brackets nothing.
    (out / "graph.json").write_text(json.dumps({"nodes": [{"id": "merged"}]}), encoding="utf-8")
    sync.restamp_artifacts(repo, spec)

    status = _check(repo)
    assert status.state == views.NOT_VERIFIABLE, "views certified against a graph they predate"
    assert len(status.blind) == 3


def test_certification_survives_a_later_graph_move(tmp_path: Path) -> None:
    """The certified state must still GO stale — certifying is not exempting.

    The bootstrap flag writes the current fingerprint for every view, and the
    tempting wrong implementation writes something that always compares equal.
    This is the arm that shows a certified view still fails the moment the graph
    moves underneath it.
    """
    repo = _repo(tmp_path)
    _stamp(repo)
    _regenerate(repo, GRAPH_REPORT="# r\n", graphml="<g/>\n", wiki="# w\n")
    assert _check(repo).state == views.OK

    (repo / "graphify-out" / "graph.json").write_text(
        json.dumps({"nodes": [{"id": "moved"}]}), encoding="utf-8"
    )

    status = _check(repo)
    assert status.state == views.STALE
    assert len(status.stale) == 3


def test_stale_outranks_unknown_provenance_and_the_blind_list_rides_along(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ORDERING ARM: a known-stale view must not be buried under an unknown one.

    Both loud states can hold at once — one view regenerated once and then left
    behind, another never observed at all. Reporting only NOT_VERIFIABLE would let
    the weaker answer suppress the stronger, so STALE wins the status and the
    blind list is still printed rather than dropped.
    """
    repo = _repo(tmp_path)
    out = repo / "graphify-out"
    _stamp(repo)
    # graphml now has provenance; the other two were never observed being generated
    _regenerate(repo, graphml="<graphml v1/>\n")
    (out / "graph.json").write_text(json.dumps({"nodes": [{"id": "moved"}]}), encoding="utf-8")

    status = _check(repo)
    assert status.state == views.STALE
    assert _stale_paths(status) == ["graphify-out/graph.graphml"]
    assert len(status.blind) == 2

    views.report([status])
    printed = capsys.readouterr().out
    assert "graph.graphml" in printed
    assert "NOT CHECKED" in printed
    assert "GRAPH_REPORT.md" in printed


# --- the directory trap ------------------------------------------------------


def test_an_in_place_rewrite_under_a_directory_view_registers_as_a_regeneration(
    tmp_path: Path,
) -> None:
    """THE DIRECTORY ARM, with its own control.

    `sync.artifact_fingerprint` stats the DIRECTORY for `wiki`, and a directory's
    mtime moves only when an entry is added or removed — measured: rewriting a
    file in place does not move it. The live tree shows the same gap from the
    other side, its newest FILE being 79 microseconds newer than the directory.

    So a `kb-artifacts` run that rewrote the same 9,465 page names would be
    invisible to the shallow fingerprint, and `view_records` would conclude the
    wiki had NOT been regenerated — leaving it reported stale forever, a check
    that can only FAIL.

    The first assertion is the CONTROL: it establishes that the shallow
    fingerprint really cannot see this edit on this filesystem. Without it the
    second assertion proves nothing, because a deep fingerprint that happened to
    agree with a shallow one would pass either way.
    """
    repo = _repo(tmp_path)
    wiki = repo / "graphify-out" / "wiki"
    shallow_before = sync.artifact_fingerprint(wiki)
    deep_before = sync.deep_artifact_fingerprint(wiki)

    (wiki / "index.md").write_text("# wiki REGENERATED, same filename\n", encoding="utf-8")

    assert sync.artifact_fingerprint(wiki) == shallow_before, (
        "control: an in-place rewrite must be invisible to the directory stat, "
        "or this test is not exercising the trap it was written for"
    )
    assert sync.deep_artifact_fingerprint(wiki) != deep_before


def test_a_wiki_regenerated_in_place_stops_being_reported_stale(tmp_path: Path) -> None:
    """The trap's consequence, end to end: the check must be CLEARABLE.

    A stale `wiki/` whose regeneration the engine cannot detect is worse than no
    check — it prints a multi-minute remedy that provably never silences it. This
    is the arm that proves running `kb-artifacts` actually works.
    """
    repo = _repo(tmp_path)
    out = repo / "graphify-out"
    _stamp(repo)
    _regenerate(repo, wiki="# wiki v1\n")
    (out / "graph.json").write_text(json.dumps({"nodes": [{"id": "moved"}]}), encoding="utf-8")
    assert "graphify-out/wiki" in _stale_paths(_check(repo))

    # `kb-artifacts`: rewrite the SAME page name, then restamp.
    _regenerate(repo, wiki="# wiki v2, regenerated in place\n")

    assert "graphify-out/wiki" not in _stale_paths(_check(repo))


def test_a_deleted_view_drops_its_record_rather_than_carrying_it(tmp_path: Path) -> None:
    """A record for a file that is gone must not survive to certify its replacement.

    Carried forward, the stale `{identity, graph}` would be compared against a
    freshly regenerated view whose identity happens to differ — and the diff would
    then record the CURRENT graph for it, certifying provenance nobody observed.
    """
    repo = _repo(tmp_path)
    out = repo / "graphify-out"
    _stamp(repo)
    _regenerate(repo, graphml="<graphml v1/>\n")
    (out / "graph.graphml").unlink()
    _stamp(repo)

    recorded = sync.stamped_views(sync.read_stamp(repo, _spec(repo)))
    assert recorded is not None
    assert "graphify-out/graph.graphml" not in recorded


# --- the stamp's other guarantees survive ------------------------------------


def test_the_views_map_does_not_disturb_version_or_input_provenance(tmp_path: Path) -> None:
    """CONTROL ARM: adding `views` must not launder what the stamp already recorded.

    `restamp_artifacts` carries `version`, `source_ref` and the input map forward
    verbatim precisely so a derived-view regeneration cannot restate what the
    graph was built FROM. A new field computed inside `write_stamp` is exactly the
    kind of change that quietly re-observes one of them.
    """
    repo = _repo(tmp_path)
    spec = _spec(repo)
    sync.write_stamp(repo, spec, version="0.9.33", source_ref="v0.9.33", inputs={"a": "sha256:x"})

    sync.restamp_artifacts(repo, spec)

    after = sync.read_stamp(repo, spec)
    assert after["version"] == "0.9.33"
    assert after["source_ref"] == "v0.9.33"
    assert sync.stamped_input_fingerprints(after) == {"a": "sha256:x"}


def test_the_primary_artifact_is_never_a_view_of_itself(tmp_path: Path) -> None:
    """A config listing the graph in both `artifact` and `artifacts` is legal.

    `all_artifacts` de-duplicates it for fingerprinting, so the same config must
    not produce a view record saying the graph was generated from the graph — which
    would go stale the instant the graph is rewritten and could never be cleared.
    """
    (tmp_path / "currency.toml").write_text(
        _CURRENCY.replace(
            'artifacts = [\n  "graphify-out/GRAPH_REPORT.md",',
            'artifacts = [\n  "graphify-out/graph.json",\n  "graphify-out/GRAPH_REPORT.md",',
        ),
        encoding="utf-8",
    )
    out = tmp_path / "graphify-out"
    out.mkdir()
    (out / "graph.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
    (out / "wiki").mkdir()
    (out / "GRAPH_REPORT.md").write_text("# report\n", encoding="utf-8")
    (out / "graph.graphml").write_text("<graphml/>\n", encoding="utf-8")

    spec = _spec(tmp_path)
    assert "graphify-out/graph.json" in spec.artifacts  # the fixture really is the odd config
    sync.write_stamp(tmp_path, spec, version="0.9.33")

    recorded = sync.stamped_views(sync.read_stamp(tmp_path, spec))
    assert recorded is not None
    assert "graphify-out/graph.json" not in recorded
