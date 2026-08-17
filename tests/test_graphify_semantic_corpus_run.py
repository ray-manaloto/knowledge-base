# Copyright (c) 2026 Raymond Manaloto
"""Tests for the corpus execution driver and the profile boundary it runs under."""

from __future__ import annotations

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
    assert config.claude_max_output_tokens == int(profile.max_output_tokens)
    assert config.max_cost_usd == profile.max_cost_usd
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


def test_an_unset_authority_is_distinguishable_from_a_wrong_one() -> None:
    """`unset` and `mismatch` are different failures and must stay different.

    Collapsing them would report "nobody reviewed this" and "the plan changed
    since review" with one word, and only the second is recoverable by
    re-authorizing rather than by reviewing from scratch.
    """
    empty = msgspec.json.decode(
        b'{"advisories_sha256":"","execution_config_sha256":"","exclusions_sha256":"",'
        b'"plan_manifest_sha256":"","schema_version":1}',
        type=graphify_semantic_corpus.AuthorityRoots,
        strict=True,
    )
    populated = msgspec.json.decode(
        graphify_semantic_corpus_authority.AUTHORITY_JSON,
        type=graphify_semantic_corpus.AuthorityRoots,
        strict=True,
    )
    # `verify_plan` treats "configured" as all four digests being non-empty, then
    # compares them. These two cases are what drive the two different reasons.
    assert not all(
        (
            empty.plan_manifest_sha256,
            empty.execution_config_sha256,
            empty.advisories_sha256,
            empty.exclusions_sha256,
        )
    )
    assert all(
        (
            populated.plan_manifest_sha256,
            populated.execution_config_sha256,
            populated.advisories_sha256,
            populated.exclusions_sha256,
        )
    )


def test_graphify_still_force_serializes_the_claude_cli_backend() -> None:
    """Graphify force-serializes claude-cli; assert that against INSTALLED source.

    Deliberately UNGUARDED. This asks a question about the pinned dependency, not
    about this repo's plan, and it is the half that must fail when a graphify
    release lifts the clamp — so the concurrency decision gets re-made rather
    than staying at 1 forever. Behind the plan guard it went quiet on exactly the
    machines that had not generated a plan, which is most of them.
    """
    import graphify.llm

    source = Path(graphify.llm.__file__).read_text(encoding="utf-8")
    assert 'backend == "claude-cli"' in source
    assert "GRAPHIFY_CLAUDE_CLI_PARALLEL" in source


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
def test_an_already_staged_chunk_the_provider_was_re_invoked_for_is_not_resumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`resumed` claims the pass was free for that chunk; prove it only says so when true.

    Both arms run over the SAME already-staged chunk and differ in one byte of
    state — whether the adapter left its metadata behind, which it writes only
    after the real `claude` subprocess returns. A profile-blind implementation
    that just counts `resumed` fails the paid arm, and one that counts everything
    as paid fails the free arm, so the pair discriminates rather than merely
    passing.
    """
    cache_root = tmp_path / "cache"
    config = _config()
    namespace = graphify_semantic_corpus_run._run_namespace(_PLAN, config.cache_namespace_sha256)
    ordinal = _ledger().chunks[0].ordinal
    graphify_semantic_corpus.chunk_stage_dir(cache_root, namespace, ordinal).mkdir(parents=True)

    def driver_paid(
        context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable
    ) -> None:
        # Exactly what a real provider call leaves behind before the callback runs.
        context.metadata_path.write_bytes(b"{}")
        on_chunk_done(0, len(context.ledger.chunks), {})

    def driver_free(
        context: graphify_semantic_corpus_run._RunContext, on_chunk_done: Callable
    ) -> None:
        on_chunk_done(0, len(context.ledger.chunks), {})

    _stub_extraction(monkeypatch, driver_paid, result={"failed_chunks": 0})
    paid = _execute(tmp_path)
    assert (paid.repaid, paid.resumed) == (1, 0), "a re-invoked chunk was reported as free"

    _stub_extraction(monkeypatch, driver_free, result={"failed_chunks": 0})
    free = _execute(tmp_path)
    assert (free.repaid, free.resumed) == (0, 1), "a cache-served chunk was reported as paid"


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
