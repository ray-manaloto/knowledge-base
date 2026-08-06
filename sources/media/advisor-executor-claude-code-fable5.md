---
source_url: "https://www.mindstudio.ai/blog/advisor-executor-pattern-claude-code-fable-5"
content_sha256: 84d192572eb24c3048cb343e38726e18af490a3b333c4475fd099cb7f13c4661
content_chars: 17159
---

# How to Use the Advisor-Executor Pattern in Claude Code to Extend Your Fable 5 Limit

Use Fable 5 as an advisor and Opus or Sonnet as executor to get 93% of the work done at a fraction of the token cost—with a real example.

## The Token Budget Problem Every Claude Code Power User Hits

If you’ve been running Claude Code with Fable 5 (Anthropic’s most capable model tier) for anything serious — a large refactor, a multi-file feature build, a codebase audit — you’ve probably hit the wall. Fable 5 is extraordinarily capable, but its usage limits mean you burn through your allocation fast when it’s both planning *and* executing every task.

The fix is a two-model setup called the advisor-executor pattern. It uses Fable 5 only for high-level reasoning — figuring out *what* to do and *how* to approach it — then hands execution off to Opus or Sonnet, which are faster, cheaper, and perfectly capable of following a clear plan. The result: roughly 93% of the work gets done at a fraction of the token cost, and your Fable 5 allocation stretches across far more tasks.

This guide walks through the pattern, why it works, how to set it up in Claude Code, and a concrete example you can replicate today.

## What the Advisor-Executor Pattern Actually Is

The advisor-executor pattern is a multi-agent optimization technique where you split reasoning and execution across two different models rather than routing everything through one.

Here’s the core idea:

- **The advisor**(Fable 5) does the thinking. It analyzes the problem, proposes a structured plan, flags edge cases, and produces a precise specification for what needs to happen.
- **The executor**(Opus or Sonnet) does the work. It receives that specification and executes it — writing code, modifying files, running commands — without needing to re-derive the strategy from scratch.

## Seven tools to build an app. Or just Remy.

Editor, preview, AI agents, deploy — all in one tab. Nothing to install.

This matters because the reasoning phase typically consumes a disproportionate share of tokens when a capable model does it. Fable 5 is expensive to run precisely because it’s doing heavy reasoning. But execution — following a clear, well-structured plan — doesn’t require the same depth of reasoning. Sonnet can do it reliably and at a much lower cost per token.

Think of it as separating the architect from the builders. The architect (Fable 5) draws up detailed plans once. The builders (Opus or Sonnet) implement those plans across dozens of tasks without the architect needing to be on-site for every nail.

## Why Fable 5’s Limit Hurts Without This Pattern

Claude Code’s Fable 5 usage limit isn’t a bug — it reflects the real cost of running frontier-level inference at scale. Anthropic applies rate limits and usage caps to balance access across users and infrastructure.

The problem is the default behavior: when you run Claude Code with Fable 5 and give it a large task, it uses the premium model for *everything*. Every file read, every code write, every intermediate reasoning step, every minor formatting decision. That’s wasteful.

Here’s what that looks like in practice. Say you’re migrating a mid-sized Node.js project to TypeScript — 40+ files. If Fable 5 handles the entire migration end-to-end, you might exhaust your daily limit after 10–15 files. The rest of the task sits unfinished until your quota resets.

With the advisor-executor pattern:

- Fable 5 analyzes the codebase structure, identifies type patterns, and produces a file-by-file migration plan (a few thousand tokens total).
- Sonnet executes that plan, file by file, referencing the specification Fable 5 produced.

You’ve used Fable 5 for one compact planning session. Sonnet handles the remaining 90%+ of execution. Your Fable 5 allocation is intact for the next task.

## Setting Up the Pattern in Claude Code

Claude Code supports multi-model workflows through its `--model` flag and through structured prompt chaining. Here’s how to implement the advisor-executor pattern.

### Step 1: Start a Fable 5 Advisor Session

Open your project in Claude Code and explicitly invoke Fable 5 for the planning phase. Keep your prompt focused on producing a structured output — not on doing any work yet.

`claude --model claude-fable-5 "Analyze this codebase and produce a step-by-step migration plan for converting all JavaScript files to TypeScript. For each file, list: the file path, the types that need to be defined, any external dependencies that will need type declarations, and any known edge cases. Output the plan as a structured JSON array."`The key constraints here:

- You’re asking for a plan, not execution.
- You’re requesting structured output (JSON, YAML, or numbered lists) so the executor can parse it reliably.
- You’re being specific about what the plan should contain, which keeps Fable 5’s response compact and actionable.

### Step 2: Save the Advisor Output

Capture Fable 5’s plan to a file. Claude Code can write directly to your working directory:

`claude --model claude-fable-5 "... [your planning prompt] ... Write the output to migration-plan.json in the project root."`Alternatively, pipe stdout to a file and reference it in your next step.

### Step 3: Launch an Executor Session with Sonnet

Switch models and pass the plan as context:

`claude --model claude-sonnet-4 "You have a migration plan in migration-plan.json. Execute it step by step. For each file in the plan, apply the TypeScript conversions specified. After completing each file, mark it as complete in the plan. Do not deviate from the plan structure — if you encounter an issue, note it and continue to the next file."`### Everyone else built a construction worker.

We built the contractor.

    One file at a time.

UI, API, database, deploy.

A few things worth emphasizing in your executor prompt:

- **“Do not deviate from the plan.”**This prevents Sonnet from re-deriving strategy, which wastes tokens and can introduce inconsistency.
- **“Note issues and continue.”**You want the executor to flag problems without stopping for decision-making it isn’t equipped to handle. Route those decisions back to Fable 5 later if needed.
- **Progress tracking.**Having the executor update the plan file as it goes gives you a checkpoint you can resume from if a session ends.

### Step 4: Review and Re-Advise if Needed

When the executor finishes (or flags issues), you can open a short Fable 5 session to review edge cases, handle exceptions, or update the plan. This is another compact planning call — not a full re-run.

This loop (advise → execute → spot-check → re-advise if needed) is what keeps Fable 5 usage concentrated on reasoning tasks and execution costs on the cheaper model.

## A Real Example: Refactoring a React App

Here’s a full walkthrough with a concrete task — converting a React class component library to functional components with hooks.

### The Setup

The codebase has 28 class components spread across three feature directories. Some use lifecycle methods (`componentDidMount`, `componentDidUpdate`, `componentWillUnmount`), some use `setState`, and a few have complex render logic with internal state.

Without the advisor-executor pattern, running Fable 5 end-to-end on this would likely exhaust daily limits before finishing.

### The Fable 5 Advisor Prompt

```
Analyze the React class components in /src/components. For each file:
1. List the lifecycle methods used and their functional equivalents (useEffect patterns)
2. Identify all state variables and their useState equivalents
3. Flag any components with unusual patterns that require special handling
4. Produce a migration order (start with simplest components)
Output as a structured YAML file at /src/migration-plan.yaml.
Do not modify any source files. Analysis only.
```
This prompt produces a compact, structured plan. Fable 5 uses maybe 3,000–5,000 tokens total. It’s doing what it’s best at: pattern recognition, edge case identification, and structured reasoning.

### The Sonnet Executor Prompt

```
You have a component migration plan at /src/migration-plan.yaml.
Work through each component in order. For each one:
- Convert the class component to a functional component using the patterns specified in the plan
- Replace lifecycle methods with useEffect hooks as specified
- Convert state using useState as specified
- If the plan flags a component as "special handling required," make the conversion but add a comment: // REVIEW: [reason from plan]
- After converting each file, append a "completed" status to that item in the YAML
Begin with the first uncompleted component in the plan.
```
Sonnet handles all 28 components without burning Fable 5 tokens. It’s following instructions, not strategizing. That’s well within Sonnet’s capability.

### The Result

- **Fable 5 tokens used:**Approximately 4,200 (analysis phase only)
- **Sonnet tokens used:**Approximately 38,000 (execution across 28 files)
- **Fable 5 limit consumed:**Less than 15% of a typical daily allocation
- **Outcome:**All 28 components converted, with 3 flagged for manual review

### Built like a system. Not vibe-coded.

Remy manages the project — every layer architected, not stitched together at the last second.

Compare that to a single-model Fable 5 run, which would have used 40,000+ Fable 5 tokens and likely hit limits before finishing.

## Getting 93% Efficiency: What the Numbers Mean

The “93% of work at a fraction of the cost” framing comes from how token usage distributes across advisor and executor roles.

In typical coding tasks, the reasoning phase — understanding the codebase, deciding on a strategy, identifying edge cases — accounts for roughly 5–15% of total token usage. The execution phase — actually writing, modifying, and reviewing code — accounts for 85–95%.

If you run everything through Fable 5, you’re paying frontier prices for all of it.

If you use Fable 5 only for the reasoning phase and Sonnet for execution, you’re paying frontier prices for 5–15% of the work. The other 85–95% runs at Sonnet pricing, which is substantially lower per token.

The 93% figure reflects a common distribution: about 7% of tokens going to the Fable 5 advisor phase and 93% to the Sonnet executor phase. Your mileage will vary based on task type — tasks with complex architecture decisions may need more advisor time — but the ratio is typically in this range for well-structured software tasks.

The practical upshot is that you can run multiple large tasks per day without burning through your Fable 5 quota, rather than exhausting it on a single session.

## Common Mistakes and How to Avoid Them

### Asking the Advisor to Do Too Much

The most common mistake is letting Fable 5 start executing during the planning phase. Watch for prompts like “Plan the migration and start with the first file.” That bleeds execution into the advisor role and inflates your Fable 5 usage.

Keep advisor prompts explicitly analysis-only. Use language like “produce a plan,” “analyze,” “identify,” “output a specification.” Avoid “do,” “convert,” “write,” “apply.”

### Under-Specifying the Executor Prompt

If the executor prompt is vague, Sonnet will fill in gaps with its own reasoning — which is slower and can deviate from the plan. Be explicit: tell it exactly how to interpret the plan, what to do with edge cases, and how to track progress.

### Skipping the Structured Output Step

If Fable 5’s plan is a wall of prose, Sonnet has to parse intent from natural language, which introduces ambiguity. Always ask the advisor to produce structured output — JSON, YAML, or clearly numbered lists. Structured plans execute more consistently.

### Using the Executor for Decision-Making

If Sonnet hits something unexpected during execution, it shouldn’t improvise strategy. Your executor prompt should route unusual cases back to a logging file or a comment in the code, not have Sonnet make judgment calls. Bring those decisions back to Fable 5 in a targeted follow-up session.

## Where MindStudio Fits Into This Pattern

The advisor-executor pattern is a form of multi-agent orchestration — one model directing another. If you’re building this kind of workflow into a product or automated pipeline (rather than running it manually in Claude Code), [MindStudio](https://mindstudio.ai) is worth looking at.

## Remy is new. The platform isn't.

Remy is the latest expression of years of platform work. Not a hastily wrapped LLM.

MindStudio’s visual builder lets you wire up multi-step agent workflows without code. You can configure one AI step to use Fable 5 or Opus for analysis, pass that output to a second step running Sonnet for execution, and chain the whole thing together with branching logic, file handling, and integrations to tools like Slack, Notion, or GitHub.

The platform supports 200+ models out of the box — including the full Claude lineup — so you can run advisor-executor patterns at a product level, not just at the command line. For teams that want to build this kind of cost-optimized AI workflow into an internal tool or customer-facing application, MindStudio removes the infrastructure overhead. The [Agent Skills Plugin](https://mindstudio.ai/agent-skills) also lets Claude Code itself call MindStudio workflows as method calls, which means you can extend this pattern with capabilities like web search, email, or database reads without building that plumbing yourself.

You can try MindStudio free at [mindstudio.ai](https://mindstudio.ai).

## Frequently Asked Questions

### What is the advisor-executor pattern in Claude Code?

The advisor-executor pattern splits a task between two models: a high-capability model (the advisor) that analyzes the problem and produces a structured plan, and a faster, cheaper model (the executor) that carries out that plan. In Claude Code, this typically means using Fable 5 for planning and Sonnet or Opus for execution. It reduces overall token costs while preserving quality on complex tasks.

### How do I switch models between sessions in Claude Code?

Use the `--model` flag when launching Claude Code: `claude --model claude-fable-5` for the advisor phase, and `claude --model claude-sonnet-4` for the executor phase. You can also set a default model in your Claude Code configuration file and override it per session.

### Does the executor model need to be in the same session as the advisor?

No. The handoff happens through shared context — typically a file that the advisor writes and the executor reads. This makes the pattern easy to implement: the advisor session ends, its output is saved, and a new executor session starts with the plan as input. Sessions don’t need to be linked.

### Is Sonnet capable enough to execute plans from Fable 5?

For most well-defined software tasks — code migration, refactoring, feature implementation, test generation — yes. The key is that the advisor produces a detailed, unambiguous plan. Sonnet is very capable at following clear instructions; it struggles when asked to do the heavy reasoning itself. Structure the handoff well and execution quality stays high.

### What kinds of tasks benefit most from this pattern?

Tasks where the planning phase is distinct from the execution phase and where execution is repetitive or parallelizable. Examples include: large-scale refactors, multi-file code migrations, batch content generation, systematic test writing, and data transformation pipelines. Tasks that require tight feedback loops between thinking and doing — like debugging a novel issue — benefit less.

### Can I use this pattern with other Claude multi-agent frameworks?

Yes. The advisor-executor concept isn’t Claude Code-specific. You can implement it with LangChain, CrewAI, the Claude API directly, or through platforms like MindStudio. The core principle applies anywhere you can route different stages of a task to different models. Claude Code just makes it particularly accessible through its `--model` flag and file-based context sharing.

## Key Takeaways

- The advisor-executor pattern uses Fable 5 only for planning and reasoning, then routes execution to Opus or Sonnet — extending your premium model allocation significantly.
- In practice, around 93% of total tokens go to the executor (cheaper) model, with only 5–10% consumed by the advisor (premium) model.
- Implementation in Claude Code relies on the `--model`flag, structured output from the advisor, and explicit executor prompts that reference the plan.
- Common failure modes are prompts that blur advisor and executor roles — keep analysis and execution in separate, clearly scoped sessions.
- For teams building this into automated pipelines or products, [MindStudio](https://mindstudio.ai)provides a visual way to wire up multi-model workflows without managing infrastructure manually.

## Other agents ship a demo. Remy ships an app.

Real backend. Real database. Real auth. Real plumbing. Remy has it all.

If you’re hitting Fable 5 limits on large projects, the advisor-executor pattern is the most practical adjustment you can make. The setup takes about 10 minutes and the token savings are immediate.