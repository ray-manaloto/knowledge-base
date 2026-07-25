# OMC Directory Conventions: Use Standard Paths

All working artifacts must go in the correct `.omc/` subdirectory. Do not create
ad-hoc directories under `.omc/`. The standard structure is:

| Path | Purpose | Examples |
|------|---------|---------|
| `.omc/state/` | General state files | Active mode tracking, session IDs |
| `.omc/state/sessions/{id}/` | Per-session state | Deep-interview state, trace state |
| `.omc/notepad.md` | Working notepad | Agent findings, intermediate notes |
| `.omc/kb/` | Persisted agent reports + raw sources | `reports/agents/<name>.md`, `raw/<slug>.md` |
| `.omc/plans/` | Plans and handoffs | Session resume plans, consensus plans |
| `.omc/specs/` | Specs from deep-dive/interview | `deep-dive-{slug}.md` |
| `.omc/research/` | Research artifacts | External context findings, doc lookups |
| `.omc/logs/` | Execution logs | Agent run logs, pipeline traces |

**Skills do NOT live under `.omc/`.** Claude Code only auto-loads project
skills from `.claude/skills/<name>/SKILL.md`. See rule 5 below.

**Corpus content does NOT live under `.omc/` either.** This repo has a separate,
committed, reproducible tree for that — mixing the two is the mistake this
section exists to prevent:

| Path | What belongs there |
|---|---|
| `sources/*.manifest` | A github source pin (url + ref + SHA); the clone is gitignored |
| `sources/media/` | Vendored non-refetchable sources (transcripts, PDFs, docs) |
| `sources/extractions/*.json` | Committed host-agent extraction chunks |
| `raw/` | `kb-add` fetch landing zone — an INPUT, gitignored, never hand-authored |
| `graphify-out/` | DERIVED. Only `memory/` is committed; everything else is rebuilt |
| `docs/currency/` | The committed tool-currency run log |

A research finding that should outlive the session belongs in the graph
(`kb-remember`, or a real source), not in `.omc/`.

## Rules

1. **No ad-hoc directories**: Do not create `.omc/handoffs/`, `.omc/temp/`,
   `.omc/output/`, or any directory not listed above. Map your artifact to the
   closest standard path.

2. **Session handoffs go in plans/**: A handoff is a "what to do next" document
   — that's a plan. Name convention: `session-{date}.md` or
   `session-{date}-{letter}.md`.

3. **Agent findings go in notepad**: Not in memory, not in standalone files.
   Append to `.omc/notepad.md`. See `notepad-enforcement.md`.

4. **Specs from deep-dive/interview go in specs/**: Not in plans, not in research.

5. **Learned skills go in `.claude/skills/<name>/SKILL.md`**: NOT in
   `.omc/skills/` (Claude Code's skill loader does not scan that path). Each
   skill is a directory containing a `SKILL.md` with YAML frontmatter (`name`,
   `description`, and optionally `user-invocable`, `triggers`,
   `argument-hint`). The frontmatter `name` should match the directory name so
   slash-invocation and auto-loading stay consistent.

## Why this rule cannot be `paths:`-scoped

It is **creation-triggered**: it governs *where to create* an artifact, so you
never read the file first. A scoped version would be absent exactly when it is
needed. See `md-size-budgets.md` § "Scoping: the trigger test".
