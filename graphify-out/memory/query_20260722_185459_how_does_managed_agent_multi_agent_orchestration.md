---
type: "query"
date: "2026-07-22T18:54:59.687174+00:00"
question: "How does managed-agent multi-agent orchestration + dynamic-workflow subagent cross-checking work (for grounding a Fable-5 orchestrator)?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["ma_orchestration_doc", "ma_outcomes_doc", "cc_agents_dynamic_workflows", "cc_agents_cross_check_verification", "sdk_overview_subagents"]
---

# Q: How does managed-agent multi-agent orchestration + dynamic-workflow subagent cross-checking work (for grounding a Fable-5 orchestrator)?

## Answer

One coordinator delegates to up to 20 context-isolated agent threads (own model/prompt/tools, shared sandbox/fs/vault), single level of delegation; define-outcomes adds rubric-graded self-evaluation loops. Dynamic workflows are a script running many subagents and cross-checking results. Doc nodes now cross-link to deer-flow orchestrator code (TokenBudgetConfig, CircuitBreakerConfig, lead_agent, SubagentsAppConfig).

## Outcome

- Signal: useful

## Source Nodes

- ma_orchestration_doc
- ma_outcomes_doc
- cc_agents_dynamic_workflows
- cc_agents_cross_check_verification
- sdk_overview_subagents