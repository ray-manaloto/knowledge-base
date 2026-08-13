# Copyright (c) 2026 Raymond Manaloto
"""Render `reflections/LESSONS.md` to an arbitrary path, WITHOUT any side effect.

Runs under graphify's BUNDLED interpreter (it imports graphify), invoked by
`kb_setup.lessons` via subprocess — NOT under the KB repo's uv python. Same
foreign-interpreter contract as `_merge_docs.py`, and it exists for the same
reason: `graphify` is not a dependency of `kb-setup`, so nothing in the uv env
can import it.

Usage: python _render_lessons.py <memory-dir> <out-path>
                                 [--graph P --analysis P --labels P]

WHY THIS IS NOT `graphify reflect --out <tmp>`, which would be one less file.
`graphify.reflect.reflect()` has a SECOND output: given a graph it also rewrites
`.graphify_learning.json`, the experiential overlay `graphify query` reads. A
staleness *check* that rewrites a read surface is not read-only — and the failure
is not cosmetic. On the exact run that matters, where the tracked LESSONS.md is
stale, `--out <tmp>` would refresh the sidecar to the NEW state while leaving the
tracked file at the OLD one: the gate would half-apply the very update it is
reporting, and a second run would then compare against a surface the first run
moved. So this script calls the PURE functions (`load_memory_docs` ->
`aggregate_lessons` -> `render_lessons_md`) and writes exactly one file.

`now` is deliberately the real clock, exactly as `graphify reflect` uses it,
rather than a frozen value that would make the comparison agree by construction.
That is safe because the render is time-invariant: `aggregate_lessons` decays
every signal by `0.5 ** (age / half_life)`, so advancing `now` scales every score
by one positive constant, preserving order and sign — and the scores themselves
are never rendered. Measured, not reasoned: at `now + 90 days` (three half-lives)
the output is byte-identical. If a future graphify breaks that, this gate reports
DRIFT, which is the safe direction.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    """Render the lessons doc for ``--memory-dir`` into ``out``; return an exit code."""
    reflect = importlib.import_module("graphify.reflect")
    ap = argparse.ArgumentParser(prog="_render_lessons.py")
    ap.add_argument("memory_dir")
    ap.add_argument("out")
    ap.add_argument("--graph")
    ap.add_argument("--analysis")
    ap.add_argument("--labels")
    opts = ap.parse_args(argv)

    docs = reflect.load_memory_docs(Path(opts.memory_dir))

    node_community = None
    known_nodes = None
    if opts.graph:
        reflect_vars = vars(reflect)
        graph = Path(opts.graph)
        analysis = (
            Path(opts.analysis) if opts.analysis else graph.parent / ".graphify_analysis.json"
        )
        labels = Path(opts.labels) if opts.labels else graph.parent / ".graphify_labels.json"
        node_community = reflect_vars["_load_node_community"](graph, analysis, labels)
        known_nodes = reflect_vars["_load_known_nodes"](graph)

    lessons = reflect.aggregate_lessons(docs, node_community, known_nodes=known_nodes)
    text = reflect.render_lessons_md(lessons)
    out = Path(opts.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"rendered {len(docs)} memories -> {out} ({len(text.encode('utf-8'))} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
