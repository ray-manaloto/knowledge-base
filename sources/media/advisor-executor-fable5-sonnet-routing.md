---
source_url: "https://www.mindstudio.ai/blog/advisor-executor-pattern-fable-5-sonnet-model-routing"
content_sha256: 785769d3b662cf2a573022092acc5ad49bfa3e15e375c3c706ce1449a60cdaad
content_chars: 19296
---

# How to Use the Advisor-Executor Pattern: Plan with Fable 5, Build with Sonnet

Cut AI costs by 50% using the advisor-executor pattern. Use Fable 5 for planning and code review, then switch to Sonnet for implementation and execution.

## Why Most AI Workflows Overspend on the Wrong Tasks

Running every step of your AI workflow through the most powerful model available sounds like the safe choice. In practice, it’s expensive and often counterproductive.

Heavy-reasoning models excel at complex planning, architectural decisions, and critical code review. But if you’re using that same model to write boilerplate functions, generate repetitive content, or handle straightforward data transformations, you’re paying a premium for work that a lighter model handles just as well — often faster.

The advisor-executor pattern fixes this. Use a high-capability model like Fable 5 as your “advisor” — the planning brain that reasons through problems, designs systems, and reviews outputs — then hand off implementation to Claude Sonnet as your “executor.” The result is a workflow that’s smarter where it needs to be and cheaper everywhere else.

This guide walks through exactly how to structure that pattern, when to apply it, and how to avoid the common mistakes that erode the cost savings.

## What Is the Advisor-Executor Pattern?

The advisor-executor pattern is a model routing strategy where two models play distinct roles in a single workflow:

- **The advisor**handles high-stakes reasoning tasks: planning, architecture, decomposition, and review.
- **The executor**handles high-volume implementation tasks: writing code, generating content, transforming data, and calling tools.

The advisor defines *what* to do and *how* to approach it. The executor does the actual work.

This isn’t just about cost. It’s also about quality. When you force a single model to both plan and execute, you often get mediocre results on both fronts — the model loses context, drifts from the original plan, or spends reasoning capacity on trivial steps.

Separating concerns keeps each model focused. The advisor can spend its full context window on strategy. The executor gets clear instructions and produces clean output without being burdened with high-level decisions.

### How It Differs from Simple Model Switching

Simple model switching means picking one model for one task type — always use Model A for code, always use Model B for text. That’s useful, but it’s static.

The advisor-executor pattern is dynamic and relational. The advisor actively shapes the executor’s inputs. It writes detailed plans, pseudocode, or step-by-step specs that the executor follows. The executor’s output might then get routed back to the advisor for review before moving downstream.

This creates a feedback loop — plan, execute, review, refine — where each model does what it does best.

## Why This Pattern Cuts Costs Without Cutting Quality

The economics of this approach are straightforward. High-capability reasoning models are typically priced at a significant premium over their faster counterparts. A workflow that routes 80% of token consumption to a cheaper executor model while keeping advisor calls to 20% can cut total inference costs by 40–60% depending on the task mix.

But raw cost isn’t the only variable. Consider:

**Latency.** Executor models are usually faster. If your workflow has sequential steps, running the execution layer through a lighter model reduces wall-clock time — which matters for real-time applications.

**Context efficiency.** Planning prompts can be concise, structured, and short. Execution prompts can be broken into isolated subtasks. When each model receives only the context it needs, you waste fewer tokens on irrelevant history.

**Error rates.** When the advisor produces a detailed, unambiguous plan before the executor starts, the executor makes fewer mistakes. Fewer mistakes means fewer retries, which compounds the cost savings.

The trade-off is workflow complexity. You’re managing two models, a handoff protocol, and potentially a review loop. That overhead is worth it at scale — not necessarily for simple one-shot tasks.

## Understanding Fable 5 as Your Advisor

Fable 5 is built for complex reasoning tasks that benefit from careful, multi-step thinking. It’s the right model for the advisor role because it handles ambiguity well, produces structured outputs consistently, and reasons reliably about constraints and dependencies before committing to a solution.

When you use Fable 5 as your advisor, you’re typically asking it to do one of three things:

### 1. Decompose a Complex Problem

Before any code gets written or content gets generated, Fable 5 breaks the task into discrete, sequenced subtasks. Each subtask becomes a clear instruction set for the executor. Good decomposition means the executor never has to make a judgment call — it just follows the spec.

For example: “Build a data pipeline that ingests CSV files, validates schema, deduplicates records, and writes to a Postgres table” becomes four executor prompts, each with clear inputs, outputs, and edge case handling already thought through.

### 2. Review and Validate Executor Output

The executor produces output fast. Fable 5 checks whether it’s right. This is particularly valuable in code generation workflows — the executor writes the function, Fable 5 reviews it against the original requirements, flags issues, and either approves or sends it back for revision.

This is more effective than asking the executor to self-review, because the executor tends to rationalize its own output rather than critique it critically.

### 3. Handle Escalations

When the executor encounters an ambiguous case — an unexpected input format, a conflict in the requirements, a schema mismatch — it escalates to the advisor. Fable 5 resolves the ambiguity and returns a decision. The executor continues.

This keeps the main execution loop fast while ensuring hard problems get proper reasoning.

## Understanding Claude Sonnet as Your Executor

Claude Sonnet is Anthropic’s mid-tier model — fast, cost-effective, and capable of handling a wide range of implementation tasks well. It’s a strong executor for several reasons:

- It follows detailed instructions reliably, especially when the advisor has pre-structured the task.
- It handles code generation, editing, and transformation competently across common languages and frameworks.
- It produces consistent output when given clear format specifications.
- It’s significantly cheaper per token than high-end reasoning models.

Sonnet works best when it receives:

- Clear, specific instructions (not open-ended prompts)
- A defined output format
- Bounded scope — one thing at a time, not a sprawling multi-part problem

The advisor-executor pattern delivers exactly those conditions. Because Fable 5 has already handled the ambiguity and complexity, Sonnet receives clean, structured tasks it can execute reliably.

Where Sonnet struggles is with genuinely novel problems that require careful reasoning before any implementation begins. That’s the advisor’s job.

## How to Implement the Advisor-Executor Pattern

Here’s a step-by-step breakdown of building this pattern into a real workflow.

### Step 1: Define the Task Boundary

Before writing any prompts, decide what constitutes an “advisor-level” task versus an “executor-level” task in your specific context.

Common advisor tasks:

- Breaking a high-level goal into implementation steps
- Designing a data schema or API contract
- Reviewing code for correctness, security, or performance
- Resolving conflicts between requirements
- Synthesizing complex research into a structured brief

Common executor tasks:

- Writing functions from a spec
- Generating content from an outline
- Transforming or reformatting data
- Filling in boilerplate
- Making targeted edits to existing code

Document this boundary. It becomes your routing logic.

### Step 2: Design the Advisor Prompt

The advisor prompt should ask Fable 5 to produce a structured output the executor can consume directly. This is not a vague planning session — it’s prompt engineering aimed at generating an executable spec.

A good advisor prompt structure:

```
You are a senior software architect. Given this high-level task:
[TASK DESCRIPTION]
Produce a step-by-step implementation plan with:
- A numbered list of subtasks
- For each subtask: inputs, expected output, and any constraints
- Any edge cases the implementer should handle
- The order of operations
Do not write any code. Only output the plan.
```
The more structured the output format, the easier the handoff to the executor.

### Step 3: Parse and Distribute Subtasks

Once Fable 5 returns the plan, your workflow needs to extract individual subtasks and send them to the executor in sequence (or in parallel, if they’re independent).

## Other agents ship a demo. Remy ships an app.

Real backend. Real database. Real auth. Real plumbing. Remy has it all.

In a no-code workflow tool, this typically means parsing the advisor’s structured response and feeding each item into an executor step. In code, you’d iterate over the plan and call the executor model for each item.

Keep executor prompts tight:

```
You are an expert Python developer. Implement the following function exactly as specified:
Task: [SUBTASK FROM PLAN]
Input: [DESCRIBED INPUT FORMAT]
Output: [DESCRIBED OUTPUT FORMAT]
Constraints: [ANY CONSTRAINTS]
Write only the function. No explanation.
```
### Step 4: Route Executor Output Back for Review

After the executor completes a subtask (or the full task), route the output back to Fable 5 for review. The review prompt should be specific — don’t ask “is this good?” Ask targeted questions:

```
Review the following [code/content/plan]:
[EXECUTOR OUTPUT]
Check for:
1. Correctness against the original requirements
2. Edge cases not handled
3. Any logical errors
Output a structured review:
- Status: APPROVED or NEEDS_REVISION
- Issues: [list any problems, or "None"]
- Suggested fixes: [specific fixes if needed]
```
If the status is NEEDS_REVISION, feed the executor output plus the suggested fixes back into the executor for another pass.

### Step 5: Terminate the Loop

Set a maximum number of review cycles (usually 2–3) to prevent infinite loops. If the advisor is still flagging issues after the limit, route to a human or log for manual review.

Most tasks resolve in one review cycle when the initial advisor plan is detailed enough.

## Real-World Use Cases for the Advisor-Executor Pattern

### Code Generation Pipelines

The advisor breaks a feature request into functions, defines the interface contracts, and specifies the test cases. The executor writes each function. The advisor reviews each one. This is faster than prompting a single model to write an entire module and self-review.

### Long-Form Content Production

The advisor creates a detailed outline with section goals, word counts, key points, and tone guidelines. The executor writes each section independently. The advisor does a final consistency pass. This keeps long articles coherent without burning a large context window on a single generation call.

### Data Transformation and ETL

The advisor designs the transformation logic and handles edge cases. The executor writes the transformation code or applies it to batches of records. The advisor reviews a sample output for accuracy.

### Automated Code Review

The advisor reviews pull requests against a defined checklist. The executor applies fixes to flagged lines. The advisor re-reviews. This works well in CI/CD pipelines where you want systematic review without human bottlenecks.

## How to Build This Pattern in MindStudio

MindStudio is a no-code platform that makes the advisor-executor pattern straightforward to implement without writing infrastructure code. You have access to Fable 5, Claude Sonnet, and 200+ other models in the same workflow builder — no separate API accounts or keys required.

Here’s how the pattern maps to MindStudio’s workflow builder:

- **Create a workflow**with a starting trigger (manual input, webhook, API call, or scheduled run).
- **Add an AI step using Fable 5**configured with your advisor prompt. Set the output format to structured JSON so the next step can parse it cleanly.
- **Add a loop or sequential step**that iterates over the advisor’s subtask list.
- **Inside the loop, add an AI step using Claude Sonnet**configured with your executor prompt, injecting the current subtask from the advisor’s output.
- **Add a review AI step using Fable 5**that takes the executor’s output and returns a structured review (APPROVED / NEEDS_REVISION).
- **Add a conditional branch**— if APPROVED, move to the next subtask. If NEEDS_REVISION, pass the feedback back to the executor step and retry.

## One coffee. One working app.

You bring the idea. Remy manages the project.

Because MindStudio handles model routing, rate limiting, and retries automatically, you don’t have to manage that infrastructure. You focus on the prompt design and workflow logic.

You can also use MindStudio’s [custom JavaScript functions](https://mindstudio.ai) to parse structured outputs, apply transformation logic between steps, or handle escalation routing if the advisor flags something outside the executor’s scope.

For teams running code generation or content production at volume, this kind of [multi-model workflow](https://mindstudio.ai) turns a manual process into something that runs on a schedule or in response to a webhook — consistently, without oversight.

You can try MindStudio free at [mindstudio.ai](https://mindstudio.ai).

## Common Mistakes That Undermine the Pattern

### Underspecifying the Advisor Prompt

If the advisor prompt is vague, the plan it produces will be vague. The executor has no margin to interpret ambiguity — it needs precise instructions. Spend most of your prompt engineering effort on the advisor, not the executor.

### Sending Too Much Context to the Executor

The executor should receive only what it needs for the current subtask. If you pass the full conversation history, the full codebase, and the original requirements all at once, you’re wasting tokens and adding noise that degrades output quality.

### Skipping the Review Step

It’s tempting to remove the review loop to save on advisor costs. This often costs more in the long run — executor errors compound, and catching them downstream is more expensive than catching them immediately.

### Using the Pattern for Simple Tasks

If your task has two or three steps with no ambiguity, one model is fine. The advisor-executor pattern adds overhead. Use it where the task is genuinely complex — multiple interdependent steps, non-trivial constraints, or outputs that need to meet a specific standard.

### Hardcoding the Task Boundary

What counts as “advisor-level” versus “executor-level” will shift as your models and use cases evolve. Treat the routing logic as a configuration parameter you revisit periodically, not a permanent architectural decision.

## Frequently Asked Questions

### What is the advisor-executor pattern in AI workflows?

The advisor-executor pattern is a model routing approach where one model (the advisor) handles planning, reasoning, and review tasks, while another model (the executor) handles implementation and execution. The advisor defines what to do and checks that it was done correctly; the executor does the actual work. This separation lets you use expensive, high-capability models only where they matter and cheaper, faster models for the bulk of the work.

### When should I use Fable 5 versus Claude Sonnet?

Use Fable 5 when the task requires careful reasoning before any output is produced — complex planning, architectural decisions, reviewing output for correctness, or resolving ambiguous requirements. Use Claude Sonnet when the task is well-defined and implementation-focused — writing code from a spec, generating content from an outline, or transforming data according to clear rules. If a task needs judgment, use Fable 5. If a task just needs execution, use Sonnet.

### How much can the advisor-executor pattern actually reduce AI costs?

## Remy is new. The platform isn't.

Remy is the latest expression of years of platform work. Not a hastily wrapped LLM.

The reduction depends on your task mix and the specific models involved. Workflows that route 70–80% of token consumption to the executor and reserve the advisor for planning and review typically see 40–60% cost reductions compared to running everything through a premium model. The savings compound at scale — the more volume you run, the more meaningful the difference.

### Can I use other models in this pattern, or does it have to be Fable 5 and Sonnet?

The pattern works with any two models where one has stronger reasoning capabilities and the other is faster and cheaper. Fable 5 and Claude Sonnet are a strong pairing because their capability profiles are well-matched to their roles — but you could apply the same structure with other model combinations depending on your use case and cost targets. The key is defining a clear task boundary and designing the handoff correctly.

### What happens when the executor produces output the advisor can’t approve?

Set a maximum retry limit (2–3 cycles is standard). If the advisor keeps flagging issues after the limit, escalate to a human review queue or log the case for manual inspection. In practice, a detailed advisor plan upfront reduces failed review cycles significantly — most issues stem from underspecified planning prompts, not fundamental model limitations.

### Is this pattern only useful for code generation?

No. The advisor-executor pattern applies to any workflow with a mix of reasoning-heavy and execution-heavy steps. Content production, data transformation, document drafting, research synthesis, and customer-facing automation are all common use cases. The code generation example is popular because the review loop has clear pass/fail criteria, but the pattern generalizes to any context where you can separate “figuring out what to do” from “doing it.”

## Key Takeaways

- The advisor-executor pattern routes planning and review tasks to a high-capability model (Fable 5) and implementation tasks to a faster, cheaper model (Claude Sonnet).
- Most AI workflow costs are concentrated in execution — token-heavy steps that don’t require deep reasoning. Routing these to the executor is where the savings come from.
- A detailed advisor plan is the most important input. If the plan is vague, the executor will produce unreliable output and the review loop will fail.
- The review step is worth keeping. Catching executor errors immediately is cheaper than letting them propagate downstream.
- MindStudio’s visual workflow builder makes this pattern implementable without managing model APIs, rate limits, or retry logic separately — you configure it in one place and run it at scale.

For teams running high-volume AI workflows, the advisor-executor pattern is one of the most practical ways to maintain output quality while keeping inference costs predictable. Start with one workflow, instrument the cost and quality metrics, and expand from there.