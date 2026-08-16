# Copyright (c) 2026 Raymond Manaloto
"""Reviewed detection classes for vendored third-party clones (#289).

The gate these cover is a RELAXATION — it lets `kb-build` proceed over files it
previously refused. So the tests that matter are the ones proving it did not
become a blanket pass: an unknown extension still blocks, a required path is
never absorbed, and an escaping symlink is refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_setup import graph, graphify_health, graphify_sdk


def _write(root: Path, relative: str, body: str = "x") -> str:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return relative


@pytest.mark.parametrize(
    "relative",
    [
        "LICENSE",
        "LICENSE.txt",
        "License-Apache",
        "crates/inner/LICENSE.BSD",
        "COPYING",
        ".gitignore",
        "web/.gitignore",
        ".dockerignore",
        ".gitattributes",
        "py.typed",
        "VERSION",
        "uv.lock",
        "docs/assets/favicon.ico",
        "dist/thing.whl",
    ],
)
def test_non_source_class_is_absorbed_silently(tmp_path: Path, relative: str) -> None:
    """Repo bookkeeping and binary artifacts are not graph source at any depth."""
    _write(tmp_path, relative)
    non_source, unsupported, unresolved = graphify_sdk.classify_unclassified(tmp_path, (relative,))
    assert non_source == (relative,)
    assert unsupported == ()
    assert unresolved == ()


@pytest.mark.parametrize(
    "relative",
    [
        "benchmark/hk.pkl",
        "stubs/thing.pyi",
        "schema/user.graphql",
        "queries/highlights.scm",
        "docs/index.adoc",
        "notebooks/bench.ipynb",
        "default.nix",
        "Cargo.toml",
        "Dockerfile",
        "Dockerfile.alpine",
        "Makefile",
        "Makefile.deepseek-v4.units",
        "builder.dockerfile",
        ".prettierrc",
        ".SRCINFO",
        ".justfile",
        "completions/_mise",
        "testdata/repos/dotGit/HEAD",
        "core/src/main/resources/META-INF/services/java.nio.file.spi.FileTypeDetector",
        "crates/typos-cli/tests/cmd/bad.in/file.ignore",
    ],
)
def test_unsupported_language_class_is_counted_not_hidden(tmp_path: Path, relative: str) -> None:
    """Real source Graphify cannot parse stays in its OWN class, so it is tallied."""
    _write(tmp_path, relative)
    non_source, unsupported, unresolved = graphify_sdk.classify_unclassified(tmp_path, (relative,))
    assert unsupported == (relative,)
    assert non_source == ()
    assert unresolved == ()


# --- the arms: prove the relaxation did NOT become a blanket pass ------------


@pytest.mark.parametrize(
    "relative",
    [
        "src/mystery.zzz",
        "src/unheard_of.qqq",
        "vendor/thing.frobnicate",
    ],
)
def test_an_unknown_extension_still_blocks(tmp_path: Path, relative: str) -> None:
    """CONTROL ARM. A genuinely new file type must still stop the build.

    Without this the whole change is indistinguishable from deleting the check.
    """
    _write(tmp_path, relative)
    non_source, unsupported, unresolved = graphify_sdk.classify_unclassified(tmp_path, (relative,))
    assert unresolved == (relative,)
    assert non_source == ()
    assert unsupported == ()


def test_a_required_path_is_never_absorbed_by_a_class(tmp_path: Path) -> None:
    """CONTROL ARM. `required_paths` outrank both classes, whatever the extension.

    A required `.pkl` is exactly the collision this has to survive: its extension
    is in the unsupported-language class, and it must fail anyway.
    """
    relative = _write(tmp_path, "required/thing.pkl")
    policy = graphify_health.SourceCoveragePolicy(required_paths=(relative,))
    widened = graphify_sdk._apply_detection_classes(tmp_path, (relative,), policy)
    assert relative not in widened.unsupported_language_paths
    assert relative not in widened.optional_unclassified_paths

    reasons = graphify_health.assess(
        graphify_health.GraphifyOperation.DETECT,
        graphify_health.GraphifyEvidence(
            observed=True,
            unclassified_paths=(relative,),
            coverage_policy=widened,
        ),
    ).reasons
    assert "required-source-unclassified" in reasons


def test_a_symlink_escaping_the_tree_is_refused(tmp_path: Path) -> None:
    """CONTROL ARM. Containment, not the link's name, is what admits a symlink.

    The name says `LICENSE`, which is in the non-source class; the bytes live
    outside the reviewed tree, so it must stay unresolved.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real.txt").write_text("bytes nobody reviewed")
    root = tmp_path / "root"
    root.mkdir()
    (root / "LICENSE").symlink_to(outside / "real.txt")

    non_source, unsupported, unresolved = graphify_sdk.classify_unclassified(root, ("LICENSE",))
    assert unresolved == ("LICENSE",)
    assert non_source == ()
    assert unsupported == ()


def test_a_symlink_inside_the_tree_is_admitted(tmp_path: Path) -> None:
    """The other direction of the same rule — otherwise it only ever refuses."""
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "LICENSE.txt").write_text("MIT")
    (tmp_path / "LICENSE").symlink_to(tmp_path / "real" / "LICENSE.txt")

    non_source, _unsupported, unresolved = graphify_sdk.classify_unclassified(
        tmp_path, ("LICENSE",)
    )
    assert non_source == ("LICENSE",)
    assert unresolved == ()


def test_a_dangling_symlink_is_refused(tmp_path: Path) -> None:
    """`is_file()` follows the link, so a broken one can never be classified."""
    (tmp_path / "LICENSE").symlink_to(tmp_path / "does-not-exist")
    _non_source, _unsupported, unresolved = graphify_sdk.classify_unclassified(
        tmp_path, ("LICENSE",)
    )
    assert unresolved == ("LICENSE",)


def test_a_path_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    """Class membership never rests on the name alone."""
    _non_source, _unsupported, unresolved = graphify_sdk.classify_unclassified(
        tmp_path, ("LICENSE", "../escape/LICENSE", "/abs/LICENSE")
    )
    assert set(unresolved) == {"LICENSE", "../escape/LICENSE", "/abs/LICENSE"}


def test_absorbed_classes_clear_the_unclassified_reason(tmp_path: Path) -> None:
    """End-to-end: a policy widened by both classes stops raising the blocker."""
    paths = (
        _write(tmp_path, "LICENSE"),
        _write(tmp_path, "benchmark/hk.pkl"),
    )
    widened = graphify_sdk._apply_detection_classes(
        tmp_path, paths, graphify_health.SourceCoveragePolicy()
    )
    receipt = graphify_health.assess(
        graphify_health.GraphifyOperation.DETECT,
        graphify_health.GraphifyEvidence(
            observed=True, unclassified_paths=paths, coverage_policy=widened
        ),
    )
    assert "unclassified-files" not in receipt.reasons
    # The unsupported-language file is RETAINED on the receipt: absorbing it
    # without recording it is the failure this whole split exists to prevent.
    assert receipt.unsupported_language_paths == ("benchmark/hk.pkl",)


def test_counts_and_tallies_survive_the_display_bound(tmp_path: Path) -> None:
    """The `*_paths` tuples are display evidence capped at 12; totals are not.

    A `len()` over the bounded tuples saturated both the unsupported-language
    and unresolved counts at 12, silently under-reporting corpus loss.
    """
    unsupported = tuple(_write(tmp_path, f"benchmark/hk_{index:02d}.pkl") for index in range(15))
    unresolved = tuple(_write(tmp_path, f"src/mystery_{index:02d}.zzz") for index in range(14))
    paths = (*unsupported, *unresolved)
    widened = graphify_sdk._apply_detection_classes(
        tmp_path, paths, graphify_health.SourceCoveragePolicy()
    )
    receipt = graphify_health.assess(
        graphify_health.GraphifyOperation.DETECT,
        graphify_health.GraphifyEvidence(
            observed=True, unclassified_paths=paths, coverage_policy=widened
        ),
    )
    assert len(receipt.unsupported_language_paths) == 12
    assert len(receipt.unresolved_paths) == 12
    assert receipt.unsupported_language_count == 15
    assert receipt.unresolved_count == 14
    assert receipt.unsupported_language_tally == ((".pkl", 15),)


def test_one_unknown_file_still_blocks_a_source_full_of_known_ones(tmp_path: Path) -> None:
    """CONTROL ARM. The classes are per-file; they never whitelist a source."""
    paths = (
        _write(tmp_path, "LICENSE"),
        _write(tmp_path, "benchmark/hk.pkl"),
        _write(tmp_path, "src/mystery.zzz"),
    )
    widened = graphify_sdk._apply_detection_classes(
        tmp_path, paths, graphify_health.SourceCoveragePolicy()
    )
    receipt = graphify_health.assess(
        graphify_health.GraphifyOperation.DETECT,
        graphify_health.GraphifyEvidence(
            observed=True, unclassified_paths=paths, coverage_policy=widened
        ),
    )
    assert "unclassified-files" in receipt.reasons


def test_the_service_loader_rule_needs_the_exact_parent(tmp_path: Path) -> None:
    """CONTROL ARM. `META-INF/services/` is the rule; `META-INF/` alone is not.

    The sibling `META-INF/gradle/` tree is absorbed on its extension, so this
    checks the directory rule itself: a file with the same arbitrary-looking
    extension somewhere else must still block.
    """
    real = _write(tmp_path, "res/META-INF/services/org.pkl.Spi")
    decoy = _write(tmp_path, "res/META-INF/other/org.pkl.Spi")

    _non_source, unsupported, unresolved = graphify_sdk.classify_unclassified(
        tmp_path, (real, decoy)
    )
    assert unsupported == (real,)
    assert unresolved == (decoy,)


def test_a_fixture_rule_matches_whole_segments_only(tmp_path: Path) -> None:
    """The path-based rule is the loosest one here, so bound it explicitly.

    `contest/` and `latest.py` contain `test` and `latest` as substrings; neither
    is a fixture directory, and a substring match would have absorbed both.
    """
    fixture = _write(tmp_path, "testdata/repos/dotGit/HEAD")
    decoy_one = _write(tmp_path, "contest/mystery.zzz")
    decoy_two = _write(tmp_path, "src/protest.zzz")

    _non_source, unsupported, unresolved = graphify_sdk.classify_unclassified(
        tmp_path, (fixture, decoy_one, decoy_two)
    )
    assert unsupported == (fixture,)
    assert set(unresolved) == {decoy_one, decoy_two}


# --- the detector-sidecar exception (cognee's snapshot drift) ----------------


def test_a_detector_sidecar_is_not_drift() -> None:
    """Graphify writes `graphify-out/converted/*.md` into its own input."""
    assert graph._is_detector_sidecar("?? graphify-out/converted/example_8a530a1d.md")
    assert graph._is_detector_sidecar('?? "graphify-out/converted/a b.md"')


@pytest.mark.parametrize(
    "line",
    [
        # CONTROL ARM. A tracked file under graphify-out/ that CHANGED is real
        # drift: the exception is for output the detector adds, never for an
        # alteration to content the source already had.
        " M graphify-out/converted/example.md",
        " D graphify-out/tracked.json",
        "M  graphify-out/tracked.json",
        # CONTROL ARM. Untracked, but nowhere near the detector's directory.
        "?? src/leaked_secret.txt",
        "?? notgraphify-out/thing.md",
        # CONTROL ARM. A sibling whose name merely starts the same way.
        "?? graphify-outside/thing.md",
    ],
)
def test_real_drift_is_still_drift(line: str) -> None:
    assert not graph._is_detector_sidecar(line)


def test_a_symlink_to_a_directory_is_refused(tmp_path: Path) -> None:
    """CONTROL ARM for `is_file()` specifically, not merely for `exists()`.

    A dangling link cannot distinguish the two — `Path.exists()` follows
    symlinks too, so it is False for a broken link exactly as `is_file()` is.
    A DIRECTORY is the case that separates them, and the mutation sweep found
    that the docstring claimed this behaviour while no test exercised it.
    """
    (tmp_path / "real").mkdir()
    (tmp_path / "LICENSE").symlink_to(tmp_path / "real")
    _non_source, _unsupported, unresolved = graphify_sdk.classify_unclassified(
        tmp_path, ("LICENSE",)
    )
    assert unresolved == ("LICENSE",)


@pytest.mark.parametrize(
    "relative",
    [
        # CONTROL ARM for the licence rule's BOUNDARY. A bare `startswith`
        # absorbed all of these as licence files — real source, taken as
        # non-source and, unlike the counted class, never tallied.
        # Raised as LOW by the cold lane on f149ed62.
        "LICENSEPLATE.py",
        "LICENSED_users.rs",
        "COPYINGCTL.c",
        "licenceplate.go",
        # CONTROL ARM for the UNDERSCORE boundary specifically. `_` is
        # non-alphanumeric, so the first boundary fix still absorbed all of
        # these — the rule refuses `_` only when a letter follows it.
        "LICENSE_KEYS.py",
        "LICENCE_manager.rs",
        "COPYING_utils.c",
    ],
)
def test_a_name_merely_starting_with_licence_still_blocks(tmp_path: Path, relative: str) -> None:
    _write(tmp_path, relative)
    non_source, _unsupported, unresolved = graphify_sdk.classify_unclassified(tmp_path, (relative,))
    assert unresolved == (relative,)
    assert non_source == ()


@pytest.mark.parametrize(
    "relative",
    ["LICENSE", "LICENCE.md", "License-Apache", "LICENSE.BSD", "COPYING.txt", "LICENSE_1_0.txt"],
)
def test_real_licence_spellings_are_still_absorbed(tmp_path: Path, relative: str) -> None:
    """The other direction — otherwise the boundary fix only ever refuses."""
    _write(tmp_path, relative)
    non_source, _unsupported, unresolved = graphify_sdk.classify_unclassified(tmp_path, (relative,))
    assert non_source == (relative,)
    assert unresolved == ()


@pytest.mark.parametrize(
    "relative",
    [
        # CONTROL ARM for the UNDERSCORE half of the licence boundary, added by
        # Ray/Codesmith on 9e6fa630. My first boundary treated `_` as a
        # separator, so these were absorbed as licence files.
        "LICENSE_KEYS.py",
        "COPYING_utils.c",
        "LICENCE_helpers.rs",
    ],
)
def test_licence_followed_by_underscore_letter_still_blocks(tmp_path: Path, relative: str) -> None:
    _write(tmp_path, relative)
    non_source, _unsupported, unresolved = graphify_sdk.classify_unclassified(tmp_path, (relative,))
    assert unresolved == (relative,)
    assert non_source == ()


def test_boost_style_licence_with_underscore_digits_still_absorbs(tmp_path: Path) -> None:
    """The other direction: `_` followed by a DIGIT is Boost's licence spelling."""
    relative = _write(tmp_path, "LICENSE_1_0.txt")
    non_source, _unsupported, unresolved = graphify_sdk.classify_unclassified(tmp_path, (relative,))
    assert non_source == (relative,)
    assert unresolved == ()
