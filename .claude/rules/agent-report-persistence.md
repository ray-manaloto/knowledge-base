# Agent Report Persistence: Verbatim, At Receipt

Every **findings-bearing** subagent report — research, review, audit,
verification, extraction, or any report carrying findings, decisions, evidence
tables, or probe output — MUST be persisted **verbatim** to disk at the moment
it is received, not summarized into the notepad and not deferred to session
end.

## Why this rule exists

An 11-agent research sweep (dotfiles, 2026-07-05) produced 13 detailed reports
— syntax sketches, `file:line` misconfiguration tables, probe transcripts, a
backend status matrix. The notepad got condensed summaries as the work
progressed, but the full reports existed **only in the session's context
window** — one `/clear` away from being lost.

Condensation is lossy in exactly the way that hurts later: the summary
keeps the conclusion but drops the evidence, the exact command lines, and
the `file:line` anchors the implementing session needs.

**This repo's extraction fan-out is the highest-stakes case.** The `kb-extract`
workflow spawns subagents that each read a raw file and return `{nodes,edges}`.
That output is not a summary of work — it *is* the work, it cost real Claude
tokens, and it is the only LLM path in the corpus. Losing one means paying for
it twice.

## Rules

1. **Persist at receipt, into `.agent/kb/`.** When a findings-bearing agent's
   final report arrives, write it verbatim to
   `.agent/kb/reports/agents/<agent-name>.md` in the SAME turn — before acting on
   its content. Sources the agent fetched go to `.agent/kb/raw/<slug>.md`.

   **One exception, and it is a stricter one: `kb-review` lane reports go to
   `.agent/kb/review/reports/review-<sha>-<lane>.md`.** Keyed by commit rather
   than by agent name, because `kb_setup.review` *reads* them — a receipt that
   names a lane which left no report is refused, so the filename is a contract
   and not a convention. An agent name is not unique across commits and could
   not carry that. Everything else here still applies: verbatim, at receipt.

   `<lane>` is the lane with any **`:variant` stripped** (`report_path` →
   `_lane_prefix`): a lane recorded as `cold:codex` must leave `…-cold.md`, not
   `…-cold:codex.md`. Following this rule literally without that caveat writes a
   file the gate cannot see, and the refusal then reads as "the lane never ran".
   (#60)

   **The report must also NAME `<sha>`** — full, or its first 12 characters —
   somewhere in its body, or the receipt is refused (#56). Verbatim persistence
   is what makes that cheap: a lane asked to state the commit it reviewed says so
   in its report, and copying it forward to a different SHA then fails visibly
   rather than silently standing as evidence for a commit nobody claimed it was
   about.

1b. **PROMOTE it to `docs/research/reports/` once it is load-bearing.** `.agent/`
   is gitignored: it dies with a fresh clone or any `git clean -xdf`. That is
   right for scratch and wrong for a report something tracked now cites —
   `currency.toml`'s `[tool.mise]` block rests on the v2026.7.x review, and a
   citation to a file only one machine can open is not a citation. Promotion is
   a COPY (the `.agent/` original stays disposable) and it is still verbatim.
   `docs/research/README.md` indexes them and states the no-normalising rule.

   **Extraction chunks are the exception, and go somewhere better:** a
   `{nodes,edges}` chunk is corpus input, not a report. Assemble it with
   `mise run kb-assemble -- <name> <chunk...>` and commit it under
   `sources/extractions/` — a tracked, reproducible location. `.agent/**` is
   gitignored and does not survive a fresh clone.

2. **Verbatim means verbatim.** Keep the agent's tables, evidence links,
   probe output, and repos-touched enumeration intact. Annotating
   decisions inline afterwards (e.g. "DECIDED: option A") is encouraged;
   trimming evidence is not.

3. **Instruct agents to persist INCREMENTALLY, not at the end.** Tell a
   research or extraction delegation to write each source as it fetches it and
   to write its report early and update it. Two agents that held everything in
   memory died silently after ~40 minutes and left **nothing**; re-dispatched
   with an incremental instruction, they produced output within minutes. An
   agent that dies having written 13 of 20 sources leaves 13. Durable capture
   must be incremental, never end-of-run.

4. **Notepad entries are additive, not substitutes.** The notepad gets the
   running condensed finding (`notepad-enforcement.md`); the artifact
   file holds the full report. Both, every time.

5. **Mechanical agents are exempt.** A delegation whose entire value is
   its immediate effect (a fan-out grep, a file-move helper) needs no
   artifact; its outcome is visible in the caller's next action. When in
   doubt, persist.

6. **Validate a chunk before you trust it.** `mise run kb-validate-chunks --
   <chunk.json>` is the cheap arm on an extraction agent's output — a chunk
   that parses is not a chunk that is well-formed.

## Applies to

All Agent-tool delegations and `Workflow` fan-outs in this repo — research
sweeps, `kb-extract` extraction passes, adversarial verification, code-review
agents, audit agents — regardless of which skill or workflow launched them.

## See also

- `notepad-enforcement.md` — the sibling rule for condensed as-you-go
  findings; this rule covers the full-fidelity layer.
- `research-repo-enumeration.md` — every persisted report ends with its
  repos-touched enumeration.
- `omc-directory-conventions.md` — where each artifact type lives, and why
  corpus content does not live under `.agent/`.
