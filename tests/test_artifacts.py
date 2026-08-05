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
