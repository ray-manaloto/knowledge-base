# Copyright (c) 2026 Raymond Manaloto
"""`capture_from_data()` — the two-slot hyperedge reader.

Pure dict-level unit tests: no subprocess, no graphify, no file I/O. The one
production caller is `graph_checks.assert_composition`, which feeds it the
already-parsed graph.json so the hyperedge list costs no second parse (#175
cold review, finding 2); `test_graph_checks.py` covers that wiring.

The carry (`capture()`/`reattach()`, #171 local mitigation, #175) was retired
at the graphify 0.9.34 bump along with its tests — upstream #2484/#2485 fixed
the losses it existed to sidestep, verified on the installed binary.
`hyperedges.py`'s module docstring records the mechanism and the evidence.
"""

from __future__ import annotations

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


def test_reads_top_level_only() -> None:
    """The `to_json` slot on its own (export.py always writes it)."""
    assert hyperedges.capture_from_data(_TOP_ONLY) == [_HE1]


def test_reads_nested_only() -> None:
    """The raw `node_link_data` shape (nested slot only, no top-level key)."""
    assert hyperedges.capture_from_data(_NESTED_ONLY) == [_HE1]


def test_reads_both_when_they_agree() -> None:
    """The full `to_json` shape: both slots present, and they agree.

    `data["graph"]` is a copy of `G.graph`, which already carries the same
    list `to_json` also writes to the top level (export.py:314).
    """
    assert hyperedges.capture_from_data(_BOTH_AGREEING) == [_HE1]


def test_raises_when_both_present_and_different() -> None:
    """A file that disagrees with itself must not have one slot silently win."""
    with pytest.raises(ValueError, match="disagrees with itself"):
        hyperedges.capture_from_data(_BOTH_DISAGREEING)


def test_neither_slot_present_returns_empty() -> None:
    assert hyperedges.capture_from_data(_NEITHER) == []
