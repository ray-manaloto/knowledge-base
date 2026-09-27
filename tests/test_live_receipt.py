# Copyright (c) 2026 Raymond Manaloto
"""Causal controls for the protected-main Graphify live receipt verifier."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from kb_setup import live_receipt

NOW = datetime(2026, 9, 27, 4, 0, tzinfo=UTC)
HEAD = "a" * 40
FORK = "b" * 40
REF = "kb-openai-cli-backend-v0.9.69-baa50674"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: dict) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _phase(*, cold: bool) -> dict:
    return {
        "direct_rc": 0,
        "finalized": True,
        "omissions": 0,
        "graph_nodes": 2,
        "graph_links": 1,
        "graph_sha256": "c" * 64,
        "command_receipt_sha256": "d" * 64 if cold else "e" * 64,
        "producer_receipts_sha256": ["f" * 64],
        "extraction_calls": 1 if cold else 0,
    }


def _payload(lock: bytes, manifest: bytes) -> dict:
    return {
        "schema": "graphify-live-v1",
        "repository": live_receipt.REPOSITORY,
        "pr_number": 813,
        "kb_commit": HEAD,
        "fork_commit": FORK,
        "fork_ref": REF,
        "issued_at_utc": NOW.isoformat(),
        "uv_lock_sha256": _digest(lock),
        "source_manifest_sha256": _digest(manifest),
        "inputs_sha256": "1" * 64,
        "declaration_sha256": "2" * 64,
        "cases": [
            {
                "name": name,
                "source": source,
                "backend": backend,
                "mode": mode,
                "request_sha256": "3" * 64,
                "profile_sha256": "4" * 64,
                "facts_audit_sha256": "5" * 64,
                "cold": _phase(cold=True),
                "warm": _phase(cold=False),
            }
            for name, (source, backend, mode) in live_receipt.CASES.items()
        ],
    }


@pytest.fixture
def signed_run(tmp_path: Path) -> tuple[Path, Path, Path, dict]:
    candidate = tmp_path / "candidate"
    (tmp_path / "evidence").mkdir()
    trusted = tmp_path / "trusted-main"
    (candidate / ".github/graphify").mkdir(parents=True)
    (candidate / "sources").mkdir()
    (trusted / ".github/graphify").mkdir(parents=True)
    lock = b"version = 1\n"
    manifest = (
        f"url = https://github.com/ray-manaloto/graphify\nref = {REF}\n"
        f"commit = {FORK}\nkind = code\n"
    ).encode()
    (candidate / "uv.lock").write_bytes(lock)
    (candidate / "sources/graphify.manifest").write_bytes(manifest)
    key = tmp_path / "signing-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
        capture_output=True,
    )
    public = key.with_suffix(".pub").read_text().strip()
    (trusted / ".github/graphify/allowed-signers").write_text(
        f'{live_receipt.SIGNER} namespaces="{live_receipt.NAMESPACE}" {public}\n'
    )
    payload = _payload(lock, manifest)
    _sign(candidate, key, payload)
    return candidate, trusted, key, payload


def _sign(candidate: Path, key: Path, payload: dict) -> None:
    path = candidate.parent / "evidence/live-receipt.json"
    path.write_bytes(_canonical(payload))
    path.with_name(path.name + ".sig").unlink(missing_ok=True)
    subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", live_receipt.NAMESPACE, str(path)],
        check=True,
        capture_output=True,
    )


def _verify(candidate: Path, trusted: Path) -> dict:
    return live_receipt.verify_receipt(
        candidate_root=candidate,
        evidence_root=candidate.parent / "evidence",
        trusted_main_root=trusted,
        expected=live_receipt.ExpectedPullRequest(813, HEAD),
        now=NOW,
    )


def test_signed_eight_case_receipt_passes(signed_run: tuple[Path, Path, Path, dict]) -> None:
    candidate, trusted, _, _ = signed_run
    assert len(_verify(candidate, trusted)["cases"]) == 8


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(pr_number=814),
        lambda p: p.update(kb_commit="0" * 40),
        lambda p: p.update(fork_commit="0" * 40),
        lambda p: p.update(issued_at_utc=(NOW - timedelta(hours=73)).isoformat()),
        lambda p: p["cases"].pop(),
        lambda p: p["cases"][0]["cold"].update(omissions=1),
        lambda p: p["cases"][0]["cold"].update(finalized=False),
        lambda p: p["cases"][0]["warm"].update(extraction_calls=1),
        lambda p: p["cases"][0]["warm"].update(graph_sha256="0" * 64),
        lambda p: p["cases"][0]["warm"].update(producer_receipts_sha256=["0" * 64]),
    ],
)
def test_trusted_signature_does_not_override_failed_evidence(
    signed_run: tuple[Path, Path, Path, dict], mutate
) -> None:
    candidate, trusted, key, payload = signed_run
    mutate(payload)
    _sign(candidate, key, payload)
    with pytest.raises(live_receipt.ReceiptError):
        _verify(candidate, trusted)


def test_changed_lock_is_refused(signed_run: tuple[Path, Path, Path, dict]) -> None:
    candidate, trusted, _, _ = signed_run
    (candidate / "uv.lock").write_text("version = 2\n")
    with pytest.raises(live_receipt.ReceiptError, match=r"uv\.lock changed"):
        _verify(candidate, trusted)


def test_changed_manifest_is_refused(signed_run: tuple[Path, Path, Path, dict]) -> None:
    candidate, trusted, _, _ = signed_run
    (candidate / "sources/graphify.manifest").write_text("ref = v0.0.0\n")
    with pytest.raises(live_receipt.ReceiptError, match="manifest changed"):
        _verify(candidate, trusted)


def test_unsigned_change_is_refused(signed_run: tuple[Path, Path, Path, dict]) -> None:
    candidate, trusted, _, _ = signed_run
    path = candidate.parent / "evidence/live-receipt.json"
    path.write_bytes(
        path.read_bytes().replace(
            b'"inputs_sha256":"' + b"1" * 64, b'"inputs_sha256":"' + b"2" * 64
        )
    )
    with pytest.raises(live_receipt.ReceiptError, match="SSH signature"):
        _verify(candidate, trusted)


def test_untrusted_signer_is_refused(signed_run: tuple[Path, Path, Path, dict]) -> None:
    candidate, trusted, _, payload = signed_run
    other = candidate.parent / "other-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(other)],
        check=True,
        capture_output=True,
    )
    _sign(candidate, other, payload)
    with pytest.raises(live_receipt.ReceiptError, match="not trusted"):
        _verify(candidate, trusted)


def test_candidate_signer_list_cannot_override_protected_main(
    signed_run: tuple[Path, Path, Path, dict],
) -> None:
    candidate, trusted, _, payload = signed_run
    other = candidate.parent / "candidate-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(other)],
        check=True,
        capture_output=True,
    )
    public = other.with_suffix(".pub").read_text().strip()
    (candidate / ".github/graphify/allowed-signers").write_text(
        f'{live_receipt.SIGNER} namespaces="{live_receipt.NAMESPACE}" {public}\n'
    )
    _sign(candidate, other, payload)
    with pytest.raises(live_receipt.ReceiptError, match="not trusted"):
        _verify(candidate, trusted)


def test_duplicate_keys_are_refused(signed_run: tuple[Path, Path, Path, dict]) -> None:
    candidate, _, _, _ = signed_run
    raw = (candidate.parent / "evidence/live-receipt.json").read_bytes()
    duplicate = raw.replace(
        b'"schema":"graphify-live-v1"', b'"schema":"graphify-live-v1","schema":"graphify-live-v1"'
    )
    with pytest.raises(live_receipt.ReceiptError, match="duplicate JSON key"):
        live_receipt.validate_payload(
            duplicate, candidate_root=candidate, expected_pr=813, expected_head=HEAD, now=NOW
        )
