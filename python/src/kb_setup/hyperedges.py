# Copyright (c) 2026 Raymond Manaloto
"""Read the hyperedge list off a parsed graph.json, wherever it lives.

graph.json can carry hyperedges in two slots: the top-level `"hyperedges"` key
graphify's `export.to_json` always writes, and the nested `"graph"."hyperedges"`
key a raw networkx `node_link_data` write leaves instead (that key is just a
serialisation of `G.graph`). This module is the one place that reads BOTH and
refuses a file that disagrees with itself. Its caller is
`graph_checks.assert_composition`, which needs the list to verify that every
member id resolves against the built node set on every build.

RETIRED HERE, 2026-08-05, at the 0.9.34 bump: `capture()`/`reattach()` — a
carry that read the list before `graphify label`/`cluster-only` ran and wrote
it straight back after. It existed solely to work around two 0.9.33 defects
this repo filed and measured (5 hyperedges in, 0 out, on the aggregate):

- graphify#2484 — `merge-graphs` never relabelled hyperedge members (0/3
  resolved) and `nx.compose` kept only the last input's hyperedge set;
- graphify#2485 — `build_from_json` read only the top-level slot, so a
  nested-only file lost everything on the next label: rc 0, nothing on stderr.

0.9.34 fixes both, verified against the INSTALLED binary rather than the
release notes (`probes-need-a-control-arm.md`): members relabel and resolve
3/3, both inputs' hyperedges survive a merge, both slots are written and read,
and a full revalidation wipeout now warns loudly instead of silently writing
`[]`. Upstream ships regression tests for all three surfaces
(`test_hyperedge_roundtrip.py`, `test_hyperedge_member_shapes.py`,
`test_merge_graphs_cli.py`). Full evidence:
`docs/research/reports/2026-08-05-hyperedge-upstream-evidence.md` (the 0.9.33
arms) and `docs/currency/runs/2026-08-05-graphify.md` (the 0.9.34 re-run).

The carry was retired rather than kept "just in case"
(`tool-currency-and-native-first.md` rule 3) for a sharper reason than
redundancy: it restored the PRE-run list verbatim, bypassing member
revalidation by design. On 0.9.33 that bypass was the point — revalidation was
what destroyed the list. On 0.9.34 revalidation is correct and loud, so the
carry had become the only writer able to push dangling members past it,
recreating exactly the inconsistency `assert_composition` exists to refuse.
"""

from __future__ import annotations

from typing import cast

#: A hyperedge as graphify (and `sources/extractions/*.json` chunks) shape it:
#: `{"id": ..., "nodes": [...], ...}`. Re-declared rather than imported from
#: `prose` (which defines the same alias) — the two modules share a JSON shape,
#: not a dependency, and a one-line structural alias is not worth coupling them.
type Hyperedge = dict[str, object]


def capture_from_data(data: dict[str, object]) -> list[Hyperedge]:
    """The hyperedge list within an ALREADY-PARSED graph.json dict.

    Takes the parsed dict rather than a path so the caller does not pay a
    SECOND full read+parse of a several-hundred-MB file just to ask this one
    question. `graph_checks.assert_composition` is exactly that caller: it
    needs the top-level node id set from its own parse and the hyperedge list
    from the SAME file (#175 cold review, finding 2).
    """
    return _coalesce(_top(data), _nested(data))


def _top(data: dict[str, object]) -> list[Hyperedge] | None:
    """The top-level slot's value, or `None` if the key is absent or not a list."""
    if "hyperedges" not in data:
        return None
    value = data["hyperedges"]
    if not isinstance(value, list):
        return None
    # `list` is invariant, so even a narrowed `object` -> `list[...]` needs an
    # explicit assertion here — `isinstance` alone proves "a list", not "a list
    # of Hyperedge", and ty (correctly) will not infer the element type for us.
    return cast("list[Hyperedge]", value)


def _nested(data: dict[str, object]) -> list[Hyperedge] | None:
    """The `graph.hyperedges` slot's value, or `None` if either level is missing."""
    graph_meta = data.get("graph")
    # Split rather than `or`-combined: ty's narrowing across a negated `or` of
    # an isinstance check and an `in` check does not resolve `graph_meta` back
    # to a plain `dict` afterward, and the two-step form has no such gap.
    if not isinstance(graph_meta, dict):
        return None
    if "hyperedges" not in graph_meta:
        return None
    value = graph_meta.get("hyperedges")
    if not isinstance(value, list):
        return None
    return cast("list[Hyperedge]", value)


def _coalesce(top: list[Hyperedge] | None, nested: list[Hyperedge] | None) -> list[Hyperedge]:
    """Both slots' values -> the one list they name, or a `ValueError` if they differ."""
    if top is not None and nested is not None:
        if top == nested:
            return top
        raise ValueError(
            f"graph.json disagrees with itself: the top-level 'hyperedges' slot "
            f"has {len(top)} entr{'y' if len(top) == 1 else 'ies'}, "
            f"'graph.hyperedges' has {len(nested)} — refusing to silently pick one."
        )
    if top is not None:
        return top
    if nested is not None:
        return nested
    return []
