# Prototypes — rescued from `/tmp`, 2026-08-26

Runnable spike code and its measured output, promoted here because it lived in
`/tmp` for **five consecutive handoffs** (2026-08-24 through 2026-08-26), each
one correctly flagging that a reboot would delete it.

This directory follows `docs/research/README.md`'s rule: promotion is a **copy**,
kept **verbatim**, and the artifacts are not normalised or tidied. The bulky
logs were left behind — what is here is the code, the output, and the verdicts.

## `diagram-bake-off/` — three shapes, measured

A **declared spike** from 2026-08-24 comparing three ways to generate
architecture and sequence diagrams from this repo's own Python. Its own
`README.md` (promoted verbatim) carries every number.

| shape | tool | measured | drawback found |
|---|---|---|---|
| A | `code2flow` | 1,313 nodes / 1,978 edges in **1.37 s** | 51 call sites resolved to more than one definition |
| B | `mermaid-trace` | **0.02 s** | only traces what actually executed |
| C | `graphify` | **7.5 s**, streaming 736 MB | **dropped a node** (`_build_checked`); node identity unqualified by default |

`emit.py` is the part worth keeping: a **four-layer extractor** producing
`skill_edges` (395), `task_edges` (82), `dispatch_edges` (13) and
`config_edges` (**2**).

That last number is the spike's real finding and is **not a bug**. This codebase
passes config paths as parameters — `manifest.load_all()` globs the path and
hands a `Path` to `load(p)`, which does the read one function away from the
literal. A single-function AST pass cannot connect them. Closing it needs
analysis that follows a value **across** a function boundary, which is what a
language server does.

## `py2puml-seqdiagram/` — two more tools, and their verdicts

Never part of the bake-off, and both actually run — so neither is
"evaluated only".

- **`py2puml` — ATTEMPTED AND FAILED.** `RC=1`, and **zero bytes of stdout**
  across five attempt variants including two patched ones. `py2puml-rc.txt` and
  the truncated stderr are here. It did not produce a diagram.
- **`seqdiagram` — PROTOTYPED, with two bugs found.** It produced real sequence
  traces (`seqdiagram-kb-entrypoint-fixed-stdout.txt`) and HTML output. Two
  defects were isolated into minimal repros, both promoted:
  - `seqdiagram/resetseq_bug.py` — **`resetseq()` does not reset.** Measured:
    2 traces → `resetseq()` → still 2 → after 2 more calls, 6.
  - `seqdiagram/kwarg_bug.py` — a keyword-argument handling defect.

## What is NOT here, and why

- **The bulk run logs** (~220 KB each × 3 for code2flow, ~5 MB of py2puml
  attempt logs). Reproducible by re-running; the verdicts above are the part
  that was expensive to obtain.
- **`/tmp/graphify-fix`** — a 710 MB clone of the graphify fork. It is **not**
  merely reproducible: it carried commit `5daeaa2`
  (*fix(extract): salt same-scope symbol-id collisions in the generic engine*,
  449 insertions across 6 files) which existed on **no remote** and in **no
  installed build**, control-armed both ways. It was **pushed** to
  `ray-manaloto/graphify` as `fix/extraction-symbol-id-collision` on 2026-08-26
  rather than copied here, because a git commit belongs in git. The clone itself
  is reproducible from that branch.

## Reproducing

The bake-off pins nothing — deliberately. Its own research recommended building
this in-repo with zero new dependencies, so the tools were reached ad hoc:

```
uv run --with code2flow --with mermaid-trace --with ijson python emit.py --all
```

Run it from a copy, not from here: `emit.py` reads the repo root and writes to
`out/`, and these files are the promoted record rather than a working directory.
