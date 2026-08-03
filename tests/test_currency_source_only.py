"""Tests for `source_only` — a tracked thing that is ingested, not installed.

The class exists because declaring `microsoft/SkillOpt` any other way produces a
permanent false red: it has no binary on PATH and no `[tools]` pin, and
`_check_resolution` reports a missing binary as DRIFT (correctly, for something
that *should* be installed). A check that can only fail is worth exactly as much
as one that can only pass — see `.claude/rules/probes-need-a-control-arm.md` —
so every assertion below is paired with the arm that proves it discriminates.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup.currency import apply as apply_mod
from kb_setup.currency import config, sync
from kb_setup.currency.decide import Verdict

_PINNED = "61735e3922efc2b90c6d6cab561e62e98452ca90"


def _repo(tmp_path: Path, *, ref: str = "main", commit: str = _PINNED) -> Path:
    manifest = tmp_path / "sources" / "skillopt.manifest"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    body = "url = https://github.com/microsoft/SkillOpt\nkind = code\n"
    if ref:
        body += f"ref = {ref}\n"
    if commit:
        body += f"commit = {commit}\n"
    manifest.write_text(body, encoding="utf-8")
    return tmp_path


def _clone_at(repo: Path, head: str) -> None:
    git = repo / "sources" / "skillopt" / ".git"
    git.mkdir(parents=True, exist_ok=True)
    (git / "HEAD").write_text(f"{head}\n", encoding="utf-8")


def _spec(name: str = "skillopt", manifest: str = "sources/skillopt.manifest") -> config.ToolSpec:
    return config.ToolSpec(
        name=name,
        mise_key="",
        source_only=True,
        github="microsoft/SkillOpt",
        manifest=manifest,
    )


# ----------------------------------------------------------------- config ----


def test_source_only_needs_no_mise_key_or_expected(tmp_path: Path):
    """The whole point: it is neither mise-managed nor self-managed."""
    (tmp_path / "currency.toml").write_text(
        "[tool.skillopt]\n"
        "source_only = true\n"
        'github = "microsoft/SkillOpt"\n'
        'manifest = "sources/skillopt.manifest"\n',
        encoding="utf-8",
    )
    specs = config.load(tmp_path)
    assert len(specs) == 1
    assert specs[0].source_only is True
    assert specs[0].tracks_upstream is True


def test_a_tool_with_none_of_the_three_is_still_refused(tmp_path: Path):
    """Control arm: relaxing the requirement must not remove it."""
    (tmp_path / "currency.toml").write_text('[tool.mystery]\ngithub = "a/b"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="source_only"):
        config.load(tmp_path)


def test_source_only_without_a_manifest_is_refused(tmp_path: Path):
    """Otherwise it reports a cheerful all-clear over an empty set of checks."""
    (tmp_path / "currency.toml").write_text(
        '[tool.skillopt]\nsource_only = true\ngithub = "microsoft/SkillOpt"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="needs a 'manifest'"):
        config.load(tmp_path)


# ------------------------------------------------------------------- sync ----


def test_no_binary_check_runs_for_a_source_only_tool(tmp_path: Path):
    """The defect this class exists to prevent: a permanent 'not installed' red.

    `skillopt` is not on PATH on any host, so the arm that matters is that no
    finding mentions installation at all.
    """
    repo = _repo(tmp_path)
    _clone_at(repo, _PINNED)
    status = sync.check_sync(repo, _spec())
    assert not any("not installed" in f.detail for f in status.findings)
    assert not status.drifted


def test_a_normal_tool_still_reports_a_missing_binary_as_drift(tmp_path: Path):
    """Control arm for the test above — the binary check itself still works."""
    (tmp_path / "mise.toml").write_text('[tools]\n"pipx:nonesuch" = "1.0.0"\n', encoding="utf-8")
    status = sync.check_sync(
        tmp_path,
        config.ToolSpec(name="nonesuch", mise_key="pipx:nonesuch", binary="nonesuch-xyz"),
    )
    assert any("not installed" in f.detail for f in status.findings)


def test_pinned_carries_the_manifest_ref_so_the_upstream_probe_has_a_current(tmp_path: Path):
    """`_run_one` feeds `status.pinned` to `upstream.probe(current=...)`.

    Leaving it empty would make every release look like a first sighting rather
    than a delta against what we ingested.
    """
    repo = _repo(tmp_path, ref="v0.2.0")
    _clone_at(repo, _PINNED)
    assert sync.check_sync(repo, _spec()).pinned == "v0.2.0"


def test_a_clone_ahead_of_the_manifest_is_drift(tmp_path: Path):
    """The corpus form of `clean-git-state.md`: a graph built from unpinnable bytes."""
    repo = _repo(tmp_path)
    _clone_at(repo, "0" * 40)
    status = sync.check_sync(repo, _spec())
    assert status.drifted
    assert any("kb-update" in f.detail for f in status.findings)


def test_an_absent_clone_is_blind_not_drift(tmp_path: Path):
    """`sources/<name>/` is gitignored and refetched by `kb-build`.

    A fresh checkout not having it yet says nothing about whether the pin is
    behind — reporting that as DRIFT would make every clean clone red.
    """
    repo = _repo(tmp_path)
    status = sync.check_sync(repo, _spec())
    assert not status.drifted
    assert any(f.status == sync.BLIND for f in status.findings)


def test_a_manifest_missing_its_ref_is_drift(tmp_path: Path):
    repo = _repo(tmp_path, ref="")
    assert sync.check_sync(repo, _spec()).drifted


def test_a_manifest_missing_its_commit_is_drift(tmp_path: Path):
    """A `ref` alone is not reproducible — a branch name moves."""
    repo = _repo(tmp_path, commit="")
    assert sync.check_sync(repo, _spec()).drifted


# ------------------------------------------------------------------ apply ----


def test_auto_apply_is_refused_and_names_kb_update(tmp_path: Path):
    """Fail closed. There is no mise pin to edit, and the real verb is kb-update.

    Refusing here rather than letting `set_pin_version` raise matters: a KeyError
    about a mise key nobody declared reads as an engine bug, not as "wrong verb".
    """
    verdict = Verdict(
        tool="skillopt",
        current="v0.2.0",
        latest="v0.3.0",
        auto_apply=True,
        gates_passed=(),
        ambiguities=(),
    )
    with pytest.raises(apply_mod.NotAuthorizedError, match="kb-update"):
        apply_mod.apply(tmp_path, _spec(), verdict)


# --------------------------------------------------- this repo's real entry ----


def test_this_repo_declares_skillopt_as_source_only():
    """The config actually loads, and says what the docs claim it says."""
    repo = Path(__file__).parent.parent.absolute()
    specs = {s.name: s for s in config.load(repo)}
    skillopt = specs["skillopt"]
    assert skillopt.source_only is True
    assert skillopt.manifest == "sources/skillopt.manifest"
    assert skillopt.github == "microsoft/SkillOpt"
    # No PyPI: the plugin is fetched from git, so a PyPI version would be a number
    # we compare against and never act on.
    assert skillopt.pypi == ""
    assert skillopt.watch, "the two local watch items must survive a config edit"
