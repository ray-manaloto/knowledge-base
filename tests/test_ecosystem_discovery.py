# Copyright (c) 2026 Raymond Manaloto
"""Pure discovery-policy tests: no GitHub client, filesystem, or graph writes."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import TypedDict, Unpack

import pytest
from kb_setup import ecosystem_discovery as discovery


class _RepoChanges(TypedDict, total=False):
    head_sha: str
    license_spdx: str | None
    is_fork: bool
    archived: bool
    default_branch: str
    evidence: tuple[discovery.Evidence, ...]
    declared_packages: tuple[str, ...]
    fork_parent: str
    template_parent: str
    vendor_origin: str
    dependency_version: str
    graphify_version: str


def _repo(repository: str, **changes: Unpack[_RepoChanges]) -> discovery.RepositorySnapshot:
    baseline = discovery.RepositorySnapshot(
        repository=repository,
        head_sha="a" * 40,
        license_spdx="Apache-2.0",
        is_fork=False,
        archived=False,
        default_branch="main",
    )
    return replace(baseline, **changes)


def test_search_plan_covers_consumers_and_alternatives_with_hard_bounds() -> None:
    plan = discovery.build_search_plan(alternatives=("cognee", "code-graph-rag"))

    assert {request.kind for request in plan.requests} == {
        discovery.SearchKind.CODE,
        discovery.SearchKind.COMMIT,
    }
    assert {request.target for request in plan.requests} == {
        discovery.SearchTarget.GRAPHIFY_CONSUMER,
        discovery.SearchTarget.ALTERNATIVE,
    }
    assert all(request.per_page <= 100 for request in plan.requests)
    assert all(request.max_pages <= 10 for request in plan.requests)
    assert plan.max_total_results == sum(request.max_results for request in plan.requests)


def test_default_search_plan_still_has_open_ended_alternative_discovery() -> None:
    plan = discovery.build_search_plan()

    assert any(request.target is discovery.SearchTarget.ALTERNATIVE for request in plan.requests)


def test_plan_cli_emits_bounded_machine_readable_work(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert discovery.plan_main(["cognee"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["max_total_results"] > 0
    assert any(request["query"] == '"cognee"' for request in payload["requests"])
    assert all(request["max_pages"] <= 10 for request in payload["requests"])


def test_invalid_alternative_term_is_rejected_instead_of_changing_the_query() -> None:
    for term in ("", 'tool" repo:private', "tool\nsecond-query"):
        with pytest.raises(ValueError, match="alternative"):
            discovery.build_search_plan(alternatives=(term,))


def test_repository_spellings_have_one_canonical_identity() -> None:
    spellings = (
        "Graphify-Labs/Graphify",
        "https://github.com/Graphify-Labs/Graphify.git",
        "git@github.com:Graphify-Labs/Graphify.git",
    )

    assert {discovery.canonical_repo_id(value) for value in spellings} == {"graphify-labs/graphify"}


def test_duplicate_search_hits_merge_exact_evidence_without_losing_paths() -> None:
    first = _repo(
        "Acme/Consumer",
        evidence=(
            discovery.Evidence(
                "pyproject.toml",
                discovery.EvidenceKind.DECLARATION,
                "graphifyy==0.9.41",
                "a" * 40,
            ),
        ),
    )
    second = _repo(
        "https://github.com/acme/consumer.git",
        evidence=(
            discovery.Evidence(
                "mise.toml",
                discovery.EvidenceKind.CLI_CALL,
                "graphify query architecture",
                "b" * 40,
            ),
        ),
    )

    groups = discovery.dedupe_candidates((first, second))

    assert len(groups) == 1
    assert {item.path for item in groups[0].representative.evidence} == {
        "mise.toml",
        "pyproject.toml",
    }


def test_same_copied_commit_under_unrelated_repositories_is_not_deduped() -> None:
    """A Git SHA is repository-local evidence, not a globally unique project id."""
    repositories = (
        _repo("acme/first", head_sha="f" * 40),
        _repo("other/copied-vendor", head_sha="f" * 40),
    )

    groups = discovery.dedupe_candidates(repositories)

    assert tuple(group.canonical_repo_id for group in groups) == (
        "acme/first",
        "other/copied-vendor",
    )


def test_explicit_fork_template_and_vendor_lineage_dedupes_to_the_source() -> None:
    repositories = (
        _repo("acme/upstream"),
        _repo("forker/copy", is_fork=True, fork_parent="acme/upstream"),
        _repo("templated/copy", template_parent="acme/upstream"),
        _repo("vendored/copy", vendor_origin="acme/upstream"),
    )

    assert discovery.dedupe_candidates(repositories) == (
        discovery.CandidateGroup(
            canonical_repo_id="acme/upstream",
            representative=repositories[0],
            members=("acme/upstream", "forker/copy", "templated/copy", "vendored/copy"),
        ),
    )


def test_usage_classification_is_limited_to_four_evidence_levels() -> None:
    evidence = (
        discovery.Evidence(
            "pyproject.toml",
            discovery.EvidenceKind.DECLARATION,
            "graphifyy==0.9.41",
            "1" * 40,
        ),
        discovery.Evidence(
            "scripts/index.py",
            discovery.EvidenceKind.SDK_CALL,
            "graphify.extract(project_root)",
            "2" * 40,
        ),
    )

    assert discovery.classify_usage(evidence) is discovery.UsageClass.SDK_BASIC
    assert set(discovery.UsageClass) == {
        discovery.UsageClass.DECLARED_ONLY,
        discovery.UsageClass.DOCS_ONLY,
        discovery.UsageClass.CLI_BASIC,
        discovery.UsageClass.SDK_BASIC,
    }


def test_requirements_txt_is_a_declaration_not_generic_documentation() -> None:
    evidence = (
        discovery.Evidence(
            "requirements.txt",
            discovery.EvidenceKind.DECLARATION,
            "graphifyy==0.9.41",
            "8" * 40,
        ),
    )

    assert discovery.classify_usage(evidence) is discovery.UsageClass.DECLARED_ONLY


def test_readme_deep_wording_is_docs_only_not_graphify_deep_usage() -> None:
    evidence = (
        discovery.Evidence(
            "README.md",
            discovery.EvidenceKind.DOCUMENTATION,
            "Our pipeline performs deep semantic extraction and reflection.",
            "3" * 40,
        ),
    )

    assert discovery.classify_usage(evidence) is discovery.UsageClass.DOCS_ONLY


def test_a_command_printed_in_docs_is_not_an_executed_cli_call() -> None:
    evidence = (
        discovery.Evidence(
            "docs/how-to.md",
            discovery.EvidenceKind.CLI_CALL,
            "graphify extract --deep",
            "4" * 40,
        ),
    )

    assert discovery.classify_usage(evidence) is discovery.UsageClass.DOCS_ONLY


def test_exact_executable_call_site_is_only_cli_basic() -> None:
    evidence = (
        discovery.Evidence(
            ".github/workflows/graph.yml",
            discovery.EvidenceKind.CLI_CALL,
            "graphify extract --deep && graphify artifacts",
            "5" * 40,
        ),
    )

    assert discovery.classify_usage(evidence) is discovery.UsageClass.CLI_BASIC


def test_moved_head_with_unchanged_evidence_path_does_not_force_refresh() -> None:
    repo = _repo(
        "acme/consumer",
        head_sha="b" * 40,
        dependency_version="graphifyy==0.9.41",
        graphify_version="0.9.41",
        evidence=(
            discovery.Evidence(
                "scripts/graph.py",
                discovery.EvidenceKind.CLI_CALL,
                "graphify query architecture",
                "1" * 40,
            ),
        ),
    )
    reviewed = discovery.ReviewedSnapshot(
        reviewed_sha="a" * 40,
        evidence_path_commits=(discovery.PathCommit("scripts/graph.py", "1" * 40),),
        dependency_version="graphifyy==0.9.41",
        graphify_version="0.9.41",
    )

    assert discovery.refresh_triggers(repo, reviewed) == ()
    checked = discovery.check_candidate(repo, checked_at_ns=123456789, reviewed=reviewed)
    assert checked.reviewed_sha_moved
    assert checked.status is discovery.CandidateStatus.CANDIDATE


def test_refresh_tracks_evidence_dependency_and_version_drift_separately() -> None:
    repo = _repo(
        "acme/consumer",
        head_sha="b" * 40,
        dependency_version="graphifyy>=0.9.42",
        graphify_version="0.9.42",
        evidence=(
            discovery.Evidence(
                "scripts/graph.py",
                discovery.EvidenceKind.SDK_CALL,
                "graphify.extract(root)",
                "2" * 40,
            ),
        ),
    )
    reviewed = discovery.ReviewedSnapshot(
        reviewed_sha="a" * 40,
        evidence_path_commits=(discovery.PathCommit("scripts/graph.py", "1" * 40),),
        dependency_version="graphifyy==0.9.41",
        graphify_version="0.9.41",
    )

    assert discovery.refresh_triggers(repo, reviewed) == (
        discovery.RefreshTrigger.EVIDENCE_PATH_CHANGED,
        discovery.RefreshTrigger.DEPENDENCY_DRIFT,
        discovery.RefreshTrigger.VERSION_DRIFT,
    )


def test_rootly_style_self_package_is_not_a_graphify_consumer() -> None:
    repo = _repo(
        "rootly/graphify-fork",
        declared_packages=("graphify",),
        evidence=(
            discovery.Evidence(
                "tests/test_api.py",
                discovery.EvidenceKind.SDK_CALL,
                "graphify.extract(fixture)",
                "6" * 40,
            ),
        ),
    )

    checked = discovery.check_candidate(repo, checked_at_ns=987654321)

    assert checked.status is discovery.CandidateStatus.EXCLUDED_SELF_PACKAGE
    assert checked.usage is None


def test_exact_package_definition_also_excludes_own_package_imports() -> None:
    repo = _repo(
        "rootly/graphify",
        evidence=(
            discovery.Evidence(
                "pyproject.toml",
                discovery.EvidenceKind.PACKAGE_DEFINITION,
                'name = "graphify"',
                "6" * 40,
            ),
            discovery.Evidence(
                "tests/test_api.py",
                discovery.EvidenceKind.SDK_CALL,
                "graphify.extract(fixture)",
                "6" * 40,
            ),
        ),
    )

    checked = discovery.check_candidate(repo, checked_at_ns=987654322)

    assert checked.status is discovery.CandidateStatus.EXCLUDED_SELF_PACKAGE
    assert checked.usage is None


def test_truncated_prefix_is_incomplete_and_retains_exact_metadata() -> None:
    evidence = discovery.Evidence(
        "mise.toml",
        discovery.EvidenceKind.CLI_CALL,
        "graphify query codebase",
        "7" * 40,
    )
    repo = _repo(
        "Acme/Consumer",
        head_sha="c" * 40,
        license_spdx="MIT",
        is_fork=True,
        fork_parent="origin/consumer",
        archived=True,
        default_branch="trunk",
        evidence=(evidence,),
    )
    coverage = discovery.SearchCoverage(truncated=True)

    checked = discovery.check_candidate(repo, checked_at_ns=112233, coverage=coverage)

    assert checked == discovery.CandidateCheck(
        canonical_repo_id="origin/consumer",
        observed_repo_id="acme/consumer",
        head_sha="c" * 40,
        reviewed_sha="",
        reviewed_sha_moved=False,
        license_spdx="MIT",
        is_fork=True,
        archived=True,
        default_branch="trunk",
        usage=None,
        usage_evidence_paths=("mise.toml",),
        checked_at_ns=112233,
        status=discovery.CandidateStatus.INCOMPLETE,
        refresh_triggers=(),
        incomplete_reasons=("github search results were truncated",),
    )


def test_rate_limit_partial_results_and_unclassified_warnings_fail_closed() -> None:
    repo = _repo("acme/consumer")
    for coverage in (
        discovery.SearchCoverage(rate_limited=True),
        discovery.SearchCoverage(partial=True),
        discovery.SearchCoverage(warnings=("unknown preview response",)),
    ):
        assert (
            discovery.check_candidate(repo, checked_at_ns=1, coverage=coverage).status
            is discovery.CandidateStatus.INCOMPLETE
        )


def test_fork_without_parent_metadata_is_incomplete_not_a_new_identity() -> None:
    repo = _repo(
        "forker/consumer",
        is_fork=True,
        evidence=(
            discovery.Evidence(
                "mise.toml",
                discovery.EvidenceKind.CLI_CALL,
                "graphify query architecture",
                "9" * 40,
            ),
        ),
    )

    checked = discovery.check_candidate(repo, checked_at_ns=42)

    assert checked.status is discovery.CandidateStatus.INCOMPLETE
    assert checked.incomplete_reasons == ("fork metadata omitted parent repository",)
