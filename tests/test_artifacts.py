"""kb-artifacts helpers: node counting + the large-graph svg skip."""

import json
import subprocess
from pathlib import Path

from kb_setup import artifacts, hyperedges


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


def test_restamp_survives_a_malformed_currency_config(tmp_path) -> None:
    """A broken currency.toml must not turn a successful kb-artifacts into a failure.

    `config.load()` raises TypeError (not ValueError) when `[tool]` is not a
    table; `_restamp` is best-effort and must swallow it with a warning.
    """
    (tmp_path / "currency.toml").write_text('tool = "not a table"\n', encoding="utf-8")
    # Must not raise — the guarantee _restamp documents.
    artifacts._restamp(tmp_path)


def test_restamp_is_a_noop_without_a_config(tmp_path) -> None:
    """Control arm: a repo with no currency.toml re-stamps nothing, cleanly."""
    artifacts._restamp(tmp_path)


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
