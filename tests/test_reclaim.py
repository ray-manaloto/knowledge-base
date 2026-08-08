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
    total = reclaim._report(findings, [_cat()], {})
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
    assert reclaim.plan([cat], tmp_path / "repo") == ([], {})


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


# ─── regressions from the 2026-08-07 two-axis review ─────────────────────────
#
# Every test below FAILS against the code as first committed. They exist because
# the original suite asked only "inside the root" vs "outside the root" and never
# whether the boundary ITSELF was excluded — so `--apply` would have rmtree'd the
# whole of ~/Library/Caches while 17 green tests and four green gates said fine.


def test_guard_refuses_the_declared_root_itself(tmp_path):
    """A root is a container, not a candidate. THIS is the near-miss."""
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(reclaim.ReclaimError, match="root itself"):
        reclaim._guard_path(root, [root], tmp_path / "repo")


def test_scan_dirs_never_emits_the_configured_root(tmp_path):
    """Whatever else it reports, the root must never be a deletion target."""
    root = tmp_path / "cache"
    (root / "old-entry").mkdir(parents=True)
    cat = _cat(kind="dirs", age_days=0, options={"paths": [str(root)]})
    findings = reclaim.scan_dirs(cat, tmp_path / "repo").findings
    assert all(f.path != root for f in findings), "scan_dirs offered the root for deletion"


def test_scan_dirs_skips_an_entry_touched_inside_the_age_window(tmp_path):
    """age_days was declared on every cache category and read by none of them."""
    root = tmp_path / "cache"
    fresh = root / "in-use"
    fresh.mkdir(parents=True)
    (fresh / "live.bin").write_bytes(b"x" * 4096)

    cat = _cat(kind="dirs", age_days=30, min_size_mb=0, options={"paths": [str(root)]})
    findings = reclaim.scan_dirs(cat, tmp_path / "repo").findings

    assert findings == [], "a cache written seconds ago was offered for deletion"


def test_touched_since_reports_recent_when_it_cannot_ask(tmp_path):
    """A failed probe must never be rendered as permission to delete."""
    assert reclaim._touched_since(tmp_path / "does-not-exist", "2000-01-01T00:00:00") is True


def test_age_stamp_is_absolute_because_the_relative_form_is_unusable(tmp_path):
    """Control arm: the ABSOLUTE form filters; the relative form does not work here.

    `find -newermt '-30 days'` errors outright on this machine's find, and on BSD
    find it silently matches nothing — indistinguishable from "no recent files",
    which would mark a live cache as stale and delete it.
    """
    old = tmp_path / "old.bin"
    old.write_bytes(b"x")
    os.utime(old, (0, 0))
    new = tmp_path / "new.bin"
    new.write_bytes(b"x")

    stamp = reclaim._age_stamp(30)
    assert stamp[4] == "-", f"not an absolute timestamp: {stamp}"
    assert "T" in stamp, f"not an absolute timestamp: {stamp}"
    # The mechanism discriminates: fresh file seen, ancient file not.
    assert reclaim._touched_since(new, stamp) is True
    assert reclaim._touched_since(old, stamp) is False


def test_ollama_age_filter_keeps_a_fresh_model_and_drops_an_old_one():
    """`keep = []` plus an unread age_days meant every model was a candidate."""
    assert reclaim._ollama_is_stale("2 weeks ago", 14) is True
    assert reclaim._ollama_is_stale("3 days ago", 14) is False
    assert reclaim._ollama_is_stale("2 minutes ago", 14) is False
    # Unparsable or absent -> NOT stale. An age that could not be established
    # must never license a deletion.
    assert reclaim._ollama_is_stale("", 14) is False
    assert reclaim._ollama_is_stale("who knows", 14) is False


def test_dir_size_keeps_dus_total_when_a_subtree_was_unreadable(tmp_path, monkeypatch):
    """`du` exits 1 on an unreadable subtree while still printing a correct total.

    Gating on rc==0 discarded that number and fell back to the slow python walk
    for `~/Library/Caches` — the single largest tree, and the one the du rewrite
    existed to speed up.
    """
    monkeypatch.setattr(reclaim, "_run", lambda *_a, **_k: (1, "2048\t/somewhere"))
    (tmp_path / "f.bin").write_bytes(b"x")
    assert reclaim._dir_size(tmp_path) == 2048 * 1024


def test_only_with_a_missing_value_is_an_error_not_a_silent_widening():
    """`--only` with no value returned an empty set, which meant EVERY category."""
    with pytest.raises(reclaim.ReclaimError, match="needs a comma-separated value"):
        reclaim._opt_list(["--apply", "--only"], "--only")
    with pytest.raises(reclaim.ReclaimError, match="needs a comma-separated value"):
        reclaim._opt_list(["--only", "--apply"], "--only")
    assert reclaim._opt_list(["--only", "docker,ollama"], "--only") == {"docker", "ollama"}


def test_main_exits_2_when_a_filter_flag_has_no_value(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "reclaim.toml").write_text(
        "[defaults]\nage_days = 1\n\n[category.docker]\nenabled = true\nkind = 'docker'\n",
        encoding="utf-8",
    )
    assert reclaim.main(["--only"], repo) == 2


def test_docker_prune_respects_containers_false(monkeypatch):
    """A config key that is declared and never read is a protection that lies."""
    calls: list[list[str]] = []

    def fake_run(argv, *, env_context=None) -> tuple[int, str]:
        calls.append(argv)
        return 0, ""

    monkeypatch.setattr(reclaim, "_run", fake_run)
    monkeypatch.setattr(reclaim, "_dir_size", lambda _p: 0)
    cat = _cat(
        kind="docker",
        options={
            "engines": [{"context": "x", "disk_image": "/nonexistent"}],
            "prune": {"containers": False},
        },
    )
    reclaim.apply_docker(cat)
    issued = [" ".join(c) for c in calls]

    # The key means EXACTLY what it says: no container prune is issued...
    assert not any("container prune" in c for c in issued), "pruned containers despite the key"
    # ...and nothing else is collaterally disabled. The first fix for this key
    # skipped the whole `docker system prune`, which silently turned off image
    # and volume pruning too — a patch that broke two other keys to honour one.
    assert any("image prune" in c for c in issued), "images were collaterally disabled"
    assert any("builder prune" in c for c in issued), "build cache was collaterally disabled"


def test_each_docker_prune_key_maps_to_exactly_one_command():
    """`docker system prune` could not express these keys; the per-type ones can.

    It always removes stopped containers AND dangling images regardless of
    `--all`, so `containers = false` and `images = false` both claimed
    protections the command was incapable of providing.
    """
    all_on = reclaim._prune_commands(
        {"containers": True, "images": True, "build_cache": True, "volumes": True}, 720
    )
    labels = [label for label, _ in all_on]
    assert labels == ["container prune", "image prune", "builder prune", "volume prune"]

    none_on = reclaim._prune_commands(
        {"containers": False, "images": False, "build_cache": False, "volumes": False}, 720
    )
    assert none_on == [], "a key set false still issued its command"

    # The age filter reaches the commands that support it. `volume prune` is
    # absent from this assertion because docker gives it no `until` filter —
    # stated rather than silently dropped.
    for label, argv in all_on:
        if label != "volume prune":
            assert "until=720h" in " ".join(argv), f"{label} lost its age bound"


def test_scan_ollama_does_not_offer_a_freshly_pulled_model(monkeypatch):
    """The age filter must be wired INTO scan_ollama, not merely exist beside it.

    A mutation that removed the `_ollama_is_stale` call from `scan_ollama`
    SURVIVED the first arms run: the unit test above exercised the helper
    directly and never its point of use, so the wiring was untested while the
    logic looked covered.
    """
    listing = (
        "NAME              ID      SIZE      MODIFIED\n"
        "fresh:latest      abc123  8.0 GB    2 minutes ago\n"
        "ancient:latest    def456  9.0 GB    6 months ago\n"
    )
    monkeypatch.setattr(reclaim.shutil, "which", lambda _n: "/usr/local/bin/ollama")
    monkeypatch.setattr(reclaim, "_run", lambda *_a, **_k: (0, listing))
    cat = _cat(kind="ollama", age_days=14, options={"keep": []})

    labels = [f.label for f in reclaim.scan_ollama(cat, Path("/repo")).findings]

    assert "fresh:latest" not in labels, "a model pulled 2 minutes ago was offered for deletion"
    assert "ancient:latest" in labels


def test_whole_tree_is_opt_in_and_never_targets_the_root(tmp_path):
    """`whole_tree` bypasses the age check — but only when explicitly written."""
    root = tmp_path / "cache"
    entry = root / "content-v2"
    entry.mkdir(parents=True)
    (entry / "blob").write_bytes(b"x" * 4096)  # fresh, so age would exclude it

    off = _cat(kind="dirs", age_days=30, min_size_mb=0, options={"paths": [str(root)]})
    off_found = reclaim.scan_dirs(off, tmp_path / "repo").findings
    assert off_found == [], "age check skipped without opt-in"

    on = _cat(
        kind="dirs",
        age_days=30,
        min_size_mb=0,
        options={"paths": [str(root)], "whole_tree": True},
    )
    findings = reclaim.scan_dirs(on, tmp_path / "repo").findings
    assert [f.path for f in findings] == [entry]
    assert root not in [f.path for f in findings], "whole_tree offered the root itself"


# ─── the third state: COULD NOT CHECK is not "nothing found" ─────────────────


def test_a_missing_configured_path_is_unavailable_not_empty(tmp_path):
    """A typo'd path must not be indistinguishable from a genuinely empty cache."""
    cat = _cat(kind="dirs", options={"paths": [str(tmp_path / "nope")]})
    res = reclaim.scan_dirs(cat, tmp_path / "repo")
    assert res.findings == []
    assert res.unavailable, "a non-existent path was reported as a clean empty scan"
    assert "does not exist" in res.unavailable[0]


def test_a_missing_binary_is_unavailable_not_empty(monkeypatch):
    """`ollama` absent means the question was never asked, not answered no."""
    monkeypatch.setattr(reclaim.shutil, "which", lambda _n: None)
    res = reclaim.scan_ollama(_cat(kind="ollama"), Path("/repo"))
    assert res.findings == []
    assert res.unavailable == ["`ollama` is not on PATH"]


def test_report_says_could_not_check_and_refuses_the_clean_wording(tmp_path, capsys):
    """The two states must READ differently, not merely be tracked differently."""
    cat = _cat(name="c", kind="dirs")
    reclaim._report([], [cat], {"c": ["configured path does not exist: /nope"]})
    out = capsys.readouterr().out
    assert "COULD NOT CHECK" in out
    assert "nothing found — scanned, not skipped" not in out, (
        "an unchecked category still claimed a clean scan"
    )


def test_report_still_says_scanned_not_skipped_for_a_real_empty(capsys):
    """Control arm: the clean wording must survive where it is TRUE."""
    reclaim._report([], [_cat(name="c", kind="dirs")], {})
    assert "nothing found — scanned, not skipped" in capsys.readouterr().out


def test_main_warns_that_the_total_is_a_floor_when_something_was_unreachable(tmp_path, capsys):
    """A headline number computed over an incomplete scan must say so."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "reclaim.toml").write_text(
        "[defaults]\nage_days = 1\nmin_size_mb = 0\n\n"
        f"[category.gone]\nenabled = true\nkind = 'dirs'\npaths = ['{tmp_path / 'nope'}']\n",
        encoding="utf-8",
    )
    assert reclaim.main([], repo) == 0
    assert "COULD NOT BE CHECKED" in capsys.readouterr().out


def test_an_unknown_kind_is_refused_not_defaulted_to_deletion(tmp_path, capsys):
    """The cascade this replaced sent an unrecognised kind to `apply_deletions`.

    That is the most destructive possible default for an unknown value, and it
    made the module docstring false: adding a reclaimer needed a scanner, a
    config block AND an apply branch, and forgetting the third was silent.
    """
    root = tmp_path / "r"
    root.mkdir()
    doomed = root / "f.bin"
    doomed.write_bytes(b"x")
    cat = _cat(name="weird", kind="not-a-real-kind", options={"paths": [str(root)]})
    finding = reclaim.Finding("weird", "f.bin", 1, "d", path=doomed)

    rc = reclaim._apply_all([cat], [finding], tmp_path / "repo")

    assert doomed.exists(), "an unknown kind deleted a file by falling through"
    assert rc == 2
    assert "REFUSED" in capsys.readouterr().out


def test_a_failed_deletion_reaches_the_exit_code(tmp_path, capsys):
    """A run that could not delete used to print FAILED and still exit 0.

    The real run this came from left 21.3G behind on a permission error and
    reported success.
    """
    root = tmp_path / "r"
    root.mkdir()
    cat = _cat(name="c", kind="dirs", options={"paths": [str(root)]})
    outside = reclaim.Finding("c", "escapee", 1, "d", path=tmp_path / "elsewhere")

    rc = reclaim._apply_all([cat], [outside], tmp_path / "repo")

    assert rc == 1, "a REFUSED deletion did not reach the exit code"
    assert "REFUSED" in capsys.readouterr().out
