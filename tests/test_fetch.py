# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.fetch — lossless source ingestion + the verbatim-token roundtrip contract.

Every check here pins its FAIL direction next to its pass. That is the whole
subject: the bug being fixed is `graphify add <url>` silently discarding 86-89%
of a reference page and exiting 0, so a test that only ever asserts PASSED would
reproduce the defect rather than catch it
(`.claude/rules/probes-need-a-control-arm.md`).

The roundtrip contract is the load-bearing piece. It samples verbatim tokens
(identifiers, defaults, signatures) from the RAW source and asserts each appears
byte-exact downstream. A rewriter or a truncator must make it FAIL — that
property is what makes it a contract rather than decoration.

No network: the fetch boundary is an injected callable, per tests/AGENTS.md
("prefer injecting the dependency over constructing it inside the function").
"""

from __future__ import annotations

import json
from pathlib import Path

import msgspec
import pytest
from kb_setup import fetch
from kb_setup.generated.fetch_receipt import FetchReceipt

FIXTURE = Path(__file__).parent / "fixtures" / "reference-sample.md"
RAW = FIXTURE.read_text(encoding="utf-8")

# graphify's real per-file cap, and the URL-path cap this whole module exists to
# bypass. Named so a future change to either is a visible diff, not a silent one.
GRAPHIFY_FILE_CAP = 20_000
GRAPHIFY_URL_CAP = 12_000


# --------------------------------------------------------------------------
# sampling — deterministic, and rich enough to be a real contract
# --------------------------------------------------------------------------


def test_sampling_finds_at_least_twenty_verbatim_tokens() -> None:
    """The contract needs >=20 tokens to be worth anything (goal clause 2)."""
    tokens = fetch.sample_verbatim_tokens(RAW, minimum=20)
    assert len(tokens) >= 20, f"only found {len(tokens)}: {tokens}"


def test_sampling_is_deterministic_across_calls() -> None:
    """Same input -> same tokens. Without this, repeatability is unmeasurable."""
    assert fetch.sample_verbatim_tokens(RAW, minimum=20) == fetch.sample_verbatim_tokens(
        RAW, minimum=20
    )


def test_sampling_captures_the_load_bearing_tokens_not_just_prose() -> None:
    """Defaults and identifiers are the product; prose is not.

    The advisor's decisive point: reference docs carry their load-bearing tokens
    INSIDE prose ("defaults to `checkOrigin: false`"), which is exactly what a
    prose rewriter would alter. So the sample must reach them.
    """
    tokens = set(fetch.sample_verbatim_tokens(RAW, minimum=20))
    for must in ("checkOrigin", "'ignore'", "4321", "astro@4.9.0", "getCollection()"):
        assert must in tokens, f"{must!r} missing from sample: {sorted(tokens)}"


def test_sampling_ignores_pure_prose_words() -> None:
    """Control arm for the sampler: it must NOT just return every word.

    A sampler that returned all words would make the roundtrip contract
    tautological on any superset, and vacuous as a fidelity check.
    """
    tokens = set(fetch.sample_verbatim_tokens(RAW, minimum=20))
    for prose in ("When", "enabled", "Controls", "matches", "the"):
        assert prose not in tokens


# --------------------------------------------------------------------------
# the roundtrip contract — BOTH directions (goal clause 3)
# --------------------------------------------------------------------------


def test_roundtrip_passes_when_content_survives_intact() -> None:
    """The pass arm. Without it, the FAIL tests are satisfied by a broken checker."""
    tokens = fetch.sample_verbatim_tokens(RAW, minimum=20)
    assert fetch.roundtrip_missing(tokens, RAW) == []


def test_roundtrip_passes_when_content_is_merely_reordered_or_sliced_losslessly() -> None:
    """Graphify slices files; concatenated slices reproduce the text exactly.

    So the contract must pass on a lossless slice-and-rejoin, or it would flag
    graphify's own (verified lossless) chunking as corruption.
    """
    mid = len(RAW) // 2
    rejoined = RAW[:mid] + RAW[mid:]
    tokens = fetch.sample_verbatim_tokens(RAW, minimum=20)
    assert fetch.roundtrip_missing(tokens, rejoined) == []


def test_roundtrip_fails_on_truncation() -> None:
    """THE regression. This is the graphify `markdown[:12000]` bug in miniature.

    Truncating the tail must be detected. Measured on the real pages this
    module exists for: the 12k cut discards 89% of the Astro config reference,
    87% of Scrapy settings, 86% of jest expect.
    """
    truncated = RAW[: len(RAW) // 3]
    tokens = fetch.sample_verbatim_tokens(RAW, minimum=20)
    missing = fetch.roundtrip_missing(tokens, truncated)
    assert missing, "truncation went undetected — the contract is decoration"


def test_roundtrip_fails_on_a_rewritten_default() -> None:
    """A lossy rewriter perturbs tokens scattered through text that REMAINS present.

    The advisor named this as the deciding risk: worse than truncation, because
    truncation loses a contiguous tail you might notice, while a rewrite leaves
    plausible-looking content that is wrong. One flipped default must fail.
    """
    corrupted = RAW.replace("**Default:** `4321`", "**Default:** `3000`")
    assert corrupted != RAW, "fixture drifted — the mutation no longer applies"
    tokens = fetch.sample_verbatim_tokens(RAW, minimum=20)
    assert "4321" in fetch.roundtrip_missing(tokens, corrupted)


def test_roundtrip_fails_when_a_code_fence_is_dropped() -> None:
    """Boilerplate strippers and markdown converters lose fenced blocks."""
    without_fence = RAW.replace("checkOrigin: false,", "")
    assert without_fence != RAW
    tokens = fetch.sample_verbatim_tokens(RAW, minimum=20)
    assert fetch.roundtrip_missing(tokens, without_fence)


# --------------------------------------------------------------------------
# acceptance gate — status AND body volume (the two ways we were burned)
# --------------------------------------------------------------------------


def test_gate_rejects_non_200_even_when_the_body_is_large() -> None:
    """A large body on a non-200 must still be rejected.

    Measured 2026-07-24: `docs.astro.build/...index.md` 404'd with 38,469 bytes
    of HTML, and `jestjs.io/llms.txt` 404'd with 21,651. A status-blind fetcher
    ingests a 404 page as an article.
    """
    assert fetch.gate(status=404, text="x" * 38_469) is not None


def test_gate_rejects_an_undersized_body_on_a_200() -> None:
    """The SPA-shell case: a render/HTTP success signal is satisfied by a shell."""
    assert fetch.gate(status=200, text="# Title\n") is not None


def test_gate_accepts_a_real_body() -> None:
    """Control arm: a gate that rejects everything is not a gate."""
    assert fetch.gate(status=200, text=RAW) is None


# --------------------------------------------------------------------------
# repeatability (goal clause 4)
# --------------------------------------------------------------------------


def test_content_hash_is_stable_for_identical_input() -> None:
    assert fetch.content_hash(RAW) == fetch.content_hash(RAW)


def test_content_hash_differs_for_one_changed_character() -> None:
    """Control arm: a hash that never changes cannot witness repeatability."""
    assert fetch.content_hash(RAW) != fetch.content_hash(RAW + " ")


# --------------------------------------------------------------------------
# the ingest path itself — bypasses the URL cap (goal clause 1)
# --------------------------------------------------------------------------


def test_fetch_source_uses_the_injected_boundary_and_never_truncates() -> None:
    """A body far larger than graphify's URL cap must survive whole."""
    big = RAW * 40  # ~37k chars: over the 12k URL cap, over the 20k file cap
    assert len(big) > GRAPHIFY_URL_CAP
    result = fetch.fetch_source(
        "https://example.com/ref", fetcher=lambda _u: (200, big, "text/markdown")
    )
    assert result.text == big
    assert len(result.text) > GRAPHIFY_URL_CAP


def test_fetch_source_surfaces_the_status_it_saw() -> None:
    """Principle 8: a gate reports the observed status, never a prose summary.

    `kb_setup.pr` printing "PR create failed" with the HTTP status discarded is
    why this is a contract and not a preference.
    """
    with pytest.raises(fetch.FetchRejectedError) as exc:
        fetch.fetch_source(
            "https://example.com/gone", fetcher=lambda _u: (404, "x" * 38_469, "text/html")
        )
    assert "404" in str(exc.value)


def test_write_source_roundtrips_byte_exact_through_disk(tmp_path: Path) -> None:
    """The whole point of routing through a FILE: what we fetched is what lands."""
    out = fetch.write_source(tmp_path, "ref", RAW, url="https://example.com/ref")
    written = out.read_text(encoding="utf-8")
    tokens = fetch.sample_verbatim_tokens(RAW, minimum=20)
    assert fetch.roundtrip_missing(tokens, written) == []


def test_write_source_is_repeatable(tmp_path: Path) -> None:
    """Same input twice -> byte-identical file (goal clause 4)."""
    a = fetch.write_source(tmp_path, "ref", RAW, url="https://example.com/ref")
    first = fetch.content_hash(a.read_text(encoding="utf-8"))
    b = fetch.write_source(tmp_path, "ref", RAW, url="https://example.com/ref")
    second = fetch.content_hash(b.read_text(encoding="utf-8"))
    assert first == second


def test_generated_receipt_model_decodes_a_valid_receipt() -> None:
    """The committed schema model accepts the complete current wire contract."""
    payload = {
        "schema_version": 1,
        "sources": [
            {
                "url": "https://example.com/ref",
                "artifact": "sources/ref.md",
                "content_sha256": "a" * 64,
                "content_bytes": 10,
                "content_chars": 10,
                "prefix_sha256": "b" * 64,
                "tail_sha256": "c" * 64,
                "read_to_eof": True,
                "truncated": False,
            }
        ],
    }

    decoded = msgspec.json.decode(json.dumps(payload).encode(), type=FetchReceipt)

    assert decoded.sources[0].artifact == "sources/ref.md"


def test_generated_receipt_model_rejects_unknown_fields() -> None:
    """The generator's generic base class keeps strict-schema decoding active."""
    payload = {
        "schema_version": 1,
        "sources": [
            {
                "url": "https://example.com/ref",
                "artifact": "sources/ref.md",
                "content_sha256": "a" * 64,
                "content_bytes": 10,
                "content_chars": 10,
                "prefix_sha256": "b" * 64,
                "tail_sha256": "c" * 64,
                "read_to_eof": True,
                "truncated": False,
                "unreviewed_extension": "must not be silently accepted",
            }
        ],
    }

    with pytest.raises(msgspec.ValidationError, match="unknown field"):
        msgspec.json.decode(json.dumps(payload).encode(), type=FetchReceipt)


def test_receipt_verifies_the_complete_body_and_both_cutoff_witnesses(tmp_path: Path) -> None:
    artifact = fetch.write_source(tmp_path / "sources", "ref", RAW, url="https://example.com/ref")
    receipt = fetch.write_receipt(
        tmp_path,
        Path("sources/downloads.receipts.json"),
        artifact,
        RAW,
        url="https://example.com/ref",
    )

    ok, failures = fetch.verify_receipt(tmp_path, receipt)

    assert ok, failures
    row = json.loads(receipt.read_text(encoding="utf-8"))["sources"][0]
    assert row["content_bytes"] == len(RAW.encode("utf-8"))
    assert row["read_to_eof"] is True
    assert row["truncated"] is False


def test_receipt_fails_when_the_artifact_tail_is_cut(tmp_path: Path) -> None:
    artifact = fetch.write_source(tmp_path / "sources", "ref", RAW, url="https://example.com/ref")
    receipt = fetch.write_receipt(
        tmp_path,
        Path("sources/downloads.receipts.json"),
        artifact,
        RAW,
        url="https://example.com/ref",
    )
    artifact.write_text(artifact.read_text(encoding="utf-8")[:-80], encoding="utf-8")

    ok, failures = fetch.verify_receipt(tmp_path, receipt)

    assert not ok
    assert any("tail_sha256 mismatch" in failure for failure in failures)


def test_verify_receipts_defaults_to_every_source_receipt(tmp_path: Path) -> None:
    artifact = fetch.write_source(tmp_path / "sources", "ref", RAW, url="https://example.com/ref")
    fetch.write_receipt(
        tmp_path,
        Path("sources/downloads.receipts.json"),
        artifact,
        RAW,
        url="https://example.com/ref",
    )

    assert fetch.verify_receipts(tmp_path) == (True, ())


def test_verify_receipts_fails_when_default_scope_is_empty(tmp_path: Path) -> None:
    assert fetch.verify_receipts(tmp_path) == (
        False,
        ("no source receipt files found",),
    )


def test_receipt_path_cannot_escape_the_repository(tmp_path: Path) -> None:
    artifact = fetch.write_source(tmp_path / "sources", "ref", RAW, url="https://example.com/ref")
    with pytest.raises(ValueError, match="inside the repository"):
        fetch.write_receipt(
            tmp_path, Path("../receipt.json"), artifact, RAW, url="https://example.com/ref"
        )


# --------------------------------------------------------------------------
# upstream-source preference (the fetch strategy that wins where it applies)
# --------------------------------------------------------------------------


def test_upstream_raw_url_maps_a_known_docs_host() -> None:
    got = fetch.upstream_raw_url("https://jestjs.io/docs/expect")
    assert got is not None
    assert got.startswith("https://raw.githubusercontent.com/")
    assert got.endswith(".md")


def test_upstream_raw_url_returns_none_for_an_unmapped_host() -> None:
    """Control arm: a mapper that answers for everything is guessing."""
    assert fetch.upstream_raw_url("https://example.invalid/whatever") is None
