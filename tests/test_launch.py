"""Tests for `kb_setup.launch` — the verified Claude Code launcher.

Every check here is armed in BOTH directions. A launcher that cannot refuse is
the same defect as a gate that cannot fail, and this one exists precisely
because the previous shell version could not refuse: it launched sessions whose
`graphify` was the wrong version, silently.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from kb_setup import launch

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


def test_the_tmux_form_injects_the_verified_path(tmp_path: Path) -> None:
    """Load-bearing: tmux hands a new session the SERVER's env, not the caller's.

    Without `-e PATH=...` the verified PATH is discarded on the way in and the
    session inherits whatever the server started with — which is the exact
    failure the preflight exists to catch, reintroduced one layer down.
    """
    argv = launch.launch_argv(
        tmp_path, tmp_path / "sib", path="/clean/bin", session="kb", in_tmux=False
    )
    assert argv[0] == "tmux"
    assert "-e" in argv
    assert "PATH=/clean/bin" in argv
    assert argv[-3:] == ["claude", "--add-dir", str(tmp_path / "sib")]


def test_inside_tmux_it_execs_claude_directly(tmp_path: Path) -> None:
    """CONTROL ARM: no nested server, and therefore no -e to inject."""
    argv = launch.launch_argv(
        tmp_path, tmp_path / "sib", path="/clean/bin", session="kb", in_tmux=True
    )
    assert argv[0] == "claude"
    assert "tmux" not in argv


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
