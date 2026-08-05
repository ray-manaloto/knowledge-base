"""Single-source graphify operations: merge a doc chunk, label, transcribe.

Each is wrapped by a mise task (kb-merge / kb-label / kb-transcribe) so NOTHING
calls graphify by hand — the PreToolUse guard (`kb_setup.hook_guard`) denies raw
`graphify …` / `_merge_docs.py` invocations and redirects here.

Every graphify subprocess runs under `graphify_env.clean_env()`, which strips
non-Claude provider keys — so labeling can only use the claude-cli backend (your
Claude Pro/Max subscription) or the deterministic no-LLM fallback, never an
auto-detected Gemini/OpenAI key.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import hyperedges, prose, stamps
from kb_setup.graphify_env import clean_env, graphify_exe, graphify_python

if TYPE_CHECKING:
    from collections.abc import Sequence

_MERGE_SCRIPT = Path(__file__).with_name("_merge_docs.py")


#: How many validation issues a refusal prints before truncating. A chunk with a
#: systematic fault (every node missing `_origin`) can produce hundreds; the
#: point of the message is to name the CLASS, and the full list is one
#: `mise run kb-validate-chunks` away.
_MAX_SHOWN_ISSUES = 10


def merge_chunk(repo_root: Path, chunk: str, root: str | None = None) -> int:
    """Merge one host-agent extraction chunk into graphify-out/graph.json.

    Runs `_merge_docs.py` under graphify's bundled interpreter (it imports
    graphify) with a Gemini-free env. `root` is the source root for path
    relativization (defaults to the chunk's dir; moot for URL-sourced chunks).

    A successful merge then RE-DERIVES the prose graph, exactly as
    `graph.build()` does at its own last step. `graph-prose.json` is a pure
    function of `graph.json`, so a merge that does not refresh it leaves the
    corpus and its scoped view disagreeing — and `--prose` is the *recommended*
    arm for a question about the documents, while the `kb-curator` ingestion
    workflow is add -> merge -> label with no prose step. Measured 2026-07-30:
    after merging a 132-node chunk, `kb-query --prose` still reported the
    pre-merge 2,421 nodes and returned none of the just-merged material; the
    only thing that had ever fixed it was the next unrelated `kb-build`. So
    every merge-only ingestion had been silently answering document questions
    from an older corpus.
    """
    chunk_path = Path(chunk)
    if not chunk_path.is_file():
        print(f"[kb-merge] no such chunk: {chunk}", file=sys.stderr)
        return 2

    # VALIDATE BEFORE MERGING — the same gate `build()` applies, for the same
    # reason (cold review, 2026-08-03). Existing-file was the ONLY check here, so
    # a chunk with a missing `_origin` marker or a dangling edge merged happily
    # and the damage showed up later as a node that had quietly stopped being
    # retrievable. `kb-merge` is the sharper of the two doors: it is the one used
    # for a FRESH extraction, straight off an agent, which is precisely the input
    # least likely to be well-formed.
    from kb_setup import chunks as _chunks

    issues = _chunks.validate_files([chunk_path]).get(chunk_path) or []
    if issues:
        print(f"[kb-merge] {chunk_path.name} failed validation — refusing:", file=sys.stderr)
        for i in issues[:_MAX_SHOWN_ISSUES]:
            print(f"  {i}", file=sys.stderr)
        if len(issues) > _MAX_SHOWN_ISSUES:
            print(f"  … and {len(issues) - _MAX_SHOWN_ISSUES} more", file=sys.stderr)
        return 2
    out = repo_root / "graphify-out" / "graph.json"
    src_root = root or str(chunk_path.resolve().parent)
    gpy = graphify_python(repo_root)
    cmd = [gpy, str(_MERGE_SCRIPT), str(chunk_path), src_root, str(out)]
    print(f"  $ {' '.join(cmd)}")
    rc = subprocess.run(cmd, cwd=repo_root, env=clean_env(), check=False).returncode
    if rc != 0:
        # Gated on the merge's rc, not run unconditionally: a failed merge may
        # have left graph.json untouched or half-written, and deriving from
        # either would replace a valid prose graph with one nobody asked for.
        # The caller's job here is the failed merge, and this rc says so.
        return rc
    prose_rc = _derive_prose(repo_root, tag="kb-merge", did="the chunk merged")
    if prose_rc != 0:
        return prose_rc

    # Deferred import: `graph` imports THIS module at its own top level
    # (`from kb_setup import graph_checks, graphify_ops`), so a top-level
    # `from kb_setup import graph` here would be circular. By the time this
    # function actually RUNS both modules are already fully loaded, so this is
    # a plain sys.modules cache hit — it only has to be deferred, not avoided.
    from kb_setup import graph

    try:
        graph.append_merged_chunk(repo_root, chunk, src_root)
    except (OSError, ValueError) as exc:
        # NOT swallowed: the chunk really did merge and the prose graph really
        # did re-derive, but reporting rc=0 here would claim the operation is
        # fully durable when the one record `kb-watch` reads to recompose from
        # just failed to extend — the same silent-discard this whole ledger
        # exists to prevent, arriving through its own write path instead of
        # through recomposition. Same shape as `_derive_prose`'s own gate.
        print(
            f"[kb-merge] the chunk merged and the prose graph was re-derived, but "
            f"recording it in the recomposition ledger failed: {exc}\n"
            f"[kb-merge] a future `mise run kb-watch` will not replay this chunk "
            f"unless it is re-merged.",
            file=sys.stderr,
        )
        return 1
    # LAST, and only on the fully-successful path (#181). `_merge_docs.py` is the
    # last writer of `graph.json` here — `_derive_prose` writes `graph-prose.json`
    # and `append_merged_chunk` writes the ledger, neither of which `currency.toml`
    # declares — so the fingerprint this records is the merge's final bytes.
    #
    # This is the THIRD wholesale writer of `graph.json`, alongside `label` and
    # `artifacts.generate`; `stamps.py`'s docstring said "two callers" because
    # this one was deferred out of #179. Without it a merge-only run — the
    # `kb-curator` skill's own quick path, with no following `kb-label` — leaves
    # `kb-currency-check` reporting build-stamp drift until something else
    # rewrites and restamps the graph.
    #
    # The full restamp, not a narrowed one. Measured on a real merge rather than
    # inferred: of the four declared artifacts, ONLY `graph.json` moves — the
    # three derived views are byte-identical before and after, so re-fingerprinting
    # them records the value they already had and masks nothing. The narrowing
    # this ticket's body floated is byte-for-byte identical in outcome. What a
    # merge really does invalidate is the derived views' CONTENT, and no
    # `size:mtime_ns` was ever able to see that — which is why the signal that
    # covers it is `currency.views`, not a variant of this call.
    #
    # A failed ledger write returns above without reaching here, so the stamp
    # stays stale for a graph that really was rewritten. That is the honest
    # outcome: the drift line then reports, truthfully, that something rewrote
    # the graph outside a complete run.
    stamps.refresh_after_regen(repo_root, tag="kb-merge")
    return 0


def _derive_prose(repo_root: Path, *, tag: str, did: str) -> int:
    """Re-derive the prose graph, reporting a failure as a non-zero rc.

    The derivation's own failure modes raise, and all of them leave NO prose
    graph — `prose.derive` unlinks first precisely so an abort fails closed.
    That is the right artifact state and the wrong exit code: `graph.json` really
    did change, so returning 0 would report an operation whose `--prose` arm has
    just gone missing as an unqualified success.

    All THREE are caught, and the first draft caught two. `ValueError` covers
    nothing-survives and — since `json.JSONDecodeError` subclasses it — an
    unreadable `graph.json`; `SystemExit` covers no-built-graph. **`OSError` is
    the one that escaped**: a full disk, a vanished directory, a permissions
    change. It is not hypothetical — `tests/test_prose_rederivation.py` injects
    exactly that fault against `prose.derive`, so the module had a test for a
    failure this wrapper then let propagate as an unhandled traceback instead of
    the rc and the message below. (Cold lane, round 2.)

    `tag`/`did` name the CALLER, because this message is the only thing telling
    someone which of their two graphs is now absent — and "the chunk merged"
    printed after a `kb-label` run would send them looking at the wrong step.
    """
    try:
        prose.derive_for(repo_root)
    except (OSError, ValueError, SystemExit) as exc:
        print(
            f"[{tag}] {did}, but the prose graph could not be re-derived: "
            f"{exc}\n[{tag}] `kb-query --prose` has no corpus until "
            f"`mise run kb-prose` (or `mise run kb-build`) succeeds.",
            file=sys.stderr,
        )
        return 1
    return 0


def label(repo_root: Path, *, missing_only: bool = False, claude_cli: bool = False) -> int:
    """(Re)label communities WITHOUT Gemini.

    Default = graphify's deterministic, LLM-free hub-name labeler (names each
    community after its highest-degree member). Instant, no API, no Gemini.

    Why deterministic is the default (Ray, 2026-07-22, control-arm verified): the
    only LLM path that is NOT Gemini is graphify's `claude-cli` backend, and that
    backend is BROKEN for labeling (issue #2076) — the CLI returns prose-wrapped
    JSON ("Done — cluster names above …") that graphify cannot parse, so every
    batch fails and the run is slow + noisy for no gain. `--claude-cli` still opts
    into it (falls back to deterministic on the inevitable failure), kept only so a
    future graphify fix can be re-probed through the task. clean_env() strips
    GEMINI/GOOGLE either way, so Gemini can never be auto-selected.

    A successful label RE-DERIVES the prose graph, for the same reason `kb-merge`
    does. `graphify label` is not a sidecar-only write: verified in the installed
    0.9.30 — `graphify/cli.py:1546` selects `label`, and that branch runs unbroken
    (no intervening `elif cmd`) to `to_json(G, communities, str(out /
    "graph.json"), …)` at :1830 — so it rewrites `graph.json` outright. (:1836 is
    six lines further on and writes the LABELS SIDECAR; this docstring cited it by
    mistake until the cold lane caught it, which had the citation pointing at
    exactly the sidecar-only write the sentence exists to deny.) The
    documented ingestion order is merge -> label, so without this the merge's own
    re-derivation is undone by the very next step and `--prose` is stale again
    with nothing having failed. (Cold lane, round 1.)

    A successful label also CARRIES HYPEREDGES across the run (#171 local
    mitigation, #175): `graphify label`'s own graph.json round-trip loses them
    (measured 5->0 on this repo's aggregate — see `hyperedges.py`'s module
    docstring for the verified mechanism). The pre-run list is captured before
    `_run` below launches anything and reattached in `_labelled`, before prose
    re-derivation — `graph-prose.json`'s hyperedge-retention report
    (`prose.ProseStats`) must see the restored list, not the emptied one.
    """
    # Gate on the binary we are ABOUT TO RUN, not on PATH. The old
    # `shutil.which("graphify")` check sat directly in front of a
    # PATH-independent invocation and could abort with `mise which` resolving
    # perfectly well — refusing to run a binary it had already found. A bare
    # name is `graphify_exe`'s last resort, and `Path("graphify").is_file()` is
    # False, so the genuinely-absent case still refuses.
    exe = graphify_exe(repo_root)
    if not Path(exe).is_file():
        print(
            "[kb-label] graphify not found — neither `mise which graphify` nor PATH "
            "resolved it. Run `mise install`.",
            file=sys.stderr,
        )
        return 2

    # Captured BEFORE anything runs: a missing graph.json (no `kb-build` yet)
    # returns [] here, and the graphify call below fails on its own account
    # (its own "no graph found" refusal) — this capture changes nothing about
    # that path, it just also has nothing to carry.
    carried = hyperedges.capture(_full_graph(repo_root))

    base = [exe, "label", "."]
    if missing_only:
        base.append("--missing-only")

    def _run(cmd: list[str], why: str) -> int:
        print(f"  $ {' '.join(cmd)}   # {why}")
        return subprocess.run(cmd, cwd=repo_root, env=clean_env(), check=False).returncode

    if not claude_cli:
        # No --backend + GEMINI/GOOGLE stripped -> auto-detect finds nothing ->
        # deterministic hub labeler. The clean default.
        return _labelled(
            repo_root, _run(base, "deterministic no-LLM hub labels (Gemini-free)"), carried
        )

    rc = _run(
        [*base, "--backend=claude-cli", "--max-concurrency=1"],
        "claude-cli backend (opt-in; broken #2076 — expect fallback)",
    )
    if rc == 0:
        return _labelled(repo_root, rc, carried)
    print(
        "[kb-label] claude-cli backend failed (#2076) — deterministic no-LLM fallback.",
        file=sys.stderr,
    )
    return _labelled(repo_root, _run(base, "deterministic fallback"), carried)


def _labelled(repo_root: Path, rc: int, carried: list[hyperedges.Hyperedge]) -> int:
    """Restore carried hyperedges, refresh the currency stamp, then re-derive the prose graph.

    All three are gated on `rc`, for the same reason `merge_chunk` gates: a labelling run that
    failed may have left `graph.json` in any state, and either reattaching over
    it, restamping it, or deriving from it would assert a fact ("the run
    succeeded") that is false. The failing rc is the caller's job, and
    returning it unchanged says so — `carried` is discarded along with it.

    Reattach happens BEFORE the restamp and BEFORE `_derive_prose`, and in that
    order, for two separate reasons:

    - The currency stamp's fingerprint must cover graph.json's FINAL bytes, and
      `reattach` is the last writer of that file — this mirrors
      `artifacts.generate`, which orders capture -> subprocess -> reattach ->
      restamp for the same reason (#179).
    - `_derive_prose` reads graph.json fresh and reports what survived
      (`prose.ProseStats.hyperedges_out`), so the restored list has to already
      be on disk when it runs, not after.

    The restamp runs before `_derive_prose`, not after, because
    `graphify-out/graph-prose.json` is NOT in the stamped set —
    `currency.toml`'s `[tool.graphify]` declares `artifact =
    "graphify-out/graph.json"` and `artifacts = ["graphify-out/GRAPH_REPORT.md",
    "graphify-out/graph.graphml", "graphify-out/wiki"]`, neither of which is the
    prose graph. So a prose derivation that fails afterwards cannot invalidate a
    fingerprint that was never about it, and gating the restamp on the prose
    step's rc would only buy a permanent, meaningless currency red on a graph
    that was legitimately relabelled.

    One more thing worth saying plainly, so the next reader does not mistake it
    for a bug: `stamps.refresh_after_regen` re-fingerprints the WHOLE declared
    artifact set via `sync.restamp_artifacts`, so this restamp also touches
    `GRAPH_REPORT.md` / `graph.graphml` / `wiki` — none of which `label`
    regenerated. That is correct and deliberate; the stamp answers "has
    anything moved since we last looked", not "is every output mutually
    consistent", which is the same semantics `stamps.refresh_after_regen`
    already documents for a partial `kb-artifacts only=` run. It also carries
    the recorded INPUT fingerprints forward verbatim rather than re-observing
    `sources/`: `label` never reads `sources/`, so it has no standing to
    restate what the graph was built from — re-observing them would be drift
    laundering, which was a P1 in the last round's review.
    """
    if rc != 0:
        return rc
    hyperedges.reattach(_full_graph(repo_root), carried)
    stamps.refresh_after_regen(repo_root, tag="kb-label")
    return _derive_prose(repo_root, tag="kb-label", did="communities were relabelled")


#: The flag `kb-query` adds on top of `graphify query`. Not a graphify flag —
#: it resolves to graphify's own `--graph`, pointed at the derived prose graph.
PROSE_FLAG = "--prose"

#: Selects the BM25/IDF lexical scorer (`kb_setup.lexical`) instead of
#: `graphify query`. A THIRD retrieval path, not a replacement for `--prose`
#: (knowledge-base#12 P1): the golden set measures `unscoped` / `prose` /
#: `prose+idf` side by side, so the scorer's effect stays attributable to the
#: scorer. It reads the same derived prose graph `--prose` selects, so the two
#: together are redundant rather than contradictory and are allowed.
IDF_FLAG = "--idf"

#: The only flags the `--idf` path understands. Everything else is REJECTED
#: rather than ignored: this path never shells out to graphify, so a
#: graphify-only flag (`--budget`, `--depth`) alongside it would have no effect
#: whatsoever — and a flag that silently does nothing is worse than one that
#: errors, because the caller reads the answer as if the flag applied.
GRAPH_FLAG = "--graph"
_IDF_TOP = "--top"

#: How many ranked hits `--idf` prints. Chosen to sit just above the golden
#: set's `k=10` window so a human reading the output can see what fell just
#: outside it; the eval calls the library directly and is not affected.
IDF_DEFAULT_TOP = 20

#: The attached form of graphify's own flag, which graphify DOES NOT SUPPORT.
#: Probed 2026-07-25 from a scratch directory: `graphify query q
#: --graph=<abs path>` exits 1 with `graph file not found:
#: /private/tmp/graphify-out/graph.json` — it ignores the argument entirely and
#: falls back to the cwd-relative default. So the form can neither be forwarded
#: (graphify drops it) nor read as "the caller pinned a corpus" (they did not,
#: as far as graphify is concerned). It is rejected instead, because the
#: alternative is an answer from a corpus nobody chose — which is the one
#: failure this wrapper exists to prevent.
ATTACHED_GRAPH = "--graph="


def query(repo_root: Path, args: Sequence[str]) -> int:
    """`kb-query` — `graphify query`, with `--prose` selecting the prose-only graph.

    The graph is ALWAYS pinned with an explicit `--graph`, never left to resolve
    against the process cwd. graphify's default is `graphify-out/graph.json`
    *relative to where it runs*, which silently agrees when invoked from the repo
    root and silently answers from some other corpus when it is not — the same
    trap that was caught in review of the retrieval eval (knowledge-base#30).

    `--prose` alongside an explicit `--graph` is an error rather than a
    precedence rule: the whole point of the flag is which corpus answered, so
    "one of them quietly wins" is the one behaviour that must not exist.
    """
    rest = [a for a in args if a not in {PROSE_FLAG, IDF_FLAG}]
    wants_prose = PROSE_FLAG in args
    wants_idf = IDF_FLAG in args
    attached = [a for a in rest if a.startswith(ATTACHED_GRAPH)]
    if attached:
        print(
            f"[kb-query] graphify does not support the attached form "
            f"({attached[0]}) — it ignores the argument and answers from the "
            f"cwd-relative default instead. Use `--graph <path>`, or --prose.",
            file=sys.stderr,
        )
        return 2
    if wants_prose and GRAPH_FLAG in rest:
        print(
            f"[kb-query] {PROSE_FLAG} and --graph both given — they name different "
            f"corpora and there is no sensible winner. Pass one.",
            file=sys.stderr,
        )
        return 2
    if wants_idf:
        return _idf_query(repo_root, rest)
    if GRAPH_FLAG not in rest:
        graph = prose.prose_graph_path(repo_root) if wants_prose else _full_graph(repo_root)
        if not graph.is_file():
            missing = "mise run kb-prose" if wants_prose else "mise run kb-build"
            print(f"[kb-query] no graph at {graph} — run `{missing}` first", file=sys.stderr)
            return 2
        rest = [*rest, "--graph", str(graph)]
    return subprocess.run(
        [graphify_exe(repo_root), "query", *rest], cwd=repo_root, env=clean_env(), check=False
    ).returncode


def _full_graph(repo_root: Path) -> Path:
    """The unscoped graph — every node, code AST included."""
    return repo_root / "graphify-out" / "graph.json"


def affected(repo_root: Path, args: Sequence[str]) -> int:
    """`kb-affected` — `graphify affected`, the reverse-dependency question.

    `query` is a forward BFS from the terms you name, so "what calls this" is a
    question it structurally cannot answer. `affected` walks the edges backwards
    instead, which is the blast radius of a change: which callers and which
    tests move if this symbol does.

    Wired here rather than left to a bare `graphify affected` — which the guard
    does allow — because `graph.refresh_self` exists precisely so this question
    is answerable about OUR code, and a capability with no verb is one nobody
    reaches for. `--depth` defaults to 2 upstream; pass it through untouched.

    The graph is pinned explicitly for the same reason `query` pins it: the
    upstream default resolves `graphify-out/graph.json` against the process cwd,
    so it answers from a different corpus depending on where it was run. Callers
    may still pass their own `--graph <path>`, which wins.

    The ATTACHED spelling `--graph=<path>` is REFUSED, exactly as `query`
    refuses it and for the same measured reason (see :data:`ATTACHED_GRAPH`):
    graphify ignores that form entirely and falls back to its cwd-relative
    default. Accepting it here would silently discard the caller's choice and
    substitute our pin — benign today, since our pin is the graph they almost
    certainly wanted, but it makes the docstring above a lie for one spelling.
    A near-identical sibling hardened against an input while this one was not is
    the shape a cold review flagged; the fix is to make them agree.
    """
    if not args:
        print(
            '[kb-affected] usage: mise run kb-affected -- "<symbol>" [--depth N] [--relation R]...',
            file=sys.stderr,
        )
        return 2
    if attached := [a for a in args if a.startswith(ATTACHED_GRAPH)]:
        print(
            f"[kb-affected] graphify does not support the attached form "
            f"({attached[0]}) — it ignores the argument and answers from the "
            f"cwd-relative default instead. Use `--graph <path>`.",
            file=sys.stderr,
        )
        return 2
    rest = list(args)
    if GRAPH_FLAG not in rest:
        graph = _full_graph(repo_root)
        if not graph.is_file():
            print(
                f"[kb-affected] no graph at {graph} — run `mise run kb-build` first",
                file=sys.stderr,
            )
            return 2
        rest = [*rest, GRAPH_FLAG, str(graph)]
    return subprocess.run(
        [graphify_exe(repo_root), "affected", *rest], cwd=repo_root, env=clean_env(), check=False
    ).returncode


@dataclass(frozen=True)
class _IdfArgs:
    """A parsed `--idf` invocation: the question, the corpus, how many to show."""

    question: str
    graph: Path | None
    top: int


def _parse_idf_args(rest: Sequence[str]) -> _IdfArgs | str:
    """Parse `--idf`'s arguments, or return the error message to print.

    Split out of :func:`_idf_query` so each half does one thing: this one only
    reads arguments and never touches the filesystem or prints, which is what
    lets it be tested without a graph on disk.
    """
    words: list[str] = []
    graph: Path | None = None
    top = IDF_DEFAULT_TOP
    args = list(rest)
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {GRAPH_FLAG, _IDF_TOP}:
            if i + 1 >= len(args):
                return f"{arg} needs a value"
            value = args[i + 1]
            i += 2
            if arg == GRAPH_FLAG:
                graph = Path(value)
                continue
            # Validated by the conversion itself, not by `isdigit()`: that
            # predicate accepts superscripts and other Numeric_Type=Digit
            # characters that `int()` then REJECTS, so `--top ²` would raise
            # instead of returning this message.
            try:
                parsed_top = int(value)
            except ValueError:
                return f"{_IDF_TOP} needs a positive integer, got {value!r}"
            if parsed_top < 1:
                return f"{_IDF_TOP} needs a positive integer, got {value!r}"
            top = parsed_top
            continue
        if arg.startswith("-"):
            return (
                f"{IDF_FLAG} does not understand {arg!r}. It runs our own scorer, "
                f"not `graphify query`, so a graphify flag would have no effect at "
                f"all — which is why this is an error and not a warning. "
                f"Supported: {GRAPH_FLAG} <path>, {_IDF_TOP} <n>."
            )
        words.append(arg)
        i += 1
    if not words:
        return f'{IDF_FLAG} needs a question, e.g. kb-query -- "…" {IDF_FLAG}'
    return _IdfArgs(question=" ".join(words), graph=graph, top=top)


def _idf_query(repo_root: Path, rest: Sequence[str]) -> int:
    """`kb-query --idf` — rank the prose graph with the BM25/IDF scorer.

    Never shells out to graphify: this is our own scorer over the same derived
    corpus (`kb_setup.lexical`). It therefore accepts only the flags it can
    honour and REJECTS everything else, rather than forwarding or ignoring it —
    a `--budget` silently doing nothing here would let a caller read the answer
    as if a budget had applied.
    """
    from kb_setup import lexical

    parsed = _parse_idf_args(rest)
    if isinstance(parsed, str):
        print(f"[kb-query] {parsed}", file=sys.stderr)
        return 2

    explicit = parsed.graph is not None
    graph = parsed.graph if explicit else prose.prose_graph_path(repo_root)
    if not graph.is_file():
        # Only the DEFAULT corpus has a task that creates it. Telling someone who
        # passed their own --graph to run `kb-prose` names a command that would
        # not produce the file they asked for.
        fix = "check the path" if explicit else "run `mise run kb-prose` first"
        print(f"[kb-query] no graph at {graph} — {fix}", file=sys.stderr)
        return 2
    try:
        index = lexical.load_index(graph)
    except (OSError, ValueError) as exc:
        print(f"[kb-query] could not index {graph}: {exc}", file=sys.stderr)
        return 1

    hits = lexical.search(index, parsed.question)
    print(f"[kb-query] {IDF_FLAG}: {index.size:,} indexed node(s) from {graph.name}")
    if not hits:
        print(
            f"[kb-query] no node shares a term with {parsed.question!r} — that is a "
            f"real empty result, not a truncated one."
        )
        return 0
    for rank, hit in enumerate(hits[: parsed.top], start=1):
        print(f"{rank:>3}  {hit.score:6.2f}  {hit.label}  [src={hit.source_file}]")
    if len(hits) > parsed.top:
        print(f"     … {len(hits) - parsed.top:,} more scoring above zero (raise {_IDF_TOP})")
    return 0


def transcribe(repo_root: Path, audio: str) -> int:
    """Transcribe a local audio file with graphify's bundled faster-whisper.

    Local, no API key, no LLM backend (e.g. a graphify-downloaded yt_*.m4a). Prints
    the transcript path. Extraction of the transcript into the graph is then the
    normal host-agent (Claude Code) step.
    """
    audio_path = Path(audio)
    if not audio_path.is_file():
        print(f"[kb-transcribe] no such audio file: {audio}", file=sys.stderr)
        return 2
    gpy = graphify_python(repo_root)
    code = (
        "from pathlib import Path\n"
        "from graphify.transcribe import transcribe\n"
        f"p = transcribe(Path({str(audio_path)!r}), output_dir=Path({str(audio_path.parent)!r}))\n"
        "print('[kb-transcribe] transcript ->', p)\n"
    )
    print(f"  $ {gpy} -c '<graphify.transcribe.transcribe {audio_path.name}>'")
    return subprocess.run([gpy, "-c", code], cwd=repo_root, env=clean_env(), check=False).returncode
