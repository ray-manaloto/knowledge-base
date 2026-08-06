"""`kb-setup skill-refresh` — the standalone entry point, not the refresh itself.

The refresh lives in `kb_setup.currency.skill` and is tested in
`test_currency_skill.py`. What is tested HERE is only what this entry point adds
on top of it, and every arm is about an exit code: a task that returns 0 after
something went wrong is how a broken skill reaches a commit.

The first version of this module was a SECOND IMPLEMENTATION of the refresh,
written by reading #133's "Ask" without first checking whether this repo had
already answered it. It was deleted rather than kept in sync
(`use-tool-builtins.md`'s answer for duplicated custom code), so these arms
deliberately do not re-test repair, backups, or the installer contract.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from kb_setup import graphify_env, skill_refresh
from kb_setup.currency import config, skill
from kb_setup.currency.config import ToolSpec

_SPEC = ToolSpec(
    name="graphify",
    mise_key="pipx:graphifyy",
    skill_dir=".claude/skills/graphify",
    skill_install=("true",),
)


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    result: skill.SkillResult,
    *,
    specs: tuple[ToolSpec, ...] = (_SPEC,),
    fmt_rc: int = 0,
) -> None:
    """Point the entry point at a canned refresh result and a canned `fmt`."""
    monkeypatch.setattr(graphify_env, "assert_pinned_graphify", lambda _r=None: None)
    monkeypatch.setattr(config, "load", lambda _r: specs)
    monkeypatch.setattr(skill, "refresh", lambda _r, _s: result)
    monkeypatch.setattr(
        skill_refresh.subprocess,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess(["mise"], fmt_rc),
    )


def test_a_clean_refresh_exits_zero(tmp_path, monkeypatch) -> None:
    """CONTROL ARM for every non-zero arm below."""
    _wire(monkeypatch, skill.SkillResult(ran=True, note="ok"))
    assert skill_refresh.refresh(tmp_path) == 0


def test_a_stale_binary_is_refused_before_anything_runs(tmp_path, monkeypatch) -> None:
    """The gate this entry point exists to add.

    Generating the skill from a stale binary produces the exact drift a refresh
    removes, while LOOKING like a refresh — live on this host, where the skill
    sat at 0.9.32 under a 0.9.34 pin. Proven with a tripwire on the refresh:
    reaching it would fail with a different message than the gate's.
    """

    def gate(_r=None) -> None:
        raise SystemExit("pinned gate fired")

    monkeypatch.setattr(graphify_env, "assert_pinned_graphify", gate)
    monkeypatch.setattr(
        skill, "refresh", lambda *_a: pytest.fail("the refresh ran despite a stale binary")
    )

    with pytest.raises(SystemExit, match="pinned gate fired"):
        skill_refresh.refresh(tmp_path)


def test_the_gate_is_absent_from_the_shared_module() -> None:
    """It must stay OUT of `currency.skill`, and the reason is the other caller.

    `currency.apply` writes the NEW pin and then calls that module, so the
    resolved binary legitimately disagrees at that moment and a gate there would
    refuse every bump it exists to serve. Asserted rather than commented: "we
    chose not to put it there" is invisible to a later reader, who sees only
    that one path has a gate and the other does not, and reasonably adds it.
    """
    src = Path(skill.__file__).read_text(encoding="utf-8")
    assert "assert_pinned_graphify" not in src


def test_a_missing_tool_table_is_a_malformed_request(tmp_path, monkeypatch) -> None:
    """Rc 2, not 1: nothing failed — the request could not be formed.

    The same split `kb-skill-score` and `currency.run` draw for an unknown
    `--tool`, because a silent 0 hides a typo in `currency.toml`.
    """
    _wire(monkeypatch, skill.SkillResult(ran=True), specs=())
    assert skill_refresh.refresh(tmp_path) == 2


def test_a_refresh_that_did_not_run_exits_nonzero(tmp_path, monkeypatch) -> None:
    """`ran=False` covers a refusal AND an installer failure — both fail here.

    `currency.apply` deliberately absorbs those into a note so an otherwise
    authorized pin move still lands. A standalone refresh has nothing else to
    land, so it reports.
    """
    _wire(monkeypatch, skill.SkillResult(ran=False, note="refusing: dirty"))
    assert skill_refresh.refresh(tmp_path) == 1


def test_a_failed_fmt_propagates_its_own_rc(tmp_path, monkeypatch) -> None:
    """Its own rc, not a synthesized one, so a reader knows which step failed."""
    _wire(monkeypatch, skill.SkillResult(ran=True), fmt_rc=7)
    assert skill_refresh.refresh(tmp_path) == 7


def test_a_lost_addendum_fails_an_otherwise_successful_refresh(tmp_path, monkeypatch) -> None:
    """THE ARM THAT MATTERS: install fine, note lost, and it must NOT exit 0.

    This is the exact shape of the 2026-08-06 defect — the refresh succeeded,
    PR #190's paragraph was gone, and the run reported success, so the diff read
    as a routine regeneration and nothing flagged it.
    """
    _wire(
        monkeypatch,
        skill.SkillResult(ran=True, lost_addenda=("references/query.md (anchor moved)",)),
    )
    assert skill_refresh.refresh(tmp_path) == 1
