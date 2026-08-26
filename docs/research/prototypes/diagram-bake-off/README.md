# diagram-generator prototype bake-off — DECLARED SPIKE

Throwaway. Not headed for `main`. Nothing under the repo working tree was
modified — verified: `git status --short` on the repo is byte-identical
before and after this run (see "Verification" below). All code and output
live under `/tmp/diagram-proto/`.

**Objective recap:** Ray wants architecture/workflow diagrams generated from
the code, kept in sync, never hand-authored, across a chain that crosses
markdown (SKILL.md), TOML (mise tasks), and Python (cli.py dispatch + the
functions it calls + the config files they read). No external tool draws all
four layers, so three plausible build shapes were prototyped from one shared
extractor to compare on real output instead of on reasoning.

## What was built

- `emit.py` — the shared four-layer extractor (`skill_edges`, `task_edges`,
  `dispatch_edges`, `config_edges`) + the mermaid emitter (`to_mermaid`) +
  the driver (`--all`).
- `depth_code2flow.py` / `depth_trace.py` / `depth_graphify.py` — one depth
  adapter per shape, each exposing `depth_edges(repo_root) -> list[tuple[str,
  str]]` exactly per the spec's interface (richer stats ride along in a
  module-level `STATS` dict as a side effect, read back by the driver — kept
  the public interface unchanged rather than widening its return shape).
- `out/*.mmd` + `out/*.html` — the three comparable artifacts, one per shape.
- `out/stats.json` — every number below, machine-readable.

Run: `uv run --with code2flow --with mermaid-trace --with ijson python
emit.py --all` from `/tmp/diagram-proto`. Total wall clock for all three
shapes: **~9.5s** (1.9s + 0.1s + 7.5s), plus the four static layers shared
across shapes (skill/task/dispatch/config extraction, sub-second).

## The four static layers, measured

- **`skill_edges`** (reuses `kb_setup.skill_lint.command_lines` +
  `DEFAULT_SKILL_GLOBS`, per the spec constraint — no new fence parser):
  **395** fenced commands across every `SKILL.md`. `kb-curator`'s SKILL.md is
  the one used for the `kb-build` worked example's skill edge.
- **`task_edges`** (`mise tasks --json`, run with `cwd=repo_root`): **82**
  tasks — matches the premise exactly. **Caught one mistake building this**:
  running `mise tasks --json` from `/tmp/diagram-proto` instead of the repo
  root silently returns mise's own 5 bootstrap tasks, not this repo's 82 —
  `cwd` is load-bearing and easy to get wrong.
- **`dispatch_edges`** (AST over `cli.py`'s `_run`, matching `if cmd ==
  "literal":` arms at the top level): **13** top-level arms. The premise's
  "**59** occurrences of `cmd == "`" counts the whole file — most of those
  live inside five `_dispatch_*` helper functions `_run` delegates to
  (`_dispatch_advisory`, `_dispatch_lint`, `_dispatch_ops`,
  `_dispatch_record`, `_dispatch_source_ops`), not inside `_run` itself. The
  `build` arm resolves correctly: `cmd == "build"` -> `_build_checked`.
  Also fixed mid-build: a bare `.attr` extraction on `module.main(...)` calls
  collapses dozens of dispatch targets onto the one ambiguous label `"main"`
  (most arms end in `<module>.main(...)` after a lazy import) — now qualified
  as `"module.main"` when the receiver is a simple name.
- **`config_edges`** (AST over every `open`/`read_text`/`.load`/`.loads` call,
  resolving same-function local-variable and `with open(...) as f:` bindings
  — still no dataflow across function boundaries, a spike-appropriate
  cutoff): **2** edges in the ENTIRE `kb_setup` tree (against 395 skill
  commands / 82 tasks / 13 top-level dispatch arms). Neither is in `cli.py`
  or `graph.py`. **This is the most important finding of the whole spike**,
  not a bug in the detector: this codebase almost universally *parameterizes*
  the config path (`def load(path: Path): ... path.read_text(...)`) rather
  than hardcoding it at the read call site — `manifest.load_all` globs
  `sources/*.manifest` and passes each `Path` into `load(p)`, which reads it
  one function away from the literal. Closing that gap needs interprocedural
  dataflow, explicitly out of scope for a throwaway AST pass. **Practical
  consequence for the real build**: whichever shape is chosen, the
  "function → config it reads" layer is the one layer none of the three
  external tools helps with, and a production version will need to invest
  specifically there — this is the spike answering exactly the question it
  was for.

## Shape A — code2flow (static call graph)

**What it drew**: the real, current-source call graph over
`python/src/kb_setup` — **1,313 nodes / 1,978 edges** in **1.37s** wall clock
(re-measured this session; premise said 1.35s, close enough to be the same
fact, not identical — as instructed, re-measured rather than quoted). It
reported **51** call sites it could not resolve to one definition ("linked
them to multiple function definitions" — premise said "~49"; both are real
numbers from re-running the same tool, small variance is expected). Filtered
to the kb-build reachability slice (BFS from a seed, see below): **109
edges**, comfortably legible.

**What it could NOT draw**: `cli::_build_checked` — the actual dispatch
target — has **zero resolved outgoing edges**. It calls `graph.build(...)`
through a function-LOCAL `from kb_setup import ... graph ...` (this
codebase's own documented pattern: "one lazy import per branch, so `kb-setup
<one command>` never pays for the other forty" — cli.py's own comment).
code2flow's static resolver cannot see through a deferred import, so the
worked example's BFS seed had to fall back to `graph::build` (which the
`_build_checked` function itself calls, and which IS resolvable since
graph.py's imports are module-level) — **the diagram supplies that one edge
itself**, not code2flow; documented as a "bridge" edge in the mermaid source
so it isn't silently presented as tool output. Dynamic dispatch generally
(`getattr`, methods resolved only by ~50 different classes sharing a method
name like `.resolve()`) is the other class of loss, visible in the 51 skipped
call sites.

**Needs the code to run?** No — pure static AST/graph analysis, no
execution, no side effects. Fastest of the three (1.37s for the whole
module).

## Shape B — MermaidTrace (runtime sequence trace)

**Deliberate, documented substitution**: the spec says "decorate `_run`'s
build arm... and run one real command," but the *real* build arm calls
`graph.build()`, which writes `graphify-out/graph.json` — forbidden outright
by this same spec (section 4: "must never write it"). `kb-setup context`
(`mise run kb-context`) is dispatched through the exact same
`cli.main -> cli._run -> if cmd == "...":` mechanism, is genuinely read-only,
and has real multi-frame depth (`cli._run -> context_usage.main -> measure ->
own_transcript -> render`) — that's what got traced, for real, decorated with
`mermaid_trace.trace` and invoked via `cli.main(["context"])`.

**What it drew**: a real `sequenceDiagram` — 6 participants, 10 lines,
525 bytes, produced in **0.02s** of actual traced execution (the command's
own real return code, 127, is `context_usage`'s own legitimate "no transcript
found for this directory" outcome — expected, since `/tmp/diagram-proto` is
not a live Claude session transcript directory; not a bug). Genuinely usable:
`Unknown->>cli`, `cli->>context_usage`, `context_usage->>PosixPath` (measure),
nested calls, then returns unwinding back up the stack.

**What it could NOT draw**: MermaidTrace's automatic participant naming is
built for `self`-bound methods; for a plain function whose first positional
argument is a non-primitive object (`repo_root: Path`), it names the
**callee participant after the argument's type** rather than the function's
owning module — the trace shows `context_usage->>PosixPath: Measure(...)`,
not `context_usage->>context_usage: measure(...)`. Usable for a human reading
top-to-bottom, actively misleading if you'd script "count edges per module"
off it without `source=`/`target=` overrides on every decorated call. It also
only shows what actually EXECUTED on this one call — no branch not taken this
run appears at all (unlike A and C, which see the whole reachable graph
regardless of which path executes).

**Needs the code to run?** Yes, always — this is the whole mechanism. No
execution, no diagram; a decorated-but-uncalled function contributes nothing.

## Shape C — graphify (pre-built knowledge graph)

**What it drew**: `graphify-out/graph.json`'s `links` (confirmed: no `edges`
key, per the premise) filtered to `repo == ".self-graph"` (**7,054** nodes,
1.43% of 492,654 — matches the premise) and `relation == "calls"` (one of
several relation types present — `references`/`imports`/`extends`/etc. also
exist and are NOT call edges; `references` alone outnumbers `calls` in the
first 500K links sampled). **4,364** call edges among our own code, touching
**2,797** of 7,054 self-graph nodes (**39.7%** — the rest are classes,
dataclasses, and functions call graphify's own AST extraction never wired
into a `calls` edge). Filtered to the kb-build reachability slice: **139
edges**. Wall clock **7.5s** total (3.68s node scan + 3.70s link scan,
streamed via `ijson` rather than loading the 736MB file whole — the file is
too big for a naive `json.load` to be the FIRST thing you reach for, though
it would still technically work).

**What it could NOT draw, and this is the headline finding**: `_build_checked`
— cli.py:540, the exact function the worked example is about — **is not a
node in `.self-graph` at all**. Measured, not assumed: only 32 callable nodes
were extracted from the whole of `cli.py`, and `_build_checked` is not among
them; it is NOT a staleness artifact either — `git merge-base --is-ancestor`
confirms the function existed at the graph's own `built_at_commit`
(`fbc80305`), 41 commits before HEAD. This is a genuine extraction gap in
graphify's self-graph for this specific function, cause not further
investigated (out of spike scope) — but it means Shape C's diagram had to
seed its BFS from `graph.build()` instead (which IS present), same bridging
compromise as Shape A, for a different underlying reason.

**Second finding, real and worth carrying into the production decision**: node
identity in `.self-graph` is bare `label`, not qualified by file. **90 of
3,401** distinct callable labels are reused across more than one file
(`main()` appears in 17 files, `_run()` in 11, `build()` in 2 — one of which
is the exact function this worked example needed). A diagram keyed on bare
`label` would silently MERGE unrelated functions from different files into
one node. This adapter mitigates it by qualifying every node as
`source_file::label` before building edges — code2flow gets this for free
(its `name` field is already `file::qualname`); a production Shape-C-style
generator would need to do the same qualification deliberately, every time.

**Needs the code to run?** No — reads a pre-built artifact, no execution. But
it needs a **pre-built, non-stale, complete** artifact, and this run
surfaced that "complete" cannot be assumed even when "non-stale" is proven —
a real function existing at the recorded build commit was still missing from
the extraction.

## Cross-shape comparison

| | code2flow (A) | mermaid-trace (B) | graphify (C) |
|---|---|---|---|
| Needs code to run | No | **Yes, always** | No |
| Wall clock (this run) | 1.37s (full module) | 0.02s (one call) | 7.5s (736MB streamed) |
| Sees the whole reachable graph | Yes | No — only what executed | Yes |
| Defeated by | deferred/lazy imports | nothing decorated | extraction gaps in a pre-built artifact |
| Node identity is qualified by default | Yes (`file::name`) | Yes (participant = module/class) | **No — had to be added** (bare `label`) |
| Missed `_build_checked` specifically | Its outgoing edges only | N/A (different command traced) | The node itself |
| Extra tooling weight | none beyond `uv run --with` | none beyond `uv run --with` | needs a graph already built (this repo's is 736MB) |

**None of the three drew the fourth layer (config reads) for this worked
example** — that gap is in `config_edges`, shared by all three shapes, and is
the one layer that needs work regardless of which shape wins (see the static
layers section above).

## Verification

```
cd /tmp/diagram-proto && uv run --with code2flow --with mermaid-trace --with ijson python emit.py --all
ls -la out/            # 3 .mmd + 3 .html (+ 1 raw mermaid-trace intermediate), all non-empty
git -C /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base status --short
```

All six `.mmd`/`.html` files contain a `flowchart` or `sequenceDiagram`
block (checked with `grep -qE "flowchart|sequenceDiagram"` on every one).
`git status --short` on the repo is byte-identical to the baseline captured
before this spike started (the baseline itself carries pre-existing
unrelated uncommitted changes from other work in this repo — not from this
spike). One side effect was caught and cleaned up mid-run: running `mise
tasks --json` / `mise run kb-query` for orientation triggers this repo's own
mise secrets-bootstrap hook, which wrote an untracked, non-gitignored
`.artifacts/mde-events.jsonl` in the repo root — unrelated to the diagram
code itself, removed before the final `git status` check above.
