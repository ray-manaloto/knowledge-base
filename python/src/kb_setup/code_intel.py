# Copyright (c) 2026 Raymond Manaloto
"""Provenance-tagged code-intelligence edges — issue #276.

This repo's knowledge graph indexes **Python AST only**. It has no nodes for
mise tasks, skills, or config files, so "what task reaches this function?"
goes unanswered and the entry-point diagram Ray keeps asking for has to be
hand-drawn and goes stale.

This module emits a provenance-tagged edge set joining four DETERMINISTIC
layers to the Python code — promoting the measured spike at
`docs/research/prototypes/diagram-bake-off/emit.py` (a declared spike, read
for reference; its four extractor functions are the starting point, not code
moved verbatim):

    SKILL.md fence  --("invokes")--------> mise task
    mise task       --("invokes")--------> cli.py dispatch arm
    dispatch arm    --("dispatches_to")--> the function it calls
    that function   --("reads")----------> the config file it opens

Every edge carries a `Provenance` tag and a `verified` bit — issue #276's
own requirement: *"Unverified LSP edges must not silently enter the
canonical Graphify graph."* An untagged edge set merged into a 736 MiB
aggregate graph is unreviewable and effectively irreversible, so provenance
is not a nice-to-have here — it is why this change is safe to make at all.

The four lanes below (`task_edges`/`skill_edges`/`dispatch_edges`/
`config_edges`) are all static reads — `mise tasks --json`, AST, and a
regex-over-fences already owned by `skill_lint` — and are `verified=True` by
construction: nothing in the read path can be wrong about what the source
literally says. A fifth lane, `TY_LSP`, is designed for and STUBBED: it
always returns `[]`, pending the backend decision from issue #276's Serena
evaluation (see `ty_edges`'s own docstring). Do not build it here.

**Scope: emit a chunk, never merge one.** `to_chunk` produces the
chunk-schema dict `mise run kb-merge` would accept; writing it anywhere
under `graphify-out/` is a separate, later step this module does not take.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from kb_setup import skill_lint

# Reused, not retyped: `chunks.py` OWNS the chunk schema (`kb-assemble` /
# `kb-validate-chunks` / `kb-merge` all import it). Importing the two
# required-field tuples means a future schema change that `to_chunk` hasn't
# been updated for fails LOUD (`_schema_dict` below raises) instead of
# quietly emitting an invalid chunk — the "a generated table drifts from its
# generator" failure this repo already has a name for.
from kb_setup.chunks import _EDGE_REQUIRED, _NODE_REQUIRED
from kb_setup.result import Rc

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Callable, Sequence

Provenance = Literal["MISE_TASK", "SKILL_FENCE", "CLI_DISPATCH", "CONFIG_READ", "TY_LSP"]


@dataclass(frozen=True)
class Edge:
    """One provenance-tagged edge between two namespaced node ids.

    ``source``/``target`` are namespaced by kind (``task:``, ``skill:``,
    ``cli:``, ``fn:``, ``config:``, ``cmd:``) so two layers never collide on a
    bare name — a mise task literally called ``build`` and a function
    literally called ``build`` become ``task:build`` and ``fn:build``, never
    the same string.

    ``verified=False`` marks an edge a lane could not confirm. `to_chunk`
    must round-trip it — represent it, never drop it, never silently promote
    it to look confirmed (issue #276's whole point).
    """

    source: str
    target: str
    relation: str  # "invokes" | "dispatches_to" | "reads"
    provenance: Provenance
    verified: bool
    evidence: str  # "path/to/file.py:LINE", or the command that produced it


def _repo_src(repo_root: Path) -> Path:
    return repo_root / "python" / "src"


def _relpath(repo_root: Path, path: Path) -> str:
    """Repo-relative POSIX evidence path — never absolute.

    The `E` premise on `Edge.evidence` allows an absolute path but asks that
    evidence stay repo-relative; this is the one place every lane below
    builds an `evidence` string, so it is the one place that has to hold.
    """
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


class LaneUnavailableError(Exception):
    """A lane could not be RUN at all — its file, function, or tool is missing.

    Distinct from a lane that ran and legitimately found zero edges (the
    STUBBED `ty` lane, e.g.): `.claude/rules/probes-need-a-control-arm.md`
    treats "could not check" as a THIRD state, never collapsed into "checked,
    found nothing". `funnel.py` makes the identical distinction over the
    identical kind of value (a list of edges) by returning `None` for "git
    could not be read" and `()` for "read, and there is nothing here"
    (`funnel.py:160-162`) — but a lane function here has a fixed
    `(Path) -> list[Edge]` shape (this module's own spec §3), so there is no
    third return value available to reuse that trick with. RAISING is the
    equivalent move for that shape: a caller cannot forget to check a
    `return None` it never received, and `run_lanes`/`code_intel_main` are
    the ONE place that converts this into a worded refusal and `Rc.NOT_RUN` —
    nothing between a `raise` here and that boundary is expected to catch it.
    """


# ---------------------------------------------------------------------------
# Lane 1: MISE_TASK — `mise tasks --json`
# ---------------------------------------------------------------------------

#: Matches the shape nearly every task in this repo's `run` line takes:
#: `uv run kb-setup <cmd> [...args]`. A match lets `task_edges` point straight
#: at the SAME `cli:<cmd>` id `dispatch_edges` emits as its OWN source, so the
#: two lanes chain into one traversable path instead of two disjoint islands.
_TASK_CLI_RE = re.compile(r"^uv run kb-setup (\S+)")

#: Mirrors `funnel._GIT_TIMEOUT`'s intent: this is a cheap metadata read about
#: this repo's OWN tasks, and a wedged one must not become the reason this
#: lane never reports (`.claude/rules/long-running-command-hangs.md` — a
#: mise-family command once wedged for ~7 hours with no timeout to abort it).
#: NOT imported from `funnel` — that name is private to its module, and the
#: SLF001 grant in `pyproject.toml` is scoped to `graph_size.py`'s one
#: documented reach into graphify's own resolver, not to every future module
#: that wants a subprocess timeout (the same reasoning `funnel.py` itself
#: gives for not importing `review`'s private git runner).
_MISE_TASKS_TIMEOUT = 30


def task_edges(repo_root: Path) -> list[Edge]:
    """One edge per non-empty ``run`` line of every mise task.

    `mise tasks --json` is CWD-sensitive: run it from anywhere but
    `repo_root` and it reflects whichever `mise.toml` is nearest THAT cwd —
    mise's own bootstrap tasks, not this repo's — so `cwd=repo_root` is
    passed explicitly rather than relying on the caller's process cwd.

    A task whose `run` is empty (a meta-task expressed only via `depends`,
    e.g. this repo's `check`) contributes no edge — there is no command to
    point at, and inventing one from `depends` is a different lane's job.

    Bounded by `_MISE_TASKS_TIMEOUT` and wrapped: unbounded and unwrapped, a
    wedged or missing `mise` binary either hangs this lane forever or raises
    `CalledProcessError`/`TimeoutExpired` past `code_intel_main`'s own error
    boundary (which only ever caught `ValueError`) as a bare traceback instead
    of the worded refusal every other failure in this module produces.
    """
    try:
        proc = subprocess.run(
            ["mise", "tasks", "--json"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=_MISE_TASKS_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        msg = f"task lane: `mise tasks --json` could not be run — {exc}"
        raise LaneUnavailableError(msg) from exc
    tasks = json.loads(proc.stdout)
    edges: list[Edge] = []
    for task in tasks:
        name = task.get("name")
        if not isinstance(name, str) or not name:
            continue
        for raw_line in task.get("run") or []:
            run_line = raw_line.strip() if isinstance(raw_line, str) else ""
            if not run_line:
                continue
            matched = _TASK_CLI_RE.match(run_line)
            target = f"cli:{matched.group(1)}" if matched else f"cmd:{run_line}"
            edges.append(
                Edge(
                    source=f"task:{name}",
                    target=target,
                    relation="invokes",
                    provenance="MISE_TASK",
                    verified=True,
                    evidence=f"mise tasks --json: {name}",
                )
            )
    return edges


# ---------------------------------------------------------------------------
# Lane 2: SKILL_FENCE — every SKILL.md, both mirrored trees, deduplicated
# ---------------------------------------------------------------------------

#: A fenced command that is itself `mise run <task>` chains straight into the
#: MISE_TASK layer's own node id, same reasoning as `_TASK_CLI_RE` above.
_MISE_RUN_RE = re.compile(r"^mise run (\S+)")


def skill_edges(repo_root: Path) -> list[Edge]:
    """One edge per fenced shell command in every SKILL.md, across BOTH trees.

    Reuses `skill_lint.command_lines` + `skill_lint.DEFAULT_SKILL_GLOBS` —
    the spec forbids a second fence parser (`use-tool-builtins.md`).

    Every skill here is mirrored into `.claude/skills/` AND `.agents/skills/`
    (measured 14 == 14 this session), so walking both globs naively double
    counts every skill, not just a recently-mirrored one.
    `DEFAULT_SKILL_GLOBS` lists `.claude/` first and `skill_lint` names it
    authoritative, so the FIRST occurrence of a skill NAME wins and its
    `.agents/` mirror is skipped: one node, not two.
    """
    edges: list[Edge] = []
    seen: set[str] = set()
    for pattern in skill_lint.DEFAULT_SKILL_GLOBS:
        for path in sorted(repo_root.glob(pattern)):
            name = path.parent.name
            if name in seen:
                continue
            seen.add(name)
            rel = _relpath(repo_root, path)
            raw = path.read_text()
            for lineno, raw_command in skill_lint.command_lines(raw):
                command = raw_command.strip()
                matched = _MISE_RUN_RE.match(command)
                target = f"task:{matched.group(1)}" if matched else f"cmd:{command}"
                edges.append(
                    Edge(
                        source=f"skill:{name}",
                        target=target,
                        relation="invokes",
                        provenance="SKILL_FENCE",
                        verified=True,
                        evidence=f"{rel}:{lineno}",
                    )
                )
    return edges


# ---------------------------------------------------------------------------
# Lane 3: CLI_DISPATCH — `cli.py::_run`'s `if cmd == ...` / `if cmd in {...}`
# ---------------------------------------------------------------------------


def _cmd_literals(test: ast.expr) -> list[str]:
    """Every ``cmd`` literal one `_run` arm's `if` test matches.

    Handles BOTH shapes `_run` actually uses: `cmd == "x"` (one token) and
    `cmd in {"a", "b"}` (several aliases dispatching to the same target,
    e.g. `cli.py`'s `graphify-contract`/`graphify-baseline`/`skillopt-contract`
    arm). The reference prototype's `_cmd_literal` handled only the first
    shape, so it undercounted every compound arm — not moved verbatim here.
    """
    if not isinstance(test, ast.Compare):
        return []
    if not (isinstance(test.left, ast.Name) and test.left.id == "cmd"):
        return []
    if len(test.ops) != 1 or len(test.comparators) != 1:
        return []
    op, comparator = test.ops[0], test.comparators[0]
    if (
        isinstance(op, ast.Eq)
        and isinstance(comparator, ast.Constant)
        and isinstance(comparator.value, str)
    ):
        return [comparator.value]
    if isinstance(op, ast.In):
        members = comparator.elts if isinstance(comparator, (ast.Set, ast.Tuple, ast.List)) else []
        return [
            member.value
            for member in members
            if isinstance(member, ast.Constant) and isinstance(member.value, str)
        ]
    return []


def _first_call(stmts: list[ast.stmt]) -> tuple[str, int] | None:
    """The arm's real dispatch call — the first call that is NOT `print`.

    Walks the arm body one top-level statement at a time, in source order —
    that half is genuine: the outer `for stmt in stmts` loop visits `stmts`
    in list order, which IS `node.body`'s source order. Within one statement
    it uses `ast.walk`, which CPython's own docstring says yields descendants
    "in no specified order" — a breadth-first walk via a `deque`
    (`ast.walk.__doc__`; check it before trusting a claim of depth-first or
    source order here again), not the depth-first, source-order traversal an
    earlier version of this paragraph claimed. `node.lineno` on the returned
    call is therefore the lineno of whichever call `ast.walk` happens to
    yield first among a statement's candidates, not necessarily that
    statement's smallest lineno.

    That correction does not touch correctness, because neither SKIP this
    function makes — a bare `print(...)` call, or an unqualifiable chained
    receiver, below — depends on visiting calls in lineno order. Each only
    needs "if this candidate is not acceptable, keep taking whatever
    `ast.walk` yields next," a property breadth-first provides exactly as
    well as depth-first would. The two cases documented next both hold for a
    narrower reason than "source order": each guard clause's `print(...)`
    and each version arm's `print(...)` is the ONLY call inside its own
    top-level statement, so however `ast.walk` orders THAT statement's other
    nodes never comes into it. The ordering guarantee this function actually
    relies on is the OUTER per-statement loop, not `ast.walk`'s internal
    order — a bare `print(...)` call is SKIPPED rather than accepted as the
    answer, and the walk continues past it looking for the next candidate.
    `print` is builtin I/O, never a delegation to a real function this lane
    should trace as a dispatch target.

    This is the fix for the confirmed defect at `06e5c615`: FIVE emitted
    edges targeted `fn:print`, `verified=True`. Two shapes, two different
    reasons the old code (which accepted the very first `ast.Call` anywhere in
    the body, full stop) got them wrong:

    * `merge`'s and `transcribe`'s validation guard — `if not rest: print(...,
      file=sys.stderr); return 2` — is a NESTED `if` whose `print(...)` sits
      before the arm's own trailing `return graphify_ops.merge_chunk(...)` /
      `return graphify_ops.transcribe(...)` in source order. Skipping the
      guard's `print` and continuing the SAME depth-first walk is what lets it
      reach the real target instead of stopping early — the guard is still
      walked (so a real call sitting inside a DIFFERENT kind of guard is still
      found), only `print` itself is excluded.
    * The version arm (`cmd in {"-V", "--version", "version"}`) is `print(...);
      return 0` — `print` genuinely is that arm's only call. Skipping it
      leaves NO candidate, so this arm now contributes NO edge at all. That is
      the honest answer: it does not dispatch anywhere, and naming a builtin
      as if it were a real function this graph should trace would be exactly
      the false-fact problem issue #276's own docstring warns `verified=True`
      is a promise about.

    A trade-off worth stating rather than hiding: this is a narrow, evidenced
    fix for `print` specifically, not a general "skip every guard clause"
    solution — an arm whose guard calls some OTHER function before its real
    dispatch (none exist in `cli.py` at this commit) would still resolve to
    that guard's call, unchanged from the pre-fix behaviour. Widening this
    into a general guard-detector is a separate, larger change this fix does
    not make.

    Qualifies `module.func(...)` as `"module.func"` when the receiver is a
    simple name — most arms end in `<module>.main(...)` after a lazy
    `from kb_setup import <module>`, so a bare `.attr` extraction would
    collapse dozens of distinct dispatch targets onto one ambiguous label.

    A receiver that is ITSELF an attribute — `sys.stderr.write(...)`,
    `self.opts.run(...)` — cannot be qualified this way at all without
    resolving the receiver expression, which is call-graph work this lane
    does not do (see the module docstring). The code used to fall through to
    a bare `func.attr` in that case: `target="fn:write"`, `verified=True` —
    the exact false-fact class `06e5c615` fixed for `print`, one AST node
    shape over, since it names a symbol the source does not call standalone.
    Latent, not live, at `fc3e084b` (`dispatch_edges` emits 25 edges there,
    none a bare unqualified attribute) — confirmed by review round 2, and
    fixed the same way as `print`: SKIP it and keep walking for a resolvable
    candidate, rather than emit a guess. Same honest-emptiness argument as
    the version arm's `print` above — an arm whose only call is a chained
    receiver now contributes NO edge, visible as a lower count from
    `dispatch_edges`, not as a wrong target.
    """
    for stmt in stmts:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                if func.id == "print":
                    continue
                return func.id, node.lineno
            if isinstance(func, ast.Attribute):
                if isinstance(func.value, ast.Name):
                    return f"{func.value.id}.{func.attr}", node.lineno
                # A chained receiver (`sys.stderr.write(...)`) cannot be
                # qualified without resolving the receiver expression itself.
                # Skip it, same as `print` above, rather than emit the bare
                # `.attr` guess this branch used to return.
                continue
    return None


def dispatch_edges(repo_root: Path) -> list[Edge]:
    """One edge per dispatch arm in `cli.py::_run`, depth-1 only.

    The target is the first NON-`print` function an arm's body calls — even
    when that target is itself a second-level dispatcher (`_dispatch_contract`
    and friends). Tracing INTO those is a call-graph problem this repo already
    assigns to a different mechanism (the `TY_LSP` lane, once built), not to a
    single static AST walk of one function. See `_first_call` for exactly why
    `print` is excluded and what that does and does not fix.

    Raises `LaneUnavailableError` — never returns `[]` — when `cli.py` itself is
    missing or its `_run` function cannot be found: those are "could not
    look", not "looked and found zero dispatch arms".
    """
    path = _repo_src(repo_root) / "kb_setup" / "cli.py"
    if not path.is_file():
        msg = f"dispatch lane: {_relpath(repo_root, path)} not found — cli.py is missing or moved"
        raise LaneUnavailableError(msg)
    rel = _relpath(repo_root, path)
    tree = ast.parse(path.read_text(), filename=str(path))
    run_fn = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_run"),
        None,
    )
    if run_fn is None:
        msg = f"dispatch lane: {rel} has no top-level `_run` function — cli.py was refactored"
        raise LaneUnavailableError(msg)
    edges: list[Edge] = []
    for node in run_fn.body:
        if not isinstance(node, ast.If):
            continue
        tokens = _cmd_literals(node.test)
        if not tokens:
            continue
        found = _first_call(node.body)
        if found is None:
            continue
        target, lineno = found
        edges.extend(
            Edge(
                source=f"cli:{token}",
                target=f"fn:{target}",
                relation="dispatches_to",
                provenance="CLI_DISPATCH",
                verified=True,
                evidence=f"{rel}:{lineno}",
            )
            for token in tokens
        )
    return edges


# ---------------------------------------------------------------------------
# Lane 4: CONFIG_READ — open/read_text/load(s) of a config-shaped path
# ---------------------------------------------------------------------------

_CONFIG_CALL_NAMES = frozenset({"open", "read_text", "load", "loads"})
_CONFIG_HINT_SUFFIXES = (".toml", ".json", ".yaml", ".yml", ".pkl", ".md", ".jsonl", ".manifest")


def config_edges(repo_root: Path) -> list[Edge]:
    """One edge per function that reads a config-shaped path.

    AST, not grep — a grep for e.g. `currency.toml` mostly matches docstring
    prose describing the file, not a read of it. Non-recursive over
    `python/src/kb_setup/*.py`, matching the reference prototype's measured
    scope: **2 edges** across the whole tree, because this codebase passes
    config paths as parameters one function away from the literal
    (`manifest.load_all()` globs a path and hands it to `load(p)`).
    Resolving THAT needs interprocedural analysis — the `TY_LSP` lane's job,
    not this one's. A `config_edges` that suddenly returns hundreds has
    become wrong, not better; do not widen the match to compensate.

    Resolves two shapes beyond a bare literal-in-place: a same-function local
    `name = <literal path expr>` later passed to a config-shaped call, and a
    same-function `with open(<literal path expr>) as f:` whose handle `f` is
    later passed to `json.load(f)` / similar. A path built from a loop
    variable, a function parameter, or returned from another function is
    invisible to this heuristic by design.

    Raises `LaneUnavailableError` — never returns `[]` — when
    `python/src/kb_setup/` itself is missing: "could not look" (the directory
    is gone) must not read the same as "looked at every file and found no
    config reads". A single file that fails to PARSE is a different judgement
    call, made in-line below: skipped, counted, and reported on stderr, not
    raised — one unparsable file among many is a skip, not a reason to fail
    a lane that is legitimately reading the other N-1.
    """
    src = _repo_src(repo_root) / "kb_setup"
    if not src.is_dir():
        msg = (
            f"config lane: {_relpath(repo_root, src)} is not a directory — "
            "the kb_setup package is missing or moved"
        )
        raise LaneUnavailableError(msg)
    edges: list[Edge] = []
    skipped: list[str] = []
    for path in sorted(src.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            skipped.append(_relpath(repo_root, path))
            continue
        rel = _relpath(repo_root, path)
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            qualname = f"{path.stem}.{func.name}"
            for cfg_path, lineno in _config_reads_in_function(func):
                edges.append(
                    Edge(
                        source=f"fn:{qualname}",
                        target=f"config:{cfg_path}",
                        relation="reads",
                        provenance="CONFIG_READ",
                        verified=True,
                        evidence=f"{rel}:{lineno}",
                    )
                )
    if skipped:
        print(
            f"[code-intel] config lane: skipped {len(skipped)} unparsable file(s): "
            f"{', '.join(skipped)}",
            file=sys.stderr,
        )
    return edges


def _local_assignments(func: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, str]:
    """Same-function `name = <literal path expr>` bindings.

    Split out of `_config_reads_in_function` so each pass stays under this
    repo's complexity gate (`C901`/`mccabe`) on its own — same technique
    `chunks._hyperedge_member_issues` already uses, for the same reason.
    """
    local_paths: dict[str, str] = {}
    for node in ast.walk(func):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            continue
        rendered = _render(node.value)
        if rendered:
            local_paths[node.targets[0].id] = rendered
    return local_paths


def _with_open_handles(
    func: ast.FunctionDef | ast.AsyncFunctionDef, local_paths: dict[str, str]
) -> dict[str, str]:
    """Same-function `with open(<literal path expr>) as f:` handle bindings."""
    handles: dict[str, str] = {}
    for node in ast.walk(func):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            call = item.context_expr
            if not (
                isinstance(call, ast.Call)
                and _call_name(call.func) == "open"
                and call.args
                and isinstance(item.optional_vars, ast.Name)
            ):
                continue
            rendered = _render(call.args[0]) or local_paths.get(_name_of(call.args[0]))
            if rendered:
                handles[item.optional_vars.id] = rendered
    return handles


def _config_call_reads(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    local_paths: dict[str, str],
    with_handles: dict[str, str],
) -> dict[str, int]:
    """`{config path: first line seen}` for every config-shaped call in `func`."""
    found: dict[str, int] = {}
    for node in ast.walk(func):
        if not isinstance(node, ast.Call) or _call_name(node.func) not in _CONFIG_CALL_NAMES:
            continue
        for arg in [*node.args, *(kw.value for kw in node.keywords)]:
            rendered = _render(arg)
            if rendered is None and isinstance(arg, ast.Name):
                rendered = with_handles.get(arg.id) or local_paths.get(arg.id)
            if rendered and any(rendered.endswith(suf) for suf in _CONFIG_HINT_SUFFIXES):
                found.setdefault(rendered, node.lineno)
    return found


def _config_reads_in_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[str, int]]:
    """`(config path, line)` pairs for one function — see `config_edges`."""
    local_paths = _local_assignments(func)
    with_handles = _with_open_handles(func, local_paths)
    found = _config_call_reads(func, local_paths, with_handles)
    return list(found.items())


def _name_of(node: ast.expr | None) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _render(node: ast.expr) -> str | None:
    """Render a `"literal"` or `x / "y" / "z"`-shaped path expression to text."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _render(node.left)
        right = _render(node.right)
        if left and right:
            return f"{left}/{right}"
        return right
    return None


# ---------------------------------------------------------------------------
# Lane 5: TY_LSP — STUB, this change
# ---------------------------------------------------------------------------


def ty_edges(_repo_root: Path) -> list[Edge]:
    """STUB. Always returns `[]` — the TY_LSP lane is not built this change.

    `ty` (pinned 0.0.74) ships `call_hierarchy_provider` / `type_hierarchy_
    provider` natively, which is the leading backend candidate, but WHICH
    backend actually lands is issue #276's own Serena evaluation to decide —
    not this change's. Do not write an LSP client here, do not add a
    dependency, do not shell out to `ty`; see this module's spec §4.
    """
    return []


# ---------------------------------------------------------------------------
# Collection: run one or more lanes, distinguishing "ran, found 0" from
# "no such lane"
# ---------------------------------------------------------------------------

_LANES: dict[str, Callable[[Path], list[Edge]]] = {
    "task": task_edges,
    "skill": skill_edges,
    "dispatch": dispatch_edges,
    "config": config_edges,
    "ty": ty_edges,
}


@dataclass(frozen=True)
class LaneRun:
    """One lane's own result — what makes "ran, found N" answerable per-lane."""

    name: str
    edges: tuple[Edge, ...]


def run_lanes(repo_root: Path, lanes: Sequence[str] | None = None) -> list[LaneRun]:
    """Run each requested lane and report ITS OWN result, not just a merged list.

    A silent zero is a defect in this repo (`probes-need-a-control-arm.md`):
    a lane NAME that matches nothing in `_LANES` must be distinguishable from
    a real lane that ran and legitimately found nothing (`ty`, this change).
    An unrecognized name raises `ValueError` naming the known set — it never
    contributes zero edges as if it had run.

    A lane that WAS a known name but could not be RUN (`dispatch`/`config`
    over a missing file or directory, `task` over a wedged or missing `mise`)
    raises `LaneUnavailableError` instead — propagated uncaught, deliberately: this
    function's contract is one `LaneRun` per requested lane, and there is no
    value to put in one for a lane that never ran. `code_intel_main` is where
    both exceptions become a worded refusal and a non-zero rc.
    """
    names = list(lanes) if lanes is not None else list(_LANES)
    unknown = [n for n in names if n not in _LANES]
    if unknown:
        known = ", ".join(sorted(_LANES))
        msg = f"unknown code-intel lane(s) {unknown!r} — known lanes: {known}"
        raise ValueError(msg)
    return [LaneRun(name=name, edges=tuple(_LANES[name](repo_root))) for name in names]


def collect(repo_root: Path, lanes: Sequence[str] | None = None) -> list[Edge]:
    """All edges from the requested lanes (default: all), flattened.

    Built on `run_lanes`, which is where the per-lane "ran, found N" report
    and the unknown-lane-name refusal both live; this is the flat
    convenience view over the same run.
    """
    return [edge for run in run_lanes(repo_root, lanes) for edge in run.edges]


# ---------------------------------------------------------------------------
# Chunk mapping — see the module docstring's "emit a chunk, never merge one"
# ---------------------------------------------------------------------------

_VERIFIED_CONFIDENCE = "EXTRACTED"
_UNVERIFIED_CONFIDENCE = "INFERRED"


def _node_kind(node_id: str) -> str:
    return node_id.split(":", 1)[0] if ":" in node_id else "unknown"


def _schema_dict(values: dict[str, object], required: tuple[str, ...], *, kind: str) -> dict:
    """`values` filtered/ordered to `required`, or a loud failure if it can't be.

    `required` is `chunks._NODE_REQUIRED` / `chunks._EDGE_REQUIRED` — the REAL
    schema, imported rather than retyped. If that schema ever grows a field
    this mapping does not know how to fill, the next `to_chunk` call raises
    HERE, at the mapping, instead of silently emitting a chunk one field
    short of what `kb-merge` requires.
    """
    missing = [k for k in required if k not in values]
    if missing:
        msg = (
            f"to_chunk {kind} mapping is missing schema field(s) {missing} — "
            f"chunks.py's schema moved; update this mapping"
        )
        raise RuntimeError(msg)
    return {k: values[k] for k in required}


def to_chunk(edges: Sequence[Edge]) -> dict:
    """Map the `Edge` model onto the REAL chunk schema (`kb_setup.chunks`).

    The schema knows nothing of `provenance`/`verified`/`evidence` — it wants
    `confidence`/`confidence_score`/`weight` on an edge and
    `id`/`label`/`file_type`/`source_file`/`source_url`/`captured_at` on a
    node. This mapping is explicit rather than inventing a field the schema
    does not have:

    - `Edge.verified` -> `confidence`: `True` -> `"EXTRACTED"`, `False` ->
      `"INFERRED"` (the schema's only two edge tiers today; AMBIGUOUS is
      edge-only and reserved by #177, never assigned here).
    - `confidence_score`: `1.0` verified, `0.5` unverified.
    - `weight`: constant `1.0` — this lane has no notion of edge strength yet.
    - `provenance`/`verified`/`evidence` are ALSO carried verbatim as extra
      edge keys the schema does not forbid, so a `verified=False` edge
      round-trips as `verified=False` explicitly — not merely as a lower
      `confidence_score`, which `_UNVERIFIED_CONFIDENCE` could be mistaken
      for on its own.
    - a node's `file_type` is its id's KIND (`task`/`skill`/`fn`/`config`/
      `cli`/`cmd`), read off the same namespace prefix that already keeps ids
      from colliding across layers.
    - `source_file`/`source_url`: this lane's nodes are tasks and functions,
      not pages — both are `""`, present (the schema only checks presence)
      rather than omitted.
    - `captured_at`: today, in the required `YYYY-MM-DD` form.

    NOT run through `chunks.validate()` — that also requires `_origin =
    "semantic"`, a claim about HOW a node was produced (LLM extraction) that
    would be false for a node this module derives deterministically from
    AST/subprocess output. Emitting a chunk is this change's scope; merging
    one is a separate, later step (see the module docstring).
    """
    captured_at = datetime.now(UTC).date().isoformat()
    nodes: dict[str, dict] = {}
    out_edges: list[dict] = []

    for edge in edges:
        for node_id in (edge.source, edge.target):
            if node_id in nodes:
                continue
            nodes[node_id] = _schema_dict(
                {
                    "id": node_id,
                    "label": node_id.split(":", 1)[-1],
                    "file_type": _node_kind(node_id),
                    "source_file": "",
                    "source_url": "",
                    "captured_at": captured_at,
                },
                _NODE_REQUIRED,
                kind="node",
            )
        edge_dict = _schema_dict(
            {
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation,
                "confidence": _VERIFIED_CONFIDENCE if edge.verified else _UNVERIFIED_CONFIDENCE,
                "confidence_score": 1.0 if edge.verified else 0.5,
                "weight": 1.0,
            },
            _EDGE_REQUIRED,
            kind="edge",
        )
        edge_dict["provenance"] = edge.provenance
        edge_dict["verified"] = edge.verified
        edge_dict["evidence"] = edge.evidence
        out_edges.append(edge_dict)

    return {
        "nodes": list(nodes.values()),
        "edges": out_edges,
        "hyperedges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }


# ---------------------------------------------------------------------------
# CLI: `uv run kb-setup code-intel [--lanes a,b] [--out PATH] [--format F]`
# ---------------------------------------------------------------------------

_USAGE = (
    "kb-setup code-intel [--lanes a,b] [--out PATH] [--format chunk|json]\n"
    "  Emit provenance-tagged code-intelligence edges (issue #276);\n"
    "  never merges into graphify-out/.\n"
    f"  lanes: {', '.join(sorted(_LANES))}"
)


def _parse_args(
    argv: Sequence[str],
) -> tuple[int | None, list[str] | None, Path | None, str]:
    """`(rc, lanes, out_path, format)`.

    `rc` is `None` to keep going, or the exit code `code_intel_main` should
    return immediately — 0 after printing `--help`, 2 after printing a bad-
    argument message. Returning the rc explicitly (rather than a sentinel
    the caller has to re-derive from `argv`) keeps there being exactly ONE
    place that decides what a parse failure is worth.
    """
    lanes: list[str] | None = None
    out_path: Path | None = None
    fmt = "chunk"
    args = list(argv)
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"-h", "--help"}:
            print(_USAGE)
            return 0, None, None, fmt
        if arg == "--lanes" and i + 1 < len(args):
            i += 1
            lanes = [x.strip() for x in args[i].split(",") if x.strip()]
            if not lanes:
                # An empty `--lanes` value splits to `[]`, which is NOT `None`
                # — so without this check it skips the default-all branch in
                # `run_lanes` (`lanes is not None`), `unknown` comes back
                # empty (nothing to be unknown), and the refusal there never
                # fires: `code_intel_main` would silently write
                # `{"edges": []}` and return 0. An empty `--lanes` is a
                # malformed REQUEST, not an empty result.
                print(
                    f"kb-setup code-intel: --lanes requires at least one lane "
                    f"name, got {args[i]!r}\n\n{_USAGE}",
                    file=sys.stderr,
                )
                return 2, None, None, fmt
        elif arg == "--out" and i + 1 < len(args):
            i += 1
            out_path = Path(args[i])
        elif arg == "--format" and i + 1 < len(args):
            i += 1
            fmt = args[i]
        else:
            print(
                f"kb-setup code-intel: unrecognized argument {arg!r}\n\n{_USAGE}",
                file=sys.stderr,
            )
            return 2, None, None, fmt
        i += 1
    if fmt not in {"chunk", "json"}:
        print(
            f"kb-setup code-intel: --format must be 'chunk' or 'json', got {fmt!r}",
            file=sys.stderr,
        )
        return 2, None, None, fmt
    return None, lanes, out_path, fmt


def code_intel_main(repo_root: Path, argv: Sequence[str]) -> int:
    """`uv run kb-setup code-intel` — the mise task `kb-code-intel`'s target.

    Prints one ``lane <name>: ran, found N`` line per lane BEFORE writing
    output — the per-lane report `run_lanes` makes possible — then writes
    the chunk (`--format chunk`, default) or the raw edge list
    (`--format json`) to `--out PATH` or stdout. An unrecognized `--lanes`
    name exits 2, naming the known set; it never silently runs an empty set.

    A `LaneUnavailableError` from any lane (a missing `cli.py`, a missing
    `kb_setup/` directory, a wedged or missing `mise` binary) is caught here
    and converted into the SAME shape every other refusal in this module
    takes: a worded message on stderr, `Rc.NOT_RUN` — "we did not look",
    never a `{"edges": []}` payload that reads like "we looked and found
    nothing".
    """
    rc, lanes, out_path, fmt = _parse_args(argv)
    if rc is not None:
        return rc

    try:
        runs = run_lanes(repo_root, lanes)
    except ValueError as exc:
        print(f"kb-setup code-intel: {exc}", file=sys.stderr)
        return 2
    except LaneUnavailableError as exc:
        print(f"kb-setup code-intel: {exc}", file=sys.stderr)
        return int(Rc.NOT_RUN)

    for run in runs:
        print(f"[code-intel] lane {run.name}: ran, found {len(run.edges)}")

    edges = [edge for run in runs for edge in run.edges]
    payload: dict | list[dict] = to_chunk(edges) if fmt == "chunk" else [asdict(e) for e in edges]
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    if out_path is not None:
        out_path.write_text(text)
        print(f"[code-intel] wrote {len(edges)} edge(s) to {out_path}")
    else:
        print(text)
    return 0
