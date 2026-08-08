# Copyright (c) 2026 Raymond Manaloto
"""This repo's eval cases — tier 1 (reachability) and tier 2 (guard fixtures).

The runner (:mod:`kb_setup.evals`) is shared; the CASES are per-repo, because
what "resolves" means differs. Here it means: the orchestration lanes the
doctrine names are reachable or their degradation is written down, the plugin's
own lane doctor can be reached, and the graph — this repo's entire reason to
exist — actually answers.

Tier 2 asks the next question again: not *does the guard exist* (tier 0's
contract) and not *is it wired* (the settings.json hook), but **does the wired
guard DECIDE correctly?** :data:`GUARD_FIXTURES` is the corpus, and its
must-ALLOW half is not decoration — it found two live false positives in
`kb_setup.hook_guard` on the day it was written (see that module).

Every gated case below carries a ``control``: the same probe logic pointed at
deliberately-broken input, which MUST come back FAIL. The runner refuses to
count a gated case whose control does not fail, so a case added here without a
real control arm turns the run red rather than quietly passing.

Writing those controls is where the work is, and it is worth stating the trap
that shows up immediately: **a control that returns SKIP is not armed.** The
obvious control for the graph canary — point it at a graph path that does not
exist — produces SKIP by design (an absent graph is expected on a fresh clone),
so it proves nothing. The controls below therefore build a real broken fixture
and drive the same code path against it.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from kb_setup import evals, fusion, graph_first, hook_guard, lexical, prose

#: Lane CLIs the routing doctrine names. `grok` is deliberately included and is
#: NOT installed — the doctrine says availability is discovered at run time, so
#: the case asserts the degradation path is DECLARED, not that grok exists.
DECLARED_LANES = ("codex", "agy", "grok")

#: Tokens whose presence constitutes "the degradation path is written down".
FALLBACK_TOKENS = ("fallback", "not installed")

#: The plugin's own lane doctor. Version-pinned inside the plugin cache, so it
#: can vanish on plugin GC — which is why the probe SKIPs loudly rather than
#: silently when it is absent.
DOCTOR_SCRIPT = Path.home().joinpath(
    ".claude/plugins/cache/fable-orchestrator/fable-orchestrator/1.14.0/scripts/doctor.sh"
)

#: A question the corpus must be able to answer at all. Deliberately NOT phrased
#: by echoing node labels — a label-echoing query grades lexical overlap and
#: reports a win that isn't there. This is only a liveness canary; real
#: retrieval quality is tier 2.
CANARY_QUESTION = "how are sources added to this knowledge base?"

_MISSING_BINARY = "definitely-not-a-real-binary-xyz"

_D = evals.GuardFixture
_DENY = evals.Decision.DENY
_ALLOW = evals.Decision.ALLOW

#: The tier-2 corpus for `kb_setup.hook_guard`: every row a real command shape,
#: with the decision it MUST get. Both halves are mandatory (the engine fails a
#: single-direction table), and the control arm runs this same table inverted.
#:
#: The must-ALLOW half is the load-bearing one. `_ALLOWED_READONLY`
#: (path/explain/god-nodes/affected/diagnose) is the surface a careless pattern
#: breaks, and the grep rows below are not hypothetical — both DENIED before the
#: fix that shipped with this table.
GUARD_FIXTURES: tuple[evals.GuardFixture, ...] = (
    # --- must DENY: every mutating / LLM-spending / task-equivalent subcommand
    _D("graphify add https://example.com/a", _DENY, "ingest goes through kb-add"),
    _D("graphify update mysource", _DENY, "re-ingest goes through kb-update"),
    _D('graphify query "how does x work"', _DENY, "retrieval goes through kb-query"),
    _D("graphify extract", _DENY, "extraction goes through kb-build"),
    _D("graphify merge-graphs", _DENY, "merges go through kb-build/kb-merge"),
    _D("graphify label", _DENY, "clustering goes through kb-label"),
    _D("graphify install --project", _DENY, "install mutates config — never by hand"),
    _D("graphify watch", _DENY, "watch is a do-not in this repo"),
    _D("graphify hook install", _DENY, "hook install is a do-not in this repo"),
    _D("graphify frobnicate", _DENY, "an UNKNOWN subcommand denies — the generic arm"),
    _D("cd /tmp && graphify extract", _DENY, "a cd prefix does not launder it"),
    _D("for f in a b; do graphify update $f; done", _DENY, "`do` is a command position"),
    _D("FOO=1 graphify add https://example.com/a", _DENY, "an env prefix does not launder it"),
    _D(
        "python python/src/kb_setup/_merge_docs.py chunk",
        _DENY,
        "the merge helper is kb-merge's job, not a hand-run script",
    ),
    _D(
        "~/.local/share/mise/installs/pipx-graphifyy/0.9.26/bin/python -c 'print(1)'",
        _DENY,
        "graphify's BUNDLED interpreter at command position",
    ),
    _D(
        'python -c "import graphify; print(graphify.__file__)"',
        _DENY,
        "a python head driving graphify — the payload is quoted here, on purpose",
    ),
    # --- must ALLOW: read-only introspection, the canonical tasks, and prose
    _D("graphify path a b", _ALLOW, "_ALLOWED_READONLY — no task equivalent"),
    _D("graphify explain kb_setup", _ALLOW, "_ALLOWED_READONLY — no task equivalent"),
    _D("graphify god-nodes", _ALLOW, "_ALLOWED_READONLY — no task equivalent"),
    _D("graphify affected python/src/kb_setup/evals.py", _ALLOW, "_ALLOWED_READONLY"),
    _D("graphify diagnose", _ALLOW, "_ALLOWED_READONLY"),
    _D(
        "graphify --help",
        _ALLOW,
        "allowed by FALL-THROUGH (the subcommand group needs a letter), not by "
        "_ALLOWED_READONLY — whose --help/-h/--version entries are unreachable",
    ),
    _D('mise run kb-query -- "how are sources added?"', _ALLOW, "the canonical task"),
    _D('mise run kb-query -- "how are sources added?" --prose', _ALLOW, "the prose-scoped form"),
    _D("mise run kb-build", _ALLOW, "the canonical task"),
    _D("mise run kb-prose", _ALLOW, "the canonical task for the derived prose graph"),
    _D(
        'grep -rn "import graphify" python/',
        _ALLOW,
        "FALSE POSITIVE, measured 2026-07-25 — grepping FOR the pattern denied",
    ),
    _D(
        'rg "_merge_docs.py" .',
        _ALLOW,
        "FALSE POSITIVE, measured 2026-07-25 — same shape, same fix",
    ),
    _D('rg "graphify add" docs/', _ALLOW, "a quoted mention is not a command position"),
    _D('echo "do not run graphify add by hand"', _ALLOW, "prose describing the ban"),
    _D(
        'git commit -m "docs: explain why graphify update is denied"',
        _ALLOW,
        "a commit message describing the ban — dotfiles hit exactly this in #176",
    ),
    _D(
        'rg "import graphify" . ; uv run python -c "print(1)"',
        _ALLOW,
        "the python head and the payload are in DIFFERENT segments",
    ),
    _D(
        "python3 -c \"import shutil; print(shutil.disk_usage('/'))\"",
        _DENY,
        "a bare interpreter resolves off $PATH and follows whatever venv is active",
    ),
    _D(
        "uv run python -c \"import shutil; print(shutil.disk_usage('/'))\"",
        _ALLOW,
        "the control arm for the row above — uv run must never be blocked",
    ),
    _D("uv run pytest tests/ -x -q", _ALLOW, "an ordinary uv command is untouched"),
    _D("git status --short", _ALLOW, "an unrelated command is untouched"),
)

#: The tier-2 corpus for `kb_setup.graph_first` (#253), graded against the REAL
#: repo root, so `python/` is a directory and `hook_guard.py` is a file because
#: they are — a guard that consults the filesystem should be graded on one.
#:
#: The must-ALLOW half is again the load-bearing one, and it is longer than the
#: deny half on purpose. This guard's failure mode is not a missed search; it is
#: blocking a targeted read, a log grep, or a `kb-query | rg` pipe — the last of
#: which would punish the exact habit the guard exists to encourage.
GRAPH_FIRST_FIXTURES: tuple[evals.GuardFixture, ...] = (
    # --- must DENY: orientation over the tree, which is the graph's job
    _D('rg "decide" .', _DENY, "a repo-wide search is orientation"),
    _D("rg decide", _DENY, "rg with no path is repo-wide by default"),
    _D('rg "hook_guard" python/', _DENY, "a source directory is a tree walk"),
    _D('grep -rn "hook_guard" python/', _DENY, "recursive grep over source"),
    _D("git grep decide", _DENY, "git grep walks the worktree with no -r"),
    _D('ls -la && rg "decide" python/', _DENY, "a later segment still counts"),
    _D(
        "rg --sort path decide",
        _DENY,
        "P1, cold lane: an unlisted value-flag made a repo-wide search look targeted",
    ),
    _D(
        "rg -g '!*.md' decide .",
        _DENY,
        "P1, cold lane: a NEGATED glob reaches every source file",
    ),
    # --- must ALLOW: everything that is not orientation
    _D(
        'rg "decide" python/src/kb_setup/hook_guard.py',
        _ALLOW,
        "ONE file is targeted work — Ray's scope, and the control for every deny above",
    ),
    _D(
        'grep -n "decide" python/src/kb_setup/hook_guard.py',
        _ALLOW,
        "a non-recursive grep of one file was never a tree walk",
    ),
    _D('rg "TODO" docs/', _ALLOW, "prose is not the source the graph indexes"),
    _D('rg "rc=" /tmp/out.log', _ALLOW, "a log grep is reading evidence in hand"),
    _D('rg "handoff" .agent/plans/', _ALLOW, "a dotted prose root is still prose"),
    _D('rg "TODO" -g "*.md" .', _ALLOW, "a restriction that cannot reach source"),
    _D(
        'mise run kb-query -- "how does X work" | rg decide',
        _ALLOW,
        "a PIPE searches bytes already in hand; denying it punishes the right habit",
    ),
    _D(
        'echo "run rg decide python/ to find it"',
        _ALLOW,
        "text ABOUT a search — the direction every measured guard defect came from",
    ),
    _D(
        'git commit -m "docs && rg decide"',
        _ALLOW,
        "P2, cold lane: a regex cannot see quoting, so a commit read as a search",
    ),
    _D(
        "rg -e decide python/src/kb_setup/hook_guard.py",
        _ALLOW,
        "P2, cold lane: `-e` ate the pattern, so the real file was dropped as one",
    ),
    _D("ls -la", _ALLOW, "an unrelated command is untouched"),
)


_NATURAL = evals.Phrasing.NATURAL
_ECHO = evals.Phrasing.ECHO
_ABSENT = evals.Phrasing.ABSENT
_G = evals.GoldenQuery

#: How far down the returned list a hit counts. `graphify query` prints roughly
#: 20-60 nodes under its token budget and applies NO relevance score — the
#: printed order is seed-then-BFS — so this window grades what a reader actually
#: sees first, which is the thing KB #12 is about.
GOLDEN_K = 10

#: A source declared absent that is one character-class away from a source that
#: IS present (`cerebras-knowledge-base.md`). The negative direction has to be
#: able to FAIL, and the realistic way it would is a sloppy matcher — a
#: substring or `endswith` comparison — quietly counting the real document as a
#: hit for this name.
NEAR_MISS_TARGET = "cerebras-knowledge-base-v2.md"

#: The golden retrieval set — 8 hand-written PAIRS plus both negatives.
#:
#: HAND-WRITTEN, not derived from the nodes under test. Generating queries by
#: paraphrasing the target labels grades paraphrase distance and reports a win
#: that is not there (`tests/AGENTS.md`, and measured here 2026-07-24). Each
#: NATURAL query is phrased the way someone who has NOT read the document would
#: ask; its ECHO twin deliberately borrows the document's own label text. THE
#: GAP BETWEEN THE TWO IS THE FINDING.
#:
#: GATED since P2, at :data:`RETRIEVAL_FLOOR` — but only on an explicit `--slow`
#: run, which `kb-ship` does not pass, so ship does NOT check retrieval. It was
#: advisory until P0-P2 moved the number: the baseline this exists to make citable
#: is 0/119 relevant nodes on two on-topic queries (knowledge-base#12), and a
#: floor at or below zero is the check that can only pass.
GOLDEN_QUERIES: tuple[evals.GoldenQuery, ...] = (
    _G(
        "hooks-blocking",
        _NATURAL,
        "if a script needs to stop a tool call from running, what should it exit "
        "with and where does its message end up?",
        ("code.claude.com_docs_en_hooks.md",),
        GOLDEN_K,
    ),
    _G(
        "hooks-blocking",
        _ECHO,
        "hook exit codes: 2 is a blocking error whose stderr is fed back to Claude",
        ("code.claude.com_docs_en_hooks.md",),
        GOLDEN_K,
    ),
    _G(
        "model-vs-effort",
        _NATURAL,
        "is it better to move up to a stronger model, or to make the one I have think harder?",
        ("platform.claude.com_docs_en_about-claude_models_choosing-a-model.md",),
        GOLDEN_K,
    ),
    _G(
        "model-vs-effort",
        _ECHO,
        "the effort parameter trades intelligence for latency and cost within a "
        "single model, and xhigh is the best setting for coding",
        ("platform.claude.com_docs_en_about-claude_models_choosing-a-model.md",),
        GOLDEN_K,
    ),
    _G(
        "unattended-work",
        _NATURAL,
        "what has to be in place before I can leave something working on its own "
        "for days without watching it?",
        ("www_anthropic_com_research_long-running-Claude.md",),
        GOLDEN_K,
    ),
    _G(
        "unattended-work",
        _ECHO,
        "long-running autonomous work depends on a test oracle and a progress "
        "file as portable long-term memory across sessions",
        ("www_anthropic_com_research_long-running-Claude.md",),
        GOLDEN_K,
    ),
    _G(
        "beyond-similarity",
        _NATURAL,
        "why is comparing meaning alone not enough to find the right passage, and "
        "what do people add on top of it?",
        ("cerebras-knowledge-base.md",),
        GOLDEN_K,
    ),
    _G(
        "beyond-similarity",
        _ECHO,
        "four-scorer hybrid retrieval with reciprocal rank fusion and contextual "
        "retrieval by prepending the thread topic",
        ("cerebras-knowledge-base.md",),
        GOLDEN_K,
    ),
    _G(
        "delegate-unavailable",
        _NATURAL,
        "what is supposed to happen when the cheaper command-line tool I hand "
        "work to turns out not to be installed?",
        ("fable-orchestrator.md",),
        GOLDEN_K,
    ),
    _G(
        "delegate-unavailable",
        _ECHO,
        "the lane fallback chain and announced substitution, with Claude Opus as "
        "the terminal fallback",
        ("fable-orchestrator.md",),
        GOLDEN_K,
    ),
    _G(
        "repeated-corrections",
        _NATURAL,
        "how do I stop having to make the same small corrections after every "
        "change that gets written for me?",
        ("claude_com_blog_building-verification-loops-in-claude-code-with-skills.md",),
        GOLDEN_K,
    ),
    _G(
        "repeated-corrections",
        _ECHO,
        "encode the repeated manual checks you already run as a skill so the "
        "agent closes its own verification feedback loop",
        ("claude_com_blog_building-verification-loops-in-claude-code-with-skills.md",),
        GOLDEN_K,
    ),
    _G(
        "many-agents-one-repo",
        _NATURAL,
        "can a lot of helpers sweep an entire repository at once, and how do I "
        "avoid having to take each of their claims on faith?",
        ("claude_com_blog_introducing-dynamic-workflows-in-claude-code.md",),
        GOLDEN_K,
    ),
    _G(
        "many-agents-one-repo",
        _ECHO,
        "dynamic workflows fan out parallel subagents with a convergence loop and "
        "independent per-finding verification",
        ("claude_com_blog_introducing-dynamic-workflows-in-claude-code.md",),
        GOLDEN_K,
    ),
    _G(
        "capability-not-loading",
        _NATURAL,
        "the packaged capability I wrote is never picked up when I run the SDK — "
        "what decides whether it gets loaded?",
        ("code.claude.com_docs_en_agent-sdk_skills.md",),
        GOLDEN_K,
    ),
    _G(
        "capability-not-loading",
        _ECHO,
        "skills are filesystem SKILL.md artifacts discovered at startup and loaded "
        "when setting_sources includes user or project",
        ("code.claude.com_docs_en_agent-sdk_skills.md",),
        GOLDEN_K,
    ),
    # --- the negative direction: relevant nodes ABSENT must come back absent
    _G(
        "absent-off-topic",
        _ABSENT,
        "how do I tune the JVM garbage collector to cut tail latency in a "
        "low-latency trading system?",
        ("jvm-garbage-collection-tuning-guide.md",),
        GOLDEN_K,
    ),
    _G(
        "absent-near-miss",
        _ABSENT,
        "why is comparing meaning alone not enough to find the right passage, and "
        "what do people add on top of it?",
        (NEAR_MISS_TARGET,),
        GOLDEN_K,
    ),
)

#: `NODE <label> [src=<source> loc=<L..> community=<name>]` — `graphify query`'s
#: line format. The label may itself contain brackets, so the source is taken
#: from the LAST `[src=` on the line.
_NODE_LINE = re.compile(r"^NODE .*\[src=(?P<src>.*?) loc=")

#: A retrieval query reloads the whole ~350 MB graph, measured at ~10s each. The
#: 60s default is for reachability probes; this needs its own headroom without
#: being unbounded.
RETRIEVAL_TIMEOUT = 180


def _graph_path(repo_root: Path) -> Path:
    return repo_root / "graphify-out" / "graph.json"


#: The four retrieval configurations the golden set is measured against, in
#: report order. Each is the previous one plus ONE change, so every arm's own
#: contribution is the delta from its predecessor (knowledge-base#12):
#:
#: * `unscoped` — the baseline: `graphify query` over the whole graph.
#: * `prose` — P0: the same retriever over the AST-free corpus. Scoping only.
#: * `prose+idf` — P1: the same corpus, ranked by our BM25/IDF scorer instead of
#:   graphify's unscored seed-then-BFS order. Scoring only.
#: * `prose+rrf` — P2: reciprocal rank fusion of the two orderings above.
#:   Fusion only.
#:
#: THE LAST ARM IS NOT THE BEST ARM, and it is kept anyway. `prose+rrf` scores
#: BELOW `prose+idf` (4 of 8 natural pairs against 5), for a structural reason
#: `kb_setup.fusion` documents in full. It stays in the report because the arm IS
#: the evidence: a negative result that lives only in an issue comment stops
#: being re-derived, and this one bounds where the next gain can come from —
#: fusion needs a genuine second scorer (P3/P5), not a tuned weight.
UNSCOPED_ARM = "unscoped"
PROSE_ARM = "prose"
IDF_ARM = "prose+idf"
RRF_ARM = "prose+rrf"

#: Minimum natural-phrasing pairs the BEST arm must score for the case to stay
#: green. Locked with Ray 2026-07-27 at ONE BELOW the measured 5, on purpose: it
#: guards regression rather than asserting aspiration, and leaves enough headroom
#: that a corpus rebuild moving a single topic does not redden the run for a
#: reason unrelated to the code. Pairs and not mean recall, because pairs is the
#: unit every comment on knowledge-base#12 reports in — so the gate and the
#: thread stay comparable.
RETRIEVAL_FLOOR = 4


def _retrieval(repo_root: Path, graph: Path) -> evals.Retrieve:
    """Bind the retriever to ONE graph, and return it.

    Shells out to `graphify query` exactly as the tier-1 canary does, rather
    than reimplementing traversal: what is being measured is the retrieval a
    session actually gets, and anything else would measure a different program.

    DELIBERATELY a bare ``"graphify"``, NOT
    :func:`kb_setup.graphify_env.graphify_exe`. Every operational call site moved
    to that resolver (#40) so corpus correctness stops depending on PATH order —
    this one must not follow, and the difference is the point. `graphify_exe`
    answers "the binary the pin names"; this case asks "the binary a session
    actually runs". Pinning here would quietly convert an ecological measurement
    into a hypothetical one, and would mask exactly the drift the eval exists to
    expose. Falsifiability is preserved instead by :func:`_corpus_stamp`, which
    records the version that ACTUALLY RAN alongside every number. When the
    environment is honest the two coincide — and `mise run cc-doctor` is what
    says whether it is.

    PINNED with an explicit ``--graph``, not left to resolve against the process
    cwd (caught in review of PR #30). That was already load-bearing with one
    corpus; with two it is the entire experiment — an unpinned query would
    answer from whichever graph the cwd happens to hold and both arms would
    report the same number.
    """

    def retrieve(query: evals.GoldenQuery) -> tuple[int, list[str]]:
        rc, out = evals.run_command(
            ["graphify", "query", query.query, "--graph", str(graph)],
            cwd=repo_root,
            timeout=RETRIEVAL_TIMEOUT,
        )
        if rc != 0:
            return rc, []
        return rc, [m.group("src") for line in out.splitlines() if (m := _NODE_LINE.match(line))]

    return retrieve


def _node_count(graph: Path, repo_root: Path) -> str:
    """``N nodes`` for one graph, via graphify's own read-only `diagnose`.

    `diagnose` is authoritative and costs ~15s on the full graph; parsing the
    graph here would cost gigabytes of resident memory for one integer.
    """
    rc, out = evals.run_command(
        ["graphify", "diagnose", "multigraph", "--json", "--graph", str(graph)],
        cwd=repo_root,
        timeout=RETRIEVAL_TIMEOUT,
    )
    if rc != 0:
        return f"node count UNAVAILABLE (diagnose rc={rc})"
    try:
        return f"{json.loads(out)['summary']['node_count']:,} nodes"
    except (ValueError, KeyError, TypeError) as exc:
        return f"node count UNPARSABLE ({type(exc).__name__})"


def _corpus_stamp(repo_root: Path) -> str:
    """Build date + node count + graphify version, for EVERY graph being measured.

    Mandatory, not decoration. This case runs against the live local graphs, so
    its numbers move when they are rebuilt or the tool is bumped; a figure
    repeated without the corpus it came from is not a measurement
    (`probes-need-a-control-arm.md` rule 6). Both arms are stamped, because the
    delta between them is only meaningful if the prose graph was derived from
    the graph the baseline arm queried — and a stale one is invisible otherwise.
    """
    version_rc, version_out = evals.run_command(["graphify", "--version"], timeout=30)
    version = version_out.strip() if version_rc == 0 else f"graphify version rc={version_rc}"
    stamps = [
        f"{name} {_node_count(path, repo_root)}, built {_built(path)}"
        for name, path in (
            (UNSCOPED_ARM, _graph_path(repo_root)),
            (PROSE_ARM, prose.prose_graph_path(repo_root)),
        )
    ]
    return f"{'; '.join(stamps)}; {version}"


def _built(graph: Path) -> str:
    """The graph file's mtime as a date — when this corpus was written."""
    return dt.datetime.fromtimestamp(graph.stat().st_mtime, tz=dt.UTC).date().isoformat()


def _corpus_membership(graph: Path) -> evals.Membership:
    """Bind the fixture-integrity oracle to ONE graph.

    Per-arm, not per-run: a target that survives into the prose graph and one
    that does not are different facts, and a positive target dropped by the
    scoping filter would otherwise report recall 0 forever and read as a
    retrieval failure rather than as the fixture rot it is.
    """

    def present(names: Sequence[str]) -> Mapping[str, bool]:
        return evals.corpus_has(graph, names)

    return present


class _LexicalRetriever:
    """The P1 arm's retriever: our BM25/IDF scorer, in-process, over one graph.

    A callable object rather than a closure because the index must be built ONCE
    and reused across the golden set's 18 queries — rebuilt per query, the arm's
    wall clock would be a measurement of JSON parsing rather than of retrieval.
    It is built lazily, on the first query, so constructing the arm list stays
    free: `cases()` runs before the precondition that checks the graph exists.

    RETURNS A REAL ``rc``, never a hardcoded 0. This is the first arm whose
    retriever does not shell out, so `evals._arm_defect`'s ``rc != 0`` check has
    no subprocess to inherit an exit code from — and a check that cannot fire is
    not a check. The failure it reports is genuinely reachable: a graph file that
    is absent, unreadable, malformed JSON, or that yields an empty index all end
    here as ``rc=2`` with the arm's rows empty, which the engine then reports as
    a defect instead of as recall 0.
    """

    #: `rc` for "this arm could not read its corpus". Mirrors the CLI's
    #: convention, where 2 is a precondition/usage failure rather than a crash.
    UNREADABLE = 2

    def __init__(self, graph: Path) -> None:
        self._graph = graph
        self._index: lexical.Index | None = None
        self._broken = False

    def __call__(self, query: evals.GoldenQuery) -> tuple[int, list[str]]:
        """Rank this arm's corpus against one golden query."""
        if self._index is None and not self._broken:
            try:
                self._index = lexical.load_index(self._graph)
            # JSONDecodeError is a ValueError subclass, so it needs no arm of
            # its own. The unparenthesised form is valid here (PEP 758, py3.14)
            # and is what ruff normalises to; parens are only REQUIRED with `as`.
            except OSError, ValueError:
                self._broken = True
        if self._index is None:
            return self.UNREADABLE, []
        return 0, [hit.source_file for hit in lexical.search(self._index, query.query)]


class _FusedRetriever:
    """The P2 arm's retriever: RRF over the two orderings its inputs produce.

    Fuses whatever its input retrievers return, by rank alone — `graphify query`
    publishes no relevance figure, so one input is a bare order while the other
    carries BM25 scores, and RRF is the instrument that combines exactly that
    asymmetry (`kb_setup.fusion`).

    RETURNS A REAL ``rc``, inherited from whichever input failed FIRST, and
    returns no rows when it does. Fusing a healthy ranking with an empty one
    would otherwise print a plausible fused list built from half the evidence —
    a defective arm reporting a recall number instead of a defect, which is what
    `evals._arm_defect` exists to prevent.
    """

    def __init__(self, retrievers: Sequence[evals.Retrieve]) -> None:
        self._retrievers = tuple(retrievers)

    def __call__(self, query: evals.GoldenQuery) -> tuple[int, list[str]]:
        """Rank this arm's corpus by fusing every input retriever's order."""
        rankings = []
        for retrieve in self._retrievers:
            rc, returned = retrieve(query)
            if rc != 0:
                return rc, []
            rankings.append(list(returned))
        return 0, fusion.fuse(rankings)


def _retrieval_arms(repo_root: Path) -> tuple[evals.Arm, ...]:
    """The four arms — baseline, P0 scoping, P1 scoring, P2 fusion — one golden set.

    The membership oracle is per-arm (see :func:`_corpus_membership`). The three
    prose arms share a FILE but not an oracle instance, which is deliberate: they
    are separate arms, and a future change giving one of them its own corpus must
    not silently inherit another's fixture verdict.

    The P2 arm builds its OWN `_LexicalRetriever` rather than reusing the P1
    arm's, for the same reason and at the cost of one 2.4 MB JSON parse: sharing
    the object would make one arm's numbers depend on another arm's state.
    """
    prose_graph = prose.prose_graph_path(repo_root)
    return (
        evals.Arm(
            UNSCOPED_ARM,
            _retrieval(repo_root, _graph_path(repo_root)),
            present=_corpus_membership(_graph_path(repo_root)),
        ),
        evals.Arm(
            PROSE_ARM,
            _retrieval(repo_root, prose_graph),
            present=_corpus_membership(prose_graph),
        ),
        evals.Arm(
            IDF_ARM,
            _LexicalRetriever(prose_graph),
            present=_corpus_membership(prose_graph),
        ),
        evals.Arm(
            RRF_ARM,
            _FusedRetriever((_retrieval(repo_root, prose_graph), _LexicalRetriever(prose_graph))),
            present=_corpus_membership(prose_graph),
        ),
    )


def _broken_retrieval() -> evals.Outcome:
    """Control arm: the same scorer, driven by a retriever that returns the absent target.

    Now REQUIRED, since the case is gated (P2) — the runner refuses to count a
    gated case whose control does not fail. The failure it arms is the whole
    reason the negative direction exists: a matcher that reports a hit for a
    document the corpus does not contain. It runs offline in microseconds,
    against a miniature golden set of the same shape rather than the real one.

    IT ARMS THE LEAK AND NOT THE FLOOR, deliberately. A control can only
    demonstrate one failure, and the leak is the one that would otherwise print a
    false WIN; the floor's failure direction is trivially reachable and is
    control-armed in both directions by unit test instead
    (`tests/test_evals.py`). No ``floor`` is passed here for a second reason —
    this miniature set has ONE positive pair, so any floor above 1 would be
    rejected as unreachable and the control would then fail for a reason that has
    nothing to do with the defect it exists to catch.

    TWO arms, matching the probe's shape: the defect has to be caught in the
    SECOND arm as well, or a broken scoped corpus could hide behind the
    baseline's numbers. The leak is placed in the second arm for exactly that
    reason — a one-armed control would pass a scorer that only ever checks the
    first.
    """
    queries = (
        _G("t", _NATURAL, "q", ("present.md",), 5),
        _G("t", _ECHO, "q", ("present.md",), 5),
        _G("absent", _ABSENT, "q", ("absent.md",), 5),
    )
    return evals.retrieval_recall(
        queries,
        (
            evals.Arm(UNSCOPED_ARM, lambda _q: (0, ["present.md"])),
            evals.Arm(PROSE_ARM, lambda _q: (0, ["present.md", "absent.md"])),
        ),
        stamp="synthetic control-arm corpus",
    )


def _broken_graph_canary() -> evals.Outcome:
    """Control arm: drive the canary against a graph that cannot answer.

    A directory holding a syntactically-present but meaningless ``graph.json``
    passes the existence gate (so this is not a SKIP) and then makes the real
    ``graphify query`` fail — which is the FAIL branch the canary must be shown
    to be able to reach.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        graph = root / "graphify-out" / "graph.json"
        graph.parent.mkdir(parents=True)
        graph.write_text("not a graph")
        return evals.graphify_canary(root, CANARY_QUESTION, timeout=30)


def _broken_doctor() -> evals.Outcome:
    """Control arm: a doctor script that reports a failing lane.

    Distinct from the absent-script case on purpose. "We could not look" (SKIP)
    and "we looked and a lane is broken" (FAIL) must never collapse into each
    other, so the control exercises the second.
    """
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "doctor.sh"
        script.write_text("#!/usr/bin/env bash\necho '0 ok, 0 warnings, 1 failures'\nexit 1\n")
        return evals.doctor_health(script, timeout=30)


#: Name of the short redacted value :func:`_redaction_collision_control` plants.
#: The control's FAIL detail must NAME it, which is what proves the canary loaded
#: rather than the arm having tripped over some short host secret.
REDACTION_CANARY = "_EVAL_REDACTION_CANARY"


def _redaction_collision_control() -> evals.Outcome:
    """The real reader, pointed at a config that DOES collide.

    Not a stubbed value list: this writes a throwaway ``mise.toml`` declaring a
    one-character redacted value and runs the same ``mise env --redacted`` the
    probe runs, so the read, the parse and the judgement are all exercised. It is
    the hand-probe that established this round's cause, promoted into the harness.

    The user-level config is still in scope inside the temp directory, so its real
    secrets are read too, and the canary is simply the shortest value present.
    That means the arm works both here and on a host holding no redacted values —
    but it also means a FAIL alone does not prove the canary LOADED, since a short
    host secret would produce one too. The probe therefore names the offending
    variables, and :data:`REDACTION_CANARY` is asserted in the test. Raised by the
    silent-failure lane: without it, a canary that quietly stopped loading on an
    all-long host set returns PASS, and PASS from a control means NOT ARMED.
    """
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "mise.toml").write_text(
            f'[env]\n{REDACTION_CANARY} = {{ value = "1", redact = true }}\n'
        )
        return evals.mise_redaction_legible(cwd=Path(tmp))


def _binary_gate(name: str, detail: str) -> evals.Outcome | None:
    """SKIP when ``name`` does not resolve on PATH; otherwise run normally.

    Environment gates belong here rather than inside a probe: the control arm
    drives the same code path, so an in-probe skip would skip the control too and
    leave the case UNARMED — a case reported as decoration for a question that
    was never asked. ``detail`` is per-tool because the REASON differs, and
    collapsing two different "does not apply here" reasons into one message is
    the same mistake one level down.
    """
    if shutil.which(name) is None:
        return evals.skip(detail)
    return None


def _mise_installed() -> evals.Outcome | None:
    """Environment gate: nothing to say about mise's redaction set without mise."""
    return _binary_gate("mise", "mise does not resolve on PATH — its redaction set cannot be read")


def _graphify_installed() -> evals.Outcome | None:
    """Environment gate: the canary cannot run where graphify is not installed.

    graphify is host-only in the sibling dotfiles repo, so inside its
    devcontainer this case asserts something that cannot be true. That is "does
    not apply here", not "the graph is broken".
    """
    return _binary_gate(
        "graphify",
        "graphify is not installed in this environment (it is host-only in "
        "the consuming repo) — the canary cannot look, which is not the same "
        "as the graph having nothing to say",
    )


def _retrieval_precondition(repo_root: Path) -> evals.Outcome | None:
    """Environment gate: needs the CLI and BOTH graphs to measure anything.

    The graphs are gitignored and derived, so their absence on a fresh clone is
    expected. Same reasoning as :func:`_graphify_installed`: this belongs in a
    precondition rather than inside the probe, because "we could not look" and
    "retrieval found nothing" are different answers and collapsing them is the
    defect this whole harness exists to catch.

    A missing prose graph skips the WHOLE case rather than quietly dropping its
    arm. Dropping it would print the baseline's numbers under a report that
    still claims to be a before/after — a comparison silently reduced to one
    side, which reads as "scoping changed nothing".
    """
    installed = _graphify_installed()
    if installed is not None:
        return installed
    for graph, task in (
        (_graph_path(repo_root), "kb-build"),
        (prose.prose_graph_path(repo_root), "kb-prose"),
    ):
        if not graph.is_file():
            return evals.skip(f"no graph at {graph} — run `mise run {task}` first")
    return None


def cases(repo_root: Path, *, doctor_script: Path | None = None) -> list[evals.Case]:
    """Build this repo's tier-1 cases."""
    doctor = doctor_script if doctor_script is not None else DOCTOR_SCRIPT
    fallback_doc = repo_root / ".claude" / "CLAUDE.md"

    return [
        evals.Case(
            name="tier1.lanes-declared-or-degraded",
            description=(
                "every lane the doctrine names either resolves on PATH, or its "
                "degradation path is written down"
            ),
            probe=lambda: evals.declared_lanes_reconcile(
                DECLARED_LANES,
                fallback_doc=fallback_doc,
                fallback_tokens=FALLBACK_TOKENS,
            ),
            # Same logic with the fallback doc pointed at a file that does not
            # exist: "we cannot read the fallback" must never read as "declared".
            control=lambda: evals.declared_lanes_reconcile(
                (_MISSING_BINARY,),
                fallback_doc=repo_root / ".claude" / "does-not-exist.md",
                fallback_tokens=FALLBACK_TOKENS,
            ),
        ),
        evals.Case(
            name="tier1.graphify-resolves",
            description="the graphify CLI this repo drives resolves on PATH",
            probe=lambda: evals.cli_present("graphify"),
            control=lambda: evals.cli_present(_MISSING_BINARY),
        ),
        evals.Case(
            name="tier1.graph-answers",
            description=(
                "the graph does not merely exist — it returns a non-empty answer "
                "(rc=0 with empty output is a corpus that reads as healthy and "
                "knows nothing)"
            ),
            probe=lambda: evals.graphify_canary(repo_root, CANARY_QUESTION),
            control=_broken_graph_canary,
            precondition=_graphify_installed,
        ),
        evals.Case(
            name="tier1.mise-redaction-legible",
            description=(
                "no value in mise's redaction set is short enough to collide "
                "with ordinary output — a redacted `1` rewrites every digit a "
                "task prints, which makes every gate figure unreadable evidence"
            ),
            probe=lambda: evals.mise_redaction_legible(cwd=repo_root),
            control=_redaction_collision_control,
            precondition=_mise_installed,
            # ADVISORY, and this is the one judgement call in the case: the remedy
            # is never in this repo (the set is populated by `_.fnox-env` in the
            # USER-level mise config, which `do-not.md` #11 forbids touching), so
            # gating it would be a ship blocker no agent could clear. `render`
            # surfaces an advisory FAIL, and a dead advisory control arm,
            # explicitly rather than folding either into the green summary line.
            # THE FULL REASONING LIVES IN ONE PLACE — `mise.toml` `[tasks.eval]`.
            # It was restated in four (here, that comment, the probe docstring,
            # and a test name) until the standards lane counted them.
            gated=False,
        ),
        evals.Case(
            name="tier1.lane-health",
            description=(
                "the plugin's own doctor.sh reports every installed lane "
                "authenticated with model access"
            ),
            probe=lambda: evals.doctor_health(doctor),
            control=_broken_doctor,
            # doctor.sh has NO offline mode: whenever a lane's CLI is present it
            # fires a real API call. So this is the live half, entirely, and can
            # never join the free gated tier — it runs only under --live.
            live=True,
        ),
        evals.Case(
            name="tier2.kb-retrieval",
            description=(
                "golden retrieval set: recall@k for 8 hand-written query pairs "
                "(natural vs label-echoing) plus both negative directions, "
                "measured against the live local graph — unscoped, prose-scoped, "
                "IDF-ranked and RRF-fused side by side"
            ),
            probe=lambda: evals.retrieval_recall(
                GOLDEN_QUERIES,
                _retrieval_arms(repo_root),
                stamp=_corpus_stamp(repo_root),
                floor=RETRIEVAL_FLOOR,
            ),
            control=_broken_retrieval,
            # GATED since P2 (2026-07-27). It was advisory from PR #30 through P1
            # because the baseline it exists to make citable is 0/119 relevant
            # nodes (knowledge-base#12) and a floor at or below zero is the check
            # that can only pass; P0-P2 moved the number far enough for
            # RETRIEVAL_FLOOR to mean something. Besides the floor it fails on a
            # broken query path, a silent graph, fixture rot, or the negative
            # direction coming back positive — harness defects, not recall.
            #
            # BUT READ THIS BEFORE TRUSTING THE GATE: it bites only on an
            # explicit `--slow` run. `kb-ship`'s eval gate does not pass --slow,
            # so this case is SKIPPED on every PR (its logs read `4 passed, 2
            # skipped`) and SHIP DOES NOT CHECK RETRIEVAL. Gating alone changed
            # nothing on the ship path. That is accepted — the slow arm reloads a
            # ~350 MB graph 18 times for ~4 minutes, and a gate that slow is one
            # people route around — on the condition that it is stated wherever
            # the floor is described, which is what this paragraph is for. A
            # floor everyone believes is enforced per-PR and is not would be
            # exactly the inert declaration dotfiles#354 exists to catch; this
            # one is inert BY DESIGN, so it says so.
            gated=True,
            # 18 queries per arm plus a `diagnose` per corpus: ~4 minutes,
            # essentially all of it the unscoped arm (each of its queries
            # reloads a ~350 MB graph at ~10s; the 2.4 MB prose graph answers in
            # ~0.3s, and the fused arm pays a second pass over it).
            slow=True,
            precondition=lambda: _retrieval_precondition(repo_root),
        ),
        evals.guard_table_case(
            "tier2.guard-fixtures",
            "the PreToolUse graphify guard decides every fixture row as declared "
            "— both directions, since false positives are the only defect class "
            "ever measured in it",
            GUARD_FIXTURES,
            hook_guard.decide,
        ),
        evals.guard_table_case(
            "tier2.graph-first-fixtures",
            "the PreToolUse graph-first guard denies a BROAD source search before "
            "any graph query, and never a targeted, prose or piped one (#253)",
            GRAPH_FIRST_FIXTURES,
            lambda command: graph_first.decide(
                "Bash", {"command": command}, repo_root, queried=False
            ),
        ),
    ]
