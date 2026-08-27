"""Depth adapter B: a real, live MermaidTrace sequence trace of one cli.py
dispatch, end to end.

API probed this session (unverified before now, per the spec's PREMISES row
A — `mermaid-trace 0.7.1.post0`, `requires_python >=3.10`): it is a
`logging`-based tracer, not a `sys.settrace` auto-tracer. `mt.trace` is a
decorator that logs a `FlowEvent` on entry/exit; `mt.configure_flow(output_file=...)`
attaches a `MermaidFileHandler` that renders those events as
`sequenceDiagram` lines. Nothing is captured unless the function you call was
decorated BEFORE the call.

**Deliberate substitution from the spec's literal wording**, stated up front
because it changes what "one real command" means here: the spec says
"decorate `_run`'s build arm... and run one real command", but the real build
arm calls `kb_setup.graph.build()`, which WRITES `graphify-out/graph.json` —
forbidden outright by this same spec (section 4: "must never write it").
`kb-setup context` (`mise run kb-context`) is dispatched through the exact
same `cli.main` -> `cli._run` -> `if cmd == "..."` mechanism, is genuinely
read-only, and has real multi-frame depth
(`context_usage.main -> measure -> own_transcript -> _last_usage -> render`)
— which is what this shape needs to demonstrate. `cli.main(["context"])` is
called directly and for real; nothing about the trace is synthetic.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROTO_ROOT = Path(__file__).resolve().parent
OUT_DIR = PROTO_ROOT / "out"

#: Populated by `depth_edges` as a side effect — see emit.py's driver.
STATS: dict = {}


def _repo_src(repo_root: Path) -> Path:
    return repo_root / "python" / "src"


def depth_edges(repo_root: Path) -> list[tuple[str, str]]:
    """Trace `kb-setup context` end to end and return the observed call
    sequence as edges. See the module docstring for why `context`, not
    `build`.
    """
    import mermaid_trace as mt

    src = str(_repo_src(repo_root))
    if src not in sys.path:
        sys.path.insert(0, src)
    from kb_setup import cli, context_usage

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_mmd = OUT_DIR / "mermaid-trace-raw.mmd"
    if out_mmd.exists():
        out_mmd.unlink()

    mt.configure_flow(output_file=str(out_mmd), overwrite=True)

    # Decorate the real dispatch entry + every real frame `context` walks
    # through. Module attributes are patched (not the imported names inside
    # `cli.py`) because `cli._run` does `from kb_setup import context_usage`
    # and calls `context_usage.main(...)` — patching the module object is
    # what a lazy re-import inside `_run` will actually see.
    patch_targets: dict[tuple[object, str], object] = {
        (cli, "_run"): cli._run,
        (context_usage, "main"): context_usage.main,
        (context_usage, "measure"): context_usage.measure,
        (context_usage, "own_transcript"): context_usage.own_transcript,
        (context_usage, "_last_usage"): context_usage._last_usage,
        (context_usage, "render"): context_usage.render,
    }
    for (owner, attr), original in patch_targets.items():
        setattr(owner, attr, mt.trace(original))

    start = time.monotonic()
    try:
        rc = cli.main(["context"])  # the REAL command, real dispatch path
    finally:
        for (owner, attr), original in patch_targets.items():
            setattr(owner, attr, original)
    elapsed = time.monotonic() - start

    mermaid_text = out_mmd.read_text() if out_mmd.exists() else ""
    edges = _edges_from_sequence(mermaid_text)

    STATS.clear()
    STATS.update(
        {
            "trace_real_command_rc": rc,
            "trace_real_command_elapsed_s": round(elapsed, 4),
            "trace_mmd_bytes": len(mermaid_text),
            "trace_mmd_lines": mermaid_text.count("\n"),
            "trace_is_sequence_diagram": mermaid_text.strip().startswith(
                "sequenceDiagram"
            ),
        }
    )
    return edges


def _edges_from_sequence(mermaid_text: str) -> list[tuple[str, str]]:
    """Best-effort (source, target) pairs from a mermaid sequenceDiagram's
    `A->>B: label` / `A-->>B: label` lines.
    """
    edges: list[tuple[str, str]] = []
    for line in mermaid_text.splitlines():
        line = line.strip()
        for arrow in ("-->>", "->>", "-->", "->"):
            if arrow in line:
                left, _, rest = line.partition(arrow)
                right = rest.split(":", 1)[0]
                a, b = left.strip(), right.strip()
                if a and b:
                    edges.append((f"trace:{a}", f"trace:{b}"))
                break
    return edges


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    e = depth_edges(root)
    print(f"{len(e)} edges, stats={STATS}")
