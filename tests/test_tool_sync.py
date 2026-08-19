# Copyright (c) 2026 Raymond Manaloto
"""Transactional controls for the reviewed mise tool-sync boundary."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from kb_setup import tool_sync
from kb_setup.currency import config, skill
from kb_setup.currency.skill import SkillResult

if TYPE_CHECKING:
    from kb_setup.currency.config import ToolSpec

_LOCK = '[[tools.probe]]\nversion = "1.2.3"\nbackend = "probe"\n'
_NEW_LOCK = '[[tools.probe]]\nversion = "1.2.3"\nbackend = "probe-new"\n'


def _repo(tmp_path: Path, *, skill_declared: bool = False) -> tuple[Path, ToolSpec]:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0"\ndependencies = []\n',
        encoding="utf-8",
    )
    (tmp_path / "mise.toml").write_text('[tools]\nprobe = "1.2.3"\n', encoding="utf-8")
    (tmp_path / "mise.lock").write_text(_LOCK, encoding="utf-8")
    skill_fields = (
        'skill_dir = ".claude/skills/probe"\nskill_install = ["probe", "install"]\n'
        if skill_declared
        else ""
    )
    (tmp_path / "currency.toml").write_text(
        '[tool.probe]\nmise_key = "probe"\nbinary = "probe"\n'
        'version_args = ["-V"]\nversion_pattern = "^probe ([0-9.]+)$"\n' + skill_fields,
        encoding="utf-8",
    )
    generated = tmp_path / ".claude" / "skills" / "probe"
    generated.mkdir(parents=True)
    (generated / "SKILL.md").write_text("old skill\n", encoding="utf-8")
    return tmp_path, config.load(tmp_path)[0]


def _success(argv: list[str], _root: Path) -> subprocess.CompletedProcess[str]:
    if "--json" in argv:
        return subprocess.CompletedProcess(argv, 0, stdout="[]", stderr="")
    stdout = "probe 1.2.3\n" if argv[-1] == "-V" else ""
    return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")


def test_success_uses_declared_version_argv_and_commits_changes(tmp_path, monkeypatch) -> None:
    root, spec = _repo(tmp_path, skill_declared=True)
    calls: list[list[str]] = []

    def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        if argv[:2] == ["mise", "lock"] and "--dry-run" not in argv:
            (cwd / "mise.lock").write_text(_NEW_LOCK, encoding="utf-8")
        return _success(argv, cwd)

    def refresh(repo: Path, _spec: ToolSpec) -> SkillResult:
        (repo / ".claude/skills/probe/SKILL.md").write_text("new skill\n", encoding="utf-8")
        return SkillResult(ran=True)

    monkeypatch.setattr(tool_sync, "_run", run)
    monkeypatch.setattr(skill, "refresh", refresh)
    tool_sync._sync(root, spec, "1.2.3")
    assert ["mise", "exec", "--", "probe", "-V"] in calls
    assert (root / "mise.lock").read_text() == _NEW_LOCK
    assert (root / ".claude/skills/probe/SKILL.md").read_text() == "new skill\n"


@pytest.mark.parametrize("stage", ["install", "version", "skill", "fsync"])
def test_every_later_failure_restores_lock_and_skill(tmp_path, monkeypatch, stage) -> None:
    root, spec = _repo(tmp_path, skill_declared=True)

    def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["mise", "lock"] and "--dry-run" not in argv:
            (cwd / "mise.lock").write_text(_NEW_LOCK, encoding="utf-8")
        if stage == "install" and argv[:2] == ["mise", "install"]:
            return subprocess.CompletedProcess(argv, 7, stdout="SECRET_BODY", stderr="")
        if stage == "version" and argv[:3] == ["mise", "exec", "--"]:
            return subprocess.CompletedProcess(argv, 0, stdout="probe 9.9.9\n", stderr="")
        return _success(argv, cwd)

    def refresh(repo: Path, _spec: ToolSpec) -> SkillResult:
        (repo / ".claude/skills/probe/SKILL.md").write_text("new skill\n", encoding="utf-8")
        if stage == "skill":
            raise KeyboardInterrupt
        return SkillResult(ran=True)

    monkeypatch.setattr(tool_sync, "_run", run)
    monkeypatch.setattr(skill, "refresh", refresh)
    original_fsync = tool_sync._fsync_tree
    calls = 0

    def fsync(path: Path) -> None:
        nonlocal calls
        calls += 1
        if stage == "fsync" and calls == 1:
            raise OSError("SECRET_FSYNC")
        original_fsync(path)

    monkeypatch.setattr(tool_sync, "_fsync_tree", fsync)
    if stage == "skill":
        with pytest.raises(KeyboardInterrupt):
            tool_sync._sync(root, spec, "1.2.3")
    else:
        with pytest.raises((tool_sync.ToolSyncError, OSError)):
            tool_sync._sync(root, spec, "1.2.3")
    assert 'version = "1.2.3"' in (root / "mise.lock").read_text()
    assert (root / ".claude/skills/probe/SKILL.md").read_text() == "old skill\n"


def test_stderr_warning_rejects_and_does_not_leak_body(tmp_path, monkeypatch, capsys) -> None:
    root, _spec = _repo(tmp_path)

    def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["mise", "lock"] and "--dry-run" not in argv:
            (cwd / "mise.lock").write_text(_NEW_LOCK, encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="warning SECRET_CANARY")
        return _success(argv, cwd)

    monkeypatch.setattr(tool_sync, "_run", run)
    assert tool_sync.main(root, ["probe"]) == 1
    output = capsys.readouterr().out
    assert "SECRET_CANARY" not in output
    assert "sha256=" in output
    assert 'version = "1.2.3"' in (root / "mise.lock").read_text()


def test_exact_mise_already_installed_progress_is_not_a_warning(tmp_path) -> None:
    _root, spec = _repo(tmp_path)
    proc = subprocess.CompletedProcess(
        ["mise", "install", "probe"],
        0,
        stdout="",
        stderr="mise probe@1.2.3                ⇢ already installed\n",
    )
    assert tool_sync._mise_progress_only(proc.stderr, spec)
    assert not tool_sync._mise_progress_only("warning: source changed\n", spec)


def test_public_main_refuses_a_synthetic_skill_bearing_tool(tmp_path, monkeypatch) -> None:
    root, _spec = _repo(tmp_path, skill_declared=True)
    monkeypatch.setattr(
        tool_sync,
        "_run",
        lambda *_a: pytest.fail("public selection reached a child for a skill-bearing tool"),
    )
    assert tool_sync.main(root, ["probe"]) == 1


def test_duplicate_mise_owner_and_python_owner_are_refused(tmp_path) -> None:
    root, _spec = _repo(tmp_path)
    (root / "currency.toml").write_text(
        '[tool.one]\nmise_key = "probe"\n[tool.two]\nmise_key = "probe"\n', encoding="utf-8"
    )
    assert tool_sync.main(root, ["one"]) == 1
    (root / "currency.toml").write_text(
        '[tool.probe]\npython_package = "probe"\n', encoding="utf-8"
    )
    assert tool_sync.main(root, ["probe"]) == 1


def test_missing_exact_pin_refuses_before_any_child(tmp_path, monkeypatch) -> None:
    root, _spec = _repo(tmp_path)
    (root / "mise.toml").write_text('[tools]\nother = "1"\n', encoding="utf-8")
    monkeypatch.setattr(
        tool_sync,
        "_run",
        lambda *_a: pytest.fail("child ran without an exact selected pin"),
    )
    assert tool_sync.main(root, ["probe"]) == 1


def test_mutable_pin_and_duplicate_python_owner_are_refused(tmp_path) -> None:
    root, _spec = _repo(tmp_path)
    (root / "mise.toml").write_text('[tools]\nprobe = "latest"\n', encoding="utf-8")
    assert tool_sync.main(root, ["probe"]) == 1
    (root / "mise.toml").write_text('[tools]\nprobe = "1.2.3"\n', encoding="utf-8")
    (root / "currency.toml").write_text(
        '[tool.mise-probe]\nmise_key = "probe"\nbinary = "probe"\n'
        '[tool.python-probe]\npython_package = "mise-probe"\n',
        encoding="utf-8",
    )
    assert tool_sync.main(root, ["mise-probe"]) == 1


def test_actual_pyproject_dependency_owner_is_refused(tmp_path) -> None:
    root, _spec = _repo(tmp_path)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\ndependencies = ["probe==1.2.3"]\n',
        encoding="utf-8",
    )
    assert tool_sync.main(root, ["probe"]) == 1


def test_malformed_pyproject_refuses_ownership_authority(tmp_path) -> None:
    root, _spec = _repo(tmp_path)
    (root / "pyproject.toml").write_text("[project\nSECRET_PARSE_BODY", encoding="utf-8")
    assert tool_sync.main(root, ["probe"]) == 1


def test_alias_name_cannot_hide_duplicate_installable_distribution(tmp_path) -> None:
    root, _spec = _repo(tmp_path)
    (root / "mise.toml").write_text('[tools]\n"pipx:graphifyy" = "1.2.3"\n', encoding="utf-8")
    (root / "currency.toml").write_text(
        '[tool.graph-cli]\nmise_key = "pipx:graphifyy"\nbinary = "graphify"\n',
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\ndependencies = ["graphifyy==1.2.3"]\n',
        encoding="utf-8",
    )
    assert tool_sync.main(root, ["graph-cli"]) == 1


def test_manifest_bearing_tool_is_explicitly_out_of_scope(tmp_path) -> None:
    root, _spec = _repo(tmp_path)
    (root / "currency.toml").write_text(
        '[tool.probe]\nmise_key = "probe"\nbinary = "probe"\nmanifest = "sources/probe.manifest"\n',
        encoding="utf-8",
    )
    assert tool_sync.main(root, ["probe"]) == 1


def test_stale_or_arbitrary_lock_rejects_and_rolls_back(tmp_path, monkeypatch) -> None:
    root, _spec = _repo(tmp_path)
    before = (root / "mise.lock").read_bytes()

    def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["mise", "lock"] and "--dry-run" not in argv:
            (cwd / "mise.lock").write_text(
                '[[tools.probe]]\nversion = "9.9.9"\nbackend = "probe"\n', encoding="utf-8"
            )
        return _success(argv, cwd)

    monkeypatch.setattr(tool_sync, "_run", run)
    assert tool_sync.main(root, ["probe"]) == 1
    assert (root / "mise.lock").read_bytes() == before


def test_real_ffmpeg_selection_uses_declared_version_flag(monkeypatch) -> None:
    """The subject is the FLAG and the argv, never which ffmpeg is pinned.

    `pinned` was asserted against the literal `"8.1.2"` until 2026-08-19, and the
    stubbed stdout carried the same literal a second time. Bumping the real pin
    to 9.0.1 turned this red for a reason that has nothing to do with what the
    test is named after — `_selection` reads `mise.toml`, so the literal was this
    test asserting a config value it does not own, exactly the coupling #396
    records in `test_skillopt_contract`.

    Now the pin is READ and then fed to the stub, so the test owns its own
    environment and a pin bump can never break it. The assertions that carry the
    meaning are unchanged and still exact: the declared version flag, the round
    trip through `_observed`, and the full argv.
    """
    repo_root = Path(__file__).parents[1]
    spec, pinned = tool_sync._selection(repo_root, ["ffmpeg"])
    assert spec.version_args == ("-version",)
    # Not a tautology against `_selection`: this asserts the pin was READABLE and
    # is version-shaped. An unreadable pin yields "" and still fails here.
    assert re.fullmatch(r"\d+\.\d+\.\d+", pinned), pinned
    seen: list[list[str]] = []

    def run(argv: list[str], _root: Path) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(
            argv, 0, stdout=f"ffmpeg version {pinned} Copyright\n", stderr=""
        )

    monkeypatch.setattr(tool_sync, "_run", run)
    assert tool_sync._observed(repo_root, spec) == pinned
    assert seen == [["mise", "exec", "--", "ffmpeg", "-version"]]


def test_live_eligibility_census_is_exactly_the_two_mise_only_pins() -> None:
    """The census is asserted EXACTLY, so an accidental widening still fails.

    It was `("ffmpeg",)` until 2026-08-19 and grew when `[tool.antigravity-cli]`
    was added to `currency.toml` — a mise-only pin with a binary and a version
    pattern, which is precisely what this deliberately narrow command CAN
    truthfully synchronize. So the growth is #314's direction (`kb-tool-sync`
    covering more than one of twelve tools), not a regression, and the test was
    renamed rather than relaxed: freezing the count at one would have made the
    next legitimate addition look like a defect.

    What keeps this honest is that it stays an exact tuple. A tool that becomes
    eligible without anyone intending it still turns this red.
    """
    repo_root = Path(__file__).parents[1]
    assert tool_sync.eligible_tools(repo_root) == ("antigravity-cli", "ffmpeg")


def test_unexpected_exception_is_redacted_after_rollback(tmp_path, monkeypatch, capsys) -> None:
    root, _spec = _repo(tmp_path)

    def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["mise", "lock"] and "--dry-run" not in argv:
            (cwd / "mise.lock").write_text(_NEW_LOCK, encoding="utf-8")
        if argv[:2] == ["mise", "install"]:
            raise RuntimeError("SECRET_RUNTIME_BODY")
        return _success(argv, cwd)

    monkeypatch.setattr(tool_sync, "_run", run)
    assert tool_sync.main(root, ["probe"]) == 1
    assert "SECRET_RUNTIME_BODY" not in capsys.readouterr().out
    assert 'version = "1.2.3"' in (root / "mise.lock").read_text()


def test_escaping_or_overlapping_skill_path_is_refused(tmp_path) -> None:
    root, _spec = _repo(tmp_path)
    for path in ("../outside", ".claude"):
        (root / "currency.toml").write_text(
            '[tool.probe]\nmise_key = "probe"\nbinary = "probe"\n'
            f'skill_dir = "{path}"\nskill_install = ["probe", "install"]\n',
            encoding="utf-8",
        )
        assert tool_sync.main(root, ["probe"]) == 1


def test_persistent_rollback_fsync_failure_restores_all_bytes_and_keeps_recovery(
    tmp_path, monkeypatch
) -> None:
    root, spec = _repo(tmp_path, skill_declared=True)
    backup = tmp_path / "recovery"
    monkeypatch.setattr(tool_sync.tempfile, "mkdtemp", lambda **_k: str(backup))

    def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["mise", "lock"] and "--dry-run" not in argv:
            (cwd / "mise.lock").write_text(_NEW_LOCK, encoding="utf-8")
        return _success(argv, cwd)

    def refresh(repo: Path, _spec: ToolSpec) -> SkillResult:
        (repo / ".claude/skills/probe/SKILL.md").write_text("new skill\n", encoding="utf-8")
        return SkillResult(ran=True)

    monkeypatch.setattr(tool_sync, "_run", run)
    monkeypatch.setattr(skill, "refresh", refresh)
    calls = 0

    def fsync(_path: Path) -> None:
        nonlocal calls
        calls += 1
        raise OSError("persistent durability failure")

    monkeypatch.setattr(tool_sync, "_fsync_tree", fsync)
    with pytest.raises(tool_sync.ToolSyncError, match=str(backup)):
        tool_sync._sync(root, spec, "1.2.3")
    assert calls > 1
    assert 'version = "1.2.3"' in (root / "mise.lock").read_text()
    assert (root / ".claude/skills/probe/SKILL.md").read_text() == "old skill\n"
    assert backup.is_dir()
    assert (backup / "0").read_text(encoding="utf-8") == _LOCK


def test_public_mise_task_forwards_tool_after_double_dash() -> None:
    repo_root = Path(__file__).parents[1]
    proc = subprocess.run(
        ["mise", "run", "kb-tool-sync", "--", "definitely-unknown-tool"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert proc.returncode != 0
    assert "unknown or duplicated" in proc.stdout
    assert "usage_args" not in proc.stderr
