# Copyright (c) 2026 Raymond Manaloto
"""Assemble and sign an exact-head live receipt from retained host artifacts.

The private key stays on the authenticated host. The matrix manifest names
read-only artifacts; this producer hashes their bytes and refuses incomplete
commands, graphs, fact audits, producer receipts, or warm provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from kb_setup import live_receipt

MAX_ARTIFACT_BYTES = 20_000_000
REQUIRED_PROFILES = {
    "claude-cli": ("opus", "xhigh"),
    "openai-cli": ("gpt-5.6-sol", "high"),
}


class ProductionError(ValueError):
    """The host evidence cannot support a signed live-qualification claim."""


def _read(path: str, *, maximum: int = MAX_ARTIFACT_BYTES) -> bytes:
    target = Path(path)
    if not target.is_file() or target.stat().st_size > maximum:
        raise ProductionError(f"missing or oversized artifact: {target}")
    return target.read_bytes()


def _json(path: str) -> dict[str, Any]:
    value = json.loads(_read(path))
    if not isinstance(value, dict):
        raise ProductionError(f"artifact is not a JSON object: {path}")
    return cast("dict[str, Any]", value)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require(condition: object, reason: str) -> None:
    if not condition:
        raise ProductionError(reason)


def _graphs(paths: list[str]) -> tuple[int, int, str, list[str]]:
    _require(bool(paths) and len(paths) == len(set(paths)), "graph paths missing or repeated")
    entries: list[str] = []
    nodes = links = 0
    for path in paths:
        raw = _read(path)
        graph = json.loads(raw)
        _require(isinstance(graph, dict), f"invalid graph {path}")
        graph_nodes = graph.get("nodes")
        graph_links = graph.get("links", graph.get("edges"))
        _require(
            isinstance(graph_nodes, list) and isinstance(graph_links, list),
            f"graph nodes or links missing: {path}",
        )
        _require(bool(graph_nodes) and bool(graph_links), f"source graph is empty: {path}")
        nodes += len(graph_nodes)
        links += len(graph_links)
        entries.append(_sha(raw))
    _require(nodes > 0 and links > 0, "graph is empty")
    bundle = json.dumps(sorted(entries), separators=(",", ":")).encode()
    return nodes, links, _sha(bundle), entries


def _command(
    phase: dict[str, Any],
    head: str,
    command: tuple[object, list[str], object],
    label: str,
) -> str:
    reported, argv, diagnostics_review = command
    path = phase["command_receipt"]
    raw = _read(path)
    receipt = json.loads(raw)
    _require(isinstance(receipt, dict), "invalid command receipt")
    _require(
        receipt.get("head_before") == head == receipt.get("head_after"),
        "command ran on a different KB commit",
    )
    _require(
        receipt.get("direct_rc") == 0
        and receipt.get("streams_settled") is True
        and receipt.get("timed_out") is False,
        "command failed, timed out, or left streams unsettled",
    )
    _require(receipt == reported, "result cites a different command receipt")
    _require(receipt.get("argv") == argv, "command did not run the frozen case")
    for stream in ("stdout", "stderr"):
        _require(
            _sha(_read(phase[stream])) == receipt.get(f"{stream}_sha256"),
            f"{stream} differs from command receipt",
        )
    stderr_raw = _read(phase["stderr"])
    diagnostics = stderr_raw.decode("utf-8", errors="strict")
    warnings = [
        line
        for line in diagnostics.splitlines()
        if not line.startswith(("[kb-graphify-ingest] $ ", "[kb-graphify-native-extract] $ "))
    ]
    if warnings:
        _require(isinstance(diagnostics_review, dict), "command diagnostics lack review")
        review = cast("dict[str, Any]", diagnostics_review)
        _require(
            review.get("phase") == label
            and review.get("stderr_sha256") == _sha(stderr_raw)
            and review.get("accepted_lines") == warnings
            and review.get("assessment") == "reviewed_nonblocking_uncertainty"
            and isinstance(review.get("reason"), str)
            and bool(review["reason"].strip()),
            "command diagnostics review differs from retained stderr",
        )
        _require(
            all(
                re.fullmatch(
                    r"\[graphify\] [1-9][0-9]* semantic node\(s\) had no evidence "
                    r"in the source and were flagged verification=unverified",
                    line,
                )
                for line in warnings
            ),
            "command stderr contains unknown diagnostics",
        )
    else:
        _require(diagnostics_review is None, "diagnostics review without diagnostics")
    return _sha(raw)


def _producers(
    paths: list[str], profile: dict[str, str]
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    _require(bool(paths) and len(paths) == len(set(paths)), "producer paths missing or repeated")
    digests: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for path in paths:
        raw = _read(path)
        receipt = json.loads(raw)
        _require(isinstance(receipt, dict), f"invalid producer receipt {path}")
        _require(receipt.get("completion") == "completed", "producer not finalized")
        process = receipt.get("process")
        _require(
            isinstance(process, dict)
            and process.get("finalized") is True
            and process.get("returncode") == 0
            and process.get("runner_error") is None,
            "producer process did not settle cleanly",
        )
        for stream in ("stdout", "stderr"):
            state = process.get(stream)
            _require(
                isinstance(state, dict) and state.get("eof") is True,
                f"producer {stream} lacks observed EOF",
            )
        artifact = process.get("result_artifact")
        if profile["backend"] == "openai-cli" or artifact is not None:
            _require(
                isinstance(artifact, dict)
                and artifact.get("eof") is True
                and artifact.get("finalized") is True,
                "producer result artifact was not finalized",
            )
        _require(
            process["stderr"].get("byte_count") == 0,
            "producer stderr requires separate review",
        )
        request = receipt.get("request")
        _require(isinstance(request, dict), "producer request missing")
        selected = request.get("requested_profile")
        _require(isinstance(selected, dict), "producer profile missing")
        _require(
            all(selected.get(key) == profile[key] for key in ("backend", "model", "effort")),
            "producer profile differs from frozen case",
        )
        receipt_id = receipt.get("receipt_id")
        _require(
            isinstance(receipt_id, str)
            and live_receipt.SHA256.fullmatch(receipt_id) is not None
            and receipt_id not in by_id,
            "producer ID missing or repeated",
        )
        by_id[receipt_id] = receipt
        digests.append(_sha(raw))
    return sorted(digests), by_id


def _phase(
    evidence: dict[str, Any],
    *,
    head: str,
    profile: dict[str, str],
    command: tuple[object, list[str], object],
    cold: bool,
) -> dict[str, Any]:
    allowed = {"command_receipt", "stdout", "stderr", "graphs", "producer_receipts"}
    allowed.add("cache_evidence")
    _require(
        set(evidence) in (allowed, allowed - {"cache_evidence"}),
        "phase contains unsupported matrix claims",
    )
    nodes, links, graph_sha, graph_digests = _graphs(evidence["graphs"])
    producers, by_id = _producers(evidence["producer_receipts"], profile)
    return {
        "direct_rc": 0,
        "finalized": True,
        "omissions": 0,
        "graph_nodes": nodes,
        "graph_links": links,
        "graph_sha256": graph_sha,
        "command_receipt_sha256": _command(evidence, head, command, "cold" if cold else "warm"),
        "producer_receipts_sha256": producers,
        "extraction_calls": len(producers) if cold else 0,
        "_graph_digests": graph_digests,
        "_producer_ids": sorted(by_id),
        "_producer_records": by_id,
    }


def _declared_subset(
    declaration: dict[str, Any], name: str, source: str, mode: str
) -> tuple[dict[str, str], dict[str, Any]]:
    rows = [item for item in declaration["inputs"] if item.get("subset") == source]
    _require(bool(rows), f"{name} source subset absent from declaration")
    paths = {item["path"]: item["sha256"] for item in rows}
    cases = [
        item
        for item in declaration["normal_requests" if mode == "NORMAL" else "deep_cases"]
        if item.get("case") == name
    ]
    _require(len(cases) == 1, f"{name} case absent or repeated in declaration")
    _require(cases[0].get("source_count") == len(paths), f"{name} source count drift")
    return paths, cases[0]


def _normal_provenance(
    evidence: dict[str, Any],
    result: dict[str, Any],
    expected_sources: dict[str, str],
    cold: dict[str, Any],
    warm: dict[str, Any],
) -> None:
    expected_ids = {item["key"]: item["producer_receipt_id"] for item in result["sources"]}
    _require(set(expected_ids) == set(expected_sources), "normal producer source keys differ")
    for label in ("cold", "warm"):
        stdout = json.loads(_read(evidence[label]["stdout"]))
        rows = stdout.get("results") if isinstance(stdout, dict) else None
        if not isinstance(rows, list):
            raise ProductionError(f"{label} stdout has no results list")
        _require(
            stdout.get("total") == len(expected_sources)
            and stdout.get("succeeded") == len(expected_sources)
            and {row.get("key") for row in rows if isinstance(row, dict)} == set(expected_sources)
            and len(rows) == len(expected_sources),
            f"{label} stdout source set differs",
        )
        for row in rows:
            key = row["key"]
            _require(row.get("cached") is (label == "warm"), f"{label} cache status differs")
            if label == "cold":
                _require(row.get("receipt_id") == expected_ids[key], "cold producer ID differs")
            else:
                cache = row.get("cache_evidence")
                _require(isinstance(cache, list) and bool(cache), "warm cache evidence missing")
                receipts = [
                    receipt for item in cache for receipt in item.get("producer_receipts", [])
                ]
                _require(
                    {receipt.get("receipt_id") for receipt in receipts} == {expected_ids[key]},
                    "warm cache producer differs",
                )
    _require(
        set(cold["_producer_ids"]) == set(expected_ids.values())
        and cold["_producer_ids"] == warm["_producer_ids"],
        "normal producer receipt IDs differ from result",
    )
    for key, receipt_id in expected_ids.items():
        receipt = cold["_producer_records"][receipt_id]
        source = receipt.get("run_context", {}).get("source_identity", {})
        _require(
            source.get("digest") == expected_sources[key], "normal producer source digest differs"
        )


def _deep_provenance(
    evidence: dict[str, Any],
    result: dict[str, Any],
    expected_paths: dict[str, str],
    cold: dict[str, Any],
    warm: dict[str, Any],
) -> None:
    retained = result.get("cold_producer_receipts")
    if not isinstance(retained, dict) or not retained:
        raise ProductionError("deep cold receipts missing")
    _require(
        set(retained) == set(cold["_producer_ids"]) == set(warm["_producer_ids"]),
        "deep producer IDs differ from result",
    )
    by_id = cold["_producer_records"]
    inventory = [
        {"path": Path(path).name, "sha256": digest}
        for path, digest in sorted(expected_paths.items())
    ]
    inventory_sha = _sha(json.dumps(inventory, sort_keys=True).encode())
    for receipt_id, record in retained.items():
        _require(
            isinstance(record, dict)
            and _sha(_read(record.get("snapshot", ""))) == record.get("sha256")
            and by_id[receipt_id] == json.loads(_read(record["snapshot"])),
            "deep producer differs from frozen result snapshot",
        )
        source_identity = by_id[receipt_id].get("run_context", {}).get("source_identity", {})
        _require(
            set(source_identity.get("scope", [])) == {Path(path).name for path in expected_paths},
            "deep producer source scope differs",
        )
        _require(
            source_identity.get("digest") == inventory_sha,
            "deep producer source inventory digest differs",
        )
    cold_cache_path = result.get("cold_cache_evidence")
    if not isinstance(cold_cache_path, str):
        raise ProductionError("deep cold cache path missing")
    _require(
        evidence["cold"].get("cache_evidence") == cold_cache_path,
        "deep cold cache path differs from result",
    )
    cold_cache = _json(cold_cache_path)
    _require(
        set(cold_cache.get("requested", [])) == set(expected_paths)
        and set(cold_cache.get("uncached", [])) == set(expected_paths),
        "deep cold cache did not require all declared inputs",
    )
    cache_path = result.get("warm_cache_evidence")
    if not isinstance(cache_path, str):
        raise ProductionError("deep warm cache path missing")
    _require(
        evidence["warm"].get("cache_evidence") == cache_path,
        "deep warm cache path differs from result",
    )
    cache = _json(cache_path)
    _require(
        cache.get("uncached") == [] and set(cache.get("requested", [])) == set(expected_paths),
        "deep warm cache has uncached or different sources",
    )
    entries = cache.get("cache_evidence")
    if not isinstance(entries, list) or not entries:
        raise ProductionError("deep warm cache evidence missing")
    replayed = [receipt for entry in entries for receipt in entry.get("producer_receipts", [])]
    _require(
        {receipt.get("receipt_id") for receipt in replayed} == set(by_id),
        "deep warm cache producer differs",
    )


def _fact_audit(
    evidence: dict[str, Any],
    *,
    name: str,
    head: str,
    fork_commit: str,
    declaration_sha: str,
) -> tuple[bytes, dict[str, Any]]:
    raw = _read(evidence["facts_audit"])
    audit = json.loads(raw)
    _require(isinstance(audit, dict), f"{name} fact audit invalid")
    _require(
        audit.get("status") == "PASS_MAPPED_SOURCE_FACTS"
        and audit.get("case") == name
        and audit.get("kb_commit") == head
        and audit.get("declaration_sha256") == declaration_sha
        and type(audit.get("fact_count")) is int
        and audit["fact_count"] > 0
        and audit.get("result_sha256") == _sha(_read(evidence["result"])),
        f"{name} fact audit does not qualify",
    )
    if live_receipt.CASES[name][2] == "DEEP":
        _require(audit.get("fork_commit") == fork_commit, f"{name} audit fork drift")
    reviews = audit.get("diagnostics_review", {})
    _require(isinstance(reviews, dict), f"{name} diagnostics review invalid")
    _require(set(reviews) <= {"cold", "warm"}, f"{name} diagnostics phases invalid")
    return raw, reviews


def _case(
    evidence: dict[str, Any],
    *,
    head: str,
    fork_commit: str,
    declaration_sha: str,
    declaration: dict[str, Any],
) -> dict[str, Any]:
    name = evidence["name"]
    _require(name in live_receipt.CASES, f"unknown case {name}")
    source, backend, mode = live_receipt.CASES[name]
    result = _json(evidence["result"])
    _require(result.get("status") == "PASS_REPLAY_STRUCTURAL", f"{name} replay failed")
    _require(result.get("identity", {}).get("kb_commit") == head, f"{name} head drift")
    expected_paths, declared = _declared_subset(declaration, name, source, mode)
    if mode == "DEEP":
        _require(result.get("identity", {}).get("fork_commit") == fork_commit, f"{name} fork drift")
    preflight = _json(evidence["preflight"])
    if mode == "NORMAL":
        identity = preflight.get("identity", {})
        _require(
            preflight.get("status") == "PREFLIGHT_PASS_NO_PROVIDER_CALL"
            and identity.get("kb_commit") == head
            and identity.get("request_sha256") == declared.get("request_sha256")
            and identity.get("source_sha256") == result.get("identity", {}).get("source_sha256"),
            f"{name} normal preflight differs",
        )
    else:
        _require(
            preflight.get("kb_commit") == head
            and preflight.get("fork_commit") == fork_commit
            and preflight.get("declaration_sha256") == declaration_sha
            and preflight.get("command") == result.get("identity", {}).get("command"),
            f"{name} deep preflight differs",
        )
    profile = _json(evidence["profile"])
    _require(
        profile.get("backend") == backend and profile.get("mode") == mode,
        "profile selector drift",
    )
    _require(
        (profile.get("model"), profile.get("effort")) == REQUIRED_PROFILES[backend],
        f"{name} model or effort differs from required subscription profile",
    )
    frozen_profile = {key: str(profile[key]) for key in ("backend", "model", "effort")}
    if mode == "NORMAL":
        request = _json(evidence["request"])
        _require(
            all(request.get(key) == profile[key] for key in ("backend", "model", "effort")),
            f"{name} request profile drift",
        )
        request_sources = request.get("sources")
        if not isinstance(request_sources, list):
            raise ProductionError(f"{name} request sources are not a list")
        _require(
            len(request_sources) == len(expected_paths)
            and all(isinstance(item, dict) for item in request_sources)
            and {item.get("path") for item in request_sources} == set(expected_paths)
            and declared.get("request") == evidence["request"]
            and declared.get("request_sha256") == _sha(_read(evidence["request"]))
            and {item.get("key") for item in request_sources}
            == set(declared.get("source_keys", []))
            and result.get("identity", {}).get("request_sha256") == declared["request_sha256"],
            f"{name} request does not match frozen source subset",
        )
        _require(
            result.get("identity", {}).get("source_sha256")
            == {item["key"]: expected_paths[item["path"]] for item in request_sources},
            f"{name} result source hashes drift",
        )
        sources = result.get("sources")
        _require(
            isinstance(sources, list)
            and len(sources) == len(expected_paths)
            and {item.get("key") for item in sources} == set(declared["source_keys"])
            and all(item.get("warm_extraction_attempts") == 0 for item in sources),
            f"{name} warm extraction attempts not zero",
        )
    else:
        command = declared.get("command")
        if not isinstance(command, list):
            raise ProductionError(f"{name} DEEP command is not a list")
        _require(
            "--target" in command
            and command.index("--target") + 1 < len(command)
            and command == result.get("identity", {}).get("command")
            and command == preflight.get("command")
            and command[command.index("--target") + 1]
            == str(next(iter(expected_paths)).rsplit("/", 1)[0])
            and preflight.get("inputs")
            == {path.rsplit("/", 1)[-1]: digest for path, digest in expected_paths.items()}
            and result.get("identity", {}).get("inputs") == preflight["inputs"]
            and result.get("source_count") == len(expected_paths),
            f"{name} DEEP command or inputs differ from frozen source subset",
        )
        for flag, value in (
            ("--backend", backend),
            ("--model", profile["model"]),
            ("--effort", profile["effort"]),
        ):
            _require(
                flag in command
                and command.index(flag) + 1 < len(command)
                and command[command.index(flag) + 1] == value,
                f"{name} DEEP command {flag} differs",
            )
        _require(
            result.get("warm_extraction_attempts") == 0,
            f"{name} warm extraction attempts not zero",
        )
    expected_argv = (
        ["mise", "run", "kb-graphify-ingest", "--", evidence["request"]]
        if mode == "NORMAL"
        else declared["command"]
    )
    audit_raw, reviews = _fact_audit(
        evidence,
        name=name,
        head=head,
        fork_commit=fork_commit,
        declaration_sha=declaration_sha,
    )
    cold = _phase(
        evidence["cold"],
        head=head,
        profile=frozen_profile,
        command=(result.get("cold_receipt"), expected_argv, reviews.get("cold")),
        cold=True,
    )
    warm = _phase(
        evidence["warm"],
        head=head,
        profile=frozen_profile,
        command=(result.get("warm_receipt"), expected_argv, reviews.get("warm")),
        cold=False,
    )
    if mode == "NORMAL":
        _normal_provenance(
            evidence,
            result,
            {item["key"]: expected_paths[item["path"]] for item in request_sources},
            cold,
            warm,
        )
    else:
        _deep_provenance(evidence, result, expected_paths, cold, warm)
    expected_graphs = (
        {item["graph_sha256"] for item in result["sources"]}
        if mode == "NORMAL"
        else {result["cold_graph"]["sha256"]}
    )
    _require(
        set(cold.pop("_graph_digests")) == set(warm.pop("_graph_digests")) == expected_graphs,
        f"{name} graphs differ from retained result",
    )
    _require(
        all(cold[key] == warm[key] for key in ("graph_nodes", "graph_links", "graph_sha256")),
        f"{name} warm graph differs",
    )
    _require(
        cold["producer_receipts_sha256"] == warm["producer_receipts_sha256"],
        f"{name} warm producer differs",
    )
    for phase in (cold, warm):
        phase.pop("_producer_ids")
        phase.pop("_producer_records")
    return {
        "name": name,
        "source": source,
        "backend": backend,
        "mode": mode,
        "request_sha256": _sha(
            _read(evidence["request"])
            if mode == "NORMAL"
            else json.dumps(declared["command"], separators=(",", ":")).encode()
        ),
        "profile_sha256": _sha(_read(evidence["profile"])),
        "facts_audit_sha256": _sha(audit_raw),
        "cold": cold,
        "warm": warm,
    }


def produce(matrix: dict[str, Any], *, candidate: Path, head: str, pr: int) -> bytes:
    """Derive canonical payload bytes from one frozen eight-case host matrix."""
    _require(pr > 0 and live_receipt.GIT_SHA.fullmatch(head), "PR or head invalid")
    actual = subprocess.run(
        ["git", "-C", str(candidate), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    _require(actual.returncode == 0 and actual.stdout.strip() == head, "candidate HEAD drift")
    status = subprocess.run(
        ["git", "-C", str(candidate), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    _require(status.returncode == 0 and not status.stdout, "candidate checkout is dirty")
    declaration_raw = _read(matrix["declaration"])
    declaration = json.loads(declaration_raw)
    _require(isinstance(declaration, dict), "declaration invalid")
    declaration_sha = _sha(declaration_raw)
    inputs_raw = _read(matrix["inputs_manifest"])
    inputs = json.loads(inputs_raw)
    _require(
        isinstance(inputs, dict) and isinstance(inputs.get("files"), dict),
        "input manifest invalid",
    )
    _require(bool(inputs["files"]), "input manifest has no source files")
    for path, expected_sha in inputs["files"].items():
        _require(
            isinstance(path, str)
            and isinstance(expected_sha, str)
            and _sha(_read(path)) == expected_sha,
            f"source input differs: {path}",
        )
    inputs_sha = _sha(inputs_raw)
    manifest_raw = _read(str(candidate / "sources/graphify.manifest"))
    fork_ref, fork_commit = live_receipt.manifest_identity(manifest_raw)
    _require(
        declaration.get("kb_commit") == head and declaration.get("fork_commit") == fork_commit,
        "declaration commit or fork differs",
    )
    declared_inputs = declaration.get("inputs")
    _require(isinstance(declared_inputs, list), "declaration inputs missing")
    _require(
        {item["path"]: item["sha256"] for item in declared_inputs} == inputs["files"],
        "declaration source hashes differ from input manifest",
    )
    cases = [
        _case(
            item,
            head=head,
            fork_commit=fork_commit,
            declaration_sha=declaration_sha,
            declaration=declaration,
        )
        for item in matrix["cases"]
    ]
    payload = {
        "schema": "graphify-live-v1",
        "repository": live_receipt.REPOSITORY,
        "pr_number": pr,
        "kb_commit": head,
        "fork_commit": fork_commit,
        "fork_ref": fork_ref,
        "issued_at_utc": datetime.now(UTC).isoformat(),
        "uv_lock_sha256": _sha(_read(str(candidate / "uv.lock"))),
        "source_manifest_sha256": _sha(manifest_raw),
        "inputs_sha256": inputs_sha,
        "declaration_sha256": declaration_sha,
        "cases": cases,
    }
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    live_receipt.validate_payload(raw, candidate_root=candidate, expected_pr=pr, expected_head=head)
    return raw


def main(argv: list[str] | None = None) -> int:
    """Sign and self-verify only a fully assembled exact-head receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--trusted-main", required=True, type=Path)
    parser.add_argument("--head", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        matrix = _json(str(args.matrix))
        raw = produce(matrix, candidate=args.candidate, head=args.head, pr=args.pr)
        _require(args.private_key.is_file(), "private signing key missing")
        _require(args.private_key.stat().st_mode & 0o077 == 0, "private key is readable by others")
        args.out.mkdir(parents=True, exist_ok=True)
        receipt = args.out / "live-receipt.json"
        receipt.write_bytes(raw)
        signed = subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "sign",
                "-f",
                str(args.private_key),
                "-n",
                live_receipt.NAMESPACE,
                str(receipt),
            ],
            capture_output=True,
            check=False,
            timeout=15,
        )
        _require(signed.returncode == 0, "SSH signing failed")
        live_receipt.verify_receipt(
            candidate_root=args.candidate,
            evidence_root=args.out,
            trusted_main_root=args.trusted_main,
            expected=live_receipt.ExpectedPullRequest(args.pr, args.head),
        )
    except (OSError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"live receipt production REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"live receipt signed: PR #{args.pr} at {args.head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
