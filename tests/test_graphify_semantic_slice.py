# Copyright (c) 2026 Raymond Manaloto
"""Contract tests for the issue #300 real Graphify semantic-slice boundary.

These tests exercise policy and verifier semantics only. They are not a fake
provider and cannot certify the real-backend acceptance criterion; that requires
the repository task's retained real-run receipt.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from copy import deepcopy
from pathlib import Path

import msgspec
import pytest
from kb_setup import cli, graphify_baseline, graphify_sdk, graphify_semantic_slice

_MODEL = "claude-haiku-4-5-20251001"


def test_the_pinned_graphify_semantic_sdk_contract_is_current() -> None:
    """No version in the NAME — see the sibling in test_graphify_sdk.py."""
    assert graphify_sdk.semantic_contract_errors(graphify_baseline._ACCEPTED_GRAPHIFY_VERSION) == ()


def test_default_preflight_checks_the_current_graphify_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from kb_setup import graphify_env

    checked: list[str] = []
    monkeypatch.setattr(graphify_env, "assert_pinned_graphify", lambda _repo: None)

    def stop_after_version(version: str) -> None:
        checked.append(version)
        raise RuntimeError("version tripwire")

    monkeypatch.setattr(graphify_sdk, "assert_semantic_sdk", stop_after_version)

    with pytest.raises(RuntimeError, match="version tripwire"):
        graphify_semantic_slice.preflight(tmp_path, environment={"PATH": "/usr/bin"})

    assert checked == [graphify_baseline._ACCEPTED_GRAPHIFY_VERSION]


def test_enforcing_authority_never_widens_the_accepted_runtime_set(
    tmp_path: Path,
) -> None:
    """The two-tier runtime check, stated as an invariant rather than a snapshot.

    This test used to assert that the historical authority and the current
    runtime were DIFFERENT versions, and it passed only while the committed
    evidence lagged the pin. The v0.9.45 round re-ran the slice, so authority and
    current are momentarily the SAME value and the old assertion could not hold —
    not because the mechanism broke, but because it was asserting a transient
    condition of the repo instead of a property of the code.

    What is durable: `enforce_authority=True` accepts a SUBSET of what `False`
    accepts, the committed receipt is accepted either way, and a runtime that is
    neither authority nor current is rejected by both. That stays true whether or
    not the two constants currently agree.
    """
    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)
    receipt = msgspec.json.decode(
        (candidate / "receipt.json").read_bytes(),
        type=graphify_semantic_slice.SemanticReceipt,
        strict=True,
    )
    committed = receipt.runtime
    foreign = msgspec.structs.replace(
        committed,
        graphify_runtime=msgspec.structs.replace(
            committed.graphify_runtime, version="0.0.0-not-a-release"
        ),
    )

    assert graphify_semantic_slice._runtime_reasons(committed, enforce_authority=True) == []
    assert graphify_semantic_slice._runtime_reasons(committed, enforce_authority=False) == []
    # Rejected in BOTH modes — the control arm. Without it, "enforcing rejects it"
    # would be satisfied by a check that rejects everything.
    for enforce in (True, False):
        assert "receipt-runtime-mismatch" in graphify_semantic_slice._runtime_reasons(
            foreign, enforce_authority=enforce
        )


def test_adapter_keeps_historical_slice_argv_and_caps_only_301_boundary() -> None:
    from kb_setup import graphify_semantic_adapter

    profile = graphify_semantic_slice.SLICE_PROFILE
    legacy = graphify_semantic_adapter._claude_invocation_args(
        Path("/real/claude"), "{}", {}, profile
    )
    corpus = graphify_semantic_adapter._claude_invocation_args(
        Path("/real/claude"),
        "{}",
        {"KB_SEMANTIC_PROVIDER_BOUNDARY_PATH": "/state/provider-start.json"},
        profile,
    )

    assert len(legacy) == 18
    assert legacy[1:] == (
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--model",
        _MODEL,
        "--json-schema",
        "{}",
        "--safe-mode",
        "--tools",
        "",
        "--strict-mcp-config",
        "--permission-mode",
        "dontAsk",
        "--no-chrome",
        "--max-budget-usd",
        "0.25",
    )
    assert len(corpus) == 20
    assert corpus[:-2] == legacy
    assert corpus[-2:] == ("--max-turns", "3")


def test_cli_dispatches_semantic_slice_without_gating_public_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, list[str]]] = []

    def record(repo_root: Path, args: list[str]) -> int:
        calls.append((repo_root, args))
        return 0

    monkeypatch.setattr(graphify_semantic_slice, "semantic_main", record)

    assert cli.main(["graphify-semantic-slice", "verify"]) == 0
    assert calls == [(Path.cwd(), ["verify"])]


def test_real_run_preflights_before_source_materialization(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []

    # `**_kwargs` because `build_candidate` now calls `preflight(repo_root,
    # require_max_turns=True)`. A positional-only stub turns the signature change
    # into a TypeError that masks what this test is actually about — and it was
    # this test that caught the change, which is the stub earning its keep.
    def stop_at_preflight(
        _repo_root: Path, **_kwargs: object
    ) -> graphify_semantic_slice.ClaudePreflight:
        calls.append("preflight")
        raise RuntimeError("preflight tripwire")

    def forbidden_materialization(_repo_root: Path, _destination: Path) -> tuple[Path, object]:
        calls.append("source")
        raise AssertionError("source materialized before preflight")

    monkeypatch.setattr(graphify_semantic_slice, "preflight", stop_at_preflight)
    monkeypatch.setattr(graphify_semantic_slice, "_admit_source", forbidden_materialization)

    with pytest.raises(RuntimeError, match="preflight tripwire"):
        graphify_semantic_slice.build_candidate(tmp_path, tmp_path / "candidate")
    assert calls == ["preflight"]


def _successful_envelope() -> dict[str, object]:
    """Return the smallest redacted shape proven by the real #293 prototype."""
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "terminal_reason": "completed",
        "stop_reason": "tool_use",
        "num_turns": 3,
        "structured_output": {"nodes": [{}], "edges": [], "hyperedges": []},
        "modelUsage": {
            _MODEL: {
                "canonicalModel": "claude-haiku-4-5",
                "provider": "firstParty",
            }
        },
        "permission_denials": [],
        "errors": [],
    }


def test_route_controls_reject_overrides_by_name_without_reading_values() -> None:
    env = {
        "HOME": "/safe/home",
        "PATH": "/safe/bin",
        "ANTHROPIC_API_KEY": "must-not-be-read",
        "CLAUDE_CODE_USE_BEDROCK": "must-not-be-read",
    }

    assert graphify_semantic_slice.route_override_names(env) == (
        "ANTHROPIC_API_KEY",
        "CLAUDE_CODE_USE_BEDROCK",
    )


@pytest.mark.parametrize(
    "name",
    [
        "ANTHROPIC_BEDROCK_BASE_URL",
        "ANTHROPIC_CUSTOM_HEADERS",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_VERTEX_BASE_URL",
        "AWS_BEARER_TOKEN_BEDROCK",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_SKIP_BEDROCK_AUTH",
        "CLAUDE_CODE_SKIP_VERTEX_AUTH",
        "HTTPS_PROXY",
    ],
)
def test_route_controls_reject_each_documented_override(name: str) -> None:
    assert graphify_semantic_slice.route_override_names({name: "not-read"}) == (name,)
    assert (
        graphify_semantic_slice.route_override_names({"HOME": "/safe/home", "PATH": "/safe/bin"})
        == ()
    )


def test_scrub_route_overrides_removes_only_forbidden_names_and_returns_them() -> None:
    """Deletes the forbidden set and nothing else, and returns only their NAMES."""
    env = {
        "HOME": "/safe/home",
        "PATH": "/safe/bin",
        "AWS_ACCESS_KEY_ID": "must-not-be-read",
        "AWS_DEFAULT_REGION": "must-not-be-read",
        "AWS_REGION": "must-not-be-read",
        "AWS_SECRET_ACCESS_KEY": "must-not-be-read",
        "ANTHROPIC_API_KEY": "must-not-be-read",
    }

    removed = graphify_semantic_slice.scrub_route_overrides(env)

    assert removed == (
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_DEFAULT_REGION",
        "AWS_REGION",
        "AWS_SECRET_ACCESS_KEY",
    )
    assert env == {"HOME": "/safe/home", "PATH": "/safe/bin"}
    # Idempotent — a second call finds nothing left to remove.
    assert graphify_semantic_slice.scrub_route_overrides(env) == ()
    assert env == {"HOME": "/safe/home", "PATH": "/safe/bin"}


def test_preflight_passes_after_scrub_with_ambient_routing_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The end-to-end arm for #334: scrub, then the real process env is clean.

    Distinct from the dict-based arm above: this plants the forbidden names in
    the REAL `os.environ` via `monkeypatch.setenv` (auto-restored at teardown)
    and scrubs with NO argument, proving the default target is the live process
    environment `preflight` checks and every spawned `claude` child inherits —
    not a copy that would leave the real one untouched.
    """
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "planted")
    assert graphify_semantic_slice.route_override_names(os.environ) != ()

    removed = graphify_semantic_slice.scrub_route_overrides()

    assert {"AWS_REGION", "AWS_ACCESS_KEY_ID"} <= set(removed)
    assert graphify_semantic_slice.route_override_names(os.environ) == ()


def test_auth_classification_retains_only_public_routing_fields() -> None:
    raw = (
        b'{"loggedIn":true,"authMethod":"claude.ai","apiProvider":"firstParty",'
        b'"subscriptionType":"max","email":"private","orgId":"private"}'
    )

    identity = graphify_semantic_slice.classify_auth(raw)

    assert identity.logged_in
    assert identity.auth_method == "claude.ai"
    assert identity.api_provider == "firstParty"
    assert identity.subscription_type == "max"
    assert "private" not in graphify_semantic_slice.encode_json(identity).decode()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("loggedIn", False),
        ("authMethod", "api-key"),
        ("apiProvider", "bedrock"),
        ("subscriptionType", "pro"),
    ],
)
def test_auth_classification_rejects_each_non_max_route(field: str, value: object) -> None:
    payload = {
        "loggedIn": True,
        "authMethod": "claude.ai",
        "apiProvider": "firstParty",
        "subscriptionType": "max",
    }
    payload[field] = value

    with pytest.raises(ValueError, match=r"not claude\.ai first-party Max"):
        graphify_semantic_slice.classify_auth(msgspec.json.encode(payload))


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("subtype", "error_max_structured_output_retries", "result-subtype-invalid"),
        ("is_error", True, "result-error"),
        ("terminal_reason", "structured_output_retry_exhausted", "terminal-state-invalid"),
        # Still refused, but under its OWN reason: truncation is the one refusal
        # graphify can recover from by bisecting the chunk, and it could not tell
        # it from the rest while both were `stop-reason-invalid`.
        ("stop_reason", "max_tokens", graphify_semantic_slice.TRUNCATED_STOP_REASON),
        ("stop_reason", "refusal", "stop-reason-invalid"),
        ("num_turns", 4, "turn-bound-exceeded"),
        ("structured_output", None, "structured-output-missing"),
        ("permission_denials", ["denied"], "permission-denial-present"),
        ("errors", ["failed"], "error-present"),
        ("warnings", ["warning"], "warning-present"),
        ("fallback_models", ["fallback"], "fallback-model-present"),
        ("routing_overrides", {"route": "changed"}, "routing-override-present"),
        ("external_tools", ["Read"], "external-tool-present"),
    ],
)
def test_success_envelope_fails_closed_one_field_at_a_time(
    field: str, value: object, reason: str
) -> None:
    envelope = _successful_envelope()
    envelope[field] = value

    assert reason in graphify_semantic_slice.envelope_reasons(envelope)


def test_the_installed_graphify_classifies_our_truncation_hint_as_retryable() -> None:
    """The truncation hint only works if the PINNED graphify agrees it is one.

    The adapter refuses a truncated envelope and exits non-zero; graphify wraps
    that as `RuntimeError("claude -p exited 1: <stderr>")` and decides whether to
    bisect the chunk by substring-matching the stringified exception. So the
    recovery rests on a string agreeing with a marker list this repo does not
    own, and a reworded marker upstream would disable it with nothing failing.

    Asserted against graphify's OWN helper rather than against a copy of its
    markers, because a copy would keep agreeing with itself after upstream moved.
    The control arm is the second assertion: an ordinary refusal must NOT be
    classified as retryable, or this test would pass for a helper that says yes
    to everything.
    """
    from graphify.llm import _looks_like_context_exceeded

    truncated = RuntimeError(
        "claude -p exited 1: semantic adapter rejected result: "
        f"{graphify_semantic_slice.TRUNCATED_STOP_REASON}\n"
        f"{graphify_semantic_slice.TRUNCATION_RETRY_HINT}"
    )
    assert _looks_like_context_exceeded(truncated), (
        "graphify no longer classifies the truncation hint as a context overflow, "
        "so adaptive retry will drop truncated chunks instead of bisecting them"
    )

    ordinary = RuntimeError(
        "claude -p exited 1: semantic adapter rejected result: stop-reason-invalid"
    )
    assert not _looks_like_context_exceeded(ordinary), (
        "an ordinary refusal is being read as retryable, so this probe cannot "
        "discriminate and proves nothing about the hint"
    )


def test_only_a_truncation_refusal_earns_the_retry_hint() -> None:
    """The hint must reach stderr for truncation and for nothing else.

    Both directions matter and they fail in opposite ways. Without the hint on a
    truncated chunk, adaptive retry never bisects and the chunk is lost. With the
    hint on an ordinary refusal, graphify bisects a chunk whose halves will fail
    exactly the same way — burning `max_retry_depth` calls to reach the same
    answer, which is the more expensive mistake of the two.
    """
    assert (
        graphify_semantic_slice.truncation_retry_hint(
            (graphify_semantic_slice.TRUNCATED_STOP_REASON,)
        )
        == graphify_semantic_slice.TRUNCATION_RETRY_HINT
    )
    assert graphify_semantic_slice.truncation_retry_hint(("stop-reason-invalid",)) is None
    assert graphify_semantic_slice.truncation_retry_hint(()) is None
    # Truncation alongside other refusals still earns it: a truncated response
    # routinely trips the structured-output checks too, and reading only the
    # first reason would drop the hint for every realistic truncation.
    assert (
        graphify_semantic_slice.truncation_retry_hint(
            ("structured-output-missing", graphify_semantic_slice.TRUNCATED_STOP_REASON)
        )
        == graphify_semantic_slice.TRUNCATION_RETRY_HINT
    )


def test_the_adapter_wires_the_hint_into_the_refusal_it_actually_prints(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Arm the adapter's WIRING, not only the decision it delegates.

    `truncation_retry_hint` is armed directly above, but nothing asserted that
    the adapter's refusal path CALLS it. That branch lived inline in
    `adapter_main`, which no test invokes, so deleting the call left the whole
    suite green — the decision was armed and its one consumer was not.
    `_report_rejection` exists as a named function so this test can reach it.

    Both directions, for the reason the sibling test gives: no hint on a
    truncated chunk and graphify drops it instead of bisecting; a hint on an
    ordinary refusal and graphify burns `max_retry_depth` bisecting halves that
    fail identically.
    """
    from kb_setup import graphify_semantic_adapter

    assert (
        graphify_semantic_adapter._report_rejection(
            (graphify_semantic_slice.TRUNCATED_STOP_REASON,)
        )
        == 1
    )
    truncated = capsys.readouterr().err
    assert (
        "semantic adapter rejected result: " + graphify_semantic_slice.TRUNCATED_STOP_REASON
    ) in truncated
    assert graphify_semantic_slice.TRUNCATION_RETRY_HINT in truncated

    assert graphify_semantic_adapter._report_rejection(("stop-reason-invalid",)) == 1
    ordinary = capsys.readouterr().err
    assert "semantic adapter rejected result: stop-reason-invalid" in ordinary
    assert graphify_semantic_slice.TRUNCATION_RETRY_HINT not in ordinary


def test_process_level_refusals_join_the_envelope_reasons_in_first_seen_order() -> None:
    """A non-zero exit and any stderr are refusals in their own right.

    Armed with a control: the same envelope through a clean process must yield
    NO reasons, or this test would pass for a collector that refuses everything.
    """
    import subprocess

    from kb_setup import graphify_semantic_adapter

    failed = subprocess.CompletedProcess(args=(), returncode=1, stdout=b"", stderr=b"boom")
    assert graphify_semantic_adapter._completion_reasons(_successful_envelope(), {}, failed) == (
        "claude-returncode-nonzero",
        "claude-stderr-present",
    )

    clean = subprocess.CompletedProcess(args=(), returncode=0, stdout=b"", stderr=b"")
    assert graphify_semantic_adapter._completion_reasons(_successful_envelope(), {}, clean) == ()


def test_tool_use_is_accepted_only_with_the_full_proven_success_envelope() -> None:
    assert graphify_semantic_slice.envelope_reasons(_successful_envelope()) == ()

    multiple_models = deepcopy(_successful_envelope())
    usage = multiple_models["modelUsage"]
    assert isinstance(usage, dict)
    usage["claude-fallback"] = {"canonicalModel": "fallback", "provider": "firstParty"}

    assert "model-identity-invalid" in graphify_semantic_slice.envelope_reasons(multiple_models)


def test_corpus_observes_positive_turn_count_without_an_unenforced_upper_bound() -> None:
    envelope = _successful_envelope()
    envelope["num_turns"] = 4

    assert graphify_semantic_slice.envelope_reasons(envelope, max_turns=None) == ()
    assert "turn-bound-exceeded" in graphify_semantic_slice.envelope_reasons(envelope)


def test_fragment_validation_rejects_unresolved_edges_and_wrong_source() -> None:
    fragment = {
        "nodes": [
            {
                "id": "n1",
                "label": "Graphify",
                "source_file": "docs/how-it-works.md",
                "_origin": "semantic",
            }
        ],
        "edges": [
            {
                "source": "n1",
                "target": "missing",
                "relation": "documents",
                "source_file": "other.md",
                "_origin": "semantic",
            }
        ],
        "hyperedges": [],
    }

    reasons = graphify_semantic_slice.fragment_reasons(fragment, source_path="docs/how-it-works.md")

    assert "unresolved-edge-endpoint" in reasons
    assert "fragment-source-scope-mismatch" in reasons


@pytest.mark.parametrize(
    ("fragment", "reason"),
    [
        ({"nodes": [{"id": []}], "edges": [], "hyperedges": []}, "semantic-node-identity-invalid"),
        (
            {"nodes": [{"id": "n"}], "edges": [{"source": [], "target": "n"}], "hyperedges": []},
            "unresolved-edge-endpoint",
        ),
        (
            {"nodes": [{"id": "n"}], "edges": [], "hyperedges": [{"nodes": [{}]}]},
            "unresolved-hyperedge-member",
        ),
    ],
)
def test_fragment_validation_returns_typed_failure_for_unhashable_identifiers(
    fragment: dict[str, object], reason: str
) -> None:
    assert reason in graphify_semantic_slice.fragment_reasons(
        fragment, source_path="docs/how-it-works.md"
    )


@pytest.mark.parametrize("name", ["failed_chunks", "out_of_scope_dropped"])
def test_missing_negative_coverage_field_is_not_treated_as_zero(name: str) -> None:
    assert graphify_semantic_slice._result_integer({}, name) == -1


def test_adapter_normalizes_stream_when_exactly_one_result_is_final() -> None:
    from kb_setup import graphify_semantic_adapter

    payload = msgspec.json.encode([{"type": "error"}, _successful_envelope()])
    envelope, observation = graphify_semantic_adapter.parse_result_envelope(payload)

    assert envelope == _successful_envelope()
    assert observation.status == "accepted-result-array"
    assert (observation.event_count, observation.result_count, observation.selected_index) == (
        2,
        1,
        1,
    )


def _candidate_member(name: str, raw: bytes) -> graphify_semantic_slice.ArtifactMember:
    return graphify_semantic_slice.ArtifactMember(
        name=name,
        sha256=hashlib.sha256(raw).hexdigest(),
        size=len(raw),
    )


_REAL_CANDIDATE = Path(__file__).parent.parent / "graphify-out" / "graphify-semantic-slice"


def _copy_real_candidate(root: Path) -> None:
    """Copy the retained real provider evidence for policy mutation tests."""
    shutil.copytree(_REAL_CANDIDATE, root)


def _replace_candidate_payloads(candidate: Path, changed: dict[str, bytes]) -> None:
    """Rewrite selected copied-real members and rehash their manifest entries."""
    for name, raw in changed.items():
        (candidate / name).write_bytes(raw)
    manifest = msgspec.json.decode(
        (candidate / "manifest.json").read_bytes(),
        type=graphify_semantic_slice.CandidateManifest,
    )
    manifest = msgspec.structs.replace(
        manifest,
        members=tuple(
            _candidate_member(member.name, changed[member.name])
            if member.name in changed
            else member
            for member in manifest.members
        ),
    )
    (candidate / "manifest.json").write_bytes(graphify_semantic_slice.encode_json(manifest) + b"\n")


def test_retained_real_candidate_is_structurally_valid_and_publicly_accepted(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)

    staged = graphify_semantic_slice._verify_candidate(candidate, enforce_authority=False)
    result = graphify_semantic_slice.verify_candidate(candidate)

    assert staged.state == "unapproved"
    assert staged.structural_complete
    assert not staged.real_semantic_complete
    assert staged.reasons == ()
    assert result.state == "complete"
    assert result.structural_complete
    assert result.real_semantic_complete
    assert result.reasons == ()


def test_public_verifier_rejects_member_bytes_changed_after_manifest(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)
    (candidate / "semantic-fragment.json").write_bytes(b"{}\n")

    result = graphify_semantic_slice._verify_candidate(candidate, enforce_authority=False)

    assert not result.real_semantic_complete
    assert "member-digest-mismatch:semantic-fragment.json" in result.reasons


def test_public_verifier_rejects_expected_member_symlink_before_read(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)
    fragment = candidate / "semantic-fragment.json"
    target = tmp_path / "outside.json"
    target.write_bytes(fragment.read_bytes())
    fragment.unlink()
    fragment.symlink_to(target)

    result = graphify_semantic_slice._verify_candidate(candidate, enforce_authority=False)

    assert not result.real_semantic_complete
    assert "candidate-entry-not-regular:semantic-fragment.json" in result.reasons


def test_public_verifier_rejects_rehashed_wrong_source_authority(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)
    receipt = msgspec.json.decode(
        (candidate / "receipt.json").read_bytes(),
        type=graphify_semantic_slice.SemanticReceipt,
    )
    changed_source = msgspec.structs.replace(receipt.source, commit="0" * 40)
    changed_receipt = msgspec.structs.replace(receipt, source=changed_source)
    changed_raw = graphify_semantic_slice.encode_json(changed_receipt) + b"\n"
    (candidate / "receipt.json").write_bytes(changed_raw)
    manifest = msgspec.json.decode(
        (candidate / "manifest.json").read_bytes(),
        type=graphify_semantic_slice.CandidateManifest,
    )
    members = tuple(
        _candidate_member(member.name, changed_raw) if member.name == "receipt.json" else member
        for member in manifest.members
    )
    changed_manifest = msgspec.structs.replace(manifest, members=members)
    (candidate / "manifest.json").write_bytes(
        graphify_semantic_slice.encode_json(changed_manifest) + b"\n"
    )

    public = graphify_semantic_slice.verify_candidate(candidate)
    result = graphify_semantic_slice._verify_candidate(candidate, enforce_authority=False)

    assert public.reasons == ("candidate-authority-mismatch",)
    assert not result.real_semantic_complete
    assert "receipt-source-identity-mismatch" in result.reasons


def test_manifest_member_set_failure_stops_before_attacker_path_read(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)
    manifest = msgspec.json.decode(
        (candidate / "manifest.json").read_bytes(),
        type=graphify_semantic_slice.CandidateManifest,
    )
    outside = tmp_path / "outside-private.json"
    outside.write_text("must-not-be-read")
    hostile = msgspec.structs.replace(
        manifest,
        members=(*manifest.members[:-1], _candidate_member(str(outside), b"must-not-be-read")),
    )
    (candidate / "manifest.json").write_bytes(graphify_semantic_slice.encode_json(hostile) + b"\n")

    result = graphify_semantic_slice._verify_candidate(candidate, enforce_authority=False)

    assert result.reasons == ("manifest-member-set-mismatch",)


def test_staged_verifier_rejects_execution_config_mutation(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)
    receipt = msgspec.json.decode(
        (candidate / "receipt.json").read_bytes(),
        type=graphify_semantic_slice.SemanticReceipt,
    )
    changed_config = msgspec.structs.replace(receipt.execution_config, claude_code_max_retries=1)
    changed_receipt = msgspec.structs.replace(receipt, execution_config=changed_config)
    receipt_raw = graphify_semantic_slice.encode_json(changed_receipt) + b"\n"
    _replace_candidate_payloads(candidate, {"receipt.json": receipt_raw})

    result = graphify_semantic_slice._verify_candidate(candidate, enforce_authority=False)

    assert "receipt-execution-config-mismatch" in result.reasons


def test_staged_verifier_rejects_json_schema_argv_mutation(tmp_path: Path) -> None:
    from kb_setup.graphify_semantic_adapter import AdapterMetadata

    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)
    metadata = msgspec.json.decode(
        (candidate / "adapter-metadata.json").read_bytes(), type=AdapterMetadata
    )
    argv = list(metadata.argv)
    argv[7] = "{}"
    metadata_raw = (
        graphify_semantic_slice.encode_json(msgspec.structs.replace(metadata, argv=tuple(argv)))
        + b"\n"
    )
    receipt = msgspec.json.decode(
        (candidate / "receipt.json").read_bytes(),
        type=graphify_semantic_slice.SemanticReceipt,
    )
    receipt_raw = (
        graphify_semantic_slice.encode_json(
            msgspec.structs.replace(
                receipt,
                adapter_metadata_sha256=hashlib.sha256(metadata_raw).hexdigest(),
            )
        )
        + b"\n"
    )
    _replace_candidate_payloads(
        candidate,
        {"adapter-metadata.json": metadata_raw, "receipt.json": receipt_raw},
    )

    result = graphify_semantic_slice._verify_candidate(candidate, enforce_authority=False)

    assert "adapter-schema-digest-mismatch" in result.reasons


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        (
            {"claude_executable": "/Users/private/account/bin/claude"},
            "adapter-executable-name-mismatch",
        ),
        ({"claude_version": "0.0.0 (Other)"}, "adapter-version-mismatch"),
        ({"duration_ms": 0}, "adapter-duration-invalid"),
        ({"duration_api_ms": 999_999}, "adapter-duration-invalid"),
        ({"elapsed_ms": 0}, "adapter-duration-invalid"),
        ({"total_cost_usd": 99.0}, "adapter-cost-invalid"),
        ({"response_sha256": ""}, "adapter-response-digest-invalid"),
        ({"stderr_sha256": "not-a-sha"}, "adapter-stderr-digest-mismatch"),
        ({"input_tokens": 41}, "adapter-token-count-mismatch"),
    ],
)
def test_staged_verifier_rejects_metadata_identity_bound_and_privacy_drift(
    tmp_path: Path, changes: dict[str, object], reason: str
) -> None:
    from kb_setup.graphify_semantic_adapter import AdapterMetadata

    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)
    metadata = msgspec.json.decode(
        (candidate / "adapter-metadata.json").read_bytes(), type=AdapterMetadata
    )
    metadata_raw = (
        graphify_semantic_slice.encode_json(msgspec.structs.replace(metadata, **changes)) + b"\n"
    )
    receipt = msgspec.json.decode(
        (candidate / "receipt.json").read_bytes(),
        type=graphify_semantic_slice.SemanticReceipt,
    )
    receipt_raw = (
        graphify_semantic_slice.encode_json(
            msgspec.structs.replace(
                receipt,
                adapter_metadata_sha256=hashlib.sha256(metadata_raw).hexdigest(),
            )
        )
        + b"\n"
    )
    _replace_candidate_payloads(
        candidate,
        {"adapter-metadata.json": metadata_raw, "receipt.json": receipt_raw},
    )

    result = graphify_semantic_slice._verify_candidate(candidate, enforce_authority=False)

    assert reason in result.reasons


def test_staged_verifier_rejects_negative_model_usage_counter(tmp_path: Path) -> None:
    from kb_setup.graphify_semantic_adapter import AdapterMetadata

    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)
    metadata = msgspec.json.decode(
        (candidate / "adapter-metadata.json").read_bytes(), type=AdapterMetadata
    )
    model_usage = (msgspec.structs.replace(metadata.model_usage[0], cache_read_input_tokens=-1),)
    metadata_raw = (
        graphify_semantic_slice.encode_json(
            msgspec.structs.replace(metadata, model_usage=model_usage)
        )
        + b"\n"
    )
    receipt = msgspec.json.decode(
        (candidate / "receipt.json").read_bytes(),
        type=graphify_semantic_slice.SemanticReceipt,
    )
    receipt_raw = (
        graphify_semantic_slice.encode_json(
            msgspec.structs.replace(
                receipt,
                adapter_metadata_sha256=hashlib.sha256(metadata_raw).hexdigest(),
            )
        )
        + b"\n"
    )
    _replace_candidate_payloads(
        candidate,
        {"adapter-metadata.json": metadata_raw, "receipt.json": receipt_raw},
    )

    result = graphify_semantic_slice._verify_candidate(candidate, enforce_authority=False)

    assert "adapter-model-token-count-invalid" in result.reasons


def test_public_verifier_rejects_rehashed_fragment_not_returned_by_claude(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)
    fragment = msgspec.json.decode((candidate / "semantic-fragment.json").read_bytes())
    assert isinstance(fragment, dict)
    nodes = fragment["nodes"]
    assert isinstance(nodes, list)
    assert isinstance(nodes[0], dict)
    nodes[0]["label"] = "tampered"
    fragment_raw = graphify_semantic_slice.encode_json(fragment) + b"\n"
    (candidate / "semantic-fragment.json").write_bytes(fragment_raw)
    receipt = msgspec.json.decode(
        (candidate / "receipt.json").read_bytes(),
        type=graphify_semantic_slice.SemanticReceipt,
    )
    receipt = msgspec.structs.replace(
        receipt,
        semantic_fragment_sha256=hashlib.sha256(fragment_raw).hexdigest(),
    )
    receipt_raw = graphify_semantic_slice.encode_json(receipt) + b"\n"
    (candidate / "receipt.json").write_bytes(receipt_raw)
    manifest = msgspec.json.decode(
        (candidate / "manifest.json").read_bytes(),
        type=graphify_semantic_slice.CandidateManifest,
    )
    changed = {
        "receipt.json": receipt_raw,
        "semantic-fragment.json": fragment_raw,
    }
    manifest = msgspec.structs.replace(
        manifest,
        members=tuple(
            _candidate_member(member.name, changed[member.name])
            if member.name in changed
            else member
            for member in manifest.members
        ),
    )
    (candidate / "manifest.json").write_bytes(graphify_semantic_slice.encode_json(manifest) + b"\n")

    result = graphify_semantic_slice._verify_candidate(candidate, enforce_authority=False)

    assert not result.real_semantic_complete
    assert "adapter-structured-output-digest-mismatch" in result.reasons


def test_staged_verifier_returns_typed_failure_for_rehashed_malformed_fragment(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate"
    _copy_real_candidate(candidate)
    fragment_raw = b'{"edges":[],"hyperedges":[],"nodes":{}}\n'
    receipt = msgspec.json.decode(
        (candidate / "receipt.json").read_bytes(),
        type=graphify_semantic_slice.SemanticReceipt,
    )
    receipt_raw = (
        graphify_semantic_slice.encode_json(
            msgspec.structs.replace(
                receipt,
                semantic_fragment_sha256=hashlib.sha256(fragment_raw).hexdigest(),
            )
        )
        + b"\n"
    )
    _replace_candidate_payloads(
        candidate,
        {"receipt.json": receipt_raw, "semantic-fragment.json": fragment_raw},
    )

    result = graphify_semantic_slice._verify_candidate(candidate, enforce_authority=False)

    assert result.state == "failed"
    assert result.reasons == ("fragment-schema-invalid",)


def test_current_claude_reads_the_current_constants_not_the_accepted_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two constants, two questions — collapsing them invalidates committed evidence.

    `_ACCEPTED_CLAUDE_*` is the authority for the COMMITTED slice receipt: a run
    that already happened, which no edit here can change. `current_claude()` is
    what a NEW run may use, and it is what the corpus plan pins.

    This arm exists because the two WERE collapsed once already, for about
    twenty minutes: Claude Code self-updated, advancing "the accepted version"
    looked like ordinary currency work, and it turned the committed slice
    candidate from `unapproved` to `failed` — evidence refused for a fact about
    the world rather than about itself. The suite caught it; reading the diff
    had not.

    Re-derived after the graphify 0.9.48 re-attest: the slice was re-run at
    2.1.238 in this same change, so ACCEPTED and CURRENT now hold the SAME value
    — a coincidence of evidence, not a merge of the two questions. Asserting
    `current.version != _ACCEPTED_CLAUDE_VERSION` would therefore be asserting a
    fact about today's repo state rather than about `current_claude()`, exactly
    the failure mode `test_authority_path_still_refuses_the_current_graphify_runtime`
    hit at the same bump. Proven instead by monkeypatching CURRENT away from
    ACCEPTED and confirming `current_claude()` follows it: an implementation that
    quietly returned `_ACCEPTED_*` would pass every other test in this file today
    and only fail once the two next diverge.
    """
    monkeypatch.setattr(graphify_semantic_slice, "_CURRENT_CLAUDE_VERSION", "9.9.9-not-accepted")
    monkeypatch.setattr(graphify_semantic_slice, "_CURRENT_CLAUDE_EXECUTABLE_SHA256", "f" * 64)

    current = graphify_semantic_slice.current_claude()

    assert current.version == "9.9.9-not-accepted"
    assert current.executable_sha256 == "f" * 64
    assert current.version != graphify_semantic_slice._ACCEPTED_CLAUDE_VERSION
    assert current.executable_sha256 != graphify_semantic_slice._ACCEPTED_CLAUDE_EXECUTABLE_SHA256
    # The CLI contract is the thing that must NOT have moved — that identity is
    # what makes advancing the version a mechanical bump rather than a review.
    # Unpatched here, so this reads the REAL current help digest, which still
    # equals the accepted one (`_CURRENT_CLAUDE_HELP_SHA256` is bound from
    # `_ACCEPTED_CLAUDE_HELP_SHA256` at import time, not a live alias).
    assert current.help_sha256 == graphify_semantic_slice._ACCEPTED_CLAUDE_HELP_SHA256


def test_the_corpus_plan_pins_the_current_claude_not_the_accepted_one() -> None:
    """The planner must declare what will run, not what already ran.

    Without this the corpus preflight refuses on a version nobody reviewed — or,
    worse, the plan records the version of a receipt from a different run and
    reads as internally consistent.
    """
    from kb_setup import graphify_semantic_corpus

    current = graphify_semantic_slice.current_claude()

    assert current.version == graphify_semantic_corpus._CLAUDE_VERSION
    assert current.executable_sha256 == graphify_semantic_corpus._CLAUDE_EXECUTABLE_SHA256
    assert current.help_sha256 == graphify_semantic_corpus._CLAUDE_HELP_SHA256


def _preflight_for(
    runtime: graphify_baseline.RuntimeIdentity, graphify_version: str
) -> graphify_semantic_slice.ClaudePreflight:
    """A preflight that differs from an accepted one ONLY in the graphify pair.

    Every other field is set to what `_runtime_reasons` accepts, so any reason it
    returns is attributable to the pair under test rather than to the fixture.
    """
    return graphify_semantic_slice.ClaudePreflight(
        executable="claude",
        executable_sha256=graphify_semantic_slice._ACCEPTED_CLAUDE_EXECUTABLE_SHA256,
        version=graphify_semantic_slice._ACCEPTED_CLAUDE_VERSION,
        help_sha256=graphify_semantic_slice._ACCEPTED_CLAUDE_HELP_SHA256,
        required_flags=(*graphify_semantic_slice._REQUIRED_CLAUDE_FLAGS, "--max-turns"),
        # `_runtime_reasons` does not inspect auth, so any well-formed identity
        # keeps this fixture from being the thing under test.
        auth=graphify_semantic_slice.AuthIdentity(
            logged_in=True,
            auth_method="subscription",
            api_provider="firstParty",
            subscription_type="max",
        ),
        environment_names=tuple(sorted({*graphify_semantic_slice._CHILD_CONTROL_ENV, "PATH"})),
        graphify_runtime=runtime,
        graphify_version=graphify_version,
        graphify_semantic_fingerprint_sha256=(
            graphify_semantic_slice._ACCEPTED_SEMANTIC_FINGERPRINT_SHA256
        ),
    )


_PAIR_REASONS = frozenset({"receipt-runtime-mismatch", "receipt-graphify-version-mismatch"})


def test_non_authority_path_accepts_the_current_graphify_runtime() -> None:
    """The CURRENT runtime must be matchable on the non-authority path.

    This is the test that was missing, and its absence is why a failure this
    file DOCUMENTED IN ADVANCE shipped twice. `_runtime_reasons` matches
    `(graphify_runtime, graphify_version)` against accepted pairs. The
    0.9.46 -> 0.9.47 bump advanced `_CURRENT_GRAPHIFY_RUNTIME` and left its
    hand-written partner literal at "0.9.46", so the pair became unmatchable and
    the non-authority path rejected EVERY run under the installed version —
    while the suite stayed green, because nothing exercised this path. The
    comment at the pairing site had predicted exactly that, having been written
    after the same slip at 0.9.46.

    Asserted on the CONSTANT rather than on the installed binary on purpose: the
    installed version moves under the session, and a test that reads it would go
    red on a self-update instead of on the defect it is here to catch.
    """
    current = graphify_semantic_slice._CURRENT_GRAPHIFY_RUNTIME
    reasons = graphify_semantic_slice._runtime_reasons(
        _preflight_for(current, current.version), enforce_authority=False
    )
    assert _PAIR_REASONS.isdisjoint(reasons), reasons


def test_authority_path_still_refuses_a_runtime_that_is_not_accepted() -> None:
    """The FAIL direction, re-derived after the 0.9.48 re-attest converged the pair.

    This used to refuse CURRENT specifically, on the premise that CURRENT and
    ACCEPTED were different versions — true right up until the 0.9.48 re-attest
    committed the slice receipt AT the installed runtime, converging the two by
    construction. That premise being gone is not a defect (the vacuity guard the
    prior form carried would have said so loudly), so this is re-derived rather
    than deleted, exactly as `test_the_current_graphify_runtime_tracks_the_pinned_manifest_ref`'s
    docstring anticipates for its own constant.

    The authority path must still refuse anything OTHER than the exact accepted
    identity. Proven with a SYNTHETIC identity differing from accepted in one
    digest only — never in the version string — so the arm shows the check
    compares the whole identity rather than merely a version number.
    """
    accepted = graphify_semantic_slice._ACCEPTED_GRAPHIFY_RUNTIME
    synthetic = msgspec.structs.replace(accepted, sdk_fingerprint_sha256="0" * 64)
    assert synthetic != accepted, "fixture must actually differ from the accepted identity"

    reasons = graphify_semantic_slice._runtime_reasons(
        _preflight_for(synthetic, synthetic.version), enforce_authority=True
    )
    assert "receipt-runtime-mismatch" in reasons


def test_a_version_skewed_from_its_runtime_is_still_refused() -> None:
    """CLI/SDK skew must still be caught — that is what the pair is FOR.

    Deriving the version half from the runtime half removed a restatement that
    drifted twice; it must not have removed the check. A preflight whose SDK
    reports a different version than its runtime identity is exactly the skew
    nobody reviewed, and it is refused on both paths.
    """
    current = graphify_semantic_slice._CURRENT_GRAPHIFY_RUNTIME
    skewed = _preflight_for(current, "0.0.0-not-the-runtime-version")
    for enforce in (True, False):
        reasons = graphify_semantic_slice._runtime_reasons(skewed, enforce_authority=enforce)
        assert "receipt-graphify-version-mismatch" in reasons, (enforce, reasons)


def test_the_current_graphify_runtime_tracks_the_pinned_manifest_ref() -> None:
    """The CURRENT runtime must not lag the pin — the OTHER half of the defect.

    `test_non_authority_path_accepts_the_current_graphify_runtime` proves the
    pair agrees with ITSELF, which is the restatement bug. It stays green with
    both halves left a release behind, so it cannot see STALENESS — measured, not
    assumed: a `kb-arms` mutation reverting this constant to 0.9.47 SURVIVED that
    test. This is the arm that kills it.

    Bound to `sources/graphify.manifest` rather than to the installed binary on
    purpose. `_CURRENT_GRAPHIFY_RUNTIME` declares what a NEW run may use, and the
    manifest is the committed statement of what this repo runs — stable, reviewed,
    and moved deliberately. Reading `graphify --version` here would instead redden
    the suite whenever the host updates out from under it, which is a fact about
    the machine and not about this constant.
    """
    from kb_setup import manifest

    pinned = manifest.load(Path("sources/graphify.manifest")).ref
    current = graphify_semantic_slice._CURRENT_GRAPHIFY_RUNTIME
    assert pinned == f"v{current.version}", (
        f"sources/graphify.manifest pins {pinned} but _CURRENT_GRAPHIFY_RUNTIME "
        f"declares {current.version}. A bump moves BOTH, and the version half of "
        f"every accepted pair derives from this object — so leaving it behind "
        f"rejects every non-authority run under the installed version."
    )
    assert current.cli_version == current.version, "cli_version drifted from version"
    assert current.sdk_version == current.version, "sdk_version drifted from version"
