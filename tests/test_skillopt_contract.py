# Copyright (c) 2026 Raymond Manaloto
"""Hostile controls for the immutable SkillOpt provenance/API boundary."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from kb_setup import skillopt_contract


def _contract_repo(tmp_path: Path) -> Path:
    source = Path(__file__).parent.parent
    for relative in (
        "pyproject.toml",
        "uv.lock",
        "mise.toml",
        "sources/skillopt.manifest",
        ".claude/settings.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
    clone = tmp_path / "sources" / "skillopt"
    clone.mkdir()
    return tmp_path


def _fake_clean_clone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        skillopt_contract,
        "_git",
        lambda _repo, *args: (
            skillopt_contract.SKILLOPT_COMMIT if args == ("rev-parse", "HEAD") else ""
        ),
    )


def test_live_installed_contract_and_repository_are_exact() -> None:
    repo = Path(__file__).parent.parent
    assert skillopt_contract.contract_errors() == ()
    assert skillopt_contract.repository_contract_errors(repo) == ()


def test_direct_url_wrong_origin_or_commit_never_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    valid = {
        "url": skillopt_contract.SKILLOPT_REPOSITORY,
        "vcs_info": {"commit_id": skillopt_contract.SKILLOPT_COMMIT},
    }
    for mutation in (
        {**valid, "url": "https://github.com/attacker/SkillOpt"},
        {**valid, "vcs_info": {"commit_id": "0" * 40}},
    ):
        monkeypatch.setattr(skillopt_contract, "installed_direct_url", lambda m=mutation: m)
        assert skillopt_contract.contract_errors()


def test_version_020_alone_cannot_certify_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        skillopt_contract,
        "installed_direct_url",
        lambda: {"url": skillopt_contract.SKILLOPT_REPOSITORY},
    )
    assert "UNKNOWN" in "\n".join(skillopt_contract.contract_errors())


def test_signature_and_entrypoint_drift_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    first = skillopt_contract._PUBLIC_SYMBOLS[0]
    monkeypatch.setattr(
        skillopt_contract,
        "_PUBLIC_SYMBOLS",
        (replace(first, expected_signature="(changed: 'bool')"),),
    )
    assert "signature changed" in "\n".join(skillopt_contract.contract_errors())
    monkeypatch.setattr(skillopt_contract, "_PUBLIC_SYMBOLS", ())
    monkeypatch.setattr(skillopt_contract, "console_entrypoint_fingerprint", lambda: ())
    assert "entry points changed" in "\n".join(skillopt_contract.contract_errors())


def test_help_drift_and_stderr_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    for name in skillopt_contract._EXPECTED_ENTRY_POINTS:
        (bin_dir / name).write_text("", encoding="utf-8")
    monkeypatch.setattr(
        skillopt_contract.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="changed", stderr=""),
    )
    with pytest.raises(RuntimeError, match="CLI help changed"):
        skillopt_contract.cli_help_fingerprint(tmp_path)
    monkeypatch.setattr(
        skillopt_contract.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr="warning"),
    )
    with pytest.raises(RuntimeError, match="stderr='warning'"):
        skillopt_contract.cli_help_fingerprint(tmp_path)


def test_repository_rejects_wrong_or_duplicate_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _contract_repo(tmp_path)
    _fake_clean_clone(monkeypatch)
    pyproject = repo / "pyproject.toml"
    original = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(
        original.replace("microsoft/SkillOpt", "attacker/SkillOpt"), encoding="utf-8"
    )
    errors = skillopt_contract.repository_contract_errors(repo)
    assert any("exactly one" in error for error in errors)
    pyproject.write_text(
        original.replace(
            '  "structlog>=26.1",',
            '  "skillopt==0.2.0",\n  "structlog>=26.1",',
        ),
        encoding="utf-8",
    )
    errors = skillopt_contract.repository_contract_errors(repo)
    assert any("exactly one" in error for error in errors)


def test_repository_rejects_skillopt_in_dependency_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _contract_repo(tmp_path)
    _fake_clean_clone(monkeypatch)
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'codegen = ["datamodel-code-generator==0.75.1"]',
            'codegen = ["datamodel-code-generator==0.75.1", "skillopt==0.2.0"]',
        ),
        encoding="utf-8",
    )
    errors = skillopt_contract.repository_contract_errors(repo)
    assert any("exactly one" in error for error in errors)


def test_manifest_comments_cannot_mask_wrong_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _contract_repo(tmp_path)
    _fake_clean_clone(monkeypatch)
    manifest = repo / "sources" / "skillopt.manifest"
    manifest.write_text(
        f"# commit = {skillopt_contract.SKILLOPT_COMMIT}\n"
        "url = https://github.com/attacker/SkillOpt\ncommit = " + "0" * 40 + "\n",
        encoding="utf-8",
    )
    errors = skillopt_contract.repository_contract_errors(repo)
    assert any("origin" in error for error in errors)
    assert any("manifest commit" in error for error in errors)


def test_wrong_clone_head_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _contract_repo(tmp_path)
    monkeypatch.setattr(
        skillopt_contract,
        "_git",
        lambda _repo, *args: "0" * 40 if args == ("rev-parse", "HEAD") else "",
    )
    errors = skillopt_contract.repository_contract_errors(repo)
    assert any("clone HEAD" in error for error in errors)


def test_dirty_clone_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _contract_repo(tmp_path)
    monkeypatch.setattr(
        skillopt_contract,
        "_git",
        lambda _repo, *args: (
            skillopt_contract.SKILLOPT_COMMIT
            if args == ("rev-parse", "HEAD")
            else " M skillopt_sleep/config.py"
        ),
    )
    errors = skillopt_contract.repository_contract_errors(repo)
    assert any("tracked modifications" in error for error in errors)


def test_mise_owner_or_plugin_reenable_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _contract_repo(tmp_path)
    _fake_clean_clone(monkeypatch)
    mise = repo / "mise.toml"
    mise.write_text(
        mise.read_text().replace("[tools]", '[tools]\nskillopt = "0.2.0"'),
        encoding="utf-8",
    )
    settings = repo / ".claude" / "settings.json"
    payload = json.loads(settings.read_text(encoding="utf-8"))
    payload["enabledPlugins"]["skillopt-sleep@skillopt"] = True
    settings.write_text(json.dumps(payload), encoding="utf-8")
    errors = skillopt_contract.repository_contract_errors(repo)
    assert any("mise duplicates" in error for error in errors)
    assert any("plugin is enabled" in error for error in errors)


def test_mise_owner_hidden_in_backend_value_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _contract_repo(tmp_path)
    _fake_clean_clone(monkeypatch)
    mise = repo / "mise.toml"
    mise.write_text(
        mise.read_text().replace("[tools]", '[tools]\nsleep_optimizer = "pipx:skillopt@0.2.0"'),
        encoding="utf-8",
    )
    errors = skillopt_contract.repository_contract_errors(repo)
    assert any("mise duplicates" in error for error in errors)


def test_real_help_and_mock_dry_run_are_warning_free_and_confined() -> None:
    repo = Path(__file__).parent.parent
    assert skillopt_contract.cli_help_fingerprint(repo)
    skillopt_contract.mock_dry_run_probe(repo)


def test_actual_mock_probe_forbids_parent_state_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = Path(__file__).parent.parent
    hostile = skillopt_contract._AUDITED_DRY_RUN.replace(
        'sys.argv = ["skillopt-sleep", *sys.argv[1:]]',
        'Path(os.environ["HOME"]).parent.joinpath(".skillopt-sleep/evidence").mkdir('
        "parents=True, exist_ok=True)",
    )
    monkeypatch.setattr(skillopt_contract, "_AUDITED_DRY_RUN", hostile)
    with pytest.raises(RuntimeError, match="external write"):
        skillopt_contract.mock_dry_run_probe(repo)


def test_mock_probe_blocks_an_arbitrary_external_write(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = Path(__file__).parent.parent
    hostile = skillopt_contract._AUDITED_DRY_RUN.replace(
        'sys.argv = ["skillopt-sleep", *sys.argv[1:]]',
        'Path("/tmp/skillopt-contract-escape").write_text("escaped")',
    )
    monkeypatch.setattr(skillopt_contract, "_AUDITED_DRY_RUN", hostile)
    with pytest.raises(RuntimeError, match="external write"):
        skillopt_contract.mock_dry_run_probe(repo)


def test_mock_probe_rejects_canary_on_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = Path(__file__).parent.parent
    hostile = skillopt_contract._AUDITED_DRY_RUN.replace(
        'sys.argv = ["skillopt-sleep", *sys.argv[1:]]',
        'print(os.environ["SKILLOPT_CONTRACT_CANARY"])',
    )
    monkeypatch.setattr(skillopt_contract, "_AUDITED_DRY_RUN", hostile)
    with pytest.raises(RuntimeError, match="leaked the contract canary"):
        skillopt_contract.mock_dry_run_probe(repo)


def test_mock_probe_rejects_canary_in_allowed_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Path(__file__).parent.parent
    hostile = skillopt_contract._AUDITED_DRY_RUN.replace(
        'sys.argv = ["skillopt-sleep", *sys.argv[1:]]',
        'Path(os.environ["SKILLOPT_CONTRACT_ROOT"], "leak").write_text('
        'os.environ["SKILLOPT_CONTRACT_CANARY"])',
    )
    monkeypatch.setattr(skillopt_contract, "_AUDITED_DRY_RUN", hostile)
    with pytest.raises(RuntimeError, match="leaked the contract canary"):
        skillopt_contract.mock_dry_run_probe(repo)


def test_locked_sync_preserves_exact_lock_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_bytes(b"exact\n")
    monkeypatch.setattr(
        skillopt_contract.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="", stderr="Resolved 162 packages in 2ms\n"
        ),
    )
    skillopt_contract.locked_sync_is_stable(tmp_path)

    def mutate_lock(*_args: object, **_kwargs: object) -> SimpleNamespace:
        lock.write_bytes(b"changed\n")
        return SimpleNamespace(returncode=0, stdout="", stderr="Resolved 162 packages in 2ms\n")

    monkeypatch.setattr(skillopt_contract.subprocess, "run", mutate_lock)
    with pytest.raises(RuntimeError, match=r"changed uv\.lock bytes"):
        skillopt_contract.locked_sync_is_stable(tmp_path)


def test_locked_sync_rejects_and_retains_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "uv.lock").write_bytes(b"exact\n")
    monkeypatch.setattr(
        skillopt_contract.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="", stderr="warning: source changed\n"
        ),
    )
    with pytest.raises(RuntimeError, match="warning: source changed"):
        skillopt_contract.locked_sync_is_stable(tmp_path)
