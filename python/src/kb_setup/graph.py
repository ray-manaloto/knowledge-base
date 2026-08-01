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
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import manifest as mf
from kb_setup import prose
from kb_setup.graphify_env import clean_env, graphify_exe, graphify_python

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
        [graphify_exe(repo_root), "extract", f"sources/{name}", "--code-only", "--force"],
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

    # FIRST — before `mf.load_all` reads a single manifest. The direction is the
    # point: an input edited mid-build did not reach this graph, so recording its
    # pre-read digest makes the very next check FIRE. Digesting later would record
    # content the build never saw and bless a graph the edit never reached, which
    # is the one direction this detector must never fail in.
    #
    # It sat after `load_all` when this landed, which is 17 lines too late — the
    # manifests were already `read_text`-ed by then, so an edit in that window
    # produced exactly the false green the comment claimed to prevent. Keep this
    # line at the top of the function; nothing above it may touch `sources/`.
    # (Cold lane, round 1.)
    inputs = _input_fingerprints(repo_root)

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
    #
    # A `kind = docs` manifest is NOT ASKED. `--code-only` is defined by graphify as
    # "index code … and skip doc/paper/image files", so running it over a docs mirror
    # is a guaranteed-empty full AST scan of every markdown file, on every build. The
    # reason to skip it is not only the waste: a docs manifest that never ran and a
    # code repo that ran and produced nothing are DIFFERENT ANSWERS, and until now
    # both printed the same `[skip] … no code nodes` line. That is the
    # not-applicable/could-not-check collapse this repo refuses everywhere else
    # (`currency`'s DRIFT/SKIP/OK). Declaring the kind makes the build say which.
    docs_only = [m.name for m in manifests if m.kind == "docs"]
    askable = [m.name for m in manifests if m.name not in docs_only]
    with_code = [name for name in askable if _extract_code(repo_root, name)]
    for name in docs_only:
        print(f"  [docs] {name}: kind=docs — no AST pass; prose comes from the extraction wave")
    skipped = [name for name in askable if name not in with_code]
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
        _run(
            [graphify_exe(repo_root), "merge-graphs", str(out), str(sub), "--out", str(out)],
            repo_root,
        )

    # Doc layer: replay the committed host-agent extractions (free — no subagents).
    gpy = graphify_python(repo_root)
    chunks = sorted((sources / "extractions").glob("*.json"))
    print(f"[kb-build] merging {len(chunks)} committed doc extraction(s)")
    for chunk in chunks:
        name = chunk.stem.removesuffix("-docs")
        root = str((sources / name).resolve())
        _run([gpy, str(_MERGE_SCRIPT), str(chunk), root, str(out)], repo_root)

    # The prose-only derived graph, from the graph we just built. Here and not in
    # a separate task-you-must-remember: it is a pure function of graph.json, so
    # any build that does not refresh it leaves a scoped corpus describing an
    # older one — and a retrieval figure measured against a stale corpus is the
    # inherited-number trap with extra steps. `kb-prose` re-derives it alone.
    prose.derive_for(repo_root)

    _stamp_build(repo_root, inputs)
    print("[kb-build] done — graphify-out/graph.json + graph-prose.json reproduced")


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


def _input_fingerprints(repo_root: Path) -> dict[str, str] | None:
    """sha256 over every committed input `currency.toml` declares, or None.

    None means "could not be read", which `write_stamp` records as the ABSENCE of
    an input map — so the staleness check reports *not verifiable* rather than
    comparing against a partial one. Best-effort, like the stamp itself: a build
    must not fail over its own bookkeeping.
    """
    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return None
        return sync.input_fingerprints(repo_root, spec)
    except (OSError, ValueError, ImportError) as e:
        print(f"[kb-build] WARNING: could not fingerprint the corpus inputs: {e}")
        return None


def _stamp_build(repo_root: Path, inputs: dict[str, str] | None = None) -> None:
    """Record which graphify version built these artifacts (currency step 1).

    graphify stamps nothing itself — `export.to_json()` writes only
    `built_at_commit` — so without this sidecar "which version built this graph?"
    is unanswerable from the artifact, and a graph built by a stale binary is
    indistinguishable from a current one.

    The version recorded is the one that ACTUALLY RAN (`graphify --version` on
    the resolved binary), never the pin. Since #40 that means resolving it the
    SAME way the build did — through `graphify_exe` — because `observed_version`
    resolves a bare name through PATH, and the build no longer does. Reading the
    two differently would stamp one binary's version onto another binary's graph:
    the precise unfalsifiable state this stamp exists to prevent, and one that
    did not exist while both sides happened to read PATH.
    Best-effort — a build must not fail over its stamp.
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
        # Resolved exactly as the build resolved it (see the docstring).
        # Unconditional, not guarded on `spec.binary`: `_currency_spec` selects
        # by `name == _STAMPED_TOOL`, so the spec reaching here is always
        # graphify's, and the build always ran `graphify_exe`. An earlier draft
        # guarded on `spec.binary == _STAMPED_TOOL`, which compared a BINARY name
        # to a TOOL name — unreachable in the normal case and, for a config
        # setting `binary` to anything else, a silent fall back to the
        # PATH-resolved reading this exists to eliminate.
        version = sync.observed_version(graphify_exe(repo_root))
        source_ref = sync.manifest_ref(repo_root, spec)
        path = sync.write_stamp(
            repo_root, spec, version=version, source_ref=source_ref, inputs=inputs
        )
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


def update_all(repo_root: Path) -> int:
    """Advance every tracked source to its latest upstream commit.

    `kind = docs` sources are INCLUDED, and the omission is worth recording: this
    filtered to `kind == "code"` when the only kind in use was `code`, so adding
    the docs kind silently excluded every docs mirror from the bulk path. The
    changed-page worklist — the entire reason a mirror is pinned — would then only
    ever appear when someone named the source by hand, which is the failure mode
    where a check exists and never runs. (Cold lane, P2.)
    """
    manifests = mf.load_all(repo_root / "sources")
    repos = [m for m in manifests if m.kind in {"code", "docs"}]
    if not repos:
        print("[kb-update] no manifests to update")
        return 0
    print(f"[kb-update] checking {len(repos)} source(s) for upstream updates")
    # WORST rc, not the last one: a bulk run must not report success because the
    # source that failed happened not to sort last.
    return max((update(repo_root, m.name) for m in repos), default=0)


def update(repo_root: Path, name: str) -> int:
    """Advance one source to its latest upstream commit and incrementally re-extract.

    Returns a process exit code. A docs pin whose diff FAILED returns 1: the pin
    is correctly left unmoved, but the CLI used to `return 0` regardless, so the
    one failure path this module has was invisible to anything reading an rc.
    (Cold lane round 2, P2 — the round-1 fix stopped the state corruption and
    left the signal broken.)
    """
    sources = repo_root / "sources"
    m = mf.load(sources / f"{name}.manifest")
    latest = mf.latest_commit(m)
    if latest == m.commit:
        print(f"[kb-update] {name} already at latest {latest[:10]} — nothing to do")
        return 0

    print(f"[kb-update] {name}: {m.commit[:10]} -> {latest[:10]}")
    if m.kind == "docs":
        return _advance_docs_pin(m, latest)

    m = mf.write_commit(m, latest)
    _ensure_clone(m)

    # Incremental CODE re-extract (AST — free; MD5-diffs graphify-out/manifest.json).
    _run([graphify_exe(repo_root), "update", f"sources/{name}"], repo_root)
    print(
        f"[kb-update] {name} code updated. NOTE: changed DOCS are not re-extracted "
        f"here — host-agent extraction (a Claude Code session) must re-run on changed "
        f"docs and refresh sources/extractions/{name}-docs.json (the semantic cache "
        f"skips unchanged docs)."
    )
    return 0


#: Extensions the host-agent extraction wave can actually read. A docs mirror is
#: still a git repo, so its own metadata (`docs_manifest.json`, workflows, README
#: scaffolding) changes on syncs that touched no documentation at all. Listing
#: those as "re-extraction work" would spend host-agent tokens on a build script.
#: (Cold lane, P2.)
_DOC_SUFFIXES = frozenset({".md", ".mdx", ".markdown", ".rst", ".txt"})

#: `git diff --name-status` emits `R<score>\told\tnew` for a rename or copy — two
#: paths where every other status has one.
_RENAME_PATHS = 2


def _is_doc(path: str) -> bool:
    return Path(path).suffix.lower() in _DOC_SUFFIXES


def _classify_change(status: str, paths: list[str]) -> tuple[list[str], list[str]]:
    """One `--name-status` row -> (paths to re-extract, stale extractions to drop).

    Both lists empty means the row touched no document — a mirror's own metadata,
    which is real churn but not extraction work.
    """
    if not any(_is_doc(p) for p in paths):
        return [], []
    if status.startswith("D"):
        return [], [p for p in paths if _is_doc(p)]
    if status.startswith(("R", "C")) and len(paths) == _RENAME_PATHS:
        old, new = paths
        extract = [new] if _is_doc(new) else []
        # A COPY leaves the original in place; only a RENAME makes it stale.
        # Treating `C###` like `R###` queued a file that still exists for
        # removal. Bounded — the worklist is advisory, read by a host agent
        # rather than executed — but it would send that agent to delete a live
        # page's extraction. (Cold lane round 2, P2.)
        if status.startswith("C"):
            return extract, []
        return extract, ([old] if _is_doc(old) else [])
    return [p for p in paths if _is_doc(p)], []


def _advance_docs_pin(m: mf.Manifest, latest: str) -> int:
    """Advance a `kind = docs` pin, but ONLY once its worklist has been reported.

    THE POINT OF A DOCS MIRROR, and the reason `kind` had to stop being inert
    metadata. Fingerprinting a page (`currency.toml` `docs_watch`) proves THAT it
    changed and can never say WHAT — knowledge-base#76 was opened on three moved
    sha256 values with no way to read the delta, and the only reason that session
    recovered one was that a gitignored `.agent/kb/raw/` copy of the old text
    happened to survive. A `git clean -xdf` erases that; a pinned clone does not.

    ORDER IS THE WHOLE CORRECTNESS ARGUMENT, and the first version got it wrong.
    It wrote the pin, then diffed, and on a diff failure printed "UNKNOWN, not
    empty — re-run". But the pin had already moved, so the re-run hit
    `latest == m.commit` and reported *"already at latest — nothing to do"*: the
    worklist was not merely unreported, it was **unrecoverable**, and the careful
    UNKNOWN message pointed at a retry that could no longer work. The comment
    there read "a report gap, not a build failure", which is exactly the kind of
    self-reassurance a cold reviewer is for — it was found by one (P2).

    So the clone is brought to `latest` in memory, the diff runs, and the manifest
    is written only if the diff SUCCEEDED. A failure now leaves the pin where it
    was, which makes the retry the message promises actually work.

    Printed, never acted on. Re-extraction is a Claude Code session's job
    (invariant: the host agent IS the extraction LLM), so this task's contract is
    to hand over an accurate worklist and stop.
    """
    advanced = replace(m, commit=latest)
    _ensure_clone(advanced)
    diff = subprocess.run(
        ["git", "-C", str(advanced.clone_dir), "diff", "--name-status", m.commit, latest],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if diff.returncode != 0:
        print(
            f"[kb-update] {m.name}: doc diff FAILED "
            f"({diff.stderr.strip() or 'no stderr'}) — the changed-page list is "
            f"UNKNOWN, not empty, so the pin was NOT advanced (still "
            f"{m.commit[:10]}). Re-run to retry."
        )
        return 1

    mf.write_commit(m, latest)
    _print_doc_worklist(m.name, diff.stdout)
    return 0


def _print_doc_worklist(name: str, name_status: str) -> None:
    """Turn `git diff --name-status` into a worklist that says what to DO.

    `--name-only` was the first version and it flattened three different jobs into
    one list (cold lane, P2). A deletion upstream is not re-extraction work — it is
    a *stale extraction to remove*, and reporting it as a page to read sends the
    host agent after a file that no longer exists. A rename is the same, plus the
    old path that has to be dropped. So the status column is kept and the output is
    grouped by the action each change implies.
    """
    extract: list[str] = []
    drop: list[str] = []
    other = 0
    for line in name_status.splitlines():
        if not line.strip():
            continue
        status, *paths = line.split("\t")
        if not paths:
            continue
        did_extract, did_drop = _classify_change(status, paths)
        if not did_extract and not did_drop:
            other += 1
            continue
        extract.extend(did_extract)
        drop.extend(did_drop)

    if not extract and not drop:
        # Distinct from "0 files changed": non-document churn is a real answer —
        # the mirror synced, and nothing the extraction wave reads was touched.
        suffix = f" ({other} non-document file(s) changed)" if other else ""
        print(f"[kb-update] {name}: pin advanced, no document changes{suffix}")
        return

    print(f"[kb-update] {name}: pin advanced — re-extraction worklist:")
    for path in extract:
        print(f"    re-extract  {path}")
    for path in drop:
        print(f"    REMOVE stale extraction for  {path}")
    if other:
        print(f"    ({other} non-document file(s) changed — not extraction work)")
