# Copyright (c) 2026 Raymond Manaloto
"""Hermetic tests for managed Graphify process capture."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import cast

import pytest
from kb_setup import graphify_execution, graphify_sdk


def _identity(path: Path) -> dict[str, str]:
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "version": "fixture-python",
    }


@pytest.mark.parametrize(
    ("backend", "model", "effort"),
    [("claude-cli", "opus", "xhigh"), ("openai-cli", "gpt-5.6-sol", "high")],
)
def test_managed_profile_defaults(backend: str, model: str, effort: str) -> None:
    profile = graphify_execution.resolve_profile(
        backend,
        graphify_execution.ProfileSelection(
            environment={},
            identity={"path": "/fixture/cli", "sha256": "a" * 64, "version": "fixture"},
        ),
    )
    assert (profile["backend"], profile["model"], profile["effort"]) == (
        backend,
        model,
        effort,
    )
    assert profile["identity_policy"]["required_per_response"] is False


def test_profile_rejects_hidden_api_auth() -> None:
    with pytest.raises(ValueError, match="API authentication"):
        graphify_execution.resolve_profile(
            selection=graphify_execution.ProfileSelection(
                environment={"ANTHROPIC_API_KEY": "secret"},
                identity={"path": "/fixture/cli", "sha256": "a" * 64, "version": "fixture"},
            ),
        )


def test_safe_environment_does_not_merge_ambient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KB_AMBIENT_MUST_NOT_RETURN", "secret")
    result = graphify_execution.safe_child_environment({"ONLY_CAPTURED": "yes"})
    assert result == {"ONLY_CAPTURED": "yes"}


def test_real_runner_preserves_stdin_and_independent_binary_streams(tmp_path: Path) -> None:
    python = Path(sys.executable)
    request = {
        "argv": [
            str(python),
            "-c",
            (
                "import json,os,sys; data=sys.stdin.buffer.read(); "
                "sys.stdout.buffer.write(json.dumps({'stdin':data.hex(),'only':os.getenv('ONLY'),"
                "'ambient':os.getenv('KB_AMBIENT_MUST_NOT_RETURN')}).encode()+b'\\x00'); "
                "sys.stderr.buffer.write(b'err\\xff')"
            ),
        ],
        "stdin": b"prompt\x00bytes",
        "cwd": str(tmp_path),
        "timeout_seconds": 10,
        "output_contract": "stdout-json-envelope",
        "requested_profile": {"binary_expectation": _identity(python)},
    }
    os.environ["KB_AMBIENT_MUST_NOT_RETURN"] = "secret"
    try:
        overrides = graphify_execution.child_environment_override_evidence("claude-cli")
        result = graphify_execution.CapturedProcessRunner(
            tmp_path / "run", {"ONLY": "yes"}, environment_overrides=overrides
        )(request)
    finally:
        os.environ.pop("KB_AMBIENT_MUST_NOT_RETURN", None)
    payload = json.loads(result["stdout"].removesuffix(b"\x00"))
    assert payload == {"stdin": b"prompt\x00bytes".hex(), "only": "yes", "ambient": None}
    assert result["stderr"] == b"err\xff"
    assert Path(result["raw_capture_refs"]["stdout"]).read_bytes() == result["stdout"]
    assert Path(result["raw_capture_refs"]["stderr"]).read_bytes() == b"err\xff"
    environment_evidence = json.loads(
        Path(result["raw_capture_refs"]["environment_overrides"]).read_text()
    )
    assert environment_evidence == {
        "schema_version": 1,
        "scope": "selected_child_process",
        "overrides": list(overrides),
    }
    assert result["environment_overrides"] == list(overrides)


def test_runner_timeout_retains_partial_bytes(tmp_path: Path) -> None:
    python = Path(sys.executable)
    request = {
        "argv": [
            str(python),
            "-c",
            (
                "import sys,time; sys.stdout.buffer.write(b'before-timeout'); "
                "sys.stdout.flush(); time.sleep(5)"
            ),
        ],
        "stdin": b"",
        "cwd": str(tmp_path),
        "timeout_seconds": 0.05,
        "output_contract": "stdout-json-envelope",
        "requested_profile": {"binary_expectation": _identity(python)},
    }
    result = graphify_execution.CapturedProcessRunner(tmp_path / "run", {})(request)
    assert result["runner_error"] == "timed_out"
    assert result["stdout"] == b"before-timeout"
    assert result["finalized"] is True


def test_runner_timeout_bounds_drain_when_descendant_keeps_pipe_open(tmp_path: Path) -> None:
    python = Path(sys.executable)
    request = {
        "argv": [
            str(python),
            "-c",
            (
                "import subprocess,sys,time; "
                "subprocess.Popen([sys.executable,'-c','import time;time.sleep(1.5)'], "
                "start_new_session=True); "
                "sys.stdout.buffer.write(b'partial'); sys.stdout.flush(); time.sleep(5)"
            ),
        ],
        "stdin": b"",
        "cwd": str(tmp_path),
        "timeout_seconds": 0.1,
        "requested_profile": {"binary_expectation": _identity(python)},
    }
    runner = graphify_execution.CapturedProcessRunner(tmp_path / "run", {}, shutdown_seconds=0.1)
    started = time.monotonic()
    result = runner(request)
    assert time.monotonic() - started < 1.0
    assert result["runner_error"] == "timed_out_incomplete_capture"
    assert result["stdout"] == b"partial"
    assert result["stdout_eof"] is False
    assert result["stderr_eof"] is False
    assert result["finalized"] is False
    assert Path(result["raw_capture_refs"]["stdout"]).read_bytes() == b"partial"


@pytest.mark.parametrize(
    ("attempts", "seconds"),
    [(0, 10.0), (True, 10.0), (1, 0.0), (1, float("inf")), (1, "10")],
)
def test_execution_budget_rejects_invalid_limits(attempts: object, seconds: object) -> None:
    with pytest.raises(ValueError, match=r"positive|finite"):
        graphify_execution.ExecutionBudget(
            max_attempts=cast("int", attempts), total_seconds=cast("float", seconds)
        )


def test_execution_budget_refuses_n_plus_one_before_process_launch(tmp_path: Path) -> None:
    python = Path(sys.executable)
    marker = tmp_path / "launches"
    request = {
        "argv": [
            str(python),
            "-c",
            (
                "from pathlib import Path; p=Path('launches'); "
                "p.write_text(p.read_text()+'x' if p.exists() else 'x')"
            ),
        ],
        "stdin": b"",
        "cwd": str(tmp_path),
        "timeout_seconds": 2.0,
        "requested_profile": {"binary_expectation": _identity(python)},
    }
    runner = graphify_execution.CapturedProcessRunner(
        tmp_path / "run", {}, budget=graphify_execution.ExecutionBudget(1, 10.0)
    )
    assert runner(request)["returncode"] == 0
    assert marker.read_text() == "x"
    with pytest.raises(RuntimeError, match="attempt budget exhausted before launch"):
        runner(request)
    assert marker.read_text() == "x"
    assert not (tmp_path / "run" / "attempts" / "0002").exists()


def test_execution_budget_refuses_expired_deadline_before_process_launch(tmp_path: Path) -> None:
    python = Path(sys.executable)
    budget = graphify_execution.ExecutionBudget(2, 0.01)
    budget.started_monotonic = time.monotonic() - 1
    runner = graphify_execution.CapturedProcessRunner(tmp_path / "run", {}, budget=budget)
    request = {
        "argv": [str(python), "-c", "raise AssertionError('launched')"],
        "stdin": b"",
        "cwd": str(tmp_path),
        "requested_profile": {"binary_expectation": _identity(python)},
    }
    with pytest.raises(TimeoutError, match="deadline expired before launch"):
        runner(request)
    assert budget.attempts_started == 0
    assert not (tmp_path / "run" / "attempts").exists()


def test_runner_timeout_tolerates_child_exit_during_killpg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = Path(sys.executable)
    request = {
        "argv": [
            str(python),
            "-c",
            (
                "import sys,time; sys.stdout.buffer.write(b'before-race'); "
                "sys.stdout.flush(); time.sleep(5)"
            ),
        ],
        "stdin": b"",
        "cwd": str(tmp_path),
        "timeout_seconds": 0.05,
        "output_contract": "stdout-json-envelope",
        "requested_profile": {"binary_expectation": _identity(python)},
    }
    real_killpg = os.killpg

    def child_exited(pid: int, sig: int) -> None:
        real_killpg(pid, sig)
        raise ProcessLookupError

    monkeypatch.setattr(os, "killpg", child_exited)
    result = graphify_execution.CapturedProcessRunner(tmp_path / "run", {})(request)
    assert result["runner_error"] == "timed_out"
    assert result["stdout"] == b"before-race"
    assert result["finalized"] is True


def test_receipt_sink_acknowledges_exact_durable_bytes(tmp_path: Path) -> None:
    receipt = {"receipt_id": "r1", "completion": "completed"}
    ack = graphify_execution.DurableReceiptSink(tmp_path)(receipt)
    payload = Path(ack["durable_ref"]).read_bytes()
    assert ack == {
        "receipt_id": "r1",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "finalized": True,
        "durable_ref": str(tmp_path / "receipts" / "r1.json"),
    }


@pytest.mark.parametrize("backend", ["claude-cli", "openai-cli"])
def test_identified_and_unidentified_events_do_not_certify_complete_coverage(backend: str) -> None:
    chunk = {"nodes": [], "edges": []}
    payload = json.dumps(chunk).encode()
    parsed = graphify_execution.result_parser(backend)(
        {
            "returncode": 0,
            "stdout": json.dumps({"result": payload.decode()}).encode(),
            "result_artifact": {"payload": payload},
            "provider_events": [
                {"model": "opus", "response_id": "identified-response"},
                {"type": "assistant", "message": "identity not reported"},
            ],
        }
    )
    assert parsed["completion"] == "completed"
    assert parsed["value"] == chunk
    assert parsed["responses"] == [{"response_id": "identified-response", "reported_model": "opus"}]
    assert parsed["coverage"]["status"] == "unproved"
    assert "complete_response_coverage_unverified" in parsed["coverage"]["reasons"]


@pytest.mark.parametrize("marker", [None, False, 0, 1, "true"])
def test_public_profile_request_refuses_unresolved_or_legacy_profile(marker: object) -> None:
    with pytest.raises(ValueError, match="resolved explicit profile"):
        graphify_execution.public_profile_request({"_explicit": marker})


def test_public_profile_request_preserves_unknown_fields_for_sdk_rejection() -> None:
    from kb_setup import graphify_sdk

    profile = graphify_execution.resolve_profile(
        selection=graphify_execution.ProfileSelection(
            environment={},
            identity={"path": "/fixture/claude", "sha256": "a" * 64, "version": "fixture"},
        )
    )
    profile["_unknown"] = "must-not-be-silently-dropped"
    projected = graphify_execution.public_profile_request(profile)
    assert projected is not profile
    assert profile["_explicit"] is True
    assert "_explicit" not in projected
    assert projected["_unknown"] == "must-not-be-silently-dropped"
    with pytest.raises(ValueError, match="unknown execution_profile fields"):
        graphify_sdk.resolve_execution_profile_public(
            None, None, None, execution_profile=projected, purpose="extract", environment={}
        )


def test_claude_terminal_array_uses_only_unique_final_result() -> None:
    chunk = {"nodes": [], "edges": [], "hyperedges": []}
    events = [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": "not the result"}},
        {"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(chunk)},
    ]
    parsed = graphify_execution.result_parser("claude-cli")(
        {"returncode": 0, "stdout": json.dumps(events).encode(), "provider_events": events}
    )
    assert parsed["completion"] == "completed"
    assert parsed["value"] == chunk
    assert parsed["coverage"]["status"] == "unproved"


def test_provider_event_capture_preserves_every_array_event() -> None:
    events = [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": "work"}},
        {"type": "result", "subtype": "success", "is_error": False, "result": "{}"},
    ]
    assert graphify_execution._provider_events(json.dumps(events).encode()) == events


def test_claude_final_result_usage_is_recorded_without_inference() -> None:
    chunk = {"nodes": [], "edges": []}
    events = [
        {"type": "assistant", "usage": {"input_tokens": 999, "output_tokens": 999}},
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": json.dumps(chunk),
            "usage": {
                "input_tokens": 4,
                "output_tokens": 12,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 20,
            },
        },
    ]
    parsed = graphify_execution.result_parser("claude-cli")(
        {"returncode": 0, "stdout": json.dumps(events).encode(), "provider_events": events}
    )
    assert parsed["completion"] == "completed"
    assert parsed["usage"] == {
        "status": "known",
        "source_event": "result",
        "input_tokens": 4,
        "output_tokens": 12,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 20,
    }


def test_codex_completed_turn_usage_is_recorded_even_when_model_is_unreported() -> None:
    chunk = {"nodes": [], "edges": []}
    payload = json.dumps(chunk).encode()
    parsed = graphify_execution.result_parser("openai-cli")(
        {
            "returncode": 0,
            "stdout": b"",
            "result_artifact": {"payload": payload},
            "provider_events": [
                {"type": "item.completed", "usage": {"input_tokens": 999}},
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 29675,
                        "output_tokens": 7860,
                        "cached_input_tokens": 0,
                        "reasoning_output_tokens": 1552,
                    },
                },
            ],
        }
    )
    assert parsed["completion"] == "completed"
    assert parsed["usage"] == {
        "status": "known",
        "source_event": "turn.completed",
        "input_tokens": 29675,
        "output_tokens": 7860,
        "cached_input_tokens": 0,
        "reasoning_output_tokens": 1552,
    }
    assert parsed["responses"] == []


@pytest.mark.parametrize("bad_count", [None, True, -1, "7"])
def test_invalid_provider_usage_is_explicitly_unknown(bad_count: object) -> None:
    parsed = graphify_execution.result_parser("openai-cli")(
        {
            "returncode": 1,
            "stdout": b"",
            "provider_events": [
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 2, "output_tokens": bad_count},
                }
            ],
        }
    )
    assert parsed["completion"] == "failed"
    assert parsed["usage"] == {"status": "unknown", "reason": "provider_usage_invalid"}


def test_timeout_without_usage_event_is_explicitly_unknown() -> None:
    parsed = graphify_execution.result_parser("claude-cli")(
        {"runner_error": "timed_out", "returncode": -9, "stdout": b"", "provider_events": []}
    )
    assert parsed["completion"] == "timed_out"
    assert parsed["usage"] == {"status": "unknown", "reason": "provider_usage_event_missing"}


@pytest.mark.parametrize(
    "events",
    [
        [{"type": "assistant", "result": '{"nodes": []}'}],
        [
            {"type": "result", "result": '{"nodes": []}'},
            {"type": "result", "result": '{"nodes": []}'},
        ],
        [{"type": "result", "is_error": True, "result": '{"nodes": []}'}],
        [
            {"type": "result", "result": '{"nodes": []}'},
            {"type": "assistant", "message": "after terminal"},
        ],
        [
            {"type": "assistant", "message": {"content": '{"nodes": []}'}},
            {"type": "result", "subtype": "success", "result": "The chunk is delivered."},
        ],
        [
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": '{"nodes": []}',
            }
        ],
    ],
)
def test_claude_terminal_array_rejects_error_ambiguity_and_nonterminal_graph(events: list) -> None:
    with pytest.raises((ValueError, TypeError), match=r"terminal|error|JSON|arrays"):
        graphify_execution.result_parser("claude-cli")(
            {"returncode": 0, "stdout": json.dumps(events).encode(), "provider_events": events}
        )


def test_claude_leaf_brief_override_preserves_other_routing_and_discovery() -> None:
    environment = {
        "CLAUDE_CODE_BRIEF": "1",
        "CLAUDE_CODE_FORK_SUBAGENT": "1",
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
        "PATH": "/fixture",
        "KB_PROJECT_CONFIGURATION": "retain",
    }
    child = graphify_execution.safe_child_environment(environment, backend="claude-cli")
    assert child == {key: value for key, value in environment.items() if key != "CLAUDE_CODE_BRIEF"}
    assert environment["CLAUDE_CODE_BRIEF"] == "1"
    assert (
        graphify_execution.safe_child_environment(environment, backend="openai-cli") == environment
    )


def _admitted_raster(tmp_path: Path) -> tuple[Path, Path, dict]:
    from graphify.raster import preflight_raster_batch, raster_attachment_source_records
    from PIL import Image

    source_root = tmp_path / "source"
    source_root.mkdir()
    image = source_root / "graph.png"
    Image.new("RGB", (2, 2), "red").save(image)
    preflight = preflight_raster_batch(
        [{"path": str(image), "label": "graph.png"}], root=source_root
    )
    record = raster_attachment_source_records(preflight)[0]
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700)
    request = {
        "schema_version": 1,
        "operation": "stage_raster_attachment",
        "snapshot_root": str(run_root / "attachments"),
        "source_record": record,
        "preflight_identity": record["preflight"]["identity"],
        "decoder": record["preflight"]["decoder"],
        "batch_sha256": record["preflight"]["batch_sha256"],
        "limits": record["preflight"]["limits"],
    }
    return source_root, image, request


def test_durable_raster_ack_is_verified_by_real_public_protocol(tmp_path: Path) -> None:
    from graphify.raster import verify_raster_snapshot_ack

    source_root, image, request = _admitted_raster(tmp_path)
    snapshot_root = Path(request["snapshot_root"])
    ack = graphify_execution.CapturedRasterStager(snapshot_root, source_root)(request)
    attachment = verify_raster_snapshot_ack(
        ack, source_record=request["source_record"], snapshot_root=snapshot_root
    )
    assert Path(ack["transport_path"]).read_bytes() == image.read_bytes()
    assert json.loads(Path(ack["receipt_ref"]).read_text()) == ack
    assert attachment["storage_mode"] == "durable"
    assert attachment["lifecycle"]["scope"] == "caller_retained"


@pytest.mark.parametrize("mutation", ["root", "source_hash", "outside_source"])
def test_durable_raster_stager_rejects_wrong_root_or_changed_source(
    tmp_path: Path, mutation: str
) -> None:
    source_root, image, request = _admitted_raster(tmp_path)
    snapshot_root = Path(request["snapshot_root"])
    if mutation == "root":
        request["snapshot_root"] = str(tmp_path / "other")
    elif mutation == "source_hash":
        image.write_bytes(image.read_bytes() + b"changed")
    else:
        request["source_record"]["original_source"]["canonical_path"] = str(
            tmp_path / "outside.png"
        )
    with pytest.raises(ValueError, match=r"root|source|bytes"):
        graphify_execution.CapturedRasterStager(snapshot_root, source_root)(request)
    assert not snapshot_root.exists()


@pytest.mark.parametrize("child", ["raw", "receipts"])
def test_durable_raster_stager_rejects_child_directory_symlink_without_outside_write(
    tmp_path: Path, child: str
) -> None:
    source_root, _image, request = _admitted_raster(tmp_path)
    snapshot_root = Path(request["snapshot_root"])
    snapshot_root.mkdir(parents=True, mode=0o700)
    snapshot_root.chmod(0o700)
    outside = tmp_path / "outside"
    outside.mkdir()
    (snapshot_root / child).symlink_to(outside, target_is_directory=True)

    with pytest.raises(OSError, match=r"directory|unsafe"):
        graphify_execution.CapturedRasterStager(snapshot_root, source_root)(request)

    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "dotted_name",
    [
        "graphify.raster.stage_ephemeral_raster_attachments",
        "graphify.raster.verify_raster_snapshot_ack",
    ],
)
def test_raster_sdk_signature_drift_is_rejected(
    monkeypatch: pytest.MonkeyPatch, dotted_name: str
) -> None:
    symbols = tuple(
        graphify_sdk.PublicSymbol(symbol.dotted_name, lambda: None, symbol.expected_signature)
        if symbol.dotted_name == dotted_name
        else symbol
        for symbol in graphify_sdk._SEMANTIC_SYMBOLS
    )
    monkeypatch.setattr(graphify_sdk, "_SEMANTIC_SYMBOLS", symbols)
    monkeypatch.setattr(graphify_sdk, "running_sdk_version", lambda: "fixture")

    errors = graphify_sdk.semantic_contract_errors("fixture")

    assert any(dotted_name in error and "signature changed" in error for error in errors)


@pytest.mark.parametrize("mutation", ["staged_sha256", "finalized"])
def test_durable_raster_public_verifier_rejects_inexact_ack(tmp_path: Path, mutation: str) -> None:
    from graphify.raster import RasterPreflightError, verify_raster_snapshot_ack

    source_root, _image, request = _admitted_raster(tmp_path)
    snapshot_root = Path(request["snapshot_root"])
    ack = graphify_execution.CapturedRasterStager(snapshot_root, source_root)(request)
    ack[mutation] = "0" * 64 if mutation == "staged_sha256" else False
    with pytest.raises(RasterPreflightError):
        verify_raster_snapshot_ack(
            ack, source_record=request["source_record"], snapshot_root=snapshot_root
        )
