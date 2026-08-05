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
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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


def audit_edges(graph_path: Path) -> Audit:
    """Count edge confidence tiers by streaming, scoped to the `links` array.

    Streams rather than `json.loads` because the graph is ~557 MB and parsing it
    costs ~3.7x that in peak RSS — a routine task should not need 2 GB to print
    four numbers.

    Scoping to `links` is not fastidiousness. A whole-file count of
    `"confidence":` returns five more than there are links, because five AST
    nodes carry the field; the tiers would then be reported over a population
    that is not the edge set.
    """
    counts: dict[str, int] = {}
    total = 0
    in_links = False
    with graph_path.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not in_links:
                # The key is emitted by json.dump at a known indent; matching the
                # stripped prefix keeps this independent of that indent.
                if stripped.startswith('"links": ['):
                    in_links = True
                continue
            if stripped.startswith(('"hyperedges"', '"built_at_commit"')):
                break  # past the array; every sibling top-level key ends it
            if stripped.startswith('"confidence":'):
                # `  "confidence": "EXTRACTED",` -> EXTRACTED
                tier = stripped.split(":", 1)[1].strip().rstrip(",").strip('"')
                counts[tier] = counts.get(tier, 0) + 1
                total += 1
    return Audit(total=total, by_tier=counts)


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


def _print_audit(graph: Path) -> None:
    """The live section — computed from graph.json, so never stale."""
    a = audit_edges(graph)
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
    """Print surprises, questions, god nodes and the provenance audit.

    `--top N` bounds each ranked list. The audit is always computed live from
    `graph.json`, so it is never stale even when the sidecar is — which is why
    it prints BEFORE the sidecar sections and prints even when there is no
    sidecar at all.
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
    _print_audit(graph)

    sidecar = out / _SIDECAR
    if not sidecar.is_file():
        return 0
    _print_sidecar(sidecar, top=top, stale="" if fresh else "  [STALE]")
    return 0
