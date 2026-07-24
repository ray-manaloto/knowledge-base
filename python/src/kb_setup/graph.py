"""Build / update the knowledge graph from committed inputs.

Reproducibility model: the graph is rebuildable from two committed things —
`sources/*.manifest` (external repo pins) and `sources/extractions/*.json` (the
non-free host-agent doc extractions). The external repos themselves are cloned on
demand and gitignored. `graphify-out/` (graph.json + manifest.json) is committed
so consumers query on clone and `update` can diff incrementally.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import manifest as mf
from kb_setup.graphify_env import clean_env, graphify_python

if TYPE_CHECKING:
    from kb_setup.currency.config import ToolSpec

_MERGE_SCRIPT = Path(__file__).with_name("_merge_docs.py")

# The tool whose artifacts `kb-build` produces. Named explicitly so a
# multi-tool currency.toml cannot silently stamp the wrong tool.
_STAMPED_TOOL = "graphify"


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"  $ {' '.join(cmd)}")
    # clean_env: no non-Claude provider key reaches graphify (Claude-Code-only).
    subprocess.run(cmd, cwd=cwd, check=True, env=clean_env())


def _ensure_clone(m: mf.Manifest) -> None:
    """Clone m.url at m.commit into m.clone_dir (gitignored).

    Re-clones if the working tree is missing or lacks git history.
    """
    d = m.clone_dir
    if not (d / ".git").is_dir():
        if d.exists():
            shutil.rmtree(d)
        print(f"  cloning {m.name} @ {m.commit[:10]}")
        subprocess.run(
            ["git", "clone", "--quiet", "--branch", m.ref, m.url, str(d)],
            check=True,
            timeout=600,
        )
    # An EXISTING clone predates any pin advance, so the newly-pinned commit is
    # simply not in it yet and `checkout` dies with "fatal: unable to read tree".
    # Measured 2026-07-23: `kb-update -- claude-plugins-community` advanced the pin
    # to 086db464, the local clone still sat at 07fb1efe, and the whole task
    # aborted — i.e. update was broken for every source whose clone already
    # existed, which is every source after its first build. Fetch when (and only
    # when) the object is absent, so the common no-op path stays offline.
    have = subprocess.run(
        ["git", "-C", str(d), "cat-file", "-e", f"{m.commit}^{{commit}}"],
        check=False,
        capture_output=True,
        timeout=60,
    )
    if have.returncode != 0:
        print(f"  fetching {m.name} @ {m.commit[:10]} (not in local clone)")
        subprocess.run(
            ["git", "-C", str(d), "fetch", "--quiet", "origin", m.ref],
            check=True,
            timeout=600,
        )
    subprocess.run(["git", "-C", str(d), "checkout", "--quiet", m.commit], check=True, timeout=120)


def _extract_code(repo_root: Path, name: str) -> bool:
    """AST-extract one source's code into its own sub-graph; True iff it made nodes.

    `--force` = clean full re-scan, no cache/manifest gate (a true reproduction). A
    prose-only repo yields an empty graph and graphify exits non-zero; that is
    NON-fatal here (its value comes from the host-agent prose wave), so the status is
    swallowed and emptiness is read from the sub-graph.
    """
    print(f"  $ graphify extract sources/{name} --code-only --force")
    subprocess.run(
        ["graphify", "extract", f"sources/{name}", "--code-only", "--force"],
        cwd=repo_root,
        check=False,
        env=clean_env(),
    )
    sub = repo_root / "sources" / name / "graphify-out" / "graph.json"
    if not sub.is_file():
        return False
    try:
        data = json.loads(sub.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return False
    return bool(data.get("nodes"))


def build(repo_root: Path) -> None:
    """Reproduce the full graph from committed inputs (deterministic, no LLM)."""
    sources = repo_root / "sources"
    out = repo_root / "graphify-out" / "graph.json"
    manifests = mf.load_all(sources)
    if not manifests:
        raise SystemExit("no sources/*.manifest found")

    # Invalidate the stamp BEFORE anything touches graph.json. `build()` overwrites
    # the artifact at the seed step but only stamps at the very end, so any abort in
    # between — a merge failure, Ctrl-C — used to leave a NEW artifact under the OLD
    # stamp, which then asserted it was built by the pinned version. Clearing first
    # makes every abort fail closed as "never stamped".
    _clear_stamp(repo_root)

    print(f"[kb-build] {len(manifests)} source(s)")
    for m in manifests:
        _ensure_clone(m)

    # Code graph (AST — free, deterministic). Each source extracts into its own
    # sub-graph; prose-only repos (no code) are skipped WITHOUT aborting the build —
    # their content is added later by the host-agent prose wave, not here.
    with_code = [m.name for m in manifests if _extract_code(repo_root, m.name)]
    skipped = [m.name for m in manifests if m.name not in with_code]
    for name in skipped:
        print(f"  [skip] {name}: no code nodes — prose-only, deferred to the extraction wave")
    if not with_code:
        raise SystemExit("no source produced code nodes")

    # Seed graph.json from the first code-bearing source; merge the rest.
    seed, *rest = with_code
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(sources / seed / "graphify-out" / "graph.json", out)
    print(f"[kb-build] seeded graph.json from {seed}")
    for name in rest:
        sub = sources / name / "graphify-out" / "graph.json"
        _run(["graphify", "merge-graphs", str(out), str(sub), "--out", str(out)], repo_root)

    # Doc layer: replay the committed host-agent extractions (free — no subagents).
    gpy = graphify_python(repo_root)
    chunks = sorted((sources / "extractions").glob("*.json"))
    print(f"[kb-build] merging {len(chunks)} committed doc extraction(s)")
    for chunk in chunks:
        name = chunk.stem.removesuffix("-docs")
        root = str((sources / name).resolve())
        _run([gpy, str(_MERGE_SCRIPT), str(chunk), root, str(out)], repo_root)

    _stamp_build(repo_root)
    print("[kb-build] done — graphify-out/graph.json reproduced")


def _currency_spec(repo_root: Path) -> ToolSpec | None:
    """The tool whose build artifacts THIS repo stamps, or None.

    Selected by NAME, not by "first spec that declares a stamp". `currency.toml`
    is explicitly multi-tool, so taking the first stamped entry would write
    `graphify --version` into whichever tool happened to sort first.
    """
    from kb_setup.currency import config

    return next((s for s in config.load(repo_root) if s.name == _STAMPED_TOOL and s.stamp), None)


def _clear_stamp(repo_root: Path) -> None:
    """Remove the build stamp so an aborted build cannot leave a stale one."""
    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return
        path = sync.stamp_path(repo_root, spec)
        if path is not None and path.exists():
            path.unlink()
            print(f"[kb-build] cleared {path.name} — it is rewritten only on success")
    except (OSError, ValueError, ImportError) as e:
        print(f"[kb-build] WARNING: could not clear the currency stamp: {e}")


def _stamp_build(repo_root: Path) -> None:
    """Record which graphify version built these artifacts (currency step 1).

    graphify stamps nothing itself — `export.to_json()` writes only
    `built_at_commit` — so without this sidecar "which version built this graph?"
    is unanswerable from the artifact, and a graph built by a stale binary is
    indistinguishable from a current one.

    The version recorded is the one that ACTUALLY RAN (`graphify --version` on
    the resolved binary), never the pin: `_run` invokes bare `graphify` through
    PATH, and a stale install dir ahead of the mise shims is exactly the drift
    this is meant to expose. Best-effort — a build must not fail over its stamp.
    """
    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return
        # NO fallback to the pin. Falling back would stamp the version we HOPED
        # ran, turning an unreadable binary into a false "in sync" — the exact
        # laundering this stamp exists to prevent. An empty version is written
        # as empty, and `check_sync` then reports "built by an unknown version".
        version = sync.observed_version(spec.binary)
        source_ref = sync.manifest_ref(repo_root, spec)
        path = sync.write_stamp(repo_root, spec, version=version, source_ref=source_ref)
        if version:
            print(f"[kb-build] stamped {path.name}: built by graphify {version}")
        else:
            print(
                f"[kb-build] WARNING: stamped {path.name} with an UNKNOWN version — "
                f"`{spec.binary} --version` could not be read, so currency step 1 "
                f"will report the graph as not verifiably built by the pin."
            )
    except (OSError, ValueError, ImportError) as e:
        print(f"[kb-build] WARNING: could not write the currency stamp: {e}")


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
