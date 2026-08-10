# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.launch` — the verified Claude Code launcher.

Every check here is armed in BOTH directions. A launcher that cannot refuse is
the same defect as a gate that cannot fail, and this one exists precisely
because the previous shell version could not refuse: it launched sessions whose
`graphify` was the wrong version, silently.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from kb_setup import launch
from kb_setup.result import Err, Ok, Rc, Result, exit_code

_SHIM = "/home/u/.local/share/mise/shims/graphify"
_INSTALL = "/home/u/.local/share/mise/installs/pipx-graphifyy/0.9.25/bin/graphify"

_DIRTY_PATH = os.pathsep.join(
    [
        "/usr/bin",
        "/home/u/.local/share/mise/installs/pipx-graphifyy/0.9.25/bin",
        "/home/u/.local/share/mise/shims",
        "/home/u/.local/share/mise/installs/npm-renovate/43.0.0/bin",
    ]
)


def _which(mapping: dict[str, str | None]) -> Callable[[str, str], str | None]:
    return lambda tool, _path: mapping.get(tool, f"/usr/bin/{tool}")


def _probes(mapping: dict[str, str | None], version: str | None = "0.9.27") -> launch.Probes:
    return launch.Probes(which=_which(mapping), version_of=lambda _b: version)


def _pinned_repo(tmp_path: Path, version: str = "0.9.27") -> Path:
    (tmp_path / "mise.toml").write_text(
        f'[tools]\n"pipx:graphifyy" = {{ version = "{version}", extras = ["all"] }}\n',
        encoding="utf-8",
    )
    return tmp_path


# --- clean_path ---------------------------------------------------------------


def test_every_install_dir_is_dropped_and_order_is_kept() -> None:
    """The shims survive; every per-version bin goes, not just graphify's."""
    cleaned = launch.clean_path(_DIRTY_PATH).split(os.pathsep)
    assert cleaned == ["/usr/bin", "/home/u/.local/share/mise/shims"]


def test_a_clean_path_is_returned_unchanged() -> None:
    """CONTROL ARM: it strips a class, not everything mise-shaped."""
    clean = os.pathsep.join(["/usr/bin", "/home/u/.local/share/mise/shims"])
    assert launch.clean_path(clean) == clean


def test_stripping_is_version_agnostic() -> None:
    """The bug this replaces named a version, so it went inert on the next bump.

    Both a *newer* and an *older* install dir than any pin must go: the stale
    entry is frozen by MISE_ENV_CACHE and does not track the pin at all.
    """
    for version in ("0.9.25", "0.9.26", "0.9.27", "1.2.3"):
        path = f"/home/u/.local/share/mise/installs/pipx-graphifyy/{version}/bin"
        assert launch.clean_path(path) == ""


# --- session_path -------------------------------------------------------------
#
# The session's PATH is NOT this process's whenever mise sat between them, and
# under `mise run cc-doctor` it always does (install dirs injected for the task,
# then re-prepended by the `uv` shim). It is also not reconstructable from the
# environment: `__MISE_ORIG_PATH` is frozen at activate time and `__MISE_SHIM` is
# unset under `mise run`. So the session is IDENTIFIED, via Claude Code's own
# exported `CLAUDE_PID`, and its PATH read from the OS.


def test_the_session_is_found_through_claude_pid() -> None:
    """The session is identified, not reconstructed.

    CLAUDE_PID is an ordinary variable, so it survives every PATH-mangling layer
    intact — which is exactly why it can name a session those layers hid.
    """
    seen: list[str] = []
    assert (
        launch.session_path(
            {"PATH": _DIRTY_PATH, "CLAUDE_PID": "4242"},
            read_env_path=lambda pid: seen.append(pid) or "/session/bin",
        )
        == "/session/bin"
    )
    assert seen == ["4242"]


def test_our_own_path_is_never_the_fallback() -> None:
    """THE regression, stated as an absence.

    Falling back to `os.environ["PATH"]` is what the bug WAS: under the task it
    is mise's PATH, and judging it made the graphify check unable to report
    green. Not-readable must degrade to None (-> UNKNOWN), never to ours.
    """
    for env in ({"PATH": _DIRTY_PATH}, {"PATH": _DIRTY_PATH, "CLAUDE_PID": "not-a-pid"}):
        assert launch.session_path(env, read_env_path=lambda _p: None) is None
    # CLAUDE_PID present but the environment unreadable — measured: an
    # intermediate /bin/zsh yields no PATH= at all while its parent does.
    assert (
        launch.session_path(
            {"PATH": _DIRTY_PATH, "CLAUDE_PID": "4242"}, read_env_path=lambda _p: None
        )
        is None
    )


def test_real_drift_in_the_session_still_survives_the_selection() -> None:
    """This picks WHICH PATH to judge; it must not clean the one it picks.

    `clean_path` strips install dirs from whatever it is handed, which is why the
    doctor must never use it (#40). A session that genuinely has a shadowing
    install dir must still come back dirty.
    """
    got = launch.session_path(
        {"PATH": "/irrelevant", "CLAUDE_PID": "4242"}, read_env_path=lambda _p: _DIRTY_PATH
    )
    assert got == _DIRTY_PATH
    assert "installs" in got


def test_the_ps_parser_is_exact_on_a_process_whose_path_we_know() -> None:
    """CONTROL ARM for the macOS reader, run against ground truth: ourselves.

    A whitespace split would be wrong on any PATH containing a space, and this
    machine's really does (`…/Application Support/JetBrains/Toolbox/scripts`).
    Skipped on Linux, where `/proc/<pid>/environ` is NUL-separated and the regex
    is never reached.
    """
    if Path("/proc").is_dir() or shutil.which("ps") is None:
        pytest.skip("macOS-only: Linux reads /proc/<pid>/environ instead")
    assert launch._env_path_of(str(os.getpid())) == os.environ["PATH"]


def test_the_ps_parser_stops_at_the_next_variable_not_the_next_space() -> None:
    """The parse rule in isolation: a space-bearing entry must survive whole."""
    spaced = "/usr/bin:/opt/Application Support/bin"
    line = f"/some/cmd --flag HOME=/home/u PATH={spaced} SHELL=/bin/zsh"
    match = launch._PS_PATH_RE.search(line)
    assert match is not None
    assert match.group(1) == spaced


# --- pinned_version -----------------------------------------------------------


def test_the_pin_is_read_from_mise_toml(tmp_path: Path) -> None:
    assert launch.pinned_version(_pinned_repo(tmp_path, "0.9.27")) == "0.9.27"


def test_a_missing_config_or_tool_pins_nothing(tmp_path: Path) -> None:
    """CONTROL ARM: absence must read as "no pin", never as a false match."""
    assert launch.pinned_version(tmp_path) is None
    (tmp_path / "mise.toml").write_text("[tools]\n", encoding="utf-8")
    assert launch.pinned_version(tmp_path) is None


# --- preflight ----------------------------------------------------------------


def _check(
    tmp_path: Path, *, probes: launch.Probes | None = None, need_tmux: bool = True
) -> launch.Preflight:
    """Preflight a sound fixture, with one dimension overridable per test.

    Explicitly typed rather than `**kwargs: object`: that shape could only reach
    `preflight` behind an inline typing suppression, which this repo rejects
    (`no_lint_skip`). Naming the two axes the tests actually vary is both honest
    and shorter.

    Note the checker is a substring match, so even *describing* a suppression by
    its literal spelling here would trip it — the same comment-survives-the-grep
    shape recorded in `feedback_forbid_tokens_substring_fragile`.
    """
    sibling = tmp_path / "sibling"
    sibling.mkdir(exist_ok=True)
    return launch.preflight(
        _pinned_repo(tmp_path),
        sibling,
        path=_DIRTY_PATH,
        probes=probes if probes is not None else _probes({"graphify": _SHIM}),
        need_tmux=need_tmux,
    )


def test_a_sound_environment_passes(tmp_path: Path) -> None:
    """The direction that must work, or every refusal below means nothing."""
    result = _check(tmp_path)
    assert result.ok, result.problems
    assert "installs" not in result.path


def test_a_version_mismatch_refuses(tmp_path: Path) -> None:
    """THE check this module exists for: built by one version, stamped another."""
    result = _check(tmp_path, probes=_probes({"graphify": _SHIM}, "0.9.25"))
    assert not result.ok
    assert any("0.9.25" in p and "0.9.27" in p for p in result.problems)


def test_resolving_to_an_install_dir_refuses_even_at_the_right_version(
    tmp_path: Path,
) -> None:
    """The subtle half — and why the check is TWO assertions, not one.

    An install dir holding today's correct version still refuses: it is frozen,
    so it will be silently wrong after the next bump. A launcher that only
    compared versions would pass here and rot.
    """
    result = _check(tmp_path, probes=_probes({"graphify": _INSTALL}))
    assert not result.ok
    assert any("not a mise shim" in p for p in result.problems)


def test_a_missing_sibling_refuses(tmp_path: Path) -> None:
    sibling = tmp_path / "nope"
    result = launch.preflight(
        _pinned_repo(tmp_path),
        sibling,
        path=_DIRTY_PATH,
        probes=_probes({"graphify": _SHIM}),
        need_tmux=False,
    )
    assert not result.ok
    assert any("sibling repo not found" in p for p in result.problems)


def test_missing_binaries_refuse(tmp_path: Path) -> None:
    """Claude and tmux are both required — and tmux only when it is needed."""
    no_claude = _check(tmp_path, probes=_probes({"graphify": _SHIM, "claude": None}))
    assert any("`claude` does not resolve" in p for p in no_claude.problems)

    no_tmux = _check(tmp_path, probes=_probes({"graphify": _SHIM, "tmux": None}))
    assert any("`tmux` does not resolve" in p for p in no_tmux.problems)

    inside = _check(tmp_path, probes=_probes({"graphify": _SHIM, "tmux": None}), need_tmux=False)
    assert inside.ok, inside.problems


def test_an_unpinned_repo_skips_the_version_check(tmp_path: Path) -> None:
    """No pin is not a mismatch. It must not manufacture a refusal.

    A REAL repo root that simply pins no graphify — hence the empty `mise.toml`.
    Without the file it would refuse for a different reason entirely (see
    :func:`test_a_root_without_mise_toml_refuses`), and this test would pass for
    the wrong reason.
    """
    (tmp_path / "mise.toml").write_text("[tools]\n", encoding="utf-8")
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    result = launch.preflight(
        tmp_path,
        sibling,
        path=_DIRTY_PATH,
        probes=_probes({"graphify": _SHIM}, None),
        need_tmux=False,
    )
    assert result.ok, result.problems


# --- launch_argv --------------------------------------------------------------


def test_the_tmux_form_does_not_try_to_inject_path(tmp_path: Path) -> None:
    """The `-e PATH=` injection is GONE, because it never did anything (#40).

    This is the unit half of that fix. It is an absence assertion on purpose: the
    behaviour it guards (`test_a_spawned_pane_inherits_the_callers_path` below)
    passes whether or not `-e` is present — the client's PATH wins either way —
    so only a structural check can stop the dead mechanism being re-added and
    re-believed.
    """
    argv = launch.launch_argv(tmp_path, tmp_path / "sib", session="kb", in_tmux=False)
    assert argv[0] == "tmux"
    assert "-e" not in argv
    assert not any(a.startswith("PATH=") for a in argv)
    assert argv[-5:] == ["claude", "--permission-mode", "auto", "--add-dir", str(tmp_path / "sib")]


@pytest.mark.skipif(shutil.which("tmux") is None, reason="needs a real tmux to observe a pane")
def test_a_spawned_pane_inherits_the_callers_path(tmp_path: Path) -> None:
    """The EFFECT, observed inside a real spawned session — not in the argv.

    The test this replaces asserted `-e` and `PATH=/clean/bin` appeared in the
    argv. They did, and the feature still did nothing: tmux discards the
    session-environment PATH and gives the pane the CLIENT's. That is a
    right-answer-wrong-reason test, and it shipped inside the module written to
    prevent exactly this class, so its replacement must observe the environment
    the pane actually runs with.

    Both arms run here:

    * the caller's PATH REACHES the pane — which is what makes `cc_main`'s
      `env={**os.environ, "PATH": cleaned}` the real mechanism;
    * an injected `-e PATH=` LOSES to it — which is why the launcher no longer
      pretends otherwise.

    Two deliberate deviations from the production argv, both required to observe
    anything: `-d` (an attaching session needs a tty pytest does not have) and a
    probe command in place of `claude`. The tmux flags under test are taken from
    `launch_argv` itself rather than restated, so a change there is not silently
    unobserved.
    """
    prefix = launch.launch_argv(tmp_path, tmp_path / "sib", session="unused", in_tmux=False)
    prefix = prefix[: prefix.index("claude")]

    def spawn(name: str, extra: list[str]) -> str:
        out = tmp_path / f"{name}.txt"
        argv = list(prefix)
        argv[argv.index("-s") + 1] = name
        argv[argv.index("-c") + 1] = str(tmp_path)
        argv.insert(argv.index("new-session") + 1, "-d")
        argv += [*extra, "/bin/sh", "-c", f'printf "%s" "$PATH" > {out}']
        subprocess.run(
            argv,
            check=True,
            timeout=60,
            env={**os.environ, "PATH": f"/SENTINEL_CLIENT/bin{os.pathsep}{os.environ['PATH']}"},
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not out.is_file():
            time.sleep(0.1)
        subprocess.run(["tmux", "kill-session", "-t", name], check=False, timeout=30)
        assert out.is_file(), f"pane never wrote {out}"
        return out.read_text(encoding="utf-8")

    # PID-scoped: `launch_argv` emits `-A`, which ATTACHES to a same-named
    # session instead of spawning one — so two concurrent runs would silently
    # share a session and the probe would read the wrong pane.
    tag = os.getpid()
    plain = spawn(f"kbprobe-plain-{tag}", [])
    assert "/SENTINEL_CLIENT/bin" in plain, "the caller's PATH must reach the pane"

    injected = spawn(f"kbprobe-injected-{tag}", ["-e", "PATH=/SENTINEL_INJECTED/bin"])
    assert "/SENTINEL_CLIENT/bin" in injected, "the client's PATH still wins"
    assert "/SENTINEL_INJECTED/bin" not in injected, (
        "if this ever fails, tmux changed and `-e PATH=` became viable — "
        "revisit the launcher docstring before celebrating"
    )


# --- shim_free ----------------------------------------------------------------

_MISE_TMUX = "/home/u/.local/share/mise/installs/tmux/latest/tmux"
_SHIM_TMUX = "/home/u/.local/share/mise/shims/tmux"


def test_a_mise_managed_tool_resolves_to_its_install_binary(tmp_path: Path) -> None:
    """`mise which` wins, because it names the version this repo pins.

    Not the first entry on an activated PATH — that may be the stale install dir
    mechanism 1 is about, and preferring it would make the launcher pick exactly
    the binary the rest of this module exists to distrust.
    """
    got = launch.shim_free(
        "tmux", repo_root=tmp_path, path=_DIRTY_PATH, lookup=lambda _t, _r: _MISE_TMUX
    )
    assert got == _MISE_TMUX


def test_a_shim_is_never_returned_while_a_real_binary_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE POINT. A shim re-prepends every install dir onto the cleaned PATH.

    Returning one would undo `clean_path` at the moment of launch — which is the
    defect this function was added for, and which every earlier version of this
    module shipped with.
    """
    monkeypatch.setattr(launch.shutil, "which", lambda _t, **_k: "/opt/bin/tmux")
    got = launch.shim_free(
        "tmux", repo_root=tmp_path, path=_DIRTY_PATH, lookup=lambda _t, _r: _SHIM_TMUX
    )
    assert got == "/opt/bin/tmux", "a shim from `mise which` must fall through to PATH"
    assert launch._SHIMS_SEGMENT not in got


def test_a_tool_mise_does_not_manage_falls_through_to_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM for the lookup order: `claude` is not a mise tool.

    `mise which claude` exits non-zero, which is not an error — without this
    fallback the launcher would resolve nothing for the one binary it must run.
    """
    monkeypatch.setattr(launch.shutil, "which", lambda _t, **_k: "/home/u/.local/bin/claude")
    got = launch.shim_free(
        "claude", repo_root=tmp_path, path=_DIRTY_PATH, lookup=lambda _t, _r: None
    )
    assert got == "/home/u/.local/bin/claude"


def test_an_unresolvable_tool_degrades_to_the_bare_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It must not raise, and must not return None.

    Refusing here would brick the launcher over a resolution the preflight has
    already checked and reported on properly. The bare name is what the shell
    would have done anyway.
    """
    monkeypatch.setattr(launch.shutil, "which", lambda _t, **_k: None)
    got = launch.shim_free("tmux", repo_root=tmp_path, path="", lookup=lambda _t, _r: None)
    assert got == "tmux"


def test_a_shim_is_still_returned_when_it_is_the_only_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Degradation, stated so it is a decision rather than an accident.

    A shim runs the right tool; it only re-pollutes PATH. Launching beats
    refusing, and `doctor` reports the consequence inside the session.
    """
    monkeypatch.setattr(launch.shutil, "which", lambda _t, **_k: _SHIM_TMUX)
    got = launch.shim_free(
        "tmux", repo_root=tmp_path, path=_DIRTY_PATH, lookup=lambda _t, _r: _SHIM_TMUX
    )
    assert got == _SHIM_TMUX


def test_the_resolved_binaries_reach_the_argv(tmp_path: Path) -> None:
    """Resolution is worthless if `launch_argv` still emits the bare names."""
    argv = launch.launch_argv(
        tmp_path,
        tmp_path / "sib",
        session="kb",
        in_tmux=False,
        binaries=launch.Binaries(tmux=_MISE_TMUX, claude="/home/u/.local/bin/claude"),
    )
    assert argv[0] == _MISE_TMUX
    assert "/home/u/.local/bin/claude" in argv
    assert "tmux" not in argv[:1], "the bare name must not survive resolution"


@pytest.mark.skipif(
    shutil.which("mise") is None or shutil.which("tmux") is None,
    reason="needs real mise + tmux to observe a pane's PATH",
)
def test_a_spawned_pane_gets_no_install_dirs_and_the_shim_form_proves_it_can(
    tmp_path: Path,
) -> None:
    """The fix, observed end-to-end — with the arm that shows the probe can fail.

    This is an ABSENCE assertion, and that is the whole lesson of the defect it
    guards: `test_a_spawned_pane_inherits_the_callers_path` asserts a sentinel
    ARRIVED, and it does arrive — a mise shim PREPENDS install dirs, it does not
    discard what was there. So a "did my value reach the pane?" test passes at
    installs=154 exactly as it does at installs=0, and could never have caught
    this. Only "and nothing else arrived in front of it" can.

    Both arms run against the same tmux, the same command, the same cleaned
    PATH — the ONLY difference is which tmux binary is invoked:

    * through the SHIM  -> install dirs come back (the pre-fix behaviour);
    * through `shim_free` -> they do not.

    Without the first arm this test would pass on a machine where nothing ever
    polluted PATH, i.e. it would be a check that cannot fail.
    """
    shim_tmux = Path.home() / ".local/share/mise/shims/tmux"
    if not shim_tmux.is_file():
        pytest.skip("no mise shim for tmux on this host")

    cleaned = launch.clean_path(os.environ["PATH"])
    assert "/mise/installs/" not in cleaned, "the cleaned PATH is the fixture; it must be clean"

    def pane_path(tmux_bin: str, name: str) -> str:
        out = tmp_path / f"{name}.txt"
        argv = [
            tmux_bin, "new-session", "-d", "-s", name, "-c", str(tmp_path),
            "/bin/sh", "-c", f'printf "%s" "$PATH" > {out}',
        ]  # fmt: skip
        subprocess.run(argv, check=True, timeout=60, env={**os.environ, "PATH": cleaned})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not out.is_file():
            time.sleep(0.1)
        subprocess.run([tmux_bin, "kill-session", "-t", name], check=False, timeout=30)
        assert out.is_file(), f"pane never wrote {out}"
        return out.read_text(encoding="utf-8")

    tag = os.getpid()

    # FAIL ARM: the pre-fix path. A shim re-enters mise, which prepends the
    # install dirs straight back onto the PATH we just cleaned.
    via_shim = pane_path(str(shim_tmux), f"kbshim-{tag}")
    assert "/mise/installs/" in via_shim, (
        "the shim no longer re-injects install dirs — if this fails, mise "
        "changed and `shim_free` may be obsolete; re-measure before deleting it"
    )

    # PASS ARM: the fix.
    resolved = launch.shim_free("tmux", repo_root=Path.cwd(), path=os.environ["PATH"])
    assert launch._SHIMS_SEGMENT not in resolved
    via_resolved = pane_path(resolved, f"kbfree-{tag}")
    assert "/mise/installs/" not in via_resolved, (
        "the pane still inherited install dirs — a bare `graphify` in the "
        "launched session would resolve to a frozen install dir again"
    )


def test_inside_tmux_it_execs_claude_directly(tmp_path: Path) -> None:
    """CONTROL ARM: no nested server, and therefore no tmux flags at all."""
    argv = launch.launch_argv(tmp_path, tmp_path / "sib", session="kb", in_tmux=True)
    assert argv[0] == "claude"
    assert "tmux" not in argv
    # The flag rides on BOTH paths: Claude Code ignores a project-settings
    # `defaultMode: "auto"` as repo-controllable, so the flag is the only source
    # this repo can supply.
    assert "--permission-mode" in argv


def test_a_root_without_mise_toml_refuses(tmp_path: Path) -> None:
    """The silent-skip hole: a wrong root must refuse, not pass.

    `kb_setup.cli` derives repo_root from the CWD, and inside a mise task the CWD
    is wherever mise was invoked from — measured as the home directory, not the
    repo. Without this check a wrong root finds no pin, skips the version
    comparison, and launches: a pass for the one reason that should refuse
    hardest. The `--root` flag exists so callers never rely on the default.
    """
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    result = launch.preflight(
        tmp_path / "not-a-repo",
        sibling,
        path=_DIRTY_PATH,
        probes=_probes({"graphify": _SHIM}),
        need_tmux=False,
    )
    assert not result.ok
    assert any("not a repo root" in p for p in result.problems)


# --- doctor: the live-session sweep -------------------------------------------


def _doctor(
    tmp_path: Path,
    *,
    probes: launch.Probes | None = None,
    settings: str | None = None,
    sibling_exists: bool = True,
) -> dict[str, launch.Check]:
    repo = _pinned_repo(tmp_path)
    sibling = tmp_path / "sibling"
    if sibling_exists:
        sibling.mkdir(exist_ok=True)
    if settings is not None:
        (repo / ".claude").mkdir(exist_ok=True)
        (repo / ".claude" / "settings.json").write_text(settings, encoding="utf-8")
    results = launch.doctor(
        repo,
        sibling,
        path=_DIRTY_PATH,
        probes=probes if probes is not None else _probes({"graphify": _SHIM}),
    )
    return {c.name: c for c in results}


def test_the_doctor_judges_the_raw_path_not_a_cleaned_one(tmp_path: Path) -> None:
    """THE difference from `preflight`, and the reason the doctor exists.

    `preflight` cleans before judging — correctly, because it is about to hand a
    cleaned PATH to a child. If the doctor did the same it would be a check that
    cannot fail: it would strip the shadowing install dir and then report that no
    install dir is shadowing. #40 went unseen for exactly this shape of reason.

    Same `_DIRTY_PATH` as the preflight tests, so the two are directly
    comparable: preflight passes it, the doctor must not.
    """
    passing = _check(tmp_path, probes=_probes({"graphify": _INSTALL}))
    assert "installs" not in passing.path  # preflight cleaned it away

    got = _doctor(tmp_path, probes=_probes({"graphify": _INSTALL}))
    assert got["graphify"].status == launch.FAIL
    assert "an install dir ahead of the shims" in got["graphify"].detail
    # And it must say what this does and does not mean. A reader who takes it as
    # corpus drift will reach for a rebuild, which fixes nothing: every kb-* task
    # resolves through `mise which` and is unaffected.
    assert "NOT corpus correctness" in got["graphify"].detail


def test_an_unreadable_version_is_not_reported_as_a_mismatch(tmp_path: Path) -> None:
    """An unreadable version must not be printed as a mismatch against None.

    The two collapsed into one branch, so a binary that answered nothing was
    reported as having *reported* the string None against the pin — a version it
    never gave. Fabricating a reading is worse than admitting the probe failed,
    and `preflight` has always kept these separate.
    """
    got = _doctor(tmp_path, probes=_probes({"graphify": _SHIM}, None))
    assert got["graphify"].status == launch.FAIL
    assert "could not read a version" in got["graphify"].detail
    assert "None" not in got["graphify"].detail


def test_a_sound_session_reports_ok(tmp_path: Path) -> None:
    """CONTROL ARM: the direction that must pass, or every FAIL above is noise."""
    got = _doctor(tmp_path, settings='{"hooks": {}}')
    assert got["graphify"].status == launch.OK
    assert got["sibling"].status == launch.OK
    assert got["hook-paths"].status == launch.OK


def test_a_version_mismatch_on_the_shims_still_fails(tmp_path: Path) -> None:
    """Resolving correctly is not enough — the version must match the pin."""
    got = _doctor(tmp_path, probes=_probes({"graphify": _SHIM}, "0.9.25"))
    assert got["graphify"].status == launch.FAIL
    assert "0.9.25" in got["graphify"].detail


def test_a_missing_sibling_is_reported(tmp_path: Path) -> None:
    assert _doctor(tmp_path, sibling_exists=False)["sibling"].status == launch.FAIL


def test_an_absolute_home_path_in_a_hook_fails_with_its_line(tmp_path: Path) -> None:
    """The outage this check exists for: a hook nobody else's machine can run."""
    got = _doctor(tmp_path, settings='{\n  "hooks": "/Users/someone/bin/thing"\n}')
    assert got["hook-paths"].status == launch.FAIL
    assert "2" in got["hook-paths"].detail


def test_a_missing_settings_file_is_unknown_not_ok(tmp_path: Path) -> None:
    """CONTROL ARM: absence is "not asked", never "asked and fine"."""
    assert _doctor(tmp_path)["hook-paths"].status == launch.UNKNOWN


def test_the_two_session_only_facts_are_never_claimed(tmp_path: Path) -> None:
    """A subprocess cannot see a session's skills or permission mode.

    They are reported UNKNOWN with the reason rather than asserted. Claiming
    either would be the one-faced probe this repo keeps banning — and check 2 in
    particular passes one-sided while `--add-dir` is silently broken, which is
    why the detail text names both a KB-only and a dotfiles-only skill.
    """
    got = _doctor(tmp_path, settings="{}")
    assert got["skills"].status == launch.UNKNOWN
    assert got["permission-mode"].status == launch.UNKNOWN
    assert "kb-curator" in got["skills"].detail
    assert "pr-workflow" in got["skills"].detail


# --- doctor_main: the wiring the tests above cannot see -----------------------
#
# Every `_doctor` test injects `path=` and REAL probes are never used, so the one
# line that chooses which PATH to judge was covered by nothing. That is exactly
# where the defect lived: `doctor_main` passed `os.environ["PATH"]`, which under
# `mise run cc-doctor` is the `uv` shim's fabrication. These two drive the real
# entry point end to end, with real `shutil.which` over real files on disk.


def _graphify_at(directory: Path, version: str = "0.9.27") -> Path:
    """A runnable `graphify --version` so the REAL `_version_of` probe works."""
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / "graphify"
    binary.write_text(f'#!/bin/sh\necho "graphify {version}"\n', encoding="utf-8")
    binary.chmod(0o755)
    return binary


def _shim_and_install(tmp_path: Path) -> tuple[str, str]:
    """Return (session PATH, shim-fabricated PATH) over two real directories."""
    shims = tmp_path / "mise" / "shims"
    installs = tmp_path / "mise" / "installs" / "pipx-graphifyy" / "0.9.27" / "bin"
    _graphify_at(shims)
    _graphify_at(installs)
    return str(shims), os.pathsep.join([str(installs), str(shims)])


def _run_doctor_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    task_path: str,
    session: str | None,
    extra_argv: list[str] | None = None,
) -> int:
    """Drive the real entry point with both PATHs controlled.

    ``task_path`` is the mise-mangled PATH this process holds; ``session`` is
    what the OS reports for `CLAUDE_PID`.
    """
    repo = _pinned_repo(tmp_path)
    sibling = tmp_path / "sibling"
    sibling.mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", task_path)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(launch, "_env_path_of", lambda _pid: session)
    return launch.doctor_main(repo, ["--sibling", str(sibling), *(extra_argv or [])])


def test_doctor_main_judges_the_session_not_the_path_mise_handed_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE regression.

    A clean session must report clean even though THIS process holds a PATH with
    the install dir in front — which is what `mise run` plus the `uv` shim do,
    unconditionally, to every invocation of this task.
    """
    session, task_path = _shim_and_install(tmp_path)
    rc = _run_doctor_main(tmp_path, monkeypatch, task_path=task_path, session=session)
    assert rc == 0
    assert "via the shims" in capsys.readouterr().out


def test_doctor_main_still_fails_when_the_session_itself_is_dirty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTROL ARM: drift that is really in the session must still be caught.

    The session's own PATH carries the install dir here — the state `cc-fresh`
    exists for. If this passed, the fix would have replaced a check that could
    not pass with one that cannot fail.
    """
    _, task_path = _shim_and_install(tmp_path)
    rc = _run_doctor_main(tmp_path, monkeypatch, task_path=task_path, session=task_path)
    assert rc == 1
    assert "an install dir ahead of the shims" in capsys.readouterr().out


def test_doctor_main_reports_unknown_rather_than_judging_its_own_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unreadable session is "not checked", never a pass.

    And never a verdict on this process's PATH either.

    Falling back to `os.environ["PATH"]` is precisely the bug: the fallback value
    here is dirty, so a regression would surface as a FAIL. UNKNOWN must not fail
    the run either — an unreadable session is not a broken one.
    """
    _, task_path = _shim_and_install(tmp_path)
    rc = _run_doctor_main(tmp_path, monkeypatch, task_path=task_path, session=None)
    out = capsys.readouterr().out
    assert rc == 0
    assert "could not be read, so this was NOT checked" in out
    assert "an install dir ahead of the shims" not in out
    assert "via the shims" not in out


def test_an_explicit_path_argument_wins_over_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An explicit answer beats every inferred one.

    `--path "$PATH"` from the session's shell is exact and needs no process
    introspection, so it must beat both this process's PATH and the CLAUDE_PID
    read — including when the latter is unavailable.
    """
    session, task_path = _shim_and_install(tmp_path)
    rc = _run_doctor_main(
        tmp_path, monkeypatch, task_path=task_path, session=None, extra_argv=["--path", session]
    )
    assert rc == 0
    assert "via the shims" in capsys.readouterr().out


def _fresh_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, preflight_ok: bool
) -> tuple[int, list[list[str]]]:
    """Drive `cc_main --fresh` with a stubbed preflight; return rc + commands run."""
    ran: list[list[str]] = []
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setattr(
        launch,
        "preflight",
        lambda *_a, **_k: launch.Preflight(
            path="/clean/bin", problems=() if preflight_ok else ("sibling repo not found",)
        ),
    )
    # Stubbed so this test stays about ORDERING. Unstubbed, `cc_main` resolves
    # both binaries through `shim_free`, which shells out to `mise which` and
    # would put two more commands in `ran` — noise that has its own tests below.
    # The sentinel paths are deliberately shim-free: asserting the kill and the
    # launch use the SAME resolved binary is part of the contract.
    monkeypatch.setattr(launch, "shim_free", lambda tool, **_k: f"/abs/{tool}")
    monkeypatch.setattr(
        launch.subprocess,
        "run",
        lambda cmd, **_k: (
            ran.append(list(cmd)) or subprocess.CompletedProcess(args=cmd, returncode=0)
        ),
    )
    sibling = tmp_path / "sibling"
    sibling.mkdir(exist_ok=True)
    rc = launch.cc_main(_pinned_repo(tmp_path), ["--fresh", "--sibling", str(sibling)])
    return rc, ran


def test_fresh_does_not_kill_the_server_when_preflight_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE ordering bug: it killed every session BEFORE validating anything.

    A missing sibling, an unresolvable `claude`, a wrong `--root` or a version
    mismatch would each destroy every tmux session on the host — including
    unrelated projects — and then launch nothing. A repair step that runs before
    its own validation is not a repair; it is an outage with no rollback.
    """
    rc, ran = _fresh_run(tmp_path, monkeypatch, preflight_ok=False)

    assert rc == 1
    assert ran == [], f"it ran {ran} despite refusing to launch"


def test_fresh_does_kill_the_server_once_preflight_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: the kill must still happen, and BEFORE the launch.

    Without this, the test above is satisfied by deleting the feature. The order
    matters as much as the fact: killing after launching would take down the
    session that was just created.
    """
    rc, ran = _fresh_run(tmp_path, monkeypatch, preflight_ok=True)

    assert rc == 0
    assert [c[:2] for c in ran] == [
        ["/abs/tmux", "kill-server"],
        ["/abs/tmux", "new-session"],
    ]


def test_fresh_refuses_inside_tmux(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--fresh` kills the server it would be running inside — refuse, don't try.

    Armed the other way by every other cc test: without `--fresh` the TMUX
    variable is simply the in-tmux launch path, not a refusal.
    """
    # Shaped like a real TMUX value (socket,pid,session) but rooted in tmp_path:
    # only its truthiness is read, and a literal /tmp path trips the temp-file rule.
    monkeypatch.setenv("TMUX", f"{tmp_path / 'tmux-sock'},1,0")
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    rc = launch.cc_main(_pinned_repo(tmp_path), ["--fresh", "--sibling", str(sibling)])
    assert rc == 2


# --- teammate transport, reported not enforced --------------------------------


def _settings(tmp_path: Path, teams: str | None) -> Path:
    d = tmp_path / ".claude"
    d.mkdir(exist_ok=True)
    env = {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": teams} if teams is not None else {}
    (d / "settings.json").write_text(json.dumps({"env": env}), encoding="utf-8")
    return tmp_path


def test_teams_enabled_reports_split_pane(tmp_path: Path) -> None:
    """The direction the queue design assumes."""
    note = launch.teammate_note(_settings(tmp_path, "1"), in_tmux=False)
    assert "enabled" in note
    assert "split-pane" in note


def test_teams_not_declared_says_so(tmp_path: Path) -> None:
    """CONTROL ARM, and the whole point: it must not look identical to enabled.

    A repo that does not enable agent teams gets NO team at all — the teammates
    the runbook assumes simply never exist. Silent before; stated now.
    """
    assert "DISABLED" in launch.teammate_note(_settings(tmp_path, None), in_tmux=False)
    assert "DISABLED" in launch.teammate_note(_settings(tmp_path, "0"), in_tmux=True)
    assert "DISABLED" in launch.teammate_note(tmp_path / "absent", in_tmux=False)


def test_a_corrupt_settings_file_reports_disabled_rather_than_raising(
    tmp_path: Path,
) -> None:
    """It is advisory — it must never take the launch down."""
    d = tmp_path / ".claude"
    d.mkdir()
    (d / "settings.json").write_text("{not json", encoding="utf-8")
    assert "DISABLED" in launch.teammate_note(tmp_path, in_tmux=False)


# --- §2 R5 tranche 4: the `Result` boundary ---------------------------------
#
# Every exit-code assertion above is unchanged and is the regression arm proving
# the split changed no behaviour. What is NEW is that "a FAILED check" and "the
# request was refused" are now different TYPES — both were non-zero ints before,
# and `doctor_main`'s 1-vs-2 split is invisible to a test asserting `rc != 0`.


def _boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    task_path: str,
    session: str | None,
    extra_argv: list[str] | None = None,
) -> Result[list[launch.Check]]:
    """`check_doctor` driven exactly the way `_run_doctor_main` drives the renderer."""
    repo = _pinned_repo(tmp_path)
    sibling = tmp_path / "sibling"
    sibling.mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", task_path)
    monkeypatch.setenv("CLAUDE_PID", "4242")
    monkeypatch.setattr(launch, "_env_path_of", lambda _pid: session)
    return launch.check_doctor(repo, ["--sibling", str(sibling), *(extra_argv or [])])


def test_doctor_boundary_a_failed_check_is_ok_with_rc_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A doctor that ran and found a broken environment SUCCEEDED — recipe rule 1.

    If someone "simplifies" this to an `Err`, `test_doctor_main_still_fails_when_
    the_session_itself_is_dirty` stays green only by accident: `Err` defaults to
    rc 2 and that test asserts 1, so the failure would be a changed integer on
    one path. This asserts the TYPE, which is the thing the integer cannot say.
    """
    _, task_path = _shim_and_install(tmp_path)

    result = _boundary(tmp_path, monkeypatch, task_path=task_path, session=task_path)

    assert isinstance(result, Ok)
    assert result.rc is Rc.FINDINGS
    assert any(c.status == launch.FAIL for c in result.value)


def test_doctor_boundary_clean_session_is_ok_with_rc_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTROL ARM: `Ok` is reachable with BOTH rcs, so the test above discriminates."""
    session, task_path = _shim_and_install(tmp_path)

    result = _boundary(tmp_path, monkeypatch, task_path=task_path, session=session)

    assert isinstance(result, Ok)
    assert result.rc is Rc.OK


def test_doctor_boundary_unknown_rows_do_not_become_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable session is "not checked", and the rc must not call it broken.

    This is the false-RED twin of the false-green this repo's doctrine is about,
    and the split makes it checkable: the UNKNOWN rows are IN the returned value
    while the rc stays `OK`, so a caller can see both facts without one erasing
    the other.
    """
    _, task_path = _shim_and_install(tmp_path)

    result = _boundary(tmp_path, monkeypatch, task_path=task_path, session=None)

    assert isinstance(result, Ok)
    assert result.rc is Rc.OK
    assert any(c.status == launch.UNKNOWN for c in result.value)


def test_doctor_boundary_a_bad_request_is_an_err(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refusing to run is a THIRD state, and the type now says so.

    The int has been 2 all along. What no test could see is whether that 2
    arrived as an `Ok` — asserting the doctor ran and reported something — or as
    an `Err`, which is the truth. A typo'd flag is not an environment verdict.
    """
    _, task_path = _shim_and_install(tmp_path)

    result = _boundary(
        tmp_path, monkeypatch, task_path=task_path, session=None, extra_argv=["--nope"]
    )

    assert isinstance(result, Err)
    assert result.rc is Rc.BAD_REQUEST
    assert "--nope" in result.message


def test_doctor_boundary_prints_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Rendering belongs to `doctor_main`; the boundary only returns.

    Armed on the FAILING path — a clean run printing nothing would also be true
    of a boundary that merely forgot to report its failures.
    """
    _, task_path = _shim_and_install(tmp_path)

    _boundary(tmp_path, monkeypatch, task_path=task_path, session=task_path)
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""


def test_doctor_int_wrapper_is_exit_code_of_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The equivalence that makes the split safe — catches a renderer computing its own rc."""
    _, task_path = _shim_and_install(tmp_path)

    rc_main = _run_doctor_main(tmp_path, monkeypatch, task_path=task_path, session=task_path)
    rc_boundary = exit_code(
        _boundary(tmp_path, monkeypatch, task_path=task_path, session=task_path)
    )

    assert rc_main == rc_boundary == int(Rc.FINDINGS)
