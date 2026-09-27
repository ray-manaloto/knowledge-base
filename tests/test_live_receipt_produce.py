# Copyright (c) 2026 Raymond Manaloto
"""Artifact-tampering controls for trusted-host live receipt production."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from kb_setup import live_receipt, live_receipt_produce


def _write(path: Path, data: dict | bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode())
    return str(path)


def _sha(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _inventory_sha(source: str) -> str:
    inventory = [{"path": Path(source).name, "sha256": _sha(source)}]
    return hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest()


def _deep_cache_fixture(
    root: Path,
    phase: str,
    source: str,
    producer_data: dict,
) -> str:
    return _write(
        root / f"{phase}-cache.json",
        {
            "requested": [source],
            "uncached": [source] if phase == "cold" else [],
            "cache_evidence": ([] if phase == "cold" else [{"producer_receipts": [producer_data]}]),
        },
    )


def _build_case(
    context: tuple[Path, str, str, str, dict[str, str]],
    name: str,
    selection: tuple[str, str, str],
) -> dict:
    evidence, head, fork_commit, declaration, sources = context
    subset, backend, mode = selection
    declaration_sha = _sha(declaration)
    root = evidence / name
    profile_data = {
        "backend": backend,
        "mode": mode,
        "model": "opus" if backend == "claude-cli" else "gpt-5.6-sol",
        "effort": "xhigh" if backend == "claude-cli" else "high",
    }
    profile = _write(root / "profile.json", profile_data)
    source = sources[subset]
    request = _write(
        root / "request.json",
        {**profile_data, "sources": [{"key": "input", "path": source}]},
    )
    command = (
        ["mise", "run", "kb-graphify-ingest", "--", request]
        if mode == "NORMAL"
        else [
            "mise",
            "run",
            "kb-graphify-native-extract",
            "--",
            "--target",
            str(Path(source).parent),
            "--backend",
            backend,
            "--model",
            profile_data["model"],
            "--effort",
            profile_data["effort"],
        ]
    )
    result_data = {
        "status": "PASS_REPLAY_STRUCTURAL",
        "identity": {
            "kb_commit": head,
            "fork_commit": fork_commit,
            "command": command,
            "request_sha256": _sha(request),
            "source_sha256": {"input": _sha(source)},
            "inputs": {"input.md": _sha(source)},
        },
        "warm_extraction_attempts": 0,
        "source_count": 1,
        "sources": [{"key": "input", "graph_sha256": "", "warm_extraction_attempts": 0}],
    }
    result = _write(root / "RESULT.json", result_data)
    preflight_data = (
        {
            "status": "PREFLIGHT_PASS_NO_PROVIDER_CALL",
            "identity": {
                "kb_commit": head,
                "request_sha256": _sha(request),
                "source_sha256": {"input": _sha(source)},
            },
        }
        if mode == "NORMAL"
        else {
            "kb_commit": head,
            "fork_commit": fork_commit,
            "declaration_sha256": declaration_sha,
            "command": command,
            "inputs": {"input.md": _sha(source)},
        }
    )
    preflight = _write(root / "PREFLIGHT.json", preflight_data)
    audit = _write(
        root / "FACTS.json",
        {
            "status": "PASS_MAPPED_SOURCE_FACTS",
            "case": name,
            "kb_commit": head,
            "fork_commit": fork_commit,
            "declaration_sha256": declaration_sha,
            "fact_count": 1,
        },
    )
    graph = {"nodes": [{"id": "a"}, {"id": "b"}], "links": [{"source": "a", "target": "b"}]}
    producer = _write(
        root / "producer.json",
        {
            "receipt_id": hashlib.sha256(name.encode()).hexdigest(),
            "completion": "completed",
            "request": {"requested_profile": profile_data},
            "run_context": {
                "source_identity": {
                    "digest": _sha(source) if mode == "NORMAL" else _inventory_sha(source),
                    "scope": [Path(source).name],
                }
            },
            "process": {
                "finalized": True,
                "returncode": 0,
                "runner_error": None,
                "stdout": {"eof": True},
                "stderr": {"eof": True, "byte_count": 0},
                "result_artifact": {"eof": True, "finalized": True},
            },
        },
    )
    producer_data = json.loads(Path(producer).read_text())
    producer_id = producer_data["receipt_id"]
    result_data["sources"][0]["producer_receipt_id"] = producer_id
    result_data["cold_producer_receipts"] = {
        producer_id: {"snapshot": producer, "sha256": _sha(producer)}
    }
    phases = {}
    for phase in ("cold", "warm"):
        stdout_data = (
            {
                "total": 1,
                "succeeded": 1,
                "results": [
                    {
                        "key": "input",
                        "cached": phase == "warm",
                        **(
                            {"cache_evidence": [{"producer_receipts": [producer_data]}]}
                            if phase == "warm"
                            else {"receipt_id": producer_id}
                        ),
                    }
                ],
            }
            if mode == "NORMAL"
            else phase.encode()
        )
        stdout = _write(root / f"{phase}.stdout", stdout_data)
        stderr = _write(root / f"{phase}.stderr", b"")
        receipt = _write(
            root / f"{phase}.receipt.json",
            {
                "head_before": head,
                "head_after": head,
                "argv": command,
                "direct_rc": 0,
                "streams_settled": True,
                "timed_out": False,
                "stdout_sha256": _sha(stdout),
                "stderr_sha256": _sha(stderr),
            },
        )
        phases[phase] = {
            "command_receipt": receipt,
            "stdout": stdout,
            "stderr": stderr,
            "graphs": [_write(root / f"{phase}.graph.json", graph)],
            "producer_receipts": [producer],
        }
        if mode == "DEEP":
            cache_path = _deep_cache_fixture(root, phase, source, producer_data)
            phases[phase]["cache_evidence"] = cache_path
            result_data[f"{phase}_cache_evidence"] = cache_path
        result_data[f"{phase}_receipt"] = json.loads(Path(receipt).read_text())
    graph_sha = _sha(phases["cold"]["graphs"][0])
    result_data["sources"][0]["graph_sha256"] = graph_sha
    result_data["cold_graph"] = {"sha256": graph_sha}
    _write(Path(result), result_data)
    audit_data = json.loads(Path(audit).read_text())
    audit_data["result_sha256"] = _sha(result)
    _write(Path(audit), audit_data)
    declared = json.loads(Path(declaration).read_text())
    if mode == "NORMAL":
        declared["normal_requests"].append(
            {
                "case": name,
                "request": request,
                "request_sha256": _sha(request),
                "source_count": 1,
                "source_keys": ["input"],
            }
        )
    else:
        result_data["identity"]["command"] = command
        _write(Path(result), result_data)
        audit_data["result_sha256"] = _sha(result)
        _write(Path(audit), audit_data)
        declared["deep_cases"].append({"case": name, "command": command, "source_count": 1})
    _write(Path(declaration), declared)
    return {
        "name": name,
        "request": request,
        "profile": profile,
        "result": result,
        "preflight": preflight,
        "facts_audit": audit,
        **phases,
    }


@pytest.fixture
def matrix(tmp_path: Path) -> tuple[dict, Path, str]:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "sources").mkdir()
    _write(candidate / "uv.lock", b"version = 1\n")
    _write(
        candidate / "sources/graphify.manifest",
        b"url = https://github.com/ray-manaloto/graphify\n"
        b"ref = kb-openai-cli-backend-v0.9.69-baa50674\n"
        b"commit = " + b"b" * 40 + b"\nkind = code\n",
    )
    subprocess.run(["git", "init", "-q", str(candidate)], check=True)
    subprocess.run(["git", "-C", str(candidate), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(candidate),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "test fixture",
        ],
        check=True,
    )
    head = subprocess.run(
        ["git", "-C", str(candidate), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    evidence = tmp_path / "evidence"
    sources = {
        subset: _write(evidence / subset / "input.md", f"{subset} input\n".encode())
        for subset in ("graphify", "planning-with-files")
    }
    inputs = _write(evidence / "inputs.json", {"files": {p: _sha(p) for p in sources.values()}})
    fork_commit = "b" * 40
    declaration = _write(
        evidence / "declaration.json",
        {
            "kb_commit": head,
            "fork_commit": fork_commit,
            "inputs": [
                {"path": path, "sha256": _sha(path), "subset": subset}
                for subset, path in sources.items()
            ],
            "normal_requests": [],
            "deep_cases": [],
        },
    )
    declaration_sha = _sha(declaration)
    cases = [
        _build_case((evidence, head, fork_commit, declaration, sources), name, selection)
        for name, selection in live_receipt.CASES.items()
    ]
    declaration_sha = _sha(declaration)
    for case in cases:
        preflight_path = Path(case["preflight"])
        preflight = json.loads(preflight_path.read_text())
        if "declaration_sha256" in preflight:
            preflight["declaration_sha256"] = declaration_sha
            preflight["command"] = next(
                item["command"]
                for item in json.loads(Path(declaration).read_text())["deep_cases"]
                if item["case"] == case["name"]
            )
            _write(preflight_path, preflight)
        audit_path = Path(case["facts_audit"])
        audit = json.loads(audit_path.read_text())
        audit["declaration_sha256"] = declaration_sha
        _write(audit_path, audit)
    return {"declaration": declaration, "inputs_manifest": inputs, "cases": cases}, candidate, head


def test_eight_case_producer_derives_valid_payload(matrix: tuple[dict, Path, str]) -> None:
    evidence, candidate, head = matrix
    raw = live_receipt_produce.produce(evidence, candidate=candidate, head=head, pr=813)
    payload = live_receipt.validate_payload(
        raw, candidate_root=candidate, expected_pr=813, expected_head=head
    )
    assert len(payload["cases"]) == 8


def test_each_source_graph_must_be_nonempty(tmp_path: Path) -> None:
    populated = _write(
        tmp_path / "populated.json",
        {"nodes": [{"id": "a"}], "links": [{"source": "a", "target": "a"}]},
    )
    empty = _write(tmp_path / "empty.json", {"nodes": [], "links": []})
    with pytest.raises(live_receipt_produce.ProductionError, match="source graph is empty"):
        live_receipt_produce._graphs([populated, empty])


def test_reviewed_unverified_node_warning_is_bound_to_stderr(
    matrix: tuple[dict, Path, str],
) -> None:
    evidence, candidate, head = matrix
    case = next(item for item in evidence["cases"] if item["name"] == "graphify-claude-cli-deep")
    warning = (
        "[graphify] 1 semantic node(s) had no evidence in the source "
        "and were flagged verification=unverified"
    )
    _write(Path(case["cold"]["stderr"]), (warning + "\n").encode())
    receipt = json.loads(Path(case["cold"]["command_receipt"]).read_text())
    receipt["stderr_sha256"] = _sha(case["cold"]["stderr"])
    _rewrite_result_binding(case, receipt)
    audit = json.loads(Path(case["facts_audit"]).read_text())
    audit["diagnostics_review"] = {
        "cold": {
            "phase": "cold",
            "stderr_sha256": receipt["stderr_sha256"],
            "accepted_lines": [warning],
            "assessment": "reviewed_nonblocking_uncertainty",
            "reason": "The source-fact audit accounts for the retained unverified node warning.",
        }
    }
    _write(Path(case["facts_audit"]), audit)
    assert live_receipt_produce.produce(evidence, candidate=candidate, head=head, pr=813)


def test_deep_producer_inventory_digest_must_match_frozen_sources(
    matrix: tuple[dict, Path, str],
) -> None:
    evidence, candidate, head = matrix
    case = next(item for item in evidence["cases"] if item["name"] == "graphify-openai-cli-deep")
    producer_path = Path(case["cold"]["producer_receipts"][0])
    producer = json.loads(producer_path.read_text())
    producer["run_context"]["source_identity"]["digest"] = "0" * 64
    _write(producer_path, producer)
    result = json.loads(Path(case["result"]).read_text())
    result["cold_producer_receipts"][producer["receipt_id"]]["sha256"] = _sha(str(producer_path))
    _write(Path(case["result"]), result)
    cache_path = Path(case["warm"]["cache_evidence"])
    cache = json.loads(cache_path.read_text())
    cache["cache_evidence"][0]["producer_receipts"] = [producer]
    _write(cache_path, cache)
    audit = json.loads(Path(case["facts_audit"]).read_text())
    audit["result_sha256"] = _sha(case["result"])
    _write(Path(case["facts_audit"]), audit)
    with pytest.raises(live_receipt_produce.ProductionError, match="inventory digest differs"):
        live_receipt_produce.produce(evidence, candidate=candidate, head=head, pr=813)


def test_trusted_host_signs_and_self_verifies(matrix: tuple[dict, Path, str]) -> None:
    evidence, candidate, head = matrix
    root = candidate.parent
    matrix_path = Path(_write(root / "matrix.json", evidence))
    private_key = root / "signing-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)],
        check=True,
        capture_output=True,
    )
    trusted = root / "trusted-main"
    allowlist = trusted / ".github/graphify/allowed-signers"
    allowlist.parent.mkdir(parents=True)
    public = private_key.with_suffix(".pub").read_text().strip()
    allowlist.write_text(f'{live_receipt.SIGNER} namespaces="{live_receipt.NAMESPACE}" {public}\n')
    output = root / "signed"
    assert (
        live_receipt_produce.main(
            [
                "--matrix",
                str(matrix_path),
                "--candidate",
                str(candidate),
                "--trusted-main",
                str(trusted),
                "--head",
                head,
                "--pr",
                "813",
                "--private-key",
                str(private_key),
                "--out",
                str(output),
            ]
        )
        == 0
    )
    assert (output / "live-receipt.json").is_file()
    assert (output / "live-receipt.json.sig").is_file()


def _rewrite_result_binding(case: dict, receipt: dict) -> None:
    _write(Path(case["cold"]["command_receipt"]), receipt)
    result = json.loads(Path(case["result"]).read_text())
    result["cold_receipt"] = receipt
    _write(Path(case["result"]), result)
    audit = json.loads(Path(case["facts_audit"]).read_text())
    audit["result_sha256"] = _sha(case["result"])
    _write(Path(case["facts_audit"]), audit)


def _tamper_artifact(case: dict, candidate: Path, change: str) -> None:
    if change == "stdout":
        Path(case["cold"]["stdout"]).write_text("altered")
    elif change == "graph":
        Path(case["warm"]["graphs"][0]).write_text('{"nodes":[],"links":[]}')
    elif change == "audit":
        audit = json.loads(Path(case["facts_audit"]).read_text())
        audit["status"] = "FAIL"
        _write(Path(case["facts_audit"]), audit)
    else:
        (candidate / "uv.lock").write_text("changed")


def _tamper_claim(case: dict, evidence: dict, change: str) -> None:
    if change == "wrong_profile":
        profile = json.loads(Path(case["profile"]).read_text())
        profile["model"] = "sonnet"
        _write(Path(case["profile"]), profile)
    elif change == "wrong_source":
        request = json.loads(Path(case["request"]).read_text())
        request["sources"][0]["path"] = evidence["cases"][4]["request"]
        _write(Path(case["request"]), request)
    elif change == "stale_audit":
        audit = json.loads(Path(case["facts_audit"]).read_text())
        audit["result_sha256"] = "0" * 64
        _write(Path(case["facts_audit"]), audit)
    elif change == "invented_calls":
        case["cold"]["extraction_calls"] = 999
    elif change == "diagnostics":
        _write(Path(case["cold"]["stderr"]), b"warning: source omitted\n")
        receipt = json.loads(Path(case["cold"]["command_receipt"]).read_text())
        receipt["stderr_sha256"] = _sha(case["cold"]["stderr"])
        _rewrite_result_binding(case, receipt)
    elif change == "unfinished_producer":
        producer = json.loads(Path(case["cold"]["producer_receipts"][0]).read_text())
        producer["process"]["stderr"]["eof"] = False
        _write(Path(case["cold"]["producer_receipts"][0]), producer)
    elif change == "wrong_producer_id":
        producer = json.loads(Path(case["cold"]["producer_receipts"][0]).read_text())
        producer["receipt_id"] = "0" * 64
        _write(Path(case["cold"]["producer_receipts"][0]), producer)
    elif change == "warm_cache_miss":
        warm = json.loads(Path(case["warm"]["stdout"]).read_text())
        warm["results"][0]["cached"] = False
        _write(Path(case["warm"]["stdout"]), warm)
        receipt = json.loads(Path(case["warm"]["command_receipt"]).read_text())
        receipt["stdout_sha256"] = _sha(case["warm"]["stdout"])
        _write(Path(case["warm"]["command_receipt"]), receipt)
        result = json.loads(Path(case["result"]).read_text())
        result["warm_receipt"] = receipt
        _write(Path(case["result"]), result)
        audit = json.loads(Path(case["facts_audit"]).read_text())
        audit["result_sha256"] = _sha(case["result"])
        _write(Path(case["facts_audit"]), audit)
    elif change == "wrong_command":
        receipt = json.loads(Path(case["cold"]["command_receipt"]).read_text())
        receipt["argv"] = ["mise", "run", "different-task"]
        _rewrite_result_binding(case, receipt)


@pytest.mark.parametrize(
    "change",
    [
        "stdout",
        "graph",
        "audit",
        "dirty",
        "wrong_profile",
        "wrong_source",
        "stale_audit",
        "invented_calls",
        "diagnostics",
        "unfinished_producer",
        "wrong_producer_id",
        "warm_cache_miss",
        "wrong_command",
    ],
)
def test_tampered_matrix_refuses_signing(matrix: tuple[dict, Path, str], change: str) -> None:
    evidence, candidate, head = matrix
    case = evidence["cases"][0]
    if change in {"stdout", "graph", "audit", "dirty"}:
        _tamper_artifact(case, candidate, change)
    else:
        _tamper_claim(case, evidence, change)
    with pytest.raises((live_receipt_produce.ProductionError, live_receipt.ReceiptError)):
        live_receipt_produce.produce(evidence, candidate=candidate, head=head, pr=813)
