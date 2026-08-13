# Copyright (c) 2026 Raymond Manaloto
"""Generate every graphify output artifact from the current graph.

Single source of truth: the `_ARTIFACTS` registry (data, not copy-paste). Each
entry reads graphify-out/graph.json and writes a distinct file, so the set is
regenerable on demand and none of it needs committing (only graph.json +
manifest.json are). Runs sequentially (safe — no shared-file races).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from kb_setup import prose, stamps
from kb_setup.graphify_env import clean_env, ensure_runtime_deps, graphify_exe

# svg does a full matplotlib spring_layout: O(n^2)-ish (useless hairball at scale)
# AND it feeds node labels through matplotlib mathtext, so any label containing a
# bare `$` raises `ParseException: Expected end of text, found '$'` and fails the
# whole task. graphify already skips its own graph.html above 5000 nodes for the
# same reason; we mirror that for svg. Verified 2026-07-22: a 61,767-node graph
# with a `$`-bearing label crashed `graphify export svg` (rc=1).
_SVG_NODE_LIMIT = 5000

# name -> graphify SUBCOMMAND argv (the binary is prepended at run time by
# `graphify_exe`, so no entry can hard-code a PATH-resolved `graphify` — see #40).
# All read graph.json; each writes its own file(s).
# neo4j/falkordb both emit cypher.txt (OpenCypher, usable by either) — one entry.
# svg needs scipy (ensured below) and is slow at scale (full spring_layout).
_ARTIFACTS: list[tuple[str, list[str], str]] = [
    ("report", ["cluster-only", ".", "--no-label"], "GRAPH_REPORT.md + graph.html"),
    ("tree", ["tree"], "GRAPH_TREE.html"),
    ("callflow", ["export", "callflow-html"], "*-callflow.html"),
    ("graphml", ["export", "graphml"], "graph.graphml (Gephi/yEd)"),
    ("cypher", ["export", "neo4j"], "cypher.txt (Neo4j/FalkorDB)"),
    ("wiki", ["export", "wiki"], "wiki/ (agent-crawlable)"),
    ("obsidian", ["export", "obsidian"], "obsidian/ (one note per node)"),
    ("svg", ["export", "svg"], "graph.svg (slow at scale; needs scipy)"),
]

#: Entries whose graphify subcommand REWRITES graph.json wholesale, rather than
#: only reading it. Only "report" (`cluster-only`) does — it shares the exact
#: CLI branch `kb-label` runs (`cli.py`, `cmd in ("cluster-only", "label")`),
#: which loads graph.json via `build_from_json` and rewrites it via `to_json`
#: at the end. Every other entry is a pure export — it reads graph.json and
#: writes a DIFFERENT file — so gating the post-run prose re-derivation on
#: this set is what keeps a `wiki`/`graphml`/`svg`/... run from re-deriving a
#: prose graph whose source bytes it never touched. (Until the 0.9.34 bump
#: this set also gated a hyperedge capture/reattach carry around the rewrite;
#: retired — `hyperedges.py`'s module docstring records why.)
_REWRITES_GRAPH = frozenset({"report"})


def _node_count(graph: Path) -> int:
    """Node count from graph.json (0 if unreadable — callers gate on it)."""
    try:
        return len(json.loads(graph.read_text(encoding="utf-8")).get("nodes", []))
    except OSError, json.JSONDecodeError:
        return 0


def _run_generator(repo_root: Path, exe: str, args: list[str]) -> int:
    """Run one artifact command and translate incomplete evidence to failure."""
    proc = subprocess.run(
        [exe, *args],
        cwd=repo_root,
        env=clean_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    from kb_setup import graphify_health

    receipt = graphify_health.assess(
        graphify_health.GraphifyOperation.ARTIFACT,
        graphify_health.GraphifyEvidence(
            observed=True,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        ),
    )
    return 0 if receipt.state is graphify_health.GraphifyState.COMPLETE else 3


def generate(repo_root: Path, only: list[str] | None = None) -> int:
    """Generate all artifacts (or the subset in `only`). Returns non-zero on any failure."""
    graph = repo_root / "graphify-out" / "graph.json"
    if not graph.is_file():
        raise SystemExit("graphify-out/graph.json missing — run `mise run kb-build` first")

    ensure_runtime_deps(repo_root)  # scipy for svg, etc.

    selected = [a for a in _ARTIFACTS if not only or a[0] in only]

    # Skip svg on a large graph — it is both doomed (mathtext `$` crash) and
    # useless (unreadable hairball). Explicit skip, NOT a silent drop: an
    # explicitly-requested `only=['svg']` still runs so the failure is visible.
    n_nodes = _node_count(graph)
    if not only and n_nodes > _SVG_NODE_LIMIT:
        before = len(selected)
        selected = [a for a in selected if a[0] != "svg"]
        if len(selected) < before:
            print(
                f"[kb-artifacts] skipping svg: {n_nodes} nodes > {_SVG_NODE_LIMIT} "
                "(full spring_layout is unreadable + crashes on `$` labels)"
            )

    print(f"[kb-artifacts] generating {len(selected)} artifact(s)")
    # BEFORE the generators run (#182). Bracketing this loop is what lets the
    # stamp certify exactly the views this run regenerated — a full run, a
    # partial `only=` run and a run whose generators all no-op each come out
    # right, with nothing enumerated here. It replaces a boolean that asserted
    # "I regenerated everything", which was true for a full run and unsound in
    # general: it certified views whose bytes had changed at some earlier,
    # unobserved moment. See `sync.view_records`.
    views_before = stamps.snapshot_views(repo_root)
    exe = graphify_exe(repo_root)
    failures: list[str] = []
    for name, args, desc in selected:
        print(f"  → {name}: {desc}")
        rewrites = name in _REWRITES_GRAPH
        # clean_env: no non-Claude backend key reaches graphify (Gemini-free).
        rc = _run_generator(repo_root, exe, args)
        if rc != 0:
            print(f"    FAILED ({name}, rc={rc})")
            failures.append(name)
        elif rewrites:
            # graph.json just changed underneath us — every OTHER writer of it
            # in this codebase re-derives the prose graph as part of the same
            # operation (`graphify_ops.merge_chunk`, `graphify_ops.label`, and
            # `graph.build` via `label`); `report` was the one exception, so
            # `kb-query --prose` went on describing whatever corpus existed
            # before this run (#175 cold review, finding 3).
            if _derive_prose(repo_root, name) != 0:
                failures.append(name)

    if failures:
        print(f"[kb-artifacts] {len(failures)} failed: {', '.join(failures)}")
        return 1
    print("[kb-artifacts] all artifacts generated")
    # Reached only when every selected generator returned 0 (the `failures` branch
    # returns 1 above), so every view that moved inside this bracket moved because
    # a generator that SUCCEEDED wrote it.
    stamps.refresh_after_regen(repo_root, tag="kb-artifacts", views_before=views_before)
    return 0


def _derive_prose(repo_root: Path, name: str) -> int:
    """Re-derive the prose graph after `name` rewrote graph.json; 1 on failure.

    Mirrors `graphify_ops._derive_prose`'s semantics as its own small copy
    rather than a shared import: that function is private to `graphify_ops`'s
    own two callers (`merge_chunk`, `label`), and this one is small enough
    that duplicating it costs less than coupling two modules with different
    jobs over one helper.
    """
    try:
        prose.derive_for(repo_root)
    except (OSError, ValueError, SystemExit) as exc:
        print(
            f"    FAILED ({name}: rewrote graph.json but the prose graph could not "
            f"be re-derived: {exc})"
        )
        return 1
    return 0
