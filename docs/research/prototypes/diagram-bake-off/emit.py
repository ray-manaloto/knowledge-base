"""Shared four-layer extractor + mermaid emitter for the diagram-generator
prototype bake-off (DECLARED SPIKE — see the spec's PREMISES for what each
number below was re-measured or assumed against).

Layers, thinnest to thickest:

    SKILL.md fence --> mise task --> cli.py dispatch arm --> function it
    calls --> the config files that function reads

`skill_edges`/`task_edges`/`dispatch_edges`/`config_edges` extract those four
layers statically (no execution, no network beyond `mise tasks --json`).
`to_mermaid` renders any (nodes, edges) pair as a mermaid flowchart. The three
depth_*.py adapters each supply the missing middle layer — "what does the
dispatched function actually call, several frames deep" — via a different
mechanism (static call graph / runtime trace / pre-built knowledge graph).

Run with `--all` to build all three shapes end-to-end (see `main()` at the
bottom); running any depth_*.py module standalone also works for isolated
inspection.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

#: Where this spike lives. Hardcoded rather than `Path.cwd()` because the
#: spec forbids touching the repo tree — every write here must land under
#: /tmp, and the repo path is only ever a READ source.
REPO_ROOT_DEFAULT = Path("/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base")
PROTO_ROOT = Path(__file__).resolve().parent
OUT_DIR = PROTO_ROOT / "out"


def _repo_src(repo_root: Path) -> Path:
    return repo_root / "python" / "src"


# ---------------------------------------------------------------------------
# Layer 1: SKILL.md fences
# ---------------------------------------------------------------------------


def skill_edges(repo_root: Path) -> list[tuple[str, str]]:
    """(skill name, command) for every fenced shell command in every SKILL.md.

    Reuses `kb_setup.skill_lint.command_lines` and `DEFAULT_SKILL_GLOBS`
    per the spec constraint — no new fence parser.
    """
    src = str(_repo_src(repo_root))
    if src not in sys.path:
        sys.path.insert(0, src)
    from kb_setup import skill_lint

    edges: list[tuple[str, str]] = []
    for pattern in skill_lint.DEFAULT_SKILL_GLOBS:
        for path in sorted(repo_root.glob(pattern)):
            name = path.parent.name  # .claude/skills/<name>/SKILL.md -> <name>
            raw = path.read_text()
            for _lineno, command in skill_lint.command_lines(raw):
                edges.append((name, command.strip()))
    return edges


# ---------------------------------------------------------------------------
# Layer 2: mise tasks
# ---------------------------------------------------------------------------


def task_edges(repo_root: Path) -> list[dict]:
    """Raw task objects from `mise tasks --json`, run FROM `repo_root`.

    `cwd` matters: `mise tasks --json` reflects whatever `mise.toml` is
    nearest the cwd, not a global config — run it anywhere else and you get
    mise's own bootstrap tasks (5 of them), not this repo's 82.
    """
    proc = subprocess.run(
        ["mise", "tasks", "--json"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# Layer 3: cli.py dispatch arms
# ---------------------------------------------------------------------------


def dispatch_edges(repo_root: Path) -> list[tuple[str, str]]:
    """(cmd token, target callable) for every `if cmd == "...":` arm in `_run`."""
    path = _repo_src(repo_root) / "kb_setup" / "cli.py"
    tree = ast.parse(path.read_text(), filename=str(path))

    run_fn = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "_run"
        ),
        None,
    )
    if run_fn is None:
        return []

    edges: list[tuple[str, str]] = []
    for node in run_fn.body:
        if not isinstance(node, ast.If):
            continue
        cmd_token = _cmd_literal(node.test)
        if cmd_token is None:
            continue
        target = _first_call_name(node.body)
        if target:
            edges.append((cmd_token, target))
    return edges


def _cmd_literal(test: ast.expr) -> str | None:
    """Match `cmd == "literal"` (the shape every dispatch arm in `_run` uses)."""
    if not isinstance(test, ast.Compare):
        return None
    if not (isinstance(test.left, ast.Name) and test.left.id == "cmd"):
        return None
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return None
    if len(test.comparators) != 1:
        return None
    comp = test.comparators[0]
    if isinstance(comp, ast.Constant) and isinstance(comp.value, str):
        return comp.value
    return None


def _first_call_name(stmts: list[ast.stmt]) -> str | None:
    """First called-function/method name inside an arm's body (usually a `return`).

    Qualifies a `module.func(...)` call as `"module.func"` (not bare `"func"`)
    when the receiver is a simple name — most arms end in `<module>.main(...)`
    after a lazy `from kb_setup import <module>`, so a bare `.attr` extraction
    would collapse dozens of distinct dispatch targets onto one ambiguous
    "main" label.
    """
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    return func.id
                if isinstance(func, ast.Attribute):
                    if isinstance(func.value, ast.Name):
                        return f"{func.value.id}.{func.attr}"
                    return func.attr
    return None


# ---------------------------------------------------------------------------
# Layer 4: config reads, via AST (not grep — see spec constraint)
# ---------------------------------------------------------------------------

_CONFIG_CALL_NAMES = {"open", "read_text", "load", "loads"}
_CONFIG_HINT_SUFFIXES = (
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".pkl",
    ".md",
    ".jsonl",
    ".manifest",
)


def config_edges(repo_root: Path) -> list[tuple[str, str]]:
    """(function qualname, config path) for open/read_text/tomllib.load(s) calls
    whose argument renders to something that looks like a config path.

    AST-based on purpose: a grep for e.g. `currency.toml` mostly matches
    docstring prose describing the file, not the read call itself.

    Resolves TWO shapes beyond a bare literal-in-place, still via AST (no
    dataflow/points-to analysis — a spike-appropriate cutoff, not a claim of
    completeness): a same-function local `name = <literal path expr>` later
    passed as `open(name)` / `name.read_text()`, and a same-function
    `with open(<literal path expr>) as f:` whose handle `f` is later passed to
    `json.load(f)` / `tomllib.load(f)`. A path built from a loop variable, a
    function parameter, or returned from another function is invisible to
    this heuristic — measured on this repo: catching only bare literals finds
    1 edge in the whole `kb_setup` tree; adding these two shapes finds far
    more (see the README's reported counts) — real config reads here are
    overwhelmingly one indirection away from the call site, not zero.
    """
    src = _repo_src(repo_root) / "kb_setup"
    edges: list[tuple[str, str]] = []
    for path in sorted(src.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            qualname = f"{path.stem}.{func.name}"
            edges.extend(
                (qualname, cfg) for cfg in _config_reads_in_function(func)
            )
    return edges


def _config_reads_in_function(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    # Pass 1: simple local bindings `name = <renderable expr>`, and
    # `with open(<renderable expr>) as handle:` handle bindings.
    local_paths: dict[str, str] = {}
    with_handles: dict[str, str] = {}
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            rendered = _render(node.value)
            if rendered:
                local_paths[node.targets[0].id] = rendered
        if isinstance(node, ast.With):
            for item in node.items:
                call = item.context_expr
                if (
                    isinstance(call, ast.Call)
                    and _call_name(call.func) == "open"
                    and call.args
                    and isinstance(item.optional_vars, ast.Name)
                ):
                    rendered = _render(call.args[0]) or (
                        local_paths.get(_name_of(call.args[0]))
                    )
                    if rendered:
                        with_handles[item.optional_vars.id] = rendered

    # Pass 2: config-shaped calls, resolving a bare-Name arg through either
    # binding map before giving up on it.
    found: set[str] = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if _call_name(node.func) not in _CONFIG_CALL_NAMES:
            continue
        for arg in [*node.args, *(kw.value for kw in node.keywords)]:
            rendered = _render(arg)
            if rendered is None and isinstance(arg, ast.Name):
                rendered = with_handles.get(arg.id) or local_paths.get(arg.id)
            if rendered and any(rendered.endswith(suf) for suf in _CONFIG_HINT_SUFFIXES):
                found.add(rendered)
    return found


def _name_of(node: ast.expr) -> str | None:
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
# Mermaid emitter
# ---------------------------------------------------------------------------


def _node_id(label: str) -> str:
    return "n" + hashlib.sha1(label.encode()).hexdigest()[:10]


def _mermaid_escape(label: str) -> str:
    label = label.replace('"', "'").replace("\n", " ").strip()
    if len(label) > 70:
        label = label[:67] + "..."
    return label


def to_mermaid(
    nodes: list[str], edges: list[tuple[str, str]], *, title: str
) -> str:
    """Render nodes/edges as a mermaid `flowchart LR`. Every node that
    appears only as an edge endpoint is declared too, so no dangling ref.
    """
    seen: dict[str, str] = {}
    lines = ["---", f"title: {title}", "---", "flowchart LR"]

    def declare(label: str) -> str:
        if label not in seen:
            seen[label] = _node_id(label)
            lines.append(f'    {seen[label]}["{_mermaid_escape(label)}"]')
        return seen[label]

    for n in nodes:
        declare(n)
    for a, b in edges:
        sid, tid = declare(a), declare(b)
        lines.append(f"    {sid} --> {tid}")
    return "\n".join(lines) + "\n"


_HTML_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
</head>
<body>
<h1>{title}</h1>
<pre class="mermaid">
{mermaid}
</pre>
<script>mermaid.initialize({{ startOnLoad: true }});</script>
</body>
</html>
"""


def write_shape(name: str, mermaid: str, *, title: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{name}.mmd").write_text(mermaid)
    (OUT_DIR / f"{name}.html").write_text(
        _HTML_TEMPLATE.format(title=title, mermaid=mermaid)
    )


# ---------------------------------------------------------------------------
# Assembly: the four static layers, parametrized per worked example
# ---------------------------------------------------------------------------

#: Shapes A (code2flow) and C (graphify) both target the real `kb-build`
#: dispatch. Shape B substitutes `kb-context` — see depth_trace.py's module
#: docstring for why running the real `build` arm is unsafe here.
KB_BUILD = ("kb-build", "build")
KB_CONTEXT = ("kb-context", "context")


def base_layers(
    repo_root: Path, *, task_name: str, cmd_token: str
) -> tuple[list[str], list[tuple[str, str]], str | None]:
    """The four static layers, filtered to ONE (task_name, cmd_token) example.

    Returns (nodes, edges, dispatch_fn_label) covering: skill -> task ->
    dispatch arm -> dispatched function -> every config file that function's
    own module reads (AST scope: `cli.py` + the module the dispatch target
    lives in — a coarse, honest slice, not full interprocedural reach; see
    `config_edges`'s docstring for the measured limit of that layer).
    `dispatch_fn_label` is returned so the caller can bridge a depth
    adapter's own internal graph onto this static skeleton.
    """
    nodes: list[str] = []
    edges: list[tuple[str, str]] = []

    for skill, command in skill_edges(repo_root):
        if task_name in command:
            edges.append((f"skill:{skill}", f"mise task:{task_name}"))
            break  # one worked example, one skill edge is plenty

    task_label = f"mise task:{task_name}"
    for task in task_edges(repo_root):
        if task.get("name") == task_name:
            run_line = " ".join(task.get("run", []))
            edges.append((task_label, f"cli.py: {run_line}"))
            break

    dispatch_label = None
    dispatch_target = None
    for cmd, target in dispatch_edges(repo_root):
        if cmd == cmd_token:
            edges.append((f"cli.py: uv run kb-setup {cmd}", f"fn:{target}"))
            dispatch_label = f"fn:{target}"
            dispatch_target = target
            break

    # Config reads owned by cli.py + whichever module the dispatch target's
    # qualname prefix names (e.g. "graph.build" -> module "graph").
    target_module = dispatch_target.split(".", 1)[0] if dispatch_target else None
    for qualname, cfg_path in config_edges(repo_root):
        owner = qualname.split(".", 1)[0]
        if owner == "cli" or (target_module and owner == target_module):
            edges.append((f"fn:{qualname}", f"config:{cfg_path}"))

    return nodes, edges, dispatch_label


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="build all three shapes")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT_DEFAULT)
    args = parser.parse_args(argv)

    if not args.all:
        parser.print_help()
        return 1

    import depth_code2flow
    import depth_graphify
    import depth_trace

    repo_root = args.repo
    stats: dict[str, dict] = {}

    build_nodes, build_edges, build_dispatch = base_layers(
        repo_root, task_name=KB_BUILD[0], cmd_token=KB_BUILD[1]
    )
    context_nodes, context_edges, context_dispatch = base_layers(
        repo_root, task_name=KB_CONTEXT[0], cmd_token=KB_CONTEXT[1]
    )

    # (module, base nodes/edges/dispatch-fn-label, bridge target, bridge note)
    # The bridge edge is SUPPLIED BY US, not discovered by the tool — each
    # note says why the tool itself couldn't draw it, which is itself part
    # of the shape comparison (see README).
    shapes = (
        (
            "code2flow",
            depth_code2flow,
            build_nodes,
            build_edges,
            build_dispatch,
            "graph::build",
            "code2flow can't resolve graph.build() from _build_checked: the "
            "call crosses a function-LOCAL `from kb_setup import graph` "
            "(this codebase's deliberate lazy-import pattern), which defeats "
            "its static import resolution.",
        ),
        (
            "mermaid-trace",
            depth_trace,
            context_nodes,
            context_edges,
            context_dispatch,
            "trace:context_usage",
            "Shape B traces `kb-setup context`, not `kb-build` — running the "
            "real build arm would write graphify-out/graph.json, which this "
            "spike must never do (spec section 4).",
        ),
        (
            "graphify",
            depth_graphify,
            build_nodes,
            build_edges,
            build_dispatch,
            "python/src/kb_setup/graph.py::build()",
            "_build_checked is ABSENT from `.self-graph` entirely (measured: "
            "32 callable nodes extracted from cli.py total, not among them, "
            "despite existing at the graph's own built_at_commit) — a real "
            "extraction gap, not staleness.",
        ),
    )

    for shape_name, module, base_nodes, base_edges, dispatch_label, bridge_target, bridge_note in shapes:
        print(f"[emit] running shape: {shape_name}")
        start = time.monotonic()
        # `depth_edges` conforms to the spec's exact interface (returns just
        # the edge list); each adapter also records its own richer stats
        # (skip counts, node coverage, etc.) into module-level STATS as a
        # side effect, which we read back here for the README.
        extra_edges = module.depth_edges(repo_root)
        elapsed = time.monotonic() - start
        meta = dict(getattr(module, "STATS", {}))
        meta["bridge_note"] = bridge_note

        bridge_edges = [(dispatch_label, bridge_target)] if dispatch_label else []
        all_edges = base_edges + bridge_edges + extra_edges
        title = f"kb-build — {shape_name}" if shape_name != "mermaid-trace" else "kb-context — mermaid-trace"
        mermaid = to_mermaid(base_nodes, all_edges, title=title)
        write_shape(shape_name, mermaid, title=title)

        stats[shape_name] = {
            "wall_clock_s": round(elapsed, 3),
            "extra_edge_count": len(extra_edges),
            "total_edge_count": len(all_edges),
            **meta,
        }
        print(f"[emit]   {shape_name}: {stats[shape_name]}")

    (OUT_DIR / "stats.json").write_text(json.dumps(stats, indent=2))
    print(f"[emit] wrote {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
