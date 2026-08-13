# Copyright (c) 2026 Raymond Manaloto
"""Hostile controls for the reviewed-ledger-only SkillOpt adapter."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from kb_setup import skillopt_reviewed as subject


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest(values: list[str]) -> str:
    return _sha(("\n".join(values) + "\n").encode())


def _write(path: Path, value: object) -> str:
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha(data)


def _ref(path: Path, root: Path) -> dict[str, str]:
    return {"path": path.relative_to(root).as_posix(), "sha256": _sha(path.read_bytes())}


def _root_for(split: str, number: int) -> str:
    while True:
        digest = _sha(f"session-{number}".encode())
        if subject._bucket(digest) == split:
            return digest
        number += 1


def _bundle(
    root: Path, name: str, root_digest: str, claim_id: str
) -> tuple[dict[str, Any], dict[str, str]]:
    iteration_hash = _sha(f"iteration-{name}".encode())
    claim_digest = _sha(claim_id.encode())
    statement_digest = _sha(f"statement-{name}".encode())
    iteration = root / f"{name}.iteration.json"
    _write(
        iteration,
        {
            "format": "kb.session-review.redacted-iteration.v1",
            "manifest_sha256": iteration_hash,
            "root_session_digest": root_digest,
            "unreviewed_requirement_ids": [],
            "unreviewed_promise_ids": [],
            "open_requirement_id_sha256s": [claim_digest],
            "open_promise_id_sha256s": [],
        },
    )
    claims_index = root / f"{name}.claims.json"
    claims_segment = Path(f"{claims_index}.0001.json")
    claim_count = 1
    claim_segment_hash = _write(
        claims_segment,
        {
            "format": "kb.session-review.redacted-claim-segment.v1",
            "iteration_manifest_sha256": iteration_hash,
            "segment_index": 1,
            "claim_count": claim_count,
            "claims": [
                {
                    "claim_id": claim_id,
                    "claim_kind": "requirement",
                    "provenance": "native_root_user",
                    "status": "open",
                    "statement_sha256": statement_digest,
                }
            ],
        },
    )
    _write(
        claims_index,
        {
            "format": "kb.session-review.redacted-claim-index.v1",
            "iteration_manifest_sha256": iteration_hash,
            "claim_count": claim_count,
            "segment_count": 1,
            "segment_sha256_manifest": _manifest([claim_segment_hash]),
            "segments": [{"suffix": ".0001.json", "sha256": claim_segment_hash, "claim_count": 1}],
        },
    )
    dispositions_index = root / f"{name}.dispositions.json"
    dispositions_segment = Path(f"{dispositions_index}.0001.json")
    disposition_hash = _write(
        dispositions_segment,
        {
            "format": "kb.session-review.redacted-disposition-segment.v1",
            "iteration_manifest_sha256": iteration_hash,
            "segment_index": 1,
            "disposition_count": 1,
            "dispositions": [{"claim_id_sha256": claim_digest, "status": "open"}],
        },
    )
    _write(
        dispositions_index,
        {
            "format": "kb.session-review.redacted-disposition-index.v1",
            "iteration_manifest_sha256": iteration_hash,
            "disposition_count": 1,
            "segment_count": 1,
            "segment_sha256_manifest": _manifest([disposition_hash]),
            "segments": [
                {
                    "suffix": ".0001.json",
                    "sha256": disposition_hash,
                    "disposition_count": 1,
                }
            ],
        },
    )
    return (
        {
            "claims_index": _ref(claims_index, root),
            "iteration": _ref(iteration, root),
            "dispositions_index": _ref(dispositions_index, root),
        },
        {
            "claim_id_sha256": claim_digest,
            "statement_sha256": statement_digest,
            "root_session_digest": root_digest,
        },
    )


def _fixture(tmp_path: Path) -> tuple[Path, Path, str, list[dict[str, str]]]:
    roots = [
        _root_for(split, offset) for split, offset in (("train", 1), ("val", 100), ("test", 200))
    ]
    bundles: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    for position, root_digest in enumerate(roots):
        bundle, source = _bundle(
            tmp_path, f"bundle{position}", root_digest, f"private-session-claim-{position}"
        )
        bundles.append(bundle)
        sources.append(source)
    reviewed_tasks = tmp_path / "reviewed-tasks.json"
    _write(
        reviewed_tasks,
        {
            "format": "kb.skillopt.reviewed-tasks.v1",
            "task_count": 3,
            "tasks": [
                {
                    "task_id": f"task-{position}",
                    "task_family": f"verification-{position}",
                    "root_session_digest": source["root_session_digest"],
                    "instruction": (
                        f"Verify bounded behavior {position} without claiming completion."
                    ),
                    "success_rubric": (
                        f"Reports observed status {position} and preserves every warning."
                    ),
                    "sources": [
                        {
                            "claim_id_sha256": source["claim_id_sha256"],
                            "statement_sha256": source["statement_sha256"],
                        }
                    ],
                }
                for position, source in enumerate(sources)
            ],
        },
    )
    bundle_hashes = [
        _manifest(
            [
                bundle["claims_index"]["sha256"],
                bundle["iteration"]["sha256"],
                bundle["dispositions_index"]["sha256"],
            ]
        )
        for bundle in bundles
    ]
    receipt = tmp_path / "review-receipt.json"
    receipt_hash = _write(
        receipt,
        {
            "format": "kb.skillopt.review-receipt.v1",
            "authority": "native_root_user",
            "bundle_sha256_manifest": _manifest(bundle_hashes),
            "reviewed_tasks_sha256": _sha(reviewed_tasks.read_bytes()),
        },
    )
    packet = tmp_path / "packet.json"
    _write(
        packet,
        {
            "format": "kb.skillopt.reviewed-packet.v1",
            "bundles": bundles,
            "reviewed_tasks": _ref(reviewed_tasks, tmp_path),
            "review_receipt": _ref(receipt, tmp_path),
        },
    )
    return packet, receipt, receipt_hash, sources


def _target(repo: Path) -> Path:
    skill = repo / ".claude/skills/example/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: example\n---\nSafe target.\n", encoding="utf-8")
    descriptor = repo / "target.json"
    _write(
        descriptor,
        {
            "format": "kb.skillopt.target.v1",
            "target_id": "example",
            "relative_path": ".claude/skills/example/SKILL.md",
            "sha256": _sha(skill.read_bytes()),
        },
    )
    return descriptor


def _refresh_authority(root: Path, packet: Path) -> str:
    value = json.loads(packet.read_text())
    bundle_hashes: list[str] = []
    for bundle in value["bundles"]:
        hashes: list[str] = []
        for key in ("claims_index", "iteration", "dispositions_index"):
            digest = _sha((root / bundle[key]["path"]).read_bytes())
            bundle[key]["sha256"] = digest
            hashes.append(digest)
        bundle_hashes.append(_manifest(hashes))
    tasks_hash = _sha((root / value["reviewed_tasks"]["path"]).read_bytes())
    value["reviewed_tasks"]["sha256"] = tasks_hash
    receipt_path = root / value["review_receipt"]["path"]
    receipt_hash = _write(
        receipt_path,
        {
            "format": "kb.skillopt.review-receipt.v1",
            "authority": "native_root_user",
            "bundle_sha256_manifest": _manifest(bundle_hashes),
            "reviewed_tasks_sha256": tasks_hash,
        },
    )
    value["review_receipt"]["sha256"] = receipt_hash
    _write(packet, value)
    return receipt_hash


def test_reviewed_corpus_cross_binds_receipt_and_withholds_native_ids(tmp_path: Path) -> None:
    packet, _, receipt_hash, _ = _fixture(tmp_path)
    corpus = subject.load_reviewed_corpus(packet, receipt_hash)
    tasks = subject.reviewed_tasks(corpus)
    assert {task.split for task in tasks} == {"train", "val", "test"}
    serialized = json.dumps([task.to_dict() for task in tasks])
    assert "private-session-claim" not in serialized
    assert all(task.source_sessions[0] not in {"train", "val", "test"} for task in tasks)
    assert all(task.reference_kind == "rubric" for task in tasks)


def test_iteration_open_set_cannot_disagree_with_claims(tmp_path: Path) -> None:
    packet, _, _, sources = _fixture(tmp_path)
    iteration = tmp_path / "bundle0.iteration.json"
    value = json.loads(iteration.read_text())
    value["open_requirement_id_sha256s"] = []
    _write(iteration, value)
    receipt_hash = _refresh_authority(tmp_path, packet)
    with pytest.raises(subject.ReviewedLedgerError, match="OPEN identities"):
        subject.load_reviewed_corpus(packet, receipt_hash)
    assert sources[0]["claim_id_sha256"] not in value["open_requirement_id_sha256s"]


def test_duplicate_claim_id_with_distinct_statement_is_refused(tmp_path: Path) -> None:
    packet, _, _, _ = _fixture(tmp_path)
    segment_path = tmp_path / "bundle0.claims.json.0001.json"
    segment = json.loads(segment_path.read_text())
    duplicate = dict(segment["claims"][0])
    duplicate["statement_sha256"] = _sha(b"different statement")
    segment["claims"].append(duplicate)
    segment["claim_count"] = 2
    segment_hash = _write(segment_path, segment)
    index_path = tmp_path / "bundle0.claims.json"
    index = json.loads(index_path.read_text())
    index["claim_count"] = 2
    index["segments"][0].update(sha256=segment_hash, claim_count=2)
    index["segment_sha256_manifest"] = _manifest([segment_hash])
    _write(index_path, index)
    receipt_hash = _refresh_authority(tmp_path, packet)
    with pytest.raises(subject.ReviewedLedgerError, match="duplicated"):
        subject.load_reviewed_corpus(packet, receipt_hash)


def test_single_partition_corpus_is_refused_without_borrowing() -> None:
    root = _root_for("train", 1)
    corpus = subject.ReviewedCorpus(
        "0" * 64,
        "1" * 64,
        (),
        (
            subject.ReviewedSkillTask(
                "task", "family", root, "Do bounded work.", "Report the status.", ()
            ),
        ),
    )
    with pytest.raises(subject.ReviewedLedgerError, match="borrowing is forbidden"):
        subject.reviewed_tasks(corpus)


@pytest.mark.parametrize("overlap", ["family", "content"])
def test_family_or_normalized_content_cannot_cross_splits(overlap: str) -> None:
    roots = [
        _root_for(split, number) for split, number in (("train", 1), ("val", 100), ("test", 200))
    ]
    tasks = tuple(
        subject.ReviewedSkillTask(
            f"task-{position}",
            "same-family" if overlap == "family" else f"family-{position}",
            root,
            "Same   bounded work" if overlap == "content" else f"Work {position}",
            "REPORT status" if overlap == "content" else f"Rubric {position}",
            (),
        )
        for position, root in enumerate(roots)
    )
    corpus = subject.ReviewedCorpus("0" * 64, "1" * 64, (), tasks)
    with pytest.raises(subject.ReviewedLedgerError, match="crosses split"):
        subject.reviewed_tasks(corpus)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("wrong_receipt", "trusted invocation"),
        ("tampered_segment", "content hash"),
        ("non_authoritative", "not authoritative"),
        ("unknown_field", "forbidden or missing"),
        ("duplicate_disposition", "unknown or duplicated"),
        ("raw_jsonl", "raw JSONL"),
        ("private_task", "forbidden path"),
    ],
)
def test_reviewed_corpus_rejects_hostile_inputs(
    tmp_path: Path, mutation: str, message: str
) -> None:
    packet, _, receipt_hash, _ = _fixture(tmp_path)
    if mutation == "wrong_receipt":
        receipt_hash = "0" * 64
    elif mutation == "tampered_segment":
        (tmp_path / "bundle0.claims.json.0001.json").write_text("{}\n", encoding="utf-8")
    elif mutation == "non_authoritative":
        path = tmp_path / "bundle0.claims.json.0001.json"
        value = json.loads(path.read_text())
        value["claims"][0]["provenance"] = "non_authoritative"
        _write(path, value)
        index_path = tmp_path / "bundle0.claims.json"
        index = json.loads(index_path.read_text())
        digest = _sha(path.read_bytes())
        index["segments"][0]["sha256"] = digest
        index["segment_sha256_manifest"] = _manifest([digest])
        _write(index_path, index)
        packet_value = json.loads(packet.read_text())
        packet_value["bundles"][0]["claims_index"]["sha256"] = _sha(index_path.read_bytes())
        _write(packet, packet_value)
    elif mutation == "unknown_field":
        value = json.loads(packet.read_text())
        value["source_path"] = "/private/canary"
        _write(packet, value)
    elif mutation == "duplicate_disposition":
        _duplicate_disposition(tmp_path, packet)
    elif mutation == "raw_jsonl":
        packet = packet.with_suffix(".jsonl")
        packet.write_text("{}\n", encoding="utf-8")
    elif mutation == "private_task":
        path = tmp_path / "reviewed-tasks.json"
        value = json.loads(path.read_text())
        value["tasks"][0]["instruction"] = "Read /Users/private/raw.jsonl"
        _write(path, value)
        packet_value = json.loads(packet.read_text())
        packet_value["reviewed_tasks"]["sha256"] = _sha(path.read_bytes())
        _write(packet, packet_value)
    with pytest.raises(subject.ReviewedLedgerError, match=message):
        subject.load_reviewed_corpus(packet, receipt_hash)


def _duplicate_disposition(root: Path, packet: Path) -> None:
    path = root / "bundle0.dispositions.json.0001.json"
    value = json.loads(path.read_text())
    value["dispositions"].append(value["dispositions"][0])
    value["disposition_count"] = 2
    _write(path, value)
    index_path = root / "bundle0.dispositions.json"
    index = json.loads(index_path.read_text())
    digest = _sha(path.read_bytes())
    index["segments"][0].update(sha256=digest, disposition_count=2)
    index["segment_sha256_manifest"] = _manifest([digest])
    index["disposition_count"] = 2
    _write(index_path, index)
    packet_value = json.loads(packet.read_text())
    packet_value["bundles"][0]["dispositions_index"]["sha256"] = _sha(index_path.read_bytes())
    _write(packet, packet_value)


def test_adapter_passes_only_train_and_val_to_upstream_and_retains_unverified_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packet, _, receipt_hash, _ = _fixture(tmp_path)
    descriptor = _target(tmp_path)
    captured_env: dict[str, str] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        env = kwargs["env"]
        assert isinstance(env, dict)
        captured_env.update({str(key): str(value) for key, value in env.items()})
        tasks_path = Path(command[command.index("--tasks-file") + 1])
        assert not (tasks_path.parent / "heldout-test-tasks.json").exists()
        tasks = json.loads(tasks_path.read_text())["tasks"]
        assert {task["split"] for task in tasks} == {"train", "val"}
        assert all(task["split"] != "test" for task in tasks)
        staging = tasks_path.parent / "project/.skillopt-sleep/staging/mock"
        _write(staging / "report.json", {"holdout_leaked": False})
        result = {
            "tasks_reviewed": True,
            "accepted": False,
            "holdout_leaked": False,
            "gate_action": "reject",
            "staging_dir": str(staging),
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(result).encode(), b"")

    monkeypatch.setattr(subject, "assert_public_contract", lambda: None)
    monkeypatch.setattr(subject.subprocess, "run", fake_run)
    receipt = subject.run_reviewed_adapter(tmp_path, packet, descriptor, "mock", receipt_hash)
    assert receipt.status == "staged_unverified"
    assert receipt.certification == "none_no_adoption_or_heldout_claim"
    assert captured_env["PATH"] == ""
    assert captured_env["KB_SKILLOPT_ALLOWED_ROOT"].endswith(receipt.run_id)
    tasks_data = (
        tmp_path / ".agent/skillopt/runs" / receipt.run_id / "optimizer-tasks.json"
    ).read_text()
    assert "private-session-claim" not in tasks_data


def test_adapter_rejects_warning_and_stale_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packet, _, receipt_hash, _ = _fixture(tmp_path)
    descriptor = _target(tmp_path)

    def warned(command: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        result = {
            "tasks_reviewed": True,
            "accepted": False,
            "holdout_leaked": False,
            "gate_action": "reject",
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(result).encode(), b"warning")

    monkeypatch.setattr(subject, "assert_public_contract", lambda: None)
    monkeypatch.setattr(subject.subprocess, "run", warned)
    with pytest.raises(subject.ReviewedLedgerError, match="diagnostics retained"):
        subject.run_reviewed_adapter(tmp_path, packet, descriptor, "mock", receipt_hash)
    run_root = next((tmp_path / ".agent/skillopt/runs").iterdir())
    assert (run_root / "stderr.bin").read_bytes() == b"warning"
    with pytest.raises(subject.ReviewedLedgerError, match="stale state reuse"):
        subject.run_reviewed_adapter(tmp_path, packet, descriptor, "mock", receipt_hash)


@pytest.mark.parametrize(
    "report",
    [
        {},
        {
            "tasks_reviewed": True,
            "accepted": False,
            "holdout_leaked": True,
            "gate_action": "reject",
        },
        {
            "tasks_reviewed": False,
            "accepted": False,
            "holdout_leaked": False,
            "gate_action": "reject",
        },
    ],
)
def test_mock_rc_zero_without_structural_report_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, report: dict[str, object]
) -> None:
    packet, _, receipt_hash, _ = _fixture(tmp_path)
    descriptor = _target(tmp_path)
    monkeypatch.setattr(subject, "assert_public_contract", lambda: None)
    monkeypatch.setattr(
        subject.subprocess,
        "run",
        lambda command, **_: subprocess.CompletedProcess(
            command, 0, json.dumps(report).encode(), b""
        ),
    )
    with pytest.raises(subject.ReviewedLedgerError, match="structural result"):
        subject.run_reviewed_adapter(tmp_path, packet, descriptor, "mock", receipt_hash)


def test_handoff_pending_withholds_test_and_preserves_live_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packet, _, receipt_hash, _ = _fixture(tmp_path)
    descriptor = _target(tmp_path)
    live_target = tmp_path / ".claude/skills/example/SKILL.md"
    before = live_target.read_bytes()

    def pending(command: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        tasks_path = Path(command[command.index("--tasks-file") + 1])
        assert not (tasks_path.parent / "heldout-test-tasks.json").exists()
        assert all(task["split"] != "test" for task in json.loads(tasks_path.read_text())["tasks"])
        return subprocess.CompletedProcess(command, 3, b'{"handoff_pending":1}', b"")

    monkeypatch.setattr(subject, "assert_public_contract", lambda: None)
    monkeypatch.setattr(subject.subprocess, "run", pending)
    receipt = subject.run_reviewed_adapter(tmp_path, packet, descriptor, "handoff", receipt_hash)
    assert receipt.status == "handoff_pending"
    assert receipt.certification == "none_no_adoption_or_heldout_claim"
    assert live_target.read_bytes() == before


def test_real_pinned_mock_is_staged_unverified_and_retains_no_native_root(
    tmp_path: Path,
) -> None:
    packet, _, receipt_hash, _ = _fixture(tmp_path)
    descriptor = _target(tmp_path)
    receipt = subject.run_reviewed_adapter(tmp_path, packet, descriptor, "mock", receipt_hash)
    assert receipt.status == "staged_unverified"
    assert receipt.certification == "none_no_adoption_or_heldout_claim"
    native = str(tmp_path.resolve()).encode()
    retained = tmp_path / ".agent/skillopt"
    assert all(native not in path.read_bytes() for path in retained.rglob("*") if path.is_file())
    stdout = json.loads((retained / "runs" / receipt.run_id / receipt.stdout.path).read_text())
    assert stdout["tasks_reviewed"] is True
    assert stdout["holdout_leaked"] is False


def test_cli_refuses_network_harvest_and_adoption_flags(tmp_path: Path) -> None:
    assert subject.reviewed_main(tmp_path, ["--backend", "cursor"]) == 2
    assert subject.reviewed_main(tmp_path, ["--schedule", "--auto-adopt"]) == 2


@pytest.mark.parametrize(
    "canary",
    [
        "sk-" + "ant-secretvalue",
        "gh" + "p_1234567890",
        "AK" + "IA1234567890",
        "/private/x",
        "../x",
        "x/y",
    ],
)
def test_reviewed_task_text_rejects_secret_and_path_canaries(tmp_path: Path, canary: str) -> None:
    packet, _, receipt_hash, _ = _fixture(tmp_path)
    tasks_path = tmp_path / "reviewed-tasks.json"
    tasks = json.loads(tasks_path.read_text())
    tasks["tasks"][0]["instruction"] = f"Inspect {canary}"
    _write(tasks_path, tasks)
    packet_value = json.loads(packet.read_text())
    packet_value["reviewed_tasks"]["sha256"] = _sha(tasks_path.read_bytes())
    _write(packet, packet_value)
    with pytest.raises(subject.ReviewedLedgerError, match="forbidden path"):
        subject.load_reviewed_corpus(packet, receipt_hash)


def test_adapter_never_calls_run_sleep_cycle_directly() -> None:
    source = Path(subject.__file__).read_text(encoding="utf-8")
    assert "from skillopt_sleep.cycle import run_sleep_cycle" not in source
    assert "run_sleep_cycle(" not in source
    assert 'certification="none_no_adoption_or_heldout_claim"' in source


@pytest.mark.parametrize(
    "relative",
    ["AGENTS.md", "CLAUDE.md", "../SKILL.md", ".claude/skills/../../AGENTS.md"],
)
def test_target_descriptor_rejects_protected_and_traversal_targets(
    tmp_path: Path, relative: str
) -> None:
    descriptor = tmp_path / "target.json"
    _write(
        descriptor,
        {
            "format": "kb.skillopt.target.v1",
            "target_id": "protected",
            "relative_path": relative,
            "sha256": "0" * 64,
        },
    )
    with pytest.raises(subject.ReviewedLedgerError, match="target path"):
        subject.load_target_descriptor(tmp_path, descriptor)


def test_target_descriptor_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("outside", encoding="utf-8")
    target = tmp_path / ".claude/skills/example/SKILL.md"
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    descriptor = tmp_path / "target.json"
    _write(
        descriptor,
        {
            "format": "kb.skillopt.target.v1",
            "target_id": "example",
            "relative_path": ".claude/skills/example/SKILL.md",
            "sha256": _sha(outside.read_bytes()),
        },
    )
    with pytest.raises(subject.ReviewedLedgerError, match="escapes"):
        subject.load_target_descriptor(tmp_path, descriptor)


def test_child_audit_covers_write_link_symlink_and_metadata_mutations() -> None:
    for event in (
        "open",
        "os.link",
        "os.symlink",
        "os.chmod",
        "os.truncate",
        "os.utime",
        "os.chown",
        "os.setxattr",
    ):
        assert event in subject._AUDITED
    assert "KB_SKILLOPT_ALLOWED_ROOT" in subject._AUDITED


def test_real_child_audit_blocks_outside_utime_and_allows_inside(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    inside = allowed / "inside"
    outside = tmp_path / "outside"
    inside.write_text("inside", encoding="utf-8")
    outside.write_text("outside", encoding="utf-8")
    os.utime(outside, ns=(1, 1))
    before = outside.stat().st_mtime_ns
    prefix, _ = subject._AUDITED.split('sys.argv = ["skillopt-sleep"', maxsplit=1)
    mutation = prefix + "\nimport os, sys\nos.utime(sys.argv[1], None)\n"
    env = {"KB_SKILLOPT_ALLOWED_ROOT": str(allowed), "PYTHONUTF8": "1"}
    denied = subprocess.run(
        [sys.executable, "-c", mutation, str(outside)],
        env=env,
        capture_output=True,
        check=False,
    )
    assert denied.returncode != 0
    assert outside.stat().st_mtime_ns == before
    os.utime(inside, ns=(1, 1))
    allowed_result = subprocess.run(
        [sys.executable, "-c", mutation, str(inside)],
        env=env,
        capture_output=True,
        check=False,
    )
    assert allowed_result.returncode == 0
    assert inside.stat().st_mtime_ns != 1


def test_project_skills_are_identical_and_route_through_mise() -> None:
    root = Path(__file__).parents[1]
    claude = (root / ".claude/skills/skillopt-reviewed/SKILL.md").read_bytes()
    agents = (root / ".agents/skills/skillopt-reviewed/SKILL.md").read_bytes()
    assert claude == agents
    assert b"mise run kb-skillopt-reviewed" in claude
