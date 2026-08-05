"""`kb-insights` — print what the graph already computed and nobody reads.

graphify computes four things on every `cluster-only` / `label` run and writes
them to `graphify-out/.graphify_analysis.json`: `surprises`, `questions`, `gods`
and `cohesion`. Nothing in this repo has ever read that file. The MCP server
exposes three of them as `graphify://surprises`, `://questions` and `://audit`,
which is why they looked unreachable — but the sidecar is the better source, for
a reason worth stating: **the MCP resource handlers render one field each**
(`serve.py:1826-1862`), discarding the `score`/`why` on a surprise and the
`type`/`why` on a question. The sidecar keeps the full dicts. Going through the
server would pay a subprocess to throw away the most useful part.

The provenance audit has no sidecar — it is four lines of arithmetic — so it is
computed here, and computed by STREAMING rather than by loading the graph.

Two measured constraints shape this module:

1. **The sidecar can be arbitrarily stale, and nothing says so.** Measured
   2026-08-05: `.graphify_analysis.json` was three days old and described 140,680
   nodes while `graph.json` held 335,812 — a corpus 2.4x larger (#138). Two
   writers, no cross-check: `graph.json` comes from `kb-build`/`kb-merge`/
   `kb-label`/`kb-watch`, the sidecar from `kb-artifacts`/`kb-label`. So this
   reports the figures AND their staleness, and never renders a stale sidecar as
   current — a "could not check" is not a green, but it is not a reason to
   withhold the number either.
2. **Counting `"confidence":` over the whole file over-counts.** graph.json is
   pretty-printed, so a line-wise count is tempting and wrong: 819,172 matches
   against 819,167 links, because five AST nodes from `codegraph` carry a stray
   edge-only `confidence` field. The audit therefore counts only inside the
   `"links": [` array.

Composition — three more facts computed in the SAME streaming pass (#175,
#167), because a second full read of a ~570 MB file is not a cost this module
pays twice for one report: how many communities span more than one source
repo (a sign the corpus is cross-pollinating rather than sitting in disjoint
per-source islands), how many EDGES cross the ast/semantic boundary (#167's
pre-stated gate is >=20; the real corpus measures 0, so this number decides a
live question and must be exact, not sampled — see `_crosses_origin`), and
graph.json's byte size against graphify's DEFAULT 512 MiB read cap
(`security.py`'s `_MAX_GRAPH_FILE_BYTES`) — this repo's mise env raises the
EFFECTIVE cap to 1 GiB, but the default is what any invocation outside that
env enforces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

#: Node/link/analysis artifacts, all under `graphify-out/`.
_GRAPH = "graph.json"
_SIDECAR = ".graphify_analysis.json"

#: How many of each ranked list to print by default. graphify itself computes
#: `top_n=10` for surprises and questions, so asking for more returns nothing —
#: the cap is in the producer, not here.
_DEFAULT_TOP = 10


#: Longest question printed before it is cut. graphify's `bridge_node` generator
#: names EVERY neighbour of a hub, and on this corpus that is not a rhetorical
#: excess — one measured question listed ~1,900 symbols and ran to ~20 KB, which
#: buries the other nine and makes the section unreadable in a terminal. The full
#: text stays in `.graphify_analysis.json` for anyone who wants it.
_QUESTION_CHARS = 240


def _clamp(text: str, limit: int = _QUESTION_CHARS) -> str:
    """Cut an over-long line, saying how much was cut rather than trailing off."""
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}… (+{len(text) - limit:,} more chars in {_SIDECAR})"


@dataclass(frozen=True)
class Audit:
    """The EXTRACTED/INFERRED/AMBIGUOUS split over the graph's real edges."""

    total: int
    by_tier: dict[str, int]

    def pct(self, tier: str) -> float:
        """That tier's share of all edges, or 0.0 on an empty graph."""
        return (self.by_tier.get(tier, 0) / self.total * 100) if self.total else 0.0


@dataclass(frozen=True)
class CommunitySpan:
    """One community whose member nodes are tagged with more than one source."""

    community: int
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Composition:
    """Cross-source structure `assert_composition` never checks (#175, #167).

    `spanning` holds every community whose members carry more than one source
    tag — evidence the corpus is cross-pollinating rather than sitting in
    disjoint per-source islands. `cross_origin_edges` is issue #167's gate
    instrument: the number of edges whose two endpoints differ in `_origin`
    (ast vs semantic). Both are computed EXACTLY, not sampled — a gate value
    that is wrong in either direction is worse than one that is merely absent.
    """

    spanning: tuple[CommunitySpan, ...]
    total_communities: int
    cross_origin_edges: int
    #: EVERY link scanned, not only links carrying a `confidence` field.
    #: `cross_origin_edges` is counted over all links (`_crosses_origin` never
    #: gates on `confidence`), so a denominator counted only over TIERED links
    #: could print `cross_origin_edges > total_edges` — not merely misleading,
    #: unrepresentable — the moment one link lacks the field (#175 cold
    #: review, finding 7).
    total_edges: int


#: A node's source bucket when it carries no `repo` attribute at all. Not a
#: gap to paper over: post-#175 semantic doc nodes may legitimately carry
#: none, and folding them into an existing tagged bucket (or dropping them)
#: would hide exactly the cross-source mixing this probe exists to surface.
_UNTAGGED = "(untagged)"

#: How many spanning communities `_print_composition` names by example. The
#: `Composition` object itself carries every one — this bounds the PRINTED
#: report, matching `_print_sidecar`'s own `[:top]` slicing-at-print-time
#: rather than the data layer.
_MAX_SPAN_EXAMPLES = 5


def _field_name(stripped: str) -> str | None:
    """The JSON key of a `"key": value,` line, or None if this is not one.

    Every real field line in graphify's pretty-printed export opens with a
    quoted key AND carries `": "` between that key and its value — the
    default `key_separator` `json.dump(..., indent=N)` always emits — so both
    are required. The `": "` half matters for a shape this module's callers
    do not control: a bare array-element line inside a list-of-strings field
    (`"foo",`, no colon at all) also opens with a quote, so without this
    check it would be treated as a KEY here and then crash `_value`'s
    `split(":", 1)[1]`, which has nothing to index (#175 cold review,
    finding 6). The None case is a defensive fallback for output this module
    reads back rather than controls — it exists so an unexpected line is
    skipped, never a crash, and this makes that promise true for the shape it
    did not originally anticipate.
    """
    if not stripped.startswith('"') or ": " not in stripped:
        return None
    return stripped.split('"', 2)[1]


def _value(stripped: str) -> str:
    """A `"key": value,` line's RHS, comma and surrounding quotes stripped.

    Works uniformly whether `value` is a quoted string or a bare int/bool/null
    token — `.strip('"')` is a no-op on an already-unquoted one. Was inlined in
    `audit_edges` for its one caller (the tier field); every field this module
    now reads shares this single copy instead.
    """
    return stripped.split(":", 1)[1].strip().rstrip(",").strip('"')


def _parse_community(raw: str | None) -> int | None:
    """A captured `community` field's raw text -> an int, or None if unassigned.

    Three cases collapse to the same None, matching `_merge_docs.py`'s own
    community reconstruction (`_communities_from_graph`): the field was
    absent, it was JSON `null` (a node added since the last full label pass),
    or it was present but not integer text. None always means "cannot
    attribute to a span" — never "attribute to community 0".
    """
    if raw is None or raw == "null":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _record_node(
    fields: dict[str, str], *, node_origin: dict[str, str], community_tags: dict[int, set[str]]
) -> None:
    """Fold one finished node's captured fields into the running maps.

    A node with no `id` cannot be indexed and is skipped — never observed on a
    real graph, but this reads untrusted output, not input we control.
    """
    nid = fields.get("id")
    if nid is None:
        return
    origin = fields.get("_origin")
    if origin is not None:
        node_origin[nid] = origin
    tag = fields.get("repo", _UNTAGGED)
    cid = _parse_community(fields.get("community"))
    if cid is not None:
        community_tags.setdefault(cid, set()).add(tag)


def _crosses_origin(link: dict[str, str], node_origin: dict[str, str]) -> bool:
    """True iff this link's two endpoints resolve to DIFFERENT `_origin` values.

    An endpoint that does not resolve — a missing `source`/`target`, or an id
    absent from `node_origin` (a dangling reference `assert_composition` only
    checks for hyperedge members, never for a plain link) — counts as unknown,
    never as a crossing: this feeds an exact gate value (#167) and must
    undercount rather than guess.
    """
    src, tgt = link.get("source"), link.get("target")
    if src is None or tgt is None:
        return False
    o1, o2 = node_origin.get(src), node_origin.get(tgt)
    return o1 is not None and o2 is not None and o1 != o2


def _build_composition(
    community_tags: dict[int, set[str]], *, cross_origin_edges: int, total_edges: int
) -> Composition:
    """Fold the per-community tag sets gathered while scanning into a report.

    Sorted by community id — arbitrary but deterministic, so two runs over an
    unchanged graph print identical output (a `set`'s iteration order is not
    guaranteed to repeat across processes).
    """
    spanning = tuple(
        sorted(
            (
                CommunitySpan(community=cid, tags=tuple(sorted(tags)))
                for cid, tags in community_tags.items()
                if len(tags) > 1
            ),
            key=lambda span: span.community,
        )
    )
    return Composition(
        spanning=spanning,
        total_communities=len(community_tags),
        cross_origin_edges=cross_origin_edges,
        total_edges=total_edges,
    )


def _skip_to(fh: Iterator[str], prefix: str) -> None:
    """Advance `fh` past (and including) the first ROOT-LEVEL line starting with `prefix`.

    Depth-tracks from the file's own opening `{` (depth 0 -> 1), so a match is
    only accepted at `depth == 1` — directly inside the root object, where
    `"directed"`/`"graph"`/`"nodes"`/`"links"`/`"hyperedges"`/`"built_at_commit"`
    all live. Without this, a same-named key nested inside `graph` is
    indistinguishable from the real one: `graph.hyperedges` precedes the
    top-level `nodes` array in every graphify export (`node_link_data` writes
    `graph` before `nodes`), and once a hyperedge carries a non-empty member
    list, that list is ALSO keyed `"nodes"` — measured on the real corpus at
    line 9 (`graph.hyperedges[0].nodes`, depth 3) vs. the real top-level
    `"nodes": [` at line 82 (depth 1). A naive first-match `_skip_to` locked
    onto line 9, positioned `fh` mid-hyperedge, and every downstream map
    stayed empty — this shape was structurally absent from the empty-
    hyperedges graph this function was first written and tested against, so
    the collision was never exercised until hyperedges carried real content.

    Same brace-only depth rules as `_iter_objects` — see that docstring for
    why a string VALUE containing a literal brace never perturbs the count.

    No-ops to EOF if the marker never appears at root level, matching this
    module's existing tolerance: an empty scan, not a crash.
    """
    depth = 0
    for line in fh:
        stripped = line.strip()
        if depth == 1 and stripped.startswith(prefix):
            return
        if stripped == "{":
            depth += 1
            continue
        if stripped in ("}", "},"):
            depth -= 1
            continue
        if stripped.endswith("{"):
            depth += 1


def _iter_objects(fh: Iterator[str], stop: str | tuple[str, ...]) -> Iterator[dict[str, str]]:
    """Yield each array element's scalar fields; stop (consuming) at a `stop` line.

    The `stop` match is gated to `depth == 0` — "not currently inside an
    element" — for the SAME reason field capture is gated to `depth == 1`
    (below): an unconditional match would treat a same-named key nested
    inside an element's own `metadata` (or any future nested field) as the
    array's closing sibling key, stopping mid-element. Not merely
    hypothetical for the SIBLING case either — `graph.hyperedges` carries a
    top-level-looking `"hyperedges"` key of its own (nested, at depth 2) that
    precedes the REAL sibling `"hyperedges"` key `_scan`'s links phase stops
    at; `depth == 0` is what keeps the two apart once this generator is
    correctly positioned by a depth-aware `_skip_to`.

    DEPTH-TRACKS rather than matching fields unconditionally, because graphify
    nests a `metadata` dict inside SOME node and link objects — measured on the
    real corpus at 4,272 nodes (`"language"`/`"kind"` for code) and more links.
    A naive unconditional `"key":` match would risk a metadata-nested field
    masquerading as the element's own; depth-gating makes that structurally
    impossible rather than merely unobserved. Empirically control-armed: a
    probe over the full 14M-line file confirms the nested branch genuinely
    fires (`max_depth_seen == 2`) while zero of `id`/`repo`/`community`/
    `_origin`/`source`/`target`/`confidence` were ever found nested — but
    capture stays gated on `depth == 1` regardless, so a future nested
    collision cannot corrupt this even though today's corpus does not
    exercise it (`probes-need-a-control-arm.md`).

    Relies on one property of `json.dump(..., indent=N)` pretty-printing: a
    string VALUE containing a literal `{`/`}` never perturbs this count,
    because such a value always shares its line with its key and closing
    quote — a brace only ever stands as a line's SOLE content (`{`, `}`, `},`)
    or as a line's trailing character (`"metadata": {`) at a true structural
    boundary, never buried inside a string.

    `fh` must be a single-pass ITERATOR (a real file handle, or `iter(list)`)
    that the caller keeps consuming afterward: this generator stops exactly at
    the `stop` line (without yielding it as an element), leaving `fh`
    positioned for whatever comes next — how one `_scan` pass covers nodes
    then links without a second read.
    """
    depth = 0
    cur: dict[str, str] = {}
    for line in fh:
        stripped = line.strip()
        if depth == 0 and stripped.startswith(stop):
            return
        if stripped == "{":
            depth += 1
            if depth == 1:
                cur = {}
            continue
        if stripped in ("}", "},"):
            depth -= 1
            if depth == 0:
                yield cur
            continue
        if stripped.endswith("{"):
            depth += 1
            continue
        if depth != 1:
            continue
        # `_field_name` returns None for a bare array-element line (a
        # list-of-strings field's own `"foo",`, no `": "` at all) — see its
        # docstring — so a colonless line is skipped here exactly like any
        # other line `_field_name` does not recognise, with no separate gate
        # needed in this loop.
        key = _field_name(stripped)
        if key is not None:
            cur[key] = _value(stripped)


def _scan(graph_path: Path) -> tuple[Audit, Composition]:
    """One streaming pass over graph.json: edge-tier audit + cross-source composition.

    Streams rather than `json.loads` for the reason this module always has: a
    ~570 MB graph costs ~3.7x that in peak RSS to parse whole (measured). This
    pass now ALSO walks `nodes` (the original `audit_edges` skipped straight to
    `"links": [`) to build id -> repo/origin maps and a community -> tag-set
    map — bounded, node-id-keyed maps for ~340k nodes, never holding an edge.

    The top-level `nodes` array fully precedes the top-level `links` array in
    every graphify export, so `node_origin` is complete before the first link
    is read — that ordering is why cross-origin edges, a fact depending on
    BOTH arrays, stays answerable in one pass. Locating each array's REAL
    opening line is not a plain first-match, though: `graph.hyperedges`
    precedes `nodes` (`node_link_data` writes `graph` before `nodes`), and a
    hyperedge's own member list is keyed `"nodes"` too — measured on the real
    corpus, a populated `graph.hyperedges` puts a decoy `"nodes": [` as early
    as line 9, well before the real one (line 82 there). `_skip_to` and
    `_iter_objects`'s `stop` matching are both depth-gated for exactly this
    reason (see their own docstrings); this line-number example is stale the
    moment the corpus changes shape, which is the point — the FIX does not
    depend on a specific line number holding.

    Tier counting stays scoped to exactly the `links` array's own element
    fields, never a whole-file match: see the module docstring for the
    819,172-vs-819,167 measured over-count a naive scan produces. Depth-gating
    (`_iter_objects`) additionally excludes a `metadata`-nested `confidence`,
    which the ORIGINAL unconditional per-line match could not have.
    """
    node_origin: dict[str, str] = {}
    community_tags: dict[int, set[str]] = {}
    tier_counts: dict[str, int] = {}
    tier_total = 0
    link_total = 0
    cross_origin = 0

    with graph_path.open(encoding="utf-8") as fh:
        _skip_to(fh, '"nodes": [')
        for node in _iter_objects(fh, '"links": ['):
            _record_node(node, node_origin=node_origin, community_tags=community_tags)
        # Same break condition this module has always used for the tier audit:
        # either sibling key ends the links array, hyperedges present or not.
        for link in _iter_objects(fh, ('"hyperedges"', '"built_at_commit"')):
            link_total += 1
            tier = link.get("confidence")
            if tier is not None:
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
                tier_total += 1
            if _crosses_origin(link, node_origin):
                cross_origin += 1

    audit = Audit(total=tier_total, by_tier=tier_counts)
    comp = _build_composition(
        community_tags, cross_origin_edges=cross_origin, total_edges=link_total
    )
    return audit, comp


def audit_edges(graph_path: Path) -> Audit:
    """Edge confidence tiers — see `_scan`.

    Its own entry point so a caller that wants ONLY this still pays one read,
    same cost as before this round; `report()` calls `_scan` directly so
    wanting the audit AND the composition costs one read, not two.
    """
    return _scan(graph_path)[0]


def composition(graph_path: Path) -> Composition:
    """Cross-source community spans + ast/semantic edge crossings — see `_scan`."""
    return _scan(graph_path)[1]


#: graphify's DEFAULT graph.json read cap — `security.py`'s module-level
#: `_MAX_GRAPH_FILE_BYTES` (verified against the pinned 0.9.33 install, NOT
#: imported: this module has no other reason to depend on graphify's package,
#: and a hardcoded constant cannot be silently moved by an unrelated upgrade
#: the way an import could). 512 MiB = 512 * 1024 * 1024. This repo's OWN mise
#: env raises the EFFECTIVE cap to 1 GiB (`GRAPHIFY_MAX_GRAPH_BYTES` in
#: `mise.toml`'s `[env]`) — reported against the DEFAULT anyway, in
#: `_print_size`, because the default is what any invocation outside that env
#: (a bare `graphify …` on another host, a CI runner with no mise env applied)
#: actually enforces.
_MAX_GRAPH_FILE_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class SizeCheck:
    """graph.json's on-disk size against graphify's default read cap."""

    size_bytes: int
    cap_bytes: int

    @property
    def over_cap(self) -> bool:
        """True once `size_bytes` exceeds `cap_bytes`."""
        return self.size_bytes > self.cap_bytes

    @property
    def ratio(self) -> float:
        """`size_bytes / cap_bytes`, or 0.0 for a zero cap (never reached in practice)."""
        return self.size_bytes / self.cap_bytes if self.cap_bytes else 0.0


def size_vs_cap(graph_path: Path) -> SizeCheck:
    """graph.json's size against graphify's default cap — a stat, not a read."""
    return SizeCheck(size_bytes=graph_path.stat().st_size, cap_bytes=_MAX_GRAPH_FILE_BYTES)


#: How far the sidecar may lag `graph.json` and still count as the same run.
#:
#: NOT a fudge factor — it is what makes the check *able to pass*. `kb-artifacts`
#: writes the sidecar and then rewrites `graph.json` (`cluster-only` re-exports
#: after analysing), so a strict `sidecar >= graph` is false the instant the
#: recommended remedy finishes. The first run of this task reported
#: `STALE by 0.0h` and told the reader to run the command they had just run —
#: a check that can only fail, which is the inverse of the one that can only
#: pass (`probes-need-a-control-arm.md`). Ten minutes is far below the gap this
#: exists to catch: the motivating case was three DAYS (#138).
_SAME_RUN_SECONDS = 600


def _freshness(repo_root: Path) -> tuple[bool, str]:
    """(is_fresh, human note) comparing the sidecar's mtime to the graph's.

    Returns a NOTE rather than raising: a stale sidecar's numbers are still the
    last ones anyone computed, and withholding them helps nobody. What must not
    happen is printing them as current.

    mtime is a PROXY and is named as one in the output. It cannot prove the
    sidecar was derived from this graph — only that it was not written long
    before it. The honest signal would be a fingerprint the way
    `.currency-stamp.json` does it; until then this says which question it
    answered.
    """
    out = repo_root / "graphify-out"
    graph, sidecar = out / _GRAPH, out / _SIDECAR
    if not sidecar.is_file():
        return False, f"no {_SIDECAR} — run `mise run kb-artifacts`"
    if not graph.is_file():
        return False, f"no {_GRAPH} — run `mise run kb-build`"
    behind = graph.stat().st_mtime - sidecar.stat().st_mtime
    if behind <= _SAME_RUN_SECONDS:
        return True, (
            f"sidecar and {_GRAPH} are within {_SAME_RUN_SECONDS // 60} min "
            f"({behind:+.0f}s) — same run, by mtime"
        )
    return False, (
        f"STALE by {behind / 3600:.1f}h — {_SIDECAR} predates {_GRAPH} by more "
        f"than {_SAME_RUN_SECONDS // 60} min, so the figures below describe an "
        f"OLDER graph. Run `mise run kb-artifacts`. (mtime is a proxy: it cannot "
        f"prove the sidecar came from THIS graph, only that it predates it.)"
    )


def _parse_top(argv: list[str]) -> int | None:
    """`--top N`, or None if it was given but malformed (the caller returns 2)."""
    if "--top" not in argv:
        return _DEFAULT_TOP
    i = argv.index("--top")
    if i + 1 >= len(argv) or not argv[i + 1].isdigit():
        return None
    return int(argv[i + 1])


def _print_audit(a: Audit) -> None:
    """The live section — computed from graph.json (via `_scan`), so never stale."""
    print(f"\n## Provenance audit — {a.total:,} edges (computed live from {_GRAPH})")
    for tier in ("EXTRACTED", "INFERRED", "AMBIGUOUS"):
        print(f"  {tier:<12}{a.by_tier.get(tier, 0):>12,}  {a.pct(tier):5.1f}%")
    for tier in sorted(set(a.by_tier) - {"EXTRACTED", "INFERRED", "AMBIGUOUS"}):
        print(f"  {tier:<12}{a.by_tier[tier]:>12,}  {a.pct(tier):5.1f}%   <- unexpected tier")
    if not a.by_tier.get("AMBIGUOUS"):
        print(
            "  note: AMBIGUOUS is 0 BY OUR CONSTRUCTION, not by accident — "
            "`chunks.py` rejects the tier and the extraction prompt never offers "
            "it. graphify weights AMBIGUOUS highest in `surprising_connections` "
            "and drives one whole `suggest_questions` generator from it, so that "
            "generator is dead code here (#168)."
        )


def _print_composition(comp: Composition) -> None:
    """Multi-source community spans + ast/semantic edge crossings (#175, #167)."""
    print(
        f"\n## Multi-source community spans — {len(comp.spanning):,} of "
        f"{comp.total_communities:,} communities span more than one source"
    )
    for span in comp.spanning[:_MAX_SPAN_EXAMPLES]:
        print(f"  community {span.community}: {{{', '.join(span.tags)}}}")
    if len(comp.spanning) > _MAX_SPAN_EXAMPLES:
        print(f"  … +{len(comp.spanning) - _MAX_SPAN_EXAMPLES:,} more")

    print(
        f"\n## Cross-origin edges — {comp.cross_origin_edges:,} of "
        f"{comp.total_edges:,} edges cross ast/semantic"
    )


def _print_size(check: SizeCheck) -> None:
    """graph.json's size against graphify's DEFAULT cap — see `_MAX_GRAPH_FILE_BYTES`."""
    verdict = "OVER" if check.over_cap else "under"
    mib = check.size_bytes / (1024 * 1024)
    cap_mib = check.cap_bytes / (1024 * 1024)
    print(
        f"\n## Size vs cap — {check.size_bytes:,} bytes ({mib:,.1f} MiB), "
        f"{verdict} graphify's default {cap_mib:,.0f} MiB cap ({check.ratio:.2f}x)"
    )
    print(
        "  note: this repo's mise env raises the EFFECTIVE cap to 1 GiB "
        "(GRAPHIFY_MAX_GRAPH_BYTES in mise.toml) — the DEFAULT is reported here "
        "because it is what an env-less graphify invocation enforces."
    )


def _print_sidecar(sidecar: Path, *, top: int, stale: str) -> None:
    """Surprises, questions and god nodes, with the fields MCP would discard."""
    data = json.loads(sidecar.read_text(encoding="utf-8"))

    surprises = data.get("surprises") or []
    print(f"\n## Surprising connections — {len(surprises)} computed{stale}")
    for s in surprises[:top]:
        print(
            f"  {s.get('source')} --{s.get('relation')}--> "
            f"{s.get('target')}  [{s.get('confidence')}]"
        )
        if files := s.get("source_files"):
            print(f"      {' -> '.join(files)}")
        if why := s.get("why"):
            print(f"      why: {why}")

    questions = data.get("questions") or []
    print(f"\n## Suggested questions — {len(questions)} computed{stale}")
    for q in questions[:top]:
        print(f"  [{q.get('type')}] {_clamp(q.get('question') or '')}")

    gods = data.get("gods") or []
    print(f"\n## God nodes — {len(gods)} computed{stale}")
    for g in gods[:top]:
        print(f"  {g.get('degree'):>6,}  {g.get('label')}")


def report(repo_root: Path, args: list[str] | None = None) -> int:
    """Print surprises, questions, god nodes, the provenance audit, and composition.

    `--top N` bounds each ranked list. The audit and composition sections are
    always computed live from `graph.json` in ONE streaming pass (`_scan`), so
    they are never stale even when the sidecar is — which is why they print
    BEFORE the sidecar sections and print even when there is no sidecar at
    all. A missing `graph.json` is refused before any of this runs (below), so
    none of these three sections ever print against a graph that is not there.
    """
    top = _parse_top(list(args or []))
    if top is None:
        print("[kb-insights] --top needs a positive integer", flush=True)
        return 2

    out = repo_root / "graphify-out"
    graph = out / _GRAPH
    if not graph.is_file():
        print(f"[kb-insights] no {_GRAPH} — run `mise run kb-build` first")
        return 2

    fresh, note = _freshness(repo_root)
    print(f"[kb-insights] {note}")
    audit, comp = _scan(graph)
    _print_audit(audit)
    _print_composition(comp)
    _print_size(size_vs_cap(graph))

    sidecar = out / _SIDECAR
    if not sidecar.is_file():
        return 0
    _print_sidecar(sidecar, top=top, stale="" if fresh else "  [STALE]")
    return 0
