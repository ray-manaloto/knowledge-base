---
name: orchestrator-routing
description: >-
  Unified cross-vendor routing doctrine for the Fable-5 architect: which executor
  lane (codex / antigravity / Claude-fallback) and reasoning-effort a delegated
  implementation subtask should run at, and how to fall back on exhaustion. Use
  whenever you are orchestrating with the adopted fable-orchestrator + antigravity
  plugins and must decide where to route a spec, how to review it cross-family, or
  what to do when a lane is unavailable. Ground every decision in the KB graph
  first (`mise run kb-query`). The Claude architect always plans + verifies; only
  execution is delegated.
---

# orchestrator-routing — Fable-5 architect + codex + antigravity lanes

The adopted plugins each cover one vendor lane; this doctrine unifies them so the
**Fable-5 architect** routes across **both** and keeps a Claude terminal fallback.
The architect emits judgment and specs, never the bulk of the code, and **verifies
the evidence itself before declaring done** — a lane's self-report is never proof.

- **codex lane** — `fable-orchestrator`'s `codex-implementer` (GPT-5.6 Sol, high reasoning).
- **antigravity lane** — the `antigravity` plugin's `/antigravity:delegate` (Google Antigravity CLI
  `agy`, Gemini 3.x).
- **Claude fallback** — a Claude Opus subagent (Agent tool, `model: "opus"`), the always-available
  terminal lane.

## Ground the decision in the graph FIRST

Before any non-trivial routing/fallback call, query this repo's KB graph — the doctrine was extracted
into it from fable-advisor / fable-orchestrator / the migration + fallback sources:

```
mise run kb-query -- "advisor executor routing: cheapest adequate lane, five-part spec, Fable-5 to Opus fallback"
```

Load-bearing nodes: `fadv_architect_pattern`, `fadv_routing_table`, `fadv_five_part_spec`,
`fadv_cost_discipline`, the linas `Fable-5→Opus-4.8 fallback pattern`, and the mindstudio
`Opus/Sonnet as Executor`.

## Routing table (route by where JUDGMENT lives, not by task size)

| Subtask class | Lane | Effort |
|---|---|---|
| Correctness-critical: concurrency, auth/security, migrations, subtle state, anything the spec can't fully pin | **codex** | high |
| Broad/mechanical, spec-fully-determined, or a second-opinion implementation for cross-vendor diversity | **antigravity** (Gemini 3.x) | medium–high |
| Both CLI lanes unavailable, or the task must stay in-family | **Claude Opus** subagent | high |
| Judgment / architecture / decomposition / final verification | **stays with the Fable-5 architect** | — |

Prefer a cheaper lane at higher effort over an expensive one at low effort. Cost discipline: the
architect emits the fewest tokens (specs + verdicts); the CLI lanes emit the most (code).

## The spec contract (context-free delegation)

Every delegated subtask carries a self-contained **six-part spec** — Objective, Files, Interfaces,
Constraints, Verification (a runnable command that proves it), Commit ownership — so the executor
implements without the architect's conversation. `fable-orchestrator` supplies this; match it for the
antigravity lane.

## Cross-family review

A behavior-bearing diff gets a **cold review from a different model family than the implementer**
(codex implemented → review with a Gemini/antigravity or Claude lens; antigravity implemented →
codex or Claude lens) — a same-family reviewer shares the author's blind spots. Reviewer sees a ref,
not a diff file; findings as `severity | claim | file:line`; the architect runs a refutation pass;
max two respec rounds, then surface to the user.

## Fallback ladder (cheapest correct recovery first; every step announced, never silent)

1. **Retry** transient `429`/`500`/overload with backoff (a burst must not trip the circuit breaker).
2. **Degrade effort** on the same lane if the ceiling is latency/cost, not capability.
3. **Fallback lane**: chosen CLI lane unavailable → the *other* CLI lane (cross-vendor separation
   survives) → **always a Claude Opus subagent** as the terminal lane.
4. **Split** the spec so each part fits the budget.

Never fall back to a weaker lane for a correctness-critical subtask without flagging the quality risk.
Verification and review do **not** relax under fallback — a substitute lane makes them matter more.

## Guardrails

- The architect + all KB/graphify work stay **Claude**; only implementation is delegated cross-vendor.
- A completion without the lane's structured report (with reap evidence) is not a success.
- Availability is discovered at run time, not declared — a missing CLI falls back loudly.
