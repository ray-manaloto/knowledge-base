from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import time
from pathlib import Path

import msgspec
from graphify.llm import _EXTRACTION_JSON_SCHEMA
from kb_setup import atomic
from kb_setup import graphify_semantic_adapter as adapter_contract
from kb_setup import graphify_semantic_corpus as corpus
from kb_setup import graphify_semantic_corpus_authority as prototype_authority
from kb_setup import graphify_semantic_corpus_prototype as prototype_contract
from kb_setup import graphify_semantic_slice as semantic


class PrototypeOutcome(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    schema_id: str
    status: str
    adapter_invocations: int
    provider_inferences: int
    chunk_ordinal: int
    chunk_total: int
    estimated_tokens: int
    prompt_sha256: str
    prompt_size: int
    elapsed_ms: int
    stage_receipt_sha256: str
    reasons: tuple[str, ...]


def encode(value: object) -> bytes:
    return msgspec.json.encode(value, order="sorted") + b"\n"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_outcome(root: Path, outcome: PrototypeOutcome) -> None:
    root.mkdir(parents=True, exist_ok=True)
    atomic.write_text(root / "prototype-receipt.json", encode(outcome).decode("utf-8"))


def parse_fragment(stdout: bytes) -> dict[str, object]:
    envelope, _observation = adapter_contract.parse_result_envelope(stdout)
    structured = envelope.get("structured_output")
    fragment = dict(structured) if isinstance(structured, dict) else {}
    if fragment:
        fragment.setdefault("hyperedges", [])
    return fragment


def main() -> int:
    repo = Path.cwd()
    plan = repo / "graphify-out/graphify-semantic-corpus"
    output = repo / "graphify-out/graphify-semantic-corpus-prototype-corrected"
    state = repo / "graphify-out/graphify-semantic-corpus-prototype-corrected-state"
    if (
        semantic.sha256_file(Path(prototype_contract.__file__))
        != prototype_authority.PROTOTYPE_CONTRACT_SHA256
    ):
        raise ValueError("prototype topology contract identity drifted")
    adapter_invocations = 0
    with tempfile.TemporaryDirectory(prefix="kb301-max-chunk-source-") as source_dir:
        source_root = Path(source_dir) / "graphify"
        corpus.admit_source(repo, source_root)
        boundary_path = prototype_contract.prepare_authorized_prototype(
            plan,
            source_root,
            output,
            state,
        )
        inventory, _advisories, _exclusions, ledger, config = corpus._typed_members(plan)
        chunk = max(ledger.chunks, key=lambda item: item.estimated_tokens)
        context = corpus._ProviderValidationContext(
            corpus.RetainedProviderEvidence(b"", b""),
            b"",
            tuple(dict.fromkeys(member.path for member in chunk.members)),
            chunk,
            (0, 0, 0),
            inventory,
            config,
            source_root,
        )
        prompt = corpus._chunk_prompt_bytes(context)
        prompt_sha = sha(prompt)
        if (
            chunk.ordinal != 22
            or chunk.total != 57
            or len(chunk.members) != 5
            or chunk.estimated_tokens != 19_985
            or config.token_budget != 20_000
            or config.timeout_seconds != 120
            or config.max_cost_usd != 0.25
            or config.concurrency != 1
            or config.claude_max_retries != 0
            or config.graphify_max_retry_depth != 0
            or config.structured_output_retries != 1
            or config.max_turns != 3
            or config.tools
            or config.claude_model != "claude-haiku-4-5-20251001"
            or prompt_sha != "4162fec1faa5fdf12f1e8149aa6dcb641b268799112e5e7a80cfd3781786d4d6"
        ):
            raise ValueError("prototype execution contract drifted")
        runtime = semantic.preflight(
            repo,
            graphify_version=config.graphify_version,
            require_max_turns=True,
        )
        if (
            runtime.auth.auth_method,
            runtime.auth.api_provider,
            runtime.auth.subscription_type,
            runtime.version,
            runtime.executable_sha256,
            runtime.help_sha256,
        ) != (
            "claude.ai",
            "firstParty",
            "max",
            config.claude_version,
            config.claude_executable_sha256,
            config.claude_help_sha256,
        ):
            raise ValueError("prototype provider preflight drifted")
        with (
            tempfile.TemporaryDirectory(prefix="kb301-max-chunk-adapter-") as adapter_dir,
            tempfile.TemporaryDirectory(prefix="kb301-max-chunk-metadata-") as metadata_dir,
        ):
            metadata_path = Path(metadata_dir) / "adapter-metadata.json"
            environment = semantic._adapter_environment(
                preflight_receipt=runtime,
                metadata_path=metadata_path,
                adapter_dir=Path(adapter_dir),
            )
            environment["KB_SEMANTIC_PROVIDER_BOUNDARY_PATH"] = str(boundary_path)
            adapter = Path(adapter_dir) / "claude"
            argv = (
                str(adapter),
                "-p",
                "--output-format",
                "json",
                "--no-session-persistence",
                "--model",
                config.claude_model,
                "--json-schema",
                _EXTRACTION_JSON_SCHEMA,
            )
            started = time.monotonic_ns()
            adapter_invocations = 1
            completed = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                check=False,
                env=prototype_contract.adapter_process_environment(os.environ, environment),
                timeout=130,
            )
            elapsed_ms = (time.monotonic_ns() - started) // 1_000_000
            fragment = parse_fragment(completed.stdout)
            metadata_raw = metadata_path.read_bytes() if metadata_path.is_file() else b""
            provider_inferences = int(boundary_path.is_file() or bool(metadata_raw))
            metadata = (
                msgspec.json.decode(
                    metadata_raw,
                    type=adapter_contract.AdapterMetadata,
                    strict=True,
                )
                if metadata_raw
                else None
            )
            records = [fragment.get(name) for name in ("nodes", "edges", "hyperedges")]
            counts = tuple(len(value) if isinstance(value, list) else 0 for value in records)
            scope_reasons = semantic.fragment_scope_reasons(
                fragment,
                source_paths=tuple(dict.fromkeys(member.path for member in chunk.members)),
            )
            adapter_reasons = (
                tuple(metadata.reasons)
                if metadata is not None
                else ("adapter-metadata-unavailable",)
            )
            call_reasons_list: list[str] = []
            if completed.returncode:
                call_reasons_list.append("adapter-returncode-nonzero")
            if completed.stderr:
                call_reasons_list.append("adapter-stderr-present")
            call_reasons_list.extend(adapter_reasons)
            call_reasons_list.extend(scope_reasons)
            call_reasons = tuple(dict.fromkeys(call_reasons_list))
            units = {unit.ordinal: unit for unit in inventory.units}
            fragment_raw = encode(fragment)
            chunk_evidence = tuple(
                semantic.ChunkEvidence(
                    ordinal=chunk.ordinal,
                    total=chunk.total,
                    source_path=unit.path,
                    source_git_object=unit.source_git_object,
                    source_sha256=unit.sha256,
                    source_size=corpus._source_unit_size(unit, source_root),
                    prompt_sha256=prompt_sha,
                    fragment_sha256=(metadata.structured_output_sha256 if metadata else ""),
                    node_count=counts[0],
                    edge_count=counts[1],
                    hyperedge_count=counts[2],
                )
                for member in chunk.members
                if (unit := units[member.unit_ordinal]) is not None
            )
            first = units[chunk.members[0].unit_ordinal]
            execution = semantic.ExecutionConfig(
                api_timeout_ms=config.timeout_seconds * 1000,
                claude_code_disable_nonessential_traffic=True,
                claude_code_disable_telemetry=True,
                claude_code_max_output_tokens=config.claude_max_output_tokens,
                claude_code_max_retries=config.claude_max_retries,
                max_structured_output_retries=config.structured_output_retries,
                graphify_api_timeout_seconds=config.timeout_seconds,
                graphify_no_incremental_cache=config.graphify_no_incremental_cache,
                chunk_size=config.graphify_chunk_size,
                token_budget=config.token_budget,
                max_concurrency=config.concurrency,
                max_retry_depth=config.graphify_max_retry_depth,
                deep_mode=config.deep_mode,
            )
            receipt = semantic.SemanticReceipt(
                schema_id="graphify-real-semantic-corpus-prototype/v0",
                status="complete" if not call_reasons else "failed",
                source=semantic.SourceIdentity(
                    source="graphify",
                    ref=inventory.source_ref,
                    commit=inventory.source_commit,
                    tree=inventory.source_tree,
                    path=f"ledger-chunk:{chunk.ordinal}",
                    git_object=first.source_git_object,
                    sha256=sha(encode(chunk)),
                    size=sum(
                        corpus._source_unit_size(units[m.unit_ordinal], source_root)
                        for m in chunk.members
                    ),
                ),
                runtime=runtime,
                adapter_metadata_sha256=sha(metadata_raw),
                semantic_fragment_sha256=sha(fragment_raw),
                chunks=chunk_evidence,
                execution_config=execution,
                attempts=1,
                backend=config.backend,
                model=config.claude_model,
                max_concurrency=config.concurrency,
                max_retry_depth=config.graphify_max_retry_depth,
                failed_chunks=0 if not call_reasons else 1,
                uncovered_files=(),
                out_of_scope_dropped=0,
                semantic_node_count=counts[0],
                semantic_edge_count=counts[1],
                semantic_hyperedge_count=counts[2],
                graph_node_count=counts[0],
                graph_edge_count=counts[1],
                warnings=(),
                errors=call_reasons,
            )
            receipt_raw = encode(receipt)
            run_namespace = sha((plan / "manifest.json").read_bytes() + b":prototype:max-chunk")
            stage = corpus.stage_chunk(
                plan,
                output,
                corpus.ChunkStageRequest(
                    source_root=source_root,
                    cache_namespace=config.cache_namespace_sha256,
                    run_namespace=run_namespace,
                    chunk=chunk,
                    fragment=fragment,
                    provider_evidence=corpus.RetainedProviderEvidence(
                        receipt_raw=receipt_raw,
                        adapter_metadata_raw=metadata_raw,
                    ),
                ),
            )
            stage_path = output / run_namespace / "chunks" / f"{chunk.ordinal:04d}" / "receipt.json"
            outcome = PrototypeOutcome(
                schema_id="graphify-semantic-corpus-prototype/v0",
                status=stage.status,
                adapter_invocations=adapter_invocations,
                provider_inferences=provider_inferences,
                chunk_ordinal=chunk.ordinal,
                chunk_total=chunk.total,
                estimated_tokens=chunk.estimated_tokens,
                prompt_sha256=prompt_sha,
                prompt_size=len(prompt),
                elapsed_ms=elapsed_ms,
                stage_receipt_sha256=corpus._sha_file(stage_path),
                reasons=stage.reasons,
            )
            write_outcome(output, outcome)
            print(encode(outcome).decode("utf-8").rstrip())
            return 0 if stage.status == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
