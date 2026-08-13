# Knowledge Base Agent Instructions

This repository builds and queries a provenance-bound Graphify knowledge graph
from immutable source manifests and reviewed extraction artifacts. `CLAUDE.md`
contains the full project reference; the rules below are the minimum required
for Codex and other Agent Skills clients.

Retain and report every Graphify stderr message, warning, truncation, source
omission, receipt failure, and version drift. Run Graphify installation only
through `mise run kb-skill-refresh`, which repairs machine-specific hooks and
instruction changes before they can enter the repository.

## Graph-first workflow

Before searching or reading project source for a codebase question:

1. Run `mise run kb-query -- "<question>"`.
2. Use the graph result to narrow source inspection and cite its source paths.
3. If the graph is missing, stale, corrupt, warning-bearing, incomplete, or
   truncated, report that state explicitly and use source only as fallback
   authority. An existing graph file or a queued build is not proof of health.

After changing code, use these repository Graphify tasks rather than a global or
bare Graphify binary:

- `mise run kb-build` — reproduce the graph from committed inputs.
- `mise run kb-query -- "<question>"` — query through health checks.
- `mise run kb-affected -- "<symbol>"` — inspect reverse impact.
- `mise run kb-graphify-contract` — verify the locked public SDK surface.
- `mise run kb-skill-refresh` — refresh reviewed Claude and Codex skills.

## Development rules

- Use `uv` through the repository environment; do not use `pip`.
- Work only in the canonical checkout or a registered worktree created from it.
- Treat dirty trees as protected evidence. Do not reset, clean, or discard work.
- Prefer repository tasks and public APIs over custom shell logic.
- Validate public behavior with real, isolated inputs and retain explicit
  failure states; mocks cannot certify product behavior.
- Resolve lint and test findings in the implementation. Any suppression requires
  explicit user approval and an independently verified justification.

Before committing, run the focused checks for changed files, then:

```text
mise run check
mise run kb-gates
```

Use the repository ship/land workflow for delivery. A local branch or green
focused test is not evidence that work reached remote `main`.
