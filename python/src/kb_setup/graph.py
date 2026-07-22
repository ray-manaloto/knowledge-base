"""Build / update the knowledge graph from committed inputs.

Reproducibility model: the graph is rebuildable from two committed things —
`sources/*.manifest` (external repo pins) and `sources/extractions/*.json` (the
non-free host-agent doc extractions). The external repos themselves are cloned on
demand and gitignored. `graphify-out/` (graph.json + manifest.json) is committed
so consumers query on clone and `update` can diff incrementally.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from kb_setup import manifest as mf
from kb_setup.graphify_env import graphify_python

_MERGE_SCRIPT = Path(__file__).with_name("_merge_docs.py")


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def _ensure_clone(m: mf.Manifest) -> None:
    """Clone m.url at m.commit into m.clone_dir (gitignored). Re-clones if the
    working tree is missing or lacks git history."""
    d = m.clone_dir
    if not (d / ".git").is_dir():
        if d.exists():
            shutil.rmtree(d)
        print(f"  cloning {m.name} @ {m.commit[:10]}")
        subprocess.run(
            ["git", "clone", "--quiet", "--branch", m.ref, m.url, str(d)],
            check=True, timeout=600,
        )
    subprocess.run(
        ["git", "-C", str(d), "checkout", "--quiet", m.commit], check=True, timeout=120
    )


def build(repo_root: Path) -> None:
    """Reproduce the full graph from committed inputs (deterministic, no LLM)."""
    sources = repo_root / "sources"
    out = repo_root / "graphify-out" / "graph.json"
    manifests = mf.load_all(sources)
    if not manifests:
        raise SystemExit("no sources/*.manifest found")

    print(f"[kb-build] {len(manifests)} source(s)")
    for m in manifests:
        _ensure_clone(m)

    # Code graph (AST — free, deterministic). `--force` = clean full re-scan (skip
    # the incremental manifest gate + cache) so a rebuild is a true reproduction,
    # not a diff against stale state. First source seeds graph.json; further
    # sources merge in via merge-graphs.
    first, *rest = manifests
    _run(
        ["graphify", "extract", f"sources/{first.name}", "--code-only", "--force", "--out", "."],
        repo_root,
    )
    for m in rest:
        _run(["graphify", "extract", f"sources/{m.name}", "--code-only", "--force"], repo_root)
        sub = f"sources/{m.name}/graphify-out/graph.json"
        _run(["graphify", "merge-graphs", str(out), sub, "--out", str(out)], repo_root)

    # Doc layer: replay the committed host-agent extractions (free — no subagents).
    gpy = graphify_python(repo_root)
    chunks = sorted((sources / "extractions").glob("*.json"))
    print(f"[kb-build] merging {len(chunks)} committed doc extraction(s)")
    for chunk in chunks:
        name = chunk.stem.removesuffix("-docs")
        root = str((sources / name).resolve())
        _run([gpy, str(_MERGE_SCRIPT), str(chunk), root, str(out)], repo_root)

    print("[kb-build] done — graphify-out/graph.json reproduced")


def update_all(repo_root: Path) -> None:
    """Advance every github-repo source to its latest upstream commit."""
    manifests = mf.load_all(repo_root / "sources")
    repos = [m for m in manifests if m.kind == "code"]
    if not repos:
        print("[kb-update] no code-repo manifests to update")
        return
    print(f"[kb-update] checking {len(repos)} source(s) for upstream updates")
    for m in repos:
        update(repo_root, m.name)


def update(repo_root: Path, name: str) -> None:
    """Advance one source to its latest upstream commit and incrementally re-extract."""
    sources = repo_root / "sources"
    m = mf.load(sources / f"{name}.manifest")
    latest = mf.latest_commit(m)
    if latest == m.commit:
        print(f"[kb-update] {name} already at latest {latest[:10]} — nothing to do")
        return

    print(f"[kb-update] {name}: {m.commit[:10]} -> {latest[:10]}")
    m = mf.write_commit(m, latest)
    _ensure_clone(m)

    # Incremental CODE re-extract (AST — free; MD5-diffs graphify-out/manifest.json).
    _run(["graphify", "update", f"sources/{name}"], repo_root)
    print(
        f"[kb-update] {name} code updated. NOTE: changed DOCS are not re-extracted "
        f"here — host-agent extraction (a Claude Code session) must re-run on changed "
        f"docs and refresh sources/extractions/{name}-docs.json (the semantic cache "
        f"skips unchanged docs)."
    )
