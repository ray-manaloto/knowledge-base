# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.currency.apply — the "and update" step, which EDITS committable files.

The safety-critical question is the same as decide's: what makes this apply a
bump it should not? So every guard is probed adversarially — an unauthorized
verdict, a file that moved under us, a tag that exists nowhere — and each must
leave the tree untouched. The happy path is the least interesting test here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Never

import pytest
from kb_setup.currency import apply as apply_mod
from kb_setup.currency import skill
from kb_setup.currency.apply import ApplyResult, NotAuthorizedError, apply, set_pin_version
from kb_setup.currency.config import ToolSpec
from kb_setup.currency.decide import Verdict

_TABLE = '[tools]\n# keep me\n"pipx:graphifyy" = { version = "0.9.25", extras = ["all"] }\n'
_BARE = '[tools]\n"pipx:graphifyy" = "0.9.25"\n'


def _verdict(*, current="0.9.25", latest="0.9.26", auto=True, ambiguities=()) -> Verdict:
    return Verdict(
        tool="graphify",
        current=current,
        latest=latest,
        auto_apply=auto,
        gates_passed=(),
        ambiguities=ambiguities,
    )


# ------------------------------------------------------ set_pin_version ----


def test_table_form_moves_only_the_version_token() -> None:
    """extras, the comment, and the table form must all survive the edit."""
    new_text, old = set_pin_version(_TABLE, "pipx:graphifyy", "0.9.26")
    assert old == "0.9.25"
    assert '"pipx:graphifyy" = { version = "0.9.26", extras = ["all"] }' in new_text
    assert "# keep me" in new_text
    assert 'extras = ["all"]' in new_text


def test_bare_form_moves_the_version() -> None:
    new_text, old = set_pin_version(_BARE, "pipx:graphifyy", "0.9.26")
    assert old == "0.9.25"
    assert '"pipx:graphifyy" = "0.9.26"' in new_text


def test_a_comment_mentioning_the_key_is_not_mistaken_for_the_pin() -> None:
    """Structural match: only the assignment line moves, never a mention of it."""
    text = (
        "[tools]\n"
        '# bump "pipx:graphifyy" carefully — it was "0.9.20" once\n'
        '"pipx:graphifyy" = "0.9.25"\n'
    )
    new_text, old = set_pin_version(text, "pipx:graphifyy", "0.9.26")
    assert old == "0.9.25"
    assert '"0.9.20" once' in new_text  # the comment's version untouched
    assert '"pipx:graphifyy" = "0.9.26"' in new_text


def test_a_missing_key_raises_rather_than_no_op() -> None:
    """A silent no-op would report a bump that never happened."""
    with pytest.raises(KeyError):
        set_pin_version(_TABLE, "pipx:nonesuch", "1.0.0")


# --------------------------------------------------------- authorization ----


def _repo(tmp_path: Path, *, mise=_TABLE, manifest=False) -> Path:
    (tmp_path / "mise.toml").write_text(mise, encoding="utf-8")
    if manifest:
        src = tmp_path / "sources"
        src.mkdir()
        (src / "graphify.manifest").write_text(
            "url = https://github.com/Graphify-Labs/graphify\n"
            "ref = v0.9.25\ncommit = aaaa\nkind = code\n",
            encoding="utf-8",
        )
    return tmp_path


def _spec(*, manifest: bool = False, skill: bool = False, tag_prefix: str = "") -> ToolSpec:
    return ToolSpec(
        name="graphify",
        mise_key="pipx:graphifyy",
        binary="graphify",
        manifest="sources/graphify.manifest" if manifest else "",
        tag_prefix=tag_prefix,
        # `skill_dir` is what gates the skill note in `apply()`; without it the
        # refresh result is never read at all, which is why the warning branch
        # went untested.
        skill_dir=".claude/skills/graphify" if skill else "",
    )


def test_an_unauthorized_verdict_is_refused_and_writes_nothing(tmp_path) -> None:
    """G7: only an auto-apply verdict may apply. The file must be byte-unchanged."""
    root = _repo(tmp_path)
    before = (root / "mise.toml").read_text(encoding="utf-8")
    ambiguous = _verdict(auto=False, ambiguities=("x",))
    with pytest.raises(NotAuthorizedError):
        apply(root, _spec(), ambiguous)
    assert (root / "mise.toml").read_text(encoding="utf-8") == before


def test_a_verdict_with_no_upgrade_is_refused(tmp_path) -> None:
    root = _repo(tmp_path)
    with pytest.raises(NotAuthorizedError):
        apply(root, _spec(), _verdict(current="0.9.25", latest="0.9.25", auto=False))


def test_apply_refuses_when_the_file_moved_under_the_verdict(tmp_path) -> None:
    """TOCTOU guard: the verdict was computed against a version no longer pinned.

    If mise.toml now pins something other than `verdict.current`, the gates never
    evaluated the current state — bumping anyway would apply a decision to a
    world it was not made in.
    """
    root = _repo(tmp_path, mise='[tools]\n"pipx:graphifyy" = "0.9.24"\n')
    with pytest.raises(NotAuthorizedError):
        apply(root, _spec(), _verdict(current="0.9.25", latest="0.9.26"))
    # And the stale pin is left exactly as found.
    assert '"0.9.24"' in (root / "mise.toml").read_text(encoding="utf-8")


def test_a_successful_apply_edits_the_pin_and_reports_it(tmp_path) -> None:
    root = _repo(tmp_path)
    result = apply(root, _spec(), _verdict())
    assert isinstance(result, ApplyResult)
    assert result.from_version == "0.9.25"
    assert result.to_version == "0.9.26"
    assert result.changed == ("mise.toml",)
    assert "rebuild pending" in result.note
    assert 'version = "0.9.26"' in (root / "mise.toml").read_text(encoding="utf-8")


def test_apply_with_a_manifest_repins_ref_and_commit(tmp_path, monkeypatch) -> None:
    root = _repo(tmp_path, manifest=True)
    monkeypatch.setattr(
        apply_mod.mf, "resolve_tag", lambda _u, v, *, prefix="": (f"{prefix or 'v'}{v}", "cafe1234")
    )
    result = apply(root, _spec(manifest=True), _verdict())
    assert set(result.changed) == {"mise.toml", "sources/graphify.manifest"}
    assert result.manifest_ref == "v0.9.26"
    manifest_text = (root / "sources" / "graphify.manifest").read_text(encoding="utf-8")
    assert "ref = v0.9.26" in manifest_text
    assert "commit = cafe1234" in manifest_text


def test_a_tag_that_resolves_nowhere_aborts_before_touching_mise(tmp_path, monkeypatch) -> None:
    """The v1.0.0-not-on-PyPI trap's git mirror: a version tagged nowhere.

    `resolve_tag` raises, and because every fallible step runs BEFORE any write,
    mise.toml must be left exactly as found — no half-applied bump.
    """
    root = _repo(tmp_path, manifest=True)
    before = (root / "mise.toml").read_text(encoding="utf-8")

    def _no_tag(_url: str, _v: str, *, prefix: str = "") -> Never:
        raise RuntimeError("no tag found")

    monkeypatch.setattr(apply_mod.mf, "resolve_tag", _no_tag)
    with pytest.raises(RuntimeError):
        apply(root, _spec(manifest=True), _verdict())
    assert (root / "mise.toml").read_text(encoding="utf-8") == before
    # The manifest, too, is untouched.
    assert "ref = v0.9.25" in (root / "sources" / "graphify.manifest").read_text(encoding="utf-8")


# --- #245: the APPLY half of the prefixed tag --------------------------------


def _prefixed_remote(monkeypatch, *tags: str) -> None:
    """Patch `resolve_tag` with the REAL candidate logic over a fake remote.

    Deliberately not a stub returning a fixed SHA. The defect was that
    `apply()` never PASSED the prefix, and a stub that answers for any input
    passes identically with and without the wiring — a test that cannot fail,
    which is the sibling finding this batch also fixes.

    argv now ends `[..., ref, f"{ref}^{{}}"]` (#500: `_resolve_ref` asks for
    the dereference too), so the REF is the second-to-last element, not the
    last — keyed on `argv[-1]` this would key on the peel PATTERN instead and
    never match a real tag name again.
    """
    import subprocess

    def _ls_remote(argv: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        ref = argv[-2]
        out = f"cafe1234\trefs/tags/{ref}\n" if ref in tags else ""
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

    monkeypatch.setattr(apply_mod.mf.subprocess, "run", _ls_remote)


def test_apply_resolves_a_tag_carrying_the_declared_prefix(tmp_path, monkeypatch) -> None:
    """The half of #245 that did NOT land, and the one that ACTS.

    `ToolSpec.tag_prefix` reached only the sync-report comparison. `apply()`
    called `resolve_tag` with no prefix at all, so an authorized codex bump —
    tag `rust-v0.147.0` — still aborted, under a comment claiming it was fixed.
    """
    root = _repo(tmp_path, manifest=True)
    _prefixed_remote(monkeypatch, "rust-v0.9.26")
    result = apply(root, _spec(manifest=True, tag_prefix="rust-v"), _verdict())
    assert result.manifest_ref == "rust-v0.9.26"
    assert "ref = rust-v0.9.26" in (root / "sources" / "graphify.manifest").read_text(
        encoding="utf-8"
    )


def test_without_the_prefix_that_same_bump_aborts_untouched(tmp_path, monkeypatch) -> None:
    """CONTROL ARM: the remote is the same; only the wiring differs.

    And the abort must still be clean — the resolve happens before any write,
    so mise.toml is byte-identical afterwards.

    Left AS-IS, deliberately (#500 spec §5): every unprefixed candidate misses
    this fake regardless of the peeling shape, so this test's green is not
    evidence for #500 either way — it is evidence for #245's wiring, which is
    what it was written to cover.
    """
    root = _repo(tmp_path, manifest=True)
    before = (root / "mise.toml").read_text(encoding="utf-8")
    _prefixed_remote(monkeypatch, "rust-v0.9.26")
    with pytest.raises(RuntimeError, match="no tag found"):
        apply(root, _spec(manifest=True), _verdict())
    assert (root / "mise.toml").read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------
# Cold-lane round 2 (`review-17e946d8adf4-cold.md`) — a COVERAGE GAP, not a defect.
#
# Every case above builds a ToolSpec with no `skill_dir`, so `skill.refresh()`
# always takes its "no project-scoped skill" no-op path and `unrepaired` is always
# empty. The branch that warns about a working tree the installer left dirty had
# therefore never been executed by a test — verified by inspection only, which is
# exactly the standard this repo does not accept for a warning nobody would
# otherwise see.
# --------------------------------------------------------------------------


def test_unrepaired_paths_are_hoisted_to_the_front_of_the_note(tmp_path, monkeypatch) -> None:
    """A warning buried mid-sentence in a note nobody parses is not a warning.

    `apply()` runs the skill refresh AFTER writing the pin and manifest, on purpose
    — a skill failure must not block an authorized bump. The cost of that ordering
    is that damage can be on disk while the bump looks clean, so the one condition
    that makes it NOT clean has to be the first thing in the note.
    """
    root = _repo(tmp_path)
    monkeypatch.setattr(
        apply_mod.skill,
        "refresh",
        lambda _root, _spec: apply_mod.skill.SkillResult(
            ran=True,
            unrepaired=(".claude/settings.json",),
            note="skill refreshed; ⚠ COULD NOT REVERT .claude/settings.json",
        ),
    )

    result = apply(root, _spec(skill=True), _verdict())

    assert result.note.startswith("⚠ working tree still dirty: .claude/settings.json"), (
        f"the warning is not first — a reader sees the bump before the damage: {result.note}"
    )
    assert "inspect before committing" in result.note


def test_a_clean_refresh_adds_no_warning(tmp_path, monkeypatch) -> None:
    """CONTROL ARM: the note must not cry wolf on the ordinary path."""
    root = _repo(tmp_path)
    monkeypatch.setattr(
        apply_mod.skill,
        "refresh",
        lambda _root, _spec: apply_mod.skill.SkillResult(ran=True, note="skill refreshed"),
    )

    result = apply(root, _spec(skill=True), _verdict())

    assert "working tree still dirty" not in result.note
    assert result.note.startswith("rebuild pending")


def test_the_reverted_delta_reaches_the_apply_note() -> None:
    """`currency.apply` must carry the reverted BYTES, not just the filenames.

    This is the caller a human reads before committing an auto-applied bump —
    the path with LESS scrutiny than a deliberate `kb-skill-refresh` — so
    dropping the delta here is exactly the "discarded without trace" case the
    capture exists to prevent (cold lane round 2 on ea6ab63).
    """
    note = apply_mod._skill_warnings(
        skill.SkillResult(
            ran=True, repaired=(".claude/settings.json",), repair_delta="-old\n+new\n"
        )
    )

    assert any("+new" in w and "-old" in w for w in note)


def test_a_clean_refresh_adds_no_apply_warning() -> None:
    """CONTROL ARM: no damage, no warnings — or every bump note cries wolf."""
    assert apply_mod._skill_warnings(skill.SkillResult(ran=True)) == []


# --- A row with no `mise_key` must REFUSE, not crash ---------------------------
#
# `apply()` passed `spec.mise_key` straight into `set_pin_version`, which raises
# `KeyError: no mise.toml pin found for ''` for an `expected`-based row. That
# escapes as a traceback rather than the clean "[currency] apply failed" every
# other refusal produces, so it reads as an engine bug instead of "this tool is
# not auto-applicable here".
#
# It became reachable for two more tools on 2026-08-08 when ruff and ty joined
# currency.toml (#242) — they are uv `dev` deps, pinned in pyproject.toml, which
# apply() does not own. Found by a cold review lane.


def test_a_spec_with_no_mise_key_refuses_instead_of_raising_keyerror(tmp_path) -> None:
    (tmp_path / "mise.toml").write_text('[tools]\nhk = "1.54.1"\n', encoding="utf-8")
    spec = ToolSpec(name="ruff", mise_key="", binary="ruff", expected="0.16.2")
    with pytest.raises(NotAuthorizedError, match=r"no `mise_key`"):
        apply(tmp_path, spec, _verdict(current="0.16.2", latest="0.16.3"))


def test_the_refusal_says_where_the_pin_actually_lives(tmp_path) -> None:
    """A refusal that does not say what to do next is a dead end, not a gate."""
    (tmp_path / "mise.toml").write_text('[tools]\nhk = "1.54.1"\n', encoding="utf-8")
    spec = ToolSpec(name="ruff", mise_key="", binary="ruff", expected="0.16.2")
    with pytest.raises(NotAuthorizedError) as e:
        apply(tmp_path, spec, _verdict(current="0.16.2", latest="0.16.3"))
    assert "pyproject.toml" in str(e.value)


def test_a_spec_with_a_mise_key_still_reaches_the_pin_editor(tmp_path) -> None:
    """CONTROL ARM: the guard must not have made every apply refuse."""
    (tmp_path / "mise.toml").write_text('[tools]\nhk = "1.54.0"\n', encoding="utf-8")
    spec = ToolSpec(name="hk", mise_key="hk", binary="hk")
    # No `manifest`/`skill_dir`, so this is the minimal successful path.
    result = apply(tmp_path, spec, _verdict(current="1.54.0", latest="1.54.1"))
    assert isinstance(result, ApplyResult)
    assert '"1.54.1"' in (tmp_path / "mise.toml").read_text(encoding="utf-8")
