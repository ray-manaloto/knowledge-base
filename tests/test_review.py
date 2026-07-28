"""Tests for `kb_setup.review` — the local cross-family review receipt.

Both directions of every gate, per `probes-need-a-control-arm.md`: a receipt
check that has only ever been run against a good receipt is decoration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import review

_SHA = "9521853abcdef0123456789abcdef0123456789a"
_OTHER = "0000000abcdef0123456789abcdef0123456789b"


def _write(tmp_path: Path, **overrides: object) -> Path:
    """Write a valid receipt with ``overrides`` applied; return the repo root."""
    payload: dict[str, object] = {
        "sha": _SHA,
        "written_at": "2026-07-28T02:14:09+00:00",
        "fixed_point": "main",
        "lanes_ran": ["standards", "spec", "cold:codex", "silent-failure"],
        "lanes_skipped": [],
        "findings": 3,
        "blocking": 0,
    }
    payload.update(overrides)
    path = review.receipt_path(tmp_path, _SHA)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_valid_receipt_passes(tmp_path: Path) -> None:
    """The PASS arm: a well-formed receipt for this SHA is accepted."""
    ok, summary = review.receipt_state(_write(tmp_path), _SHA)
    assert ok
    assert "cold:codex" in summary


def test_write_receipt_roundtrips(tmp_path: Path) -> None:
    """`write_receipt` produces something `receipt_state` accepts."""
    review.write_receipt(
        tmp_path,
        review.Receipt(
            sha=_SHA,
            fixed_point="main",
            lanes_ran=("standards", "spec"),
            lanes_skipped=("cold:not-applicable-docs-only",),
            findings=0,
            blocking=0,
        ),
    )
    ok, summary = review.receipt_state(tmp_path, _SHA)
    assert ok
    assert "not-applicable-docs-only" in summary


def test_missing_receipt_fails(tmp_path: Path) -> None:
    """No receipt at all is the common case and must refuse."""
    ok, summary = review.receipt_state(tmp_path, _SHA)
    assert not ok
    assert "no review receipt" in summary


def test_amended_commit_invalidates_receipt(tmp_path: Path) -> None:
    """A receipt for one SHA must not authorise a different HEAD.

    This is the realistic break: amend or rebase after reviewing, and the
    reviewed bytes no longer exist.
    """
    ok, _ = review.receipt_state(_write(tmp_path), _OTHER)
    assert not ok


def test_copied_receipt_fails(tmp_path: Path) -> None:
    """A receipt filed under this SHA that RECORDS another is a copied file."""
    ok, summary = review.receipt_state(_write(tmp_path, sha=_OTHER), _SHA)
    assert not ok
    assert "different SHA" in summary


def test_unparsable_receipt_fails_closed(tmp_path: Path) -> None:
    """Garbage must never read as approval — a parse error is not a "no"."""
    path = review.receipt_path(tmp_path, _SHA)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json at all", encoding="utf-8")
    ok, summary = review.receipt_state(tmp_path, _SHA)
    assert not ok
    assert "unreadable" in summary


def test_non_object_receipt_fails_closed(tmp_path: Path) -> None:
    """Valid JSON that is not an object is still not a receipt."""
    path = review.receipt_path(tmp_path, _SHA)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    ok, _ = review.receipt_state(tmp_path, _SHA)
    assert not ok


def test_blocking_findings_fail(tmp_path: Path) -> None:
    """A blocking finding stops the ship."""
    ok, summary = review.receipt_state(_write(tmp_path, blocking=2), _SHA)
    assert not ok
    assert "2 blocking" in summary


def test_missing_blocking_count_fails_closed(tmp_path: Path) -> None:
    """An absent or non-integer blocking count is ambiguity, not consent."""
    ok, _ = review.receipt_state(_write(tmp_path, blocking="none"), _SHA)
    assert not ok


def test_no_lane_ran_fails(tmp_path: Path) -> None:
    """A receipt recording that nothing ran is not evidence that anything did."""
    ok, summary = review.receipt_state(_write(tmp_path, lanes_ran=[]), _SHA)
    assert not ok
    assert "no lane" in summary


@pytest.mark.parametrize("skipped", [["cold"], ["cold:"], [123]])
def test_unexplained_skip_fails(tmp_path: Path, skipped: list[object]) -> None:
    """A skip with no reason is a GAP, not a skip.

    "did not run" and "does not apply here" are different states; collapsing
    them is how a gap gets reported as coverage.
    """
    ok, summary = review.receipt_state(_write(tmp_path, lanes_skipped=skipped), _SHA)
    assert not ok
    assert "no reason" in summary


def test_explained_skip_passes(tmp_path: Path) -> None:
    """The control arm for the test above: a reasoned skip is accepted."""
    ok, _ = review.receipt_state(
        _write(tmp_path, lanes_skipped=["cold:not-applicable-docs-only"]), _SHA
    )
    assert ok


def test_empty_sha_fails(tmp_path: Path) -> None:
    """An unreadable HEAD must not pass; `head_sha` returns "" when git fails."""
    ok, summary = review.receipt_state(tmp_path, "")
    assert not ok
    assert "HEAD" in summary
