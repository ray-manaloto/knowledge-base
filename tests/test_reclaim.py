# Copyright (c) 2026 Raymond Manaloto
"""Tests for `kb_setup.reclaim` — the safety properties and the sizing arithmetic.

The two properties worth a test here are the two that make a config-driven
deleter tolerable at all: **dry run is the default**, and **a category can only
act inside its own declared roots**. Both are asserted in the FAIL direction —
a guard that has only ever been shown to permit is not a guard.

The sparse-file test is a regression, not a hypothetical. The first live run of
this module reported **2343.4G reclaimable on a 1.8TB disk**, because it summed
`st_size` and `Docker.raw` advertises 1858.2G while occupying 285.8G.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from kb_setup import reclaim


def _cat(**kw: object) -> reclaim.Category:
    base = {
        "name": "t",
        "kind": "dirs",
        "enabled": True,
        "age_days": 30,
        "min_size_mb": 0,
        "options": {},
    }
    base.update(kw)
    return reclaim.Category(**base)


# ─── the sizing arithmetic ───────────────────────────────────────────────────


def test_allocated_ignores_the_apparent_size_of_a_sparse_file(tmp_path):
    """A sparse file's ADVERTISED size must never be counted as disk in use."""
    sparse = tmp_path / "disk.raw"
    with sparse.open("wb") as fh:
        fh.truncate(4 * 1024 * 1024 * 1024)  # 4 GiB apparent, ~0 allocated

    st = sparse.stat()
    apparent = st.st_size
    allocated = reclaim._allocated(st)

    # Control arm: the file really is sparse on this filesystem, so the test can
    # discriminate. Without this the assertion below could pass on a filesystem
    # that silently materialised the bytes.
    if st.st_blocks * 512 >= apparent:
        pytest.skip("filesystem did not create a sparse file; nothing to discriminate")

    assert allocated < apparent
    assert allocated == st.st_blocks * 512


def test_dir_size_sums_allocated_not_apparent(tmp_path):
    """The directory walker inherits the sparse-aware measurement."""
    (tmp_path / "solid.bin").write_bytes(b"x" * 8192)
    assert reclaim._dir_size(tmp_path) >= 8192
    assert reclaim._dir_size(tmp_path / "missing") == 0


def test_informational_findings_are_never_summed_into_the_total(capsys):
    """A container disk image is context; counting it double-counts the reclaim."""
    findings = [
        reclaim.Finding("t", "real", 100, "d"),
        reclaim.Finding("t", "image", 900, "d", informational=True),
    ]
    total = reclaim._report(findings, [_cat()])
    assert total == 100
    assert "context, not counted" in capsys.readouterr().out


# ─── safety property 1: roots are honoured ───────────────────────────────────


def test_guard_allows_a_target_inside_a_declared_root(tmp_path):
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    reclaim._guard_path(root / "sub", [root], tmp_path / "repo")


def test_guard_refuses_a_target_outside_every_declared_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    with pytest.raises(reclaim.ReclaimError, match="escapes every declared root"):
        reclaim._guard_path(outside, [root], tmp_path / "repo")


def test_guard_refuses_a_target_inside_the_repository(tmp_path):
    """Even a correctly-declared root may not reach into the repo itself."""
    repo = tmp_path / "repo"
    (repo / "python").mkdir(parents=True)
    with pytest.raises(reclaim.ReclaimError, match="inside the repository"):
        reclaim._guard_path(repo / "python", [tmp_path], repo)


def test_guard_refuses_the_filesystem_root():
    with pytest.raises(reclaim.ReclaimError, match="filesystem root"):
        reclaim._guard_path(Path(os.sep), [Path(os.sep)], Path.cwd())


def test_apply_deletions_refuses_rather_than_deleting_an_out_of_root_path(tmp_path):
    """The REFUSAL is what is asserted, and the file must survive it."""
    root = tmp_path / "root"
    root.mkdir()
    victim = tmp_path / "outside.bin"
    victim.write_bytes(b"keep me")
    cat = _cat(options={"paths": [str(root)]})
    finding = reclaim.Finding("t", "outside.bin", 7, "d", path=victim)

    lines = reclaim.apply_deletions(cat, [finding], tmp_path / "repo")

    assert victim.exists(), "guard let a deletion through"
    assert any("REFUSED" in line for line in lines)


def test_apply_deletions_removes_a_path_inside_its_root(tmp_path):
    """The control arm for the test above: in-root deletion DOES happen."""
    root = tmp_path / "root"
    root.mkdir()
    doomed = root / "cache.bin"
    doomed.write_bytes(b"bye")
    cat = _cat(options={"paths": [str(root)]})
    finding = reclaim.Finding("t", "cache.bin", 3, "d", path=doomed)

    lines = reclaim.apply_deletions(cat, [finding], tmp_path / "repo")

    assert not doomed.exists()
    assert any("removed" in line for line in lines)


# ─── safety property 2: dry run is the default ───────────────────────────────


def test_main_deletes_nothing_without_apply(tmp_path):
    """The default invocation must be observably read-only."""
    repo = tmp_path / "repo"
    repo.mkdir()
    target_root = tmp_path / "downloads"
    target_root.mkdir()
    keeper = target_root / "big.dmg"
    keeper.write_bytes(b"z" * 2048)
    os.utime(keeper, (0, 0))  # ancient, so it is definitely a finding
    (repo / "reclaim.toml").write_text(
        "[defaults]\nage_days = 1\nmin_size_mb = 0\n\n"
        "[category.downloads]\nenabled = true\nkind = 'files'\n"
        f"paths = ['{target_root}']\nextensions = ['.dmg']\nmin_size_mb = 0\n",
        encoding="utf-8",
    )

    rc = reclaim.main([], repo)

    assert rc == 0
    assert keeper.exists(), "a dry run deleted a file"


def test_main_refuses_an_only_that_matches_no_category(tmp_path):
    """A filter matching nothing is a malformed request, not an empty success."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "reclaim.toml").write_text(
        "[defaults]\nage_days = 1\n\n[category.docker]\nenabled = true\nkind = 'docker'\n",
        encoding="utf-8",
    )
    assert reclaim.main(["--only", "nope"], repo) == 2


def test_main_reports_a_missing_config_rather_than_scanning_nothing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert reclaim.main([], repo) == 2


# ─── config ──────────────────────────────────────────────────────────────────


def test_load_config_merges_defaults_into_each_category(tmp_path):
    cfg = tmp_path / "reclaim.toml"
    cfg.write_text(
        "[defaults]\nage_days = 30\nmin_size_mb = 100\n\n"
        "[category.a]\nenabled = true\nkind = 'dirs'\n\n"
        "[category.b]\nenabled = false\nkind = 'files'\nage_days = 7\n",
        encoding="utf-8",
    )
    cats = {c.name: c for c in reclaim.load_config(cfg)}
    assert cats["a"].age_days == 30
    assert cats["a"].min_size_mb == 100
    assert cats["b"].age_days == 7
    assert cats["b"].enabled is False


def test_plan_skips_disabled_categories(tmp_path):
    """A disabled category contributes nothing — and is not silently an error."""
    cat = _cat(enabled=False, options={"paths": [str(tmp_path)]})
    assert reclaim.plan([cat], tmp_path / "repo") == []


def test_parse_size_handles_dockers_human_units():
    assert reclaim._parse_size("120.9GB (48%)") == 120_900_000_000
    assert reclaim._parse_size("77.64GB") == 77_640_000_000
    assert reclaim._parse_size("unparsable") == 0


def test_repo_config_is_loadable_and_declares_every_kind_a_scanner_handles():
    """The shipped reclaim.toml must not name a kind with no scanner behind it."""
    cats = reclaim.load_config(Path.cwd() / "reclaim.toml")
    assert cats, "shipped config declared no categories"
    for cat in cats:
        assert cat.kind in reclaim._SCANNERS, f"{cat.name} declares unknown kind {cat.kind!r}"


def test_brew_freed_bytes_reads_a_size_mid_sentence():
    """Regression: brew puts the size mid-line, and trimming the tail returned 0.

    The first version handed `_parse_size` the string "9.1GB of disk space" and
    got 0, so the homebrew category reported "nothing found" over a real 9.1GB —
    a silent zero, which reads exactly like an empty result.
    """
    real = "==> This operation would free approximately 9.1GB of disk space."
    assert reclaim._brew_freed_bytes(real) == 9_100_000_000
    assert reclaim._brew_freed_bytes("nothing to say here") == 0
