# Copyright (c) 2026 Raymond Manaloto
"""Tests for :mod:`kb_setup.env_refresh` (#702).

The live three-arm probe that settled the design is recorded in the module
docstring; it cannot run here, because the condition it measures — the Bash
tool re-sourcing a shell snapshot before every command — is a property of the
main session's tool and is invisible to anything spawned another way. These
tests pin the parts that ARE reproducible: the exit code when the variable is
absent, idempotence, refusal to guess a shims path, and the line ORDER, which is
the one detail a reader gets backwards.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import env_refresh
from kb_setup.result import Rc

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest


class _Proc:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode


def _mise_ok(shims: str = "/data/mise/shims") -> Callable[..., _Proc]:
    def run(*_args: object, **_kwargs: object) -> _Proc:
        return _Proc(json.dumps({"dirs": {"shims": shims}}))

    return run


def test_absent_env_file_is_not_run_never_ok(tmp_path: Path) -> None:
    """No CLAUDE_ENV_FILE means the hook event cannot persist environment.

    `Rc.NOT_RUN`, never `Rc.OK`: reporting success here is exactly the failure
    mode #702 warns about — a hook that writes nothing looks like one that works.
    """
    assert env_refresh.apply({}, run=_mise_ok()) == Rc.NOT_RUN
    assert list(tmp_path.iterdir()) == []


def test_writes_shims_entry_and_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "env.sh"
    env = {env_refresh.ENV_FILE_VAR: str(target)}

    assert env_refresh.apply(env, run=_mise_ok()) == Rc.OK
    first = target.read_text(encoding="utf-8")
    assert 'export PATH="/data/mise/shims:$PATH"' in first

    # A CwdChanged or FileChanged trigger fires many times a session; without
    # the marker check each fire would append another PATH entry, unbounded.
    assert env_refresh.apply(env, run=_mise_ok()) == Rc.OK
    assert target.read_text(encoding="utf-8") == first


def test_sentinel_lands_behind_the_shims_entry() -> None:
    """`export PATH="X:$PATH"` PREPENDS, so the LAST line written wins the head.

    The sentinel is emitted first precisely so the shims directory ends up at
    PATH position 1 and the sentinel at 2 — which is what the live arm measured.
    """
    lines = env_refresh.lines_for(Path("/data/mise/shims"), sentinel=True)
    sentinel_at = lines.index(f'export PATH="{env_refresh.SENTINEL_DIR}:$PATH"')
    shims_at = lines.index('export PATH="/data/mise/shims:$PATH"')
    assert sentinel_at < shims_at
    assert lines[0] == env_refresh.MARKER


def test_no_sentinel_by_default() -> None:
    lines = env_refresh.lines_for(Path("/data/mise/shims"))
    assert not any(env_refresh.SENTINEL_DIR in line for line in lines)
    assert not any(env_refresh.SENTINEL_VAR in line for line in lines)


def test_refuses_to_guess_when_mise_cannot_answer(tmp_path: Path) -> None:
    """A PATH entry that resolves nothing is indistinguishable from success."""
    target = tmp_path / "env.sh"

    def run(*_args: object, **_kwargs: object) -> _Proc:
        return _Proc("", returncode=1)

    assert env_refresh.apply({env_refresh.ENV_FILE_VAR: str(target)}, run=run) == Rc.NOT_RUN
    assert not target.exists()


def test_shims_dir_survives_mise_missing() -> None:
    def run(*_args: object, **_kwargs: object) -> _Proc:
        raise OSError("mise not found")

    assert env_refresh.shims_dir(run=run) is None


def test_shims_dir_survives_unparsable_output() -> None:
    def run(*_args: object, **_kwargs: object) -> _Proc:
        return _Proc("not json at all")

    assert env_refresh.shims_dir(run=run) is None


def test_shims_dir_survives_missing_key() -> None:
    def run(*_args: object, **_kwargs: object) -> _Proc:
        return _Proc(json.dumps({"dirs": {}}))

    assert env_refresh.shims_dir(run=run) is None


def test_append_preserves_other_hooks_lines(tmp_path: Path) -> None:
    """`hooks.md:1185` says APPEND so other hooks' variables survive."""
    target = tmp_path / "env.sh"
    target.write_text('export FROM_ANOTHER_HOOK="kept"\n', encoding="utf-8")

    assert env_refresh.apply({env_refresh.ENV_FILE_VAR: str(target)}, run=_mise_ok()) == Rc.OK
    body = target.read_text(encoding="utf-8")
    assert 'export FROM_ANOTHER_HOOK="kept"' in body
    assert env_refresh.MARKER in body


def test_append_to_a_file_with_no_trailing_newline(tmp_path: Path) -> None:
    """A preamble is sourced, so a glued-together line would be a syntax error."""
    target = tmp_path / "env.sh"
    target.write_text('export A="1"', encoding="utf-8")

    assert env_refresh.apply({env_refresh.ENV_FILE_VAR: str(target)}, run=_mise_ok()) == Rc.OK
    lines = target.read_text(encoding="utf-8").splitlines()
    assert lines[0] == 'export A="1"'
    assert env_refresh.MARKER in lines


def test_unknown_argument_is_a_bad_request() -> None:
    assert env_refresh.main(["--nope"], env={}) == Rc.BAD_REQUEST


def test_main_reads_the_passed_env_not_the_process(tmp_path: Path) -> None:
    target = tmp_path / "env.sh"
    assert env_refresh.main([], env={env_refresh.ENV_FILE_VAR: str(target)}) == Rc.OK
    assert target.exists()


def test_default_run_actually_invokes_subprocess_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`run=None` must REACH `subprocess.run`, not merely be importable beside it.

    Cold review P3 on b5404f11: the previous version of this test asserted
    `env_refresh.subprocess.run is subprocess.run`, which is true by virtue of
    the plain `import subprocess` at the top of the module and stays true no
    matter what the default path does. It could not fail. This one substitutes
    the real function and asserts the default branch called it, with the argv
    the module claims to send.
    """
    seen: list[list[str]] = []

    def spy(args: list[str], **_kwargs: object) -> _Proc:
        seen.append(args)
        return _Proc(json.dumps({"dirs": {"shims": "/spy/shims"}}))

    monkeypatch.setattr(env_refresh.subprocess, "run", spy)
    assert env_refresh.shims_dir() == Path("/spy/shims")
    assert seen == [["mise", "doctor", "--json"]]


def test_unwritable_target_is_not_run_not_a_traceback(tmp_path: Path) -> None:
    """Cold review P2 on b5404f11: an unwritable target must not raise.

    `shims_dir` already caught `OSError`; the write path did not, so a missing
    parent directory took the hook down with a raw traceback at exit 1 instead
    of the module's own `Rc` vocabulary.
    """
    missing_parent = tmp_path / "no-such-dir" / "env.sh"
    rc = env_refresh.apply({env_refresh.ENV_FILE_VAR: str(missing_parent)}, run=_mise_ok())
    assert rc == Rc.NOT_RUN
    assert not missing_parent.exists()


def test_read_only_target_is_not_run(tmp_path: Path) -> None:
    """The other half of P2: the file exists and cannot be appended to."""
    target = tmp_path / "env.sh"
    target.write_text('export A="1"\n', encoding="utf-8")
    target.chmod(0o444)
    try:
        rc = env_refresh.apply({env_refresh.ENV_FILE_VAR: str(target)}, run=_mise_ok())
    finally:
        target.chmod(0o644)
    assert rc == Rc.NOT_RUN
    assert env_refresh.MARKER not in target.read_text(encoding="utf-8")
