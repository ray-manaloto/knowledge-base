# Copyright (c) 2026 Raymond Manaloto
"""Verify a trusted host's detached, exact-head Graphify live receipt.

This module reads a candidate checkout and a separate signed evidence artifact
as data. A protected workflow must load this verifier and its allowed signers
from the protected default branch, never from the pull request being checked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

NAMESPACE = "graphify-live@ray-manaloto.github"
SIGNER = "graphify-live@ray-manaloto"
REPOSITORY = "ray-manaloto/knowledge-base"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_RECEIPT_BYTES = 1_000_000
MAX_SIGNATURE_BYTES = 20_000
MAX_SIGNERS_BYTES = 20_000
MAX_AGE = timedelta(hours=72)
CASES = {
    f"{source}-{backend}-{mode.lower()}": (source, backend, mode)
    for source in ("graphify", "planning-with-files")
    for backend in ("claude-cli", "openai-cli")
    for mode in ("NORMAL", "DEEP")
}
ROOT_KEYS = {
    "schema",
    "repository",
    "pr_number",
    "kb_commit",
    "fork_commit",
    "fork_ref",
    "issued_at_utc",
    "uv_lock_sha256",
    "source_manifest_sha256",
    "inputs_sha256",
    "declaration_sha256",
    "cases",
}
CASE_KEYS = {
    "name",
    "source",
    "backend",
    "mode",
    "request_sha256",
    "profile_sha256",
    "facts_audit_sha256",
    "cold",
    "warm",
}
PHASE_KEYS = {
    "direct_rc",
    "finalized",
    "omissions",
    "graph_nodes",
    "graph_links",
    "graph_sha256",
    "command_receipt_sha256",
    "producer_receipts_sha256",
    "extraction_calls",
}


class ReceiptError(ValueError):
    """A live receipt is missing, malformed, stale, or bound to another run."""


@dataclass(frozen=True)
class ExpectedPullRequest:
    """The event-supplied PR and immutable commit this receipt must attest."""

    number: int
    head: str


def _require(condition: object, reason: str) -> None:
    if not condition:
        raise ReceiptError(reason)


def _sha256(value: object, label: str) -> None:
    _require(
        isinstance(value, str) and SHA256.fullmatch(value) is not None, f"{label} is not SHA-256"
    )


def _same_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    _require(isinstance(value, dict) and set(value) == expected, f"{label} fields differ")
    return cast("dict[str, Any]", value)


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ReceiptError(f"non-JSON number {value}")


def _candidate_file(root: Path, relative: str, maximum: int) -> bytes:
    target = root / relative
    resolved = target.resolve(strict=True)
    _require(
        resolved.is_relative_to(root.resolve(strict=True)), f"{relative} leaves candidate checkout"
    )
    _require(
        target.is_file() and target.stat().st_size <= maximum, f"{relative} missing or too large"
    )
    return target.read_bytes()


def _manifest_identity(raw: bytes) -> tuple[str, str]:
    values: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        if line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if key in {"url", "ref", "commit", "kind"}:
            _require(key not in values, f"duplicate Graphify manifest {key}")
            values[key] = value
    _require(
        values.get("url") == "https://github.com/ray-manaloto/graphify",
        "unexpected Graphify source URL",
    )
    _require(values.get("kind") == "code", "Graphify manifest is not code")
    ref, commit = values.get("ref", ""), values.get("commit", "")
    _require(bool(ref) and re.fullmatch(r"[A-Za-z0-9._-]+", ref) is not None, "unsafe Graphify ref")
    _require(GIT_SHA.fullmatch(commit) is not None, "Graphify manifest commit is not exact")
    return ref, commit


def _phase(value: object, label: str, *, cold: bool) -> dict[str, Any]:
    phase = _same_keys(value, PHASE_KEYS, label)
    _require(type(phase["direct_rc"]) is int and phase["direct_rc"] == 0, f"{label} command failed")
    _require(phase["finalized"] is True, f"{label} is not finalized")
    _require(type(phase["omissions"]) is int and phase["omissions"] == 0, f"{label} has omissions")
    for key in ("graph_nodes", "graph_links"):
        _require(type(phase[key]) is int and phase[key] > 0, f"{label} {key} is empty")
    for key in ("graph_sha256", "command_receipt_sha256"):
        _sha256(phase[key], f"{label} {key}")
    producers = phase["producer_receipts_sha256"]
    _require(
        isinstance(producers, list) and all(isinstance(item, str) for item in producers),
        f"{label} producer list invalid",
    )
    _require(bool(producers), f"{label} original producer receipts missing")
    _require(len(producers) == len(set(producers)), f"{label} duplicate producer receipt")
    for item in producers:
        _sha256(item, f"{label} producer receipt")
    calls = phase["extraction_calls"]
    _require(
        type(calls) is int and (calls > 0 if cold else calls == 0),
        f"{label} extraction calls invalid",
    )
    return phase


def validate_payload(
    raw: bytes,
    *,
    candidate_root: Path,
    expected_pr: int,
    expected_head: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Reject ambiguity, incomplete cells, stale receipts, and identity drift."""
    _require(len(raw) <= MAX_RECEIPT_BYTES, "receipt too large")
    try:
        data = json.loads(
            raw, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"invalid receipt JSON: {exc}") from exc
    payload = _same_keys(data, ROOT_KEYS, "receipt")
    canonical = (
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")
    _require(raw == canonical, "receipt is not canonical JSON")
    _require(payload["schema"] == "graphify-live-v1", "unknown receipt schema")
    _require(payload["repository"] == REPOSITORY, "receipt names another repository")
    _require(
        type(payload["pr_number"]) is int and payload["pr_number"] == expected_pr > 0,
        "receipt PR differs",
    )
    _require(
        GIT_SHA.fullmatch(expected_head) is not None and payload["kb_commit"] == expected_head,
        "receipt KB head differs",
    )
    _require(
        isinstance(payload["fork_commit"], str)
        and GIT_SHA.fullmatch(payload["fork_commit"]) is not None,
        "fork commit invalid",
    )
    current = now or datetime.now(UTC)
    _require(current.tzinfo is not None, "verification clock lacks timezone")
    try:
        issued = datetime.fromisoformat(payload["issued_at_utc"])
    except (TypeError, ValueError) as exc:
        raise ReceiptError("invalid receipt timestamp") from exc
    _require(
        issued.tzinfo is not None and issued.utcoffset() == timedelta(0),
        "receipt timestamp is not UTC",
    )
    age = current.astimezone(UTC) - issued.astimezone(UTC)
    _require(-timedelta(minutes=5) <= age <= MAX_AGE, "receipt timestamp is stale or in the future")
    for key in ("uv_lock_sha256", "source_manifest_sha256", "inputs_sha256", "declaration_sha256"):
        _sha256(payload[key], key)
    lock = _candidate_file(candidate_root, "uv.lock", 20_000_000)
    manifest = _candidate_file(candidate_root, "sources/graphify.manifest", 100_000)
    _require(
        hashlib.sha256(lock).hexdigest() == payload["uv_lock_sha256"],
        "uv.lock changed since live run",
    )
    _require(
        hashlib.sha256(manifest).hexdigest() == payload["source_manifest_sha256"],
        "Graphify manifest changed since live run",
    )
    ref, commit = _manifest_identity(manifest)
    _require(
        (payload["fork_ref"], payload["fork_commit"]) == (ref, commit),
        "fork ref/commit differs from manifest",
    )
    cases = payload["cases"]
    _require(isinstance(cases, list) and len(cases) == len(CASES), "eight live cases required")
    seen: set[str] = set()
    for entry in cases:
        case = _same_keys(entry, CASE_KEYS, "case")
        name = case["name"]
        _require(
            isinstance(name, str) and name in CASES and name not in seen,
            "unknown or duplicate live case",
        )
        seen.add(name)
        _require(
            (case["source"], case["backend"], case["mode"]) == CASES[name],
            f"{name} selector differs",
        )
        for key in ("request_sha256", "profile_sha256", "facts_audit_sha256"):
            _sha256(case[key], f"{name} {key}")
        cold = _phase(case["cold"], f"{name} cold", cold=True)
        warm = _phase(case["warm"], f"{name} warm", cold=False)
        for key in ("graph_nodes", "graph_links", "graph_sha256"):
            _require(cold[key] == warm[key], f"{name} warm graph differs")
        _require(
            cold["producer_receipts_sha256"] == warm["producer_receipts_sha256"],
            f"{name} warm producer provenance differs",
        )
    _require(seen == set(CASES), "live case coverage incomplete")
    return payload


def verify_receipt(
    *,
    candidate_root: Path,
    evidence_root: Path,
    trusted_main_root: Path,
    expected: ExpectedPullRequest,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Verify protected-main signer and external exact-head evidence, fail closed."""
    receipt = _candidate_file(evidence_root, "live-receipt.json", MAX_RECEIPT_BYTES)
    signature = _candidate_file(evidence_root, "live-receipt.json.sig", MAX_SIGNATURE_BYTES)
    payload = validate_payload(
        receipt,
        candidate_root=candidate_root,
        expected_pr=expected.number,
        expected_head=expected.head,
        now=now,
    )
    signers = trusted_main_root / ".github/graphify/allowed-signers"
    _require(
        signers.is_file() and signers.stat().st_size <= MAX_SIGNERS_BYTES,
        "protected-main signer allowlist unavailable",
    )
    signature_path = evidence_root / "live-receipt.json.sig"
    result = subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "verify",
            "-f",
            str(signers),
            "-I",
            SIGNER,
            "-n",
            NAMESPACE,
            "-s",
            str(signature_path),
        ],
        input=receipt,
        capture_output=True,
        check=False,
        timeout=15,
    )
    _require(
        result.returncode == 0,
        "SSH signature is missing, invalid, or not trusted by protected main",
    )
    _require(signature.startswith(b"-----BEGIN SSH SIGNATURE-----"), "signature format invalid")
    return payload


def main(argv: list[str] | None = None) -> int:
    """Check one candidate receipt against the protected-main signer list."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--trusted-main-root", required=True, type=Path)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--head", required=True)
    args = parser.parse_args(argv)
    try:
        payload = verify_receipt(
            candidate_root=args.candidate_root,
            evidence_root=args.evidence_root,
            trusted_main_root=args.trusted_main_root,
            expected=ExpectedPullRequest(args.pr, args.head),
        )
    except (OSError, ReceiptError, subprocess.TimeoutExpired) as exc:
        print(f"live receipt REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"live receipt OK: PR #{payload['pr_number']} at {payload['kb_commit']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
