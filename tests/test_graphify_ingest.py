# Copyright (c) 2026 Raymond Manaloto
"""NORMAL ingestion prompt, cache, and metadata contract tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest
from kb_setup import graphify_execution, graphify_ingest, graphify_sdk


def _source(path: Path, **overrides: object) -> graphify_ingest.Source:
    values = {"key": "sample", "path": path, "url": "https://example.test/source", "kind": "doc"}
    values.update(overrides)
    return graphify_ingest.Source(
        key=cast("str", values["key"]),
        path=values["path"],
        url=cast("str", values["url"]),
        kind=cast("str", values["kind"]),
        note=cast("str", values.get("note", "")),
        source_file=cast("str | None", values.get("source_file")),
    )


def _chunk(source_file: str) -> dict:
    return {
        "nodes": [
            {
                "id": "sample_concept",
                "label": "Concept",
                "_origin": "semantic",
                "file_type": "concept",
                "source_file": source_file,
                "source_url": "https://example.test/source",
                "captured_at": "2026-09-14",
                "author": None,
                "contributor": None,
                "rationale": "The source states a concept.",
            }
        ],
        "edges": [],
        "hyperedges": [],
    }


def test_source_file_precedence_and_clone_root_qualification(tmp_path: Path) -> None:
    clone = tmp_path / "sources" / "graphify" / "README.md"
    assert graphify_ingest.source_file_for(_source(clone)) == "graphify/README.md"
    assert graphify_ingest.source_file_for(_source(clone, source_file="reviewed/readme.md")) == (
        "reviewed/readme.md"
    )
    assert graphify_ingest.source_file_for(_source(tmp_path / "raw" / "unique.md")) == "unique.md"


@pytest.mark.parametrize("value", ["", "2026-02-30", "1969-12-31", "2026-9-14"])
def test_captured_at_must_be_a_real_canonical_date(value: str) -> None:
    with pytest.raises(ValueError, match="real ISO date"):
        graphify_ingest.validate_captured_at(value)


def test_help_is_safe_without_a_request_or_provider(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert graphify_ingest.ingest_main(tmp_path, ["--help"]) == 0
    output = capsys.readouterr().out
    assert "mise run kb-graphify-ingest" in output
    assert "opus / gpt-5.6-sol" in output
    assert "xhigh / high" in output


def test_rendered_prompt_contains_bytes_and_all_metadata(tmp_path: Path) -> None:
    source = _source(
        tmp_path / "doc.md",
        source_file="qualified/doc.md",
        note="reviewed context",
    )
    prompt = graphify_ingest.render_prompt(source, "2026-09-14", b"complete source text")
    for expected in (
        "complete source text",
        "qualified/doc.md",
        "https://example.test/source",
        "2026-09-14",
        "reviewed context",
        '_origin     : "semantic"',
        "MEMBER -> CONTAINER",
    ):
        assert expected in prompt


def test_cache_miss_uses_identical_prompt_for_lookup_invoke_and_save(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source.md"
    source_path.write_text("all source bytes")
    source = _source(source_path)
    chunk = _chunk("source.md")
    seen: dict[str, str] = {}

    def cache(
        *args: object, **kwargs: object
    ) -> tuple[list[dict], list[dict], list[dict], list[str]]:
        seen["lookup"] = cast("str", kwargs["prompt"])
        return [], [], [], cast("list[str]", args[0])

    def build(prompt: str, **kwargs: object) -> dict:
        seen["invoke"] = prompt
        return {"timeout_seconds": None, "backend": "claude-cli", "argv": ["/fixture/claude"]}

    def run(*args: object, **kwargs: object) -> dict:
        assert cast("dict[str, object]", args[0])["argv"] == [
            "/fixture/claude",
            "--safe-mode",
            "--tools",
            "Read",
        ]
        return {
            "value": chunk,
            "receipt": {
                "receipt_id": "receipt-1",
                "completion": "completed",
                "coverage": {"status": "unproved", "reasons": ["served_model_identity_missing"]},
            },
        }

    def save(*args: object, **kwargs: object) -> int:
        seen["save"] = cast("str", kwargs["prompt"])
        return 1

    monkeypatch.setattr(graphify_sdk, "check_semantic_cache_public", cache)
    monkeypatch.setattr(graphify_sdk, "build_cli_invocation_public", build)
    monkeypatch.setattr(graphify_sdk, "run_cli_invocation_public", run)
    monkeypatch.setattr(graphify_sdk, "save_semantic_cache_public", save)
    result = graphify_ingest.ingest_source(
        graphify_ingest.IngestSourceRequest(
            repo_root=tmp_path,
            scratch_dir=tmp_path / ".agent" / "kb" / "graphify-ingest" / "scratch" / "chunks",
            source=source,
            captured_at="2026-09-14",
            profile={
                "_explicit": True,
                "backend": "claude-cli",
                "model": "opus",
                "effort": "xhigh",
            },
            run_root=tmp_path / ".agent" / "kb" / "graphify-ingest" / "runs" / "run",
        ),
        process_runner=lambda _request: {},
        receipt_sink=lambda _receipt: {},
    )
    assert seen["lookup"] == seen["invoke"] == seen["save"]
    assert result["cached"] is False
    assert json.loads(Path(result["output"]).read_text()) == chunk


def test_warm_cache_writes_chunk_without_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source.md"
    source_path.write_text("all source bytes")
    chunk = _chunk("source.md")

    def cache_hit(
        *_args: object, **_kwargs: object
    ) -> tuple[list[dict], list[dict], list[dict], list[str]]:
        return chunk["nodes"], [], [], []

    def unexpected_invocation(*_args: object, **_kwargs: object) -> dict:
        pytest.fail("warm cache must not invoke a CLI")

    monkeypatch.setattr(graphify_sdk, "check_semantic_cache_public", cache_hit)
    monkeypatch.setattr(graphify_sdk, "build_cli_invocation_public", unexpected_invocation)
    result = graphify_ingest.ingest_source(
        graphify_ingest.IngestSourceRequest(
            repo_root=tmp_path,
            scratch_dir=tmp_path / ".agent" / "kb" / "graphify-ingest" / "scratch" / "chunks",
            source=_source(source_path),
            captured_at="2026-09-14",
            profile={
                "_explicit": True,
                "backend": "claude-cli",
                "model": "opus",
                "effort": "xhigh",
            },
            run_root=tmp_path / ".agent" / "kb" / "graphify-ingest" / "runs" / "run",
        )
    )
    assert result["cached"] is True


def test_runner_exception_persists_incomplete_receipt_without_semantic_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class RunnerExplodedError(RuntimeError):
        graphify_attempt: dict

    source_path = tmp_path / "source.md"
    source_path.write_text("all source bytes")
    run_root = tmp_path / ".agent" / "kb" / "graphify-ingest" / "runs" / "failed-run"
    output_path = tmp_path / ".agent" / "kb" / "graphify-ingest" / "scratch" / "sample.json"
    profile = graphify_execution.resolve_profile(
        selection=graphify_execution.ProfileSelection(
            environment={},
            identity={"path": "/fixture/claude", "sha256": "a" * 64, "version": "fixture"},
        ),
    )

    def cache_miss(
        *args: object, **_kwargs: object
    ) -> tuple[list[dict], list[dict], list[dict], list[str]]:
        return [], [], [], cast("list[str]", args[0])

    def explode(_request: dict) -> dict:
        raise RunnerExplodedError("fixture runner failure")

    def unexpected_save(*_args: object, **_kwargs: object) -> int:
        pytest.fail("a failed attempt must not become semantic cache success")

    monkeypatch.setattr(graphify_sdk, "check_semantic_cache_public", cache_miss)
    monkeypatch.setattr(graphify_sdk, "save_semantic_cache_public", unexpected_save)
    with pytest.raises(RunnerExplodedError) as error:
        graphify_ingest.ingest_source(
            graphify_ingest.IngestSourceRequest(
                repo_root=tmp_path,
                scratch_dir=output_path.parent,
                source=_source(source_path),
                captured_at="2026-09-14",
                profile=profile,
                run_root=run_root,
            ),
            process_runner=explode,
        )

    attempt = error.value.graphify_attempt
    assert attempt["receipt"]["completion"] == "incomplete_capture"
    receipts = list((run_root / "receipts").glob("*.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text())["completion"] == "incomplete_capture"
    assert not output_path.exists()


def test_explicit_existing_run_root_is_refused_before_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source.md"
    source_path.write_text("source")
    run_root = tmp_path / ".agent" / "kb" / "graphify-ingest" / "runs" / "already-used"
    run_root.mkdir(parents=True)

    def unexpected_cache(*_args: object, **_kwargs: object) -> object:
        pytest.fail("an existing run root must be rejected before cache lookup")

    monkeypatch.setattr(graphify_sdk, "check_semantic_cache_public", unexpected_cache)
    with pytest.raises(FileExistsError, match="run root already exists"):
        graphify_ingest.ingest_source(
            graphify_ingest.IngestSourceRequest(
                repo_root=tmp_path,
                scratch_dir=(tmp_path / ".agent" / "kb" / "graphify-ingest" / "scratch" / "chunks"),
                source=_source(source_path),
                captured_at="2026-09-14",
                profile={
                    "_explicit": True,
                    "backend": "claude-cli",
                    "model": "opus",
                    "effort": "xhigh",
                },
                run_root=run_root,
            )
        )

    assert list(run_root.iterdir()) == []


def test_source_content_path_and_source_file_each_change_the_prompt(tmp_path: Path) -> None:
    first = _source(tmp_path / "a" / "doc.md")
    second = _source(tmp_path / "b" / "doc.md")
    baseline = graphify_ingest.render_prompt(first, "2026-09-14", b"one")
    assert graphify_ingest.render_prompt(first, "2026-09-14", b"two") != baseline
    assert graphify_ingest.render_prompt(second, "2026-09-14", b"one") != baseline
    assert (
        graphify_ingest.render_prompt(
            _source(first.path, source_file="explicit/doc.md"), "2026-09-14", b"one"
        )
        != baseline
    )


@pytest.mark.parametrize(
    "source_file",
    [
        "/escape/out.json",
        "../out.json",
        "a/../../out",
        "a\\b",
        "a//b",
        "a/./b",
        "a/",
    ],
)
def test_source_file_rejects_absolute_and_traversal(tmp_path: Path, source_file: str) -> None:
    with pytest.raises(ValueError, match="sourceFile"):
        graphify_ingest.source_file_for(_source(tmp_path / "doc.md", source_file=source_file))


@pytest.mark.parametrize("key", ["../escape", "a/b", ".hidden", "UPPER", ""])
def test_source_key_is_one_safe_component(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError, match="source key"):
        _source(tmp_path / "doc.md", key=key)


def test_request_with_unsafe_key_fails_before_runtime_or_profile_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source.md"
    source_path.write_text("source")
    task_root = tmp_path / ".agent" / "kb" / "graphify-ingest"
    protected = tmp_path / ".agent" / "kb" / "gates"
    protected.mkdir(parents=True)
    marker = protected / "keep.txt"
    marker.write_text("preserve")
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "capturedAt": "2026-09-14",
                "scratchDir": str(task_root / "scratch" / "valid"),
                "cacheRoot": str(task_root / "cache" / "valid"),
                "sources": [
                    {
                        "key": "../sibling",
                        "path": str(source_path),
                        "url": "https://example.test/source",
                        "kind": "doc",
                    }
                ],
            }
        )
    )

    def unexpected_profile(*_args: object, **_kwargs: object) -> dict:
        pytest.fail("an unsafe source key must fail before profile resolution")

    monkeypatch.setattr(graphify_execution, "resolve_profile", unexpected_profile)
    with pytest.raises(ValueError, match="source key"):
        graphify_ingest.ingest_main(tmp_path, [str(request)])

    assert not task_root.exists()
    assert marker.read_text() == "preserve"
    assert list(protected.iterdir()) == [marker]


def test_outside_scratch_root_is_refused_before_any_write(tmp_path: Path) -> None:
    source_path = tmp_path / "source.md"
    source_path.write_text("source")
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    with pytest.raises(ValueError, match="scratchDir"):
        graphify_ingest.ingest_source(
            graphify_ingest.IngestSourceRequest(
                repo_root=tmp_path,
                scratch_dir=outside,
                source=_source(source_path),
                captured_at="2026-09-14",
                profile={
                    "_explicit": True,
                    "backend": "claude-cli",
                    "model": "opus",
                    "effort": "xhigh",
                },
                run_root=tmp_path / ".agent" / "kb" / "graphify-ingest" / "runs" / "run",
            )
        )
    assert not outside.exists()


def test_symlinked_runtime_destination_cannot_escape(tmp_path: Path) -> None:
    source_path = tmp_path / "source.md"
    source_path.write_text("source")
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    runtime = tmp_path / ".agent" / "kb" / "graphify-ingest" / "scratch"
    runtime.mkdir(parents=True)
    (runtime / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="scratchDir"):
        graphify_ingest.ingest_source(
            graphify_ingest.IngestSourceRequest(
                repo_root=tmp_path,
                scratch_dir=runtime / "escape",
                source=_source(source_path),
                captured_at="2026-09-14",
                profile={
                    "_explicit": True,
                    "backend": "claude-cli",
                    "model": "opus",
                    "effort": "xhigh",
                },
                run_root=tmp_path / ".agent" / "kb" / "graphify-ingest" / "runs" / "run",
            )
        )
    assert list(outside.iterdir()) == []


def test_runtime_roots_reject_sibling_families_before_any_write(tmp_path: Path) -> None:
    source_path = tmp_path / "source.md"
    source_path.write_text("source")
    task_root = tmp_path / ".agent" / "kb" / "graphify-ingest"
    valid_scratch = task_root / "scratch" / "chunks"
    cases = [
        (
            "scratchDir",
            task_root / "runs" / "not-scratch",
            None,
            None,
        ),
        (
            "run root",
            valid_scratch,
            task_root / "scratch" / "not-run",
            None,
        ),
        (
            "cacheRoot",
            valid_scratch,
            None,
            task_root / "runs" / "not-cache",
        ),
    ]
    for label, scratch_dir, run_root, cache_root in cases:
        with pytest.raises(ValueError, match=label):
            graphify_ingest.ingest_source(
                graphify_ingest.IngestSourceRequest(
                    repo_root=tmp_path,
                    scratch_dir=scratch_dir,
                    source=_source(source_path),
                    captured_at="2026-09-14",
                    profile={
                        "_explicit": True,
                        "backend": "claude-cli",
                        "model": "opus",
                        "effort": "xhigh",
                    },
                    run_root=run_root,
                    cache_root=cache_root,
                )
            )

    assert not task_root.exists()


def test_valid_task_owned_runtime_families_write_only_expected_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source.md"
    source_path.write_text("source")
    task_root = tmp_path / ".agent" / "kb" / "graphify-ingest"
    chunk = _chunk("source.md")

    def cache_hit(
        *_args: object, **_kwargs: object
    ) -> tuple[list[dict], list[dict], list[dict], list[str]]:
        return chunk["nodes"], [], [], []

    monkeypatch.setattr(graphify_sdk, "check_semantic_cache_public", cache_hit)
    result = graphify_ingest.ingest_source(
        graphify_ingest.IngestSourceRequest(
            repo_root=tmp_path,
            scratch_dir=task_root / "scratch" / "chunks",
            source=_source(source_path),
            captured_at="2026-09-14",
            profile={
                "_explicit": True,
                "backend": "claude-cli",
                "model": "opus",
                "effort": "xhigh",
            },
            run_root=task_root / "runs" / "valid-run",
            cache_root=task_root / "cache" / "semantic",
        )
    )

    assert Path(result["output"]).is_file()
    assert Path(result["run_root"]).is_dir()
    assert not (tmp_path / ".agent" / "kb" / "gates").exists()
    assert not (tmp_path / ".agent" / "evidence").exists()


@pytest.mark.parametrize("backend", ["claude-cli", "openai-cli"])
def test_real_public_sdk_cold_save_warm_and_cross_profile_cache(
    tmp_path: Path, backend: str
) -> None:
    """Compose real profile/cache/invocation APIs; fake only external process I/O."""
    source_path = tmp_path / "source.md"
    source_path.write_text("all source bytes")
    task_root = tmp_path / ".agent" / "kb" / "graphify-ingest"
    chunk = _chunk("source.md")
    calls: list[dict] = []
    profile = graphify_execution.resolve_profile(
        backend,
        selection=graphify_execution.ProfileSelection(
            environment={},
            identity={"path": f"/fixture/{backend}", "sha256": "a" * 64, "version": "fixture"},
        ),
    )
    original = json.loads(json.dumps(profile))

    def runner(request: dict) -> dict:
        calls.append(request)
        payload = json.dumps({**chunk, "input_tokens": 0, "output_tokens": 0}).encode()
        envelope = {
            "type": "result",
            "result": payload.decode(),
            "model": request["requested_profile"]["model"],
            "response_id": f"fixture-response-{len(calls)}",
        }
        stdout = json.dumps(envelope).encode() if backend == "claude-cli" else b""
        capture = tmp_path / f"process-{len(calls)}"
        stdout_path, stderr_path, result_path = (
            capture / "stdout.bin",
            capture / "stderr.bin",
            capture / "result.bin",
        )
        graphify_execution.atomic_bytes(stdout_path, stdout)
        graphify_execution.atomic_bytes(stderr_path, b"")
        graphify_execution.atomic_bytes(result_path, payload)
        return {
            "returncode": 0,
            "stdout": stdout,
            "stderr": b"",
            "stdout_eof": True,
            "stderr_eof": True,
            "finalized": True,
            "binary": request["requested_profile"]["binary_expectation"],
            "raw_capture_refs": {"stdout": str(stdout_path), "stderr": str(stderr_path)},
            "provider_events": [envelope] if backend == "claude-cli" else [],
            "result_artifact": {
                "requested_path": request["output_path"],
                "payload": payload,
                "byte_count": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "raw_ref": str(result_path),
                "eof": True,
                "finalized": True,
            },
            "runner_error": None,
        }

    def ingest(run: str, selected: dict) -> dict:
        return graphify_ingest.ingest_source(
            graphify_ingest.IngestSourceRequest(
                repo_root=tmp_path,
                scratch_dir=task_root / "scratch" / run,
                source=_source(source_path),
                captured_at="2026-09-14",
                profile=selected,
                run_root=task_root / "runs" / run,
                cache_root=task_root / "cache" / "semantic",
            ),
            process_runner=runner,
        )

    cold = ingest("cold", profile)
    assert cold["cached"] is False
    assert len(calls) == 1
    assert json.loads(Path(cold["output"]).read_text()) == chunk
    cold_bytes = Path(cold["output"]).read_bytes()
    warm = ingest("warm", profile)
    assert warm["cached"] is True
    assert len(calls) == 1
    assert json.loads(Path(warm["output"]).read_text()) == chunk
    assert Path(warm["output"]).read_bytes() == cold_bytes
    assert warm["cache_evidence"]
    assert cold["receipt_id"] in {
        receipt["receipt_id"]
        for item in warm["cache_evidence"]
        for receipt in item["producer_receipts"]
    }
    assert not list(Path(warm["run_root"]).rglob("attempts/*"))
    other = graphify_execution.resolve_profile(
        backend,
        selection=graphify_execution.ProfileSelection(
            effort="medium" if backend == "openai-cli" else "high",
            environment={},
            identity={"path": f"/fixture/{backend}", "sha256": "a" * 64, "version": "fixture"},
        ),
    )
    cross_profile = ingest("cross-profile", other)
    assert cross_profile["cached"] is False
    assert len(calls) == 2
    assert profile == original
    assert profile["_explicit"] is True


@pytest.mark.parametrize("runner_outcome", ["completed", "raises"])
def test_openai_normal_cold_isolates_cli_cwd_and_retains_project_identity(
    tmp_path: Path, runner_outcome: str
) -> None:
    """Exercise the public cold path without starting a paid CLI process."""
    source_path = tmp_path / "source.md"
    source_path.write_text("all source bytes")
    project_config = tmp_path / ".codex" / "config.toml"
    project_config.parent.mkdir()
    project_config.write_text('[mcp_servers.project_fixture]\ncommand = "false"\n')
    task_root = tmp_path / ".agent" / "kb" / "graphify-ingest"
    profile = graphify_execution.resolve_profile(
        "openai-cli",
        graphify_execution.ProfileSelection(
            environment={},
            identity={"path": "/fixture/codex", "sha256": "b" * 64, "version": "fixture"},
        ),
    )
    calls: list[dict] = []

    def runner(invocation: dict) -> dict:
        calls.append(invocation)
        cli_cwd = Path(invocation["cwd"])
        assert cli_cwd.is_dir()
        assert not cli_cwd.resolve().is_relative_to(tmp_path.resolve())
        assert invocation["project_root"] == str(tmp_path.resolve())
        assert "--ignore-user-config" in invocation["argv"]
        if runner_outcome == "raises":
            raise RuntimeError("fixture runner failed")
        raw_root = task_root / "runner-fixture"
        stdout_path, stderr_path, result_path = (
            raw_root / "stdout.bin",
            raw_root / "stderr.bin",
            raw_root / "result.bin",
        )
        payload = json.dumps(_chunk("source.md")).encode()
        graphify_execution.atomic_bytes(stdout_path, b"")
        graphify_execution.atomic_bytes(stderr_path, b"")
        graphify_execution.atomic_bytes(result_path, payload)
        return {
            "returncode": 0,
            "stdout": b"",
            "stderr": b"",
            "stdout_eof": True,
            "stderr_eof": True,
            "finalized": True,
            "binary": profile["binary_expectation"],
            "raw_capture_refs": {"stdout": str(stdout_path), "stderr": str(stderr_path)},
            "result_artifact": {
                "requested_path": invocation["output_path"],
                "payload": payload,
                "byte_count": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "raw_ref": str(result_path),
                "eof": True,
                "finalized": True,
            },
            "provider_events": [],
            "runner_error": None,
        }

    request = graphify_ingest.IngestSourceRequest(
        repo_root=tmp_path,
        scratch_dir=task_root / "scratch" / "cold",
        source=_source(source_path),
        captured_at="2026-09-14",
        profile=profile,
        run_root=task_root / "runs" / "cold",
        cache_root=task_root / "cache" / "semantic",
    )
    if runner_outcome == "raises":
        with pytest.raises(RuntimeError, match="fixture runner failed"):
            graphify_ingest.ingest_source(request, process_runner=runner)
        run_root = task_root / "runs" / "cold"
    else:
        result = graphify_ingest.ingest_source(request, process_runner=runner)
        assert result["cached"] is False
        assert json.loads(Path(result["output"]).read_text()) == _chunk("source.md")
        run_root = Path(result["run_root"])
    assert len(calls) == 1
    assert not Path(calls[0]["cwd"]).exists()
    receipts = list((run_root / "receipts").glob("*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text())
    assert receipt["request"]["cwd"] == calls[0]["cwd"]
    assert receipt["run_context"]["project_root"] == str(tmp_path.resolve())
    assert receipt["completion"] == (
        "incomplete_capture" if runner_outcome == "raises" else "completed"
    )


@pytest.mark.parametrize("primary_output", [b"", b"partial-provider-output"])
def test_explicit_fallback_requires_zero_primary_work(
    tmp_path: Path, primary_output: bytes
) -> None:
    source_path = tmp_path / "source.md"
    source_path.write_text("all source bytes")
    task_root = tmp_path / ".agent" / "kb" / "graphify-ingest"
    identity = {"path": "/fixture/claude", "sha256": "a" * 64, "version": "fixture"}
    primary = graphify_execution.resolve_profile(
        selection=graphify_execution.ProfileSelection(environment={}, identity=identity)
    )
    fallback = graphify_execution.resolve_profile(
        selection=graphify_execution.ProfileSelection(
            model="sonnet", environment={}, identity=identity
        )
    )
    calls: list[dict] = []

    def runner(invocation: dict) -> dict:
        calls.append(invocation)
        first = len(calls) == 1
        success = json.dumps({"result": json.dumps(_chunk("source.md"))}).encode()
        stdout = primary_output if first else success
        retained = tmp_path / f"process-{len(calls)}"
        stdout_path, stderr_path = retained / "stdout.bin", retained / "stderr.bin"
        graphify_execution.atomic_bytes(stdout_path, stdout)
        graphify_execution.atomic_bytes(stderr_path, b"primary refused" if first else b"")
        return {
            "returncode": 7 if first else 0,
            "stdout": stdout,
            "stderr": b"primary refused" if first else b"",
            "stdout_eof": True,
            "stderr_eof": True,
            "finalized": True,
            "binary": invocation["requested_profile"]["binary_expectation"],
            "raw_capture_refs": {"stdout": str(stdout_path), "stderr": str(stderr_path)},
            "provider_events": [],
            "runner_error": None,
        }

    request = graphify_ingest.IngestSourceRequest(
        repo_root=tmp_path,
        scratch_dir=task_root / "scratch" / "fallback",
        source=_source(source_path),
        captured_at="2026-09-14",
        profile=primary,
        fallback_profile=fallback,
        cache_root=task_root / "cache" / "semantic",
    )
    if primary_output:
        with pytest.raises(RuntimeError, match="did not complete"):
            graphify_ingest.ingest_source(request, process_runner=runner)
        assert len(calls) == 1
    else:
        result = graphify_ingest.ingest_source(request, process_runner=runner)
        assert len(calls) == 2
        assert calls[0]["requested_profile"]["model"] == "opus"
        assert calls[1]["requested_profile"]["model"] == "sonnet"
        assert result["fallback_after_receipt"]
        assert Path(result["output"]).is_file()


@pytest.mark.parametrize("source_file", ["/outside/unrelated.md", "other/source.md"])
def test_cached_source_mapping_rejects_other_identities(tmp_path: Path, source_file: str) -> None:
    chunk = {"nodes": [{"id": "known", "source_file": source_file}], "edges": [], "hyperedges": []}
    with pytest.raises(ValueError, match="staged source identity"):
        graphify_ingest._portable_cached_chunk(
            chunk,
            staged_source=tmp_path / "cache-input" / "graphify" / "README.md",
            source_file="graphify/README.md",
        )
    assert chunk["nodes"][0]["source_file"] == source_file


def test_cached_source_mapping_preserves_metadata_and_input_across_buckets(tmp_path: Path) -> None:
    staged = tmp_path / "cache-input" / "graphify" / "README.md"
    chunk = {
        "nodes": [{"id": "node", "source_file": str(staged), "rationale": "literal evidence"}],
        "edges": [
            {"source": "node", "target": "other", "source_file": str(staged), "confidence": 1}
        ],
        "hyperedges": [{"id": "group", "source_file": "graphify/README.md", "members": ["node"]}],
    }
    original = json.loads(json.dumps(chunk))
    portable = graphify_ingest._portable_cached_chunk(
        chunk,
        staged_source=staged,
        source_file="graphify/README.md",
    )
    assert portable == {
        "nodes": [
            {"id": "node", "source_file": "graphify/README.md", "rationale": "literal evidence"}
        ],
        "edges": [
            {
                "source": "node",
                "target": "other",
                "source_file": "graphify/README.md",
                "confidence": 1,
            }
        ],
        "hyperedges": [{"id": "group", "source_file": "graphify/README.md", "members": ["node"]}],
    }
    assert chunk == original
