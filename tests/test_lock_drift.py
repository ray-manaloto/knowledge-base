# Copyright (c) 2026 Raymond Manaloto
"""`kb-setup lock-drift` — does `mise.lock` still describe what `mise.toml` pins?

The defect these cover SHIPPED. `6b3ab427` merged with `mise.toml` at
`antigravity-cli = "1.2.0"` and `mise.lock` at `1.1.25`, one commit after this
repo added a gate whose subject is *a pin move leaves its derived values behind*,
with all nine gates green.

🔴 AND THEN THE GATE BUILT TO CATCH IT WAS BLIND TO AN ADDED TOOL. The first
version parsed mise's HUMAN report, which prints the same
`✓ node@24.0.0 for linux-arm64` progress rows whether that tool is newly pinned
or fully in sync — so a pin added to `mise.toml` and never locked read as
`mise.lock agrees`, rc 0. Found by a cold review of `7b28f460`;
`test_a_tool_absent_from_the_lock_is_caught` is that arm, and it fails against
the text parser it replaced.

Every fixture below is mise's REAL `--json` output, captured from
`mise lock --dry-run --json` against this repo on 2026-09-10 (mise 2026.9.4).
A hand-invented format would test the invention.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from kb_setup import lock_drift as ld
from kb_setup.result import Rc

#: Captured verbatim from a repo whose lockfile is fully in sync. mise emits an
#: entry only for a tool it would CHANGE, so "clean" is an empty array — there is
#: no narration left to misread, which is the whole point of the `--json` move.
_CLEAN = "[]\n"

#: `MISE_NODE_VERSION=24.0.0` — a tool pinned in the config with NO lock entry.
#: `old_versions: []` is the fact the human report cannot express.
_ADDED_TOOL = """\
[
  {
    "name": "node",
    "backend": "core:node",
    "lockfile": "~/repo/mise.lock",
    "old_versions": [],
    "new_versions": [
      "24.0.0"
    ]
  }
]
"""

#: `MISE_UV_VERSION=0.12.12` against a lock at 0.12.8 — the shipped defect's shape.
_STALE_VERSION = """\
[
  {
    "name": "uv",
    "backend": "aqua:astral-sh/uv",
    "lockfile": "~/repo/mise.lock",
    "old_versions": [
      "0.12.8"
    ],
    "new_versions": [
      "0.12.12"
    ]
  }
]
"""

#: A lock entry for a tool the config no longer pins — the weeks-old second
#: instance: `mise.toml` moved `codex` to `npm:@openai/codex` while the lock kept
#: `[[tools.codex]] backend = "aqua:openai/codex"`. An ORPHAN from a BACKEND
#: change, not merely a stale version.
_ORPHAN_TOOL = """\
[
  {
    "name": "codex",
    "backend": "aqua:openai/codex",
    "lockfile": "~/repo/mise.lock",
    "old_versions": [
      "0.149.1"
    ],
    "new_versions": []
  }
]
"""


# --- the PASS arm. Without it every failure below could be a broken parser. ---


def test_a_run_with_nothing_stale_is_clean() -> None:
    """An in-sync lockfile previews as an empty array, and that is not drift."""
    assert ld.drift(_CLEAN) == []


# --- the FAIL arms, each a REAL string mise emitted --------------------------


def test_a_tool_absent_from_the_lock_is_caught() -> None:
    """🔴 THE COLD-REVIEW DEFECT: a newly pinned tool with no lock entry.

    This is the arm the text parser could not pass and could not have been made
    to pass. mise's human report for this case is the `→ Dry run - would update:`
    header plus `✓ node@24.0.0 for <platform>` rows — byte-identical in shape to
    the resolution progress a CLEAN run prints — so the old parser skipped them
    and returned `mise.lock agrees`, rc 0. Armed against the real repo with
    `MISE_NODE_VERSION=24.0.0`: rc 0 before, rc 1 after.

    `old_versions == []` is the discriminator, and it exists only in `--json`.
    """
    rows = ld.drift(_ADDED_TOOL)
    assert len(rows) == 1
    assert rows[0].verb == "add"
    assert rows[0].name == "node"
    assert rows[0].old == ()
    assert rows[0].new == ("24.0.0",)


def test_the_shipped_defect_is_caught() -> None:
    """A version in the lock that the config has moved past."""
    rows = ld.drift(_STALE_VERSION)
    assert len(rows) == 1
    assert rows[0].verb == "update"
    assert rows[0].name == "uv"
    assert "0.12.8" in rows[0].line()
    assert "0.12.12" in rows[0].line()


def test_an_orphaned_tool_entry_is_caught() -> None:
    """A lock entry for a tool the config no longer pins at all."""
    rows = ld.drift(_ORPHAN_TOOL)
    assert [r.verb for r in rows] == ["remove"]
    assert rows[0].name == "codex"
    assert rows[0].new == ()


def test_both_drifts_at_once_are_both_reported() -> None:
    """A parser that stops at the first change hides the rest."""
    merged = (
        _STALE_VERSION.rstrip().removesuffix("]") + "," + _ORPHAN_TOOL.lstrip().removeprefix("[")
    )
    rows = ld.drift(merged)
    assert len(rows) == 2
    assert {r.name for r in rows} == {"uv", "codex"}


def test_an_entry_that_would_not_change_is_not_drift() -> None:
    """Belt-and-braces: a no-op entry reported as drift makes the gate fire always.

    mise is not observed to emit these, so this pins the parser's own contract
    rather than mise's — a gate that fires on every run stops being read, which
    the text parser this replaced shipped once.
    """
    same = '[{"name":"uv","old_versions":["0.12.8"],"new_versions":["0.12.8"]}]'
    assert ld.drift(same) == []


# --- the states that are NOT findings, and never a pass ----------------------


def test_a_crashed_mise_is_not_a_clean_lockfile(tmp_path: Path, monkeypatch) -> None:
    """🔴 rc>0 printed no rows and read as CLEAN (cold review of `7f4035cd`).

    mise returns rc 0 whether the lock is in sync or stale, which is why the
    REPORT is the answer — but a mise that CRASHED also prints no report, and the
    first version returned `Rc.OK` for it. A broken environment read as perfectly
    in sync: `probes-need-a-control-arm.md` rule 4, "answered no" collapsed into
    "never asked".
    """
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


def test_an_unparsable_report_is_not_a_clean_lockfile(tmp_path: Path, monkeypatch) -> None:
    """The SAME collapse arriving by a different road — the JSON layer's version.

    A run that exits 0 but prints something that is not its report has not
    answered the question either. Without this, `json.loads` would raise past
    `main`'s handler and die as a traceback, which in a gate run reads as the
    gate being broken rather than as the environment being unreadable.
    """
    (tmp_path / "mise.toml").write_text("[tools]\n", encoding="utf-8")
    (tmp_path / "mise.lock").write_text("", encoding="utf-8")

    def _garbage(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=list(ld._ARGV),
            returncode=0,
            stdout="mise: unknown flag --json\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", _garbage)
    with pytest.raises(ld.LockUnavailableError, match="not its JSON report"):
        ld.drift(ld.preview(tmp_path))
    assert ld.main(tmp_path) == Rc.NOT_RUN


def test_a_json_document_of_the_wrong_shape_is_not_run() -> None:
    """Valid JSON that is not the report is still "could not ask", never clean."""
    with pytest.raises(ld.LockUnavailableError, match="not the expected list"):
        ld.drift('{"error": "nope"}')
    with pytest.raises(ld.LockUnavailableError, match="non-object entry"):
        ld.drift('["node"]')


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


def test_the_dry_run_and_json_flags_are_present_in_the_argv() -> None:
    """Both flags are one word each and both fail SILENTLY when absent.

    Without `--dry-run` this WRITES the lockfile — a check that repairs what it
    measures reports clean forever and has measured nothing. Without `--json` it
    gets the human report, whose progress rows cannot distinguish a newly pinned
    tool from an in-sync one, which is the cold-review defect above.
    """
    assert "--dry-run" in ld._ARGV
    assert "--json" in ld._ARGV
    assert ld._ARGV[:2] == ("mise", "lock")


# --- round 2 of the cold review: three defects INSIDE the round-1 fix --------


def test_an_empty_report_is_not_a_clean_lockfile() -> None:
    """🔴 THE THIRD STATE, THIRD TIME — and this one was inside the fix for it.

    Round 1 fixed "a crashed mise reads as clean" at the rc layer. The JSON
    parser it shipped then wrote `json.loads(output or "[]")`, which turns
    *mise printed nothing at rc 0* back into *the lockfile is clean*. Round 2 of
    the same review caught it. `probes-need-a-control-arm.md` rule 4: "answered
    no" is not "never asked", however many layers you fix it at.
    """
    for silent in ("", "   ", "\n"):
        with pytest.raises(ld.LockUnavailableError, match="printed nothing"):
            ld.drift(silent)


def test_a_renamed_version_field_is_not_a_clean_lockfile() -> None:
    """A schema change must be NOT_RUN, never a silent pass.

    `entry.get("old_versions") or ()` read mise renaming or dropping these keys
    as "no versions on either side" — a no-op entry, which the `old == new` skip
    then discards. A gate silently emptied by an upstream rename is precisely
    what this module exists to catch one directory up.
    """
    with pytest.raises(ld.LockUnavailableError, match="no list `old_versions`"):
        ld.drift('[{"name":"uv","from_versions":["0.12.8"],"new_versions":["0.12.12"]}]')
    with pytest.raises(ld.LockUnavailableError, match="no list `new_versions`"):
        ld.drift('[{"name":"uv","old_versions":["0.12.8"]}]')


def test_a_warning_on_a_successful_run_is_reported_not_dropped(tmp_path: Path, monkeypatch) -> None:
    """🔴 Ray's 2026-09-10 §1 complaint, reintroduced inside the fix for it.

    *"the stdout/stderr is being silently dropped and i see a lot of warnings
    and errors that are not being handled"* — and round 1's fix, moving from
    `stdout + stderr` to `stdout` alone so the JSON would parse, dropped exactly
    that. mise exits 0 and warns for things worth seeing (a legacy lockfile
    format, a backend it fell back from).

    Reported, never fatal: a warning is not drift, so the run still returns OK.
    """
    (tmp_path / "mise.toml").write_text("[tools]\n", encoding="utf-8")
    (tmp_path / "mise.lock").write_text("", encoding="utf-8")

    def _warns(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=list(ld._ARGV),
            returncode=0,
            stdout="[]\n",
            stderr="mise WARN  mise.lock uses legacy lockfile format version 0\n",
        )

    monkeypatch.setattr(subprocess, "run", _warns)
    seen: list[str] = []
    monkeypatch.setattr(ld.events, "warn", lambda _id, msg, **_k: seen.append(msg))

    assert ld.main(tmp_path) == Rc.OK, "a warning is not drift"
    assert any("legacy lockfile format" in m for m in seen), "the warning was dropped"
