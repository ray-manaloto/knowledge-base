"""Build / update the knowledge graph from committed inputs.

Reproducibility model: the graph is rebuildable from two committed things —
`sources/*.manifest` (external repo pins) and `sources/extractions/*.json` (the
non-free host-agent doc extractions). The external repos themselves are cloned on
demand and gitignored — and so is everything under `graphify-out/` except the
authored `memory/`: `graph.json` is DERIVED, far past git's limits at aggregate
scale, and consumers reach it via `kb-serve` (MCP) or a pushed graph DB, never a
git blob. (This paragraph claimed graph.json + manifest.json were committed
until 2026-08-05 — stale since the aggregate outgrew git, flagged by a lane
mid-#175.) `build()` composes everything in ONE N-ary merge and ends in the
final labelled state; `refresh_self` (kb-watch) recomposes from the recorded
inputs rather than patching the artifact in place.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import atomic, graph_checks, graphify_ops
from kb_setup import manifest as mf
from kb_setup.graphify_env import clean_env, graphify_exe, graphify_python

if TYPE_CHECKING:
    from kb_setup.currency.config import ToolSpec

_MERGE_SCRIPT = Path(__file__).with_name("_merge_docs.py")

# The tool whose artifacts `kb-build` produces. Named explicitly so a
# multi-tool currency.toml cannot silently stamp the wrong tool.
_STAMPED_TOOL = "graphify"

#: Permission bits restored on the swapped-in graph.json — see
#: `_recompose_into_temp`'s docstring. Same value and same reason as
#: `hyperedges._GRAPH_MODE`; a separate constant because these are separate
#: modules and the integer is not worth a shared import.
_GRAPH_MODE = 0o644


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


#: Filename of the DERIVED record `build()` writes describing what it actually
#: composed — never hand-authored, never committed (`graphify-out/` is
#: gitignored beyond `memory/`). `refresh_self` reads it back so a
#: recomposition uses the SAME corpus leaves and self location the last full
#: build did, rather than re-deriving them from `sources/*.manifest` (which may
#: have grown or shrunk since — `refresh_self` deliberately never reads a
#: manifest at all; that is the point, not an oversight).
_COMPOSE_MANIFEST_NAME = ".compose-manifest.json"

#: Filename of the ledger every successful `kb-merge` appends to between
#: builds (`append_merged_chunk`). `build()` resets it to `[]` at the moment it
#: writes the compose manifest — a fresh build subsumes every merge recorded
#: since the previous one.
_MERGED_CHUNKS_NAME = ".merged-chunks.json"


def _compose_manifest_path(repo_root: Path) -> Path:
    """Where `build()` records what it composed."""
    return repo_root / "graphify-out" / _COMPOSE_MANIFEST_NAME


def _merged_chunks_path(repo_root: Path) -> Path:
    """Where every between-build `kb-merge` is recorded for later replay."""
    return repo_root / "graphify-out" / _MERGED_CHUNKS_NAME


@dataclass(frozen=True)
class ComposeManifest:
    """What ONE `build()` actually composed, read back by `refresh_self`.

    Every path is repo-root-relative (:func:`_resolve` turns it back into a
    real `Path`), except a `chunks` entry for a chunk merged from outside the
    repo tree, which is its own absolute string — see
    :func:`_relativize_or_str`, which is what produces one. `self_graph` is
    recorded for provenance — it IS what "this build actually composed" means,
    literally — even though `refresh_self` never reads it back to find the
    self sub-graph: that location is a fixed constant (:func:`_self_subgraph`),
    not something a recomposition needs to recover from a record.

    `chunk_roots` is the root OVERRIDE map for `chunks` entries whose replay
    root cannot be safely re-derived from the naming convention
    `_replay_targets` otherwise falls back to — see `_write_compose_manifest`.
    """

    corpus: tuple[str, ...]
    self_graph: str
    chunks: tuple[str, ...]
    chunk_roots: dict[str, str]


def _write_compose_manifest(
    repo_root: Path, manifest: ComposeManifest, *, tag: str = "kb-build"
) -> None:
    """Record what `build()` (or a successful `refresh_self`) just composed.

    Takes the whole `ComposeManifest` rather than its four fields as separate
    keywords — `build()` constructs one fresh each time, `refresh_self` builds
    one via `dataclasses.replace` on the manifest it just read back, and
    either way the shape written here is exactly the shape `ComposeManifest`
    already declares, so restating its fields as a parallel parameter list
    was pure duplication (and had grown past ruff's arg-count budget).

    `manifest.chunk_roots` maps a SUBSET of `manifest.chunks` to the root it
    must replay under. Only entries whose root is not safely re-derivable
    from the `<name>-docs.json` -> `sources/<name>` naming convention need
    one — every chunk `build()` itself discovers via the
    `sources/extractions/*.json` glob follows that convention by
    construction, so `build()` always passes `{}`. A chunk promoted here from
    the between-build merge ledger may not: it was merged with whatever root
    `kb-merge` actually used, recorded on the ledger entry itself
    (:class:`MergedChunkEntry`), which can differ from the convention's guess
    (#175 cold review, finding 4b). See :func:`_replay_targets` for how the
    two are reconciled.

    `tag` names the CALLER in every printed line — `build()`'s default is
    right for a full build, and `refresh_self` passes `"kb-watch"` so a
    `kb-watch` run's own bookkeeping does not print as if `kb-build` had run
    (#175 cold review, finding 9).

    Best-effort, like the build stamp it sits beside: a failure here must not
    fail a build that just produced a correct `graph.json`. The one thing that
    goes wrong if this write fails is that `kb-watch` later refuses and says
    so (:func:`_load_compose_manifest_or_refuse`) — the safe direction to fail
    in, not a build dying over its own bookkeeping.
    """
    try:
        path = _compose_manifest_path(repo_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "corpus": list(manifest.corpus),
            "self": manifest.self_graph,
            "chunks": list(manifest.chunks),
            "chunk_roots": manifest.chunk_roots,
        }
        atomic.write_text(path, json.dumps(payload, indent=2) + "\n")
    except OSError as e:
        print(
            f"[{tag}] WARNING: could not record the compose manifest: {e}\n"
            f"[{tag}] `mise run kb-watch` will refuse until the next successful "
            f"`mise run kb-build`."
        )


def _valid_compose_fields(
    data: dict[str, object],
) -> tuple[list[str], str, list[str], dict[str, str]] | None:
    """Extract + validate every compose-manifest field, or None if any is malformed.

    Split out of `_read_compose_manifest` purely to keep THAT function's own
    return-statement count under ruff's complexity budget — adding the
    `chunk_roots` check (#175 cold review, finding 4) pushed it over. The
    validation itself is unchanged: every field is checked rather than
    trusted, this is untrusted JSON any editor could have touched, the same
    discipline `kb_setup.gates._parse` applies to its own on-disk record. An
    over-promising type here is how a caller stops checking it. `chunk_roots`
    is validated as strictly as every other field: a manifest written before
    #175's cold-review fixes has no such key at all, and that reads as
    "unreadable", not "no overrides" — the same unknown-is-not-permission
    rule the rest of this module follows, and it costs nothing since the file
    is derived and `mise run kb-build` regenerates it.
    """
    corpus, self_graph, chunks, chunk_roots = (
        data.get("corpus"),
        data.get("self"),
        data.get("chunks"),
        data.get("chunk_roots"),
    )
    if not isinstance(corpus, list) or not all(isinstance(c, str) and c for c in corpus):
        return None
    if not isinstance(self_graph, str) or not self_graph:
        return None
    if not isinstance(chunks, list) or not all(isinstance(c, str) and c for c in chunks):
        return None
    if not isinstance(chunk_roots, dict) or not all(
        isinstance(k, str) and k and isinstance(v, str) and v for k, v in chunk_roots.items()
    ):
        return None
    # Rebuilt explicitly rather than returned as narrowed: `isinstance(x, list)`
    # proves "x is A list", never "a list of str" — `ty` cannot follow the
    # `all(isinstance(...))` checks above into an element-type narrowing, so
    # the checked-but-untyped `corpus`/`chunks`/`chunk_roots` would not satisfy
    # this function's own declared return type. Same idiom as
    # `sync.stamped_input_fingerprints`'s `{str(k): str(v) ...}`.
    return (
        [str(c) for c in corpus],
        str(self_graph),
        [str(c) for c in chunks],
        {str(k): str(v) for k, v in chunk_roots.items()},
    )


def _read_compose_manifest(repo_root: Path) -> ComposeManifest | None:
    """The compose manifest, or `None` if it is absent, unreadable, or not one.

    See :func:`_valid_compose_fields` for the field-level validation rules.
    """
    try:
        data = json.loads(_compose_manifest_path(repo_root).read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    fields = _valid_compose_fields(data)
    if fields is None:
        return None
    corpus, self_graph, chunks, chunk_roots = fields
    return ComposeManifest(
        corpus=tuple(corpus),
        self_graph=self_graph,
        chunks=tuple(chunks),
        chunk_roots=dict(chunk_roots),
    )


@dataclass(frozen=True)
class MergedChunkEntry:
    """One between-build `kb-merge`, as recorded in the recomposition ledger.

    `root` is the source root `kb-merge` actually used for path
    relativization (`graphify_ops.merge_chunk`'s `src_root` — a caller's
    `--root`, or its own default of the chunk's parent directory). Recorded so
    a later `kb-watch` replays this chunk under the SAME root it was really
    merged with, rather than re-deriving one from the `<name>-docs.json` ->
    `sources/<name>` naming convention that a chunk merged with a custom (or
    even the ordinary default) root need not follow (#175 cold review,
    finding 4b).
    """

    chunk: str
    sha256: str
    root: str


def _write_merged_chunks(repo_root: Path, entries: list[MergedChunkEntry]) -> None:
    path = _merged_chunks_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [{"chunk": e.chunk, "sha256": e.sha256, "root": e.root} for e in entries]
    atomic.write_text(path, json.dumps(payload, indent=2) + "\n")


def _reset_merged_chunks(repo_root: Path, *, tag: str = "kb-build") -> None:
    """Empty the ledger. Best-effort, for the same reason the compose manifest is.

    `tag` names the caller — see `_clear_stamp`'s docstring for why (#175 cold
    review, finding 9).
    """
    try:
        _write_merged_chunks(repo_root, [])
    except OSError as e:
        print(f"[{tag}] WARNING: could not reset the merge ledger: {e}")


def _read_merged_chunks(repo_root: Path) -> list[MergedChunkEntry] | None:
    """The ledger's entries — `[]` if absent, `None` if present but unreadable.

    The distinction is the whole point of the ledger existing. An ABSENT file
    means no `kb-merge` has landed since the last build — the ordinary case,
    indistinguishable from "nothing to replay". A PRESENT-but-corrupt one means
    a recomposition cannot tell whether it would be dropping an entry it can no
    longer read, and must refuse rather than guess "empty" — the same
    unknown-is-not-permission rule the compose manifest follows. A ledger
    entry missing `root` (written before #175's cold-review fixes) is
    unreadable by the same rule: guessing a root would silently reintroduce
    the exact divergence recording it exists to prevent, and the file is
    derived — `mise run kb-build` regenerates it from nothing.
    """
    path = _merged_chunks_path(repo_root)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    entries: list[MergedChunkEntry] = []
    for row in data:
        if not isinstance(row, dict):
            return None
        chunk, sha, root = row.get("chunk"), row.get("sha256"), row.get("root")
        if (
            not isinstance(chunk, str)
            or not chunk
            or not isinstance(sha, str)
            or not sha
            or not isinstance(root, str)
            or not root
        ):
            return None
        entries.append(MergedChunkEntry(chunk=chunk, sha256=sha, root=root))
    return entries


def _sha256_file(path: Path) -> str:
    """Hex sha256 of `path`'s bytes, read in blocks rather than loaded whole."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def append_merged_chunk(repo_root: Path, chunk: str, root: str) -> None:
    """Record one successful between-build `kb-merge` in the recomposition ledger.

    Called by `graphify_ops.merge_chunk` on its fully-successful path only —
    after the merge subprocess AND the prose re-derivation both succeeded — so
    every ledger entry corresponds to content that is really on `graph.json`
    right now. `root` is `merge_chunk`'s own `src_root` — the root the merge
    ACTUALLY ran under — recorded so a later replay uses it verbatim instead
    of re-deriving one (#175 cold review, finding 4b).

    `chunk` is stored CANONICALIZED — resolved, then made repo-root-relative
    when it sits under `repo_root`, else its own absolute string
    (:func:`_relativize_or_str`, the SAME helper `refresh_self`'s
    ledger-promotion loop already uses) — never the raw string the caller
    passed. Before this, the raw string was stored VERBATIM and read two
    different ways by two different readers: this function digested it
    relative to the process's CURRENT WORKING DIRECTORY (`Path(chunk)`, opened
    as given), while `_verified_ledger_chunks` later resolved the recorded
    string relative to `repo_root` (:func:`_resolve`). The two agreed only
    because mise always runs tasks from the config root — a caller invoked
    from anywhere else recorded a ledger entry that could never verify again
    (#175 cold review round 2, the round-1 finding 8 secondary item).
    Resolving once, HERE, and storing the canonical form makes every later
    reader agree regardless of the cwd at append time or at verify time.

    Raises rather than swallowing a write failure: a caller that reported
    success while silently failing to extend the ledger would leave a future
    `kb-watch` unable to tell this merge ever happened — the exact silent
    discard the ledger exists to prevent, just arriving through its own
    recording step instead of through recomposition. `merge_chunk` turns a
    raise here into its own `rc=1`, the same shape `_derive_prose` already uses
    when a real change could not be fully accounted for.

    Also raises if the EXISTING ledger cannot be read: appending blindly to an
    unreadable file would either duplicate or silently drop whatever is
    already there, and neither is an improvement on refusing.
    """
    existing = _read_merged_chunks(repo_root)
    if existing is None:
        raise ValueError(
            f"{_merged_chunks_path(repo_root)} exists but is not a readable merge "
            f"ledger — refusing to append blindly"
        )
    resolved = Path(chunk).resolve()
    digest = _sha256_file(resolved)
    stored = _relativize_or_str(resolved, repo_root)
    _write_merged_chunks(
        repo_root, [*existing, MergedChunkEntry(chunk=stored, sha256=digest, root=root)]
    )


def _resolve(repo_root: Path, rel_or_abs: str) -> Path:
    """A compose-manifest/ledger path string -> a real `Path`.

    Every string either record carries is either ABSOLUTE or relative to
    `repo_root` — never to the process cwd, matching how the rest of this
    module addresses `sources/` (always `repo_root / ...`, never a bare
    relative literal). `mise run kb-watch` therefore recomposes the same way
    regardless of where it happens to be invoked from.
    """
    p = Path(rel_or_abs)
    return p if p.is_absolute() else repo_root / p


def _relativize_or_str(path: Path, repo_root: Path) -> str:
    """`path` relative to `repo_root` when possible, else its own absolute string.

    `Path.relative_to` raises `ValueError` for a path outside `repo_root` — and
    an out-of-tree ledger chunk is a real, supported case: `_resolve` already
    special-cases an absolute string, and `cli.py` passes a `kb-merge` caller's
    argv through verbatim, so `mise run kb-merge -- /elsewhere/chunk.json`
    genuinely reaches the ledger. Letting that raise here would crash
    `refresh_self` AFTER `graph.json` has already been swapped in — the
    recomposition would land with no stamp written and the ledger not reset
    (#175 cold review, finding 8). Falling back to the absolute string keeps
    the round-trip lossless either way: `_resolve` reads an absolute string
    back unchanged, exactly as it does a repo-relative one.

    Two call sites must agree on this canonical form, and both go through this
    one helper rather than reimplementing it: `refresh_self`'s ledger-promotion
    loop (naming a chunk already promoted into `manifest.chunks`) and
    `append_merged_chunk` (naming what a `kb-merge` just recorded) — see the
    latter's docstring for the append/verify cwd mismatch that unifying on
    this helper closes (#175 cold review round 2).
    """
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _load_compose_manifest_or_refuse(repo_root: Path) -> ComposeManifest:
    """The last build's recorded composition, or a refusal naming the fix.

    A missing file, a malformed one, and one from before this mechanism
    existed are all treated identically: unknown is not permission, and there
    is nothing safe to recompose FROM until a `kb-build` has written one.
    """
    manifest = _read_compose_manifest(repo_root)
    if manifest is None:
        raise SystemExit(
            f"no usable {_compose_manifest_path(repo_root)} — `kb-watch` recomposes "
            f"from what the last full build actually composed, and there is no "
            f"readable record of one. Run `mise run kb-build` first."
        )
    return manifest


def _verified_ledger_chunks(repo_root: Path) -> list[tuple[Path, str]]:
    """Ledger entries COLLAPSED to one per resolved path, then VERIFIED `(path, root)` pairs.

    Collapsed FIRST, by resolved path, keeping the LAST row for each — append
    order is merge order, so the last row for a path is what `graph.json`
    actually reflects right now. The ordinary re-ingestion flow supersedes a
    row this way with no misuse at all: `kb-assemble` overwrites a chunk under
    `sources/extractions/` in place, then `kb-merge` merges it again, and the
    ledger simply gets a second row for the same path. Verifying EVERY row
    instead of only the surviving one produced two defects (#175 cold review
    round 2, NEW-2 and NEW-3):

    * an EARLIER row's sha256 — computed against content the file no longer
      holds — refused `kb-watch` forever, for a flow that did nothing wrong
      (NEW-3); and
    * a chunk merged N times with UNCHANGED content (every row's sha256 still
      matches) was verified, promoted, and replayed N times — and because the
      promoted duplicates land in the persisted `manifest.chunks` tuple, the
      waste PERSISTED on every subsequent `kb-watch` until the next full
      `kb-build` (NEW-2).

    `dict.pop` then re-insert (not a plain `d[k] = v` overwrite) so the
    surviving row also takes the POSITION of its LATEST occurrence — a plain
    reassignment updates the value but leaves an existing key at its ORIGINAL
    position, which would replay a since-superseded path too early relative to
    whatever else was appended between its two occurrences.

    Refuses the moment the SURVIVING entry for a path cannot be trusted —
    missing file, unreadable file, or a sha256 that no longer matches what was
    recorded at merge time — because recomposing over that would silently drop
    that merge's content, which is the one property this mechanism exists to
    keep from the base-guard machinery it replaces. `root` is the entry's OWN
    recorded root (:attr:`MergedChunkEntry.root`), returned alongside the path
    so a caller never has to re-derive one — see :func:`_replay_targets`.
    """
    ledger = _read_merged_chunks(repo_root)
    if ledger is None:
        raise SystemExit(
            f"{_merged_chunks_path(repo_root)} exists but could not be read as a "
            f"merge ledger — recomposing now could silently drop a between-build "
            f"`kb-merge`. Run `mise run kb-build` to reset it."
        )
    by_path: dict[Path, MergedChunkEntry] = {}
    for entry in ledger:
        key = _resolve(repo_root, entry.chunk)
        by_path.pop(key, None)
        by_path[key] = entry

    verified: list[tuple[Path, str]] = []
    for path, entry in by_path.items():
        if not path.is_file():
            raise SystemExit(
                f"the recomposition ledger names {entry.chunk!r} but that file is "
                f"missing — recomposing now would silently drop that merge's "
                f"content. Restore the file, or run `mise run kb-build` to reset "
                f"the ledger."
            )
        try:
            actual = _sha256_file(path)
        except OSError as e:
            raise SystemExit(
                f"the recomposition ledger names {entry.chunk!r} but it could not "
                f"be read ({e}) — recomposing now would silently drop that merge's "
                f"content."
            ) from e
        if actual != entry.sha256:
            raise SystemExit(
                f"{entry.chunk!r} has changed since it was merged (sha256 was "
                f"{entry.sha256}, is now {actual}) — recomposing now would replay "
                f"different content than what was actually merged. Run "
                f"`mise run kb-build` to reset the ledger."
            )
        verified.append((path, entry.root))
    return verified


def _validate_replay_chunks(paths: list[Path]) -> None:
    """Refuse if any chunk about to be replayed fails schema/integrity validation.

    The same gate `build()` applies to the same chunks, for the same reason —
    a chunk that merged cleanly once is not guaranteed to still be well-formed
    if it, or a chunk sharing its cross-chunk id space, was hand-edited since.
    """
    from kb_setup import chunks as _chunks

    problems = {p: i for p, i in _chunks.validate_files(paths).items() if i}
    if not problems:
        return
    lines = [f"  {p.name}: {i}" for p, issues in problems.items() for i in issues[:5]]
    raise SystemExit(
        f"{len(problems)} extraction chunk(s) failed validation — refusing to "
        f"recompose:\n" + "\n".join(lines)
    )


def _require_present(paths: list[Path], *, what: str) -> None:
    """Refuse, NAMING every path, if any recorded input is no longer on disk."""
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise SystemExit(
            f"{len(missing)} recorded {what}(s) no longer on disk — cannot "
            f"recompose:\n  " + "\n  ".join(missing) + "\nRun `mise run kb-build`."
        )


def _replay_targets(
    repo_root: Path,
    sources: Path,
    manifest_chunk_names: list[str],
    chunk_roots: dict[str, str],
    ledger_chunks: list[tuple[Path, str]],
) -> list[tuple[Path, str]]:
    """`(chunk, root)` pairs for `_MERGE_SCRIPT`, manifest order then ledger order.

    A manifest chunk's root is `chunk_roots[name]` when the compose manifest
    recorded an override for it — every chunk ever promoted from the ledger
    carries one (:func:`append_merged_chunk`'s `root`, threaded through
    `refresh_self`'s promotion) — and otherwise falls back to the convention
    `build()` itself used to merge it the first time: `sources/<name>`, `name`
    derived from the chunk's stem. That fallback is safe ONLY for a chunk
    `build()` discovered via its own `sources/extractions/*.json` glob, which
    is exactly the set that has no override.

    A ledger chunk not yet promoted carries its OWN verified `(path, root)`
    pair straight from `_verified_ledger_chunks` — the root `kb-merge`
    actually used, never a guess. Before #175's cold-review fixes this derived
    a ledger chunk's root from `c.resolve().parent` on every call, which
    happened to match `merge_chunk`'s own DEFAULT but silently discarded a
    caller's custom `--root` — and, the sharper bug, was recomputed fresh on
    every recomposition rather than recorded once, so a chunk promoted into
    `manifest.chunks` replayed under a DIFFERENT derived root on the very next
    `kb-watch` (finding 4b). Recording the root at merge time and carrying it
    through the promotion is what makes it stable across every later replay.
    """
    manifest_targets = [
        (
            _resolve(repo_root, name),
            chunk_roots.get(name, str((sources / Path(name).stem.removesuffix("-docs")).resolve())),
        )
        for name in manifest_chunk_names
    ]
    return manifest_targets + list(ledger_chunks)


def _recompose_into_temp(
    repo_root: Path, real_out: Path, inputs: list[Path], replay: list[tuple[Path, str]]
) -> None:
    """Merge `inputs`, replay `replay`, into a scratch file — then swap it in atomically.

    The scratch file lives in the SAME directory as `real_out` (never the
    system temp dir), so the final `Path.replace` is guaranteed to be an
    atomic rename rather than risking a cross-filesystem copy — the same
    reason `atomic.write_text`, `prose.derive` and `hyperedges._write_atomic`
    all reserve their temp name beside the file they replace.

    Every step above the swap runs against the SCRATCH file, never `real_out`
    — so the real `graphify-out/graph.json` stays exactly what the last
    successful build (or recomposition) left it, valid and correctly stamped,
    for the entire — potentially multi-minute — duration of this call. The
    stamp is cleared only immediately before the swap (see the comment at that
    line); any failure before the swap leaves `real_out` untouched, and the
    `except` below removes the scratch file and re-raises — the same "clear
    first, only re-stamp on full success" rule `build()`'s own `_clear_stamp`
    follows, applied at the one moment it actually matters for this shape.

    `tmp_out` is chmod'd to :data:`_GRAPH_MODE` BEFORE the swap:
    `tempfile.mkstemp` always creates its file `0600`, and `Path.replace` is a
    rename — the surviving inode's permission bits are the TEMP file's, not
    the file it replaces. Left unfixed, one recomposition would silently
    tighten `graph.json` from world-readable to owner-only, and graphify's own
    `_atomic_replace` PRESERVES whatever mode is already there, so nothing
    downstream would ever repair it (#175 cold review, finding 5 — the exact
    hazard `hyperedges._write_atomic` already guards against for its own
    writes; see `hyperedges._GRAPH_MODE`).
    """
    gpy = graphify_python(repo_root)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(real_out.parent), prefix=real_out.name + ".", suffix=".recompose.tmp"
    )
    os.close(fd)
    tmp_out = Path(tmp_name)
    try:
        print(f"[kb-watch] composing graph.json from {len(inputs)} recorded input(s)")
        _merge_sources_into(repo_root, tmp_out, inputs)
        print(f"[kb-watch] replaying {len(replay)} doc extraction(s)")
        for chunk, root in replay:
            _run([gpy, str(_MERGE_SCRIPT), str(chunk), root, str(tmp_out)], repo_root)
        # Only NOW — immediately before the swap — does the REAL artifact's
        # identity actually change. Clearing the stamp any earlier would mark a
        # still-good graph unstamped for no reason (everything above wrote only
        # to `tmp_out`); any later and a crash between clearing and replacing
        # could leave the swap landing under a stamp that no longer describes
        # what it is about to become.
        _clear_stamp(repo_root, tag="kb-watch")
        tmp_out.chmod(_GRAPH_MODE)
        tmp_out.replace(real_out)
    except BaseException:
        tmp_out.unlink(missing_ok=True)
        raise


def refresh_self(repo_root: Path) -> None:
    """Recompose `graph.json` from what the last build recorded — `kb-watch`.

    THIS REPLACES the base-snapshot/guard machinery that used to restart
    `graph.json` from a pre-self-merge snapshot, which #175's single-N-ary
    -merge restructure removed the separable step that machinery depended on
    (see git history for the two rounds of cold-review fixes — a
    competing-writer race, then a re-check-before-swap race — that machinery
    had needed to be safe). The property that machinery existed to guarantee
    survives here in a different shape: instead of a snapshot, `build()`
    records exactly what it composed (`.compose-manifest.json`) and every
    between-build `kb-merge` appends its chunk's path and sha256 to a ledger
    (`.merged-chunks.json`, via :func:`append_merged_chunk`); this function
    refuses — rather than silently dropping — the moment a ledger entry cannot
    be verified against what is actually on disk, and recomposes entirely in a
    scratch file (:func:`_recompose_into_temp`) so the real artifact is never
    at risk while that verification and the recompose itself are running.

    This does NOT fingerprint `sources/*.manifest` / `sources/extractions/*.json`
    the way `build()` does. That was tried and was a REGRESSION, not a
    simplification (#175 cold review, finding 1): this function recomposes
    ONLY from the recorded compose manifest and the verified ledger,
    deliberately never re-reading a manifest at all (see the paragraph above).
    Stamping a live glob over those files anyway would record, as "what this
    graph was built from", inputs it structurally did not consult — so a
    manifest or chunk added since the last `kb-build` would be fingerprinted
    WITHOUT being in the graph, and `kb-currency-check` would report the
    corpus in sync while it excludes exactly that content. What a
    recomposition CAN honestly claim is that the artifact's own fingerprints
    still describe what is on disk now, with the input map it inherits from
    the last real build carried forward VERBATIM — recorded by
    :func:`_restamp_self` from a snapshot :func:`_held_stamp` takes BEFORE
    `_recompose_into_temp` clears the stamp, since by the time this function's
    own tail runs there is no stamp left on disk to read back (#175 cold
    review round 2, NEW-1 — see `_held_stamp`'s docstring for the defect this
    fixes).
    """
    manifest = _load_compose_manifest_or_refuse(repo_root)
    sources = repo_root / "sources"
    manifest_chunks = [_resolve(repo_root, c) for c in manifest.chunks]
    ledger_verified = _verified_ledger_chunks(repo_root)
    ledger_chunks = [path for path, _root in ledger_verified]

    _validate_replay_chunks(manifest_chunks + ledger_chunks)

    corpus_leaves = [_resolve(repo_root, c) for c in manifest.corpus]
    _require_present(corpus_leaves, what="corpus leaf")
    _require_present(manifest_chunks + ledger_chunks, what="chunk")

    # Fold this run's ledger into the chunk bookkeeping BEFORE anything
    # replays — DE-DUPLICATED (#175 cold review, finding 4a): a chunk whose
    # resolved path is already in `manifest.chunks` (an earlier `kb-watch`
    # already promoted it, or it was already part of `build()`'s own glob
    # before ALSO being merged by hand — the documented flow commits a chunk
    # under `sources/extractions/` AND merges it, so both can name the same
    # file in the SAME run) is replayed exactly ONCE, via the manifest branch
    # below, never a second time via the ledger branch. `chunk_roots` is
    # refreshed for EVERY verified ledger entry regardless of the dedup
    # outcome, so an already-present chunk still replays with the root THIS
    # run actually used — the most recently correct one — not a stale or
    # re-derived guess.
    #
    # `ledger_verified` cannot itself name the same resolved path twice —
    # `_verified_ledger_chunks` already collapsed the ledger to one row per
    # path before returning (#175 cold review round 2, NEW-2) — so this
    # `existing_chunks` check only ever has the ledger-vs-MANIFEST case left
    # to catch; a within-this-run ledger-vs-ledger duplicate can no longer
    # reach this loop at all.
    existing_chunks = set(manifest.chunks)
    new_chunk_roots = dict(manifest.chunk_roots)
    promoted: list[str] = []
    new_ledger_entries: list[tuple[Path, str]] = []
    for path, root in ledger_verified:
        name = _relativize_or_str(path, repo_root)
        new_chunk_roots[name] = root
        if name in existing_chunks:
            continue
        promoted.append(name)
        new_ledger_entries.append((path, root))

    self_subgraphs = _extract_self(repo_root)
    replay = _replay_targets(
        repo_root, sources, list(manifest.chunks), new_chunk_roots, new_ledger_entries
    )
    real_out = repo_root / "graphify-out" / "graph.json"
    # MUST run before `_recompose_into_temp` — that call is what clears the
    # stamp (`_clear_stamp`, immediately before the swap), and this is the
    # only remaining chance to read what it is about to delete. See
    # `_held_stamp`'s own docstring (#175 cold review round 2, NEW-1).
    held_stamp = _held_stamp(repo_root)
    _recompose_into_temp(repo_root, real_out, [*corpus_leaves, *self_subgraphs], replay)

    label_rc = graphify_ops.label(repo_root)
    if label_rc != 0:
        raise SystemExit(f"[kb-watch] label pass failed (rc={label_rc}) — aborting")
    graph_checks.assert_composition(real_out, tag="kb-watch")

    _write_compose_manifest(
        repo_root,
        replace(
            manifest,
            self_graph=str(_self_subgraph(repo_root).relative_to(repo_root)),
            chunks=(*manifest.chunks, *promoted),
            chunk_roots=new_chunk_roots,
        ),
        tag="kb-watch",
    )
    _reset_merged_chunks(repo_root, tag="kb-watch")
    _restamp_self(repo_root, held_stamp)
    print("[kb-watch] done — graphify-out/graph.json recomposed from recorded inputs")


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
    graph_checks.assert_composition(out, tag="kb-build")

    # What `kb-watch` recomposes FROM (#175's follow-up). Recorded here, after
    # composition is proven correct, so a `refresh_self` reading it back is
    # reading a description of an artifact `assert_composition` just vouched
    # for — never of a build that failed partway through. Resetting the ledger
    # in the same breath is the other half: this build already reflects every
    # `kb-merge` that landed since the last one (they are baked into `out`
    # above), so replaying them again on the next recomposition would be
    # redundant at best and wrong if any of them has since been hand-edited.
    _write_compose_manifest(
        repo_root,
        ComposeManifest(
            corpus=tuple(
                str((sources / n / "graphify-out" / "graph.json").relative_to(repo_root))
                for n in corpus
            ),
            self_graph=str(_self_subgraph(repo_root).relative_to(repo_root)),
            chunks=tuple(str(p.relative_to(repo_root)) for p in chunk_paths),
            # Every chunk here came from `build()`'s own `sources/extractions/*.json`
            # glob, so its root is always the naming-convention default
            # `_replay_targets` falls back to — no override needed.
            chunk_roots={},
        ),
    )
    _reset_merged_chunks(repo_root)

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


def _clear_stamp(repo_root: Path, *, tag: str = "kb-build") -> None:
    """Remove the build stamp so an aborted build cannot leave a stale one.

    `tag` names the caller in the printed lines — `refresh_self` (via
    `_recompose_into_temp`) passes `"kb-watch"` so a `kb-watch` run's own
    bookkeeping is not misreported as `kb-build`'s (#175 cold review,
    finding 9).
    """
    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return
        path = sync.stamp_path(repo_root, spec)
        if path is not None and path.exists():
            path.unlink()
            print(f"[{tag}] cleared {path.name} — it is rewritten only on success")
    except (OSError, ValueError, ImportError) as e:
        print(f"[{tag}] WARNING: could not clear the currency stamp: {e}")


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


@dataclass(frozen=True)
class _HeldStamp:
    """A build stamp's carry-forward fields, snapshotted before `_clear_stamp` runs.

    `_recompose_into_temp` unlinks the stamp file (`_clear_stamp`) immediately
    before swapping in the recomposed graph.json — the same "clear first,
    write only on success" rule `build()` follows, applied at the one moment
    it matters for this shape (see that function's own docstring). But unlike
    `build()`, `refresh_self` never runs a builder to re-observe `version`
    from and never re-reads a manifest to derive `source_ref` from — the only
    thing it can honestly do is carry the LAST real build's values forward
    VERBATIM, and that means reading them off disk BEFORE the clear destroys
    them, not after.

    Before this existed, `refresh_self` tried to restamp AFTER the clear by
    calling `sync.restamp_artifacts` — whose contract is "refresh an EXISTING
    stamp" (`if path is None or not path.exists(): return None`), exactly
    right for its OTHER caller `kb-artifacts`, which never deletes the stamp
    first. Here it always found the file already gone and always returned
    `None`, so every `kb-watch` silently left the repo permanently unstamped
    (#175 cold review round 2, NEW-1). `_held_stamp` is the fix: read these
    fields while the file still exists, hold them across the clear, and write
    them straight back via `sync.write_stamp` — never through
    `restamp_artifacts`, which by then would find nothing.
    """

    version: str
    source_ref: str
    inputs: dict[str, str] | None


def _held_stamp(repo_root: Path) -> _HeldStamp | None:
    """Snapshot the stamp's carry-forward fields — MUST run BEFORE the clear.

    `refresh_self` calls this before `_recompose_into_temp`, which is what
    clears the stamp. There is no later point at which these fields could
    still be read off disk — see :class:`_HeldStamp`'s docstring for the
    defect this exists to avoid repeating.

    Mirrors `sync.restamp_artifacts`'s own "no existing stamp -> nothing to
    carry forward" rule (`None` here means the same thing `restamp_artifacts`
    returning `None` means there), just evaluated on the PRE-clear file
    instead of a post-clear one that can no longer exist.

    Best-effort, like every other stamp path in this module: a read failure
    must not abort a recomposition that is otherwise fine. `refresh_self`
    just ends unstamped and says so — the same outcome as running `kb-watch`
    before any `kb-build` has ever stamped anything.
    """
    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return None
        path = sync.stamp_path(repo_root, spec)
        if path is None or not path.exists():
            return None
        existing = sync.read_stamp(repo_root, spec)
        return _HeldStamp(
            version=str(existing.get("version", "")),
            source_ref=str(existing.get("source_ref", "")),
            inputs=sync.stamped_input_fingerprints(existing),
        )
    except (OSError, ValueError, ImportError) as e:
        print(f"[kb-watch] WARNING: could not read the existing currency stamp: {e}")
        return None


def _restamp_self(repo_root: Path, held: _HeldStamp | None) -> None:
    """Write `held` back as the stamp — the fields `_held_stamp` read before the clear.

    NOT `sync.restamp_artifacts`: that reads the CURRENT on-disk stamp, and by
    the time `refresh_self` reaches its own tail, `_recompose_into_temp` has
    already unlinked it (`_clear_stamp`, immediately before the swap). `held`
    is what survives that — a snapshot taken earlier, before the file was
    destroyed (#175 cold review round 2, NEW-1; see `_held_stamp`).

    `version` and `source_ref` are written back exactly as held, never
    re-observed: the graph changed but the BUILDER did not, and re-observing
    would let a graphify upgrade mid-session silently relabel a graph the
    previous version actually built. The recorded INPUT fingerprint map is
    carried forward the same way and for the same reason: `refresh_self`
    deliberately never re-reads `sources/*.manifest` /
    `sources/extractions/*.json` (see its own docstring), so it has no more
    standing to restate what the graph was built from than `kb-artifacts`
    does. `sync.write_stamp` recomputes `artifact_fingerprints` itself, fresh
    — that part MUST be live, since the whole point of a restamp is that the
    artifact's bytes just moved.

    `held is None` means there was nothing to carry forward — either no
    `kb-build` has ever stamped this repo, or `_held_stamp`'s own read failed.
    Without ANY restamp, a refresh is actively harmful: `artifact_fingerprints`
    is `size:mtime_ns`, so any rewrite of graph.json moves it, and every later
    `kb-currency-check` reports the graph as not verifiably built by the pin —
    a permanent red that means nothing, which is how a real signal gets
    ignored. So this still prints the warning a from-scratch `kb-watch` has
    always printed, rather than staying silent. Best-effort like every other
    stamp path here: a refresh must not fail over its own bookkeeping.
    """
    try:
        from kb_setup.currency import sync

        spec = _currency_spec(repo_root)
        if spec is None:
            return
        if held is None:
            print(
                "[kb-watch] WARNING: no build stamp to refresh — run `mise run kb-build`; "
                "currency step 1 will report this graph as never stamped."
            )
            return
        path = sync.write_stamp(
            repo_root, spec, version=held.version, source_ref=held.source_ref, inputs=held.inputs
        )
        print(f"[kb-watch] restamped {path.name}")
    except (OSError, ValueError, ImportError) as e:
        print(f"[kb-watch] WARNING: could not restamp: {e}")


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
