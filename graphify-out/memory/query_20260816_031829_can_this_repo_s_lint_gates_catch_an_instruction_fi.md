---
type: "query"
date: "2026-08-16T03:18:29.576769+00:00"
question: "Can this repo's lint gates catch an instruction file that contradicts a core invariant?"
contributor: "graphify"
outcome: "useful"
---

# Q: Can this repo's lint gates catch an instruction file that contradicts a core invariant?

## Answer

No. Every one of them was working correctly and none of them can read meaning.

Commit 0367588e added 23 instruction files containing, at
`.agents/skills/kb-curator/SKILL.md:56`:

    **2. Codex only — NEVER Gemini or any auto-detected key.** All LLM work is
    Codex …

against do-not.md rule 4 and CLAUDE.md mandate 2. It also manufactured
Codex-cli, ericbuess/Codex-docs, code.Codex.com, ~/.Codex/projects,
[tool.Codex] and .Codex/skills/** — none of which exist.

That commit passed, cleanly:

  lint (every hk step)   agnix --strict: 0 errors, 0 warnings
  gitleaks: 31.15 MB scanned, no leaks     md_size_budget: 34 files
  skill_lint: 10 skills checked            typos, rumdl, taplo, ty, ruff

skill_lint is the closest thing to a reader and it scans .claude/skills/* only,
so it never looked at the tree where this happened.

The cold cross-family review lane caught it and rated it HIGH.

The durable point: a syntax gate cannot detect an inverted claim, because the
inverted claim is well-formed. Adding files that INSTRUCT an agent is a different
risk class from adding files that RUN, and this repo's gates are built for the
second. Before committing generated or mirrored instruction text, diff it against
its source and read the diff — the tooling will not.


## Outcome

- Signal: useful