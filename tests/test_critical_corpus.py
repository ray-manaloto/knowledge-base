# Copyright (c) 2026 Raymond Manaloto
"""Bounded critical-dependency corpus controls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import critical_corpus


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "sources/alpha").mkdir(parents=True)
    (tmp_path / "sources/beta").mkdir()
    (tmp_path / "sources/alpha.manifest").write_text(
        "url = 'https://alpha.invalid'\nref = 'v1'\ncommit = 'abc'\n", encoding="utf-8"
    )
    (tmp_path / "sources/beta.manifest").write_text(
        "url = 'https://beta.invalid'\nref = 'v2'\ncommit = 'def'\n", encoding="utf-8"
    )
    (tmp_path / "sources/alpha/main.py").write_text(
        "def alpha():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "sources/alpha/README.md").write_text("# Alpha\n", encoding="utf-8")
    (tmp_path / "sources/beta/main.py").write_text("def beta():\n    return 2\n", encoding="utf-8")
    (tmp_path / "sources/critical-corpus.toml").write_text(
        "graphify_version = '0.9.39'\n"
        "[[dependency]]\nname = 'alpha'\nmanifest = 'sources/alpha.manifest'\n"
        "code = ['sources/alpha/main.py']\n"
        "documents = ['sources/alpha/README.md']\n"
        "depends_on = []\n"
        "[[dependency]]\nname = 'beta'\nmanifest = 'sources/beta.manifest'\n"
        "code = ['sources/beta/main.py']\ndocuments = []\n"
        "depends_on = ['alpha']\n",
        encoding="utf-8",
    )
    return tmp_path


def test_config_is_bounded_and_rejects_unknown_dependency(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    version, dependencies = critical_corpus.load_config(repo)
    assert version == "0.9.39"
    assert [item.name for item in dependencies] == ["alpha", "beta"]
    config = repo / "sources/critical-corpus.toml"
    config.write_text(config.read_text().replace("['alpha']", "['missing']"), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown dependency targets"):
        critical_corpus.load_config(repo)


def test_repository_config_lists_the_approved_critical_dependencies() -> None:
    repo = Path(__file__).parents[1]
    version, dependencies = critical_corpus.load_config(repo)
    assert version == "0.9.40"
    assert {item.name for item in dependencies} == {
        "agnix",
        "chezmoi",
        "claude-code",
        "codex",
        "graphify",
        "hk",
        "mattpocock-skills",
        "mise",
        "ruff",
        "ty",
        "uv",
    }
    assert sum(len(item.code) for item in dependencies) == 18
    assert sum(len(item.documents) for item in dependencies) == 25


def test_materialize_copies_only_selected_files_and_hashes_full_bytes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _version, dependencies = critical_corpus.load_config(repo)
    output = repo / "graphify-out/critical"
    inventory = critical_corpus._materialize(repo, output, dependencies)
    assert (output / "corpus/alpha/main.py").is_file()
    assert (output / "corpus/alpha/README.md").is_file()
    assert len(list((output / "corpus").rglob("*.*"))) == 3
    receipt = inventory["dependencies"][0]["documents"][0]
    assert receipt["bytes"] == len(b"# Alpha\n")
    assert len(receipt["sha256"]) == 64


def test_overlay_keeps_canonical_dependencies_out_of_god_nodes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _version, dependencies = critical_corpus.load_config(repo)
    output = repo / "graphify-out/critical"
    output.mkdir(parents=True)
    graph = output / "graph.json"
    graph.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "alpha-file",
                        "label": "main.py",
                        "source_file": "alpha/main.py",
                        "file_type": "code",
                        "source_location": "L1",
                    }
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )
    missing = critical_corpus._write_overlay(output, dependencies, graph)
    overlay = json.loads((output / "dependency-overlay.json").read_text())
    assert overlay["god_node_eligible"] is False
    assert all(node["god_node_eligible"] is False for node in overlay["nodes"])
    assert "degree" not in overlay["nodes"][0]
    assert {link["relation"] for link in overlay["links"]} == {"DEPENDS_ON", "SOURCE"}
    assert missing == ("beta/main.py",)
    assert overlay["unanchored_code_files"] == ["beta/main.py"]


def test_remote_openai_backend_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KB_CRITICAL_LOCAL_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    with pytest.raises(ValueError, match="localhost"):
        critical_corpus._local_backend()


def test_build_is_red_when_no_local_semantic_model_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = _repo(tmp_path)
    graph_dir = repo / "graphify-out/critical/graphify-out"

    monkeypatch.setattr(critical_corpus, "assert_pinned_graphify", lambda _root: None)
    monkeypatch.setattr(critical_corpus, "graphify_exe", lambda _root: "/graphify")
    monkeypatch.setattr(critical_corpus, "running_graphify_version", lambda _exe: "0.9.39")
    monkeypatch.setattr(critical_corpus, "_local_backend", lambda: (None, {}))

    def fake_extract(_root: Path, output: Path, _backend: str | None, _extra: object) -> str:
        graph_dir.mkdir(parents=True)
        (graph_dir / "graph.json").write_text(
            json.dumps({"nodes": [{"id": "n"}], "links": []}), encoding="utf-8"
        )
        return "BLOCKED_NO_LOCAL_MODEL"

    monkeypatch.setattr(critical_corpus, "_run_extract", fake_extract)
    monkeypatch.setattr(critical_corpus, "_sdk_control", lambda *_args: (1, 0))
    monkeypatch.setattr(critical_corpus, "_artifacts", lambda *_args: ("html", "wiki"))
    monkeypatch.setattr(critical_corpus, "_learning", lambda *_args: None)
    assert critical_corpus.build(repo) == 1
    result = json.loads((repo / "graphify-out/critical/build-result.json").read_text())
    assert result["status"] == "RED"
    assert result["semantic_status"] == "BLOCKED_NO_LOCAL_MODEL"
    assert not (repo / "graphify-out/critical/corpus").exists()


def test_cli_dispatches_critical_corpus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from kb_setup import cli

    called: list[list[str]] = []
    monkeypatch.setattr(
        critical_corpus, "build", lambda _root, rest: (called.append(list(rest)), 7)[1]
    )
    monkeypatch.setattr("kb_setup.graphify_env.assert_pinned_graphify", lambda _root: None)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["critical-corpus"]) == 7
    assert called == [[]]
