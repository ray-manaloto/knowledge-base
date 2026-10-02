# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.currency — a binaryless Python LIBRARY as a currency target (#826).

A `python_package` tool used to be assumed to ship an executable: resolution
looked for `<project>/.venv/bin/<binary>` and reported DRIFT forever when a
library (githubkit) installs none. `library = true` reads the installed
distribution's metadata instead. Every test pairs with its opposite arm: an
installed library at the pin is OK, at another version is DRIFT, absent is DRIFT,
and a NON-library python_package with no executable is still DRIFT.
"""

import json
from pathlib import Path

import pytest
from kb_setup.currency import config, sync

_PIN = '[project]\nname = "probe"\nversion = "0"\ndependencies = ["githubkit==0.13.4"]\n'


def _write_config(root: Path, body: str) -> None:
    (root / "currency.toml").write_text(body, encoding="utf-8")


def _library_repo(tmp_path: Path, *, installed: str | None, pin: str = _PIN) -> Path:
    """A repo pinning githubkit, with `installed` in its venv (None = absent)."""
    (tmp_path / "pyproject.toml").write_text(pin, encoding="utf-8")
    _write_config(
        tmp_path,
        '[tool.githubkit]\npython_package = "githubkit"\nlibrary = true\n'
        'pypi = "githubkit"\ngithub = "yanyongyu/githubkit"\n',
    )
    site = tmp_path / ".venv" / "lib" / "python3.14" / "site-packages"
    site.mkdir(parents=True)
    if installed is not None:
        dist = site / f"githubkit-{installed}.dist-info"
        dist.mkdir()
        (dist / "METADATA").write_text(
            f"Metadata-Version: 2.4\nName: githubkit\nVersion: {installed}\n",
            encoding="utf-8",
        )
    return tmp_path


def _spec(root: Path) -> config.ToolSpec:
    (spec,) = config.load(root)
    return spec


def _finding(status: sync.SyncStatus, check: str) -> sync.Finding:
    return next(f for f in status.findings if f.check == check)


# ---------------------------------------------------------------- config ----


def test_library_flag_parses_and_leaves_binary_empty(tmp_path) -> None:
    spec = _spec(_library_repo(tmp_path, installed="0.13.4"))
    assert spec.library is True
    # Empty, not the tool's name: a library has no executable to default to.
    assert spec.binary == ""


def test_non_library_python_package_still_defaults_binary_to_its_name(tmp_path) -> None:
    _write_config(tmp_path, '[tool.graphify]\npython_package = "graphifyy"\n')
    spec = _spec(tmp_path)
    assert spec.library is False
    assert spec.binary == "graphify"


def test_library_without_python_package_is_refused(tmp_path) -> None:
    _write_config(tmp_path, '[tool.githubkit]\nmise_key = "pipx:githubkit"\nlibrary = true\n')
    with pytest.raises(ValueError, match="library"):
        config.load(tmp_path)


def test_library_declaring_a_binary_is_refused(tmp_path) -> None:
    _write_config(
        tmp_path,
        '[tool.githubkit]\npython_package = "githubkit"\nlibrary = true\nbinary = "gk"\n',
    )
    with pytest.raises(ValueError, match="binary"):
        config.load(tmp_path)


# ------------------------------------------------------------ resolution ----


def test_installed_library_at_the_pin_is_in_sync(tmp_path) -> None:
    root = _library_repo(tmp_path, installed="0.13.4")
    status = sync.check_sync(root, _spec(root))
    resolution = _finding(status, "resolution")
    assert resolution.status == sync.OK, resolution.detail
    assert status.resolved == "0.13.4"
    assert status.ok
    # The founding defect: no `.venv/bin/githubkit` exists, and that is fine.
    assert not (root / ".venv" / "bin" / "githubkit").exists()


def test_installed_library_at_another_version_is_drift(tmp_path) -> None:
    root = _library_repo(tmp_path, installed="0.13.3")
    status = sync.check_sync(root, _spec(root))
    resolution = _finding(status, "resolution")
    assert resolution.status == sync.DRIFT
    assert "0.13.3" in resolution.detail
    assert "0.13.4" in resolution.detail
    assert status.resolved == "0.13.3"


def test_library_absent_from_the_venv_is_drift_not_ok(tmp_path) -> None:
    root = _library_repo(tmp_path, installed=None)
    resolution = _finding(sync.check_sync(root, _spec(root)), "resolution")
    assert resolution.status == sync.DRIFT
    assert "githubkit" in resolution.detail
    assert "mise deps" in resolution.detail


def test_library_with_no_venv_at_all_is_drift(tmp_path) -> None:
    root = _library_repo(tmp_path, installed=None)
    for path in sorted((root / ".venv").rglob("*"), reverse=True):
        path.rmdir()
    (root / ".venv").rmdir()
    resolution = _finding(sync.check_sync(root, _spec(root)), "resolution")
    assert resolution.status == sync.DRIFT


def test_library_detail_carries_no_absolute_host_path(tmp_path) -> None:
    root = _library_repo(tmp_path, installed=None)
    detail = _finding(sync.check_sync(root, _spec(root)), "resolution").detail
    assert str(root) not in detail


def test_non_library_python_package_without_executable_is_still_drift(tmp_path) -> None:
    """Control arm: the executable requirement is relaxed ONLY for `library`."""
    root = _library_repo(tmp_path, installed="0.13.4")
    _write_config(
        root,
        '[tool.githubkit]\npython_package = "githubkit"\npypi = "githubkit"\n',
    )
    resolution = _finding(sync.check_sync(root, _spec(root)), "resolution")
    assert resolution.status == sync.DRIFT
    assert ".venv/bin/githubkit" in resolution.detail


def test_library_in_a_nested_project_reads_that_projects_venv(tmp_path) -> None:
    nested = tmp_path / "python"
    nested.mkdir()
    _library_repo(nested, installed="0.13.4")
    spec = config.ToolSpec(
        name="githubkit",
        python_package="githubkit",
        python_project_dir="python",
        library=True,
    )
    resolution = _finding(sync.check_sync(tmp_path, spec), "resolution")
    assert resolution.status == sync.OK, resolution.detail


def test_git_pinned_library_resolves_through_direct_url_without_an_executable(
    tmp_path,
) -> None:
    revision = "93bdf3d770b99128daf35278218e5a666fe392f3"
    pin = (
        "[project]\ndependencies = ["
        f'"githubkit @ git+https://github.com/yanyongyu/githubkit@{revision}"'
        "]\n"
    )
    root = _library_repo(tmp_path, installed="0.13.4", pin=pin)
    dist = next((root / ".venv").rglob("githubkit-*.dist-info"))
    spec = _spec(root)

    resolution = _finding(sync.check_sync(root, spec), "resolution")
    assert resolution.status == sync.DRIFT  # no direct_url.json yet

    (dist / "direct_url.json").write_text(
        json.dumps({"url": "x", "vcs_info": {"vcs": "git", "commit_id": revision}}),
        encoding="utf-8",
    )
    resolution = _finding(sync.check_sync(root, spec), "resolution")
    assert resolution.status == sync.OK, resolution.detail


def test_two_installed_versions_of_one_library_is_drift_not_a_guess(tmp_path) -> None:
    root = _library_repo(tmp_path, installed="0.13.4")
    site = next((root / ".venv").rglob("site-packages"))
    stale = site / "githubkit-0.13.3.dist-info"
    stale.mkdir()
    (stale / "METADATA").write_text(
        "Metadata-Version: 2.4\nName: githubkit\nVersion: 0.13.3\n", encoding="utf-8"
    )
    resolution = _finding(sync.check_sync(root, _spec(root)), "resolution")
    assert resolution.status == sync.DRIFT
    assert "conflicting" in resolution.detail


# ------------------------------------------- the false alarm names its fix ----
#
# `library = true` is opt-in, so a consumer that bumps the engine but never adds
# the line keeps the old red. That red used to say "run `mise deps`" — a remedy
# that can never work for a package that ships no executable. These pin the
# hint, and its two opposite arms where the hint must NOT appear.


def test_undeclared_library_drift_names_library_true_as_the_fix(tmp_path) -> None:
    root = _library_repo(tmp_path, installed="0.13.4")
    _write_config(root, '[tool.githubkit]\npython_package = "githubkit"\n')
    resolution = _finding(sync.check_sync(root, _spec(root)), "resolution")
    assert resolution.status == sync.DRIFT
    assert "library = true" in resolution.detail
    assert "mise deps" not in resolution.detail


def test_installed_cli_package_missing_its_executable_gets_no_library_hint(tmp_path) -> None:
    """A package that DOES declare a console script is a broken install, not a library."""
    root = _library_repo(tmp_path, installed="0.13.4")
    dist = next((root / ".venv").rglob("githubkit-*.dist-info"))
    (dist / "entry_points.txt").write_text(
        "[console_scripts]\ngithubkit = githubkit.cli:main\n", encoding="utf-8"
    )
    _write_config(root, '[tool.githubkit]\npython_package = "githubkit"\n')
    resolution = _finding(sync.check_sync(root, _spec(root)), "resolution")
    assert resolution.status == sync.DRIFT
    assert "library = true" not in resolution.detail
    assert "mise deps" in resolution.detail


def test_uninstalled_package_missing_its_executable_gets_no_library_hint(tmp_path) -> None:
    root = _library_repo(tmp_path, installed=None)
    _write_config(root, '[tool.githubkit]\npython_package = "githubkit"\n')
    resolution = _finding(sync.check_sync(root, _spec(root)), "resolution")
    assert "library = true" not in resolution.detail
    assert "mise deps" in resolution.detail
    assert str(root) not in resolution.detail
