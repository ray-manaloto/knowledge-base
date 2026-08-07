# Copyright (c) 2026 Raymond Manaloto
"""Structural direction checks over an extraction chunk's edges.

Added after a cold review found **63 findings** in one round's chunks, nearly all
of them reversed or over-strong edges — and after the hand-written check that was
supposed to catch that class **reported 0 while ~25 were live**. That check
looked only for a `*_doc` node as the SOURCE of a `part_of` edge, so it was
structurally blind to `plugin part_of skill`, where neither endpoint is a `_doc`
node. It verified one shape of the bug and announced the class clean.

WHAT THIS CANNOT SEE — read this before trusting a green run
------------------------------------------------------------
**Semantic direction is not mechanically checkable, and this module does not
claim to check it.** `bun_requirement requires supported_set` is exactly
backwards ("Bun requires the channels"), yet it contains no cycle, no self-edge
and no unknown verb — nothing here fires on it. Deciding that edge needs a reader
who knows what Bun is.

What IS mechanically decidable is a *contradiction*: an edge set that cannot be
true no matter what the nodes mean. A cycle in `part_of` says A contains B and B
contains A. A self-edge says A contains itself. Those are wrong without reading a
single label, which is why they belong in a gate and the rest belongs in review.

The advisory checks below are named heuristics, reported separately and never
mixed into the hard failures, because a lint that cries wolf gets switched off —
the same reason a naive node-id check would have to classify same-`source_file`
reuse as legitimate (#231).
"""

from __future__ import annotations

import re
from typing import Any

#: THERE IS DELIBERATELY NO RELATION ALLOWLIST, and the first version of this
#: module had one. It listed the fifteen verbs `.claude/workflows/kb-extract.js`
#: names and failed anything else — because that prompt's list reads
#: "(enables, requires, part_of, contrasts_with, mitigates, defines, verifies,
#: routes_to, ...)" and the trailing "..." was read as decoration.
#:
#: Run against the real corpus it fired **1,936 times across 25 chunks**, on
#: **308 distinct verbs** in ordinary use — `conceptually_related_to` (575),
#: `rationale_for` (307), `constrains` (64), `explains` (43). The vocabulary is
#: OPEN by design; a closed gate over it red-lights every committed chunk and
#: gets switched off, which is worse than no gate.
#:
#: The replacement was measured too, and ALSO refuted. "A verb used exactly once
#: in the corpus is a plausible typo" sounds like the signal the allowlist was
#: reaching for; run over the 25 committed chunks it flags **182 of the 308
#: verbs**. A check that calls 59% of the vocabulary suspicious is not narrowing
#: anything — the distribution is simply long-tailed. It was written, measured,
#: and deleted rather than shipped as advisory noise nobody would read.
#:
#: What is left is deliberately small and high-precision: three contradictions
#: that need no semantics, plus one named naming-convention warning. Over the
#: whole corpus that is **1 hard failure and 10 advisories** — a signal a reader
#: will actually look at.

#: Relations whose meaning is TRANSITIVE and ANTISYMMETRIC, so a cycle among them
#: is a contradiction rather than a modelling choice. `part_of` cannot be
#: circular (A inside B inside A); neither can a dependency.
_ACYCLIC = ("part_of", "requires", "depends_on")

#: The extraction prompt says of `contrasts_with`: "symmetric in meaning — emit
#: exactly ONE edge, not both." Both directions present is a contract violation,
#: and it double-weights the pair in every traversal.
_SYMMETRIC = ("contrasts_with",)

#: ADVISORY ONLY. A `requires` edge whose SOURCE is named like a prerequisite is
#: usually reversed: the rule is DEPENDENT -> DEPENDENCY, so a node called
#: `bun_requirement` or `worktree_needs_a_commit` belongs on the TARGET side.
#: Every one of the reversed `requires` edges the cold lane found in the round
#: that motivated this module matched this pattern. It is a NAMING convention
#: check, not a semantic one, so it is reported as a warning.
_PREREQ_NAMED = re.compile(
    r"(?:^|_)(requirement|requirements|needs|need|prereq|prerequisite|required)(?:_|$)"
)


def _edge_pairs(edges: list[Any], relation: str) -> set[tuple[str, str]]:
    return {
        (e["source"], e["target"])
        for e in edges
        if isinstance(e, dict)
        and e.get("relation") == relation
        and isinstance(e.get("source"), str)
        and isinstance(e.get("target"), str)
    }


def _find_cycle(pairs: set[tuple[str, str]]) -> list[str] | None:
    """Return one cycle as a node list, or None.

    Iterative DFS with an explicit stack: a chunk is small, but a recursive walk
    would raise RecursionError on a pathological chain instead of reporting the
    problem, and a validator that crashes on bad input is not a validator.
    """
    adj: dict[str, list[str]] = {}
    for s, t in pairs:
        adj.setdefault(s, []).append(t)
    colour: dict[str, int] = {}  # 0 = unvisited, 1 = on stack, 2 = done
    for root in list(adj):
        if colour.get(root, 0) != 0:
            continue
        stack: list[tuple[str, int]] = [(root, 0)]
        path: list[str] = []
        colour[root] = 1
        path.append(root)
        while stack:
            node, idx = stack.pop()
            kids = adj.get(node, [])
            if idx < len(kids):
                stack.append((node, idx + 1))
                nxt = kids[idx]
                state = colour.get(nxt, 0)
                if state == 1:
                    return [*path[path.index(nxt) :], nxt]
                if state == 0:
                    colour[nxt] = 1
                    path.append(nxt)
                    stack.append((nxt, 0))
            else:
                colour[node] = 2
                if path and path[-1] == node:
                    path.pop()
    return None


def _scan_edges(edges: list[Any], label: str) -> tuple[list[str], list[str]]:
    """Per-edge checks: self-edges (hard) and prerequisite-named sources (soft)."""
    hard: list[str] = []
    soft: list[str] = []
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            continue
        src, tgt, rel = e.get("source"), e.get("target"), e.get("relation")
        if src is not None and src == tgt:
            hard.append(f"{label}: edge[{i}] is a SELF-EDGE: {src!r} {rel} itself")
        if (
            rel == "requires"
            and isinstance(src, str)
            and _PREREQ_NAMED.search(src)
            and isinstance(tgt, str)
            and not _PREREQ_NAMED.search(tgt)
        ):
            soft.append(
                f"{label}: edge[{i}] {src!r} requires {tgt!r} — the SOURCE is named "
                f"like a prerequisite. `requires` is DEPENDENT -> DEPENDENCY, so this "
                f"is probably reversed. Read it aloud to decide"
            )
    return (hard, soft)


def check(chunk: object, *, label: str = "chunk") -> tuple[list[str], list[str]]:
    """`(hard_problems, advisories)` for one chunk's edges.

    Hard problems are contradictions — true regardless of what the nodes mean.
    Advisories are named heuristics; a caller may print them but must not fail on
    them, or the gate becomes noise and gets turned off.
    """
    if not isinstance(chunk, dict):
        return ([f"{label}: not a JSON object"], [])
    edges = chunk.get("edges")
    if not isinstance(edges, list):
        return ([], [])  # `chunks.validate` already reports a non-list `edges`.

    hard, soft = _scan_edges(edges, label)

    for rel in _ACYCLIC:
        cycle = _find_cycle(_edge_pairs(edges, rel))
        if cycle:
            hard.append(
                f"{label}: `{rel}` has a CYCLE: {' -> '.join(cycle)}. "
                f"`{rel}` is antisymmetric, so at least one of these edges is reversed"
            )

    for rel in _SYMMETRIC:
        pairs = _edge_pairs(edges, rel)
        seen: set[tuple[str, str]] = set()
        for s, t in sorted(pairs):
            if (t, s) in pairs and (t, s) not in seen:
                seen.add((s, t))
                hard.append(
                    f"{label}: `{rel}` emitted in BOTH directions between {s!r} and "
                    f"{t!r}; the extraction contract says emit exactly one"
                )

    return (hard, soft)
