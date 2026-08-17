# Copyright (c) 2026 Raymond Manaloto
"""Public contract tests for the complete Graphify semantic-corpus planner.

These tests use real filesystem bytes and Git identities.  They do not stand in
for a semantic provider run; only retained real-provider receipts can certify
that part of issue #301.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import runpy
import shutil
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType
from typing import Never, cast

import msgspec
import pytest
from kb_setup import (
    cli,
    graphify_semantic_adapter,
    graphify_semantic_corpus,
    graphify_semantic_corpus_authority,
    graphify_semantic_corpus_prototype,
    graphify_semantic_slice,
)

_UNSET_AUTHORITY_JSON = (
    b'{"advisories_sha256":"",'
    b'"execution_config_sha256":"",'
    b'"exclusions_sha256":"",'
    b'"plan_manifest_sha256":"",'
    b'"schema_version":1}\n'
)


@pytest.fixture
def unset_authority(monkeypatch) -> None:
    """Assert the un-authorized behaviour against an explicitly un-authorized root.

    These tests describe what verification says when NOBODY has signed off on a
    plan, and they used to get that state for free because the committed
    `AUTHORITY_JSON` was empty. It is no longer empty — and because planning is
    deterministic, a plan rebuilt from the same pinned source is byte-identical to
    the authorized one, so the digests match and the tests silently began
    describing the opposite case.

    Setting the precondition here rather than inheriting it is the fix: a test
    that depends on the ambient authorization state is measuring the repository's
    mood, not the verifier.
    """
    monkeypatch.setattr(graphify_semantic_corpus_authority, "AUTHORITY_JSON", _UNSET_AUTHORITY_JSON)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def _source(root: Path) -> tuple[str, str]:
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "corpus@example.invalid")
    _git(root, "config", "user.name", "Corpus Contract")
    words = "semantic " * 50_100
    (root / "guide.md").write_text(f"# Guide\n\n{words}\n", encoding="utf-8")
    _git(root, "add", "guide.md")
    _git(root, "commit", "-qm", "source")
    return _git(root, "rev-parse", "HEAD"), _git(root, "rev-parse", "HEAD^{tree}")


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _rehash_plan(candidate: Path) -> None:
    members = []
    for name in graphify_semantic_corpus.PLAN_MEMBER_NAMES:
        raw = (candidate / name).read_bytes()
        members.append({"name": name, "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)})
    manifest = json.loads((candidate / "manifest.json").read_text(encoding="utf-8"))
    manifest["members"] = members
    (candidate / "manifest.json").write_bytes(_canonical(manifest))


def _real_fragment(repo_root: Path) -> dict[str, object]:
    return json.loads(
        (repo_root / "graphify-out/graphify-semantic-slice/semantic-fragment.json").read_text(
            encoding="utf-8"
        )
    )


def _real_provider_evidence(repo_root: Path) -> tuple[bytes, bytes]:
    root = repo_root / "graphify-out/graphify-semantic-slice"
    return (root / "receipt.json").read_bytes(), (root / "adapter-metadata.json").read_bytes()


def _exact_graphify_plan(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    source = tmp_path / "exact-graphify-source"
    source_pin = graphify_semantic_corpus.admit_source(repo_root, source)
    candidate = tmp_path / "exact-graphify-plan"
    graphify_semantic_corpus.plan_source(
        source,
        candidate,
        source=source_pin,
    )
    return candidate


def test_cli_dispatches_semantic_corpus_verifier(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, list[str]]] = []

    def record(repo_root: Path, args: list[str]) -> int:
        calls.append((repo_root, args))
        return 0

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(graphify_semantic_corpus, "corpus_main", record)

    assert cli.main(["graphify-semantic-corpus", "verify", "candidate"]) == 0
    assert calls == [(tmp_path, ["verify", "candidate"])]


def test_plan_artifact_verifier_rehashes_real_source_bytes(unset_authority, tmp_path: Path) -> None:
    source = tmp_path / "source"
    commit, tree = _source(source)
    candidate = tmp_path / "candidate"
    graphify_semantic_corpus.plan_source(
        source,
        candidate,
        source=graphify_semantic_corpus.SourcePin(ref="test-ref", commit=commit, tree=tree),
        token_budget=20_000,
    )

    complete = graphify_semantic_corpus.verify_plan(candidate, source_root=source)
    assert complete.state == "incomplete"
    assert complete.structural_complete is True
    assert complete.execution_authorized is False
    assert complete.reasons == ("plan-authority-unset",)

    inventory = candidate / "source-inventory.json"
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    payload["units"][0]["sha256"] = hashlib.sha256(b"hostile mutation").hexdigest()
    inventory.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    rejected = graphify_semantic_corpus.verify_plan(candidate, source_root=source)
    assert rejected.state == "failed"
    assert "member-digest-mismatch:source-inventory.json" in rejected.reasons


def test_plan_warning_is_a_structural_failure(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init", "-q")
    _git(source, "config", "user.email", "corpus@example.invalid")
    _git(source, "config", "user.name", "Corpus Contract")
    (source / "tiny.md").write_text("tiny\n", encoding="utf-8")
    _git(source, "add", "tiny.md")
    _git(source, "commit", "-qm", "source")
    candidate = tmp_path / "candidate"
    graphify_semantic_corpus.plan_source(
        source,
        candidate,
        source=graphify_semantic_corpus.SourcePin(
            ref="test-ref",
            commit=_git(source, "rev-parse", "HEAD"),
            tree=_git(source, "rev-parse", "HEAD^{tree}"),
        ),
    )

    authority_path = tmp_path / "reviewed-authority.json"
    authority_path.write_bytes(
        _canonical(
            {
                "advisories_sha256": hashlib.sha256(
                    (candidate / "advisories.json").read_bytes()
                ).hexdigest(),
                "execution_config_sha256": hashlib.sha256(
                    (candidate / "execution-config.json").read_bytes()
                ).hexdigest(),
                "exclusions_sha256": hashlib.sha256(
                    (candidate / "exclusions.json").read_bytes()
                ).hexdigest(),
                "plan_manifest_sha256": hashlib.sha256(
                    (candidate / "manifest.json").read_bytes()
                ).hexdigest(),
                "schema_version": 1,
            }
        )
    )
    result = graphify_semantic_corpus.verify_plan(
        candidate,
        source_root=source,
        authority_path=authority_path,
    )
    assert result.state == "failed"
    assert result.reasons == ("plan-warning-bearing",)


def test_exact_graphify_cost_advisory_has_separate_review_authority(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = repo_root / "sources/graphify"
    candidate = tmp_path / "candidate"
    graphify_semantic_corpus.plan_source(
        source,
        candidate,
        source=graphify_semantic_corpus.SourcePin(
            ref="v0.9.45",
            commit=_git(source, "rev-parse", "HEAD"),
            tree=_git(source, "rev-parse", "HEAD^{tree}"),
        ),
    )

    advisories = json.loads((candidate / "advisories.json").read_text(encoding="utf-8"))
    assert advisories["entries"] == [
        {
            "code": "graphify-large-corpus-token-cost",
            "detector_git_object": "f76a4259f6a7360872663fbe711c4738ecda4680",
            "file_count_threshold": 500,
            "message": (
                "Large corpus: 792 files · ~1,394,475 words. Semantic extraction will be "
                "expensive (many Claude tokens). Consider running on a subfolder."
            ),
            "observed_files": 792,
            "observed_words": 1_394_475,
            "review_status": "provisional",
            "word_count_threshold": 500_000,
        }
    ]
    authority_path = tmp_path / "reviewed-authority.json"
    authority_path.write_bytes(
        _canonical(
            {
                "advisories_sha256": hashlib.sha256(
                    (candidate / "advisories.json").read_bytes()
                ).hexdigest(),
                "execution_config_sha256": hashlib.sha256(
                    (candidate / "execution-config.json").read_bytes()
                ).hexdigest(),
                "exclusions_sha256": hashlib.sha256(
                    (candidate / "exclusions.json").read_bytes()
                ).hexdigest(),
                "plan_manifest_sha256": hashlib.sha256(
                    (candidate / "manifest.json").read_bytes()
                ).hexdigest(),
                "schema_version": 1,
            }
        )
    )
    result = graphify_semantic_corpus.verify_plan(
        candidate,
        source_root=source,
        authority_path=authority_path,
    )
    assert result.state == "complete"
    assert result.structural_complete is True
    assert result.execution_authorized is True
    assert result.reasons == ()


def test_coherently_rehashed_advisory_cannot_bypass_source_recomputation(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = repo_root / "sources/graphify"
    candidate = tmp_path / "candidate"
    graphify_semantic_corpus.plan_source(
        source,
        candidate,
        source=graphify_semantic_corpus.SourcePin(
            ref="v0.9.45",
            commit=_git(source, "rev-parse", "HEAD"),
            tree=_git(source, "rev-parse", "HEAD^{tree}"),
        ),
    )
    advisory_path = candidate / "advisories.json"
    advisory = json.loads(advisory_path.read_text(encoding="utf-8"))
    advisory["entries"][0]["observed_files"] += 1
    advisory["entries"][0]["message"] = advisory["entries"][0]["message"].replace(
        # 792 -> 793, tracking `observed_files += 1` above. These two must stay in
        # step: the mutation is only a mutation while the written value DIFFERS
        # from the recomputed one, so leaving "791 files" here after the corpus
        # grew would rewrite nothing and the test would assert a mismatch it
        # never actually created.
        "792 files",
        "793 files",
    )
    advisory_path.write_bytes(_canonical(advisory))
    _rehash_plan(candidate)

    result = graphify_semantic_corpus.verify_plan(candidate, source_root=source)
    assert result.state == "failed"
    assert result.reasons == ("source-advisory-recomputation-mismatch",)


def test_verify_plan_requires_source_snapshot() -> None:
    parameter = inspect.signature(graphify_semantic_corpus.verify_plan).parameters["source_root"]
    assert parameter.default is inspect.Parameter.empty


def test_public_cli_verify_recomputes_exact_pinned_snapshot(
    unset_authority, capsys, tmp_path: Path
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    candidate = _exact_graphify_plan(tmp_path)

    assert graphify_semantic_corpus.corpus_main(repo_root, ["verify", str(candidate)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "execution_authorized": False,
        "reasons": [
            "plan-authority-unset",
            "cost-advisory-review-required",
            "provisional-input-decisions",
        ],
        "state": "incomplete",
        "structural_complete": True,
    }


def test_prototype_adapter_environment_overlays_required_ambient_without_secrets(
    tmp_path: Path,
) -> None:
    ambient = {
        "HOME": "/Users/example",
        "PATH": "/usr/bin",
        "XDG_CONFIG_HOME": "/Users/example/.config",
        "ANTHROPIC_API_KEY": "must-not-pass",
        "UNRELATED_SECRET": "must-not-pass",
    }
    overlay = {
        "PATH": "/adapter:/usr/bin",
        "KB_SEMANTIC_ORIGINAL_PATH": "/usr/bin",
        "KB_SEMANTIC_METADATA_PATH": str(tmp_path / "metadata.json"),
        "KB_SEMANTIC_REAL_CLAUDE": "/usr/bin/claude",
        "KB_SEMANTIC_REAL_CLAUDE_SHA256": "a" * 64,
        "GRAPHIFY_API_TIMEOUT": "120",
        "GRAPHIFY_CLAUDE_CLI_MODEL": "claude-haiku-4-5-20251001",
        "GRAPHIFY_NO_INCREMENTAL_CACHE": "1",
    }

    with pytest.raises(ValueError, match="forbidden routing environment names"):
        graphify_semantic_corpus_prototype.adapter_process_environment(ambient, overlay)

    ambient.pop("ANTHROPIC_API_KEY")
    child = graphify_semantic_corpus_prototype.adapter_process_environment(ambient, overlay)
    assert child["HOME"] == "/Users/example"
    assert child["XDG_CONFIG_HOME"] == "/Users/example/.config"
    assert child["PATH"] == "/adapter:/usr/bin"
    assert child["KB_SEMANTIC_ORIGINAL_PATH"] == "/usr/bin"
    assert "UNRELATED_SECRET" not in child


def test_failed_adapter_attempt_audit_preserves_unknown_provider_inferences() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    audit = msgspec.json.decode(
        (repo_root / "docs/agents/evidence/issue-301/failed-attempt-audit-v2.json").read_bytes(),
        type=graphify_semantic_corpus_prototype.FailedAttemptAudit,
        strict=True,
    )

    assert audit.status == "failed-phase-unknown"
    assert audit.adapter_invocations == 1
    assert audit.provider_inferences == "unknown"
    assert audit.failure_phase == "unknown"
    assert audit.original_outcome_sha256 == (
        "d451f0009c9769c8b193ca50e3cf4f67293675d773c9e6fd7111d39289b3f90c"
    )
    assert audit.stage_receipt_sha256 == (
        "534891bb528e923928d1a83ed3dbb26a3d0c7ff221cec03cbd2c36473f62d1ad"
    )


def test_corrected_call_consumption_distinguishes_boundary_from_inference() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    evidence = repo_root / "docs/agents/evidence/issue-301"
    consumption = json.loads(
        (evidence / "corrected-max-chunk-consumption.json").read_text(encoding="utf-8")
    )
    marker = json.loads(
        (evidence / "corrected-max-chunk-terminal" / "provider-boundary-start.json").read_text(
            encoding="utf-8"
        )
    )

    assert consumption["adapter_invocations"] == 1
    assert consumption["provider_inferences"] == "unknown"
    assert consumption["provider_process_boundary_invocations"] == 1
    assert consumption["obsolete_local_post_parse_reasons"] == ["turn-bound-exceeded"]
    assert marker["provider_process_invocations"] == 1
    assert marker["provider_inferences"] == "unknown"


def test_prototype_identity_check_rejects_wrong_launcher_file(tmp_path: Path) -> None:
    plan = _exact_graphify_plan(tmp_path)
    launcher = tmp_path / "launcher.py"
    launcher.write_text("# hostile replacement\n", encoding="utf-8")

    assert graphify_semantic_corpus_prototype.prototype_identity_reasons(plan, launcher) == (
        "launcher-identity-mismatch",
    )


def test_adapter_retains_exact_provider_boundary_start_marker(tmp_path: Path) -> None:
    destination = tmp_path / "provider-boundary-start.json"
    marker = graphify_semantic_adapter.write_provider_boundary_start(
        destination,
        adapter_sha256="a" * 64,
        prompt=b"exact prompt",
        argv=("claude", "-p"),
    )

    assert marker.phase == "provider-boundary-started"
    assert marker.provider_process_invocations == 1
    assert marker.provider_inferences == "unknown"
    assert marker.prompt_sha256 == hashlib.sha256(b"exact prompt").hexdigest()
    assert (
        msgspec.json.decode(
            destination.read_bytes(),
            type=graphify_semantic_adapter.ProviderBoundaryStart,
            strict=True,
        )
        == marker
    )
    with pytest.raises(ValueError, match="already exists"):
        graphify_semantic_adapter.write_provider_boundary_start(
            destination,
            adapter_sha256="a" * 64,
            prompt=b"exact prompt",
            argv=("claude", "-p"),
        )


def test_provider_boundary_marker_fsyncs_file_and_parent(monkeypatch, tmp_path: Path) -> None:
    calls: list[int] = []
    original = os.fsync

    def record(descriptor: int) -> None:
        calls.append(descriptor)
        original(descriptor)

    monkeypatch.setattr(os, "fsync", record)
    graphify_semantic_adapter.write_provider_boundary_start(
        tmp_path / "provider-boundary-start.json",
        adapter_sha256="a" * 64,
        prompt=b"exact prompt",
        argv=("claude", "-p"),
    )

    assert len(calls) == 2


def test_adapter_rejects_unset_provider_boundary_path() -> None:
    with pytest.raises(ValueError, match="path is unset"):
        graphify_semantic_adapter._provider_boundary_path({})


def test_provider_boundary_marker_allows_only_one_concurrent_creator(tmp_path: Path) -> None:
    destination = tmp_path / "provider-boundary-start.json"

    def create() -> str:
        try:
            graphify_semantic_adapter.write_provider_boundary_start(
                destination,
                adapter_sha256="a" * 64,
                prompt=b"exact prompt",
                argv=("claude", "-p"),
            )
        except ValueError as exc:
            return str(exc)
        return "created"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: create(), range(2)))

    assert sorted(results) == ["created", "provider boundary marker already exists"]


def test_prototype_marker_state_is_disjoint_from_future_stage_output(tmp_path: Path) -> None:
    output = tmp_path / "prototype-output"
    state = tmp_path / "prototype-state"

    marker = graphify_semantic_corpus_prototype.prepare_prototype_topology(output, state)

    assert not output.exists()
    assert marker == state / "provider-boundary-start.json"
    assert marker.parent.is_dir()
    graphify_semantic_adapter.write_provider_boundary_start(
        marker,
        adapter_sha256="a" * 64,
        prompt=b"exact prompt",
        argv=("claude", "-p"),
    )
    output.mkdir()
    assert output.is_dir()


def test_prototype_topology_rejects_lexical_parent_traversal(tmp_path: Path) -> None:
    output = tmp_path / "prototype-output"
    state = tmp_path / "alias" / ".." / "prototype-state"

    with pytest.raises(ValueError, match="parent traversal"):
        graphify_semantic_corpus_prototype.prepare_prototype_topology(output, state)

    assert not output.exists()
    assert not (tmp_path / "prototype-state").exists()


def test_prototype_topology_rejects_equivalent_output_and_state_paths(tmp_path: Path) -> None:
    output = tmp_path / "prototype-output"

    with pytest.raises(ValueError, match="distinct canonical siblings"):
        graphify_semantic_corpus_prototype.prepare_prototype_topology(output, output)

    assert not output.exists()


def test_prototype_topology_rejects_symlinked_parent_equivalence(tmp_path: Path) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    alias_parent = tmp_path / "alias"
    alias_parent.symlink_to(real_parent, target_is_directory=True)
    output = real_parent / "prototype-output"
    state = alias_parent / "prototype-state"

    with pytest.raises(ValueError, match="symlinked parent"):
        graphify_semantic_corpus_prototype.prepare_prototype_topology(output, state)

    assert not output.exists()
    assert not (real_parent / "prototype-state").exists()


def test_prototype_topology_anchors_creation_against_parent_swap(
    monkeypatch, tmp_path: Path
) -> None:
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    anchored = tmp_path / "anchored"
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    real_mkdir = os.mkdir
    swapped = False

    def swap_then_create(
        path: str | bytes | os.PathLike[str], mode: int = 0o777, *, dir_fd: int | None = None
    ) -> None:
        nonlocal swapped
        if dir_fd is not None and not swapped:
            trusted.rename(anchored)
            trusted.symlink_to(attacker, target_is_directory=True)
            swapped = True
        return real_mkdir(path, mode=mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "mkdir", swap_then_create)
    marker = graphify_semantic_corpus_prototype.prepare_prototype_topology(
        trusted / "output", trusted / "state"
    )

    assert marker == trusted / "state/provider-boundary-start.json"
    assert (anchored / "state").is_dir()
    assert not (attacker / "state").exists()
    (attacker / "state").mkdir()
    with pytest.raises(ValueError, match="destination is unavailable"):
        graphify_semantic_adapter.write_provider_boundary_start(
            marker,
            adapter_sha256="a" * 64,
            prompt=b"exact prompt",
            argv=("claude", "-p"),
        )
    assert not (attacker / "state/provider-boundary-start.json").exists()


def test_no_inference_runtime_probe_retains_typed_timeout(monkeypatch) -> None:
    def timeout(argv: list[str], **_: object) -> Never:
        raise subprocess.TimeoutExpired(argv, timeout=30)

    monkeypatch.setattr(subprocess, "run", timeout)
    completed, reason = graphify_semantic_corpus_prototype._probe_runtime(
        ["claude", "--version"], environment={}
    )

    assert completed is None
    assert reason == "TimeoutExpired"


def test_exact_graphify_visual_exclusions_bind_deterministic_evidence(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = repo_root / "sources/graphify"
    candidate = tmp_path / "candidate"
    graphify_semantic_corpus.plan_source(
        source,
        candidate,
        source=graphify_semantic_corpus.SourcePin(
            ref="v0.9.42",
            commit=_git(source, "rev-parse", "HEAD"),
            tree=_git(source, "rev-parse", "HEAD^{tree}"),
        ),
    )

    exclusions = json.loads((candidate / "exclusions.json").read_text(encoding="utf-8"))
    by_path = {entry["path"]: entry for entry in exclusions["entries"]}
    assert {
        path: (
            entry["exclusion_class"],
            entry["semantic_authority_path"],
            tuple(entry["evidence_paths"]),
        )
        for path, entry in by_path.items()
    } == {
        "docs/demo-path.svg": (
            "regenerable-derived-visual",
            "scripts/gen_demo_path.py",
            ("scripts/gen_demo_path.py",),
        ),
        "docs/graph-hero.png": (
            "presentation-derived-screenshot",
            "README.md",
            ("README.md",),
        ),
        "docs/logo.png": (
            "presentation-branding-asset",
            "README.md",
            ("README.md",),
        ),
        "worked/rsl-siege-manager/graph.html": (
            "generated-graph-visualization-duplicate",
            "worked/rsl-siege-manager/graph.json",
            ("worked/rsl-siege-manager/graph.json",),
        ),
    }
    assert all(entry["review_status"] == "provisional" for entry in by_path.values())
    assert all(len(entry["evidence_sha256"]) == 64 for entry in by_path.values())
    assert all(
        len(value) == 40 for entry in by_path.values() for value in entry["evidence_git_objects"]
    )


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("svg", "svg-evidence-byte-mismatch"),
        ("html", "html-evidence-graph-mismatch"),
        ("html-node", "html-evidence-graph-mismatch"),
        ("html-duplicate-node", "html-evidence-duplicate-node-id"),
        ("html-duplicate-edge", "html-evidence-duplicate-edge"),
        ("readme", "png-evidence-readme-mismatch:docs/graph-hero.png"),
        ("readme-path-binding", "png-evidence-readme-mismatch:docs/graph-hero.png"),
    ],
)
def test_visual_exclusion_evidence_rejects_real_source_drift(
    tmp_path: Path, mutation: str, reason: str
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    original = repo_root / "sources/graphify"
    source = tmp_path / "source"
    subprocess.run(["git", "clone", "-q", "--shared", str(original), str(source)], check=True)
    if mutation == "svg":
        generator = source / "scripts/gen_demo_path.py"
        generator.write_text(
            generator.read_text(encoding="utf-8").replace("#0c1712", "#ffffff", 1),
            encoding="utf-8",
        )
    elif mutation in {"html", "html-node", "html-duplicate-node", "html-duplicate-edge"}:
        graph_path = source / "worked/rsl-siege-manager/graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        if mutation == "html":
            graph["links"][0]["relation"] = "hostile_relation"
        elif mutation == "html-node":
            graph["nodes"][0]["label"] = "hostile label"
        else:
            key = "nodes" if mutation == "html-duplicate-node" else "links"
            graph[key].append(graph[key][0])
            html_path = source / "worked/rsl-siege-manager/graph.html"
            html = html_path.read_text(encoding="utf-8")
            raw_name = "RAW_NODES" if key == "nodes" else "RAW_EDGES"
            match = re.search(rf"const {raw_name} = (\[.*?\]);", html, re.DOTALL)
            assert match is not None
            embedded = json.loads(match.group(1))
            embedded.append(embedded[0])
            html_path.write_text(
                html[: match.start(1)]
                + json.dumps(embedded, separators=(",", ":"))
                + html[match.end(1) :],
                encoding="utf-8",
            )
        graph_path.write_bytes(_canonical(graph))
    elif mutation == "readme":
        readme = source / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8").replace(
                "The FastAPI codebase mapped by graphify.",
                "The screenshot description drifted.",
                1,
            ),
            encoding="utf-8",
        )
    else:
        readme = source / "README.md"
        text = readme.read_text(encoding="utf-8")
        expected_alt = (
            "graphify's interactive graph.html showing the FastAPI codebase as a "
            "force-directed knowledge graph with a legend of detected communities"
        )
        readme.write_text(
            text.replace(f'alt="{expected_alt}"', 'alt="unrelated image"', 1)
            + f'\n<img src="unrelated.png" alt="{expected_alt}">\n',
            encoding="utf-8",
        )
    _git(source, "config", "user.email", "corpus@example.invalid")
    _git(source, "config", "user.name", "Corpus Contract")
    _git(source, "add", "-A")
    _git(source, "commit", "-qm", "hostile evidence drift")

    with pytest.raises(ValueError, match=re.escape(reason)):
        graphify_semantic_corpus.plan_source(
            source,
            tmp_path / "candidate",
            source=graphify_semantic_corpus.SourcePin(
                ref="v0.9.42",
                commit=_git(source, "rev-parse", "HEAD"),
                tree=_git(source, "rev-parse", "HEAD^{tree}"),
            ),
        )


def test_exact_graphify_plan_is_structurally_complete_after_authority_revocation(
    unset_authority,
    tmp_path: Path,
) -> None:
    """Regenerate and exercise the exact pinned #301 plan bytes."""
    candidate = _exact_graphify_plan(tmp_path)
    inventory = json.loads((candidate / "source-inventory.json").read_text(encoding="utf-8"))
    ledger = json.loads((candidate / "chunk-ledger.json").read_text(encoding="utf-8"))
    config = json.loads((candidate / "execution-config.json").read_text(encoding="utf-8"))

    assert inventory["source_ref"] == "v0.9.45"
    assert inventory["source_commit"] == "0738af373af9cf5c95f862cc5f3327fd96b4ea23"
    assert inventory["source_tree"] == "e0e089a404dd0b9f6d01273b869c80197c0cc03c"
    assert inventory["detected_source_count"] == 374
    assert inventory["discovered_unit_count"] == 478
    assert inventory["admitted_unit_count"] == 474
    assert (
        inventory["source_manifest_sha256"]
        == "980fab12cee6348416b2962121f42a3c66a97277ac9e89855abb9d6fe4856911"
    )
    assert len(ledger["chunks"]) == 58
    assert config["max_turns"] == 3
    assert (
        config["semantic_slice_sha256"]
        == hashlib.sha256(Path(graphify_semantic_slice.__file__).read_bytes()).hexdigest()
    )
    result = graphify_semantic_corpus.verify_plan(
        candidate, source_root=candidate.parent / "exact-graphify-source"
    )
    assert result.state == "incomplete"
    assert result.structural_complete is True
    assert result.execution_authorized is False
    assert result.reasons == (
        "plan-authority-unset",
        "cost-advisory-review-required",
        "provisional-input-decisions",
    )


def test_recorded_authority_authorizes_this_plan_and_only_this_plan(
    monkeypatch, tmp_path: Path
) -> None:
    """Arm BOTH directions of the authorization gate on the real committed roots.

    The positive half is the one that had no coverage: every existing test
    asserted refusal, so a change that authorized everything would have passed
    them all. The negative half deliberately corrupts ONE digest rather than
    emptying all four, because that is the case the two reasons have to keep
    apart — `mismatch` means the plan moved since it was reviewed, `unset` means
    it never was, and only the first is fixed by re-authorizing.
    """
    candidate = _exact_graphify_plan(tmp_path)
    source_root = candidate.parent / "exact-graphify-source"

    authorized = graphify_semantic_corpus.verify_plan(candidate, source_root=source_root)
    assert authorized.execution_authorized is True
    assert authorized.reasons == ()
    assert authorized.state == "complete"

    # The mutated prefix is READ from the constant rather than written here as a
    # literal. The literal version named `1706edf9`, the advisories digest of the
    # plan reviewed at 0.9.44; the 0.9.45 re-authorization replaced that digest,
    # so `.replace` matched nothing and the corruption became a no-op — the exact
    # shape where a negative arm keeps passing while testing nothing. Its own
    # `mutation was inert` assertion is what caught that, and it is kept below
    # because deriving the prefix makes inertness unreachable rather than merely
    # unlikely, and an unreachable case still deserves the arm that says so.
    authority = graphify_semantic_corpus_authority.AUTHORITY_JSON
    advisories_digest = json.loads(authority)["advisories_sha256"].encode()
    corrupted = authority.replace(advisories_digest[:8], b"0000dead")
    assert corrupted != authority, "mutation was inert"
    monkeypatch.setattr(graphify_semantic_corpus_authority, "AUTHORITY_JSON", corrupted)

    refused = graphify_semantic_corpus.verify_plan(candidate, source_root=source_root)
    assert refused.execution_authorized is False
    assert "plan-authority-mismatch" in refused.reasons
    assert "plan-authority-unset" not in refused.reasons


def test_consumed_authority_blocks_prototype_before_topology_creation(
    unset_authority, tmp_path: Path
) -> None:
    candidate = _exact_graphify_plan(tmp_path)
    source = candidate.parent / "exact-graphify-source"
    output = tmp_path / "cleared-prototype-output"
    state = tmp_path / "cleared-prototype-state"

    with pytest.raises(ValueError, match="prototype plan is not authorized"):
        graphify_semantic_corpus_prototype.prepare_authorized_prototype(
            candidate,
            source,
            output,
            state,
        )

    assert not output.exists()
    assert not state.exists()


def test_corpus_adapter_rejects_more_than_three_turns() -> None:
    envelope = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "terminal_reason": "completed",
        "stop_reason": "tool_use",
        "num_turns": 4,
        "structured_output": {"nodes": [], "edges": [], "hyperedges": []},
        "modelUsage": {
            "claude-haiku-4-5-20251001": {
                "canonicalModel": "claude-haiku-4-5",
                "provider": "firstParty",
            }
        },
        "permission_denials": [],
        "errors": [],
    }

    reasons = graphify_semantic_adapter.result_envelope_reasons(
        envelope,
        {"KB_SEMANTIC_PROVIDER_BOUNDARY_PATH": "/retained/state/provider-boundary-start.json"},
    )

    assert reasons == ("turn-bound-exceeded",)
    assert envelope["num_turns"] == 4


def test_hidden_max_turns_parser_probe_requires_invalid_integer_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def supported(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(argv)
        return subprocess.CompletedProcess(
            argv,
            1,
            b"",
            b"error: option '--max-turns <turns>' argument "
            b"'not-an-integer' is invalid. must be a number\n",
        )

    monkeypatch.setattr(subprocess, "run", supported)

    graphify_semantic_slice._assert_value_flag_supported(
        Path("/fake/claude"), "--max-turns", environment={}
    )
    assert calls == [["/fake/claude", "-p", "--max-turns", "not-an-integer"]]


def test_hidden_max_turns_parser_probe_rejects_unknown_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unsupported(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            argv,
            1,
            b"",
            b"error: unknown option '--max-turns'\n",
        )

    monkeypatch.setattr(subprocess, "run", unsupported)

    with pytest.raises(ValueError, match="--max-turns parser probe failed"):
        graphify_semantic_slice._assert_value_flag_supported(
            Path("/fake/claude"), "--max-turns", environment={}
        )


def test_result_array_normalizes_exactly_one_final_graphify_envelope() -> None:
    # Mirrors Graphify v0.9.43's streamed error-envelope fixture. Parsing and
    # policy validation are separate: this test proves strict normalization.
    raw = (
        b'[{"type":"system","subtype":"init"},'
        b'{"type":"result","subtype":"success","is_error":true,'
        b'"result":"API Error: Rate limit reached",'
        b'"stop_reason":"stop_sequence","usage":{"input_tokens":0,'
        b'"output_tokens":0},"modelUsage":{}}]'
    )

    envelope, observation = graphify_semantic_adapter.parse_result_envelope(raw)

    assert envelope == {
        "type": "result",
        "subtype": "success",
        "is_error": True,
        "result": "API Error: Rate limit reached",
        "stop_reason": "stop_sequence",
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "modelUsage": {},
    }
    assert msgspec.structs.asdict(observation) == {
        "schema_id": "graphify-claude-envelope-parse/v1",
        "status": "accepted-result-array",
        "response_sha256": "9a20666913bb548f761e4a11c8b2f8d36fa9ef40a0ec50d09ce147e0efc6bf83",
        "response_size": 222,
        "utf8_valid": True,
        "json_valid": True,
        "top_level_kind": "array",
        "event_count": 2,
        "result_count": 1,
        "selected_index": 1,
        "error_offset": -1,
        "trailing_non_whitespace": False,
    }
    encoded = graphify_semantic_slice.encode_json(observation)
    assert b"API Error" not in encoded
    assert b"modelUsage" not in encoded


def test_tracked_prototype_launcher_uses_strict_result_normalization() -> None:
    launcher = (
        Path(__file__).resolve().parents[1]
        / "docs/agents/evidence/issue-301/prototype-corrected-launcher.py"
    )
    namespace = runpy.run_path(str(launcher))
    parse_fragment = cast("Callable[[bytes], dict[str, object]]", namespace["parse_fragment"])
    raw = (
        b'[{"type":"system","subtype":"init"},'
        b'{"type":"result","structured_output":{"nodes":[],"edges":[]}}]'
    )

    assert parse_fragment(raw) == {"nodes": [], "edges": [], "hyperedges": []}
    assert parse_fragment(b'[{"type":"result"},{"type":"assistant"}]') == {}


@pytest.mark.parametrize(
    ("raw", "status", "event_count", "result_count", "selected_index"),
    [
        (b"[]", "result-array-empty", 0, 0, -1),
        (
            b'[{"type":"assistant"}]',
            "result-array-missing-final-result",
            1,
            0,
            -1,
        ),
        (
            b'[{"type":"result"},{"type":"result"}]',
            "result-array-ambiguous-result",
            2,
            2,
            -1,
        ),
        (
            b'[{"type":"result"},{"type":"assistant"}]',
            "result-array-trailing-event",
            2,
            1,
            0,
        ),
        (
            b'[{"type":"assistant"},"private-secret"]',
            "result-array-non-object-event",
            2,
            0,
            -1,
        ),
        (
            b'[{"type":"result"},"private-secret"]',
            "result-array-non-object-event",
            2,
            1,
            -1,
        ),
    ],
)
def test_result_array_rejects_ambiguous_or_hostile_shapes_without_content(
    raw: bytes,
    status: str,
    event_count: int,
    result_count: int,
    selected_index: int,
) -> None:
    envelope, observation = graphify_semantic_adapter.parse_result_envelope(raw)

    assert envelope == {}
    assert observation.status == status
    assert observation.top_level_kind == "array"
    assert observation.event_count == event_count
    assert observation.result_count == result_count
    assert observation.selected_index == selected_index
    assert (
        graphify_semantic_adapter.parse_observation_reasons(
            observation,
            digest=graphify_semantic_adapter.parse_observation_sha256(observation),
            response_sha256=observation.response_sha256,
            response_size=observation.response_size,
        )
        == ()
    )
    encoded = graphify_semantic_slice.encode_json(observation)
    assert raw not in encoded
    assert b"private-secret" not in encoded


@pytest.mark.parametrize(
    ("raw", "expected_envelope", "expected"),
    [
        (
            b'{"type":"result"}',
            {"type": "result"},
            {
                "status": "accepted-object",
                "response_sha256": (
                    "f0ff450aef5c321f0d608f03568fc76dd0f14e04eeb8b2e86637a3459e128451"
                ),
                "response_size": 17,
                "utf8_valid": True,
                "json_valid": True,
                "top_level_kind": "object",
                "event_count": 1,
                "result_count": 1,
                "selected_index": 0,
                "error_offset": -1,
                "trailing_non_whitespace": False,
            },
        ),
        (
            b"\xff",
            {},
            {
                "status": "invalid-utf8",
                "response_sha256": (
                    "a8100ae6aa1940d0b663bb31cd466142ebbdbd5187131b92d93818987832eb89"
                ),
                "response_size": 1,
                "utf8_valid": False,
                "json_valid": False,
                "top_level_kind": "unknown",
                "event_count": 0,
                "result_count": 0,
                "selected_index": -1,
                "error_offset": 0,
                "trailing_non_whitespace": False,
            },
        ),
        (
            b'{"type":',
            {},
            {
                "status": "truncated-json",
                "response_sha256": (
                    "d356aa44394dfb9e6d62d1ee01fa0e67610ff5b42d93791e44c2731901c7df66"
                ),
                "response_size": 8,
                "utf8_valid": True,
                "json_valid": False,
                "top_level_kind": "object",
                "event_count": 0,
                "result_count": 0,
                "selected_index": -1,
                "error_offset": 8,
                "trailing_non_whitespace": False,
            },
        ),
        (
            b'{"type":"result"}\n{"extra":true}',
            {},
            {
                "status": "trailing-data",
                "response_sha256": (
                    "2d59126638c06cb97de3d735190c0a1c11e4fb80ad8730d7ad9880727c9080b6"
                ),
                "response_size": 32,
                "utf8_valid": True,
                "json_valid": False,
                "top_level_kind": "object",
                "event_count": 0,
                "result_count": 0,
                "selected_index": -1,
                "error_offset": 18,
                "trailing_non_whitespace": True,
            },
        ),
        (
            '{"x":"é" "y":1}'.encode(),
            {},
            {
                "status": "invalid-json",
                "response_sha256": (
                    "6f54c4ec1bbb57e9e439c8cf41c323b2122936deda6092e8b858271b850cb3c8"
                ),
                "response_size": 16,
                "utf8_valid": True,
                "json_valid": False,
                "top_level_kind": "object",
                "event_count": 0,
                "result_count": 0,
                "selected_index": -1,
                "error_offset": 10,
                "trailing_non_whitespace": False,
            },
        ),
        (
            b'[{"type":"result"}]',
            {"type": "result"},
            {
                "status": "accepted-result-array",
                "response_sha256": (
                    "5b51d00d46fe9b28ec9c405101ad42380081e0e8d5dd666e08a5d1d32375e543"
                ),
                "response_size": 19,
                "utf8_valid": True,
                "json_valid": True,
                "top_level_kind": "array",
                "event_count": 1,
                "result_count": 1,
                "selected_index": 0,
                "error_offset": -1,
                "trailing_non_whitespace": False,
            },
        ),
        (
            b'"result"',
            {},
            {
                "status": "valid-non-object",
                "response_sha256": (
                    "d9fd9a3d81d750e6edc61aec66e7c4112f7af7c34ebe0a0d20189464ec9df135"
                ),
                "response_size": 8,
                "utf8_valid": True,
                "json_valid": True,
                "top_level_kind": "string",
                "event_count": 0,
                "result_count": 0,
                "selected_index": -1,
                "error_offset": -1,
                "trailing_non_whitespace": False,
            },
        ),
    ],
)
def test_parse_observation_retains_only_sanitized_shape(
    raw: bytes,
    expected_envelope: dict[str, object],
    expected: dict[str, object],
) -> None:
    envelope, observation = graphify_semantic_adapter.parse_result_envelope(raw)

    assert envelope == expected_envelope
    assert msgspec.structs.asdict(observation) == {
        "schema_id": "graphify-claude-envelope-parse/v1",
        **expected,
    }
    encoded = msgspec.json.encode(observation, order="sorted")
    assert raw not in encoded


@pytest.mark.parametrize(
    ("raw", "response_sha256"),
    [
        (
            b'{"extra":NaN}',
            "f67e63489a6b27b71a66522d7fb8a94d5996490dfae297a8431355bf3769d607",
        ),
        (
            b'{"extra":Infinity}',
            "74e7fa90f0854ffc55c2ee05e937bc97a89a5e41bace6e08e16d9e1ee6abe321",
        ),
        (
            b'{"extra":-Infinity}',
            "1cc56c056508f57245286e309e34ad7349ce971d7b2c64efebf72bb8a295254b",
        ),
    ],
)
def test_parse_observation_rejects_non_json_numeric_constants(
    raw: bytes,
    response_sha256: str,
) -> None:
    envelope, observation = graphify_semantic_adapter.parse_result_envelope(raw)

    assert envelope == {}
    assert msgspec.structs.asdict(observation) == {
        "schema_id": "graphify-claude-envelope-parse/v1",
        "status": "non-json-constant",
        "response_sha256": response_sha256,
        "response_size": len(raw),
        "utf8_valid": True,
        "json_valid": False,
        "top_level_kind": "object",
        "event_count": 0,
        "result_count": 0,
        "selected_index": -1,
        "error_offset": -1,
        "trailing_non_whitespace": False,
    }
    assert (
        graphify_semantic_adapter.parse_observation_reasons(
            observation,
            digest=graphify_semantic_adapter.parse_observation_sha256(observation),
            response_sha256=response_sha256,
            response_size=len(raw),
        )
        == ()
    )


def test_parse_observation_classifies_decoder_integer_limit() -> None:
    raw = b'{"extra":' + (b"1" * 5_000) + b"}"

    envelope, observation = graphify_semantic_adapter.parse_result_envelope(raw)

    assert envelope == {}
    assert msgspec.structs.asdict(observation) == {
        "schema_id": "graphify-claude-envelope-parse/v1",
        "status": "numeric-limit",
        "response_sha256": ("1eff2f020fdbf3a04199fdb261f586dc21fc55a896c4cdc055dfdad0324fd1d3"),
        "response_size": 5_010,
        "utf8_valid": True,
        "json_valid": False,
        "top_level_kind": "object",
        "event_count": 0,
        "result_count": 0,
        "selected_index": -1,
        "error_offset": -1,
        "trailing_non_whitespace": False,
    }
    assert (
        graphify_semantic_adapter.parse_observation_reasons(
            observation,
            digest=graphify_semantic_adapter.parse_observation_sha256(observation),
            response_sha256=observation.response_sha256,
            response_size=observation.response_size,
        )
        == ()
    )


def test_parse_observation_classifies_decoder_nesting_limit() -> None:
    """The nesting-limit branch, at a depth this interpreter actually recurses on.

    The fixture was 50,000 and stopped reaching the branch: the classifier decodes
    with the STDLIB `json`, and CPython 3.14 scans deep arrays iteratively, so
    50,000 now decodes cleanly and the observation came back
    `result-array-non-object-event` with `json_valid: True`. The branch was not
    dead — the fixture had simply become too shallow for the interpreter (#317).

    Re-measured on 3.14.7 rather than guessed: 100,000 decodes fine, 500,000 and
    1,000,000 raise `RecursionError`, and a 200,000-deep OBJECT raises too. 500k
    is used for the 5x margin over the last known-passing depth, because a fixture
    sitting on the boundary would be flaky against stack size.

    That margin is the only thing making this test stable, and it is a property of
    the interpreter rather than of the code — so if this fails again, re-measure
    the threshold before changing the classifier.
    """
    raw = (b"[" * 500_000) + b"0" + (b"]" * 500_000)

    envelope, observation = graphify_semantic_adapter.parse_result_envelope(raw)

    assert envelope == {}
    assert msgspec.structs.asdict(observation) == {
        "schema_id": "graphify-claude-envelope-parse/v1",
        "status": "nesting-limit",
        "response_sha256": ("8742aa50eb17792747965876fb2216ddd8e0df9fe4c5cb44c1dfee3d755dca9d"),
        "response_size": 1_000_001,
        "utf8_valid": True,
        "json_valid": False,
        "top_level_kind": "array",
        "event_count": 0,
        "result_count": 0,
        "selected_index": -1,
        "error_offset": -1,
        "trailing_non_whitespace": False,
    }
    assert (
        graphify_semantic_adapter.parse_observation_reasons(
            observation,
            digest=graphify_semantic_adapter.parse_observation_sha256(observation),
            response_sha256=observation.response_sha256,
            response_size=observation.response_size,
        )
        == ()
    )


def test_parse_observation_digest_rejects_coherent_metadata_tampering() -> None:
    raw = b'{"type":"result"}'
    _envelope, observation = graphify_semantic_adapter.parse_result_envelope(raw)
    digest = graphify_semantic_adapter.parse_observation_sha256(observation)
    tampered = msgspec.structs.replace(
        observation,
        status="accepted-result-array",
        top_level_kind="array",
    )

    assert graphify_semantic_adapter.parse_observation_reasons(
        tampered,
        digest=digest,
        response_sha256=("f0ff450aef5c321f0d608f03568fc76dd0f14e04eeb8b2e86637a3459e128451"),
        response_size=17,
    ) == ("parse-observation-digest-mismatch",)


@pytest.mark.parametrize(
    ("changes", "digest", "response_sha256", "response_size", "reason"),
    [
        ({}, "not-a-digest", None, None, "parse-observation-digest-invalid"),
        (
            {"response_sha256": "not-a-digest"},
            None,
            "not-a-digest",
            None,
            "parse-observation-response-digest-invalid",
        ),
        (
            {"response_size": -1},
            None,
            None,
            -1,
            "parse-observation-response-size-invalid",
        ),
        (
            {"status": "invalid-json", "json_valid": False, "error_offset": 18},
            None,
            None,
            None,
            "parse-observation-error-offset-invalid",
        ),
    ],
)
def test_parse_observation_rejects_malformed_or_impossible_bindings(
    changes: dict[str, object],
    digest: str | None,
    response_sha256: str | None,
    response_size: int | None,
    reason: str,
) -> None:
    raw = b'{"type":"result"}'
    _envelope, observation = graphify_semantic_adapter.parse_result_envelope(raw)
    changed = msgspec.structs.replace(observation, **changes)

    reasons = graphify_semantic_adapter.parse_observation_reasons(
        changed,
        digest=digest or graphify_semantic_adapter.parse_observation_sha256(changed),
        response_sha256=response_sha256 or changed.response_sha256,
        response_size=changed.response_size if response_size is None else response_size,
    )

    assert reason in reasons


def test_parse_observation_does_not_retain_object_keys_or_values() -> None:
    raw = b'{"private-secret-key":"private-secret-value"}'

    envelope, observation = graphify_semantic_adapter.parse_result_envelope(raw)
    encoded = graphify_semantic_slice.encode_json(observation)

    assert envelope == {"private-secret-key": "private-secret-value"}
    assert b"private-secret-key" not in encoded
    assert b"private-secret-value" not in encoded


def test_adapter_metadata_atomically_binds_sanitized_parse_observation() -> None:
    raw = b'{"type":"result"}'
    envelope, observation = graphify_semantic_adapter.parse_result_envelope(raw)
    metadata = graphify_semantic_adapter._metadata(
        graphify_semantic_adapter.MetadataInputs(
            executable=Path("/bin/sh"),
            version="test",
            argv=(),
            environment={},
            auth=graphify_semantic_slice.AuthIdentity(
                logged_in=True,
                auth_method="claude.ai",
                api_provider="firstParty",
                subscription_type="max",
            ),
            prompt=b"prompt",
            stdout=raw,
            stderr=b"",
            returncode=0,
            envelope=envelope,
            parse_observation=observation,
            elapsed_ms=1,
            reasons=(),
        )
    )

    assert metadata.parse_observation == observation
    assert metadata.parse_observation_sha256 == (
        graphify_semantic_adapter.parse_observation_sha256(observation)
    )
    assert (
        graphify_semantic_adapter.parse_observation_reasons(
            metadata.parse_observation,
            digest=metadata.parse_observation_sha256,
            response_sha256=metadata.response_sha256,
            response_size=metadata.response_size,
        )
        == ()
    )


def test_corpus_accepts_strictly_normalized_final_result_array() -> None:
    raw = (
        b'[{"type":"system","subtype":"init"},'
        b'{"type":"result","subtype":"success","is_error":false,'
        b'"terminal_reason":"completed","stop_reason":"tool_use",'
        b'"permission_denials":[]}]'
    )
    envelope, observation = graphify_semantic_adapter.parse_result_envelope(raw)
    metadata = graphify_semantic_adapter._metadata(
        graphify_semantic_adapter.MetadataInputs(
            executable=Path("/bin/sh"),
            version="test",
            argv=(),
            environment={},
            auth=graphify_semantic_slice.AuthIdentity(
                logged_in=True,
                auth_method="claude.ai",
                api_provider="firstParty",
                subscription_type="max",
            ),
            prompt=b"prompt",
            stdout=raw,
            stderr=b"",
            returncode=0,
            envelope=envelope,
            parse_observation=observation,
            elapsed_ms=1,
            reasons=(),
        )
    )

    assert metadata.parse_observation is not None
    assert metadata.parse_observation.status == "accepted-result-array"
    assert graphify_semantic_corpus._adapter_metadata_reasons(metadata) == []


def test_corrected_terminal_artifacts_remain_byte_identical() -> None:
    root = (
        Path(__file__).resolve().parents[1]
        / "docs/agents/evidence/issue-301/corrected-max-chunk-terminal"
    )
    expected = {
        "adapter-metadata.json": (
            "3630a9938b2f1d67bbcdb6bc5f2980e4b3a5c7b04fcae5f59e6695c43a0df92a"
        ),
        "prototype-receipt.json": (
            "440afc68da1f548dd88e3b633363239f289fddbac06ca75d04e4540e80e11074"
        ),
        "provider-boundary-start.json": (
            "0fb585e7cc1b19b5649990baef8710a9a28c89eeb8676458dd870adc774644c7"
        ),
        "provider-receipt.json": (
            "7bd4634e156ecd6afe9da5b6a569e216c159b95fd8d877a0cee801594e8ef961"
        ),
        "semantic-fragment.json": (
            "65e21f615cda6af21bb599ee7a521f26aaa10dc1d337edeb749574948fbb4d15"
        ),
        "stage-receipt.json": ("070abf2f683fe21cd86ef5a28c4ae91025cc5c3045e4b1b43d96712336bac867"),
    }

    assert {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(root.iterdir())
    } == expected


def test_corpus_refuses_provider_evidence_without_bound_parse_observation() -> None:
    root = (
        Path(__file__).resolve().parents[1]
        / "docs/agents/evidence/issue-301/corrected-max-chunk-terminal"
    )
    metadata = msgspec.json.decode(
        (root / "adapter-metadata.json").read_bytes(),
        type=graphify_semantic_adapter.AdapterMetadata,
        strict=True,
    )

    assert "provider-parse-observation-unavailable" in (
        graphify_semantic_corpus._adapter_metadata_reasons(metadata)
    )


def test_an_impossible_negative_cost_is_refused_like_an_over_budget_one(
    tmp_path: Path,
) -> None:
    """The cost check bounds BOTH ends, because only one end was a real bound.

    It checked `cost <= max` alone, so `total_cost_usd = -1.0` passed — an
    impossible cost, and exactly the shape a missing-value sentinel takes, which
    means an adapter that failed to observe the cost sailed through the check
    that exists to observe it. The slice validator has always checked
    `0.0 <= cost <= max`; this was the corpus copy of one rule drifting looser.

    Three arms off ONE real committed fixture: negative refused, over-budget
    refused, and the fixture's own cost accepted. The last is the control — the
    first two would both pass against a check that refuses everything.
    """
    root = (
        Path(__file__).resolve().parents[1]
        / "docs/agents/evidence/issue-301/corrected-max-chunk-terminal"
    )
    metadata = msgspec.json.decode(
        (root / "adapter-metadata.json").read_bytes(),
        type=graphify_semantic_adapter.AdapterMetadata,
        strict=True,
    )
    config = msgspec.json.decode(
        (_exact_graphify_plan(tmp_path) / "execution-config.json").read_bytes(),
        type=graphify_semantic_corpus.CorpusExecutionConfig,
        strict=True,
    )
    reason = "provider-adapter-cost-bound-exceeded"

    negative = msgspec.structs.replace(metadata, total_cost_usd=-1.0)
    assert reason in graphify_semantic_corpus._adapter_config_reasons(negative, config)

    over = msgspec.structs.replace(metadata, total_cost_usd=config.max_cost_usd + 1.0)
    assert reason in graphify_semantic_corpus._adapter_config_reasons(over, config)

    within = msgspec.structs.replace(metadata, total_cost_usd=0.0)
    assert reason not in graphify_semantic_corpus._adapter_config_reasons(within, config)


def test_file_backed_authority_converges_without_changing_planner_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    commit, tree = _source(source)
    candidate = tmp_path / "candidate"
    graphify_semantic_corpus.plan_source(
        source,
        candidate,
        source=graphify_semantic_corpus.SourcePin(ref="test-ref", commit=commit, tree=tree),
    )
    manifest_sha = hashlib.sha256((candidate / "manifest.json").read_bytes()).hexdigest()
    config_sha = hashlib.sha256((candidate / "execution-config.json").read_bytes()).hexdigest()
    exclusions_sha = hashlib.sha256((candidate / "exclusions.json").read_bytes()).hexdigest()
    advisories_sha = hashlib.sha256((candidate / "advisories.json").read_bytes()).hexdigest()
    planner_sha_before = hashlib.sha256(
        Path(graphify_semantic_corpus.__file__).read_bytes()
    ).hexdigest()
    authority_path = tmp_path / "reviewed-authority.json"
    authority_path.write_bytes(
        _canonical(
            {
                "advisories_sha256": advisories_sha,
                "execution_config_sha256": config_sha,
                "exclusions_sha256": exclusions_sha,
                "plan_manifest_sha256": manifest_sha,
                "schema_version": 1,
            }
        )
    )
    assert (
        graphify_semantic_corpus.verify_plan(
            candidate, source_root=source, authority_path=authority_path
        ).state
        == "complete"
    )
    assert hashlib.sha256(Path(graphify_semantic_corpus.__file__).read_bytes()).hexdigest() == (
        planner_sha_before
    )

    config_path = candidate / "execution-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["backend"] = "hostile-backend"
    config_path.write_bytes(_canonical(config))
    _rehash_plan(candidate)
    result = graphify_semantic_corpus.verify_plan(
        candidate, source_root=source, authority_path=authority_path
    )
    assert result.state == "failed"
    assert "config-contract-mismatch" in result.reasons


def test_semantic_slice_policy_drift_invalidates_existing_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    commit, tree = _source(source)
    candidate = tmp_path / "candidate"
    graphify_semantic_corpus.plan_source(
        source,
        candidate,
        source=graphify_semantic_corpus.SourcePin(ref="test-ref", commit=commit, tree=tree),
    )
    original_module_sha = graphify_semantic_corpus._module_sha

    def hostile_module_sha(module: ModuleType) -> str:
        if module is graphify_semantic_slice:
            return "f" * 64
        return original_module_sha(module)

    monkeypatch.setattr(graphify_semantic_corpus, "_module_sha", hostile_module_sha)

    verdict = graphify_semantic_corpus.verify_plan(candidate, source_root=source)

    assert "config-contract-mismatch" in verdict.reasons


def test_ledger_is_reconciled_to_real_source_inventory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    commit, tree = _source(source)
    candidate = tmp_path / "candidate"
    graphify_semantic_corpus.plan_source(
        source,
        candidate,
        source=graphify_semantic_corpus.SourcePin(ref="test-ref", commit=commit, tree=tree),
    )
    ledger_path = candidate / "chunk-ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["chunks"][0]["members"][0]["path"] = "fabricated.md"
    ledger_path.write_bytes(_canonical(ledger))
    config_path = candidate / "execution-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["chunk_ledger_sha256"] = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    config["cache_namespace_sha256"] = graphify_semantic_corpus.cache_namespace_for(config)
    config_path.write_bytes(_canonical(config))
    _rehash_plan(candidate)

    result = graphify_semantic_corpus.verify_plan(candidate, source_root=source)
    assert result.state == "failed"
    assert "ledger-member-inventory-mismatch" in result.reasons


def test_run_is_a_typed_refusal_before_execution_authority(tmp_path: Path, capsys) -> None:
    rc = graphify_semantic_corpus.corpus_main(tmp_path, ["run", str(tmp_path / "missing")])

    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_id"] == "graphify-semantic-corpus-abort/v0"
    assert payload["status"] == "aborted"
    assert payload["provider_calls"] == 0
    assert payload["reasons"] == ["plan-unavailable"]


def _first_chunk(candidate: Path) -> graphify_semantic_corpus.PlannedChunk:
    ledger = msgspec.json.decode(
        (candidate / "chunk-ledger.json").read_bytes(),
        type=graphify_semantic_corpus.ChunkLedger,
        strict=True,
    )
    assert len(ledger.chunks) == 1
    return ledger.chunks[0]


class _StageOverrides(msgspec.Struct, frozen=True):
    fragment: object | None = None
    provider_raw: bytes | None = None
    metadata_raw: bytes | None = None
    cache_namespace: str | None = None
    run_namespace: str | None = None


def _stage_real(
    candidate: Path,
    cache_root: Path,
    repo_root: Path,
    overrides: _StageOverrides | None = None,
) -> tuple[graphify_semantic_corpus.ChunkStageReceipt, str, graphify_semantic_corpus.PlannedChunk]:
    overrides = overrides or _StageOverrides()
    config = json.loads((candidate / "execution-config.json").read_text(encoding="utf-8"))
    resolved_namespace = overrides.run_namespace or config["cache_namespace_sha256"]
    real_provider_raw, real_metadata_raw = _real_provider_evidence(repo_root)
    chunk = _first_chunk(candidate)
    receipt = graphify_semantic_corpus.stage_chunk(
        candidate,
        cache_root,
        graphify_semantic_corpus.ChunkStageRequest(
            source_root=candidate.parent / "source",
            cache_namespace=(overrides.cache_namespace or config["cache_namespace_sha256"]),
            run_namespace=resolved_namespace,
            chunk=chunk,
            fragment=(
                _real_fragment(repo_root) if overrides.fragment is None else overrides.fragment
            ),
            provider_evidence=graphify_semantic_corpus.RetainedProviderEvidence(
                overrides.provider_raw or real_provider_raw,
                overrides.metadata_raw or real_metadata_raw,
            ),
        ),
    )
    return receipt, resolved_namespace, chunk


def _verify_real_stage(
    candidate: Path,
    cache_root: Path,
    run_namespace: str,
    chunk: graphify_semantic_corpus.PlannedChunk,
) -> graphify_semantic_corpus.ChunkStageVerification:
    config = json.loads((candidate / "execution-config.json").read_text(encoding="utf-8"))
    return graphify_semantic_corpus.verify_staged_chunk(
        cache_root,
        graphify_semantic_corpus.ChunkStageReference(
            candidate=candidate,
            source_root=candidate.parent / "source",
            cache_namespace=config["cache_namespace_sha256"],
            run_namespace=run_namespace,
            chunk=chunk,
        ),
    )


def test_chunk_staging_retains_inherited_real_candidate_but_refuses_it_for_corpus_execution(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).parent.parent
    candidate = _execution_plan(tmp_path, repo_root)
    receipt, namespace, chunk = _stage_real(candidate, tmp_path / "cache", repo_root)
    assert receipt.status == "failed"
    assert "provider-token-budget-mismatch" in receipt.reasons
    assert "provider-chunk-size-mismatch" in receipt.reasons
    assert "provider-deep-mode-mismatch" in receipt.reasons
    verified = _verify_real_stage(candidate, tmp_path / "cache", namespace, chunk)
    assert verified.state == "failed"
    assert "provider-token-budget-mismatch" in verified.reasons

    staged = tmp_path / "cache" / namespace / "chunks/0001/semantic-fragment.json"
    staged.write_bytes(b'{"nodes":[]}\n')
    rejected = _verify_real_stage(candidate, tmp_path / "cache", namespace, chunk)
    assert rejected.state == "failed"
    assert "fragment-digest-mismatch" in rejected.reasons
    assert "fragment-invalid" in rejected.reasons


def test_chunk_stage_retains_and_rejects_forged_plan_and_runtime_bindings(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).parent.parent
    candidate = _execution_plan(tmp_path, repo_root)
    provider_raw, metadata_raw = _real_provider_evidence(repo_root)
    provider = json.loads(provider_raw)
    provider["chunks"][0]["source_git_object"] = "0" * 40
    provider["chunks"][0]["source_size"] += 1
    provider["chunks"][0]["ordinal"] = 2
    provider["chunks"][0]["prompt_sha256"] = "f" * 64
    metadata = json.loads(metadata_raw)
    schema_index = metadata["argv"].index("--json-schema") + 1
    metadata["argv"][schema_index] = '{"type":"array"}'
    model_index = metadata["argv"].index("--model") + 1
    metadata["argv"][model_index] = "forged-model"

    receipt, namespace, chunk = _stage_real(
        candidate,
        tmp_path / "forged",
        repo_root,
        _StageOverrides(
            provider_raw=_canonical(provider),
            metadata_raw=_canonical(metadata),
        ),
    )

    assert receipt.status == "failed"
    assert "provider-source-evidence-mismatch" in receipt.reasons
    assert "provider-chunk-ordinal-total-mismatch" in receipt.reasons
    assert "provider-prompt-identity-mismatch" in receipt.reasons
    assert "provider-schema-identity-mismatch" in receipt.reasons
    assert "provider-adapter-argv-mismatch" in receipt.reasons
    retained = tmp_path / "forged" / namespace / "chunks/0001/provider-receipt.json"
    assert retained.read_bytes() == _canonical(provider)
    verified = _verify_real_stage(candidate, tmp_path / "forged", namespace, chunk)
    assert verified.state == "failed"
    assert "provider-source-evidence-mismatch" in verified.reasons


def test_chunk_stage_rejects_coherently_rehashed_runtime_and_prompt_identity(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).parent.parent
    candidate = _execution_plan(tmp_path, repo_root)
    provider_raw, metadata_raw = _real_provider_evidence(repo_root)
    provider = json.loads(provider_raw)
    metadata = json.loads(metadata_raw)
    forged_sha = "f" * 64
    provider["runtime"]["executable_sha256"] = forged_sha
    provider["runtime"]["help_sha256"] = forged_sha
    provider["runtime"]["graphify_version"] = "0.9.43"
    provider["runtime"]["graphify_runtime"]["version"] = "0.9.43"
    provider["runtime"]["graphify_semantic_fingerprint_sha256"] = forged_sha
    metadata["claude_executable_sha256"] = forged_sha
    metadata["prompt_sha256"] = forged_sha
    provider["chunks"][0]["prompt_sha256"] = forged_sha
    changed_metadata = _canonical(metadata)
    provider["adapter_metadata_sha256"] = hashlib.sha256(changed_metadata).hexdigest()

    receipt, _, _ = _stage_real(
        candidate,
        tmp_path / "coherent-forgery",
        repo_root,
        _StageOverrides(
            provider_raw=_canonical(provider),
            metadata_raw=changed_metadata,
        ),
    )

    assert receipt.status == "failed"
    assert "provider-executable-identity-mismatch" in receipt.reasons
    assert "provider-help-identity-mismatch" in receipt.reasons
    assert "provider-graphify-runtime-mismatch" in receipt.reasons
    assert "provider-semantic-fingerprint-mismatch" in receipt.reasons
    assert "provider-prompt-bytes-mismatch" in receipt.reasons


def test_stage_distinguishes_config_cache_namespace_from_fresh_run_namespace(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).parent.parent
    candidate = _execution_plan(tmp_path, repo_root)

    receipt, _, _ = _stage_real(
        candidate,
        tmp_path / "variance",
        repo_root,
        _StageOverrides(run_namespace="d" * 64),
    )

    assert "stage-cache-namespace-mismatch" not in receipt.reasons
    assert "stage-run-namespace-invalid" not in receipt.reasons

    hostile, _, _ = _stage_real(
        candidate,
        tmp_path / "hostile-cache",
        repo_root,
        _StageOverrides(cache_namespace="e" * 64, run_namespace="d" * 64),
    )
    assert "stage-cache-namespace-mismatch" in hostile.reasons

    with pytest.raises(ValueError, match="run namespace"):
        _stage_real(
            candidate,
            tmp_path / "invalid-run",
            repo_root,
            _StageOverrides(run_namespace="not-a-sha"),
        )


def test_chunk_stage_rejects_invalid_references_and_symlinked_members(tmp_path: Path) -> None:
    repo_root = Path(__file__).parent.parent
    candidate = _execution_plan(tmp_path, repo_root)
    fragment = _real_fragment(repo_root)
    nodes = fragment["nodes"]
    assert isinstance(nodes, list)
    assert isinstance(nodes[0], dict)
    nodes.append(dict(nodes[0]))
    invalid, _, _ = _stage_real(
        candidate, tmp_path / "invalid", repo_root, _StageOverrides(fragment=fragment)
    )
    assert invalid.status == "failed"
    assert "duplicate-semantic-node-identity" in invalid.reasons

    valid = _real_fragment(repo_root)
    _, namespace, chunk = _stage_real(
        candidate, tmp_path / "symlink", repo_root, _StageOverrides(fragment=valid)
    )
    staged = tmp_path / "symlink" / namespace / "chunks/0001/semantic-fragment.json"
    external = tmp_path / "external.json"
    shutil.copyfile(staged, external)
    staged.unlink()
    staged.symlink_to(external)
    result = _verify_real_stage(candidate, tmp_path / "symlink", namespace, chunk)
    assert result.state == "failed"
    assert "chunk-entry-not-regular:semantic-fragment.json" in result.reasons

    _, fifo_namespace, chunk = _stage_real(
        candidate, tmp_path / "fifo", repo_root, _StageOverrides(fragment=valid)
    )
    staged_receipt = tmp_path / "fifo" / fifo_namespace / "chunks/0001/receipt.json"
    staged_receipt.unlink()
    os.mkfifo(staged_receipt)
    fifo_result = _verify_real_stage(candidate, tmp_path / "fifo", fifo_namespace, chunk)
    assert fifo_result.state == "failed"
    assert "chunk-entry-not-regular:receipt.json" in fifo_result.reasons


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("warnings", ["real warning"], "provider-warning-bearing"),
        ("errors", ["real error"], "provider-error-bearing"),
        ("uncovered_files", ["docs/how-it-works.md"], "provider-uncovered-files"),
        ("out_of_scope_dropped", 1, "provider-out-of-scope-dropped"),
    ],
)
def test_chunk_stage_retains_and_rejects_provider_diagnostics(
    tmp_path: Path, field: str, value: object, reason: str
) -> None:
    repo_root = Path(__file__).parent.parent
    candidate = _execution_plan(tmp_path, repo_root)
    fragment = _real_fragment(repo_root)
    provider_raw, metadata_raw = _real_provider_evidence(repo_root)
    provider = json.loads(provider_raw)
    provider[field] = value
    changed_provider_raw = _canonical(provider)
    receipt, namespace, chunk = _stage_real(
        candidate,
        tmp_path / "diagnostic",
        repo_root,
        _StageOverrides(
            fragment=fragment,
            provider_raw=changed_provider_raw,
            metadata_raw=metadata_raw,
        ),
    )

    assert receipt.status == "failed"
    assert reason in receipt.reasons
    retained = tmp_path / "diagnostic" / namespace / "chunks/0001/provider-receipt.json"
    assert retained.read_bytes() == changed_provider_raw
    verified = _verify_real_stage(candidate, tmp_path / "diagnostic", namespace, chunk)
    assert verified.state == "failed"
    assert reason in verified.reasons


def test_chunk_stage_retains_and_rejects_truncation(tmp_path: Path) -> None:
    repo_root = Path(__file__).parent.parent
    candidate = _execution_plan(tmp_path, repo_root)
    fragment = _real_fragment(repo_root)
    provider_raw, metadata_raw = _real_provider_evidence(repo_root)
    metadata = json.loads(metadata_raw)
    metadata["stop_reason"] = "max_tokens"
    changed_metadata_raw = _canonical(metadata)
    receipt, namespace, _ = _stage_real(
        candidate,
        tmp_path / "truncated",
        repo_root,
        _StageOverrides(
            fragment=fragment,
            provider_raw=provider_raw,
            metadata_raw=changed_metadata_raw,
        ),
    )

    assert receipt.status == "failed"
    assert "provider-truncated-or-incomplete" in receipt.reasons
    retained = tmp_path / "truncated" / namespace / "chunks/0001/adapter-metadata.json"
    assert retained.read_bytes() == changed_metadata_raw


class _EvidenceSpec(msgspec.Struct, frozen=True):
    mode: str
    provider_calls: int
    run_namespace: str
    fragment_ledger_sha256: str
    graph_sha256: str
    counts: tuple[int, int, int]


class _RunSpec(msgspec.Struct, frozen=True):
    mode: str
    provider_calls: int
    run_namespace: str


def _execution_evidence(
    candidate: Path, spec: _EvidenceSpec
) -> graphify_semantic_corpus.RunEvidence:
    inventory = json.loads((candidate / "source-inventory.json").read_text(encoding="utf-8"))
    ledger = json.loads((candidate / "chunk-ledger.json").read_text(encoding="utf-8"))
    config = json.loads((candidate / "execution-config.json").read_text(encoding="utf-8"))
    chunk_count = len(ledger["chunks"])
    namespace = config["cache_namespace_sha256"]
    return graphify_semantic_corpus.RunEvidence(
        mode=spec.mode,
        plan_manifest_sha256=hashlib.sha256((candidate / "manifest.json").read_bytes()).hexdigest(),
        execution_config_sha256=hashlib.sha256(
            (candidate / "execution-config.json").read_bytes()
        ).hexdigest(),
        exclusions_sha256=hashlib.sha256((candidate / "exclusions.json").read_bytes()).hexdigest(),
        source_inventory_sha256=hashlib.sha256(
            (candidate / "source-inventory.json").read_bytes()
        ).hexdigest(),
        chunk_ledger_sha256=hashlib.sha256(
            (candidate / "chunk-ledger.json").read_bytes()
        ).hexdigest(),
        source_commit=inventory["source_commit"],
        source_tree=inventory["source_tree"],
        cache_namespace_sha256=namespace,
        run_namespace_sha256=spec.run_namespace,
        chunk_count=chunk_count,
        completed_chunks=chunk_count,
        provider_calls=spec.provider_calls,
        failed_chunks=0,
        uncovered_units=0,
        fragment_ledger_sha256=spec.fragment_ledger_sha256,
        graph_sha256=spec.graph_sha256,
        covered_units=inventory["admitted_unit_count"],
        semantic_node_count=spec.counts[0],
        semantic_edge_count=spec.counts[1],
        semantic_hyperedge_count=spec.counts[2],
        graph_node_count=spec.counts[0],
        graph_edge_count=spec.counts[1],
        graph_hyperedge_count=spec.counts[2],
        warnings=(),
        errors=(),
    )


def _execution_plan(tmp_path: Path, repo_root: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init", "-q")
    _git(source, "config", "user.email", "corpus@example.invalid")
    _git(source, "config", "user.name", "Corpus Contract")
    (source / "docs").mkdir()
    shutil.copyfile(
        repo_root / "sources/graphify/docs/how-it-works.md",
        source / "docs/how-it-works.md",
    )
    (source / "filler.py").write_text("semantic = 1\n" * 50_100, encoding="utf-8")
    _git(source, "add", "docs/how-it-works.md", "filler.py")
    _git(source, "commit", "-qm", "real semantic source")
    commit, tree = _git(source, "rev-parse", "HEAD"), _git(source, "rev-parse", "HEAD^{tree}")
    candidate = tmp_path / "candidate"
    graphify_semantic_corpus.plan_source(
        source,
        candidate,
        source=graphify_semantic_corpus.SourcePin(ref="test-ref", commit=commit, tree=tree),
    )
    return candidate


def _run_artifact(
    root: Path,
    candidate: Path,
    repo_root: Path,
    spec: _RunSpec,
) -> Path:
    ledger = msgspec.json.decode(
        (candidate / "chunk-ledger.json").read_bytes(),
        type=graphify_semantic_corpus.ChunkLedger,
        strict=True,
    )
    assert len(ledger.chunks) == 1
    chunk = ledger.chunks[0]
    fragment = _real_fragment(repo_root)
    provider_raw, metadata_raw = _real_provider_evidence(repo_root)
    cache_root = root / f"{spec.mode}-cache"
    stage_receipt = graphify_semantic_corpus.stage_chunk(
        candidate,
        cache_root,
        graphify_semantic_corpus.ChunkStageRequest(
            source_root=candidate.parent / "source",
            cache_namespace=json.loads(
                (candidate / "execution-config.json").read_text(encoding="utf-8")
            )["cache_namespace_sha256"],
            run_namespace=spec.run_namespace,
            chunk=chunk,
            fragment=fragment,
            provider_evidence=graphify_semantic_corpus.RetainedProviderEvidence(
                provider_raw, metadata_raw
            ),
        ),
    )
    assert stage_receipt.status == "failed"
    run_root = cache_root / spec.run_namespace
    destination = run_root / "chunks/0001"
    member = graphify_semantic_corpus.RunFragmentMember(
        chunk_ordinal=1,
        chunk_sha256=hashlib.sha256(_canonical(msgspec.to_builtins(chunk))).hexdigest(),
        unit_ordinals=tuple(item.unit_ordinal for item in chunk.members),
        source_paths=("docs/how-it-works.md",),
        stage_receipt_sha256=hashlib.sha256(
            (destination / "receipt.json").read_bytes()
        ).hexdigest(),
        provider_receipt_sha256=hashlib.sha256(
            (destination / "provider-receipt.json").read_bytes()
        ).hexdigest(),
        adapter_metadata_sha256=hashlib.sha256(
            (destination / "adapter-metadata.json").read_bytes()
        ).hexdigest(),
        fragment_sha256=hashlib.sha256(
            (destination / "semantic-fragment.json").read_bytes()
        ).hexdigest(),
        node_count=stage_receipt.node_count,
        edge_count=stage_receipt.edge_count,
        hyperedge_count=stage_receipt.hyperedge_count,
    )
    config = json.loads((candidate / "execution-config.json").read_text(encoding="utf-8"))
    fragment_ledger = graphify_semantic_corpus.RunFragmentLedger(
        cache_namespace_sha256=config["cache_namespace_sha256"],
        run_namespace_sha256=spec.run_namespace,
        members=(member,),
    )
    fragment_ledger_raw = _canonical(msgspec.to_builtins(fragment_ledger))
    (run_root / "fragment-ledger.json").write_bytes(fragment_ledger_raw)
    graph_raw = _canonical(
        {
            "hyperedges": fragment["hyperedges"],
            "links": fragment["edges"],
            "nodes": fragment["nodes"],
        }
    )
    (run_root / "graph.json").write_bytes(graph_raw)
    evidence = _execution_evidence(
        candidate,
        _EvidenceSpec(
            spec.mode,
            spec.provider_calls,
            spec.run_namespace,
            hashlib.sha256(fragment_ledger_raw).hexdigest(),
            hashlib.sha256(graph_raw).hexdigest(),
            (stage_receipt.node_count, stage_receipt.edge_count, stage_receipt.hyperedge_count),
        ),
    )
    (run_root / "run-receipt.json").write_bytes(_canonical(msgspec.to_builtins(evidence)))
    return run_root


def _authority(candidate: Path, destination: Path) -> Path:
    destination.write_bytes(
        _canonical(
            {
                "advisories_sha256": hashlib.sha256(
                    (candidate / "advisories.json").read_bytes()
                ).hexdigest(),
                "execution_config_sha256": hashlib.sha256(
                    (candidate / "execution-config.json").read_bytes()
                ).hexdigest(),
                "exclusions_sha256": hashlib.sha256(
                    (candidate / "exclusions.json").read_bytes()
                ).hexdigest(),
                "plan_manifest_sha256": hashlib.sha256(
                    (candidate / "manifest.json").read_bytes()
                ).hexdigest(),
                "schema_version": 1,
            }
        )
    )
    return destination


def test_execution_namespace_contract_accepts_fresh_variance_and_rejects_reuse(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).parent.parent
    candidate = _execution_plan(tmp_path, repo_root)
    binding = graphify_semantic_corpus._plan_binding(candidate)
    common = _EvidenceSpec(
        "cold",
        1,
        binding.cache_namespace_sha256,
        "a" * 64,
        "b" * 64,
        (13, 8, 1),
    )
    cold = _execution_evidence(candidate, common)
    variance = _execution_evidence(
        candidate,
        msgspec.structs.replace(
            common,
            mode="variance",
            run_namespace="d" * 64,
        ),
    )

    assert graphify_semantic_corpus._variance_reasons(cold, variance, binding) == []
    hostile = msgspec.structs.replace(variance, run_namespace_sha256=cold.run_namespace_sha256)
    assert graphify_semantic_corpus._variance_reasons(cold, hostile, binding) == [
        "variance-namespace-not-fresh"
    ]


def test_execution_mode_verifier_refuses_inherited_slice_as_corpus_evidence(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).parent.parent
    candidate = _execution_plan(tmp_path, repo_root)
    config = json.loads((candidate / "execution-config.json").read_text(encoding="utf-8"))
    namespace = config["cache_namespace_sha256"]
    cold = _run_artifact(tmp_path, candidate, repo_root, _RunSpec("cold", 1, namespace))
    reuse = _run_artifact(tmp_path, candidate, repo_root, _RunSpec("reuse", 0, namespace))
    rebuild = _run_artifact(
        tmp_path,
        candidate,
        repo_root,
        _RunSpec("rebuild", 0, namespace),
    )
    variance = _run_artifact(
        tmp_path,
        candidate,
        repo_root,
        _RunSpec("variance", 1, "d" * 64),
    )
    authority = _authority(candidate, tmp_path / "authority.json")

    refused = graphify_semantic_corpus.verify_execution_modes(
        candidate,
        candidate.parent / "source",
        graphify_semantic_corpus.ExecutionRunSet(cold, reuse, rebuild, variance),
        authority_path=authority,
    )
    assert refused.state == "failed"
    assert any("provider-token-budget-mismatch" in reason for reason in refused.reasons)
    assert any("run-semantic-graph-unreconstructable" in reason for reason in refused.reasons)
    (reuse / "provider-only-fabrication.json").write_bytes(b"{}\n")
    rejected = graphify_semantic_corpus.verify_execution_modes(
        candidate,
        candidate.parent / "source",
        graphify_semantic_corpus.ExecutionRunSet(cold, reuse, rebuild, variance),
        authority_path=authority,
    )
    assert rejected.state == "failed"
    assert "reuse:run-artifact-entry-set-mismatch" in rejected.reasons


def test_semantic_graph_is_rebuilt_from_retained_real_fragment_bytes(tmp_path: Path) -> None:
    repo_root = Path(__file__).parent.parent
    candidate = _execution_plan(tmp_path, repo_root)
    binding = graphify_semantic_corpus._plan_binding(candidate)
    fragment = _real_fragment(repo_root)

    rebuilt, reasons = graphify_semantic_corpus._semantic_graph_bytes([fragment], binding)

    assert reasons == []
    assert rebuilt is not None
    assert graphify_semantic_corpus._graph_counts(rebuilt) == (13, 8, 1)
    assert (
        graphify_semantic_corpus._semantic_graph_integrity_reasons(
            rebuilt, {"docs/how-it-works.md"}
        )
        == []
    )

    hostile = json.loads(rebuilt)
    hostile["links"][0]["target"] = "fabricated-node"
    hostile_raw = _canonical(hostile)
    assert "run-graph-reference-invalid" in (
        graphify_semantic_corpus._semantic_graph_integrity_reasons(
            hostile_raw, {"docs/how-it-works.md"}
        )
    )
    assert hostile_raw != rebuilt


def test_execution_mode_verifier_rejects_fabricated_caller_structs(tmp_path: Path) -> None:
    repo_root = Path(__file__).parent.parent
    candidate = _execution_plan(tmp_path, repo_root)
    fabricated = _execution_evidence(
        candidate,
        _EvidenceSpec("cold", 1, "a" * 64, "b" * 64, "c" * 64, (100, 90, 2)),
    )
    result = graphify_semantic_corpus.verify_execution_modes(
        candidate,
        candidate.parent / "source",
        graphify_semantic_corpus.ExecutionRunSet(fabricated, fabricated, fabricated, fabricated),
    )
    assert result.state == "failed"
    assert result.reasons == ("execution-artifact-path-invalid",)
