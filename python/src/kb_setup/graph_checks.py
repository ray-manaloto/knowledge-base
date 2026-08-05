"""In-build composition invariants for the merged aggregate graph (#175).

`_merge_sources_into` (graph.py) composes every corpus sub-graph AND the self
sub-graph in ONE `merge-graphs` call so graphify's `prefix_graph_for_global`
prefixes each input's node ids exactly once (#120: a pairwise loop that fed the
accumulator back in re-prefixed everything already merged, measured at 33% of
the whole file — see `_merge_sources_into`'s own docstring for the full
measurement). `tests/test_merge_prefixes_once.py` proves that invariant
against the real binary — but a test only runs when the suite runs. This
module checks the SAME invariant inside every `build()`, against the actual
artifact `build()` just produced, so a regression that reintroduces pairwise
merging (or any other path that feeds an already-merged graph back into
`merge-graphs`) is caught on the very next build, not only on the next
`mise run test`.

The hyperedge check exists for a related but distinct reason. `hyperedges.py`'s
module docstring documents a MEASURED loss: graphify's own `label`/
`cluster-only` round-trip silently drops any hyperedge whose member ids fail
revalidation against the just-rebuilt node set (5 -> 0, measured on this
repo's aggregate). `hyperedges.capture`/`reattach` sidesteps that by carrying
the pre-run list through untouched — which is only correct so long as the ids
it carries still resolve. If an earlier step in the SAME build (a merge, a
re-prefix) silently changed a member's id without anything noticing, `capture`
would faithfully carry forward a reference to a node that no longer exists — a
durable, self-inflicted version of exactly the loss `hyperedges.py` exists to
prevent, and one that mechanism cannot see because it only ever compares a
list to itself. This function is the check FOR that: it runs on the file
`graphify_ops.label` just captured from and re-derived the prose graph from,
so a dangling member is caught here rather than discovered later by a query or
a prose derivation silently missing it.
"""

from __future__ import annotations

import json
from pathlib import Path

from kb_setup import hyperedges

#: How many offending ids/members a refusal prints before truncating.
#: Composition violations should be rare-to-never in a healthy build; a
#: handful is enough to name the CLASS of break without dumping the graph.
_MAX_EXAMPLES = 5

#: A node id may carry at most this many `::` separators — one, from exactly
#: one `merge-graphs` prefix pass. Corpus ids are `<source>::<local>`, the self
#: sub-graph's are `.self-graph::<local>`; semantic doc nodes (added via
#: `_merge_docs.py`'s `build_merge`, which never goes through `merge-graphs`)
#: carry none. Two or more is the #120 signature: an input merged more than
#: once, each pass stacking its own prefix on top of the last.
_MAX_SEPARATORS = 1


def assert_composition(graph_path: Path, *, tag: str) -> None:
    """Refuse a `graph.json` that violates this build's composition invariants.

    Loads the whole file with a plain `json.load` EXACTLY ONCE — accepted
    here, not elsewhere in this codebase's stream-conscious writers, because
    this function is the only reader either count needs, and it needs both
    from the SAME parsed dict. This docstring used to justify a single parse
    by claiming `graphify_ops.label`'s subprocess "already loads the same file
    whole in the same build" — true, but not a shared cost: that load happens
    inside a separate `graphify` PROCESS that has already exited by the time
    this function runs, so it bought this process nothing. The actual
    mechanism used to call `hyperedges.capture(graph_path)` for the hyperedge
    list on top of this function's own `json.loads` of the same bytes — TWO
    live parses of a several-hundred-MB file at once, roughly double the
    ~3.7x-of-file-size peak RSS `kb_setup.insights` measures for one (#175
    cold review, finding 2). `hyperedges.capture_from_data` reads the
    hyperedge list off THIS function's own already-parsed `data` instead.

    Enforces two things: (a) every node id contains at most
    :data:`_MAX_SEPARATORS` `::` separators, and (b) every hyperedge member —
    read via :func:`kb_setup.hyperedges.capture_from_data`, which already
    reconciles graph.json's two possible hyperedge slots — resolves to a node
    id in this same file. Raises `SystemExit` with counts and a few example
    offenders on either violation; returns `None` on success.

    `tag` names the CALLER (`"kb-build"` or `"kb-watch"`, this function's only
    two call sites) in every printed line — the same discipline
    `stamps.refresh_after_regen` uses, and for the same reason: a message
    tagged with the wrong caller sends someone looking at the wrong task.
    There is deliberately no default; a caller that forgot to pass one would
    silently mislabel every line it prints, which is worse than a `TypeError`
    at the call site.
    """
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    ids = {str(n["id"]) for n in nodes if isinstance(n, dict) and "id" in n}

    bad_depth = sorted(nid for nid in ids if nid.count("::") > _MAX_SEPARATORS)

    carried = hyperedges.capture_from_data(data)
    dangling: list[str] = []
    members_seen = 0
    for edge in carried:
        members = edge.get("nodes", edge.get("members"))
        if not isinstance(members, list):
            continue
        members_seen += len(members)
        dangling.extend(str(m) for m in members if str(m) not in ids)

    # Printed on EVERY call to this function — kb-build or kb-watch — pass or
    # fail. The counts are already computed here and nothing else reports
    # them: `kb-insights` covers provenance, spans, cross-origin and size but
    # not hyperedges, so before this line the only way to answer "how many
    # hyperedges does the aggregate hold, and do their members resolve?" was
    # an ad-hoc probe. #176 asks for that figure to be re-measured after every
    # change, and a measurement you have to hand-roll is one that stops being
    # taken. Silence here would also be ambiguous in the worst direction —
    # "no complaint" reads identically whether there are five healthy
    # hyperedges or none at all.
    print(
        f"[{tag}] composition: {len(ids)} node ids (max '::' depth "
        f"{max((nid.count('::') for nid in ids), default=0)}), {len(carried)} "
        f"hyperedge(s) / {members_seen} member(s), {len(dangling)} dangling"
    )

    if not bad_depth and not dangling:
        return

    lines = [f"graph.json fails a build composition invariant ({graph_path}):"]
    if bad_depth:
        lines.append(
            f"  {len(bad_depth)} node id(s) carry more than {_MAX_SEPARATORS} '::' "
            f"separator(s) — an input was merged more than once (the #120 shape, "
            f"which pairwise/sequential merging or feeding graph.json back into "
            f"merge-graphs both reproduce). e.g. {bad_depth[:_MAX_EXAMPLES]}"
        )
    if dangling:
        lines.append(
            f"  {len(dangling)} hyperedge member reference(s) do not resolve to a "
            f"node id — a carried hyperedge now points at a node the merge "
            f"renamed or dropped. e.g. {dangling[:_MAX_EXAMPLES]}"
        )
    raise SystemExit("\n".join(lines))
