"""Carry hyperedges across graphify's label/cluster-only round-trip (#171, #175).

VERIFIED MECHANISM (installed graphify 0.9.33 source, not the changelog — see
`probes-need-a-control-arm.md`). `graphify label` / `cluster-only` (`cli.py`,
the `cmd in ("cluster-only", "label")` branch, :1578) loads graph.json with a
plain `json.loads` (:1679) and hands the whole dict to `build_from_json`
(:1681, defined `build.py`:612). That function DOES try to restore
hyperedges (`build.py`:1053-1094) — but it reads only the TOP-LEVEL
`extraction["hyperedges"]` key, never the nested
`extraction["graph"]["hyperedges"]` a raw networkx `node_link_data` write
(e.g. `merge-graphs`) uses instead; and whatever it reads is re-validated by
matching every member id against the just-rebuilt node set, silently
dropping (:1082-1089, one WARNING per casualty) any hyperedge that fails,
then skipping `G.graph["hyperedges"] = ...` entirely once nothing survives
(the `if kept_hyperedges:` guard at :1093). The branch then writes the
result with `to_json`, which unconditionally sets
`data["hyperedges"] = G.graph.get("hyperedges", [])` (`export.py`:314) — so a
revalidation wipeout becomes a durably written `[]`. Measured on this repo's
aggregate `graphify-out/graph.json`: 5 hyperedges in, 0 out.

This module does not try to fix graphify's revalidation (a pinned
third-party tool — see `use-tool-builtins.md`); it sidesteps it entirely.
`capture()` reads the raw list straight off graph.json before the subprocess
runs; `reattach()` writes it straight back after. Neither goes through
`build_from_json`, so neither is subject to whatever made the original 5
fail re-validation.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

#: A hyperedge as graphify (and `sources/extractions/*.json` chunks) shape it:
#: `{"id": ..., "nodes": [...], ...}`. Re-declared rather than imported from
#: `prose` (which defines the same alias) — the two modules share a JSON shape,
#: not a dependency, and a one-line structural alias is not worth coupling them.
type Hyperedge = dict[str, object]

#: Permissions restored on the rewritten file. `tempfile.mkstemp` always creates
#: its file `0600` regardless of the destination's mode, and `Path.replace` is a
#: rename — the surviving inode (and its permission bits) is the TEMP file's,
#: not the file it replaces. Left unfixed, one reattach would silently tighten
#: graph.json from world-readable to owner-only. Matches `prose.py`'s
#: `_ARTIFACT_MODE` and what graphify's own writers produce.
_GRAPH_MODE = 0o644


def capture_from_data(data: dict[str, object]) -> list[Hyperedge]:
    """The hyperedge list within an ALREADY-PARSED graph.json dict.

    The pure half of :func:`capture`, split out so a caller that has already
    parsed the file does not pay a SECOND full read+parse of a several-hundred
    -MB file just to ask this one question. `graph_checks.assert_composition`
    is exactly that caller: it needs the top-level node id set from its own
    parse, and used to also call `capture(graph_path)` — a second `json.loads`
    of the same bytes, with both copies live in memory at once — to get the
    hyperedge list it needs from the SAME file (#175 cold review, finding 2).
    `capture` itself is unchanged for every caller that has not already
    parsed the file.
    """
    return _coalesce(_top(data), _nested(data))


def capture(graph_path: Path) -> list[Hyperedge]:
    """The hyperedge list currently on `graph_path`, read from wherever it lives.

    graph.json can carry it in two places (module docstring): the top-level
    `"hyperedges"` key `to_json` always writes, and the nested
    `"graph"."hyperedges"` key a raw networkx `node_link_data` write leaves
    instead (that key is just a copy of `G.graph`). Both are read. When both
    are present they must agree — a disagreement means the file already
    contradicts itself about what is attached to the graph, and silently
    preferring one slot would manufacture an answer rather than surface the
    conflict.

    A missing file returns `[]` rather than raising, so a caller (`label()`,
    `generate()`) can call this unconditionally before graph.json necessarily
    exists — "nothing to carry" and "no file yet" collapse to the same answer,
    and `mise run kb-build` not having run yet is not this module's problem to
    diagnose.
    """
    if not graph_path.is_file():
        return []
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    return capture_from_data(data)


def reattach(graph_path: Path, hyperedges: Sequence[Mapping[str, object]]) -> None:
    """Write `hyperedges` into both of graph.json's slots, atomically.

    A no-op — the file is not even opened for writing — when there is nothing
    to carry AND nothing already on disk: rewriting a several-hundred-MB graph
    to restate an agreement that already holds would be pure cost with no
    observable effect. Otherwise both slots are set unconditionally, creating
    whichever one is missing, because a caller that captured a non-empty list
    must not have it silently dropped for landing in a file that happens to use
    the other shape.

    This restores the CAPTURED (pre-run) list, in full, regardless of what the
    just-finished run left behind — it does not try to merge the two. That is
    deliberate: the whole point is not depending on whatever graphify's own
    hyperedge handling did on this particular run (module docstring).

    Accepts `Sequence[Mapping[str, object]]` rather than `list[Hyperedge]` on
    purpose: `list`/`dict` are INVARIANT, so a caller's own hand-written
    hyperedge (e.g. `{"id": "he1", "nodes": ["a"]}` in a test) types as
    `dict[str, str | list[str]]` — narrower than `dict[str, object]` by its
    literal values — and ty correctly refuses that as a `list[Hyperedge]`
    argument even though every value in it genuinely satisfies `object`.
    `Sequence`/`Mapping` are read-only and covariant, which is exactly this
    parameter's real contract: `reattach` only ever reads `hyperedges`, never
    mutates it, so nothing here needs the stricter invariant types — those
    stay on `capture`'s return, which is a promise about what THIS module
    hands back, not a constraint on what a caller may hand in.
    """
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    if not hyperedges and not _top(data) and not _nested(data):
        return
    data["hyperedges"] = hyperedges
    graph_meta = data.get("graph")
    if not isinstance(graph_meta, dict):
        graph_meta = {}
        data["graph"] = graph_meta
    graph_meta["hyperedges"] = hyperedges
    _write_atomic(graph_path, data)


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


def _write_atomic(graph_path: Path, data: dict[str, object]) -> None:
    """Full dump of `data` to `graph_path`, via a same-directory temp file + rename.

    Mirrors `prose.derive`'s write half exactly — `mkstemp` rather than a fixed
    temp name, so two writers never share one inode and tear each other's write;
    `Path.replace` for the atomic swap, so a crash or ENOSPC mid-write cannot
    leave `graph_path` half-written. This is a second copy of that pattern
    rather than a shared helper because it lives on a dict already fully in
    memory (the caller just parsed it) where `prose.derive` streams a
    freshly-built one — the two have no common signature to factor through.
    `indent=1`, NOT graphify's own `indent=2` (`export.to_json` /
    `write_json_atomic`), is a deliberate divergence, not a drifted default.
    This artifact is DERIVED and every consumer parses JSON regardless of
    indent width — this repo's own `kb_setup.insights._iter_objects` line-
    scans it, but even that keys on stripped content, never column position —
    so matching upstream byte-for-byte buys nothing. What it costs: this
    function is the LAST writer in the `kb-build`/`kb-watch` pipeline
    (`reattach` runs after `graphify_ops.label`'s own `to_json`), so ITS
    indent is what the artifact's final byte count reflects, and one fewer
    indent level per nested line is real bytes at this scale — measured today
    at 538,616,284 bytes with `indent=2`, against graphify's own DEFAULT
    536,870,912-byte read cap (`security.py`'s `_MAX_GRAPH_FILE_BYTES`; this
    repo's mise env raises the effective cap to 1 GiB, but the default is
    what an env-less invocation enforces). `chunks.py`'s `assemble()` already
    writes `indent=1` for the identical reason, so this is not a new
    precedent in this codebase, only a second writer adopting it.
    `ensure_ascii=True` stays the implicit default, matching graphify's own
    `export.to_json`: only the indent width is the intentional divergence.
    """
    fd, tmp_name = tempfile.mkstemp(
        dir=graph_path.parent, prefix=graph_path.name + ".", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        tmp.chmod(_GRAPH_MODE)
        tmp.replace(graph_path)
    except BaseException:
        # A partial temp file is not the artifact and must not be mistaken for
        # one — including on KeyboardInterrupt, hence BaseException rather than
        # Exception (mirrors `prose.derive`'s own cleanup, same reasoning).
        tmp.unlink(missing_ok=True)
        raise
