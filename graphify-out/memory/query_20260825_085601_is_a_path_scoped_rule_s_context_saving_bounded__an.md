---
type: "query"
date: "2026-08-25T08:56:01.509890+00:00"
question: "Is a path-scoped rule's context saving bounded, and is hierarchical CLAUDE.md a real option?"
contributor: "graphify"
outcome: "corrected"
correction: "PROGRESSIVE DISCLOSURE IS REAL, AND IT CAN ALSO BE COMPLETELY DARK. Both, measured.\n\nFrom the docs, verbatim: \"Claude also discovers CLAUDE.md and CLAUDE.local.md files in\nsubdirectories under your current working directory. Instead of loading them at\nlaunch, they are included when Claude reads files in those subdirectories.\" And on\ncompaction: nested CLAUDE.md and `paths:` rules \"reload as Claude reads files they\napply to\" — so they DROP at compaction rather than staying resident, which is a better\ncost profile than was claimed.\n\nMeasured on this repo's own OTEL telemetry (`.agent/telemetry/`, raw request bodies,\n684 requests from one session):\n\n  zero-skip-policy   (eager)   684 / 684   <- control arm; the method discriminates\n  ci-local-parity    (paths:)   93 / 684   <- lazy loading WORKS, ~86% saved\n  md-size-budgets    (paths:)    0 / 684   <- never loaded, all session\n\nmd-size-budgets globs `.claude/rules/*.md` and `**/CLAUDE.md`. Both were cat-ed and\ngrep-ed repeatedly that session. It never loaded once. The docs say path-scoped rules\ntrigger \"when Claude reads files matching the pattern, not on every tool use\" and are\nsilent on a Bash `cat`; this session is instructed to prefer Bash over the Read tool.\n\nSO: never assume a glob will fire because it matches files you touch. VALIDATE IT\nagainst telemetry — the data is already on disk, no hook needed. `InstructionsLoaded`\nexists for this and is not wired here.\n\nTwo more corrections from the same fetch: `@path` imports do NOT save context\n(\"imported files load at launch\"); and AGENTS.md is not loaded at all — \"Claude Code\nreads CLAUDE.md, not AGENTS.md\" — so its bytes were wrongly counted in a cost table.\n"
---

# Q: Is a path-scoped rule's context saving bounded, and is hierarchical CLAUDE.md a real option?

## Answer

BELIEF, held and stated in a published artifact on 2026-08-25: that a path-scoped
rule's saving is "front-loaded, not bounded" — free until it fires, then resident for
the rest of the session exactly like an eager rule — and that hierarchical
per-subdirectory CLAUDE.md was not a real mechanism worth considering.

Both halves were wrong, and the correction came from the docs plus our own telemetry.


## Outcome

- Signal: corrected
- Correction: PROGRESSIVE DISCLOSURE IS REAL, AND IT CAN ALSO BE COMPLETELY DARK. Both, measured.

From the docs, verbatim: "Claude also discovers CLAUDE.md and CLAUDE.local.md files in
subdirectories under your current working directory. Instead of loading them at
launch, they are included when Claude reads files in those subdirectories." And on
compaction: nested CLAUDE.md and `paths:` rules "reload as Claude reads files they
apply to" — so they DROP at compaction rather than staying resident, which is a better
cost profile than was claimed.

Measured on this repo's own OTEL telemetry (`.agent/telemetry/`, raw request bodies,
684 requests from one session):

  zero-skip-policy   (eager)   684 / 684   <- control arm; the method discriminates
  ci-local-parity    (paths:)   93 / 684   <- lazy loading WORKS, ~86% saved
  md-size-budgets    (paths:)    0 / 684   <- never loaded, all session

md-size-budgets globs `.claude/rules/*.md` and `**/CLAUDE.md`. Both were cat-ed and
grep-ed repeatedly that session. It never loaded once. The docs say path-scoped rules
trigger "when Claude reads files matching the pattern, not on every tool use" and are
silent on a Bash `cat`; this session is instructed to prefer Bash over the Read tool.

SO: never assume a glob will fire because it matches files you touch. VALIDATE IT
against telemetry — the data is already on disk, no hook needed. `InstructionsLoaded`
exists for this and is not wired here.

Two more corrections from the same fetch: `@path` imports do NOT save context
("imported files load at launch"); and AGENTS.md is not loaded at all — "Claude Code
reads CLAUDE.md, not AGENTS.md" — so its bytes were wrongly counted in a cost table.
