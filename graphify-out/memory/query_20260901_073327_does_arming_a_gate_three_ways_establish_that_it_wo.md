---
type: "query"
date: "2026-09-01T07:33:27.949416+00:00"
question: "Does arming a gate three ways establish that it works?"
contributor: "graphify"
outcome: "corrected"
correction: "A gate armed only against a CONVENIENT mutation certifies nothing. Three times\nthis round I shipped something \"armed three ways\" that was blind to the\nREALISTIC break:\n\n1. `lane_recording` did not catch `--ephemeral` re-added to\n   `.claude/agents/kb-codex-advisor.md` — the file it exists to protect — because\n   that file's invocation spans backslash-continued lines. All three arms had\n   mutated the SINGLE-LINE patterns in a different file. Measured rc 0.\n2. The fixed version then leaked joins ACROSS fence boundaries, hiding a complete\n   `codex exec --ephemeral -\"` inside one quoted token.\n3. It scanned only `.claude/**`, so `.codex/agents/kb-codex-advisor.toml` — the\n   mirror codex's own CLI reads — kept instructing `--ephemeral` while the gate\n   reported every file clean.\n\nThe rule: a mutation must be the break that could REALLY happen, in the file the\ngate actually protects, in the SHAPE that file actually uses. A clean arm score\nis a statement about the tests, never about the premise.\n\nCorollary measured the same round: an inherited COUNT is not a measurement.\n`182` transcripts was carried from a lane report into the plan and never\nre-derived; the true figure was 174 and the 30-day retention wall had ALREADY\nfired rather than being \"about to\".\n"
---

# Q: Does arming a gate three ways establish that it works?

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

- Signal: corrected
- Correction: A gate armed only against a CONVENIENT mutation certifies nothing. Three times
this round I shipped something "armed three ways" that was blind to the
REALISTIC break:

1. `lane_recording` did not catch `--ephemeral` re-added to
   `.claude/agents/kb-codex-advisor.md` — the file it exists to protect — because
   that file's invocation spans backslash-continued lines. All three arms had
   mutated the SINGLE-LINE patterns in a different file. Measured rc 0.
2. The fixed version then leaked joins ACROSS fence boundaries, hiding a complete
   `codex exec --ephemeral -"` inside one quoted token.
3. It scanned only `.claude/**`, so `.codex/agents/kb-codex-advisor.toml` — the
   mirror codex's own CLI reads — kept instructing `--ephemeral` while the gate
   reported every file clean.

The rule: a mutation must be the break that could REALLY happen, in the file the
gate actually protects, in the SHAPE that file actually uses. A clean arm score
is a statement about the tests, never about the premise.

Corollary measured the same round: an inherited COUNT is not a measurement.
`182` transcripts was carried from a lane report into the plan and never
re-derived; the true figure was 174 and the 30-day retention wall had ALREADY
fired rather than being "about to".
