# Copyright (c) 2026 Raymond Manaloto
"""Pin the reviewed agentsview/hk detect exceptions and their source manifests (#884)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from kb_setup import graph, graphify_health, graphify_sdk
from kb_setup import manifest as mf
from kb_setup.generated.reviewed_classification import ReviewedClassification

_EXPECTED_FILES = (
    (
        "agentsview",
        "docker/debian-mirrors.list",
        "41f9bd663ee0a1ff6bbf238824230c192e0026c8ad81b79402c637794f8dbc58",
        "ff8fb4e84823b9583eba417afc243140caabdcb0",
        ReviewedClassification.reviewed_build_toolchain_config,
    ),
    (
        "agentsview",
        "docker/debian-security-mirrors.list",
        "0905a5d6fed2827d21654a5aed2da1fe02d47e938a6e0e01da6661435cca0343",
        "ff8fb4e84823b9583eba417afc243140caabdcb0",
        ReviewedClassification.reviewed_build_toolchain_config,
    ),
    (
        "hk",
        "docs/.vitepress/fonts/LiberationMono-Bold.ttf",
        "626655e94dd82f3f42549daf995c921b0915fa8ab1f4b839559e8892ea41d240",
        "bb2303bf2a138c4d5d27eac9604ade1ff2fc50de",
        ReviewedClassification.reviewed_binary_docs_asset,
    ),
    (
        "hk",
        "docs/.vitepress/fonts/LiberationMono-Regular.ttf",
        "395fa5ab8d40c8eba390ced528744ea75a7f69aabf3e68b6f925ca0e39a27370",
        "bb2303bf2a138c4d5d27eac9604ade1ff2fc50de",
        ReviewedClassification.reviewed_binary_docs_asset,
    ),
    (
        "hk",
        "docs/.vitepress/fonts/SpaceGrotesk.ttf",
        "acad6de1fc93436f5c0f1f4137751ef04f1aea3063e7036535970ffcfbd79f72",
        "bb2303bf2a138c4d5d27eac9604ade1ff2fc50de",
        ReviewedClassification.reviewed_binary_docs_asset,
    ),
)


def test_reviewed_agentsview_hk_inventory_is_exact() -> None:
    actual = [
        (
            item.source_name,
            item.relative_path,
            item.content_sha256,
            item.pinned_commit,
            item.classification,
        )
        for item in graph._EXPECTED_UNCLASSIFIED
        if item.source_name in {"agentsview", "hk"}
    ]

    assert len(actual) == len(_EXPECTED_FILES)
    assert set(actual) == set(_EXPECTED_FILES)


@pytest.mark.parametrize("source_name", ["agentsview", "hk"])
def test_reviewed_agentsview_hk_pins_match_manifests(source_name: str) -> None:
    sources = Path(__file__).resolve().parent.parent / "sources"
    pinned_commit = mf.load(sources / f"{source_name}.manifest").commit
    entries = [item for item in graph._EXPECTED_UNCLASSIFIED if item.source_name == source_name]

    assert entries
    assert all(item.pinned_commit == pinned_commit for item in entries)


@pytest.mark.parametrize(
    "classification",
    [
        ReviewedClassification.reviewed_build_toolchain_config,
        ReviewedClassification.reviewed_binary_docs_asset,
    ],
)
def test_reviewed_detection_rejects_changed_bytes(
    tmp_path: Path, classification: ReviewedClassification
) -> None:
    """Exercise the real absorption predicate with matching and changed on-disk bytes."""
    relative_path = "docs/reviewed.asset"
    path = tmp_path / relative_path
    path.parent.mkdir()
    path.write_bytes(b"reviewed bytes\n")
    expected = graphify_health.ExpectedUnclassifiedFile(
        source_name="hk",
        relative_path=relative_path,
        content_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        pinned_commit="bb2303bf2a138c4d5d27eac9604ade1ff2fc50de",
        classification=classification,
    )

    accepted = graphify_sdk.source_detection_policy(tmp_path, "hk", (expected,))
    assert accepted.optional_unclassified_paths == (relative_path,)

    path.write_bytes(b"changed bytes\n")
    changed = graphify_sdk.source_detection_policy(tmp_path, "hk", (expected,))
    assert changed.optional_unclassified_paths == ()
