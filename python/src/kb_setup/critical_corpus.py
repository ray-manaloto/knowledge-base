# Copyright (c) 2026 Raymond Manaloto
"""Build the bounded critical-dependency graph without touching the aggregate.

The committed TOML is the selection policy.  This module materializes only those
files below ``graphify-out/critical/``, exercises both Graphify's CLI and public
AST SDK, optionally performs semantic ``--mode deep`` extraction through an
explicit local backend, and then generates the navigational/learning artifacts.

Canonical dependency nodes are an overlay, not synthetic god nodes.  The overlay
records only relationships declared in the TOML or exact file membership; it is
written beside the untouched Graphify graph so structural rankings remain honest.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kb_setup import manifest as source_manifest
from kb_setup.graphify_env import (
    assert_pinned_graphify,
    clean_env,
    graphify_exe,
    graphify_python,
    running_graphify_version,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_CONFIG = "sources/critical-corpus.toml"
_OUTPUT = "graphify-out/critical"
_LOCAL_BACKENDS = frozenset({"ollama", "openai"})


@dataclass(frozen=True)
class Dependency:
    """One bounded critical-source slice."""

    name: str
    manifest: str
    code: tuple[str, ...]
    documents: tuple[str, ...]
    coverage_only: tuple[str, ...]
    depends_on: tuple[str, ...]


@dataclass(frozen=True)
class BuildResult:
    """Machine-readable result; blocked semantic work is never rendered green."""

    graphify_version: str
    dependencies: int
    code_files: int
    document_files: int
    coverage_files: int
    cli_nodes: int
    sdk_nodes: int
    cli_edges: int
    sdk_edges: int
    unanchored_code_files: tuple[str, ...]
    semantic_status: str
    semantic_backend: str | None
    artifacts: tuple[str, ...]
    status: str


def _strings(raw: object, field: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError(f"{field} must be an array of strings")
    return tuple(raw)


def load_config(repo_root: Path) -> tuple[str, tuple[Dependency, ...]]:
    """Load and validate the committed bounded-corpus policy."""
    with (repo_root / _CONFIG).open("rb") as fh:
        data = tomllib.load(fh)
    version = data.get("graphify_version")
    if not isinstance(version, str) or not version:
        raise ValueError("critical corpus requires graphify_version")
    rows = data.get("dependency")
    if not isinstance(rows, list) or not rows:
        raise ValueError("critical corpus requires at least one dependency")
    dependencies: list[Dependency] = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise TypeError(f"dependency {index} must be a table")
        name, manifest = raw.get("name"), raw.get("manifest")
        if not isinstance(name, str) or not name:
            raise ValueError(f"dependency {index} has no name")
        if not isinstance(manifest, str) or not manifest:
            raise ValueError(f"dependency {name} has no manifest")
        dependencies.append(
            Dependency(
                name=name,
                manifest=manifest,
                code=_strings(raw.get("code"), f"{name}.code"),
                documents=_strings(raw.get("documents"), f"{name}.documents"),
                coverage_only=_strings(raw.get("coverage_only"), f"{name}.coverage_only"),
                depends_on=_strings(raw.get("depends_on"), f"{name}.depends_on"),
            )
        )
    names = [item.name for item in dependencies]
    if len(names) != len(set(names)):
        raise ValueError("critical dependency names must be unique")
    unknown = sorted({target for item in dependencies for target in item.depends_on} - set(names))
    if unknown:
        raise ValueError(f"unknown dependency targets: {', '.join(unknown)}")
    return version, tuple(dependencies)


def _manifest_pin(path: Path) -> dict[str, str]:
    parsed = source_manifest.load(path)
    return {"url": parsed.url, "ref": parsed.ref, "commit": parsed.commit}


def _source_path(repo_root: Path, raw: str) -> Path:
    path = (repo_root / raw).resolve()
    if not path.is_relative_to(repo_root.resolve()):
        raise ValueError(f"critical source escapes repository: {raw}")
    if not path.is_file():
        raise ValueError(f"critical source missing: {raw}")
    return path


def _materialize(
    repo_root: Path, output: Path, dependencies: Sequence[Dependency]
) -> dict[str, Any]:
    """Copy only selected inputs and record full-file hashes for cutoff proof."""
    corpus = output / "corpus"
    corpus.mkdir(parents=True)
    inventory: dict[str, Any] = {"dependencies": []}
    for dep in dependencies:
        row: dict[str, Any] = {
            "name": dep.name,
            "manifest": dep.manifest,
            "pin": _manifest_pin(_source_path(repo_root, dep.manifest)),
            "code": [],
            "documents": [],
            "coverage_only": [],
            "depends_on": list(dep.depends_on),
        }
        for kind, paths in (("code", dep.code), ("documents", dep.documents)):
            for raw in paths:
                source = _source_path(repo_root, raw)
                relative = Path(raw).relative_to("sources")
                target = corpus / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                row[kind].append(_receipt(source, repo_root))
        for raw in dep.coverage_only:
            row["coverage_only"].append(_receipt(_source_path(repo_root, raw), repo_root))
        inventory["dependencies"].append(row)
    (output / "inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return inventory


def _receipt(path: Path, repo_root: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {
        "path": str(path.relative_to(repo_root)),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _run(cmd: Sequence[str], *, cwd: Path, env: Mapping[str, str] | None = None) -> int:
    shown = list(cmd)
    if "-c" in shown:
        code_index = shown.index("-c") + 1
        if code_index < len(shown):
            shown[code_index] = "<inline Graphify SDK control>"
    print(f"  $ {' '.join(shown)}")
    return subprocess.run(list(cmd), cwd=cwd, env=dict(env or clean_env()), check=False).returncode


def _graph_path(output: Path) -> Path:
    graph = output / "graphify-out" / "graph.json"
    if not graph.is_file():
        raise ValueError(f"Graphify produced no graph: {graph}")
    return graph


def _counts(graph: Path) -> tuple[int, int]:
    data = json.loads(graph.read_text(encoding="utf-8"))
    return len(data.get("nodes", [])), len(data.get("links", []))


_SDK_PROBE = """
import json
from pathlib import Path
from graphify.build import build
from graphify.extract import extract

request = json.loads(Path(__import__('sys').argv[1]).read_text(encoding='utf-8'))
paths = [Path(item) for item in request['paths']]
result = extract(
    paths,
    cache_root=Path(request['cache']),
    root=Path(request['root']),
    parallel=False,
)
graph = build([result], root=Path(request['root']), directed=False)
Path(request['output']).write_text(
    json.dumps(
        {
            'nodes': graph.number_of_nodes(),
            'edges': graph.number_of_edges(),
            'raw_nodes': len(result.get('nodes', [])),
            'raw_edges': len(result.get('edges', [])),
        },
        indent=2,
    ),
    encoding='utf-8',
)
""".strip()


def _sdk_control(repo_root: Path, output: Path, inventory: Mapping[str, Any]) -> tuple[int, int]:
    corpus = output / "corpus"
    paths = [
        str(corpus / Path(receipt["path"]).relative_to("sources"))
        for dep in inventory["dependencies"]
        for receipt in dep["code"]
    ]
    request = output / "sdk-request.json"
    result = output / "sdk-control.json"
    request.write_text(
        json.dumps(
            {
                "paths": paths,
                "cache": str(output / "sdk-cache"),
                "root": str(corpus),
                "output": str(result),
            }
        ),
        encoding="utf-8",
    )
    rc = _run([graphify_python(repo_root), "-c", _SDK_PROBE, str(request)], cwd=repo_root)
    request.unlink(missing_ok=True)
    if rc != 0 or not result.is_file():
        raise ValueError(f"Graphify public SDK control failed (rc={rc})")
    return _counts_extraction(result)


def _counts_extraction(path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return int(data.get("nodes", 0)), int(data.get("edges", 0))


def _local_backend() -> tuple[str | None, dict[str, str]]:
    backend = os.environ.get("KB_CRITICAL_LOCAL_BACKEND", "").strip().lower()
    if not backend:
        return None, {}
    if backend not in _LOCAL_BACKENDS:
        raise ValueError("KB_CRITICAL_LOCAL_BACKEND must be ollama or openai")
    extra: dict[str, str] = {}
    if backend == "openai":
        base = os.environ.get("OPENAI_BASE_URL", "").strip()
        if not base.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("openai deep extraction requires a localhost OPENAI_BASE_URL")
        extra["OPENAI_BASE_URL"] = base
        if model := os.environ.get("OPENAI_MODEL", "").strip():
            extra["OPENAI_MODEL"] = model
    return backend, extra


def _run_extract(
    repo_root: Path, output: Path, backend: str | None, extra: Mapping[str, str]
) -> str:
    exe = graphify_exe(repo_root)
    corpus = output / "corpus"
    base = [exe, "extract", str(corpus), "--force", "--max-workers", "1", "--out", str(output)]
    if backend is None:
        rc = _run([*base, "--code-only"], cwd=repo_root)
        if rc != 0:
            raise ValueError(f"Graphify CLI AST extraction failed (rc={rc})")
        return "BLOCKED_NO_LOCAL_MODEL"
    rc = _run(
        [*base, "--backend", backend, "--mode", "deep", "--max-concurrency", "1"],
        cwd=repo_root,
        env=clean_env(dict(extra)),
    )
    if rc != 0:
        raise ValueError(f"Graphify local deep extraction failed (backend={backend}, rc={rc})")
    return "COMPLETE"


def _write_overlay(
    output: Path, dependencies: Sequence[Dependency], graph: Path
) -> tuple[str, ...]:
    data = json.loads(graph.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    file_nodes = {
        str(node.get("source_file")): str(node.get("id")) for node in nodes if _is_file_node(node)
    }
    anchors = [
        {
            "id": f"critical-dependency:{dep.name}",
            "label": dep.name,
            "type": "canonical_dependency",
            "god_node_eligible": False,
            "manifest": dep.manifest,
        }
        for dep in dependencies
    ]
    links: list[dict[str, str]] = []
    for dep in dependencies:
        anchor = f"critical-dependency:{dep.name}"
        links.extend(
            {
                "source": anchor,
                "target": f"critical-dependency:{target}",
                "relation": "DEPENDS_ON",
                "confidence": "EXTRACTED",
            }
            for target in dep.depends_on
        )
        links.extend(
            {
                "source": anchor,
                "target": node_id,
                "relation": "SOURCE",
                "confidence": "EXTRACTED",
            }
            for source_file, node_id in file_nodes.items()
            if source_file.startswith(f"{dep.name}/")
        )
    expected = {str(Path(raw).relative_to("sources")) for dep in dependencies for raw in dep.code}
    missing = tuple(sorted(expected - file_nodes.keys()))
    overlay = {
        "nodes": anchors,
        "links": links,
        "god_node_eligible": False,
        "unanchored_code_files": missing,
    }
    (output / "dependency-overlay.json").write_text(
        json.dumps(overlay, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    combined = dict(data)
    combined["nodes"] = [*nodes, *anchors]
    combined["links"] = [*data.get("links", []), *links]
    (output / "graph-with-anchors.json").write_text(
        json.dumps(combined, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return missing


def _is_file_node(node: Mapping[str, object]) -> bool:
    """Recognize Graphify file nodes before or after basename disambiguation."""
    source, label = node.get("source_file"), node.get("label")
    return (
        node.get("source_location") == "L1"
        and bool(node.get("id"))
        and isinstance(source, str)
        and isinstance(label, str)
        and (label == Path(source).name or source.endswith(f"/{label}"))
    )


def _artifacts(repo_root: Path, output: Path) -> tuple[str, ...]:
    exe = graphify_exe(repo_root)
    commands = (
        ("report", ["cluster-only", ".", "--no-label", "--no-viz"]),
        ("tree", ["tree"]),
        ("html", ["export", "html"]),
        ("wiki", ["export", "wiki"]),
        ("graphml", ["export", "graphml"]),
        ("cypher", ["export", "neo4j"]),
        ("callflow", ["export", "callflow-html"]),
    )
    complete: list[str] = []
    diagnostics = subprocess.run(
        [exe, "diagnose", "multigraph", "--graph", "graphify-out/graph.json", "--json"],
        cwd=output,
        env=clean_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"  $ {exe} diagnose multigraph --graph graphify-out/graph.json --json")
    if diagnostics.returncode == 0:
        (output / "graphify-out" / "diagnostics.json").write_text(
            diagnostics.stdout, encoding="utf-8"
        )
        complete.append("diagnostics")
    for name, args in commands:
        if _run([exe, *args], cwd=output) == 0:
            complete.append(name)
    return tuple(complete)


def _learning(repo_root: Path, output: Path, result: BuildResult) -> None:
    exe = graphify_exe(repo_root)
    memory = output / "graphify-out" / "memory"
    graph = _graph_path(output)
    answer = (
        f"Focused critical corpus {result.status}: {result.dependencies} dependencies, "
        f"{result.cli_nodes} CLI nodes, semantic={result.semantic_status}."
    )
    _run(
        [
            exe,
            "save-result",
            "--question",
            "Did the focused critical-dependency corpus build with local deep extraction?",
            "--answer",
            answer,
            "--outcome",
            "useful" if result.status == "GREEN" else "dead_end",
            "--memory-dir",
            str(memory),
        ],
        cwd=repo_root,
    )
    _run(
        [
            exe,
            "reflect",
            "--memory-dir",
            str(memory),
            "--out",
            str(output / "graphify-out" / "reflections" / "LESSONS.md"),
            "--graph",
            str(graph),
        ],
        cwd=repo_root,
    )


def build(repo_root: Path, argv: Sequence[str] = ()) -> int:
    """Build the isolated corpus and return red until local deep extraction succeeds."""
    if argv:
        print("kb-setup critical-corpus takes no arguments")
        return 2
    expected, dependencies = load_config(repo_root)
    assert_pinned_graphify(repo_root)
    exe = graphify_exe(repo_root)
    actual = running_graphify_version(exe)
    if actual != expected:
        raise ValueError(f"critical corpus requires Graphify {expected}, got {actual or 'unknown'}")
    output = repo_root / _OUTPUT
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    inventory = _materialize(repo_root, output, dependencies)
    backend, extra = _local_backend()
    semantic = _run_extract(repo_root, output, backend, extra)
    graph = _graph_path(output)
    cli_nodes, cli_edges = _counts(graph)
    sdk_nodes, sdk_edges = _sdk_control(repo_root, output, inventory)
    if (cli_nodes, cli_edges) != (sdk_nodes, sdk_edges):
        raise ValueError(
            "Graphify CLI/SDK AST controls disagree: "
            f"cli={cli_nodes}/{cli_edges}, sdk={sdk_nodes}/{sdk_edges}"
        )
    unanchored = _write_overlay(output, dependencies, graph)
    generated = _artifacts(repo_root, output)
    result = BuildResult(
        graphify_version=actual,
        dependencies=len(dependencies),
        code_files=sum(len(dep.code) for dep in dependencies),
        document_files=sum(len(dep.documents) for dep in dependencies),
        coverage_files=sum(len(dep.coverage_only) for dep in dependencies),
        cli_nodes=cli_nodes,
        sdk_nodes=sdk_nodes,
        cli_edges=cli_edges,
        sdk_edges=sdk_edges,
        unanchored_code_files=unanchored,
        semantic_status=semantic,
        semantic_backend=backend,
        artifacts=generated,
        status="GREEN" if semantic == "COMPLETE" and not unanchored else "RED",
    )
    # The mirrored source tree is an ephemeral build input. Keeping it makes the
    # repo lint gate scan third-party changelogs, generated fixtures, and large
    # source files after every critical run. The receipts and graph artifacts
    # above are the durable evidence; remove only this task-owned mirror.
    corpus = output / "corpus"
    if corpus.exists():
        shutil.rmtree(corpus)
    (output / "build-result.json").write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _learning(repo_root, output, result)
    print(
        f"[critical-corpus] {result.status}: {result.dependencies} dependencies; "
        f"CLI/SDK={cli_nodes}/{cli_edges}; semantic={semantic}; "
        f"artifacts={','.join(generated) or 'none'}"
    )
    return 0 if result.status == "GREEN" else 1
