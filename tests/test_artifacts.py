"""kb-artifacts helpers: node counting + the large-graph svg skip."""

import json
import subprocess
from pathlib import Path

from kb_setup import artifacts, hyperedges, prose


def test_node_count_reads_graph(tmp_path) -> None:
    g = tmp_path / "graph.json"
    g.write_text(json.dumps({"nodes": [{"id": "a"}, {"id": "b"}], "edges": []}))
    assert artifacts._node_count(g) == 2


def test_node_count_missing_is_zero(tmp_path) -> None:
    assert artifacts._node_count(tmp_path / "nope.json") == 0


def test_svg_in_default_registry_but_gated_by_limit() -> None:
    # svg ships in the registry (runnable via `only=['svg']`) but the limit exists
    # so a large-graph default run drops it. Guards against the #2076-adjacent crash.
    names = [a[0] for a in artifacts._ARTIFACTS]
    assert "svg" in names
    assert artifacts._SVG_NODE_LIMIT == 5000


# --- hyperedge carry (#171 local mitigation, #175) --------------------------

_HYPEREDGE = {"id": "he1", "nodes": ["a"]}


def _graph_with_hyperedge(repo_root: Path) -> Path:
    out = repo_root / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    p = out / "graph.json"
    p.write_text(
        json.dumps(
            {
                "nodes": [{"id": "a", "label": "a"}],
                "links": [],
                "graph": {"hyperedges": [_HYPEREDGE]},
                "hyperedges": [_HYPEREDGE],
            }
        ),
        encoding="utf-8",
    )
    return p


def test_report_entry_carries_hyperedges_across_the_rewrite(tmp_path: Path, monkeypatch) -> None:
    """`report` runs `cluster-only` — the one entry sharing `kb-label`'s lossy round-trip.

    See `hyperedges.py`'s module docstring for the verified mechanism, and
    `_REWRITES_GRAPH`'s comment above for why "report" is the only entry here
    that needs it.
    """
    graph = _graph_with_hyperedge(tmp_path)

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        # Reproduce graphify's own lossy rewrite: cluster-only loads + rewrites
        # graph.json, and on this repo's real aggregate that empties both slots.
        graph.write_text(
            json.dumps({"nodes": [{"id": "a", "label": "a"}], "links": [], "hyperedges": []}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(list(cmd), 0)

    monkeypatch.setattr(artifacts, "ensure_runtime_deps", lambda _r: [])
    monkeypatch.setattr(artifacts, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(artifacts.subprocess, "run", fake_run)

    assert artifacts.generate(tmp_path, only=["report"]) == 0

    on_disk = json.loads(graph.read_text(encoding="utf-8"))
    assert on_disk["hyperedges"] == [_HYPEREDGE]
    assert on_disk["graph"]["hyperedges"] == [_HYPEREDGE]


def test_report_entry_re_derives_the_prose_graph_after_the_rewrite(
    tmp_path: Path, monkeypatch
) -> None:
    """The rewriting entry changed graph.json — `--prose` must see the new corpus.

    `report` (`cluster-only`) is the one `_ARTIFACTS` entry that REWRITES
    graph.json (`_REWRITES_GRAPH`), and every OTHER writer of graph.json in
    this codebase re-derives the prose graph as part of the same operation
    (#175 cold review, finding 3). Stubbed at the `prose.derive_for` boundary
    rather than run for real: what is under test is that `generate()` calls
    it AT ALL for the rewriting entry, not `prose.derive`'s own filtering
    logic — that is `test_prose_rederivation.py`'s job.
    """
    graph = _graph_with_hyperedge(tmp_path)
    derived: list[Path] = []

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(list(cmd), 0)

    monkeypatch.setattr(artifacts, "ensure_runtime_deps", lambda _r: [])
    monkeypatch.setattr(artifacts, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(artifacts.subprocess, "run", fake_run)
    monkeypatch.setattr(artifacts.prose, "derive_for", derived.append)

    assert artifacts.generate(tmp_path, only=["report"]) == 0
    assert derived == [tmp_path], "the rewriting entry must re-derive the prose graph"
    assert graph.is_file(), "fixture sanity: graph.json must still be the one just rewritten"


def test_report_entries_failed_prose_derivation_fails_generate(tmp_path: Path, monkeypatch) -> None:
    """A prose-derivation failure must not be reported as a clean `kb-artifacts` run.

    CONTROL ARM for the test above: `report` rewrote graph.json (the
    subprocess succeeded), but the prose graph could not be re-derived —
    `generate()` must still return non-zero, or `kb-query --prose` is left
    silently describing an older corpus with nothing on the CLI having said
    so (#175 cold review, finding 3).
    """
    _graph_with_hyperedge(tmp_path)

    monkeypatch.setattr(artifacts, "ensure_runtime_deps", lambda _r: [])
    monkeypatch.setattr(artifacts, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(
        artifacts.subprocess, "run", lambda cmd, **_: subprocess.CompletedProcess(list(cmd), 0)
    )

    def boom(_root: Path) -> prose.ProseStats:
        raise ValueError("no non-AST nodes")

    monkeypatch.setattr(artifacts.prose, "derive_for", boom)

    assert artifacts.generate(tmp_path, only=["report"]) == 1


def test_a_non_rewriting_entry_never_touches_hyperedges(tmp_path: Path, monkeypatch) -> None:
    """`graphml` only READS graph.json — capture()/reattach() must not even run.

    Paying a several-hundred-MB read for an entry that structurally cannot have
    dropped anything would be pure cost with no defect to guard against. Checked
    by call count, not just by outcome: an entry that happens to leave the file
    unchanged would pass an outcome-only assertion even if it wastefully called
    capture()/reattach() anyway.
    """
    graph = _graph_with_hyperedge(tmp_path)
    before = graph.read_bytes()
    calls: list[str] = []

    monkeypatch.setattr(hyperedges, "capture", lambda _p: (calls.append("capture"), [])[1])
    monkeypatch.setattr(hyperedges, "reattach", lambda _p, _h: calls.append("reattach"))
    monkeypatch.setattr(artifacts, "ensure_runtime_deps", lambda _r: [])
    monkeypatch.setattr(artifacts, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(
        artifacts.subprocess, "run", lambda cmd, **_: subprocess.CompletedProcess(list(cmd), 0)
    )

    assert artifacts.generate(tmp_path, only=["graphml"]) == 0

    assert calls == []
    assert graph.read_bytes() == before


# --- currency stamp refresh really gets called (#179 respec, mutation survivor) --
#
# `test_graphify_exe_call_sites.py`'s `test_artifacts_run_the_resolved_binary`
# patches `stamps.refresh_after_regen` to a no-op, but that test's SUBJECT is
# which binary `generate` runs, not whether the restamp happens — patching a
# function that exists either way proves nothing about whether it was called.
# Before the #179 refactor this was incidentally covered: the old
# `monkeypatch.setattr(artifacts, "_restamp", ...)` would raise `AttributeError`
# the moment `_restamp` stopped existing, so deleting the restamp call silently
# broke that test for an unrelated reason. `stamps.refresh_after_regen` exists
# independent of whether `generate` calls it, so that accidental tripwire is
# gone — this test is the direct replacement.


def test_generate_refreshes_the_currency_stamp_on_success(tmp_path: Path, monkeypatch) -> None:
    """A successful `generate()` run must call the shared restamp exactly once.

    The snapshot it hands over is asserted separately, below.
    """
    _graph_with_hyperedge(tmp_path)
    calls: list[tuple[Path, str]] = []

    def fake_refresh(
        repo_root: Path, *, tag: str, views_before: dict[str, dict[str, str]] | None = None
    ) -> None:
        calls.append((repo_root, tag))

    monkeypatch.setattr(artifacts, "ensure_runtime_deps", lambda _r: [])
    monkeypatch.setattr(artifacts, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(
        artifacts.subprocess, "run", lambda cmd, **_: subprocess.CompletedProcess(list(cmd), 0)
    )
    monkeypatch.setattr(artifacts.stamps, "refresh_after_regen", fake_refresh)

    assert artifacts.generate(tmp_path, only=["graphml"]) == 0

    assert calls == [(tmp_path, "kb-artifacts")]


def test_the_views_snapshot_is_taken_before_the_generators_run(tmp_path: Path, monkeypatch) -> None:
    """The bracket, pinned by ORDER (#182) — this replaced a boolean that was unsound.

    `generate` used to assert "I regenerated everything" with a flag. A cold review
    showed that certifies views whose bytes changed at some earlier, unobserved
    moment (`sync.view_records` carries the reproduction). The snapshot fixes it
    ONLY if it is taken before the generators run — taken after, it would compare
    the new bytes against themselves and certify nothing, and taken from the last
    stamp it would be the unsound version again.

    Asserted by call order rather than by outcome, because reading the stamp after
    `generate` returns reflects the final state either way. `views_before is not
    None` is the second half: passing None is the documented "I cannot say what I
    regenerated", which would silently stop certifying anything at all.
    """
    _graph_with_hyperedge(tmp_path)
    order: list[str] = []
    handed: list[object] = []

    def fake_snapshot(_repo_root: Path) -> dict[str, dict[str, str]]:
        order.append("snapshot")
        return {"graphify": {}}

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        order.append("generate")
        return subprocess.CompletedProcess(list(cmd), 0)

    def fake_refresh(
        _repo_root: Path, *, tag: str, views_before: dict[str, dict[str, str]] | None = None
    ) -> None:
        order.append("refresh")
        handed.append(views_before)

    monkeypatch.setattr(artifacts, "ensure_runtime_deps", lambda _r: [])
    monkeypatch.setattr(artifacts, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(artifacts.subprocess, "run", fake_run)
    monkeypatch.setattr(artifacts.stamps, "snapshot_views", fake_snapshot)
    monkeypatch.setattr(artifacts.stamps, "refresh_after_regen", fake_refresh)

    assert artifacts.generate(tmp_path, only=["graphml"]) == 0

    assert order == ["snapshot", "generate", "refresh"], f"bracket is wrong: {order}"
    assert handed == [{"graphify": {}}]


def test_generate_does_not_refresh_the_stamp_on_failure(tmp_path: Path, monkeypatch) -> None:
    """CONTROL ARM: a failed `generate()` run must not restamp anything.

    Same reasoning as the `label()` failure gate: an artifact that failed to
    regenerate may be in any state, and stamping it would assert "this is
    current" about output that is not.
    """
    _graph_with_hyperedge(tmp_path)
    calls: list[tuple[Path, str]] = []

    def fake_refresh(repo_root: Path, *, tag: str, regenerated_views: bool = False) -> None:
        assert not regenerated_views
        calls.append((repo_root, tag))

    monkeypatch.setattr(artifacts, "ensure_runtime_deps", lambda _r: [])
    monkeypatch.setattr(artifacts, "graphify_exe", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(
        artifacts.subprocess, "run", lambda cmd, **_: subprocess.CompletedProcess(list(cmd), 1)
    )
    monkeypatch.setattr(artifacts.stamps, "refresh_after_regen", fake_refresh)

    assert artifacts.generate(tmp_path, only=["graphml"]) == 1

    assert calls == []
