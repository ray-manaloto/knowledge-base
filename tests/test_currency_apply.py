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


def _spec(*, manifest: bool = False) -> ToolSpec:
    return ToolSpec(
        name="graphify",
        mise_key="pipx:graphifyy",
        binary="graphify",
        manifest="sources/graphify.manifest" if manifest else "",
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
    monkeypatch.setattr(apply_mod.mf, "resolve_tag", lambda _u, v: (f"v{v}", "cafe1234"))
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

    def _no_tag(_url: str, _v: str) -> Never:
        raise RuntimeError("no tag found")

    monkeypatch.setattr(apply_mod.mf, "resolve_tag", _no_tag)
    with pytest.raises(RuntimeError):
        apply(root, _spec(manifest=True), _verdict())
    assert (root / "mise.toml").read_text(encoding="utf-8") == before
    # The manifest, too, is untouched.
    assert "ref = v0.9.25" in (root / "sources" / "graphify.manifest").read_text(encoding="utf-8")
