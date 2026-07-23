---
source_url: "https://x.com/towards_AI/article/2078892237287801283"
type: article
title: "What the hell is graph engineering really"
author: "Towards AI (@towards_AI)"
captured_at: "2026-07-23"
retrieval: "logged-in Chrome (graphify fetch hit the X auth wall)"
---

# What the hell is graph engineering really

By Towards AI (@towards_AI) · Jul 19, 2026

AI engineering has a naming problem. Every useful idea gets about six months before someone declares it dead. Prompt engineering became context engineering. Context engineering became harness engineering. Then everyone started talking about loop engineering.

Peter Steinberger (creator of OpenClaw) posted nine words about "graph" that caused immediate confusion. There is **no new product called Graph**, and loops are not going anywhere. But something real happened: over the past few months we learned how to make **one** agent keep working (the loop). Now we need to design what happens when **many** agents, checks, branches, retries, and human decisions work together. That larger structure is a **graph**.

## Loop vs prompt
A prompt asks an AI to do something once. A loop gives it a goal, lets it act, checks the result, and sends it back to work when the result is wrong. "Fix the type errors" becomes: run the type checker → read errors → fix → run again → stop when it passes or stops making progress.

A real loop needs three things:
- **An external verifier.** A test passes or fails; a build compiles or not. If the same agent writes the work AND decides whether the work is good, you have built a very expensive machine for agreeing with itself.
- **State outside the conversation** — remember what it tried, what failed, which artifacts changed.
- **An exit** — success is one exit, a hard limit is the other.

(Hanako's loop-engineering article: verifier + persistent state + stop condition turn repeated prompting into a working system.)

## A graph is a map of who does what next
Individual pieces of work are **nodes** (an agent investigating one file, a test suite, a reviewer, an approval step, a stored artifact, or an ordinary deterministic script). Connections are **edges** — an edge says what can happen next (carry data, express a dependency, or activate only when a condition is true). Several nodes can run at once; results converge into one reviewer; a failed check sends work back to a fixer; an external event can start an entire section of the graph.

Example — a code-review system: a new PR fans out to several audit agents → findings go to a verifier → confirmed problems go to a fixer → then the test suite; if tests fail, work goes back to the fixer; if they pass, the review is published. **The graph is the whole system; the loop is only the retry path between fixing and testing.** This is why "loops versus graphs" is the wrong argument — **graphs have loops.**

## Isn't this just workflow engineering?
Mostly yes. Anthropic's 2024 "Building effective agents" distinguished workflows (LLMs+tools follow predefined code paths) from agents (the model decides how to proceed), and laid out patterns: prompt chaining (a straight path), routing (a conditional branch), parallelization (fan out + collect), orchestrator-workers (create tasks dynamically + delegate), evaluator-optimizer (loop until it improves). Draw any of them and you get a graph. **Graph engineering is not a replacement — it means drawing the full map of how work moves between agents, tools, and checks.** Workflow engineering asks what happens inside one process; graph engineering zooms out: how the larger system connects, what triggers each part, what information moves, and who decides when they disagree. That information is the system's **state** (finished tasks, each agent's output, failed checks, human approvals). The graph is the map of possible paths; the state says where the system is on that map. The underlying CS is not new (workflow engines, DAG schedulers, state machines, distributed systems).

## Why now
What changed is the kind of work inside some nodes. A normal workflow step follows fixed rules; an agent interprets the task from its current context, so it can misunderstand or choose differently next run. One chat window hides a surprising amount of bad architecture: the model decides what happens next, results pile up in context, verification is mixed with generation, state exists wherever the conversation happens to remember it. That works for small jobs but gets fragile across hundreds of files, several repos, multiple data sources, or hours of work. Graphs force the relationships into the open — you must decide: which work runs in parallel; what state crosses between nodes; which result counts as evidence; who can reject a result; which failures retry; what survives a restart; where human approval belongs; how much the system can spend before it stops. When the graph is written as code, its weak points become findable, and you fix the workflow itself instead of hoping the model remembers.

## Claude Code gave the graph a runtime
Claude Code's **dynamic workflows**: Claude writes the plan as a JavaScript program that can spawn subagents, run independent jobs concurrently, send results through review, and retry failed work; a background runtime follows the program so Claude does not direct every step in the chat. "A workflow moves the plan into code." Mario Zechner's advice: start with Anthropic's dynamic workflows, recognize the directed graph underneath, then think about marrying triggering (sub-)graphs via external events — which pushes the idea beyond one Claude Code run.

## DAGs, cycles, and why the difference matters
Some workflows are DAGs (directed = each connection has a direction; acyclic = never returns to an earlier node). A research workflow can be a DAG — every stage runs once, nothing travels backward. Add a verifier that rejects unsupported claims and sends them back → the workflow has a **cycle**. Cycles introduce cost, state, and stopping problems a DAG does not have: the graph must know which work can be reused, which branches rerun, and when repeated failures stop the run.

## A useful graph does more than move work
Execution side = what runs next (branches, parallel work, reviews, retries, handoffs). But the graph can also check whether the work is still moving toward the right goal (Carlos E. Perez). Example: a support agent rewarded for closing tickets quickly learns to close difficult conversations instead of solving them — **Goodhart's law in production**: once a measure becomes the target, the system improves the measure without improving reality. The control side connects the loop to other signals (customer retention, reopened tickets); if tickets close faster while retention falls, the graph flags the conflict and asks a human. One graph, two jobs: execution closes tickets, control checks whether customers were helped. Good graph engineering connects both.

## Graphs can still produce extremely organized nonsense
Adding more agents does not create independent judgment. Twenty agents using the same model, reading the same flawed context, checking the same broken metric can agree at industrial scale — a graph multiplies mistakes as efficiently as useful work. A graph can be circular in a dangerous way: agent A checks a report against another report; an audit agent checks both against a dashboard; the dashboard was built from the same data. Every node agrees; nothing touches reality. It looks well-governed because the diagram has reviewers everywhere — it is still wrong.

**Reality anchors** — some evidence MUST come from outside the agent system: tests that actually ran, money that reached the bank, customers who stayed, measurements from the physical system, rules the optimizer cannot quietly rewrite, human judgment about what "better" means. Without anchors, a graph is a larger hallucination with better project management.

## What a graph engineer does
The same work good distributed-systems / workflow engineers have done for years, applied to agents: design boundaries; decide which tasks deserve probabilistic agents vs ordinary code; define the state passed between workers; separate the maker from the checker; choose retry rules, timeouts, budgets, permissions, stop conditions; decide who has authority (can a reviewer block a deployment? can an optimizing agent alter its own tests? which external events are trusted? when must the system wake a human?).

Prompt engineering = communicating intent to a model. Loop engineering = building a process that keeps pursuing that intent. **Graph engineering = designing the relationships between those processes.** The name is new; most of the hard problems are not.

## Start with the loop
Do not respond by building a 40-agent graph. Start with one recurring task: give it a real verifier, store its state somewhere inspectable, add a hard stop, run it enough to understand how it fails. Then draw what has to happen around it (a second reviewer, five parallel branches, a security check with veto power, a failed test that restarts one branch, a PR/webhook/scheduled trigger). At that point you have a graph — you did not abandon the loop, you gave it neighbors, supervision, memory, and somewhere honest to report failure.
