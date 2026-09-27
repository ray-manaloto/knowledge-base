# Copyright (c) 2026 Raymond Manaloto
"""Merge committed document extractions into graphify-out/graph.json.

Runs under the locked Graphify-capable interpreter chosen by graph.py. It is a
subprocess boundary even when the current KB uv environment provides Graphify.

Usage: python _merge_docs.py <chunk.json> <source_root_abs> <graph.json>
                             [--prior-nodes N] [--prior-hyperedges N]
                             [--counts-out PATH]
       python _merge_docs.py --batch <repo_root> <graph.json> <chunk.json>...

`--prior-nodes` is how many nodes `graph.json` held BEFORE this merge, when the
caller could establish that for free (`kb_setup.graph_counts`). Given it, the
merge line asserts its own arithmetic instead of leaving the subtraction to a
human — see `_report` below. Omitted, the line says so; it never guesses.

`--prior-hyperedges` is the same measurement for the hyperedge set (#198 item 1).
It is a SEPARATE flag rather than a richer `--prior-nodes` payload because the two
are independently available: `graph_counts.read` can return a ledger entry carrying
one and not the other, and a merge that can check nodes but not hyperedges must say
exactly that rather than fall back to checking neither. The hyperedge half exists
because the FIRST loss this whole ticket family was filed over — the #186 round's
11 hyperedges -> 8 — moved no nodes at all, so a node-only assertion would have been
blind to the very incident that motivated it.

`--counts-out` is a path this script writes its post-merge counts to, so the
caller — which does not read the subprocess's in-memory Graph — can record them
in the ledger. The fingerprint that makes those
counts trustworthy is added by the caller, deliberately: duplicating the
`size:mtime_ns` formula into this file would give the ledger two owners that
could drift into disagreeing about what "the graph moved" means.

MERGE-ONLY (#169, #175). Clustering and labeling happen once in `build()` after
the code and document layers have landed. Full builds collapse approved
capture-date supersessions and merge all committed chunks once; incremental
recomposition retains the one-chunk mode and its threaded count handoff.
"""

import json
import sys
from collections.abc import Mapping
from pathlib import Path


def _collapse_replay(chunks: list[dict]) -> tuple[list[dict], dict[str, set[str]]]:
    """Keep only the last semantic claimant of each source in an ordered replay.

    Full builds have already validated the chunks and their declared overlaps.
    Materializing the final owners before Graphify's one merge avoids parsing and
    serializing the entire code graph once per small document chunk.
    """
    from kb_setup.chunks import normalise_source_file

    # The one-chunk path returns before merging a zero-node chunk. A full build
    # must make the same choice even if that chunk carries cross-chunk edges.
    chunks = [chunk for chunk in chunks if chunk.get("nodes")]
    owners: dict[str, int] = {}
    for index, chunk in enumerate(chunks):
        for node in chunk.get("nodes", []):
            if node.get("_origin") != "semantic":
                raise ValueError("batched document replay requires semantic-only nodes")
            source = normalise_source_file(node.get("source_file"))
            if source is None:
                raise ValueError("batched document replay requires node source_file")
            owners[source] = index

    effective: list[dict] = []
    expected: dict[str, set[str]] = {source: set() for source in owners}
    for index, chunk in enumerate(chunks):
        filtered = dict(chunk)
        for field in ("nodes", "edges", "hyperedges"):
            kept = []
            for item in chunk.get(field, []) or []:
                source = normalise_source_file(item.get("source_file"))
                if source is not None and owners.get(source, index) != index:
                    continue
                kept.append(item)
                if field == "nodes":
                    expected[source].add(item["id"])
            filtered[field] = kept
        effective.append(filtered)
    return effective, expected


def _batch_main(argv: list[str]) -> int:
    """Replay validated committed chunks with one graph load and one write."""
    from graphify.build import _is_ast_tier, build_merge
    from graphify.export import to_json

    try:
        root, out, *paths = argv[2:]
    except ValueError as exc:
        raise ValueError("usage: _merge_docs.py --batch ROOT GRAPH CHUNK...") from exc
    if not paths:
        raise ValueError("batched document replay needs at least one chunk")
    chunks = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    effective, expected = _collapse_replay(chunks)
    if not effective:
        print(f"[merge] {len(paths)} zero-node document chunks skipped")
        return 0
    # Sequential replay reloads every earlier chunk's edges before the last
    # merge. Graphify's loader backfills _origin on those persisted edges; the
    # final chunk's edges have not been reloaded yet. Preserve that distinction.
    for chunk in effective[:-1]:
        for edge in chunk["edges"]:
            edge.setdefault("_origin", "ast" if _is_ast_tier(edge) else "semantic")
    graph = build_merge(effective, graph_path=out, root=root, directed=False, dedup=False)

    observed: dict[str, set[str]] = {source: set() for source in expected}
    for node_id, data in graph.nodes(data=True):
        source = data.get("source_file")
        if data.get("_origin") == "semantic" and source in observed:
            observed[source].add(node_id)
    # Graphify canonicalizes legacy semantic IDs from their full source paths.
    # The input IDs are therefore not the output IDs even when all nodes survive.
    # The full-corpus sequential/batch parity control checks final identities.
    mismatches = [source for source in expected if len(observed[source]) != len(expected[source])]
    if mismatches:
        raise ValueError(
            "batched document replay changed semantic node counts for "
            + ", ".join(sorted(mismatches)[:8])
        )

    communities = _communities_from_graph(graph)
    if not to_json(graph, communities, out):
        print("[merge] ERROR: to_json refused (shrink guard #479)")
        return 1
    print(
        f"[merge] batched {len(paths)} document chunks; "
        f"{len(expected)} final source owners; "
        f"{graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges; "
        "semantic source counts checked"
    )
    return 0


# Graphify imports stay inside the entry points so the pure-Python reporting
# helpers remain independently testable. Both the batch and one-chunk paths run
# under the selected Graphify interpreter; callers must not rely on their own
# environment to select the merge implementation.


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


def counts_for(g: object) -> dict[str, int]:
    """The post-merge counts the caller records in the continuity ledger.

    A named function rather than an inline block inside `main()` because `main()`
    imports graphify and is unreachable from this repo's own interpreter — so the
    ONLY producer of real ledger counts was untestable, and every arm in the suite
    fabricated the dict it is supposed to emit. A regression here (a renamed
    hyperedge slot, members counted per-edge instead of summed) would have left
    the whole suite green. (Cold lane, round 2, P1.)

    Reads BOTH hyperedge member spellings — graphify writes `nodes`, older chunks
    say `members` — and skips a non-dict entry rather than raising, because this
    runs after a successful merge and must not turn one into a traceback.
    """
    hyperedges = g.graph.get("hyperedges") or []
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "hyperedges": len(hyperedges),
        "members": sum(
            len(h.get("nodes", h.get("members")) or []) for h in hyperedges if isinstance(h, dict)
        ),
    }


def _int_opt(argv: list[str], flag: str) -> int | None:
    """`_opt` parsed as an int, or None when absent/non-numeric.

    Factored out when `--prior-hyperedges` made this the second caller (#198).
    Non-numeric degrades to None — "not checked" — rather than raising: these
    values come from a ledger that deliberately answers `None` when the graph
    moved outside a tracked writer, and a merge must not be turned into a
    traceback by a count it was only ever going to print.
    """
    raw = _opt(argv, flag)
    return int(raw) if raw is not None and raw.lstrip("-").isdigit() else None


#: Every way a doc merge can lose a hyperedge, read from the INSTALLED graphify
#: 0.9.35 source on 2026-08-07. The arithmetic in `_hyperedge_line` sees the SUM
#: and cannot attribute it, which is why the message enumerates instead of
#: asserting a cause — see that function's docstring for why nodes may assert one
#: and hyperedges may not.
_HYPEREDGE_LOSS_CAUSES = (
    "a carried hyperedge whose source_file this chunk also names, so it was "
    "replaced by this chunk's version (build.py:1735-1736); "
    "an id collision with one this chunk re-emitted, so it was deduped "
    "(export.py attach_hyperedges); "
    "a NEW hyperedge none of whose members resolved to a built node, which "
    "graphify DROPS with a stderr warning (build.py:1230-1237); "
    "or a hyperedge with a falsy `id`, which attach_hyperedges skips SILENTLY"
)


def _hyperedge_line(
    prior: int | None,
    added: int,
    total: int,
    *,
    self_remerge: bool = False,
    declared: object = (),
) -> str | None:
    """The hyperedge-continuity line, or None when there is nothing to assert.

    Pure ints in, string out, so the arithmetic that #198 exists for is testable
    from this repo's own interpreter — `main()` imports graphify and is not.

    THE IDENTITY IS THE SAME AS NODES; THE EXPLANATION IS NOT, and that asymmetry
    is the whole reason this is a separate function rather than a second `if` in
    `_report`. A doc merge (`prune_sources=None`) has exactly ONE way to drop a
    node — `build_merge` drops every existing node whose `source_file` this chunk
    also names — so the node line may name that cause outright. Hyperedges have
    four (`_HYPEREDGE_LOSS_CAUSES`), only one of which is that same rule, and only
    one of which graphify announces. Reusing the node wording here would print a
    confident single-cause sentence that is false whenever the loss came from the
    other three.

    `self_remerge` is not cosmetic and is not copied for symmetry — without it this
    line would cry wolf on the single most common merge there is. Re-merging an
    already-committed chunk puts every `source_file` it names into
    `new_sem_sources`, so ALL of its prior hyperedges are dropped from the carry
    and its new ones are added back: a routine re-merge of the 45-hyperedge
    `graphify-2026-08-06` chunk balances to exactly 45 "lost". The node half
    learned this the same way (measured 2026-08-06, `REPLACED 10` on a re-merge);
    a check that fires on the ordinary path is one people stop reading.

    Returns None — printing nothing — only when there is provably nothing to
    assert: no hyperedges before, none incoming, none held. That is silence about
    an empty set, not silence about an unchecked one; every other unchecked case
    says so out loud.
    """
    if prior is None:
        if added == 0 and total == 0:
            return None
        return (
            f"[merge] hyperedges: {total} held, +{added} from this chunk "
            f"(prior hyperedge count unknown — arithmetic NOT checked)"
        )
    if prior == 0 and added == 0 and total == 0:
        return None
    lost = prior + added - total
    if lost == 0:
        return f"[merge] hyperedges: arithmetic checks: {prior} + {added} = {total}, 0 lost"
    if lost < 0:
        # Not reachable through `build_merge` as read: the kept set is a subset of
        # (new + carried), so total <= prior + added. Reported rather than assumed
        # away, because the assumption is about SOMEONE ELSE'S code and this file
        # already carries one comment that overstated what that code does.
        return (
            f"[merge] hyperedges: UNEXPECTED GAIN of {-lost}: {prior} + {added} = "
            f"{prior + added}, but the graph holds {total}. The merge produced "
            f"hyperedges from neither the prior graph nor this chunk."
        )
    if self_remerge:
        why = (
            "EXPECTED — this chunk is already committed and is the only claimant of "
            "every source_file it names, so its prior hyperedges were replaced by "
            "the versions in this same chunk."
        )
    elif declared:
        why = f"EXPECTED — the chunk declares supersedes={declared}."
    else:
        why = (
            "UNEXPECTED — the chunk declares no supersession and is not re-merging "
            f"its own committed contribution. This arithmetic sees the SUM of: "
            f"{_HYPEREDGE_LOSS_CAUSES}. Only the third announces itself, so read "
            "graphify's stderr above before concluding which one this was."
        )
    return (
        f"[merge] LOST {lost} hyperedge(s): {prior} + {added} = {prior + added}, "
        f"but the graph holds {total}. {why}"
    )


def _report(
    chunk_path: str,
    chunk: dict,
    prior: Mapping[str, int | None] | None,
    g: object,
    *,
    self_remerge: bool = False,
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

    That third entry used to be the joke in this docstring: it named a hyperedge
    loss inside the one function structurally unable to see one, because every
    number here came from `g.number_of_nodes()`. `_hyperedge_line` closes it
    (#198 item 1) — and note the #186 shape moved NO nodes, so the node half of
    this function would have printed "0 replaced" over it and been right.

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
    # ONE mapping rather than one int per field (#198 item 1). `graph_counts.read`
    # already returns exactly this shape, so the old `prior: int` forced the caller
    # to destructure a dict only for this function to re-assemble it — and each new
    # field the ledger grows would have been another positional. A field the ledger
    # could not establish is ABSENT here and reads back as None, which is the same
    # "not checked, not guessed" contract the int had, now stated per field instead
    # of for the whole report.
    priors = prior or {}
    prior_nodes = priors.get("nodes")
    added = len(chunk.get("nodes", []))
    declared = chunk.get("supersedes") or []
    total = g.number_of_nodes()
    head = f"[merge] {chunk_path}: +{added} doc nodes -> {total} nodes, {g.number_of_edges()} edges"
    # Computed BEFORE the node half's early returns and printed after every one of
    # them (#198 item 1). The node path returns early on both of its clean cases,
    # so appending the hyperedge line at the bottom of this function would have
    # emitted it only on a node REPLACEMENT — silent on exactly the #186 shape
    # this half exists for, where nodes balance and hyperedges do not.
    hyper = _hyperedge_line(
        priors.get("hyperedges"),
        len(chunk.get("hyperedges") or []),
        # `g.graph` directly, not a getattr default: `_report`'s only real caller
        # hands it the networkx Graph from `build_merge`, which always has the
        # attribute, and a fallback here would be a branch no arm could reach —
        # the shape this repo calls decoration.
        len(g.graph.get("hyperedges") or []),
        self_remerge=self_remerge,
        declared=declared,
    )

    def _emit(node_line: str) -> None:
        print(node_line)
        if hyper is not None:
            print(hyper)

    if prior_nodes is None:
        _emit(f"{head} (prior node count unknown — arithmetic NOT checked)")
        return
    observed = total - prior_nodes
    replaced = added - observed
    if replaced == 0:
        _emit(f"{head} — arithmetic checks: {prior_nodes} + {added} = {total}, 0 replaced")
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
    _emit(
        f"{head}\n"
        f"[merge] REPLACED {replaced} node(s): {prior_nodes} + {added} = "
        f"{prior_nodes + added}, "
        f"but the graph holds {total}. Every replaced node carried a source_file "
        f"this chunk also names. {why}"
    )


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        return _batch_main(sys.argv)
    from graphify.build import build_merge
    from graphify.export import to_json

    chunk_path, root, out = sys.argv[1], sys.argv[2], sys.argv[3]
    # Rebuilt into the ledger's own shape at the argv boundary. The flags stay
    # separate on the command line — argv carries strings, and one absent flag must
    # not suppress the other's check — but everything downstream sees the single
    # mapping `graph_counts.read` produces, so there is one shape to reason about.
    prior = {
        "nodes": _int_opt(sys.argv, "--prior-nodes"),
        "hyperedges": _int_opt(sys.argv, "--prior-hyperedges"),
    }
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
        Path(counts_out).write_text(json.dumps(counts_for(G)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
