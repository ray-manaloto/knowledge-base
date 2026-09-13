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

import os
import shutil
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


def test_clonefile_refuses_an_existing_destination(tmp_path: Path) -> None:
    """EEXIST, and it is load-bearing rather than incidental.

    The `/bin/cp -R` form this replaced copied INTO an existing directory,
    producing `dst/<name>/`; the pin check then read the enclosing repository
    and the cleanup deleted a directory the module never created. The syscall
    refusing outright is what makes that unreachable, so it is armed here
    rather than assumed.
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.txt").write_text("x\n", encoding="utf-8")
    dst = tmp_path / "dst"
    dst.mkdir()

    failure = wt._clonefile(src, dst)

    assert failure, "cloning onto an existing path must fail, not merge into it"
    assert "EEXIST" in failure
    assert not (dst / "src").exists(), "nothing may be copied INTO the existing directory"


def test_clonefile_succeeds_and_recurses_into_dot_git(tmp_path: Path) -> None:
    """The control arm for the test above, plus the `.git` claim.

    `graphify_catalog` needs `clone/.git` to exist in the copy, so a mechanism
    that skipped dotfiles would pass every other test here and fail the one
    end-to-end test this module exists to fix.
    """
    src = tmp_path / "src"
    (src / ".git").mkdir(parents=True)
    (src / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    dst = tmp_path / "dst"

    assert wt._clonefile(src, dst) == ""
    assert (dst / ".git" / "HEAD").is_file()


def test_clonefile_refuses_a_missing_source(tmp_path: Path) -> None:
    failure = wt._clonefile(tmp_path / "nope", tmp_path / "dst")
    assert "ENOENT" in failure


def test_rev_parse_refuses_an_ancestors_answer(tmp_path: Path) -> None:
    """`git -C <path> rev-parse HEAD` WALKS UP — this must not accept that.

    Armed against the real failure: a plain directory nested inside a real
    repository. `git` answers with the enclosing repository's HEAD and exits
    0, so a caller comparing that to a pin gets a confident wrong answer about
    the wrong repository. The control arm below is the same call on a genuine
    clone root, which must still return its own HEAD.
    """
    repo = tmp_path / "repo"
    head = _init_clone(repo)
    nested = repo / "not-a-repo"
    nested.mkdir()

    assert wt._rev_parse(nested) == "", "an ancestor's HEAD is not this path's HEAD"
    assert wt._rev_parse(repo) == head, "control: a real clone root still answers"


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


def test_a_missing_required_clone_is_not_a_success(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A donor with the graph files but not the clones must NOT exit 0.

    `REQUIRED_CLONES` is named required. The first version refused only when
    clones AND graph files were all absent, so this case returned `Ok`, printed
    two `skipped` rows, and declared a worktree ready in which both end-to-end
    tests still fail. `skipped` is the right ROW; what was missing is that no
    skipped REQUIRED item reached the exit code.
    """
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    donor, target = donor_and_target
    shutil.rmtree(donor / "sources" / wt.REQUIRED_CLONES[0])

    result = wt.prepare_existing(target)

    assert isinstance(result, Err)
    assert result.rc == Rc.NOT_RUN
    assert wt.REQUIRED_CLONES[0] in result.message
    assert "kb-build" in result.message, "a refusal must name the remediation"


def test_an_existing_non_clone_directory_is_refused_not_deleted(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The destructive path, armed.

    An interrupted copy can leave `sources/<name>/` present without a usable
    `.git`, and the module can therefore manufacture its own precondition. The
    earlier version copied into that directory, misread the pin from the
    enclosing worktree, and then `rmtree`'d it — destroying a directory it had
    not created, while reporting a donor race that never happened.
    """
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    _, target = donor_and_target
    name = wt.REQUIRED_CLONES[0]
    squatter = target / "sources" / name
    squatter.mkdir(parents=True)
    (squatter / "IMPORTANT.txt").write_text("not ours to delete\n", encoding="utf-8")

    result = wt.prepare_existing(target)

    assert isinstance(result, Err)
    assert result.rc == Rc.BAD_REQUEST, "the request was wrong, not the world"
    assert (squatter / "IMPORTANT.txt").is_file(), "must not delete what it did not create"
    assert "moved during the copy" not in result.message, (
        "must not blame a race that did not happen"
    )


def test_a_graph_file_that_changed_size_mid_copy_is_removed(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Donor quiescence for the graph files, which had none.

    A clone is checked against its pin; a graph file has no pin, so the copy
    was accepted unconditionally — and `already-present` then certified a
    truncated file on every later run. Simulated by growing the donor file
    during the clone, which is what a concurrent `kb-build` does.
    """
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    _donor, target = donor_and_target
    rel = wt.REQUIRED_GRAPH_FILES[0]
    real_clonefile = wt._clonefile

    def _grow_the_donor_mid_copy(src: Path, dst: Path) -> str:
        failure = real_clonefile(src, dst)
        if str(src).endswith(rel):
            src.write_text('{"nodes": [1, 2, 3]}\n', encoding="utf-8")
        return failure

    monkeypatch.setattr(wt, "_clonefile", _grow_the_donor_mid_copy)

    result = wt.prepare_existing(target)

    assert isinstance(result, Err)
    assert result.rc == Rc.NOT_RUN
    assert "being written during the copy" in result.message
    assert not (target / rel).exists(), "the torn copy must not survive to be reported present"


def test_running_from_a_subdirectory_resolves_to_the_worktree_root(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A subdirectory is INSIDE a worktree; refusing it told the caller a falsehood."""
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    _, target = donor_and_target
    subdir = target / "python" / "src"
    subdir.mkdir(parents=True)

    assert wt.main(subdir, []) == int(Rc.OK)


def test_a_dangling_symlink_at_the_destination_is_refused_not_written_through(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The round-2 defect, armed — in the round-1 fix's own guard.

    `Path.exists()` FOLLOWS symlinks, so a dangling one read as absent: the
    guard said "go copy it" and `clonefile(2)` (flags=0 follows the link) wrote
    a whole clone at the link's TARGET, outside the worktree — from a guard
    whose message is "not touching a path this task did not create". A reaped
    `/private/tmp` agent scratchpad is exactly what leaves a symlink outliving
    its target.
    """
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    _donor, target = donor_and_target
    name = wt.REQUIRED_CLONES[0]
    outside = target.parent / "OUTSIDE-THE-WORKTREE"
    (target / "sources" / name).symlink_to(outside)

    result = wt.prepare_existing(target)

    assert isinstance(result, Err)
    assert result.rc == Rc.BAD_REQUEST
    assert not outside.exists(), "must not write a clone through the link, outside the target"


def test_a_dangling_symlink_at_a_graph_path_is_refused(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same trap on the graph path, where it landed worse.

    Nothing downstream disagreed with `_prepare_graph_file`, so this one
    returned `created` and rc 0 while putting the graph outside the worktree.
    """
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    _donor, target = donor_and_target
    rel = wt.REQUIRED_GRAPH_FILES[0]
    outside = target.parent / "OUTSIDE-GRAPH.json"
    (target / rel).parent.mkdir(parents=True, exist_ok=True)
    (target / rel).symlink_to(outside)

    result = wt.prepare_existing(target)

    assert isinstance(result, Err)
    assert result.rc == Rc.BAD_REQUEST
    assert not outside.exists(), "must not write the graph through the link"


def test_a_stale_graph_file_is_not_certified_already_present(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-9's other half — the branch the first fix did not reach.

    `clonefile(2)` is atomic, so a run killed AFTER the syscall leaves a
    complete copy of a then-truncated donor. The size check went on the create
    branch; the certifying branch had none, so the next run stamped it
    `already-present` forever.
    """
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    _donor, target = donor_and_target
    rel = wt.REQUIRED_GRAPH_FILES[0]
    (target / rel).parent.mkdir(parents=True, exist_ok=True)
    (target / rel).write_text("{}\n", encoding="utf-8")

    result = wt.prepare_existing(target)

    assert isinstance(result, Err)
    assert result.rc == Rc.NOT_RUN
    assert "already-present" in result.message


def test_a_prepared_target_does_not_depend_on_the_donors_inventory(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The round-2 over-correction, armed.

    The first F-7 fix made the donor's inventory a precondition of the whole
    run, so a fully-prepared worktree was refused because the donor had since
    lost a clone it no longer needed — contradicting this module's own
    idempotency claim, and reachable during `kb-build`'s re-clone window.
    """
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    donor, target = donor_and_target
    first = wt.prepare_existing(target)
    assert isinstance(first, Ok), getattr(first, "message", first)

    shutil.rmtree(donor / "sources" / wt.REQUIRED_CLONES[0])

    second = wt.prepare_existing(target)
    assert isinstance(second, Ok), "the target has everything; the donor's state is not its problem"


def test_a_physical_copy_is_not_a_clone(
    donor_and_target: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The headline guarantee, armed — the one property this module exists for.

    Round 1's F-8 was "the fail-closed branches have zero tests"; the fix
    deleted those branches (correctly) and added no test of the property they
    protected. A round-2 arm then replaced `_clonefile` with a genuine
    `shutil.copytree` that preserves every observable the unit tests check, and
    the whole suite stayed green — so "never a silent physical copy" would not
    be noticed if someone simplified the `ctypes` call away.

    Free space discriminates where the observables do not: cloning a file costs
    nothing, copying it costs its size.
    """
    monkeypatch.setattr(wt, "_uv_sync", _no_sync)
    donor, target = donor_and_target
    payload = donor / "graphify-out" / "graph.json"
    payload.write_bytes(b"x" * (48 * 1024 * 1024))

    statvfs = os.statvfs
    before = statvfs(str(target)).f_bavail * statvfs(str(target)).f_frsize
    result = wt.prepare_existing(target)
    after = statvfs(str(target)).f_bavail * statvfs(str(target)).f_frsize

    assert isinstance(result, Ok), getattr(result, "message", result)
    assert (target / "graphify-out" / "graph.json").stat().st_size == payload.stat().st_size
    assert before - after < payload.stat().st_size // 2, (
        "cloning must not consume the payload's size in real disk — a physical "
        "copy would, and that is the one thing this module promises not to do"
    )
