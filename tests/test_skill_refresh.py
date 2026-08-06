"""`kb-skill-refresh` runs the generator and keeps what the generator must not own.

The fake installer here does not merely record that it was called — it performs
the **real** #133 regression on the file, byte for byte: rewrites the hook
command to an absolute version-frozen path, drops the `"timeout": 15`, and
strips the trailing newline. A stub that only asserted "subprocess.run was
invoked" would pass against a `refresh()` that never restored anything, which is
the entire behaviour under test (`stubbed-run-hides-second-writer-bugs`).

Every arm therefore reads the FILE afterwards, never the mock.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from kb_setup import graphify_env, skill_refresh

SETTINGS = ".claude/settings.json"
CLAUDE_MD = ".claude/CLAUDE.md"

#: The hook command shape this repo commits — mise-relative, so it follows the
#: pin on every clone. The installer replaces it with an absolute path.
_MISE_HOOK = 'mise exec -C "${CLAUDE_PROJECT_DIR:-.}" -- graphify hook-guard search'

#: The shape this repo commits: a mise-relative hook command with a timeout, and
#: a trailing newline. All three are what the installer destroys.
_GOOD_SETTINGS = (
    json.dumps(
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": _MISE_HOOK,
                                "timeout": 15,
                            }
                        ],
                    }
                ]
            }
        },
        indent=2,
    )
    + "\n"
)


def _repo(tmp_path: Path) -> Path:
    """A repo root carrying both protected files and a stamp."""
    (tmp_path / ".claude" / "skills" / "graphify").mkdir(parents=True)
    (tmp_path / SETTINGS).write_text(_GOOD_SETTINGS, encoding="utf-8")
    (tmp_path / CLAUDE_MD).write_text("# graphify\n\nhand-authored pointer.\n", encoding="utf-8")
    (tmp_path / skill_refresh.STAMP).write_text("0.9.32", encoding="utf-8")
    return tmp_path


def _wire(monkeypatch: pytest.MonkeyPatch, root: Path, installer, *, fmt_rc: int = 0) -> list[str]:
    """Point `refresh` at a fake graphify whose `install` runs ``installer``."""
    monkeypatch.setattr(graphify_env, "assert_pinned_graphify", lambda _r=None: None)
    monkeypatch.setattr(graphify_env, "graphify_exe", lambda _r=None: "/fake/graphify")
    monkeypatch.setattr(graphify_env, "clean_env", lambda _extra=None: {})
    monkeypatch.setattr(graphify_env, "pinned_graphify_version", lambda _r=None: "0.9.34")
    seen: list[str] = []

    def fake_run(cmd: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        seen.append(" ".join(cmd))
        if cmd[1:] == ["install", "--project"]:
            return subprocess.CompletedProcess(cmd, installer(root))
        return subprocess.CompletedProcess(cmd, fmt_rc)

    monkeypatch.setattr(skill_refresh.subprocess, "run", fake_run)
    return seen


def _regressing_installer(root: Path) -> int:
    """Reproduce #133's three regressions exactly, then stamp the new version.

    Edited through the PARSED payload, not the raw text: the first version of
    this fixture did a `str.replace` for `-C "${CLAUDE_PROJECT_DIR:-.}"`, which
    never matched because the quotes are backslash-escaped inside JSON — so the
    absolute-path regression silently did not happen and only two of the three
    were actually exercised. Caught by the arm that asserts the offending bytes
    appear in the printed diff (`prove-the-mutation-hit-the-line`).
    """
    hook = json.loads((root / SETTINGS).read_text(encoding="utf-8"))
    entry = hook["hooks"]["PreToolUse"][0]["hooks"][0]
    entry["command"] = entry["command"].replace(
        'mise exec -C "${CLAUDE_PROJECT_DIR:-.}" -- graphify',
        "/Users/x/.local/share/mise/installs/pipx-graphifyy/0.9.34/bin/graphify",
    )
    del entry["timeout"]
    (root / SETTINGS).write_text(json.dumps(hook, indent=2), encoding="utf-8")  # no newline
    (root / skill_refresh.STAMP).write_text("0.9.34", encoding="utf-8")
    return 0


def test_the_installers_settings_regression_is_reverted(tmp_path, monkeypatch) -> None:
    """All three #133 regressions are undone, and the file is byte-identical.

    Byte equality rather than three field assertions: the newline strip is one
    of the three, and a field-wise check cannot see it.
    """
    root = _repo(tmp_path)
    _wire(monkeypatch, root, _regressing_installer)

    assert skill_refresh.refresh(root) == 0
    assert (root / SETTINGS).read_text(encoding="utf-8") == _GOOD_SETTINGS


def test_the_reverted_change_is_printed_not_swallowed(tmp_path, monkeypatch, capsys) -> None:
    """A discarded installer change must leave a trace a human can read.

    This is the arm that keeps the wrapper from becoming a second way to go
    stale: a future graphify that legitimately adds a hook would otherwise have
    it reverted with no trace at all.
    """
    root = _repo(tmp_path)
    _wire(monkeypatch, root, _regressing_installer)
    skill_refresh.refresh(root)

    out = capsys.readouterr().out
    assert "reverted the installer's rewrite" in out
    # The diff must carry the actual offending bytes, not just say "it changed".
    assert "pipx-graphifyy/0.9.34/bin/graphify" in out
    assert "timeout" in out


def test_an_untouched_file_reports_nothing(tmp_path, monkeypatch, capsys) -> None:
    """CONTROL ARM: silence when the installer changed nothing.

    Without this, a `refresh()` that printed "reverted" unconditionally would
    pass every arm above while telling the operator a lie on every clean run.
    """
    root = _repo(tmp_path)
    _wire(monkeypatch, root, lambda _r: 0)

    assert skill_refresh.refresh(root) == 0
    out = capsys.readouterr().out
    assert "reverted" not in out
    assert "CREATED" not in out
    assert "DELETED" not in out


def test_a_file_the_installer_creates_is_kept(tmp_path, monkeypatch, capsys) -> None:
    """An absent protected file that the installer writes is a new artifact.

    `None` and `""` are kept distinct in `_read` for exactly this: reverting a
    creation would silently defeat a first-time `graphify install --project`.
    """
    root = _repo(tmp_path)
    (root / CLAUDE_MD).unlink()

    def creates(r: Path) -> int:
        (r / CLAUDE_MD).write_text("# graphify\n", encoding="utf-8")
        return 0

    _wire(monkeypatch, root, creates)

    assert skill_refresh.refresh(root) == 0
    assert (root / CLAUDE_MD).read_text(encoding="utf-8") == "# graphify\n"
    assert "CREATED by the installer" in capsys.readouterr().out


def test_a_file_the_installer_deletes_is_restored(tmp_path, monkeypatch, capsys) -> None:
    """Deletion is a rewrite to nothing and must be undone like any other."""
    root = _repo(tmp_path)

    def deletes(r: Path) -> int:
        (r / SETTINGS).unlink()
        return 0

    _wire(monkeypatch, root, deletes)

    assert skill_refresh.refresh(root) == 0
    assert (root / SETTINGS).read_text(encoding="utf-8") == _GOOD_SETTINGS
    assert "DELETED by the installer" in capsys.readouterr().out


def test_a_failed_installer_restores_nothing_and_propagates_its_rc(
    tmp_path, monkeypatch, capsys
) -> None:
    """A failed install leaves the tree alone and returns the installer's rc.

    Restoring after a failure would be worse than useless: it would overwrite
    whatever partial state the operator needs to diagnose, and a synthesized rc
    would hide which step failed.
    """
    root = _repo(tmp_path)

    def fails(r: Path) -> int:
        (r / SETTINGS).write_text("half written", encoding="utf-8")
        return 3

    _wire(monkeypatch, root, fails)

    assert skill_refresh.refresh(root) == 3
    assert (root / SETTINGS).read_text(encoding="utf-8") == "half written"
    assert "nothing restored" in capsys.readouterr().out


def test_a_failed_fmt_propagates_its_own_rc(tmp_path, monkeypatch) -> None:
    """`fmt` failing is reported as `fmt` failing, after the restores ran."""
    root = _repo(tmp_path)
    _wire(monkeypatch, root, _regressing_installer, fmt_rc=7)

    assert skill_refresh.refresh(root) == 7
    # The restore still happened — the formatter runs last, on purpose.
    assert (root / SETTINGS).read_text(encoding="utf-8") == _GOOD_SETTINGS


def test_a_stale_binary_is_refused_before_the_installer_runs(tmp_path, monkeypatch) -> None:
    """The version gate fires FIRST — generating from a stale graphify IS the drift.

    Proven with a tripwire on the installer: reaching it would fail with a
    different message than the gate's.
    """
    root = _repo(tmp_path)

    def gate(_r=None) -> None:
        raise SystemExit("pinned gate fired")

    monkeypatch.setattr(graphify_env, "assert_pinned_graphify", gate)
    monkeypatch.setattr(
        skill_refresh.subprocess,
        "run",
        lambda *_a, **_k: pytest.fail("the installer ran despite a stale binary"),
    )

    with pytest.raises(SystemExit, match="pinned gate fired"):
        skill_refresh.refresh(root)


def test_both_hand_owned_claude_files_are_protected() -> None:
    """The protected set is the contract.

    `.claude/CLAUDE.md` is NOT in #133's list and is here deliberately: the
    installer writes a `# graphify` block there, and that file is hand-authored
    and sits at its `md_size_budget`, so an installer append breaks a gate
    rather than merely churning bytes.
    """
    assert skill_refresh.PROTECTED == (".claude/settings.json", ".claude/CLAUDE.md")
