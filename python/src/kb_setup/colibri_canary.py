# Copyright (c) 2026 Raymond Manaloto
"""Run a bounded real Colibri model -> Graphify deep-extraction canary."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, TypedDict
from urllib.parse import urlsplit

from kb_setup import artifact_download
from kb_setup.graphify_env import clean_env, graphify_exe

_COLIBRI_REPO = "https://github.com/JustVugg/colibri.git"
_COLIBRI_COMMIT = "2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b"
_SERVER_START_TIMEOUT_SECONDS = 300
_FIXTURE = """# Dependency workflow

The knowledge-base project owns verified dependency research. Dotfiles consumes
that research through a project-scoped plugin. Graphify 0.9.39 extracts a graph
from the selected source documents. A currency task reviews release notes before
changing a dependency pin. The verification gate compares Graphify CLI output
with its public Python SDK and refuses to publish stale artifacts.
"""
_ModelName = Literal["olmoe", "glm52"]


@dataclass(frozen=True)
class _ModelConfig:
    name: _ModelName
    repo_id: str
    revision: str
    model_id: str
    build_target: str
    preparation: str
    server_env: tuple[tuple[str, str], ...]
    server_args: tuple[str, ...] = ()


_MODEL_CONFIGS: dict[_ModelName, _ModelConfig] = {
    "olmoe": _ModelConfig(
        name="olmoe",
        repo_id="allenai/OLMoE-1B-7B-0125-Instruct",
        revision="b89a7c4bc24fb9e55ce2543c9458ce0ca5c4650e",
        model_id="olmoe-colibri",
        build_target="olmoe",
        preparation="download-source-and-convert",
        server_env=(("NOGPU", "1"),),
    ),
    "glm52": _ModelConfig(
        name="glm52",
        repo_id="mastouri/GLM-5.2-colibri-int4-g64-with-int8-mtp",
        # Hugging Face model API `sha`, verified 2026-08-11. Never use `main`.
        revision="fd9b461ac7cae4b921470d0db12230c6505bd03c",
        model_id="glm52-colibri",
        build_target="glm",
        preparation="download-ready-container",
        server_env=(
            ("NOGPU", "1"),
            ("COLI_METAL", "0"),
            ("COLI_VULKAN", "0"),
            ("MTP", "0"),
            ("KV_SLOTS", "1"),
            ("KVSAVE", "0"),
            ("COLI_TEMP", "0"),
            ("SEED", "0"),
        ),
        server_args=("--kv-slots", "1"),
    ),
}


class _SemanticScore(TypedDict):
    required_concepts: list[str]
    found_concepts: list[str]
    missing_concepts: list[str]
    expected_edge_signatures: list[str]
    found_edge_signatures: list[str]
    passes: bool


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def _head_commit(source: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _require_pinned_source(source: Path) -> Path:
    commit = _head_commit(source)
    if commit != _COLIBRI_COMMIT:
        raise ValueError(f"Colibri source must be pinned to {_COLIBRI_COMMIT}; got {commit}")
    return source


def _source_checkout(source: Path | None, work: Path) -> Path:
    """Use an explicit pinned checkout or create one at the one allowed commit."""
    if source is not None:
        return _require_pinned_source(source.resolve())

    checkout = work / "colibri-source"
    if checkout.exists():
        return _require_pinned_source(checkout)

    checkout.mkdir(parents=True)
    _run(["git", "init"], cwd=checkout)
    _run(["git", "remote", "add", "origin", _COLIBRI_REPO], cwd=checkout)
    _run(["git", "fetch", "--depth", "1", "origin", _COLIBRI_COMMIT], cwd=checkout)
    _run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=checkout)
    return _require_pinned_source(checkout)


def _request(url: str, *, payload: dict[str, object] | None = None) -> dict[str, object]:
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Colibri canary requests must stay on loopback HTTP")
    body = None if payload is None else json.dumps(payload).encode()
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=15)
    connection.request(
        "GET" if body is None else "POST",
        parsed.path,
        body=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
    )
    response = connection.getresponse()
    value = json.loads(response.read())
    connection.close()
    if not isinstance(value, dict):
        raise TypeError("Colibri returned a non-object response")
    return value


def _wait_for_server(base_url: str, process: subprocess.Popen[str]) -> float:
    started = time.monotonic()
    while time.monotonic() - started < _SERVER_START_TIMEOUT_SECONDS:
        if process.poll() is not None:
            raise RuntimeError(f"Colibri server exited during startup (rc={process.returncode})")
        try:
            _request(f"{base_url}/models")
            return time.monotonic() - started
        except OSError, json.JSONDecodeError:
            time.sleep(1)
    raise TimeoutError("Colibri server did not become ready within 300 seconds")


def _counts(graph_path: Path) -> tuple[int, int]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    return len(graph.get("nodes", [])), len(graph.get("links", []))


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _semantic_score(graph_path: Path) -> _SemanticScore:
    """Score the frozen fixture without treating a nonempty graph as quality."""
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    labels = {str(node.get("label", "")).casefold() for node in graph.get("nodes", [])}
    required = {
        "knowledge base",
        "dotfiles",
        "graphify",
        "currency task",
        "release notes",
        "verification gate",
        "cli",
        "python sdk",
    }
    expected_edges = {
        ("dotfiles", "consumes", "knowledge base"),
        ("graphify", "extracts", "graph"),
        ("currency task", "reviews", "release notes"),
        ("verification gate", "compares", "cli"),
    }
    observed_edges = {
        (
            str(edge.get("source", "")).casefold(),
            str(edge.get("relation", "")).casefold(),
            str(edge.get("target", "")).casefold(),
        )
        for edge in graph.get("links", [])
    }
    found_edges = expected_edges & observed_edges
    missing = required - labels
    return {
        "required_concepts": sorted(required),
        "found_concepts": sorted(required & labels),
        "missing_concepts": sorted(missing),
        "expected_edge_signatures": sorted(
            f"{source}:{relation}:{target}" for source, relation, target in expected_edges
        ),
        "found_edge_signatures": sorted(
            f"{source}:{relation}:{target}" for source, relation, target in found_edges
        ),
        "passes": not missing and len(found_edges) == len(expected_edges),
    }


def _raw_content(response: dict[str, object]) -> str:
    choices = response.get("choices", [])
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message", {})
    return str(message.get("content", "")) if isinstance(message, dict) else ""


def _prepare_model(config: _ModelConfig, source: Path, work: Path) -> Path:
    if config.name == "glm52":
        model = work / "model"
        artifact_download.download(
            artifact_download.DownloadOptions(
                provider_name="hf-xet",
                source=config.repo_id,
                revision=config.revision,
                destination=model,
                includes=(
                    "*.safetensors",
                    "config.json",
                    "generation_config.json",
                    "tokenizer.json",
                    "tokenizer_config.json",
                ),
                receipt=work / "model-download.json",
                dry_run=False,
            )
        )
        return model

    source_model = work / "source-model"
    model = work / "model"
    artifact_download.download(
        artifact_download.DownloadOptions(
            provider_name="hf-xet",
            source=config.repo_id,
            revision=config.revision,
            destination=source_model,
            includes=(
                "*.safetensors",
                "model.safetensors.index.json",
                "config.json",
                "generation_config.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "special_tokens_map.json",
            ),
            receipt=work / "source-model-download.json",
            dry_run=False,
        )
    )
    _run(
        [
            sys.executable,
            str(source / "c/tools/convert_olmoe_merged.py"),
            "--model",
            str(source_model),
            "--out",
            str(model),
            "--min-free-gb",
            "20",
        ],
        cwd=source,
    )
    return model


def _server_environment(config: _ModelConfig) -> dict[str, str]:
    environment = dict(os.environ)
    environment.update({"CTX": "4096", "COLI_API_KEY": "local", **dict(config.server_env)})
    return environment


def _server_command(config: _ModelConfig, source: Path, model: Path, port: int) -> list[str]:
    return [
        sys.executable,
        str(source / "c/coli"),
        "serve",
        "--model",
        str(model),
        "--model-id",
        config.model_id,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--ctx",
        "4096",
        "--ngen",
        "1024",
        "--cap",
        "64",
        "--api-key",
        "local",
        *config.server_args,
    ]


def _extract(
    repo_root: Path, fixture: Path, output: Path, graph_env: dict[str, str]
) -> tuple[subprocess.CompletedProcess[str], float, Path]:
    started = time.monotonic()
    completed = subprocess.run(
        [
            graphify_exe(repo_root),
            "extract",
            str(fixture),
            "--backend",
            "openai",
            "--mode",
            "deep",
            "--token-budget",
            "1000",
            "--max-concurrency",
            "1",
            "--force",
            "--out",
            str(output),
        ],
        cwd=repo_root,
        env=graph_env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    return completed, time.monotonic() - started, output / "graphify-out/graph.json"


def run(
    repo_root: Path,
    source: Path | None,
    work: Path,
    port: int,
    model_name: _ModelName = "olmoe",
) -> int:
    """Build, download, serve, and exercise two real deep extractions."""
    work.mkdir(parents=True, exist_ok=True)
    source = _source_checkout(source, work)
    config = _MODEL_CONFIGS[model_name]
    commit = _head_commit(source)
    _run(["make", "-C", "c", config.build_target], cwd=source)
    model = _prepare_model(config, source, work)
    fixture = work / "fixture"
    fixture.mkdir(exist_ok=True)
    (fixture / "dependency-workflow.md").write_text(_FIXTURE, encoding="utf-8")
    base_url = f"http://127.0.0.1:{port}/v1"
    server_log = (work / "colibri-server.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        _server_command(config, source, model, port),
        cwd=source,
        env=_server_environment(config),
        stdout=server_log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        load_seconds = _wait_for_server(base_url, process)
        raw_started = time.monotonic()
        raw = _request(
            f"{base_url}/chat/completions",
            payload={
                "model": config.model_id,
                "messages": [
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": '{"probe":"reply with ok"}'},
                ],
                "temperature": 0,
                "max_completion_tokens": 128,
                "stream": False,
            },
        )
        raw_seconds = time.monotonic() - raw_started
        graph_env = clean_env(
            {
                "OPENAI_BASE_URL": base_url,
                "OPENAI_API_KEY": "local",
                "OPENAI_MODEL": config.model_id,
                "GRAPHIFY_MAX_OUTPUT_TOKENS": "1024",
            }
        )
        first, first_seconds, first_graph = _extract(
            repo_root, fixture, work / "graphify-output-1", graph_env
        )
        second, second_seconds, second_graph = _extract(
            repo_root, fixture, work / "graphify-output-2", graph_env
        )
        nodes, links = _counts(first_graph) if first_graph.is_file() else (0, 0)
        semantic_score = _semantic_score(first_graph) if first_graph.is_file() else {}
        first_hash = _sha256(first_graph)
        second_hash = _sha256(second_graph)
        schema_clean = all(
            result.returncode == 0 and "Extraction warning" not in result.stderr
            for result in (first, second)
        )
        semantic_clean = bool(semantic_score.get("passes"))
        transport_clean = bool(_raw_content(raw))
        deterministic = first_hash is not None and first_hash == second_hash
        report = {
            "schema_version": 2,
            "colibri_commit": commit,
            "model_name": config.name,
            "model": config.repo_id,
            "model_revision": config.revision,
            "model_config": asdict(config),
            "server_load_seconds": round(load_seconds, 3),
            "raw_request_seconds": round(raw_seconds, 3),
            "raw_response": raw,
            "graphify_version": "0.9.39",
            "graphify_rc": first.returncode,
            "graphify_repeat_rc": second.returncode,
            "graphify_seconds": round(first_seconds, 3),
            "graphify_repeat_seconds": round(second_seconds, 3),
            "graphify_nodes": nodes,
            "graphify_links": links,
            "graph_sha256": first_hash,
            "graph_repeat_sha256": second_hash,
            "graphify_stdout": first.stdout,
            "graphify_stderr": first.stderr,
            "graphify_repeat_stdout": second.stdout,
            "graphify_repeat_stderr": second.stderr,
            "semantic_score": semantic_score,
            "transport_status": "PASS" if transport_clean else "FAIL",
            "schema_status": "PASS" if schema_clean else "FAIL",
            "semantic_status": "PASS" if semantic_clean else "FAIL",
            "determinism_status": "PASS" if deterministic else "FAIL",
            "status": "PASS"
            if nodes > 0 and transport_clean and schema_clean and semantic_clean and deterministic
            else "FAIL",
        }
        (work / "result.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "PASS" else 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        server_log.close()


def main(repo_root: Path, argv: list[str]) -> int:
    """Parse the task boundary and run the isolated canary."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=tuple(_MODEL_CONFIGS), default="olmoe")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18081)
    args = parser.parse_args(argv)
    return run(
        repo_root,
        args.source.resolve() if args.source else None,
        args.work.resolve(),
        args.port,
        args.model,
    )
