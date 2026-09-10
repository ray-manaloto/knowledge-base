# Copyright (c) 2026 Raymond Manaloto
"""`kb-setup lock-drift` — does `mise.lock` still describe what `mise.toml` pins?

The defect these cover SHIPPED. `6b3ab427` merged with `mise.toml` at
`antigravity-cli = "1.2.0"` and `mise.lock` at `1.1.25`, one commit after this
repo added a gate whose subject is *a pin move leaves its derived values behind*,
with all nine gates green.

The parser is tested against mise's REAL output strings, captured from
`mise lock --dry-run` on 2026-09-10 (mise 2026.9.4). A hand-invented format
would test the invention.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import lock_drift as ld
from kb_setup.result import Rc

#: Captured verbatim. The `✓` lines and the `would update:` header are what mise
#: prints on EVERY run, including one where nothing has drifted.
_CLEAN = """\
→ Targeting 11 platform(s) for /repo/mise.lock: linux-arm64, macos-arm64
→ Processing 21 tool(s): python@3.14.7, uv@0.12.8, antigravity-cli@1.2.0
→ Dry run - would update:
  ✓ python@3.14.7 for linux-arm64
  ✓ lychee@0.24.2 for windows-x64
mise WARN  /repo/mise.lock uses legacy lockfile format version 0
"""

_STALE_VERSION = (
    _CLEAN + "→ Dry run - would prune 1 stale version entry from /repo/mise.lock:"
    " antigravity-cli@1.1.25\n"
)

_ORPHAN_TOOL = _CLEAN + "→ Dry run - would prune 1 stale tool entry from /repo/mise.lock: codex\n"


# --- the PASS arm. Without it every failure below could be a broken parser. ---


def test_a_run_with_nothing_stale_is_clean() -> None:
    """The header and the progress ticks appear on a clean run and are NOT drift.

    The first version of this parser counted `→ Dry run - would update:` as a
    change, which made the gate fire on every run — the way a gate stops being
    read. Measured against the real repo with the lockfile fully in sync.
    """
    assert ld.drift(_CLEAN) == []


# --- the FAIL arms, each a REAL string mise emitted --------------------------


def test_the_shipped_defect_is_caught() -> None:
    """`antigravity-cli` at 1.1.25 in the lock while `mise.toml` says 1.2.0."""
    rows = ld.drift(_STALE_VERSION)
    assert len(rows) == 1
    assert rows[0].verb == "prune"
    assert "antigravity-cli@1.1.25" in rows[0].detail


def test_an_orphaned_tool_entry_is_caught() -> None:
    """The weeks-old second instance: a lock entry for a tool the config moved.

    `mise.toml` pins `npm:@openai/codex` while the lock carried
    `[[tools.codex]] backend = "aqua:openai/codex"` — an orphan from a BACKEND
    change, not merely a stale version.
    """
    rows = ld.drift(_ORPHAN_TOOL)
    assert [r.verb for r in rows] == ["prune"]
    assert "codex" in rows[0].detail


def test_both_drifts_at_once_are_both_reported() -> None:
    """A parser that stops at the first change hides the rest."""
    rows = ld.drift(_STALE_VERSION + _ORPHAN_TOOL.replace(_CLEAN, ""))
    assert len(rows) == 2


def test_a_word_in_ordinary_prose_is_not_a_change() -> None:
    """Anchored at line start, so a line merely CONTAINING the phrase is inert.

    This repo's guards have failed on exactly this shape more than once — a
    regex seeing `ruff check` inside `git commit -m "…"`.

    The third case is the one a cold review of `7f4035cd` said was missing: the
    first two never contained `Dry run - would` at all, so they could not have
    exercised the anchor and would have passed against the unanchored regex too.
    A test that cannot fail against the defect is not a test for it.
    """
    assert ld.drift("→ Processing 21 tool(s): would-update-tool@1.0.0\n") == []
    assert ld.drift("some prose that would add nothing\n") == []
    assert ld.drift("mise WARN  cache dir /tmp/Dry run - would add/x is unwritable\n") == []


def test_a_crashed_mise_is_not_a_clean_lockfile(tmp_path: Path, monkeypatch) -> None:
    """🔴 The defect a cold review found: rc>0 printed no rows and read as CLEAN.

    mise returns rc 0 whether the lock is in sync or stale, which is why the
    REPORT is the answer — but a mise that CRASHED also prints no `would` line,
    and the first version returned `Rc.OK` for it. A broken environment read as
    perfectly in sync: `probes-need-a-control-arm.md` rule 4, "answered no"
    collapsed into "never asked".
    """
    import subprocess

    (tmp_path / "mise.toml").write_text("[tools]\n", encoding="utf-8")
    (tmp_path / "mise.lock").write_text("", encoding="utf-8")

    def _boom(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=list(ld._ARGV),
            returncode=1,
            stdout="",
            stderr="mise ERROR failed to parse mise.toml\n",
        )

    monkeypatch.setattr(subprocess, "run", _boom)
    with pytest.raises(ld.LockUnavailableError, match="exited 1"):
        ld.preview(tmp_path)
    assert ld.main(tmp_path) == Rc.NOT_RUN


def test_the_rendered_line_is_not_double_spaced() -> None:
    """Cosmetic, and it was real: `rest` keeps the space after the verb."""
    rows = ld.drift(_ORPHAN_TOOL)
    assert "  " not in rows[0].line()


# --- the states that are NOT findings ----------------------------------------


def test_no_lockfile_is_not_run_and_never_a_pass(tmp_path: Path) -> None:
    """A repo that keeps no lockfile has not drifted; the question was not asked."""
    (tmp_path / "mise.toml").write_text("[tools]\n", encoding="utf-8")
    with pytest.raises(ld.LockUnavailableError):
        ld.preview(tmp_path)
    assert ld.main(tmp_path) == Rc.NOT_RUN


def test_no_mise_toml_is_not_run(tmp_path: Path) -> None:
    assert ld.main(tmp_path) == Rc.NOT_RUN


def test_an_unknown_flag_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    assert ld.main(tmp_path, ["--nope"]) == Rc.BAD_REQUEST


def test_the_dry_run_flag_is_present_in_the_argv() -> None:
    """Without `--dry-run` this WRITES the lockfile.

    A check that repairs what it measures reports clean forever and has measured
    nothing. Pinned here because the flag is one word and its absence is silent.
    """
    assert "--dry-run" in ld._ARGV
    assert ld._ARGV[:2] == ("mise", "lock")
