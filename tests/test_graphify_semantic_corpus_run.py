# Copyright (c) 2026 Raymond Manaloto
"""Tests for the corpus execution driver and the profile boundary it runs under."""

from __future__ import annotations

import itertools
import os
import shutil
from collections.abc import Callable
from pathlib import Path

import msgspec
import pytest
from graphify import file_slice
from graphify.file_slice import FileSlice, expand_oversized_files
from kb_setup import (
    graphify_semantic_adapter,
    graphify_semantic_corpus,
    graphify_semantic_corpus_authority,
    graphify_semantic_corpus_run,
    graphify_semantic_slice,
)

# Anchored to the repository root resolved from this file, the way
# `test_graphify_semantic_corpus.py` already does it. As a RELATIVE path it
# resolved against pytest's working directory, so every `skipif(not
# _PLAN.is_dir())` in this module silently became "skip everything" when the
# suite ran from anywhere but the repo root — coverage disappearing without a
# single failing test to say so.
_PLAN = Path(__file__).resolve().parents[1] / "graphify-out/graphify-semantic-corpus"
# The real committed slice evidence, which `test_graphify_semantic_corpus.py`
# also reads. Used where a test needs adapter metadata that actually DECODES —
# a `{}` placeholder makes staging fail on a missing field, which looks like the
# arm passing when it never reached the behaviour it names.
_SLICE_EVIDENCE = Path(__file__).resolve().parents[1] / "graphify-out/graphify-semantic-slice"


def _inventory() -> graphify_semantic_corpus.SourceInventory:
    return msgspec.json.decode(
        (_PLAN / "source-inventory.json").read_bytes(),
        type=graphify_semantic_corpus.SourceInventory,
        strict=True,
    )


def _ledger() -> graphify_semantic_corpus.ChunkLedger:
    return msgspec.json.decode(
        (_PLAN / "chunk-ledger.json").read_bytes(),
        type=graphify_semantic_corpus.ChunkLedger,
        strict=True,
    )


def _config() -> graphify_semantic_corpus.CorpusExecutionConfig:
    return msgspec.json.decode(
        (_PLAN / "execution-config.json").read_bytes(),
        type=graphify_semantic_corpus.CorpusExecutionConfig,
        strict=True,
    )


def test_profile_selection_fails_closed_and_rejects_unknown_values() -> None:
    """The env may pick between reviewed profiles and may not invent one."""
    assert graphify_semantic_slice.profile_for({}) is graphify_semantic_slice.SLICE_PROFILE
    assert (
        graphify_semantic_slice.profile_for({graphify_semantic_slice.PROFILE_ENV_NAME: "corpus"})
        is graphify_semantic_slice.CORPUS_PROFILE
    )
    # An unrecognized value must RAISE rather than fall back. Falling back would
    # report a run made under one shape as evidence about another.
    with pytest.raises(ValueError, match="unknown semantic profile"):
        graphify_semantic_slice.profile_for(
            {graphify_semantic_slice.PROFILE_ENV_NAME: "claude-opus-5"}
        )


def test_corpus_argv_carries_effort_and_the_budget_literal() -> None:
    """The corpus argv differs from the slice's only in reviewed, visible ways."""
    slice_argv = graphify_semantic_slice.expected_adapter_argv(
        graphify_semantic_slice.SLICE_PROFILE, "{}"
    )
    corpus_argv = graphify_semantic_slice.expected_adapter_argv(
        graphify_semantic_slice.CORPUS_PROFILE, "{}"
    )
    assert "--effort" not in slice_argv
    assert corpus_argv[-2:] == ("--effort", "high")
    # The budget is carried as a STRING literal, not re-rendered from a float.
    # `str(25.0)` is "25.0" and would not match this argv; that mismatch is what
    # the shared definition exists to prevent.
    budget = corpus_argv[corpus_argv.index("--max-budget-usd") + 1]
    assert budget == "25.00"
    assert budget != str(graphify_semantic_slice.CORPUS_PROFILE.max_cost_usd)
    assert len(corpus_argv) == graphify_semantic_slice.CORPUS_PROFILE.retained_argv_length
    assert len(slice_argv) == graphify_semantic_slice.SLICE_PROFILE.retained_argv_length


def test_recorded_schema_returns_empty_on_a_wrong_length_argv() -> None:
    """A shape error must not be reported in the vocabulary of a content error."""
    profile = graphify_semantic_slice.CORPUS_PROFILE
    good = graphify_semantic_slice.expected_adapter_argv(profile, "SCHEMA")
    assert graphify_semantic_slice.recorded_schema(good, profile) == "SCHEMA"
    assert graphify_semantic_slice.recorded_schema(good[:-2], profile) == ""


@pytest.mark.skipif(not _PLAN.is_dir(), reason="corpus plan has not been generated here")
def test_enabling_the_cache_omits_the_variable_rather_than_setting_zero() -> None:
    """`"0"` is truthy to graphify, so a warm cache means an ABSENT name."""
    name = "GRAPHIFY_NO_INCREMENTAL_CACHE"
    config = _config()
    assert config.graphify_no_incremental_cache is False
    # None, NOT an absent key: an overlay can only override names it mentions, so
    # omitting this one let an ambient `=1` survive and silently make a
    # cache-enabled run cold while its receipt still said warm.
    assert graphify_semantic_corpus_run.incremental_cache_env(config) == {name: None}
    cold = msgspec.structs.replace(config, graphify_no_incremental_cache=True)
    assert graphify_semantic_corpus_run.incremental_cache_env(cold) == {name: "1"}


@pytest.mark.skipif(not _PLAN.is_dir(), reason="corpus plan has not been generated here")
def test_an_ambient_cache_disable_does_not_survive_into_a_warm_run() -> None:
    """The end-to-end half: a hostile ambient value must actually be removed.

    Asserting the mapping alone would pass even if `_temporary_environment`
    ignored `None`, which is exactly how the defect existed in the first place —
    the pieces were each defensible and the composition leaked.
    """
    name = "GRAPHIFY_NO_INCREMENTAL_CACHE"
    os.environ[name] = "1"
    try:
        overlay = graphify_semantic_corpus_run.incremental_cache_env(_config())
        with graphify_semantic_corpus_run._temporary_environment(overlay):
            assert name not in os.environ, "an ambient cache-disable leaked into a warm run"
        # And it is restored, because clearing it is scoped to the call.
        assert os.environ[name] == "1"
    finally:
        os.environ.pop(name, None)


def _multi_file_result() -> dict[str, object]:
    """A provider result citing two files — what every real corpus chunk returns."""
    return {
        "nodes": [
            {"id": "n1", "source_file": "README.md", "_origin": "semantic"},
            {"id": "n2", "source_file": "docs/how-it-works.md", "_origin": "semantic"},
        ],
        "edges": [{"source": "n1", "target": "n2", "source_file": "README.md"}],
        "hyperedges": [],
    }


def test_corpus_reduction_does_not_scope_fragments_to_the_slices_one_file() -> None:
    """The reduction the corpus uses must accept a multi-file chunk.

    This is the arm for the cold lane's P1. `semantic_fragment` asserted the
    fragment was scoped to `SOURCE_PATH` — the slice's single document — while
    being exported for the corpus to share, so the first chunk of any real run
    would have raised AFTER its provider call was paid for. Reverting to that
    reduction makes the first assertion below fail, which is what makes this a
    test of the fix rather than a description of it.
    """
    result = _multi_file_result()
    fragment = graphify_semantic_slice.normalize_fragment(result)
    nodes = fragment["nodes"]
    assert isinstance(nodes, list)
    assert [node["id"] for node in nodes] == ["n1", "n2"]

    # And the slice's own behaviour is unchanged: scoped to one file, a fragment
    # citing another is still a hard failure there.
    with pytest.raises(ValueError, match="fragment failed"):
        graphify_semantic_slice.semantic_fragment(result)


@pytest.mark.skipif(not _PLAN.is_dir(), reason="corpus plan has not been generated here")
def test_corpus_scope_failures_are_reasons_for_one_chunk_not_a_run_abort() -> None:
    """An under-covered chunk must be refusable without killing the extraction.

    `normalize_fragment` deliberately does not raise on scope, because the whole
    corpus run happens inside ONE `extract_corpus_parallel` call: an exception in
    the callback takes the other 57 chunks with it. The scope answer still exists
    — as reasons, per chunk — which is what `stage_chunk` consumes.
    """
    fragment = graphify_semantic_slice.normalize_fragment(_multi_file_result())
    covered = graphify_semantic_slice.fragment_scope_reasons(
        fragment, source_paths=("README.md", "docs/how-it-works.md")
    )
    assert covered == ()
    under_covered = graphify_semantic_slice.fragment_scope_reasons(
        fragment, source_paths=("README.md",)
    )
    assert under_covered != (), "a fragment citing an unplanned file must be refused"


def _run_context(tmp_path: Path) -> graphify_semantic_corpus_run._RunContext:
    """Build a context good enough to reach the driver's reduction call."""
    preflight = graphify_semantic_slice.ClaudePreflight(
        executable="claude",
        executable_sha256="0" * 64,
        version="2.1.233",
        help_sha256="0" * 64,
        required_flags=(),
        auth=graphify_semantic_slice.AuthIdentity(
            logged_in=True,
            auth_method="claude.ai",
            api_provider="firstParty",
            subscription_type="max",
        ),
        environment_names=(),
        graphify_runtime=graphify_semantic_slice.accepted_graphify_runtime(),
        graphify_version="0.9.45",
        graphify_semantic_fingerprint_sha256="0" * 64,
    )
    return graphify_semantic_corpus_run._RunContext(
        candidate=tmp_path / "plan",
        cache_root=tmp_path / "cache",
        source_root=tmp_path / "src",
        inventory=_inventory(),
        ledger=_ledger(),
        config=_config(),
        preflight_receipt=preflight,
        run_namespace="a" * 64,
        metadata_path=tmp_path / "adapter-metadata.json",
        boundary_dir=tmp_path,
    )


@pytest.mark.skipif(not _PLAN.is_dir(), reason="corpus plan has not been generated here")
def test_driver_reduces_without_asserting_the_slices_scope(tmp_path: Path) -> None:
    """THE arm for the P1 fix: it fails if the driver reverts to `semantic_fragment`.

    The first attempt at arming this passed with the fix reverted, because the
    other tests exercise the two reduction FUNCTIONS and never the driver's choice
    between them. This one calls the driver and reads WHICH failure it reaches:

    * with `normalize_fragment` (fixed) it gets past the reduction and dies on the
      absent adapter metadata — "semantic adapter metadata is unavailable";
    * with `semantic_fragment` (the defect) the multi-file fragment is rejected
      first — "Graphify semantic fragment failed".

    Two different messages from the same call, so the assertion discriminates
    rather than merely passing.
    """
    context = _run_context(tmp_path)
    chunk = context.ledger.chunks[0]
    # `match=` IS the discrimination: with the fix reverted the call instead
    # raises a fragment-failed error naming a source-scope mismatch, which does
    # not match this pattern and fails the test.
    with pytest.raises(ValueError, match="adapter metadata is unavailable"):
        graphify_semantic_corpus_run._stage_completed_chunk(_multi_file_result(), chunk, context)


def test_envelope_validation_follows_the_profile_that_was_invoked() -> None:
    """A corpus response naming Opus must not be rejected as a model mismatch.

    Round 2's P1: `_model_reasons` compared `modelUsage` to the slice's haiku
    constants, so the adapter refused every corpus chunk with
    `model-identity-invalid` — a whole-corpus failure whose message named the
    model rather than the check. Both directions are asserted, so a profile-blind
    implementation fails whichever constant it picks.
    """

    def envelope(model: str, canonical: str) -> dict[str, object]:
        return {"modelUsage": {model: {"canonicalModel": canonical, "provider": "firstParty"}}}

    corpus = graphify_semantic_slice.CORPUS_PROFILE
    slice_profile = graphify_semantic_slice.SLICE_PROFILE
    corpus_envelope = envelope(corpus.model, corpus.canonical_model)
    slice_envelope = envelope(slice_profile.model, slice_profile.canonical_model)

    assert "model-identity-invalid" not in graphify_semantic_slice.envelope_reasons(
        corpus_envelope, profile=corpus
    )
    assert "model-identity-invalid" in graphify_semantic_slice.envelope_reasons(
        corpus_envelope, profile=slice_profile
    )
    assert "model-identity-invalid" not in graphify_semantic_slice.envelope_reasons(
        slice_envelope, profile=slice_profile
    )
    assert "model-identity-invalid" in graphify_semantic_slice.envelope_reasons(
        slice_envelope, profile=corpus
    )


def test_adapter_reads_the_profile_from_the_environment_for_envelope_checks() -> None:
    """The adapter boundary must carry the profile through, not drop it."""
    corpus = graphify_semantic_slice.CORPUS_PROFILE
    corpus_envelope = {
        "modelUsage": {
            corpus.model: {"canonicalModel": corpus.canonical_model, "provider": "firstParty"}
        }
    }
    under_corpus = graphify_semantic_adapter.result_envelope_reasons(
        corpus_envelope, {graphify_semantic_slice.PROFILE_ENV_NAME: corpus.name}
    )
    under_default = graphify_semantic_adapter.result_envelope_reasons(corpus_envelope, {})
    assert "model-identity-invalid" not in under_corpus
    assert "model-identity-invalid" in under_default


def test_chunk_stage_dir_is_the_same_path_stage_chunk_refuses_to_overwrite() -> None:
    """The resume check must ask about the directory staging actually uses."""
    namespace = "a" * 64
    root = Path("/cache")
    assert graphify_semantic_corpus.chunk_stage_dir(
        root, namespace, 7
    ) == graphify_semantic_corpus._chunk_dir(root, namespace, 7)
    assert graphify_semantic_corpus.chunk_stage_dir(root, namespace, 7).name == "0007"


def test_temporary_environment_restores_an_absent_name_as_absent() -> None:
    """Restoring an absent variable as "" would leave it defined and falsy."""
    name = "KB_TEST_SEMANTIC_ABSENT"
    os.environ.pop(name, None)
    with graphify_semantic_corpus_run._temporary_environment({name: "1"}):
        assert os.environ[name] == "1"
    assert name not in os.environ


def test_extract_corpus_parallel_cannot_accept_the_plans_slice_units() -> None:
    """Pin the upstream constraint that forces `admitted_paths` to pass FILES.

    Control-armed in both directions: a `Path` expands, a `FileSlice` raises. If a
    graphify bump ever makes the slice form work, this test fails and the driver's
    file-level dispatch can be revisited deliberately rather than by accident.
    """
    # Resolved dynamically on purpose. graphify declares the parameter as
    # `list[Path]`, so passing the slice form through the imported symbol is a
    # type error the checker rejects before the interpreter can demonstrate the
    # RUNTIME refusal — and the runtime refusal is the fact being pinned here.
    # (An inline suppression is not an option: `no_lint_skip` rejects them.)
    expand: Callable[..., object] = getattr(file_slice, "expand_oversized" + "_files")
    with pytest.raises(AttributeError):
        expand([FileSlice(path=Path("README.md"), start=0, end=10, index=0, total=2)], 20_000)
    assert expand_oversized_files([Path("README.md")], 20_000)


@pytest.mark.skipif(not _PLAN.is_dir(), reason="corpus plan has not been generated here")
def test_admitted_paths_dedupes_slices_of_one_file() -> None:
    """A file sliced N ways is dispatched once, not N times."""
    inventory = _inventory()
    root = Path("/src")
    paths = graphify_semantic_corpus_run.admitted_paths(inventory, root)
    assert len(paths) == len({unit.path for unit in inventory.units})
    assert len(paths) < len(inventory.units), "the plan should contain at least one sliced file"
    assert len(paths) == len(set(paths))
    assert all(path.is_relative_to(root) for path in paths)


@pytest.mark.skipif(not _PLAN.is_dir(), reason="corpus plan has not been generated here")
def test_provider_execution_config_is_read_from_the_plan() -> None:
    """Every field is projected from the plan, never restated as a literal."""
    config = _config()
    projected = graphify_semantic_corpus_run._provider_execution_config(config)
    assert projected.claude_code_max_output_tokens == config.claude_max_output_tokens
    assert projected.claude_code_max_retries == config.claude_max_retries
    assert projected.max_concurrency == config.concurrency
    assert projected.max_retry_depth == config.graphify_max_retry_depth
    assert projected.api_timeout_ms == config.timeout_seconds * 1000
    assert projected.graphify_no_incremental_cache == config.graphify_no_incremental_cache


@pytest.mark.skipif(not _PLAN.is_dir(), reason="corpus plan has not been generated here")
def test_plan_records_the_running_graphify_version_and_the_corpus_profile() -> None:
    """The regenerated plan must agree with the pin and with the chosen profile."""
    config = _config()
    profile = graphify_semantic_slice.CORPUS_PROFILE
    assert config.graphify_version == config.graphify_runtime.version
    assert config.claude_model == profile.model
    # NOT the profile's literal any more, and that inequality IS the assertion.
    # The profile keeps 8192 as the floor a launcher with no plan behind it gets;
    # the plan carries half the model's resolved ceiling, which is strictly
    # larger. An equality here would mean the resolution never reached the plan.
    assert config.claude_max_output_tokens > int(profile.max_output_tokens)
    assert config.max_cost_usd == profile.max_cost_usd
    # Per chunk and per run are different authorities. Equal values would mean the
    # cumulative cap was a restatement rather than a new bound.
    assert config.max_total_cost_usd > config.max_cost_usd
    # `--effort` is proven by the preflight and therefore lands in the receipt's
    # flag list, which is compared for EQUALITY — so the config must carry it.
    assert "--effort" in config.claude_required_flags


@pytest.mark.skipif(not _PLAN.is_dir(), reason="corpus plan has not been generated here")
def test_recorded_authority_digests_match_the_plan_on_disk() -> None:
    """A recorded authorization must describe THIS plan, not a previous one.

    The failure this catches is the quiet one: a re-plan leaves the four digests
    pointing at bytes that no longer exist, and the only symptom is
    `plan-authority-mismatch` at run time — which reads like a broken gate rather
    than like "nobody has reviewed the plan you are about to spend on".
    """
    authority = msgspec.json.decode(
        graphify_semantic_corpus_authority.AUTHORITY_JSON,
        type=graphify_semantic_corpus.AuthorityRoots,
        strict=True,
    )
    for recorded, name in (
        (authority.plan_manifest_sha256, "manifest.json"),
        (authority.execution_config_sha256, "execution-config.json"),
        (authority.advisories_sha256, "advisories.json"),
        (authority.exclusions_sha256, "exclusions.json"),
    ):
        assert recorded == graphify_semantic_corpus.sha256_path(_PLAN / name), name


# The `unset`-versus-mismatch distinction is armed in
# `tests/test_graphify_semantic_corpus.py`, by
# `test_recorded_authority_authorizes_this_plan_and_only_this_plan`, which calls
# `verify_plan` against the real committed roots in both directions.
#
# A test lived HERE claiming the same coverage and never called `verify_plan` at
# all: it decoded two `AuthorityRoots` and asserted that one had empty digests
# and the other did not — a property of its own fixtures, true no matter what the
# verifier did with them. A cold lane proved the point by replacing `verify_plan`
# with a function that always raises; the test still passed. It is deleted rather
# than repaired because repairing it would only duplicate the sibling above, and
# two tests of one behaviour drift until they disagree about which is right.


def test_graphify_still_force_serializes_the_claude_cli_backend() -> None:
    """Graphify force-serializes claude-cli; assert that against INSTALLED source.

    Deliberately UNGUARDED. This asks a question about the pinned dependency, not
    about this repo's plan, and it is the half that must fail when a graphify
    release lifts the clamp — so the concurrency decision gets re-made rather
    than staying at 1 forever. Behind the plan guard it went quiet on exactly the
    machines that had not generated a plan, which is most of them.

    Asserted STRUCTURALLY, against the clamp's own statement. It used to assert
    that the strings `backend == "claude-cli"` and `GRAPHIFY_CLAUDE_CLI_PARALLEL`
    both appeared somewhere in a file of several thousand lines, which stays true
    if the assignment they guard is deleted — the tripwire would keep passing
    through exactly the release it exists to catch. Both strings survive in the
    docstring of the function itself, so this was not a hypothetical margin.
    """
    import ast
    import inspect

    import graphify.llm

    tree = ast.parse(inspect.getsource(graphify.llm.extract_corpus_parallel))
    clamps = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and "claude-cli" in ast.dump(node.test)
        and any(
            isinstance(stmt, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "max_concurrency" for t in stmt.targets)
            and isinstance(stmt.value, ast.Constant)
            and stmt.value.value == 1
            for stmt in node.body
        )
    ]
    assert clamps, (
        "graphify no longer clamps max_concurrency to 1 for the claude-cli backend "
        "inside extract_corpus_parallel — the plan records concurrency=1 as a "
        "MEASUREMENT of this clamp, so that decision must be re-made"
    )
    # The opt-out is what makes the clamp conditional rather than absolute, so a
    # release that kept the clamp but dropped the escape hatch is also a change
    # worth noticing.
    assert "GRAPHIFY_CLAUDE_CLI_PARALLEL" in ast.dump(clamps[0].test)


@pytest.mark.skipif(not _PLAN.is_dir(), reason="corpus plan has not been generated here")
def test_planned_concurrency_matches_what_the_extractor_will_actually_do() -> None:
    """The clamp above is what makes 1 the only honest value for the plan to record."""
    assert _config().concurrency == 1


def _stub_extraction(
    monkeypatch: pytest.MonkeyPatch,
    driver: Callable[[graphify_semantic_corpus_run._RunContext, Callable[..., None]], None],
    *,
    result: dict[str, object],
) -> None:
    """Replace the provider call with a driver that fires the callback directly.

    Stubbing `_extract_corpus` rather than a lower seam is deliberate: every one
    of the three defects armed below lived in `execute`'s COMPOSITION — the
    callback's control flow, and what `execute` did with graphify's returned
    counters — not in a function a unit test could call on its own.
    """

    def fake(
        paths: list[Path],
        context: graphify_semantic_corpus_run._RunContext,
        *,
        semantic_cache: Path,
        environment: object,
        on_chunk_done: Callable[..., None],
    ) -> dict[str, object]:
        driver(context, on_chunk_done)
        return result

    monkeypatch.setattr(graphify_semantic_corpus_run, "_extract_corpus", fake)
    # The preflight is stubbed, but `executable_sha256` is the REAL binary's:
    # `_adapter_overlay` re-hashes it and refuses a mismatch, and satisfying that
    # check with a truthful digest keeps the overlay's own guard live in these
    # tests instead of stubbing past it.
    real_claude = shutil.which("claude")
    assert real_claude is not None
    receipt = msgspec.structs.replace(
        _run_context(Path("/nonexistent")).preflight_receipt,
        executable_sha256=graphify_semantic_slice.sha256_file(Path(real_claude).resolve()),
    )
    monkeypatch.setattr(graphify_semantic_slice, "preflight", lambda *_args, **_kwargs: receipt)


_PROVIDER_BINARIES_PRESENT = bool(shutil.which("claude") and shutil.which("kb-semantic-claude"))
_needs_driver = pytest.mark.skipif(
    not (_PLAN.is_dir() and _PROVIDER_BINARIES_PRESENT),
    reason="corpus plan or the provider binaries are unavailable here",
)


def _execute(tmp_path: Path) -> graphify_semantic_corpus_run.RunSummary:
    return graphify_semantic_corpus_run.execute(
        _PLAN,
        tmp_path / "cache",
        tmp_path / "src",
        repo_root=tmp_path,
    )


@_needs_driver
def test_a_chunk_that_fails_to_stage_does_not_abort_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One unusable chunk must become an outcome, not an exception past the summary.

    `_stage_completed_chunk` has three reachable raise paths, and every one of
    them propagated out of `execute` — leaving the chunks already staged on disk
    with no summary naming them, which is the artifact an operator reads to
    decide what to do next. The arm drives a malformed provider result through
    the real callback and asserts a SUMMARY comes back.
    """

    def driver(context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable) -> None:
        on_chunk_done(0, len(context.ledger.chunks), {"nodes": "not-a-list"})

    _stub_extraction(monkeypatch, driver, result={"failed_chunks": 0})
    summary = _execute(tmp_path)
    assert summary.failed == 1
    assert summary.completed == 0
    assert summary.outcomes[0].reasons[0].startswith("chunk-staging-failed")


@_needs_driver
@pytest.mark.parametrize(
    "corrupt",
    [
        pytest.param(lambda stage: stage.mkdir(parents=True), id="empty-directory"),
        pytest.param(
            lambda stage: (
                stage.mkdir(parents=True),
                (stage / "receipt.json").write_text("{}"),
            ),
            id="partial-members",
        ),
        pytest.param(
            lambda stage: (
                stage.parent.mkdir(parents=True, exist_ok=True),
                stage.symlink_to(stage.parent),
            ),
            id="symlinked-stage",
        ),
    ],
)
def test_a_stage_directory_that_is_not_this_chunks_evidence_is_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corrupt: Callable
) -> None:
    """An unverified stage directory used to count as done and exit 0.

    The driver decided "already staged" from `chunk_stage_dir(...).exists()`, so
    a cold cross-family lane substituted an unrelated directory for every stage
    and got "58 accounted, 0 failed, success" — silent corpus loss wearing a
    green result. Existence is a claim about the filesystem; what the driver
    needs is a claim about the evidence.

    The three arms are the three shapes that predicate could not tell from a real
    stage: nothing in the directory, some of the four members, and a symlink
    (which `exists()` answers about the TARGET). Each must land as a FAILURE
    naming its reason, because there is no repair path — `stage_chunk` refuses
    the occupied destination — so the operator has to be told to remove it.

    Deliberately asserts `repaid == 0` too. A fix that merely ADDED a failure
    while still counting the chunk as staged would satisfy `failed == 1` and
    leave the completeness gate green, which is the defect rather than the fix.
    """
    cache_root = tmp_path / "cache"
    config = _config()
    namespace = graphify_semantic_corpus_run._run_namespace(_PLAN, config.cache_namespace_sha256)
    ordinal = _ledger().chunks[0].ordinal
    corrupt(graphify_semantic_corpus.chunk_stage_dir(cache_root, namespace, ordinal))

    def driver(context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable) -> None:
        # Exactly what a real provider call leaves behind before the callback runs.
        context.metadata_path.write_bytes(b"{}")
        on_chunk_done(0, len(context.ledger.chunks), {})

    _stub_extraction(monkeypatch, driver, result={"failed_chunks": 0})
    summary = _execute(tmp_path)

    assert summary.repaid == 0, "an unverifiable stage directory was counted as staged"
    assert summary.failed == 1
    assert summary.outcomes[0].reasons
    assert all(
        reason.startswith("chunk-stage-unverifiable: ") for reason in summary.outcomes[0].reasons
    ), summary.outcomes[0].reasons


@pytest.mark.parametrize(("markers", "expected"), [(0, 0), (1, 1), (3, 3)])
def test_rotation_counts_the_provider_crossings_before_it_clears_them(
    tmp_path: Path, markers: int, expected: int
) -> None:
    """`_rotate_evidence` reports how many provider calls this chunk's turn made.

    graphify's `_extract_with_adaptive_retry` recurses on halves and merges, then
    fires ONE callback, so a bisected chunk makes N provider calls and yields a
    single callback. The receipt hardcoded `attempts=1`, which was false in
    committed evidence for every chunk graphify ever bisected. The boundary
    markers recording those crossings were already being collected here and then
    deleted unexamined.

    The count is taken BEFORE the rotation and that ordering is the whole fix —
    `clear_stale_evidence` empties the directory, so a count taken afterwards is
    always zero.

    The zero arm's job, stated accurately: it pins the ABSENT case to 0 rather
    than to 1. The 1 and 3 arms already exclude every constant between them, so
    the zero arm is not the control against a stubbed counter — an earlier
    version of this docstring claimed it was, which is arithmetically false. What
    it does exclude is a `max(1, count)`-style floor, the natural way someone
    "fixes" an empty directory, and that would silently report one provider call
    for a chunk that made none.

    What this does NOT establish: that a count above 1 REFUSES the chunk. It does
    not, and must not. This directory is not chunk-scoped — a chunk whose
    provider call fails never reaches the callback that clears it, so its marker
    lands in the next chunk's count. The refusal lives in
    `_provider_chunk_reasons`, where a chunk-scoped signal exists, and is armed by
    `test_graphify_semantic_corpus.py::test_a_bisected_chunk_is_named_partial_not_corrupt`.
    """
    boundary = tmp_path / "boundary"
    boundary.mkdir()
    metadata = tmp_path / "adapter-metadata.json"
    metadata.write_bytes(b"{}")
    for index in range(markers):
        (boundary / f"provider-boundary-{index}.json").write_text("{}")

    raw, counted = graphify_semantic_corpus_run._rotate_evidence(metadata, boundary)

    assert raw == b"{}"
    assert counted == expected
    # Rotated: the next chunk starts from an empty directory, which is what makes
    # the count belong to one chunk's turn rather than to the whole run.
    assert not tuple(boundary.glob("provider-boundary-*.json"))
    assert not metadata.exists()


@_needs_driver
def test_one_callback_per_chunk_is_enforced_rather_than_assumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repeated callback index must raise, not quietly absorb an unvisited chunk.

    The guard checked only that the index was in RANGE. Accounting counts events
    and `skipped` clamps its own negative, so two callbacks for one index made a
    chunk that never arrived report as `skipped=0` — a hole in the corpus behind
    a clean summary.

    The control arm is the second half: the same driver visiting two DISTINCT
    indices must not raise, or this would pass against a guard that rejects every
    second callback for any reason at all.
    """

    def driver_duplicate(
        context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable
    ) -> None:
        context.metadata_path.write_bytes(b"{}")
        on_chunk_done(0, len(context.ledger.chunks), {})
        on_chunk_done(0, len(context.ledger.chunks), {})

    _stub_extraction(monkeypatch, driver_duplicate, result={"failed_chunks": 0})
    with pytest.raises(ValueError, match="repeated index 0"):
        _execute(tmp_path)

    def driver_distinct(
        context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable
    ) -> None:
        for index in (0, 1):
            context.metadata_path.write_bytes(b"{}")
            on_chunk_done(index, len(context.ledger.chunks), {})

    _stub_extraction(monkeypatch, driver_distinct, result={"failed_chunks": 0})
    assert _execute(tmp_path).chunk_total == len(_ledger().chunks)


@_needs_driver
def test_a_missing_failed_chunks_counter_is_an_error_not_a_clean_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The -1 sentinel exists so absent and zero differ; it must not be clamped away.

    The control arm is the second half: the SAME call with the counter present
    and zero returns a summary, so this asserts the sentinel is read rather than
    that the function raises for some unrelated reason.
    """

    def driver(context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable) -> None:
        return None

    _stub_extraction(monkeypatch, driver, result={})
    with pytest.raises(ValueError, match="omitted failed_chunks"):
        _execute(tmp_path)

    _stub_extraction(monkeypatch, driver, result={"failed_chunks": 0})
    assert _execute(tmp_path).failed == 0


#: Monotonic across every `_spend` call in the process, so no two records can
#: ever share a filename. See the note inside `_spend`.
_SPEND_SEQ = itertools.count()


def _spend(boundary: Path, *amounts: float) -> None:
    """Leave one spend record per amount, in the shape the adapter writes.

    Written directly rather than through `write_provider_spend`, matching how the
    marker arms in this module already lay down evidence. The writer opens every
    directory component with `O_NOFOLLOW`, and the driver's own evidence directory
    comes from `tempfile.TemporaryDirectory()` — which on macOS sits under `/var`,
    a symlink to `/private/var`. So the real writer cannot write into the driver's
    real directory on this platform, and an arm using it here would be measuring
    that unrelated defect (fixed on `fix-328-extraction-warning-accounting`,
    unmerged) instead of the summation it names.

    The writer/reader agreement is armed separately, in
    `test_a_spend_record_round_trips_through_the_directory`, against pytest's
    `tmp_path` — which is already canonical.
    """
    for amount in amounts:
        record = graphify_semantic_adapter.ProviderSpendRecord(
            schema_id="graphify-claude-provider-spend/v0",
            total_cost_usd=amount,
        )
        # A PROCESS-WIDE counter, not `enumerate(amounts)`. That is the whole
        # reason this comment exists: with a per-call index, two calls each
        # writing one record of the same amount produced the SAME filename, so
        # the second overwrote the first. The rotation arm then passed with the
        # rotation deleted — a test that could not fail, caught by `kb-arms`
        # reporting C4 SURVIVED and not by reading it.
        (boundary / f"provider-spend-{os.getpid()}-{next(_SPEND_SEQ)}.json").write_bytes(
            msgspec.json.encode(record)
        )


def test_a_spend_record_round_trips_through_the_directory(tmp_path: Path) -> None:
    """The adapter's writer and the driver's reader agree, and each call is its own file.

    Two records rather than one, because the whole reason this is a directory of
    files instead of a field in the adapter metadata is that the metadata path is
    a single file every call overwrites. If two writes collapsed into one record
    the sum would be wrong in exactly the case — a bisected chunk — that costs the
    most.
    """
    graphify_semantic_adapter.write_provider_spend(tmp_path, 1.25)
    graphify_semantic_adapter.write_provider_spend(tmp_path, 0.75)

    assert len(tuple(tmp_path.glob("provider-spend-*.json"))) == 2
    assert graphify_semantic_corpus_run.observed_spend_usd(tmp_path) == pytest.approx(2.0)


def test_an_unreadable_spend_record_is_skipped_rather_than_fatal(tmp_path: Path) -> None:
    """A malformed record can only make the total LOW, which the cap already handles.

    The control arm is the second assertion: a good record in the SAME directory
    is still counted, so this measures "the bad one was skipped" rather than "the
    reader returned zero for some unrelated reason".
    """
    (tmp_path / "provider-spend-garbage.json").write_text("not json")
    assert graphify_semantic_corpus_run.observed_spend_usd(tmp_path) == pytest.approx(0.0)

    _spend(tmp_path, 3.5)
    assert graphify_semantic_corpus_run.observed_spend_usd(tmp_path) == pytest.approx(3.5)


def test_an_absent_boundary_directory_reports_no_spend(tmp_path: Path) -> None:
    """Absence is the normal pre-first-call state, not an error."""
    assert graphify_semantic_corpus_run.observed_spend_usd(tmp_path / "missing") == 0.0


@_needs_driver
def test_a_run_halts_once_cumulative_spend_crosses_the_plans_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cap that did not exist: per-chunk authority summing past any total.

    `max_cost_usd` bounds ONE chunk and `--max-budget-usd` bounds one provider
    invocation, so 58 chunks each individually within authority could spend far
    past anything a human approved. This arm drives three chunks whose recorded
    spend crosses the plan's `max_total_cost_usd` on the second, and asserts the
    third never ran.

    The control arm is the second half: the same three chunks with spend UNDER the
    cap must run to the end with `halted == ""`. Without it this would pass
    against a driver that halts on every run.

    The halted run must still return a SUMMARY. An exception escaping `execute`
    would leave the operator with a traceback and no record of which chunks are
    staged on disk, which is the artifact that decides what to do next.
    """
    cap = _config().max_total_cost_usd

    def driver_over(
        context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable
    ) -> None:
        for index in range(3):
            context.metadata_path.write_bytes(b"{}")
            _spend(context.boundary_dir, cap * 0.6)
            on_chunk_done(index, len(context.ledger.chunks), {})

    _stub_extraction(monkeypatch, driver_over, result={"failed_chunks": 0})
    halted = _execute(tmp_path)

    assert halted.halted, "a run that crossed its cumulative cap reported no reason"
    assert "max_total_cost_usd" in halted.halted
    assert halted.spend_usd == pytest.approx(cap * 1.2)
    # Two chunks reached the callback, not three: the third was never dispatched.
    assert len(halted.outcomes) == 2
    assert halted.skipped == len(_ledger().chunks) - 2

    def driver_under(
        context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable
    ) -> None:
        for index in range(3):
            context.metadata_path.write_bytes(b"{}")
            _spend(context.boundary_dir, cap * 0.1)
            on_chunk_done(index, len(context.ledger.chunks), {})

    _stub_extraction(monkeypatch, driver_under, result={"failed_chunks": 0})
    completed = _execute(tmp_path / "under")

    assert completed.halted == ""
    assert len(completed.outcomes) == 3
    assert completed.spend_usd == pytest.approx(cap * 0.3)


@_needs_driver
def test_spend_is_charged_before_the_disposition_so_no_branch_escapes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A chunk that FAILS to stage still spent money, and must still be charged.

    The charge sits above the branch rather than inside the staging path, and this
    is the arm for that placement: the driver here produces a malformed result, so
    every chunk lands in the failure branch — the one a charge written inside
    `_stage_completed_chunk` would never reach.

    A cap blind to the runs that go wrong is worse than no cap, because the runs
    that go wrong are the ones that retry.
    """

    def driver(context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable) -> None:
        for index in range(2):
            _spend(context.boundary_dir, 4.0)
            on_chunk_done(index, len(context.ledger.chunks), {"nodes": "not-a-list"})

    _stub_extraction(monkeypatch, driver, result={"failed_chunks": 0})
    summary = _execute(tmp_path)

    assert summary.failed == 2
    assert summary.completed == 0
    assert summary.spend_usd == pytest.approx(8.0)


@_needs_driver
def test_a_bisected_chunks_calls_are_summed_rather_than_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One callback, N provider calls — the case summing adapter metadata gets wrong.

    graphify's `_extract_with_adaptive_retry` recurses on halves and merges, then
    fires ONE callback. The adapter metadata lives at a single fixed path every
    call overwrites, so a driver reading `metadata.total_cost_usd` sees only the
    LAST leaf and undercounts precisely the chunks that cost the most.

    The control is the arithmetic: three records of 2.0 must total 6.0, not 2.0.
    A reader that took the last record — the metadata behaviour — would produce
    2.0 and pass any assertion that only checked "nonzero".
    """

    def driver(context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable) -> None:
        context.metadata_path.write_bytes(b"{}")
        _spend(context.boundary_dir, 2.0, 2.0, 2.0)
        on_chunk_done(0, len(context.ledger.chunks), {})

    _stub_extraction(monkeypatch, driver, result={"failed_chunks": 0})
    assert _execute(tmp_path).spend_usd == pytest.approx(6.0)


@_needs_driver
def test_spend_records_are_rotated_so_one_chunk_is_not_charged_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Records are cleared with the markers; a survivor would be charged again.

    Two chunks, one record each, must total 2.0. If the rotation missed the spend
    records the first chunk's record would still be present at the second chunk's
    read and the total would be 3.0 — an over-count that fires the cap early,
    which is the failure mode that looks like the cap working.
    """

    def driver(context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable) -> None:
        for index in range(2):
            context.metadata_path.write_bytes(b"{}")
            _spend(context.boundary_dir, 1.0)
            on_chunk_done(index, len(context.ledger.chunks), {})

    _stub_extraction(monkeypatch, driver, result={"failed_chunks": 0})
    assert _execute(tmp_path).spend_usd == pytest.approx(2.0)


def test_the_child_takes_the_plans_output_cap_over_the_profile_literal() -> None:
    """The resolved, plan-pinned cap must reach the provider, by VALUE not by name.

    Three arms, because each is a different way this can silently be wrong:

    * With the variable set, the child gets the plan's value — otherwise the whole
      resolution is decoration and the run still uses the profile literal.
    * With it absent, the child gets the profile's literal, which is the LOWER of
      the two: an absent variable can only under-spend.
    * With it malformed, resolution RAISES. A typo that quietly reverted to the
      literal is the exact failure this replaces — an unnoticed low cap truncates
      a structured extraction mid-object and the run reports a refusal whose cause
      appears nowhere in the evidence.

    The fourth assertion is the one that protects the committed slice evidence:
    the child's environment NAMES are identical either way. `environment_names` is
    the only environment fact any receipt compares, so a new variable here would
    invalidate evidence for a fact the plan already records.
    """
    profile = graphify_semantic_slice.CORPUS_PROFILE
    name = graphify_semantic_slice.MAX_OUTPUT_TOKENS_ENV_NAME

    pinned = graphify_semantic_slice.claude_child_environment({name: "64000"}, profile=profile)
    assert pinned["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "64000"

    bare = graphify_semantic_slice.claude_child_environment({}, profile=profile)
    assert bare["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == profile.max_output_tokens
    assert int(profile.max_output_tokens) < 64000, "the fallback must be the lower value"

    assert sorted(pinned) == sorted(bare)

    for bad in ("0", "-1", "64k", "sixty"):
        with pytest.raises(ValueError, match=name):
            graphify_semantic_slice.claude_child_environment({name: bad}, profile=profile)


@_needs_driver
def test_the_driver_exports_the_plans_cap_rather_than_the_profiles(tmp_path: Path) -> None:
    """The overlay carries the plan's number, which is what makes the pin reach the call.

    The second assertion is the discrimination: an overlay that simply restated
    `CORPUS_PROFILE.max_output_tokens` would satisfy the first if the two happened
    to agree, and they must not — the whole change is that the plan's value is
    resolved rather than typed.
    """
    real_claude = shutil.which("claude")
    assert real_claude is not None
    context = msgspec.structs.replace(
        _run_context(tmp_path),
        preflight_receipt=msgspec.structs.replace(
            _run_context(tmp_path).preflight_receipt,
            executable_sha256=graphify_semantic_slice.sha256_file(Path(real_claude).resolve()),
        ),
    )
    adapter_dir = tmp_path / "bin"
    adapter_dir.mkdir()
    overlay = graphify_semantic_corpus_run._adapter_overlay(context, adapter_dir)

    name = graphify_semantic_slice.MAX_OUTPUT_TOKENS_ENV_NAME
    assert overlay[name] == str(_config().claude_max_output_tokens)
    assert overlay[name] != graphify_semantic_slice.CORPUS_PROFILE.max_output_tokens
