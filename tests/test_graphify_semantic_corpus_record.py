# Copyright (c) 2026 Raymond Manaloto
"""Behavioral coverage for recording semantic-corpus authority."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import msgspec
import pytest
from kb_setup import cli, graphify_semantic_corpus, graphify_semantic_corpus_authority
from kb_setup import graphify_semantic_corpus_record as record

_REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def exact_plan(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Build one plan with the same real resolver and planner as the CLI."""
    root = tmp_path_factory.mktemp("semantic-corpus-record")
    source = root / "exact-graphify-source"
    source_pin = graphify_semantic_corpus.admit_source(_REPO_ROOT, source)
    candidate = root / "exact-graphify-plan"
    graphify_semantic_corpus.plan_source(
        source,
        candidate,
        source=source_pin,
        max_output_tokens=graphify_semantic_corpus.planned_max_output_tokens(
            _REPO_ROOT, os.environ
        ),
    )
    return candidate, source


def _copy_plan(source: Path, destination: Path) -> Path:
    destination.mkdir(parents=True)
    for name in record.PLAN_FILES:
        shutil.copyfile(source / name, destination / name)
    return destination


def _identity_moved_authority(plan: Path) -> bytes:
    """An authority one IDENTITY-only move away from `plan`, independent of repo state.

    The fixture used to copy the REAL recorded authority, which made every
    "identity-only move" test depend on the real canonical plan being stale
    relative to a fresh one — true until the first real `record --accept`
    landed, false the moment it did (the tests flipped to "nothing to record").
    A test must own its environment: derive the authority from the candidate
    itself and perturb only the two identity digests.
    """
    digests = {
        "advisories_sha256": graphify_semantic_corpus.sha256_path(plan / "advisories.json"),
        "exclusions_sha256": graphify_semantic_corpus.sha256_path(plan / "exclusions.json"),
        "execution_config_sha256": graphify_semantic_corpus.sha256_path(
            plan / "execution-config.json"
        ),
        "plan_manifest_sha256": graphify_semantic_corpus.sha256_path(plan / "manifest.json"),
    }
    for name in record.IDENTITY_DIGESTS:
        digests[name] = "0" * 8 + digests[name][8:]
    return graphify_semantic_corpus.encode_canonical(
        graphify_semantic_corpus.AuthorityRoots(schema_version=1, **digests)
    )


def _state(tmp_path: Path, candidate: Path) -> tuple[Path, Path, Path]:
    canonical = _copy_plan(candidate, tmp_path / "state/canonical")
    authority = tmp_path / "state/authority.json"
    authority.write_bytes(_identity_moved_authority(candidate))
    ledger = tmp_path / "state/authority-ledger.md"
    ledger.write_text(
        "---\nname: test-authority-ledger\ndescription: Isolated authority history.\n---\n\n"
        "Recorded test authority.\n\n- **before** — unchanged\n",
        encoding="utf-8",
    )
    return canonical, authority, ledger


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(root.iterdir())}


def _authority_for_plan(plan: Path) -> bytes:
    return graphify_semantic_corpus.encode_canonical(
        graphify_semantic_corpus.AuthorityRoots(
            advisories_sha256=graphify_semantic_corpus.sha256_path(plan / "advisories.json"),
            exclusions_sha256=graphify_semantic_corpus.sha256_path(plan / "exclusions.json"),
            execution_config_sha256=graphify_semantic_corpus.sha256_path(
                plan / "execution-config.json"
            ),
            plan_manifest_sha256=graphify_semantic_corpus.sha256_path(plan / "manifest.json"),
            schema_version=1,
        )
    )


def _reserialize_advisories(plan: Path, *, update_manifest: bool) -> None:
    path = plan / "advisories.json"
    payload = json.loads(path.read_bytes())
    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    assert raw != path.read_bytes()
    path.write_bytes(raw)
    if not update_manifest:
        return
    manifest_path = plan / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    for member in manifest["members"]:
        if member["name"] == "advisories.json":
            member["sha256"] = hashlib.sha256(raw).hexdigest()
            member["size"] = len(raw)
    manifest_path.write_bytes(msgspec.json.encode(manifest, order="sorted") + b"\n")


def test_plan_files_match_the_planner_contract() -> None:
    """The member-only promotion allowlist must cover exactly one plan."""
    assert set(record.PLAN_FILES) == {
        *graphify_semantic_corpus._PLAN_MEMBERS,
        "manifest.json",
    }


def test_recorded_authority_is_loaded_from_canonical_data() -> None:
    """The tracked JSON is the sole source of execution authority."""
    path = Path(graphify_semantic_corpus_authority.__file__).with_name(
        "graphify_semantic_corpus_authority.json"
    )
    assert path.read_bytes() == graphify_semantic_corpus_authority.AUTHORITY_JSON
    authority = msgspec.json.decode(
        path.read_bytes(),
        type=graphify_semantic_corpus.AuthorityRoots,
        strict=True,
    )
    assert path.read_bytes() == graphify_semantic_corpus.encode_canonical(authority)
    # Structural, not literal: the four digests change on every `record --accept`
    # (this test pinned the pre-first-accept values and broke on the first one).
    # What must hold forever: five fields, four 64-hex digests, schema 1, and the
    # file is exactly the canonical (sorted-key) encoding of what it decodes to.
    assert authority.schema_version == 1
    for name in (*record.IDENTITY_DIGESTS, *record.DECISION_DIGESTS):
        digest = getattr(authority, name)
        assert len(digest) == 64
        assert set(digest) <= set("0123456789abcdef")


def test_cli_routes_record_before_the_existing_corpus_parser(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Path, list[str]]] = []

    def record_main(repo_root: Path, args: list[str]) -> int:
        calls.append((repo_root, args))
        return 17

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(record, "record_main", record_main)

    assert cli.main(["graphify-semantic-corpus", "record", "--accept"]) == 17
    assert calls == [(tmp_path, ["--accept"])]


def test_identity_only_dry_run_is_recordable_and_mutates_nothing(
    exact_plan: tuple[Path, Path], tmp_path: Path
) -> None:
    candidate, source = exact_plan
    canonical, authority, ledger = _state(tmp_path, candidate)
    before = (_tree_bytes(canonical), authority.read_bytes(), ledger.read_bytes())

    report = record.record_plan(
        candidate,
        repo_root=_REPO_ROOT,
        canonical_dir=canonical,
        authority_path=authority,
        ledger_path=ledger,
        source_root=source,
    )

    assert report.moved == (
        "plan_manifest_sha256",
        "execution_config_sha256",
    )
    assert report.decision_moved == ()
    assert report.recordable is True
    assert report.accepted is False
    assert report.authorized_after is None
    assert before == (_tree_bytes(canonical), authority.read_bytes(), ledger.read_bytes())


def test_decision_digest_requires_exact_explicit_name(
    exact_plan: tuple[Path, Path], tmp_path: Path
) -> None:
    original, source = exact_plan
    candidate = _copy_plan(original, tmp_path / "decision-candidate")
    _reserialize_advisories(candidate, update_manifest=True)
    canonical, authority, ledger = _state(tmp_path, original)

    unacknowledged = record.record_plan(
        candidate,
        repo_root=_REPO_ROOT,
        canonical_dir=canonical,
        authority_path=authority,
        ledger_path=ledger,
        source_root=source,
    )
    acknowledged = record.record_plan(
        candidate,
        repo_root=_REPO_ROOT,
        canonical_dir=canonical,
        authority_path=authority,
        ledger_path=ledger,
        accept_decision_change=frozenset({"advisories_sha256"}),
        source_root=source,
    )
    wrong_name = record.record_plan(
        candidate,
        repo_root=_REPO_ROOT,
        canonical_dir=canonical,
        authority_path=authority,
        ledger_path=ledger,
        accept_decision_change=frozenset({"exclusions_sha256"}),
        source_root=source,
    )

    assert unacknowledged.decision_moved == ("advisories_sha256",)
    assert unacknowledged.recordable is False
    assert acknowledged.recordable is True
    assert wrong_name.recordable is False


def test_accept_replaces_only_plan_members_and_records_authority(
    exact_plan: tuple[Path, Path], tmp_path: Path
) -> None:
    candidate, source = exact_plan
    canonical, authority, ledger = _state(tmp_path, candidate)
    ledger_before = ledger.read_text(encoding="utf-8")

    report = record.record_plan(
        candidate,
        repo_root=_REPO_ROOT,
        canonical_dir=canonical,
        authority_path=authority,
        ledger_path=ledger,
        accept=True,
        source_root=source,
    )

    assert report.accepted is True
    assert report.authorized_after is True
    assert {path.name for path in canonical.iterdir()} == set(record.PLAN_FILES)
    assert all(path.is_file() and not path.is_symlink() for path in canonical.iterdir())
    assert _tree_bytes(canonical) == _tree_bytes(candidate)
    assert report.superseded_dir is not None
    superseded = _REPO_ROOT / report.superseded_dir
    if not superseded.is_absolute():
        superseded = _REPO_ROOT / superseded
    assert superseded.is_dir()
    decoded = json.loads(authority.read_bytes())
    assert set(decoded) == {
        "advisories_sha256",
        "exclusions_sha256",
        "execution_config_sha256",
        "plan_manifest_sha256",
        "schema_version",
    }
    assert authority.read_bytes() == _authority_for_plan(candidate)
    ledger_after = ledger.read_text(encoding="utf-8")
    assert ledger_after.startswith(ledger_before)
    assert ledger_after.count("\n- **") == ledger_before.count("\n- **") + 1
    # Hashes are recorded IN FULL: a 12-char prefix read as words to the
    # spell-checker, whose --write-changes hook rewrote a short commit id.
    appended = ledger_after[len(ledger_before) :]
    assert report.digests_after["plan_manifest_sha256"] in appended
    assert report.digests_after["execution_config_sha256"] in appended
    assert report.digests_before["plan_manifest_sha256"] in appended
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert len(head) == 40
    assert f"HEAD {head} " in appended


def test_failed_post_accept_verification_rolls_everything_back(
    exact_plan: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    candidate, source = exact_plan
    canonical, authority, ledger = _state(tmp_path, candidate)
    before = (_tree_bytes(canonical), authority.read_bytes(), ledger.read_bytes())
    real_verify = record.verify_plan
    calls = 0

    def fail_second_verify(
        candidate_path: Path,
        source_root: Path,
        *,
        authority_path: Path | None = None,
        repo_root: Path | None = None,
    ) -> graphify_semantic_corpus.PlanVerification:
        nonlocal calls
        calls += 1
        if calls == 2:
            return graphify_semantic_corpus.PlanVerification(
                state="incomplete",
                structural_complete=True,
                execution_authorized=False,
                reasons=("plan-authority-mismatch",),
            )
        return real_verify(
            candidate_path,
            source_root,
            authority_path=authority_path,
            repo_root=repo_root,
        )

    monkeypatch.setattr(record, "verify_plan", fail_second_verify)
    report = record.record_plan(
        candidate,
        repo_root=_REPO_ROOT,
        canonical_dir=canonical,
        authority_path=authority,
        ledger_path=ledger,
        accept=True,
        source_root=source,
    )

    assert report.accepted is False
    assert report.authorized_after is False
    assert before == (_tree_bytes(canonical), authority.read_bytes(), ledger.read_bytes())
    assert not list(canonical.parent.glob(f"{canonical.name}.superseded-*"))


def test_failed_canonical_move_preserves_the_original_directory(
    exact_plan: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    candidate, source = exact_plan
    canonical, authority, ledger = _state(tmp_path, candidate)
    before = (_tree_bytes(canonical), authority.read_bytes(), ledger.read_bytes())
    path_replace = Path.replace

    def fail_canonical_move(path: Path, target: Path) -> Path:
        if path == canonical and ".superseded-" in target.name:
            raise OSError("simulated canonical move failure")
        return path_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_canonical_move)
    report = record.record_plan(
        candidate,
        repo_root=_REPO_ROOT,
        canonical_dir=canonical,
        authority_path=authority,
        ledger_path=ledger,
        accept=True,
        source_root=source,
    )

    assert report.accepted is False
    assert report.authorized_after is False
    assert before == (_tree_bytes(canonical), authority.read_bytes(), ledger.read_bytes())
    assert not list(canonical.parent.glob(f"{canonical.name}.superseded-*"))


def test_structural_failure_is_not_recordable(
    exact_plan: tuple[Path, Path], tmp_path: Path
) -> None:
    original, source = exact_plan
    candidate = _copy_plan(original, tmp_path / "corrupt-candidate")
    _reserialize_advisories(candidate, update_manifest=False)
    canonical, authority, ledger = _state(tmp_path, original)
    before = (_tree_bytes(canonical), authority.read_bytes(), ledger.read_bytes())

    report = record.record_plan(
        candidate,
        repo_root=_REPO_ROOT,
        canonical_dir=canonical,
        authority_path=authority,
        ledger_path=ledger,
        accept=True,
        source_root=source,
    )

    assert report.recordable is False
    assert "member-digest-mismatch:advisories.json" in report.candidate_reasons
    assert before == (_tree_bytes(canonical), authority.read_bytes(), ledger.read_bytes())


def test_staging_ignores_extras_and_refuses_missing_members(
    exact_plan: tuple[Path, Path], tmp_path: Path
) -> None:
    original, source = exact_plan
    candidate = _copy_plan(original, tmp_path / "candidate-with-extra")
    (candidate / "plan.log").write_text("ignored\n", encoding="utf-8")
    canonical, authority, ledger = _state(tmp_path, original)

    with_extra = record.record_plan(
        candidate,
        repo_root=_REPO_ROOT,
        canonical_dir=canonical,
        authority_path=authority,
        ledger_path=ledger,
        source_root=source,
    )
    (candidate / "execution-config.json").unlink()
    missing = record.record_plan(
        candidate,
        repo_root=_REPO_ROOT,
        canonical_dir=canonical,
        authority_path=authority,
        ledger_path=ledger,
        source_root=source,
    )

    assert with_extra.ignored_extras == ("plan.log",)
    assert "candidate-entry-set-mismatch" not in with_extra.candidate_reasons
    assert missing.recordable is False
    assert "member-unavailable:execution-config.json" in missing.candidate_reasons


def test_nothing_to_record_is_refused(exact_plan: tuple[Path, Path], tmp_path: Path) -> None:
    candidate, source = exact_plan
    canonical, authority, ledger = _state(tmp_path, candidate)
    authority.write_bytes(_authority_for_plan(candidate))

    report = record.record_plan(
        candidate,
        repo_root=_REPO_ROOT,
        canonical_dir=canonical,
        authority_path=authority,
        ledger_path=ledger,
        source_root=source,
    )

    assert report.moved == ()
    assert report.recordable is False
