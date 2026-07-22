---
type: "query"
date: "2026-07-22T23:00:21.795348+00:00"
question: "What doctrine grounds the Fable-5 orchestrator (phases 3-4) built from the KB?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["fadv_architect_pattern", "fadv_routing_table", "fadv_five_part_spec"]
---

# Q: What doctrine grounds the Fable-5 orchestrator (phases 3-4) built from the KB?

## Answer

Advisor/executor: Fable-5 architect emits judgment+specs only, routes each impl task to cheapest-adequate lane via a five-part context-free spec, verifies evidence before done (fable-advisor, mindstudio Opus/Sonnet-as-executor). Effort low..max per-model, default high; Fable-5 low often beats prior xhigh; haiku background (model-config, prompting-fable-5). Fallback Fable-5->Opus-4.8 'Opus-in-chair' on limit exhaustion; circuit-breaker/budget/limiter; 429/500 retry-to-limit, burst!=trip (linas, fable5-orchestrator, deer-flow). Long-running: test oracle + 'the queue writes itself' self-feeding verification loop + define-outcomes rubric (long-running-Claude, migration, define-outcomes). Delegation via context-isolated subagents / Workflow fan-out (agents, workflows, multiagent-orchestration).

## Outcome

- Signal: useful

## Source Nodes

- fadv_architect_pattern
- fadv_routing_table
- fadv_five_part_spec