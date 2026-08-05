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
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from kb_setup import graph_checks, graphify_ops
from kb_setup import manifest as mf
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
#:
#: CONFIRMED GENERALLY 2026-08-03: the rebuilt aggregate has **0 cross-namespace
#: edges of 815,481** across 40 namespaces (control-armed — injecting one crossing
#: moves the count to 1). So "no edge can span two namespaces" is not a quirk of
#: our two trees; it is what `merge-graphs` does to every input, and one extraction
#: root is the only way any cross-tree edge can exist.
_SELF_ROOT = "."

#: Where the single self sub-graph is written, and the reason this constant
#: exists at all. `graphify extract <path>` defaults its output to
#: `<path>/graphify-out/`, so extracting the repo root would write the AGGREGATE
#: `graphify-out/graph.json` — overwriting a 133k-node merged corpus with a
#: root-only extraction. `--out` redirects it. Gitignored, derived, disposable.
_SELF_OUT = ".self-graph"

#: Where `scope = study` sources land — repos we are analysing rather than
#: learning from. They are still fully ingested — no exclusions — just not ranked
#: beside the corpus.
#:
#: ⚠️ THE ORIGINAL RATIONALE WAS PARTLY A BUG, corrected 2026-08-03 (#120). This
#: said the partition existed because merging study sources took graph.json 7.6 MiB
#: past the 512 MiB cap — "71.0 MB of sub-graphs became >=155 MiB of aggregate
#: growth, since `merge-graphs` re-namespaces ids and expands edges on every merge".
#: The re-namespacing was real; the >=2x expansion was not inherent to it. It came
#: from `build()` merging PAIRWISE and re-prefixing its own accumulator once per
#: source. After the N-ary fix, duplicate-prefix waste measures 0.00% and id depth
#: is 1-2 rather than 1-22.
#:
#: The partition SURVIVES the correction on its own merits — nothing analysing a
#: study repo needs its nodes ranked beside the corpus, and Ray's instruction was
#: "ingest all three, no exclusions", which routing satisfies and dropping would
#: not. But do not carry the byte figure forward as an argument: it was inflated,
#: and a reader reaching for it to justify the next partition would be reasoning
#: from a defect. See `_merge_sources_into`.
STUDY_GRAPH_NAME = "study-graph.json"


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


def refresh_self(_repo_root: Path) -> NoReturn:
    """Refuse — `kb-watch` has no recomposition story under the single-merge build.

    THIS IS A STUB, and the reason is worth recording precisely rather than
    leaving a bare refusal. The incremental refresh this replaces restarted
    `graph.json` from `.base-graph.json` — a snapshot of the corpus taken
    BEFORE our own code was merged in — then re-extracted and re-merged just
    the self sub-graph back in. That mechanism existed only because `build()`
    used to compose the corpus and merge our code in as a SEPARATE, later step,
    which meant "everything except our code" was a real, snapshottable state.

    #175 removed that separable step: the self sub-graph is now one ordinary
    input to the SAME single N-ary `merge-graphs` call the corpus sources go
    through (see `build()` and `_merge_sources_into`), so there is no longer a
    "before our code" state to snapshot or restart from. Reintroducing a
    snapshot now would mean composing corpus-only and corpus+self as two
    separate merges again — exactly the shape #175 removed, and exactly the
    shape that re-prefixes an already-merged graph's ids (#120) the moment a
    refresh actually needs to run.

    A real incremental refresh under the one-merge shape needs its own design
    — recomposing from the pinned corpus sub-graphs plus a freshly re-extracted
    self sub-graph, without ever feeding `graph.json` itself back into a merge
    — and that design is the next task on this branch, not a resurrection of
    the base-guard machinery this replaces. That machinery had already needed
    two rounds of cold-review fixes (a competing-writer race, then a
    re-check-before-swap race) to be safe for a shape that no longer exists.
    Refusing loudly here is cheaper than migrating it forward unexamined.
    """
    raise SystemExit(
        "kb-watch recomposition not yet implemented after the single-merge "
        "restructure — run `mise run kb-build`"
    )


def _merge_sources_into(repo_root: Path, out: Path, inputs: list[Path]) -> None:
    """Compose `inputs` into `out` with ONE `merge-graphs` call — never pairwise.

    THE FIX FOR #120, and the reason it is a shared helper rather than two edits.

    graphify's `merge-graphs` takes N graph paths (`cli.py` parses every
    non-`--out` argument into `graph_paths`) and prefixes each input's node ids
    with a distinct `<repo_tag>::` so same-stem nodes from different repos cannot
    collide (#1729). `prefix_graph_for_global` (`build.py:1449`) applies that
    prefix UNCONDITIONALLY — `relabel = {n: f"{repo_tag}::{n}" ...}` with no
    already-prefixed guard.

    So feeding the accumulator back in as an input, once per source, re-prefixes
    everything already merged. Measured on the 2026-08-03 aggregate: of 218,243
    node ids only 9,645 (4.4%) carried a single `::`; 90,795 carried ten and
    11,932 carried twenty-two. Across every id-bearing field (`id`, `source`,
    `target`, `_src`, `_tgt`) that is 296,904,672 bytes where 112,626,720 would
    do — **184 MB, 33% of the whole file**, which is what pushed graph.json past
    graphify's 512 MiB read cap and made the entire aggregate unqueryable.

    Calling the N-ary form once gives every input exactly one prefix, which is
    the invariant `tests/test_merge_prefixes_once.py` asserts. It is also
    `use-tool-builtins.md` in the literal: the loop was ours, the N-ary merge is
    graphify's, and the loop was the defect.

    Two related workarounds in this file were written believing the blowup was
    inherent to merging rather than a bug in how we called it — the
    `STUDY_GRAPH_NAME` partition ("71.0 MB of sub-graphs became >=155 MiB of
    aggregate growth") and the #101 disjoint-namespace note. Neither is retired
    here: study partitioning still has an independent ranking rationale, and #101
    was fixed by extracting one root. But a future reader weighing either should
    know the cost figure behind them was inflated by this.

    A single input is COPIED, not merged: `merge-graphs` requires two paths and
    exits 1 on one. That leaves a lone source unprefixed while N>=2 sources each
    carry one — an asymmetry inherited from the code this replaces, harmless
    because it is reachable only with exactly one code-bearing corpus source.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    if len(inputs) == 1:
        shutil.copy(inputs[0], out)
        return
    _run(
        [graphify_exe(repo_root), "merge-graphs", *[str(p) for p in inputs], "--out", str(out)],
        repo_root,
    )


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
    print(f"[kb-build] composing {STUDY_GRAPH_NAME} from {len(study)} study source(s)")
    _merge_sources_into(
        repo_root, study_out, [sources / n / "graphify-out" / "graph.json" for n in study]
    )


def _cluster_study_graph(repo_root: Path, study_out: Path) -> None:
    """Deterministically re-cluster `study_out` THROUGH the graphify binary.

    A no-op when there is nothing to cluster (no study sources this build, or a
    study source that produced no graph) — matching `_build_study_graph`'s own
    early return rather than raising over an absent optional artifact.

    VERIFIED MECHANISM (installed graphify 0.9.33 `cli.py`, the
    `cmd in ("cluster-only", "label")` branch — never run graphify by hand here;
    read the installed source instead). `--graph <path>` controls only where the
    run LOADS from (`graph_json = graph_override if ... else watch_path /
    _GRAPHIFY_OUT / "graph.json"`, cli.py:1640). The WRITE target is computed
    separately and does NOT follow it: `out = graph_json.parent` only when that
    parent directory is literally named `graphify-out` (cli.py:1711-1716), and
    either way the final write is `to_json(G, communities, str(out /
    "graph.json"), ...)` (cli.py:1862) — the LITERAL string `"graph.json"`,
    never `graph_json.name`. So `--graph graphify-out/study-graph.json` would
    LOAD the study graph but WRITE its clustered result to
    `graphify-out/graph.json` — the aggregate — because that path's parent
    directory happens to also be named `graphify-out`. No flag changes this.

    The only safe invocation is therefore to give the run its OWN isolated
    `<tmp>/graphify-out/graph.json` to read and write: with no `--graph`
    override, `graph_json` resolves to exactly that path by default, so both
    the load and the write stay inside the throwaway directory and the real
    aggregate is never touched. `--no-label` keeps this deterministic —
    placeholder `"Community {cid}"` names, no hub-labeler, no LLM call
    (cli.py:1797-1799) — and `--no-viz` skips the `graph.html` render, which
    this graph is never served from.
    """
    if not study_out.is_file():
        return
    with tempfile.TemporaryDirectory(prefix="kb-study-cluster-") as tmp:
        work = Path(tmp)
        staged = work / "graphify-out" / "graph.json"
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(study_out, staged)
        _run([graphify_exe(repo_root), "cluster-only", ".", "--no-label", "--no-viz"], work)
        shutil.copy(staged, study_out)


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

    # VALIDATE EVERY COMMITTED CHUNK **FIRST** — before the stamp is cleared,
    # before a single clone, and above all before anything writes graph.json.
    #
    # This sat after the corpus merge until the cold lane's round 2. It refused,
    # correctly, but only AFTER `_merge_sources_into` had already replaced the
    # aggregate with a code-only composition — so a bad chunk cost the working
    # graph and left a partial one that `kb-query` will happily serve, since it
    # checks only that the file exists. A refusal that is not atomic with respect
    # to the artifact it protects is a refusal that has already done the damage.
    # Cheap enough to be free here: 18 files, a few milliseconds, no network.
    from kb_setup import chunks as _chunks

    chunk_paths = sorted((sources / "extractions").glob("*.json"))
    problems = {p: i for p, i in _chunks.validate_files(chunk_paths).items() if i}
    if problems:
        lines = [f"  {p.name}: {i}" for p, issues in problems.items() for i in issues[:5]]
        raise SystemExit(
            f"{len(problems)} extraction chunk(s) failed validation — refusing to build:\n"
            + "\n".join(lines)
            + "\nRun `mise run kb-validate-chunks -- sources/extractions/*.json` for the full list."
        )

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

    # Compose graph.json from every code-bearing CORPUS source AND our own code
    # in ONE merge. Self joins this call rather than a second one as of #175 —
    # see `_merge_sources_into` for why pairwise/sequential merging duplicates
    # prefixes (#120), and `refresh_self` for why that removes its old
    # incremental-restart path. Every source (and self) now carries its own
    # tag, exactly once.
    self_subgraphs = _extract_self(repo_root)
    print(f"[kb-build] composing graph.json from {len(corpus)} corpus source(s) + our own code")
    _merge_sources_into(
        repo_root,
        out,
        [sources / n / "graphify-out" / "graph.json" for n in corpus] + self_subgraphs,
    )

    _build_study_graph(repo_root, sources, out.parent, study)
    _cluster_study_graph(repo_root, out.parent / STUDY_GRAPH_NAME)

    # Doc layer: replay the committed host-agent extractions (free — no subagents).
    # MERGE-ONLY (#169): `_merge_docs.py` no longer clusters, scores, or reports
    # per chunk — 17 of 18 such passes were discarded and never read. It loads
    # graph.json, merges the chunk, reconstructs communities from what the graph
    # already carries, and writes. The real clustering/labelling happens ONCE,
    # below, after every chunk has landed — not once per chunk.
    gpy = graphify_python(repo_root)
    # Already validated at the TOP of build(), before anything wrote graph.json.
    print(f"[kb-build] merging {len(chunk_paths)} validated doc extraction(s)")
    for chunk in chunk_paths:
        name = chunk.stem.removesuffix("-docs")
        root = str((sources / name).resolve())
        _run([gpy, str(_MERGE_SCRIPT), str(chunk), root, str(out)], repo_root)

    # ONE final label pass — deterministic (no LLM; see `graphify_ops.label`'s own
    # docstring) — re-clusters the fully-composed graph, carries hyperedges across
    # graphify's own label/cluster-only round-trip (#171 — measured 5->0 without
    # this), and re-derives the prose graph as its own last step. `build()` no
    # longer calls `prose.derive_for` itself: this IS that call now, made by the
    # function that already has to load graph.json for the label pass, rather
    # than a second, separate load of the same file.
    label_rc = graphify_ops.label(repo_root)
    if label_rc != 0:
        raise SystemExit(f"[kb-build] final label pass failed (rc={label_rc}) — aborting")

    # The composition invariants #120 and #171/#175 depend on: every id carries
    # at most one merge prefix, every carried hyperedge still resolves. Checked
    # HERE, on the artifact this build just produced, so a regression is caught
    # on the next build rather than only on the next `mise run test`.
    graph_checks.assert_composition(out)

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
