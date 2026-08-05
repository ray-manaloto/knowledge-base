"""`capture()`/`reattach()` — the hyperedge carry (#171 local mitigation, #175).

These are pure file-I/O unit tests: no subprocess, no graphify. The round-trip
through an actual `graphify_ops.label()` / `artifacts.generate()` run (proving
this module is correctly WIRED, not just correct in isolation) lives in
`test_prose_rederivation.py` and `test_artifacts.py` respectively — mirroring
where those two call sites' other behaviour is already tested.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import hyperedges

_HE1 = {"id": "he1", "nodes": ["a"]}
_HE2 = {"id": "he2", "nodes": ["a"]}

_TOP_ONLY: dict[str, object] = {
    "nodes": [{"id": "a"}],
    "links": [],
    "hyperedges": [_HE1],
}

_NESTED_ONLY: dict[str, object] = {
    "nodes": [{"id": "a"}],
    "links": [],
    "graph": {"hyperedges": [_HE1]},
}

_BOTH_AGREEING: dict[str, object] = {
    "nodes": [{"id": "a"}],
    "links": [],
    "graph": {"hyperedges": [_HE1]},
    "hyperedges": [_HE1],
}

_BOTH_DISAGREEING: dict[str, object] = {
    "nodes": [{"id": "a"}],
    "links": [],
    "graph": {"hyperedges": [_HE1]},
    "hyperedges": [_HE2],
}

_NEITHER: dict[str, object] = {"nodes": [{"id": "a"}], "links": [], "graph": {}}


def _write(tmp_path: Path, data: dict[str, object]) -> Path:
    p = tmp_path / "graph.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# --- capture() -------------------------------------------------------------


def test_capture_reads_top_level_only(tmp_path: Path) -> None:
    p = _write(tmp_path, _TOP_ONLY)
    assert hyperedges.capture(p) == [_HE1]


def test_capture_reads_nested_only(tmp_path: Path) -> None:
    """The `merge-graphs` shape (raw `node_link_data`, no top-level key at all)."""
    p = _write(tmp_path, _NESTED_ONLY)
    assert hyperedges.capture(p) == [_HE1]


def test_capture_reads_both_when_they_agree(tmp_path: Path) -> None:
    """The `to_json` shape: both slots present, and they agree.

    `data["graph"]` is a copy of `G.graph`, which already carries the same
    list `to_json` also writes to the top level (export.py:314).
    """
    p = _write(tmp_path, _BOTH_AGREEING)
    assert hyperedges.capture(p) == [_HE1]


def test_capture_raises_when_both_present_and_different(tmp_path: Path) -> None:
    """A file that disagrees with itself must not have one slot silently win."""
    p = _write(tmp_path, _BOTH_DISAGREEING)
    with pytest.raises(ValueError, match="disagrees with itself"):
        hyperedges.capture(p)


def test_capture_missing_file_returns_empty(tmp_path: Path) -> None:
    """A missing file is "nothing to carry", not an error.

    Lets a caller invoke this unconditionally before graph.json necessarily
    exists — see `capture`'s own docstring and `label()`'s call site.
    """
    assert hyperedges.capture(tmp_path / "nope.json") == []


def test_capture_neither_slot_present_returns_empty(tmp_path: Path) -> None:
    p = _write(tmp_path, _NEITHER)
    assert hyperedges.capture(p) == []


# --- capture_from_data() ------------------------------------------------------
#
# The pure half `graph_checks.assert_composition` reuses so it does not pay a
# second full read+parse of a several-hundred-MB file for the hyperedge list
# alone (#175 cold review, finding 2). Same reconciliation rules as `capture`
# — these are the same two fixtures, just fed in already-parsed.


def test_capture_from_data_matches_capture_on_the_same_content(tmp_path: Path) -> None:
    """The pure dict-level function must agree with the file-reading wrapper."""
    p = _write(tmp_path, _BOTH_AGREEING)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert hyperedges.capture_from_data(data) == hyperedges.capture(p) == [_HE1]


def test_capture_from_data_raises_on_disagreement_same_as_capture() -> None:
    """The refusal-on-disagreement behaviour must survive the split."""
    with pytest.raises(ValueError, match="disagrees with itself"):
        hyperedges.capture_from_data(_BOTH_DISAGREEING)


# --- reattach() --------------------------------------------------------------


def test_reattach_writes_both_slots_creating_them_as_needed(tmp_path: Path) -> None:
    p = _write(tmp_path, _NEITHER)  # "graph": {} present, no "hyperedges" anywhere

    hyperedges.reattach(p, [_HE1])

    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["hyperedges"] == [_HE1]
    assert data["graph"]["hyperedges"] == [_HE1]


def test_reattach_creates_a_missing_graph_key_too(tmp_path: Path) -> None:
    """A file with no `"graph"` key at all (not even `{}`) still gets one."""
    p = _write(tmp_path, {"nodes": [{"id": "a"}], "links": []})

    hyperedges.reattach(p, [_HE1])

    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["graph"] == {"hyperedges": [_HE1]}


def test_reattach_no_leftover_tmp_file_after_a_real_write(tmp_path: Path) -> None:
    p = _write(tmp_path, _NEITHER)

    hyperedges.reattach(p, [_HE1])

    assert list(tmp_path.glob("*.tmp")) == []


def test_reattach_restores_the_files_permissions(tmp_path: Path) -> None:
    """A reattach must not silently tighten graph.json's permissions.

    `tempfile.mkstemp` creates `0600`; `Path.replace` carries the TEMP file's
    bits onto the destination name, not the destination's own. Unfixed, one
    reattach would silently tighten graph.json from world-readable to
    owner-only — proven here, not just asserted in `hyperedges.py`'s docstring.
    """
    p = _write(tmp_path, _NEITHER)
    p.chmod(0o644)

    hyperedges.reattach(p, [_HE1])

    assert (p.stat().st_mode & 0o777) == 0o644


def test_reattach_empty_carry_against_an_already_empty_file_is_a_true_noop(
    tmp_path: Path,
) -> None:
    """The one no-op the interface specifies: nothing captured, nothing on disk.

    Proven two ways together, because either alone could be satisfied by a
    "no-op" that quietly writes back byte-identical content: the directory is
    made read-only first, so ANY write attempt (even just `mkstemp` creating
    its temp file) would raise; only once that passes are permissions restored
    and the file's bytes/mtime checked unchanged.
    """
    p = _write(tmp_path, _NEITHER)
    before = p.read_bytes()
    before_mtime_ns = p.stat().st_mtime_ns

    tmp_path.chmod(0o555)
    try:
        hyperedges.reattach(p, [])
    finally:
        tmp_path.chmod(0o755)

    assert p.read_bytes() == before
    assert p.stat().st_mtime_ns == before_mtime_ns


def test_reattach_nonempty_carry_writes_even_though_current_is_empty(
    tmp_path: Path,
) -> None:
    """CONTROL ARM for the no-op test: reattach() still writes when it must."""
    p = _write(tmp_path, _NEITHER)

    hyperedges.reattach(p, [_HE1])

    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["hyperedges"] == [_HE1]


def test_reattach_empty_carry_still_overwrites_nonempty_current_slots(
    tmp_path: Path,
) -> None:
    """Not the documented no-op case, which requires BOTH sides empty.

    An empty capture restores "this run started with nothing carried"
    unconditionally — `reattach` restores the captured pre-run state, it does
    not merge against whatever the just-finished run produced (module
    docstring).
    """
    p = _write(tmp_path, _TOP_ONLY)  # currently non-empty

    hyperedges.reattach(p, [])

    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["hyperedges"] == []
    assert data["graph"]["hyperedges"] == []
