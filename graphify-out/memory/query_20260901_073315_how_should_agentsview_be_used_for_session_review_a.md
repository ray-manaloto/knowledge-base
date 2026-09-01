---
type: "query"
date: "2026-09-01T07:33:15.256686+00:00"
question: "How should agentsview be used for session review across all agents working on this project?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should agentsview be used for session review across all agents working on this project?

## Answer

# Using agentsview for session review — what this round established

**Adopted, shipped, landed**: agentsview 0.41.1 pinned `github:kenn-io/agentsview`,
wrapped by `mise run kb-session-search` (`kb_setup.agentsview`). PRs #644 and #645.

## What it can and cannot answer, measured

- Reads BOTH `~/.claude/projects/` and `~/.codex/sessions/`. Control-armed:
  searching this session's own lanes returns hits where a bogus term returns 0.
- Indexes Claude SUBAGENT lanes as first-class sessions (`agent-a<lane>-<hash>`),
  which `kb-session-select` structurally cannot see: 174 top-level transcripts
  vs 1,193 subagent transcripts.
- **Cannot** answer reasoning effort or sandbox mode: `effort`/`sandbox` -> 0 of
  483 columns. REQUESTED settings are provable from the parent's recorded
  dispatch (`session search --in tool_input`); APPLIED settings have no source.
- **No OTel ingestion** — three independent arms agree. The binary is saturated
  with OpenTelemetry on the EXPORT side (4,195 strings) with nowhere to put an
  ingested span.
- Parenting is entirely WITHIN-FAMILY: claude->claude 1,552, codex->codex 1,438,
  ZERO cross-family edges. A `codex exec` shelled from a Claude lane is never
  attributable to its round.

## The mechanism defects found

- `agentsview sync` is NOT concurrency-safe: two simultaneous syncs -> one rc=1
  "sync already in progress". So "every lane queries sessions itself" needs a
  single-writer seam first.
- An evidence TOKEN cannot bind a report to a session: it propagates into
  callers, siblings and nested agents. A token search returns the propagation
  set. It cannot even be control-armed — searching for a token types it in.
- `skipped_files` holds 425 rows with NO reason column, so a green sync plus
  `"searched": true` does not prove coverage.

## The plan

`.agent/kb/reports/agents/plan-agentsview-session-review-v3.md` — 747 lines,
nine ordered steps, 46-item checklist. Verdict MERGE not replace, with each
overlap decision a consequence of a measurement.


## Outcome

- Signal: useful