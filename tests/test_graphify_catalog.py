# Copyright (c) 2026 Raymond Manaloto
"""`kb-setup graphify-catalog` — does the catalog still describe the pinned commit?

The defect these cover shipped: the 0.9.57 pin advanced `source_commit` and left
`source_tree`, the `uv.lock` row and `BaselineAuthority.catalog_sha256` describing
the previous commit, and **all eight gates passed over it**.

Every fixture here is a REAL git repository with real blobs. A mocked `git` would
test the mock, and the whole class of defect is a recorded digest that stopped
describing a real object — which only real objects can exhibit.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import msgspec
import pytest
from kb_setup import graphify_baseline
from kb_setup import graphify_catalog as gc
from kb_setup.graphify_baseline import BaselineAuthority
from kb_setup.result import Rc

#: The catalog's ref must be the one `load_disposition_catalog` accepts — it is
#: checked against a module constant, and the ref is not what these tests vary.
_REF = graphify_baseline.accepted_authority().source_ref


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _clone(tmp_path: Path, files: dict[str, str]) -> tuple[Path, str, str]:
    """A real one-commit repo. Returns (clone, commit, tree)."""
    clone = tmp_path / "sources" / "graphify"
    clone.mkdir(parents=True)
    _git(clone, "init", "-q", "-b", "main")
    _git(clone, "config", "user.email", "t@example.invalid")
    _git(clone, "config", "user.name", "t")
    for name, body in files.items():
        target = clone / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    _git(clone, "add", "-A")
    _git(clone, "commit", "-q", "-m", "fixture")
    return clone, _git(clone, "rev-parse", "HEAD"), _git(clone, "rev-parse", "HEAD^{tree}")


def _repo(tmp_path: Path, files: dict[str, str], *, entries: list[dict] | None = None) -> Path:
    """A repo_root whose manifest, catalog and clone all agree."""
    clone, commit, tree = _clone(tmp_path, files)
    (tmp_path / "sources" / "graphify.manifest").write_text(
        f"url = https://example.invalid/g\nref = {_REF}\ncommit = {commit}\n", encoding="utf-8"
    )
    rows = entries if entries is not None else _entries(clone, commit, files)
    (tmp_path / "sources" / "graphify.dispositions.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": "graphify",
                "source_ref": _REF,
                "source_commit": commit,
                "source_tree": tree,
                "entries": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return tmp_path


def _entries(clone: Path, commit: str, files: dict[str, str]) -> list[dict]:
    rows = []
    for name in files:
        found = gc._blob(clone, commit, name)
        assert found is not None
        sha, size = found
        rows.append(
            {
                "path": name,
                "kind": "unsupported-file",
                "reason": "fixture",
                "sha256": sha,
                "size": size,
                "file_type": "regular",
            }
        )
    return rows


def _authority(commit: str, tree: str, repo_root: Path) -> BaselineAuthority:
    """An authority that agrees with the fixture, digest included."""
    catalog = graphify_baseline.load_disposition_catalog(repo_root)
    return BaselineAuthority(
        source_ref=_REF,
        source_commit=commit,
        source_tree=tree,
        catalog_sha256=graphify_baseline.catalog_digest(catalog),
        source_manifest_sha256="b" * 64,
        detected_count=1,
        extracted_count=1,
    )


@pytest.fixture
def agreeing(tmp_path: Path) -> tuple[Path, BaselineAuthority]:
    root = _repo(tmp_path, {"uv.lock": "version = 1\n", "LICENSE": "MIT\n"})
    clone = root / "sources" / "graphify"
    commit = _git(clone, "rev-parse", "HEAD")
    tree = _git(clone, "rev-parse", "HEAD^{tree}")
    return root, _authority(commit, tree, root)


# --- the PASS arm. Without it every failure below could be a broken probe. ----


def test_a_catalog_that_matches_its_pin_is_clean(
    agreeing: tuple[Path, BaselineAuthority],
) -> None:
    root, authority = agreeing
    report = gc.check(root, authority=authority)
    assert report.drift == ()
    assert report.examined == 2


# --- the FAIL arms, each a REALISTIC break -----------------------------------


def test_a_stale_source_tree_is_reported(agreeing: tuple[Path, BaselineAuthority]) -> None:
    """The literal 0.9.57 defect: the commit advanced, the tree digest did not."""
    root, authority = agreeing
    path = root / "sources" / "graphify.dispositions.json"
    catalog = json.loads(path.read_text())
    catalog["source_tree"] = "0" * 40
    path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    drift = gc.check(root, authority=authority).drift
    assert [row.what for row in drift if row.what == "source_tree"] == ["source_tree"]


def test_moved_bytes_under_an_unchanged_path_are_reported(
    agreeing: tuple[Path, BaselineAuthority],
) -> None:
    """`uv.lock`'s real shape: same path, new content, stale sha256 AND size.

    Both rows must fire. A checker comparing only the digest would pass a file
    whose size row had been hand-edited, and vice versa.
    """
    root, authority = agreeing
    path = root / "sources" / "graphify.dispositions.json"
    catalog = json.loads(path.read_text())
    row = next(e for e in catalog["entries"] if e["path"] == "uv.lock")
    row["sha256"] = "f" * 64
    row["size"] = row["size"] + 153  # the real 1015646 -> 1015799 delta
    path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    whats = {row.what for row in gc.check(root, authority=authority).drift}
    assert "uv.lock sha256" in whats
    assert "uv.lock size" in whats


def test_a_path_the_pin_no_longer_has_is_absent_not_an_error(
    agreeing: tuple[Path, BaselineAuthority],
) -> None:
    """How the mise resync red-lined `kb-build`: a catalog path gone at the new pin.

    It must be a ROW, so the other nineteen answers survive — not an exception.
    """
    root, authority = agreeing
    path = root / "sources" / "graphify.dispositions.json"
    catalog = json.loads(path.read_text())
    catalog["entries"].append(
        {
            "path": "gone.txt",
            "kind": "unsupported-file",
            "reason": "fixture",
            "sha256": "a" * 64,
            "size": 1,
            "file_type": "regular",
        }
    )
    path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    report = gc.check(root, authority=authority)
    absent = [row for row in report.drift if row.kind == "absent"]
    assert [row.what for row in absent] == ["gone.txt"]
    assert report.examined == 3, "the other rows were still examined"


def test_a_stale_authority_tree_is_reported(agreeing: tuple[Path, BaselineAuthority]) -> None:
    """The half a catalog-only fix leaves behind — the python literal."""
    root, authority = agreeing
    stale = msgspec.structs.replace(authority, source_tree="0" * 40)
    whats = {row.what for row in gc.check(root, authority=stale).drift}
    assert "authority source_tree" in whats


def test_editing_the_catalog_invalidates_the_authority_digest(
    agreeing: tuple[Path, BaselineAuthority],
) -> None:
    """The ORDER-DEPENDENT row, and the reason `--write` is not implemented.

    Fixing a stale catalog entry changes the digest that names the catalog, so a
    fix applied without re-deriving this one trades one drift for another. This
    is the row the cold review itself missed.
    """
    root, authority = agreeing
    assert gc.check(root, authority=authority).drift == (), "control: agreeing to start with"

    path = root / "sources" / "graphify.dispositions.json"
    catalog = json.loads(path.read_text())
    catalog["entries"][0]["reason"] = "fixture, reworded"
    path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    whats = {row.what for row in gc.check(root, authority=authority).drift}
    assert whats == {"authority catalog_sha256"}, (
        "a reason-only edit must move the digest and nothing else"
    )


# --- the states that are NOT findings ----------------------------------------


def test_no_clone_is_not_run_and_never_a_pass(tmp_path: Path) -> None:
    (tmp_path / "sources").mkdir()
    with pytest.raises(gc.CatalogUnavailableError):
        gc.check(tmp_path)
    assert gc.main(tmp_path) == Rc.NOT_RUN


def test_a_commit_the_clone_lacks_is_not_run_not_twenty_absent_rows(tmp_path: Path) -> None:
    """A shallow clone missing the object must not read as 'every path is gone'."""
    root = _repo(tmp_path, {"uv.lock": "version = 1\n"})
    manifest = root / "sources" / "graphify.manifest"
    manifest.write_text(
        manifest.read_text().replace(
            _git(root / "sources" / "graphify", "rev-parse", "HEAD"), "d" * 40
        ),
        encoding="utf-8",
    )
    with pytest.raises(gc.CatalogUnavailableError):
        gc.check(root)


def test_an_unknown_flag_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    assert gc.main(tmp_path, ["--nope"]) == Rc.BAD_REQUEST


def test_write_is_refused_because_the_order_is_not_guessable(tmp_path: Path) -> None:
    assert gc.main(tmp_path, ["--write"]) == Rc.BAD_REQUEST


def test_main_returns_findings_on_drift(agreeing: tuple[Path, BaselineAuthority]) -> None:
    """The CLI boundary, not just `check` — rc 1 is what a gate reads."""
    root, _ = agreeing
    path = root / "sources" / "graphify.dispositions.json"
    catalog = json.loads(path.read_text())
    catalog["source_tree"] = "0" * 40
    path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    assert gc.main(root) == Rc.FINDINGS


def test_the_real_repo_agrees_with_its_own_pin() -> None:
    """The end-to-end arm: this repository, its real catalog, its real authority.

    The fixtures above prove the checker discriminates; this proves the tree it
    ships in is actually clean. Without it a green suite could sit on top of the
    exact drift the module was written for.
    """
    assert gc.main(Path.cwd()) == Rc.OK
