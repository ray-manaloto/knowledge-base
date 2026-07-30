# Agent Artifact Conventions: Where Working Files Go

Agent working artifacts live under **`.agent/`** (gitignored, machine-local).
Durable artifacts that should survive a clone are **tracked**, and live in the
repo proper — never in `.agent/`. Do not create ad-hoc directories in either.

> **Renamed from `.omc/` (2026-07-25).** The old tree was named after the
> `oh-my-claudecode` plugin, which is **not enabled** in this repo — a
> convention named for a tool nothing loads. `.agent/` is vendor-neutral and
> matches the `AGENTS.md` naming this repo already uses. Verified before
> adopting: Claude Code neither claims nor reserves `.agent/` (control-armed
> over its full docs corpus — `.agent/` → 0 hits while `CLAUDE.md` → 439, so
> the probe discriminates). Claude Code owns `.claude/**` exclusively.

## The local tree (gitignored)

| Path | Purpose |
|------|---------|
| `.agent/state/` | General state files (session ids, mode tracking) |
| `.agent/notepad.md` | Working notepad — findings as you go |
| `.agent/plans/` | Plans and session handoffs (`session-{date}[-letter].md`) |
| `.agent/logs/` | Execution logs, pipeline traces |
| `.agent/brain-audit.md` | The advisory SessionEnd transcript audit |
| `.agent/kb/review/receipt-<sha>.json` | One `kb-review` receipt, keyed to the exact commit — what **both `kb-ship` and `kb-land`** gate on (`land` is the backstop for a PR that reached the remote without `ship`). An ancestor's receipt also covers HEAD when everything committed since is in `review.EXEMPT_PATHS` (`graphify-out/memory/**`, `docs/goals/README.md`), which is what lets a round commit its own `kb-remember`/`kb-goal-outcome` output (#66) |
| `.agent/kb/review/reports/review-<sha>-<lane>.md` | That review's per-lane reports; the receipt refuses to name a lane that left none. `<lane>` is the lane with any `:variant` **stripped** — `cold:codex` leaves `…-cold.md` |

`.agent/` is in the real **`.gitignore`**, not a per-clone
`.git/info/exclude`. That distinction is the reason this rule exists in its
current form: the old `.omc/*` exclusion lived in `.git/info/exclude`, which
does not survive a fresh clone, so every artifact anyone actually wanted
tracked had to be force-added with `git add -f`. An ignore rule that only
exists on one machine is not a convention, it is an accident.

## Durable artifacts are TRACKED, and do not live in `.agent/`

If it should survive a clone, it belongs in the repo:

| Path | What belongs there |
|---|---|
| `docs/` | Authored documentation and design specs |
| `docs/currency/` | The committed tool-currency run log |
| `sources/*.manifest` | A github source pin (url + ref + SHA) |
| `sources/media/` | Vendored non-refetchable sources (transcripts, PDFs) |
| `sources/extractions/*.json` | Committed host-agent extraction chunks |
| `graphify-out/memory/` | Authored work-memory — the ONE committed part of a derived tree |

**Corpus content is never rewritten to match a rename.** `sources/**` records
what a source said at ingestion time, including paths that have since moved.
Editing it to keep links tidy would falsify the provenance the manifest exists
to guarantee. Leave it; fix the pointer in the authored doc instead.

## Inputs and derived output

| Path | Nature |
|---|---|
| `raw/` | `kb-add` fetch landing zone — an INPUT, gitignored, never hand-authored |
| `graphify-out/` | DERIVED — rebuilt by `kb-build`/`kb-artifacts`; only `memory/` is committed |
| `sources/<name>/` | Gitignored clone, re-fetched from its pinned manifest SHA |

## Rules

1. **No ad-hoc directories.** Do not create `.agent/temp/`, `.agent/output/`,
   or any path not listed above. Map your artifact to the closest one.
2. **A handoff is a plan.** `.agent/plans/session-{date}.md`.
3. **Findings go to the notepad as you go** — see `notepad-enforcement.md`.
4. **A finding that should outlive the session goes in the GRAPH**
   (`mise run kb-remember`, or a real source), not in `.agent/`. `.agent/` is
   swept away by any `git clean -xdf` and does not exist on another machine.
5. **Skills live in `.claude/skills/<name>/SKILL.md`**, never under `.agent/` —
   Claude Code's loader does not scan anywhere else. Same for `.claude/rules/`
   and `.claude/agents/`.

## Why this rule cannot be `paths:`-scoped

It is **creation-triggered**: it governs *where to create* an artifact, so you
never read the file first. A scoped version would be absent exactly when it is
needed. See `md-size-budgets.md` § "Scoping: the trigger test".

## See also

- `notepad-enforcement.md` — the running findings layer.
- `agent-report-persistence.md` — the full-fidelity layer.
- `research-repo-enumeration.md` — what every persisted report must end with.
