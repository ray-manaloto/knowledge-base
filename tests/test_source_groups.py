# Copyright (c) 2026 Raymond Manaloto
"""Strict source-group parsing and lifecycle controls."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from kb_setup import source_groups
from kb_setup.generated.source_groups import (
    Capability,
    EvidenceStage,
    LicenseStatus,
    SourceStatus,
)
from kb_setup.source_groups import (
    SourceGroupValidationError,
    check_main,
    load_source_groups,
    parse_source_groups,
    validate_transition,
)

REVIEWED = "a" * 40
CURRENT = "b" * 40


def _document(*sources: str) -> str:
    return (
        'schema_version = 1\ngroup_id = "graphify-ecosystem"\n'
        "generated_at_ns = 1900000000000000000\n\n" + "\n".join(sources)
    )


def _source(**changes: str | bool | int) -> str:
    options: dict[str, str | bool | int] = {
        "source_id": "graphify-demo",
        "status": "CANDIDATE",
        "reviewed": REVIEWED,
        "current": CURRENT,
        "capability_evidence": True,
        "license_status": "ALLOWED",
        "registry_admission": "METADATA_ONLY",
        "graph_ingestion": "DISABLED",
        "deep_extraction": "DISABLED",
        "reflection": "DISABLED",
        "artifacts": "DISABLED",
        "promotion": "BLOCKED",
        "status_changed_ns": 1800000000000000000,
    }
    options.update(changes)
    source_id = options["source_id"]
    status = options["status"]
    reviewed = options["reviewed"]
    current = options["current"]
    capability_evidence = options["capability_evidence"]
    license_status = options["license_status"]
    registry_admission = options["registry_admission"]
    graph_ingestion = options["graph_ingestion"]
    deep_extraction = options["deep_extraction"]
    reflection = options["reflection"]
    artifacts = options["artifacts"]
    promotion = options["promotion"]
    status_changed_ns = options["status_changed_ns"]
    capability = ""
    if capability_evidence:
        capability = f"""\
[[sources.capability_evidence]]
capability = "INGEST"
stage = "VERIFIED"
path = "docs/graphify.md"
commit = "{reviewed}"
observed_at_ns = 1700000000000000010
summary = "Project setup invokes Graphify ingest."
"""
    else:
        capability = "capability_evidence = []\n"
    license_fields = ""
    license_evidence = ""
    if license_status not in {"UNKNOWN", "REVIEW_REQUIRED"}:
        license_fields = 'spdx_id = "Apache-2.0"\nreviewed_at_ns = 1700000000000000020\n'
        license_evidence = f"""\
[[sources.license.evidence]]
path = "LICENSE"
commit = "{reviewed}"
"""
    else:
        license_fields = "evidence = []\n"
    source_budget = ""
    if graph_ingestion != "DISABLED":
        source_budget = """\
estimated_checkout_bytes = 2048
estimated_selected_files = 4
estimated_ingest_seconds = 2
"""
    semantic_budget = ""
    if deep_extraction != "DISABLED":
        semantic_budget = """\
estimated_input_tokens = 1000
max_output_tokens = 500
estimated_deep_seconds = 30
max_cost_usd_micros = 25000
"""
    return f"""\
[[sources]]
source_id = "{source_id}"
role = "PRODUCTION_CONSUMER"
status = "{status}"
warnings = ["Reviewed against the immutable pin."]

{capability}
[sources.repository]
repo_id = "example/{source_id}"
canonical_url = "https://github.com/example/{source_id}"
ref = "main"
default_branch = "main"
reviewed_commit = "{reviewed}"
is_fork = false
is_archived = false
is_vendor_mirror = false

[sources.repository.current_head]
commit = "{current}"
observed_at_ns = 1700000000000000030

[sources.license]
status = "{license_status}"
{license_fields}
{license_evidence}
[sources.paths]
include_paths = ["docs", "src"]
exclude_paths = ["src/generated"]
graphifyignore_policy = "HONOR_IF_PRESENT"

[sources.timestamps]
discovered_at_ns = 1700000000000000000
last_reviewed_at_ns = 1700000000000000040
last_status_change_at_ns = {status_changed_ns}

[sources.budgets.source]
{source_budget}
[sources.budgets.semantic]
{semantic_budget}
[sources.policies]
registry_admission = "{registry_admission}"
graph_ingestion = "{graph_ingestion}"
deep_extraction = "{deep_extraction}"
reflection = "{reflection}"
artifacts = "{artifacts}"
promotion = "{promotion}"

[sources.refresh]
cadence = "MONTHLY"
last_checked_at_ns = 1700000000000000050
next_check_after_ns = 1800000000000000050
update_available = true

[sources.pivot]
is_candidate = false
status = "NOT_EVALUATED"
comparison_dimensions = []
"""


def test_loads_exact_initial_source_config(tmp_path: Path) -> None:
    path = tmp_path / "sources" / "groups" / "graphify-ecosystem.toml"
    path.parent.mkdir(parents=True)
    path.write_text(_document(_source()), encoding="utf-8")

    config = load_source_groups(path)

    assert config.schema_version == 1
    assert config.group_id == "graphify-ecosystem"
    assert config.generated_at_ns == 1900000000000000000
    assert len(config.sources) == 1
    source = config.sources[0]
    assert source.source_id == "graphify-demo"
    assert source.status == SourceStatus.CANDIDATE
    assert source.repository.reviewed_commit == REVIEWED
    assert source.repository.current_head is not None
    assert source.repository.current_head.commit == CURRENT
    assert source.repository.current_head.commit != source.repository.reviewed_commit
    assert source.capability_evidence[0].capability == Capability.INGEST
    assert source.capability_evidence[0].stage == EvidenceStage.VERIFIED
    assert source.license.status == LicenseStatus.ALLOWED
    assert source.paths.include_paths == ["docs", "src"]
    assert source.paths.exclude_paths == ["src/generated"]


def test_committed_ecosystem_registry_tracks_every_reviewed_project() -> None:
    """The reviewed census is durable even though no candidate is admitted yet."""
    config = load_source_groups(
        Path(__file__).resolve().parents[1] / "sources/groups/graphify-ecosystem.toml"
    )

    assert len(config.sources) == 20
    assert sum(source.status == SourceStatus.REVIEWING for source in config.sources) == 16
    assert sum(source.status == SourceStatus.REJECTED for source in config.sources) == 4
    assert all(source.policies.graph_ingestion.value == "DISABLED" for source in config.sources)


def _copy_reviewed_registry(tmp_path: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    destination = tmp_path / "sources" / "groups"
    destination.mkdir(parents=True)
    shutil.copy2(root / "sources/groups/graphify-ecosystem.toml", destination)
    shutil.copy2(root / "sources/groups/graphify-ecosystem.baseline.json", destination)
    return destination / "graphify-ecosystem.toml"


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (
            "program-context-protocol/program-context-protocol",
            "attacker/identity-substitute",
            "repo_id differs",
        ),
        ("src/pcp/coupling.py", "does/not/exist.py", "capability evidence differs"),
        (
            "8a5eccc6a2034ab61c9d0738dedbc988ee9fda23",
            "0000000000000000000000000000000000000000",
            "reviewed_commit differs",
        ),
    ],
)
def test_public_check_rejects_review_identity_evidence_and_sha_mutations(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    old: str,
    new: str,
    message: str,
) -> None:
    registry = _copy_reviewed_registry(tmp_path)
    text = registry.read_text(encoding="utf-8")
    if message == "repo_id differs":
        text = text.replace(f"https://github.com/{old}", f"https://github.com/{new}", 1)
    registry.write_text(text.replace(old, new), encoding="utf-8")

    assert check_main(tmp_path, [str(registry)]) == 1
    assert message in capsys.readouterr().err


def test_public_check_rejects_incomplete_registry_membership(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = _copy_reviewed_registry(tmp_path)
    text = registry.read_text(encoding="utf-8")
    marker = text.index("[[sources]]", text.index("[[sources]]") + 1)
    registry.write_text(text[:marker], encoding="utf-8")

    assert check_main(tmp_path, [str(registry)]) == 1
    assert "registry membership differs" in capsys.readouterr().err


@pytest.mark.parametrize("mutation", ["ghost-repo", "nonexistent-path", "aaaa-sha"])
def test_public_check_rejects_registry_and_baseline_co_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mutation: str,
) -> None:
    registry = _copy_reviewed_registry(tmp_path)
    baseline_path = registry.with_name("graphify-ecosystem.baseline.json")
    registry_text = registry.read_text(encoding="utf-8")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    reviewed = baseline["sources"][0]
    original_repo = "program-context-protocol/program-context-protocol"
    original_commit = "8a5eccc6a2034ab61c9d0738dedbc988ee9fda23"
    original_path = "src/pcp/coupling.py"

    if mutation == "ghost-repo":
        ghost = "ghost-owner/ghost-repository"
        registry_text = registry_text.replace(original_repo, ghost)
        reviewed["repo_id"] = ghost
        reviewed["canonical_url"] = f"https://github.com/{ghost}"
    elif mutation == "nonexistent-path":
        nonexistent = "does/not/exist.py"
        registry_text = registry_text.replace(original_path, nonexistent)
        reviewed["capability_evidence"][1]["path"] = nonexistent
    else:
        false_commit = "a" * 40
        registry_text = registry_text.replace(original_commit, false_commit)
        reviewed["reviewed_commit"] = false_commit
        for evidence in reviewed["capability_evidence"]:
            evidence["commit"] = false_commit

    registry.write_text(registry_text, encoding="utf-8")
    baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")

    def fake_remote(url: str, _source_id: str) -> bytes:
        if mutation == "ghost-repo":
            raise SourceGroupValidationError("remote authority: ghost repository")
        repository_url = f"https://api.github.com/repos/{original_repo}"
        if url == repository_url:
            return json.dumps(
                {
                    "full_name": original_repo,
                    "html_url": f"https://github.com/{original_repo}",
                    "default_branch": "main",
                    "fork": False,
                    "archived": False,
                }
            ).encode()
        if mutation == "aaaa-sha":
            raise SourceGroupValidationError("remote authority: unknown commit")
        if url.endswith("/commits/" + original_commit):
            return json.dumps({"sha": original_commit}).encode()
        raise SourceGroupValidationError("remote authority: nonexistent evidence path")

    monkeypatch.setattr(source_groups, "_fetch_remote", fake_remote)

    assert check_main(tmp_path, [str(registry)]) == 1
    assert "remote authority" in capsys.readouterr().err


def test_public_check_fails_closed_when_remote_authority_is_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = _copy_reviewed_registry(tmp_path)

    def offline(_url: str, _source_id: str) -> bytes:
        raise SourceGroupValidationError("remote authority unavailable: offline")

    monkeypatch.setattr(source_groups, "_fetch_remote", offline)

    assert check_main(tmp_path, [str(registry)]) == 1
    assert "remote authority unavailable: offline" in capsys.readouterr().err


def test_rejects_duplicate_source_ids() -> None:
    config = _document(_source(), _source(current="c" * 40))
    with pytest.raises(SourceGroupValidationError, match="duplicate source_id"):
        parse_source_groups(config)


def test_rejects_unknown_keys_at_nested_contract_boundaries() -> None:
    config = _document(_source()).replace(
        'default_branch = "main"',
        'default_branch = "main"\nundeclared_key = true',
    )
    with pytest.raises(SourceGroupValidationError, match="unknown field"):
        parse_source_groups(config)


def test_candidate_requires_exact_capability_evidence() -> None:
    with pytest.raises(SourceGroupValidationError, match="requires capability evidence"):
        parse_source_groups(_document(_source(capability_evidence=False)))


def test_admitted_source_enables_only_selected_path_ingestion() -> None:
    config = parse_source_groups(
        _document(
            _source(
                status="ADMITTED",
                registry_admission="ADMITTED",
                graph_ingestion="SELECTED_PATHS_ONLY",
            )
        )
    )
    assert config.sources[0].status == SourceStatus.ADMITTED
    assert config.sources[0].paths.include_paths == ["docs", "src"]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {
                "status": "ADMITTED",
                "registry_admission": "ADMITTED",
                "graph_ingestion": "SELECTED_PATHS_ONLY",
            },
            "unknown license cannot admit",
        ),
        ({"deep_extraction": "CANARY"}, "unknown license cannot deep-extract"),
        ({"promotion": "MANUAL_AFTER_GATES"}, "unknown license cannot promote"),
    ],
)
def test_unknown_license_cannot_admit_deep_or_promote(
    changes: dict[str, str], message: str
) -> None:
    with pytest.raises(SourceGroupValidationError, match=message):
        parse_source_groups(_document(_source(license_status="UNKNOWN", **changes)))


def test_invalid_status_transition_is_rejected() -> None:
    previous = parse_source_groups(_document(_source(status="CANDIDATE")))
    current = parse_source_groups(
        _document(
            _source(
                status="REVIEWING",
                status_changed_ns=1800000000000000001,
            )
        )
    )
    with pytest.raises(SourceGroupValidationError, match="invalid status transition"):
        validate_transition(previous, current)


def test_reviewed_commit_is_immutable_but_current_head_is_observational() -> None:
    previous = parse_source_groups(_document(_source(status="CANDIDATE")))
    moved_head = parse_source_groups(_document(_source(status="CANDIDATE", current="c" * 40)))
    validate_transition(previous, moved_head)

    re_reviewed = parse_source_groups(
        _document(_source(status="CANDIDATE", reviewed="d" * 40, current="e" * 40))
    )
    with pytest.raises(SourceGroupValidationError, match="reviewed_commit is immutable"):
        validate_transition(previous, re_reviewed)


@pytest.mark.parametrize(
    ("status", "license_status", "registry_admission"),
    [
        ("LICENSE_REVIEW_REQUIRED", "REVIEW_REQUIRED", "REVIEW_REQUIRED"),
        ("QUARANTINED", "UNKNOWN", "REVIEW_REQUIRED"),
        ("REJECTED", "UNKNOWN", "DENIED"),
    ],
)
def test_non_admitted_terminal_and_review_states_are_metadata_only(
    status: str, license_status: str, registry_admission: str
) -> None:
    config = parse_source_groups(
        _document(
            _source(
                status=status,
                license_status=license_status,
                registry_admission=registry_admission,
            )
        )
    )
    assert config.sources[0].status.value == status
