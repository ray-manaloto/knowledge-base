---
type: "query"
date: "2026-08-28T05:19:44.895685+00:00"
question: "How should a Claude/Codex agent team optimise limited Fable-5 tokens and the Claude↔Codex channel, with graphify on the openai-cli backend as the end goal? (round 2, 2026-08-28)"
contributor: "graphify"
outcome: "useful"
---

# Q: How should a Claude/Codex agent team optimise limited Fable-5 tokens and the Claude↔Codex channel, with graphify on the openai-cli backend as the end goal? (round 2, 2026-08-28)

## Answer

The team does not need new roles; it needs a typed, file-first transport with a VERIFIED executor id. Executed on codex-cli 0.150.1 this round: `--output-schema` works (happy path), `exec resume --last` recovers a SIGTERM'd run, `--json` carries NO timestamps (clock recommendation refuted), `codex mcp-server` is DEPRECATED on the installed binary (transport = `codex exec` + schema + resume; `app-server` deferred). The "8 in 8" resend claim narrowed to 8/55; "one resend recovers the report" refuted (2/4 failed) — the report FILE on disk is the delivery channel. New failure class: a lane substituting itself (#559); fix = a codex session id the architect verifies with `codex exec resume <id>`, not a self-reported field (fable-advisor). The Fable consult conflict is settled precedence: Ray's 2026-08-27 directive governs; the gate reads a capped spec file. The openai-cli backend is already wired: `mise run kb-graphify-native-extract -- --backend openai-cli` dry-run rc 0; sync the four governance surfaces first, then a ~25-file serial slice with GRAPHIFY_OPENAI_CLI_EFFORT exported and --api-timeout > 722 s. Ray's corrections: "A: stop" stopped only the PyO3 binding; a FULL CLI for the aggregated-search plugin is the deliverable; the marketplace step was never started. Report: docs/research/reports/2026-08-28-agent-team-transport.md; page: docs/artifacts/the-team-is-a-transport.html.


## Outcome

- Signal: useful