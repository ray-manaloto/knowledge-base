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

from kb_setup import prose
from kb_setup.graphify_env import clean_env, graphify_exe, graphify_python

if TYPE_CHECKING:
    from collections.abc import Sequence

_MERGE_SCRIPT = Path(__file__).with_name("_merge_docs.py")


def merge_chunk(repo_root: Path, chunk: str, root: str | None = None) -> int:
    """Merge one host-agent extraction chunk into graphify-out/graph.json.

    Runs `_merge_docs.py` under graphify's bundled interpreter (it imports
    graphify) with a Gemini-free env. `root` is the source root for path
    relativization (defaults to the chunk's dir; moot for URL-sourced chunks).
    """
    chunk_path = Path(chunk)
    if not chunk_path.is_file():
        print(f"[kb-merge] no such chunk: {chunk}", file=sys.stderr)
        return 2
    out = repo_root / "graphify-out" / "graph.json"
    src_root = root or str(chunk_path.resolve().parent)
    gpy = graphify_python(repo_root)
    cmd = [gpy, str(_MERGE_SCRIPT), str(chunk_path), src_root, str(out)]
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=repo_root, env=clean_env(), check=False).returncode


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

    base = [exe, "label", "."]
    if missing_only:
        base.append("--missing-only")

    def _run(cmd: list[str], why: str) -> int:
        print(f"  $ {' '.join(cmd)}   # {why}")
        return subprocess.run(cmd, cwd=repo_root, env=clean_env(), check=False).returncode

    if not claude_cli:
        # No --backend + GEMINI/GOOGLE stripped -> auto-detect finds nothing ->
        # deterministic hub labeler. The clean default.
        return _run(base, "deterministic no-LLM hub labels (Gemini-free)")

    rc = _run(
        [*base, "--backend=claude-cli", "--max-concurrency=1"],
        "claude-cli backend (opt-in; broken #2076 — expect fallback)",
    )
    if rc == 0:
        return 0
    print(
        "[kb-label] claude-cli backend failed (#2076) — deterministic no-LLM fallback.",
        file=sys.stderr,
    )
    return _run(base, "deterministic fallback")


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
