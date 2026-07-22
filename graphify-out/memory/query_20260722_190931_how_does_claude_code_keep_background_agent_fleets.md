---
type: "query"
date: "2026-07-22T19:09:31.016447+00:00"
question: "How does Claude Code keep background agent fleets running unattended (durability primitives for an orchestrator)?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["yt_fleet_session_survival", "yt_fleet_ratelimit_resume", "yt_fleet_durability_network", "yt_fleet_auto_pr", "yt_fleet_end_babysitting"]
---

# Q: How does Claude Code keep background agent fleets running unattended (durability primitives for an orchestrator)?

## Answer

Subagents run in background by default (up to ~200), auto commit+push+draft-PR on completion; notifications on finish/needs-input; sessions survive stop/restart/daemon-replacement; interrupted agents resume; network drops don't abort turns (transient errors retry w/ backoff); rate-limited subagents report+resume instead of dying silently; MCP calls >2min auto-background; rewind reaches past /clear. These are the platform-level durability primitives an orchestrator can lean on.

## Outcome

- Signal: useful

## Source Nodes

- yt_fleet_session_survival
- yt_fleet_ratelimit_resume
- yt_fleet_durability_network
- yt_fleet_auto_pr
- yt_fleet_end_babysitting