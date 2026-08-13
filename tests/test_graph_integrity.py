# Copyright (c) 2026 Raymond Manaloto
"""Typed dependency anchors and Graphify limit semantics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import graph_integrity
from kb_setup.currency import config as currency_config


def _repo(tmp_path: Path, *, cross_link: bool) -> Path:
    (tmp_path / "graphify-out").mkdir(parents=True)
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/a.manifest").write_text("url = 'https://a.invalid'\n", encoding="utf-8")
    (tmp_path / "sources/b.manifest").write_text("url = 'https://b.invalid'\n", encoding="utf-8")
    (tmp_path / "currency.toml").write_text(
        "[tool.a]\nmanifest = 'sources/a.manifest'\n[tool.b]\nmanifest = 'sources/b.manifest'\n",
        encoding="utf-8",
    )
    links = [{"source": "a1", "target": "b1", "confidence": "INFERRED"}] if cross_link else []
    graph = {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": [
            {"id": "a1", "repo": "a", "source_file": "a/main.py"},
            {"id": "a2", "repo": "a", "source_file": "a/README.md"},
            {"id": "b1", "repo": "b", "source_file": "b/main.py"},
        ],
        "links": links,
        "hyperedges": [],
    }
    (tmp_path / "graphify-out/graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return tmp_path


def test_limit_classifier_keeps_query_budget_separate_from_environment() -> None:
    limits = graph_integrity.classify_limits(
        query_budget=7_000,
        env={
            "GRAPHIFY_MAX_OUTPUT_TOKENS": "9000",
            "GRAPHIFY_MAX_GRAPH_BYTES": "1GB",
            "GRAPHIFY_MAX_CONTEXTS": "16",
        },
    )
    assert limits.query_output_tokens == 7_000
    assert limits.semantic_llm_output_tokens == 9_000
    assert limits.graph_load_bytes == 1024**3
    assert limits.mcp_project_contexts == 16


def test_invalid_environment_values_use_graphify_defaults() -> None:
    limits = graph_integrity.classify_limits(
        env={
            "GRAPHIFY_MAX_OUTPUT_TOKENS": "bad",
            "GRAPHIFY_MAX_GRAPH_BYTES": "bad",
            "GRAPHIFY_MAX_CONTEXTS": "0",
        }
    )
    assert limits.semantic_llm_output_tokens is None
    assert limits.graph_load_bytes == 512 * 1024 * 1024
    assert limits.mcp_project_contexts == 1
    assert (
        graph_integrity.classify_limits(env={"GRAPHIFY_MAX_CONTEXTS": "bad"}).mcp_project_contexts
        == 8
    )


def test_anchors_are_typed_ranked_without_degree_and_excluded_from_gods(tmp_path: Path) -> None:
    audit = graph_integrity.audit_anchors(_repo(tmp_path, cross_link=True))
    assert [anchor.name for anchor in audit.anchors] == ["a", "b"]
    assert audit.anchors[0].type == "canonical_dependency"
    assert audit.anchors[0].graph_nodes == 2
    assert audit.anchors[0].source_receipts == 2
    assert audit.anchors[0].source_coverage[0].prefix == "repo:a"
    assert audit.anchors[0].source_coverage[0].graph_nodes == 2
    assert audit.anchors[0].god_node_eligible is False
    assert "degree" not in audit.anchors[0].__dataclass_fields__


def test_offline_harness_docs_attach_once_to_the_right_anchor(tmp_path: Path) -> None:
    repo = _repo(tmp_path, cross_link=True)
    (repo / "currency.toml").write_text(
        "[tool.codex]\nmanifest = 'sources/codex.manifest'\n"
        "anchor_source_prefixes = ['agent-harness-docs/docs/codex/']\n"
        "[tool.claude-code]\nmanifest = 'sources/claude-code.manifest'\n"
        "anchor_source_prefixes = ['agent-harness-docs/docs/claude-code/']\n",
        encoding="utf-8",
    )
    graph = json.loads((repo / "graphify-out/graph.json").read_text(encoding="utf-8"))
    graph["nodes"] = [
        {
            "id": "codex-repo",
            "repo": "codex",
            "source_file": "codex/codex-rs/lib.rs",
        },
        {
            "id": "codex-doc",
            "source_file": "agent-harness-docs/docs/codex/hooks.md",
        },
        {
            "id": "claude-doc",
            "source_file": "agent-harness-docs/docs/claude-code/hooks.md",
        },
    ]
    graph["links"] = [{"source": "codex-doc", "target": "claude-doc", "confidence": "INFERRED"}]
    (repo / "graphify-out/graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")

    audit = graph_integrity.audit_anchors(repo)
    by_name = {anchor.name: anchor for anchor in audit.anchors}
    assert by_name["codex"].graph_nodes == 2
    assert by_name["claude-code"].graph_nodes == 1
    codex_coverage = {
        source.prefix: source.graph_nodes for source in by_name["codex"].source_coverage
    }
    assert codex_coverage == {
        "repo:codex": 1,
        "agent-harness-docs/docs/codex/": 1,
    }
    claude_coverage = {
        source.prefix: source.graph_nodes for source in by_name["claude-code"].source_coverage
    }
    assert claude_coverage == {
        "repo:claude-code": 0,
        "agent-harness-docs/docs/claude-code/": 1,
    }
    assert sum(anchor.graph_nodes for anchor in audit.anchors) == 3
    assert audit.cross_dependency_edges == 1
    assert audit.missing_sources == ("claude-code:repo:claude-code",)


def test_overlapping_anchor_attribution_is_refused(tmp_path: Path) -> None:
    repo = _repo(tmp_path, cross_link=False)
    (repo / "currency.toml").write_text(
        "[tool.a]\nmanifest = 'sources/a.manifest'\n"
        "anchor_source_prefixes = ['shared/']\n"
        "[tool.b]\nmanifest = 'sources/b.manifest'\n"
        "anchor_source_prefixes = ['shared/']\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="overlap"):
        graph_integrity.audit_anchors(repo)


def test_cross_dependency_reach_has_positive_and_negative_arms(tmp_path: Path) -> None:
    linked = graph_integrity.audit_anchors(_repo(tmp_path / "linked", cross_link=True))
    isolated = graph_integrity.audit_anchors(_repo(tmp_path / "isolated", cross_link=False))
    assert linked.cross_dependency_edges == 1
    assert linked.anchors[0].project_reach
    assert linked.red is False
    assert isolated.cross_dependency_edges == 0
    assert all(not anchor.project_reach for anchor in isolated.anchors)
    assert isolated.red is True


def test_report_writes_typed_artifact_and_returns_red_for_islands(tmp_path: Path) -> None:
    repo = _repo(tmp_path, cross_link=False)
    assert graph_integrity.report(repo) == 1
    artifact = json.loads((repo / "graphify-out/dependency-anchors.json").read_text())
    assert artifact["status"] == "RED"
    assert artifact["anchor_type"] == "canonical_dependency"
    assert artifact["god_node_eligible"] is False
    assert artifact["ranking"] == ["graph_nodes", "source_receipts", "project_reach"]


def test_report_rejects_bad_query_budget(tmp_path: Path) -> None:
    assert graph_integrity.report(_repo(tmp_path, cross_link=True), ["--query-budget", "x"]) == 2


def test_cli_dispatches_graph_integrity(monkeypatch, tmp_path: Path) -> None:
    """Deleting the real dispatch must make the test fail."""
    from kb_setup import cli

    called: list[list[str]] = []
    monkeypatch.setattr(
        graph_integrity,
        "report",
        lambda _root, rest: (called.append(list(rest)), 0)[1],
    )
    monkeypatch.chdir(tmp_path)
    assert cli.main(["graph-integrity", "--query-budget", "4000"]) == 0
    assert called == [["--query-budget", "4000"]]


def test_repo_declares_mattpocock_skills_as_source_only() -> None:
    repo_root = Path(__file__).parents[1]
    specs = {spec.name: spec for spec in currency_config.load(repo_root)}
    matt = specs["mattpocock-skills"]
    assert matt.source_only is True
    assert matt.github == "mattpocock/skills"
    assert matt.manifest == "sources/mattpocock-skills.manifest"
