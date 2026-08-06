"""Merge a committed doc-extraction chunk into graphify-out/graph.json.

Runs under graphify's BUNDLED interpreter (imports graphify), invoked by
graph.py via subprocess — NOT under the KB repo's uv python.

Usage: python _merge_docs.py <chunk.json> <source_root_abs> <graph.json>
                             [--prior-nodes N] [--counts-out PATH]

`--prior-nodes` is how many nodes `graph.json` held BEFORE this merge, when the
caller could establish that for free (`kb_setup.graph_counts`). Given it, the
merge line asserts its own arithmetic instead of leaving the subtraction to a
human — see `_report` below. Omitted, the line says so; it never guesses.

`--counts-out` is a path this script writes its post-merge counts to, so the
caller — which runs under a DIFFERENT interpreter and cannot import anything
from here — can record them in the ledger. The fingerprint that makes those
counts trustworthy is added by the caller, deliberately: duplicating the
`size:mtime_ns` formula into this file would give the ledger two owners that
could drift into disagreeing about what "the graph moved" means.

MERGE-ONLY (#169, #175). This used to also re-cluster (Louvain), score
cohesion, find god nodes and surprising connections, and render GRAPH_REPORT.md
— once PER CHUNK, i.e. once per source in the doc-replay loop. Measured: 17 of
those 18 per-chunk passes were discarded and never read, because `build()`
replays every committed chunk in one run and only the LAST chunk's report
survived on disk. The real clustering/labelling now happens exactly once, in
`build()`, via `graphify_ops.label` — AFTER every chunk (this script, run once
per chunk) and the code layer have all landed. This script's only remaining
job is: merge one chunk in, hand `to_json` a communities mapping, write.
"""

import json
import sys
from pathlib import Path

# graphify is imported INSIDE main(), not at module scope, so the pure-python
# helpers below (`_opt`, `_report`) can be imported and tested from the repo's
# own uv interpreter — which has no graphify and never will, since this script
# is the one thing that deliberately runs under graphify's bundled one. The
# arithmetic in `_report` is the whole point of #191; leaving it unreachable by
# the test suite would make it the kind of check that is only ever verified by
# the incident it was written for.


def _communities_from_graph(g: object) -> dict[int, list[str]]:
    """Reconstruct `{community_id: [node_id, ...]}` from each node's own attr.

    Mirrors graphify's own `graphify.serve._communities_from_graph` (verified
    in the installed 0.9.33 source, `serve.py`:69-76) rather than importing
    it: that function lives in the MCP-server module for an unrelated reason
    (answering a live query), and reaching into a leading-underscore symbol
    across modules for a six-line, dependency-free algorithm is more coupling
    than the reuse is worth.

    `to_json` (`export.py`:232) takes `communities: dict[int, list[str]]` as a
    REQUIRED positional argument — there is no "skip clustering" option in its
    signature — so a per-chunk merge that no longer runs Louvain still has to
    hand it something. Reading back what the graph already carries is that
    something: `build_merge` loads the EXISTING graph.json (which already has
    real community assignments from the last full `graphify_ops.label` pass)
    and only appends the new chunk's nodes, so every pre-existing node keeps
    its real community. A node with no `community` attribute at all — brand
    new this chunk, or from a graph that predates any label pass — contributes
    to none, exactly as graphify's own version does; it comes back as
    `community: null` in this write and gets a real assignment at the next
    label pass, rather than being coerced into a guessed bucket here.
    """
    communities: dict[int, list[str]] = {}
    for node_id, data in g.nodes(data=True):
        cid = data.get("community")
        if cid is not None:
            communities.setdefault(int(cid), []).append(node_id)
    return communities


def _opt(argv: list[str], flag: str) -> str | None:
    """The value following `flag`, or None. A trailing flag with no value is None.

    Hand-rolled rather than argparse because this script's three positionals are
    passed by exactly one caller and argparse would put a `--help` surface on a
    file that must never be run by hand (`hook_guard` denies it).
    """
    if flag not in argv:
        return None
    i = argv.index(flag)
    return argv[i + 1] if i + 1 < len(argv) else None


def _report(
    chunk_path: str, chunk: dict, prior: int | None, g: object, *, self_remerge: bool = False
) -> None:
    """Print the merge line, ASSERTING its own arithmetic where it can (#191).

    Takes the parsed `chunk` rather than a pre-extracted node count and
    `supersedes` list. Both readings then come from ONE object at one moment, so
    a caller cannot hand this function a count from one chunk and a declaration
    from another — and there is no second place where "how many nodes did this
    chunk add" is computed.

    The old line printed `+N doc nodes -> TOTAL` and nothing else, which made
    "did this merge replace anything" a subtraction between two numbers a
    human had to hold in their head across separate runs. That subtraction is
    the ONLY thing that ever caught this class: 72 nodes of an unrelated source
    destroyed on 2026-08-06 with every gate green, 69 lost on the 2026-08-05
    rebuild, 3 hyperedges on the #186 one.

    So the line now states the identity it depends on. `added` is what the chunk
    contributed; `prior` is what the graph held; anything missing from
    `added + prior` was REPLACED — `build_merge` drops every existing node whose
    `source_file` this chunk also names, which is right for re-extraction and is
    also precisely how a basename collision eats another source.

    Replacement is REPORTED, not refused. It is legitimate and common — a
    re-extraction of an already-committed chunk replaces its own prior nodes
    one-for-one — and the blocking layer is upstream, where
    `chunks.collision_issues` refuses an UNDECLARED cross-chunk claim before any
    of this runs (#189). The job here is to make a shrink impossible to miss,
    not to adjudicate it.

    With no `prior`, the line says the arithmetic was not checked rather than
    printing a delta computed against a guess.

    `self_remerge` distinguishes the routine case from the alarming one, and it
    is not cosmetic. Re-merging an already-committed chunk replaces that chunk's
    OWN prior contribution one-for-one — measured live on 2026-08-06, a re-merge
    of `claude-commands-docs.json` reported `REPLACED 10` with the total
    unchanged, which is exactly correct and exactly what a routine re-merge does
    every time. Phrasing that as *"the loss is real"* would put a false alarm on
    the single most common merge there is, and a check that cries wolf on the
    ordinary path is one people stop reading. The caller decides, because only it
    can see the committed corpus: see `graphify_ops._self_remerge`.
    """
    added = len(chunk.get("nodes", []))
    declared = chunk.get("supersedes") or []
    total = g.number_of_nodes()
    head = f"[merge] {chunk_path}: +{added} doc nodes -> {total} nodes, {g.number_of_edges()} edges"
    if prior is None:
        print(f"{head} (prior node count unknown — arithmetic NOT checked)")
        return
    observed = total - prior
    replaced = added - observed
    if replaced == 0:
        print(f"{head} — arithmetic checks: {prior} + {added} = {total}, 0 replaced")
        return
    if self_remerge:
        why = (
            "EXPECTED — this chunk is already committed and is the only claimant of "
            "every source_file it names, so it replaced its own prior contribution."
        )
    elif declared:
        why = f"EXPECTED — the chunk declares supersedes={declared}."
    else:
        why = (
            "UNEXPECTED — the chunk declares no supersession and is not re-merging "
            "its own committed contribution. The identities collided (#189) and the "
            "loss is real."
        )
    print(
        f"{head}\n"
        f"[merge] REPLACED {replaced} node(s): {prior} + {added} = {prior + added}, "
        f"but the graph holds {total}. Every replaced node carried a source_file "
        f"this chunk also names. {why}"
    )


def main() -> int:
    from graphify.build import build_merge
    from graphify.export import to_json

    chunk_path, root, out = sys.argv[1], sys.argv[2], sys.argv[3]
    prior_raw = _opt(sys.argv, "--prior-nodes")
    prior = int(prior_raw) if prior_raw is not None and prior_raw.lstrip("-").isdigit() else None
    counts_out = _opt(sys.argv, "--counts-out")
    chunk = json.loads(Path(chunk_path).read_text(encoding="utf-8"))
    n = len(chunk.get("nodes", []))
    if n == 0:
        print(f"[merge] {chunk_path}: 0 nodes — skipped")
        return 0

    # dedup=False: the chunk is already single-repo-deduped at extraction, and the
    # target graph now spans MULTIPLE repos — graphify forbids cross-project dedup
    # (a `main` in repo A != repo B), the same reason the code layer merges via
    # `merge-graphs` without deduping. Cross-repo dedup here raises ValueError.
    #
    # build_merge attaches this chunk's own hyperedges (if any) to `G.graph`,
    # resolving their endpoints against the freshly-loaded+merged graph — that
    # is unchanged by this file's #169 restructure; only the analysis/report
    # calls that used to follow it were removed.
    G = build_merge(
        [chunk], graph_path=out, prune_sources=None, root=root, directed=False, dedup=False
    )
    communities = _communities_from_graph(G)

    if not to_json(G, communities, out):
        print("[merge] ERROR: to_json refused (shrink guard #479)")
        return 1

    _report(chunk_path, chunk, prior, G, self_remerge="--self-remerge" in sys.argv)
    print(f"[merge] {len(communities)} communities carried forward")

    # AFTER the write, so the caller fingerprints the bytes that now exist.
    # Written even when `--prior-nodes` was unknown: this run is what makes the
    # NEXT one checkable, and a merge that could not check its own arithmetic is
    # exactly the one after which the ledger most needs re-establishing.
    if counts_out:
        hyperedges = G.graph.get("hyperedges") or []
        members = sum(
            len(h.get("nodes", h.get("members")) or []) for h in hyperedges if isinstance(h, dict)
        )
        Path(counts_out).write_text(
            json.dumps(
                {
                    "nodes": G.number_of_nodes(),
                    "edges": G.number_of_edges(),
                    "hyperedges": len(hyperedges),
                    "members": members,
                }
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
