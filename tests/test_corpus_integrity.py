# Copyright (c) 2026 Raymond Manaloto
"""`corpus_integrity` separates an altered fragment from an altered receipt.

Every test builds its own tree under `tmp_path` — nothing reads the real
`graphify-out/`, whose contents change with every corpus run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from kb_setup import corpus_integrity
from kb_setup.result import Rc

_NS = "9e1adc3b7df5"


def _stage(
    root: Path,
    ordinal: str,
    body: bytes,
    *,
    receipt: str | None = None,
    provider: str | None = None,
) -> Path:
    """Write one staged chunk. `receipt`/`provider` override the recorded digest."""
    chunk = root / "graphify-out/graphify-semantic-corpus-chunks" / _NS / "chunks" / ordinal
    chunk.mkdir(parents=True)
    (chunk / "semantic-fragment.json").write_bytes(body)
    true_digest = hashlib.sha256(body).hexdigest()
    (chunk / "receipt.json").write_text(
        json.dumps({"fragment_sha256": receipt or true_digest, "fragment_size": len(body)})
    )
    (chunk / "provider-receipt.json").write_text(
        json.dumps({"semantic_fragment_sha256": provider or true_digest})
    )
    return chunk


def test_clean_tree_reports_ok(tmp_path: Path) -> None:
    _stage(tmp_path, "0001", b'{"a":1}')
    findings, examined = corpus_integrity.scan(tmp_path)
    assert examined == 1
    assert findings == []
    assert corpus_integrity.integrity_main(tmp_path) == Rc.OK


def test_altered_fragment_is_caught_and_names_the_file(tmp_path: Path) -> None:
    """The 2026-08-23 shape: both receipts agree, the file does not."""
    # A one-byte loss, the shape `typos --write-changes` produced on the real
    # corpus. The bytes are a repeated filler character and NOT a word: two
    # earlier drafts used a real misspelling, and this repo's own formatter
    # (which reaches `tests/`) "corrected" each one, leaving both sides equal —
    # a fixture that could not fail. See #413; nothing here may be a dictionary
    # word, or the next `mise run fmt` disarms this test again.
    filler = b"\x78" * 6
    original = b'{"n":"' + filler + b'"}'
    chunk = _stage(tmp_path, "0002", original)
    (chunk / "semantic-fragment.json").write_bytes(original.replace(filler, filler[:-1]))

    findings, examined = corpus_integrity.scan(tmp_path)
    assert examined == 1
    assert [f.kind for f in findings] == ["fragment-altered"]
    assert "the FILE was altered" in findings[0].detail
    assert "-1 bytes" in findings[0].detail
    assert corpus_integrity.integrity_main(tmp_path) == Rc.FINDINGS


def test_receipts_disagreeing_is_a_different_finding(tmp_path: Path) -> None:
    """A single-receipt check would have called this an altered fragment."""
    _stage(tmp_path, "0003", b'{"a":1}', provider="0" * 64)

    findings, _ = corpus_integrity.scan(tmp_path)
    assert [f.kind for f in findings] == ["receipts-disagree"]
    assert "the fragment is not implicated" in findings[0].detail


def test_empty_tree_is_not_run_never_ok(tmp_path: Path) -> None:
    """A gate that never asked the question is not a pass."""
    findings, examined = corpus_integrity.scan(tmp_path)
    assert (findings, examined) == ([], 0)
    assert corpus_integrity.integrity_main(tmp_path) == Rc.NOT_RUN
    assert "NOT RUN" in corpus_integrity.render([], 0)


def test_unparsable_receipt_is_reported_not_skipped(tmp_path: Path) -> None:
    chunk = _stage(tmp_path, "0004", b'{"a":1}')
    (chunk / "receipt.json").write_text("{not json")

    findings, examined = corpus_integrity.scan(tmp_path)
    assert examined == 1
    assert [f.kind for f in findings] == ["unreadable"]


def test_render_forbids_the_dangerous_remedy(tmp_path: Path) -> None:
    """The report must steer away from re-stamping, which launders the evidence."""
    chunk = _stage(tmp_path, "0005", b'{"a":11}')
    (chunk / "semantic-fragment.json").write_bytes(b'{"a":1}')

    findings, examined = corpus_integrity.scan(tmp_path)
    text = corpus_integrity.render(findings, examined)
    assert "never" in text
    assert "re-stamp" in text


def test_scan_examines_every_chunk_not_just_the_first(tmp_path: Path) -> None:
    """A bound at the first chunk would report the corpus clean on chunk 2's drift."""
    _stage(tmp_path, "0001", b'{"a":1}')
    chunk = _stage(tmp_path, "0002", b'{"a":22}')
    (chunk / "semantic-fragment.json").write_bytes(b'{"a":2}')

    findings, examined = corpus_integrity.scan(tmp_path)
    assert examined == 2
    assert len(findings) == 1
    assert findings[0].chunk.endswith("0002")
