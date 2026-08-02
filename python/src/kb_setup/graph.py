"""Build / update the knowledge graph from committed inputs.

Reproducibility model: the graph is rebuildable from two committed things —
`sources/*.manifest` (external repo pins) and `sources/extractions/*.json` (the
non-free host-agent doc extractions). The external repos themselves are cloned on
demand and gitignored. `graphify-out/` (graph.json + manifest.json) is committed
so consumers query on clone and `update` can diff incrementally.
"""

from __future__ import annotations

import hashlib
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


#: THIS repo's own code, indexed into the aggregate graph beside the pinned
#: sources. Two trees rather than one, and the second is not an afterthought:
#: `python/` holds the library dotfiles consumes as a pinned git dependency, while
#: the root `tests/` holds the 41 files Ray widened this to include (2026-07-31).
#:
#: ⚠️ THAT WIDENING DOES NOT YET DELIVER WHAT IT WAS FOR — knowledge-base#101.
#: Its purpose was "which tests cover this symbol?", and that is unavailable FOR
#: OUR CODE. It is a config gap of ours, NOT a tool gap — a first pass here said
#: otherwise and an adversarial verifier refuted it. `affected` links tests fine:
#: `affected "_state"` returns 9 test functions under `tests/`, and a
#: `conftest.py` fixture reaches 17 test functions across two modules.
#:
#: The cause is that these are TWO extraction runs and `merge-graphs`
#: re-namespaces ids per merge, so the two halves land in disjoint namespaces
#: (`knowledge-base::python::…` vs `tests::…`) and no edge can span them. A/B on
#: byte-identical syntax: `sync.restamp_artifacts(...)` at `graph.py:252` gets an
#: edge; the same call at `test_currency_staleness.py:378` does not. Edge census:
#: 3,368 tests-touching, **0** crossing, against a control of 2,194 within
#: `python/`. `cognee` — one pinned source, ONE extraction run — has 10,099
#: test<->src edges in the same graph file. One variable differs.
#:
#: RESOLVED 2026-08-02 by the constants below. Kept as history because it is the
#: only place the pre-fix measurement survives, and because the refuted reading
#: ("a graphify limitation") is the one a future reader will reach for again.
#:
#: The `_SELF_TREES = ("python", "tests")` tuple this paragraph used to annotate
#: is GONE, not merely unused. Once one root covers both trees it had no reader —
#: a constant nothing consults is a claim about the code that the code does not
#: make, and leaving it would have let a later edit "restore" the loop by
#: consulting it again. The two trees are still exactly what gets indexed; the
#: root below is simply what contains them.

#: ONE extraction root covering both trees, which is THE FIX for the above.
#: `merge-graphs` re-namespaces ids on every merge, so two runs can only ever
#: produce two namespaces; the crossing edge has to exist *within a single
#: extraction* or it cannot exist at all. graphify's `extract` takes exactly one
#: path, so the one root that contains both of ours is the repo root.
#:
#: Indirect arm: `cognee` is one pinned source extracted in ONE run, and it has
#: 10,099 test<->src edges in this same graph file. That is evidence the shape
#: works, NOT evidence this change works — the direct arm is the depth test in
#: `tests/test_affected_covers_tests.py`, which must move from red to green
#: across the rebuild that carries this.
_SELF_ROOT = "."

#: Where the single self sub-graph is written, and the reason this constant
#: exists at all. `graphify extract <path>` defaults its output to
#: `<path>/graphify-out/`, so extracting the repo root would write the AGGREGATE
#: `graphify-out/graph.json` — overwriting a 133k-node merged corpus with a
#: root-only extraction. `--out` redirects it. Gitignored, derived, disposable.
_SELF_OUT = ".self-graph"

#: The aggregate as it stands BEFORE our own code is merged in — everything the
#: pinned manifests and committed doc chunks contribute, and nothing of ours.
#: `kb-watch` restarts from this rather than appending to graph.json, which is the
#: only thing that makes repeated refreshes idempotent (see `refresh_self`).
#: Public because the tests import it: a restated literal keeps passing after a
#: rename, asserting on a filename nothing writes.
BASE_GRAPH_NAME = ".base-graph.json"

#: Where `scope = study` sources land — repos we are analysing rather than
#: learning from. Kept out of the aggregate because merging them into it took
#: graph.json 7.6 MiB past graphify's 512 MiB cap and failed the build outright:
#: 71.0 MB of sub-graphs became >=155 MiB of aggregate growth, since
#: `merge-graphs` re-namespaces ids and expands edges on every merge. They are
#: still fully ingested — no exclusions — just not ranked beside the corpus.
STUDY_GRAPH_NAME = "study-graph.json"

#: sha256 of the `graph.json` that the base snapshot is known to compose with.
#: `refresh_self` refuses unless the current `graph.json` still matches it.
#:
#: THIS EXISTS BECAUSE THE SNAPSHOT ALONE IS NOT SAFE, found by a cold review.
#: `.base-graph.json` is written only by `build()`, but it is NOT the only writer
#: of `graph.json` — `kb-merge` folds in a doc-extraction chunk and `kb-label`
#: rewrites the graph outright, both documented as legitimate no-LLM steps
#: BETWEEN builds. So `kb-build` → `kb-merge` → `kb-watch` restored a base that
#: predates the merge, silently discarding it, and then restamped the result as
#: verified — `kb-currency-check` reported clean. Silent data loss wearing a
#: green light, which is the one failure mode the whole currency engine exists to
#: prevent.
BASE_GUARD_NAME = ".base-graph.sha256"


def _self_subgraph(repo_root: Path) -> Path:
    """The single sub-graph the self extraction writes. One place, one spelling."""
    return repo_root / _SELF_OUT / "graphify-out" / "graph.json"


def _self_extract_argv(repo_root: Path) -> list[str]:
    """The ONE argv both self-extraction call sites use.

    Stated once because the two call sites drifting apart is precisely how the
    `update`-vs-`extract` defect arrived: two spellings of "extract our code",
    one of which produced different `source_file` values. A shared builder makes
    that class of drift unrepresentable rather than merely discouraged.
    """
    return [
        graphify_exe(repo_root),
        "extract",
        _SELF_ROOT,
        "--code-only",
        "--force",
        "--out",
        _SELF_OUT,
    ]


def _extract_self(repo_root: Path) -> list[Path]:
    """AST-extract this repo's OWN code; return each sub-graph for merging.

    Why this exists at all. `graphify affected "<symbol>"` is the blast-radius
    question, and it was unanswerable about our own code for a reason that had
    nothing to do with graphify: `python/src/kb_setup/` was simply never
    extracted — 0 of 37 tracked files, control-armed on `source_file` against
    `graphify/extractors/` -> 429 and `cognee/api/` -> 793. Every such query
    returned "No unique node match", which is the SAME string graphify returns for
    a symbol that does not exist. A missing INDEX and a missing SYMBOL were
    indistinguishable, so the failure announced nothing.

    Emptiness is NOT tolerated here, unlike `_extract_code`. That function
    swallows a non-zero status because a pinned upstream source may legitimately
    be prose-only, and its content arrives later via the host-agent wave. These
    two trees are ours and are always Python, so an empty sub-graph means the
    extraction broke rather than that there was nothing to find — `_run`'s
    check=True says so loudly instead of shipping a graph that silently cannot
    answer the question this function exists to answer.

    Paths are relative to `repo_root` (`_run` passes cwd), matching how
    `_extract_code` addresses `sources/<name>`.
    """
    _run(_self_extract_argv(repo_root), repo_root)
    return [_self_subgraph(repo_root)]


def refresh_self(repo_root: Path) -> int:
    """Re-extract this repo's own code into the AGGREGATE graph, then restamp.

    The freshness half of self-indexing (`kb-watch`). `build()` indexes our code
    once; this keeps it current between builds, incrementally and without an LLM.

    WHY THIS IS NOT A WATCHER, recorded because the obvious reading of the task
    name is wrong. `graphify watch <path>` was the intended mechanism and cannot
    do this job: measured on the PINNED 0.9.31 — which is what `graphify_exe`
    resolves, and NOT what a bare `graphify` reaches (a 0.9.32 also exists on
    this host; reading the wrong one is how the first draft of this comment cited
    the wrong version) — its entire CLI surface is one
    positional path (`_watch(watch_path)` — no `--out`, no merge target, no
    post-rebuild hook, control-armed against `merge-graphs`, which DOES parse
    `--out`), and it rebuilds only `<path>/graphify-out/graph.json`. But `affected`
    reads the AGGREGATE, and `currency.toml` fingerprints the aggregate, so a watch
    on `python/` refreshes neither. Pointing it at the repo root instead would try
    to overwrite the merged 130k-node graph with a root-only extraction; graphify's
    `_check_shrink` refuses that, so it fails loudly rather than destroying the
    corpus, but it is not a design. Ray chose the one-shot refresh over a
    homegrown poll loop (2026-08-01) — this stays native, and `use-tool-builtins`
    is satisfied because the loop we would have written has no tool feature behind
    it.

    Order matters. Our code is re-extracted into its sub-graph FIRST and merged
    after, because merging a sub-graph we have not refreshed would restamp a
    graph that gained nothing — a green stamp over stale content, which is the
    one failure this whole currency mechanism exists to prevent.

    This said "Each tree is re-extracted into its own sub-graph" until 2026-08-02
    and described a per-tree loop the same commit had already replaced with one
    root (#101). Caught by the cold lane — see the "ONE extraction run, over ONE
    root" block in this function's body, which warns about the same class of
    drift and lost a round to it too.
    """
    out = repo_root / "graphify-out" / "graph.json"
    base = out.parent / BASE_GRAPH_NAME
    if not base.is_file():
        raise SystemExit(f"no graphify-out/{BASE_GRAPH_NAME} — run `mise run kb-build` first")

    # FAIL CLOSED if anything else has written graph.json since the snapshot was
    # composed. `kb-merge` and `kb-label` both legitimately do, and restoring the
    # base over their output would discard it in silence — then restamp the
    # result as verified. Refusing costs a rebuild; not refusing costs the merge
    # AND the ability to notice it went missing.
    _assert_base_guard(repo_root, "since the snapshot was written")

    # STAGED, then swapped in one `os.replace`. Writing straight into `out` meant
    # the copy above wiped every self node FIRST and the extract/merge loop then
    # rebuilt them on disk, so any failure part-way — a graphify crash, a Ctrl-C —
    # left graph.json strictly WORSE than before the refresh started, with no
    # rollback and `affected` back to "No unique node match". A refresh that can
    # damage the artifact it refreshes is not a refresh. (Cold lane, 04312f3.)
    staging = out.with_name(out.name + ".refresh")
    shutil.copy(base, staging)

    # ONE extraction run, over ONE root, always `extract --force`, never `update`.
    #
    # Two separate constraints landed on this line, and both are load-bearing:
    #
    # * NEVER `update`. The first draft branched — `update` when a sub-graph
    #   existed, `extract` otherwise — on the reasoning that "the two paths
    #   differ in cost, not in result". Measured, that was false: the same file
    #   came out as `source_file='src/kb_setup/graph.py'` down one path and
    #   `'python/src/kb_setup/graph.py'` down the other, so the aggregate ended
    #   up disagreeing with itself about where our own code lives. A cheaper path
    #   that yields different data is not the same path, and a comment asserting
    #   otherwise is how it survived review.
    # * ONE root, not one per tree (#101). Per-tree runs put `python/` and
    #   `tests/` in namespaces `merge-graphs` cannot bridge, so `affected` could
    #   never answer "which tests cover this symbol" about our own code.
    _run(_self_extract_argv(repo_root), repo_root)
    _run(
        [
            graphify_exe(repo_root),
            "merge-graphs",
            str(staging),
            str(_self_subgraph(repo_root)),
            "--out",
            str(staging),
        ],
        repo_root,
    )

    # RE-CHECK IMMEDIATELY BEFORE THE SWAP. The check at the top of this function
    # is a time-of-check, and the swap below is the time-of-use — separated by a
    # multi-minute extract+merge loop. A `kb-merge` landing inside that window was
    # invisible to the first check, got clobbered by the swap, and then had the
    # guard REARMED over it, certifying the corrupted graph as verified. Exactly
    # the bug the guard was added to prevent, surviving inside the fix for it.
    # (Cold lane round 2, 0f22927 — reproduced live against the shipped function.)
    _assert_base_guard(repo_root, "during the refresh")

    # The swap. Atomic on POSIX, so graph.json is either wholly the old corpus or
    # wholly the new one — never a half-merged intermediate.
    staging.replace(out)

    # graph.json changed, so the prose graph derived FROM it is now stale. Every
    # writer of graph.json re-derives it (`kb-build`/`kb-merge`/`kb-label`); a
    # writer that skips this leaves `kb-query --prose` describing an older corpus.
    prose.derive_for(repo_root)

    # Re-arm the guard for the NEXT refresh, against the graph we just wrote.
    # Skipping this would make the very next `kb-watch` refuse against its own
    # output — a gate that fires on the honest path teaches people to remove it.
    _write_base_guard(repo_root)
    _restamp_self(repo_root)
    print("[kb-watch] refreshed python/ + tests/ into graphify-out/graph.json")
    return 0


def _digest(path: Path) -> str:
    """sha256 of a file, or "" if it cannot be read.

    Content, not `size:mtime_ns`. The stamp uses mtime for OUTPUTS because
    digesting a 382 MB graph on every check is 142x slower (#89) — but this runs
    once per `kb-watch`, not once per session, and it must survive a rewrite that
    happens to land on the same size. "Cheap enough there" and "correct enough
    here" are different questions.
    """
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def _write_base_guard(repo_root: Path) -> None:
    """Record the digest of the graph.json the base snapshot composes with."""
    out = repo_root / "graphify-out" / "graph.json"
    digest = _digest(out)
    if not digest:
        return
    try:
        (out.parent / BASE_GUARD_NAME).write_text(digest, encoding="utf-8")
    except OSError as e:
        # Loud, not silent: an unwritten guard makes the NEXT refresh proceed
        # unchecked, so the operator must know the protection is off.
        print(
            f"[kb-watch] WARNING: could not write {BASE_GUARD_NAME}: {e} — "
            f"the next refresh will not be able to detect a competing writer."
        )


def _read_base_guard(repo_root: Path) -> str | None:
    """The recorded digest; None when the guard file does not exist.

    ABSENT and UNREADABLE are different answers and must not collapse, which is
    the distinction the first version got wrong: a bare `except OSError: return
    ""` made a 0-byte guard (an interrupted write — realistic, this repo has a
    whole rule about killing wedged processes) and a guard that is a directory
    both read as "no guard", silently disabling a check whose own comment says
    FAIL CLOSED. Reproduced by the cold lane: 0-byte guard -> silent revert,
    exit 0, no error at all.

    So: None means the file is not there — a graph built before this guard
    existed, which proceeds, because refusing those would break every existing
    clone to catch a case that cannot have happened there. Anything else that
    goes wrong RAISES, and the caller refuses. Unknown is not permission.
    """
    path = repo_root / "graphify-out" / BASE_GUARD_NAME
    if not path.exists():
        return None
    digest = path.read_text(encoding="utf-8").strip()
    if not digest:
        raise SystemExit(
            f"graphify-out/{BASE_GUARD_NAME} exists but is EMPTY — most likely an "
            f"interrupted write. Refusing rather than treating it as absent, because "
            f"an unverifiable guard cannot certify that nothing else wrote graph.json.\n"
            f"  Run `mise run kb-build` to rebuild the snapshot and the guard together."
        )
    return digest


def _assert_base_guard(repo_root: Path, when: str) -> None:
    """Refuse unless graph.json still matches the digest the snapshot composes with.

    Called TWICE — once before the copy and once immediately before the atomic
    swap. Both are needed: the pair brackets the extract+merge loop, which is
    where a concurrent `kb-merge` would otherwise slip in unseen.
    """
    expected = _read_base_guard(repo_root)
    if expected is None:
        return
    out = repo_root / "graphify-out" / "graph.json"
    actual = _digest(out) if out.is_file() else ""
    if actual and expected != actual:
        raise SystemExit(
            f"graphify-out/graph.json changed {when} "
            f"(expected sha256 {expected[:12]}, found {actual[:12]}).\n"
            f"  `kb-merge` and `kb-label` both write graph.json and neither refreshes "
            f"the snapshot, so continuing would silently discard their work.\n"
            f"  Run `mise run kb-build` to rebuild the snapshot and the graph together."
        )


def _restamp_self(repo_root: Path) -> None:
    """Refresh the stamp's artifact fingerprints after a self-refresh.

    `restamp_artifacts` and not `write_stamp`: the graph changed but the BUILDER
    did not, so version and source_ref are carried forward rather than re-observed.
    Re-observing would be worse than redundant — it would let a graphify upgrade
    mid-session silently relabel a graph the previous version actually built.

    Without this the refresh is actively harmful: `artifact_fingerprints` is
    `size:mtime_ns`, so any rewrite of graph.json moves it, and every later
    `kb-currency-check` reports the graph as not verifiably built by the pin —
    a permanent red that means nothing, which is how a real signal gets ignored.
    Best-effort, like every other stamp path here: a refresh must not fail over
    its own bookkeeping.
    """
    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return
        path = sync.restamp_artifacts(repo_root, spec)
        if path is None:
            print(
                "[kb-watch] WARNING: no build stamp to refresh — run `mise run kb-build`; "
                "currency step 1 will report this graph as never stamped."
            )
            return
        print(f"[kb-watch] restamped {path.name}")
    except (OSError, ValueError, ImportError) as e:
        print(f"[kb-watch] WARNING: could not restamp: {e}")


def _build_study_graph(repo_root: Path, sources: Path, out_dir: Path, study: list[str]) -> None:
    """Merge every `scope = study` source into its own graph, never the aggregate.

    Extracted from `build()` rather than inlined — ruff flagged `build` at
    complexity 12, and the honest fix for "this function grew a fourth job" is a
    fourth function, not a suppression.

    These repos are fully ingested; only their DESTINATION differs. That
    distinction is the whole design: the standing instruction was "ingest all
    three, no exclusions", and merging them into the corpus took graph.json 7.6
    MiB past graphify's 512 MiB cap. Nothing that analyses them needs their nodes
    ranked beside the corpus.
    """
    if not study:
        return
    study_out = out_dir / STUDY_GRAPH_NAME
    seed, *rest = study
    shutil.copy(sources / seed / "graphify-out" / "graph.json", study_out)
    print(f"[kb-build] seeded {STUDY_GRAPH_NAME} from {seed} ({len(study)} study source(s))")
    for name in rest:
        sub = sources / name / "graphify-out" / "graph.json"
        _run(
            [
                graphify_exe(repo_root),
                "merge-graphs",
                str(study_out),
                str(sub),
                "--out",
                str(study_out),
            ],
            repo_root,
        )


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

    # Partition by SCOPE before anything is seeded. Doing it here rather than in
    # the merge loop below is the whole correctness argument: the seed is chosen
    # first, so a partition applied only to merging would still let a study repo
    # seed the aggregate whenever it sorted ahead of the corpus sources — and the
    # corpus would then simply BE that repo, silently and totally.
    study_names = {m.name for m in manifests if m.scope == "study"}
    corpus = [n for n in with_code if n not in study_names]
    study = [n for n in with_code if n in study_names]
    if not corpus:
        raise SystemExit("no CORPUS source produced code nodes (only scope=study ones did)")

    # Seed graph.json from the first code-bearing CORPUS source; merge the rest.
    seed, *rest = corpus
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(sources / seed / "graphify-out" / "graph.json", out)
    print(f"[kb-build] seeded graph.json from {seed}")
    for name in rest:
        sub = sources / name / "graphify-out" / "graph.json"
        _run(
            [graphify_exe(repo_root), "merge-graphs", str(out), str(sub), "--out", str(out)],
            repo_root,
        )

    _build_study_graph(repo_root, sources, out.parent, study)

    # Doc layer: replay the committed host-agent extractions (free — no subagents).
    gpy = graphify_python(repo_root)
    chunks = sorted((sources / "extractions").glob("*.json"))
    print(f"[kb-build] merging {len(chunks)} committed doc extraction(s)")
    for chunk in chunks:
        name = chunk.stem.removesuffix("-docs")
        root = str((sources / name).resolve())
        _run([gpy, str(_MERGE_SCRIPT), str(chunk), root, str(out)], repo_root)

    # THE BASE SNAPSHOT — taken here, after every external contribution and before
    # a single node of ours. Order is the entire correctness argument: a snapshot
    # taken one step later would be a perfectly valid file that reintroduces the
    # duplication it exists to prevent, and nothing downstream would notice.
    base = out.parent / BASE_GRAPH_NAME
    shutil.copy(out, base)
    print(f"[kb-build] snapshotted {BASE_GRAPH_NAME} — the corpus without our own code")

    # Our own library and test tree, merged LAST. They are also the only part
    # `kb-watch` re-merges, so keeping them at the end is what lets that task
    # reproduce this exact state from the snapshot above rather than append to it.
    for sub in _extract_self(repo_root):
        _run(
            [graphify_exe(repo_root), "merge-graphs", str(out), str(sub), "--out", str(out)],
            repo_root,
        )

    # The prose-only derived graph, from the graph we just built. Here and not in
    # a separate task-you-must-remember: it is a pure function of graph.json, so
    # any build that does not refresh it leaves a scoped corpus describing an
    # older one — and a retrieval figure measured against a stale corpus is the
    # inherited-number trap with extra steps. `kb-prose` re-derives it alone.
    prose.derive_for(repo_root)

    # Arm the base guard against the graph we just produced, so a later
    # `kb-watch` can tell whether anything else has written it since.
    _write_base_guard(repo_root)
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
