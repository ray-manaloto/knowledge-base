# Copyright (c) 2026 Raymond Manaloto
"""`kb-setup worktree-ready` — make a fresh git worktree usable (S0).

Every fixture here is a REAL git repository (a real donor "main checkout" with
real nested clones, a real linked worktree made with `git worktree add`). A
mocked `git`/`cp` would test the mock, and the whole point of this module is
that a real `git rev-parse HEAD` inside a real copied clone agrees with a real
pinned commit — only real objects can exhibit that.

`tests/test_skillopt_contract.py` and `tests/test_graphify_catalog.py` are
NOT modified here; their own end-to-end tests are the acceptance arm, run by
hand against a real throwaway worktree per the spec's verification sequence.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from kb_setup import worktree as wt
from kb_setup.result import Err, Ok, Rc


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _no_sync(_target: Path) -> None:
    """A fake `sync` for `prepare_existing`.

    The copy/pin logic is what these tests exercise, not a real
    `uv sync --locked`, which needs a real uv project the bare-git fixture
    below deliberately does not build.
    """
    return


def _init_clone(path: Path, *, commit_message: str = "fixture") -> str:
    """A real one-commit repo at `path`. Returns its HEAD commit."""
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.invalid")
    _git(path, "config", "user.name", "t")
    (path / "marker.txt").write_text("fixture\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", commit_message)
    return _git(path, "rev-parse", "HEAD")


@pytest.fixture
def donor_and_target(tmp_path: Path) -> tuple[Path, Path]:
    """A real donor repo (the "main checkout") with a real linked worktree.

    The donor gets a full `sources/skillopt` and `sources/graphify` clone (each
    a real repo, pinned by a real manifest) plus `graphify-out/graph.json` +
    `graph-prose.json`. The worktree starts with NEITHER — exactly the
    "fresh worktree" state section 1 describes.
    """
    donor = tmp_path / "donor"
    donor.mkdir()
    _git(donor, "init", "-q", "-b", "main")
    _git(donor, "config", "user.email", "t@example.invalid")
    _git(donor, "config", "user.name", "t")
    (donor / "README.md").write_text("donor\n", encoding="utf-8")
    _git(donor, "add", "-A")
    _git(donor, "commit", "-q", "-m", "init")

    target = tmp_path / "wt"
    _git(donor, "worktree", "add", "-b", "feat", str(target))

    (target / "sources").mkdir(parents=True, exist_ok=True)
    for name in wt.REQUIRED_CLONES:
        clone = donor / "sources" / name
        commit = _init_clone(clone)
        (donor / "sources" / f"{name}.manifest").write_text(
            f"url = https://example.invalid/{name}\nref = main\ncommit = {commit}\n",
            encoding="utf-8",
        )
        # Every worktree already tracks its own copy of the manifest via git —
        # simulate that by writing the identical manifest into the target too.
        (target / "sources" / f"{name}.manifest").write_text(
            (donor / "sources" / f"{name}.manifest").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    (donor / "graphify-out").mkdir()
    (donor / "graphify-out" / "graph.json").write_text('{"nodes": []}\n', encoding="utf-8")
    (donor / "graphify-out" / "graph-prose.json").write_text('{"nodes": []}\n', encoding="utf-8")

    return donor, target


def test_prepares_a_fresh_worktree(donor_and_target: tuple[Path, Path]) -> None:
    donor, target = donor_and_target
    result = wt.prepare_existing(target, sync=_no_sync)
    assert isinstance(result, Ok), getattr(result, "message", result)
    report = result.value
    assert report.target == str(target.resolve())
    assert report.donor == str(donor.resolve())
    assert report.donor_graph != "absent"

    statuses = {item.name: item.status.value for item in report.items}
    for name in wt.REQUIRED_CLONES:
        assert statuses[f"sources/{name}"] == "created"
    for rel in wt.REQUIRED_GRAPH_FILES:
        assert statuses[rel] == "created"


def test_copied_clones_are_real_directories_not_symlinks(
    donor_and_target: tuple[Path, Path],
) -> None:
    """Acceptance criterion 6: `is_dir() and not is_symlink()` on each copy."""
    _, target = donor_and_target
    result = wt.prepare_existing(target, sync=_no_sync)
    assert isinstance(result, Ok)
    for name in wt.REQUIRED_CLONES:
        copy = target / "sources" / name
        assert copy.is_dir()
        assert not copy.is_symlink()
        assert (copy / ".git").exists()


def test_copied_clone_head_matches_the_pin(donor_and_target: tuple[Path, Path]) -> None:
    _, target = donor_and_target
    result = wt.prepare_existing(target, sync=_no_sync)
    assert isinstance(result, Ok)
    for name in wt.REQUIRED_CLONES:
        pin = wt._pinned_commit(target, name)
        assert pin is not None
        assert wt._rev_parse(target / "sources" / name) == pin


def test_never_writes_inside_the_donor(donor_and_target: tuple[Path, Path]) -> None:
    """Acceptance criterion 3: write inside the COPY, show the donor untouched."""
    donor, target = donor_and_target
    result = wt.prepare_existing(target, sync=_no_sync)
    assert isinstance(result, Ok)

    name = wt.REQUIRED_CLONES[0]
    marker = target / "sources" / name / "written-by-test.txt"
    marker.write_text("only in the copy\n", encoding="utf-8")

    assert marker.is_file()
    assert not (donor / "sources" / name / "written-by-test.txt").exists()


def test_rerun_is_idempotent(donor_and_target: tuple[Path, Path]) -> None:
    """Acceptance criterion 4: a second run reports already-present, changes nothing."""
    _, target = donor_and_target
    first = wt.prepare_existing(target, sync=_no_sync)
    assert isinstance(first, Ok)

    second = wt.prepare_existing(target, sync=_no_sync)
    assert isinstance(second, Ok)
    statuses = {item.name: item.status.value for item in second.value.items}
    for name in wt.REQUIRED_CLONES:
        assert statuses[f"sources/{name}"] == "already-present"
    for rel in wt.REQUIRED_GRAPH_FILES:
        assert statuses[rel] == "already-present"


def test_nothing_examined_refuses_naming_counts(tmp_path: Path) -> None:
    """Acceptance criterion 5: an empty donor -> Rc.NOT_RUN naming the counts."""
    donor = tmp_path / "donor"
    donor.mkdir()
    _git(donor, "init", "-q", "-b", "main")
    _git(donor, "config", "user.email", "t@example.invalid")
    _git(donor, "config", "user.name", "t")
    (donor / "README.md").write_text("empty donor\n", encoding="utf-8")
    _git(donor, "add", "-A")
    _git(donor, "commit", "-q", "-m", "init")
    target = tmp_path / "wt"
    _git(donor, "worktree", "add", "-b", "feat", str(target))

    result = wt.prepare_existing(target)
    assert isinstance(result, Err)
    assert result.rc == Rc.NOT_RUN
    assert "skillopt" in result.message
    assert "graphify" in result.message


def test_refuses_the_main_checkout(donor_and_target: tuple[Path, Path]) -> None:
    """Nothing to prepare in the donor itself — Rc.BAD_REQUEST, not NOT_RUN."""
    donor, _ = donor_and_target
    result = wt.prepare_existing(donor)
    assert isinstance(result, Err)
    assert result.rc == Rc.BAD_REQUEST


def test_refuses_an_unregistered_path(tmp_path: Path) -> None:
    stray = tmp_path / "not-a-worktree"
    stray.mkdir()
    result = wt.prepare_existing(stray)
    assert isinstance(result, Err)
    assert result.rc == Rc.BAD_REQUEST


def test_refuses_when_an_existing_clone_disagrees_with_the_pin(
    donor_and_target: tuple[Path, Path],
) -> None:
    """A pre-existing but WRONG-HEAD clone in the target is not silently trusted."""
    _, target = donor_and_target
    name = wt.REQUIRED_CLONES[0]
    wrong = target / "sources" / name
    _init_clone(wrong, commit_message="wrong head entirely")

    result = wt.prepare_existing(target)
    assert isinstance(result, Err)
    assert result.rc == Rc.NOT_RUN
    assert "HEAD" in result.message


def test_best_mount_type_matches_the_longest_mountpoint() -> None:
    """Pure parser test: a nested mountpoint must win over its parent."""
    mount_output = (
        "/dev/disk3s1s1 on / (apfs, local, journaled)\n"
        "/dev/disk3s6 on /System/Volumes/VM (apfs, local, journaled, noexec)\n"
        "map auto_home on /home (autofs, automounted, nobrowse)\n"
    )
    assert wt._best_mount_type(mount_output, "/Users/t/repo") == "apfs"
    assert wt._best_mount_type(mount_output, "/System/Volumes/VM/x") == "apfs"
    assert wt._best_mount_type(mount_output, "/home/t") == "autofs"


def test_best_mount_type_reports_nothing_for_no_match() -> None:
    assert wt._best_mount_type("garbage\nnot a mount line\n", "/no/such/mount") == ""


def test_parse_rejects_unknown_flag() -> None:
    result = wt.parse(["--nope"])
    assert isinstance(result, Err)
    assert result.rc == Rc.BAD_REQUEST


def test_parse_requires_a_value_for_target() -> None:
    result = wt.parse(["--target"])
    assert isinstance(result, Err)
    assert result.rc == Rc.BAD_REQUEST


def test_parse_defaults_target_to_none() -> None:
    result = wt.parse([])
    assert isinstance(result, Ok)
    assert result.value is None


def test_main_defaults_target_to_repo_root(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    _, target = donor_and_target
    assert wt.main(target, []) == int(Rc.OK)


def test_main_refuses_main_checkout_as_bad_request(donor_and_target: tuple[Path, Path]) -> None:
    donor, _ = donor_and_target
    assert wt.main(donor, []) == int(Rc.BAD_REQUEST)


def test_main_honours_explicit_target_flag(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    donor, target = donor_and_target
    assert wt.main(donor, ["--target", str(target)]) == int(Rc.OK)


def test_a_donor_that_moved_mid_copy_refuses_and_removes_the_torn_copy(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The torn-copy branch, armed.

    `/bin/cp -c -R` can observe a clone while `kb-build` or `kb-update` is
    mutating it. The copy then has a HEAD the target's manifest does not pin —
    and it fails the very end-to-end test this module exists to fix,
    INTERMITTENTLY, so it reads as flake rather than as a missing check.

    This test exists because a mutation arm found the branch UNCOVERED. Every
    other fixture here builds a donor whose clone HEAD already equals the pin,
    so the comparison was true in every direction and severing it changed
    nothing. Advancing the donor past the target's pin is what makes the
    branch reachable — the same shape as a donor moving mid-copy.
    """
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    donor, target = donor_and_target
    name = wt.REQUIRED_CLONES[0]

    moved = donor / "sources" / name
    (moved / "marker.txt").write_text("the donor moved\n", encoding="utf-8")
    _git(moved, "add", "-A")
    _git(moved, "commit", "-q", "-m", "donor advanced past the target's pin")

    result = wt.prepare_existing(target)

    assert isinstance(result, Err)
    assert result.rc == Rc.NOT_RUN
    assert "moved during the copy" in result.message
    assert not (target / "sources" / name).exists(), (
        "the torn copy must be removed, not left in place for a later run to "
        "report as already-present"
    )
