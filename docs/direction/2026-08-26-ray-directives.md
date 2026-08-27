# Ray's directives — 2026-08-26

Verbatim. This file is the PRIMARY SOURCE; anything restating it must cite it
rather than another restatement.

**Two directives were given this day.** The second is **UNPROCESSED BY
INSTRUCTION** — Ray's words: *"do not act or do anything on it besides having the
next session in /kb-resume process and analyze the statements below."* It is
recorded here and nowhere else, deliberately unanalysed.

---

## PART ONE — the coverage directive (processed 2026-08-26b)

Given mid-round. Its thirteen numbered items plus the quoted requirements below
were worked in session `kb-20260825.06`; outcomes are tracked in issues
**#518–#529** and summarised in `docs/artifacts/thirteen-directives.html`.

### The thirteen, verbatim

> 1. we need to build a true doctor command for the project that makes sure the project is healty. that does the following:
>    - run doctor/validate/verify/health commands of our dependencies:
>      - for example:
>        - mise doctor
>        - mise outdated --local -b -J
>        - uv tree --outdated --show-sizes --all-groups --format json
>        - uv check
>        - provide suggestions
>    - make sure there is a mise task mapped to each graphify cli command
>    - checks currency map is up to date
>      - status of:
>        - deep extraction
>        - reflection
>        - generated artifacts
>    - hk checks are passing
>    - the session-review workflow needs to check what should be added to the doctor command
>    - working on a git branch and not main
>    - this should should also be able to output into structured output so that it can be fed into our code to action upon
>    - provide suggestions of checks we are making that can definitiely provide the health status of the project currently
>
> 2. this statement is incorrect "this repo is project-Claude-only"
>    - we are already adding support for openai-cli backend and have fable-orchestrator codex lanes
>    - we have antigravity cold reviews
>    - add a github issue to also automate adding the skill for antigravity and keeping it up to date
>      - what we've been doing for:
>        - .agents/skills/graphify/.graphify_version
>        - .claude/skills/graphify/.graphify_version
>
> 3. what are the "6 invariant-banned verbs"?
>    - we might need to revisit some of the pre-existing rules/requirements as they might have been misunderstood that we need to clean up to not cause issues going forward on follow up sessions or confuse agents running on codex/antigravity models
>
> 4. also worth reviewing if we should also use Pyrefly (https://github.com/facebook/pyrefly) for type checking
>    - if it is a superset of ty and/or can be used in parallel w ty
>    - have graphify deeply extract and reflect on these:
>      - https://pyrefly.org/blog/too-many-type-checkers/
>      - https://pyrefly.org/blog/speed-and-memory-comparison/
>
> 5. i think it is also time to fully implement https://github.com/ray-manaloto/knowledge-base/issues/509
>    - and run the aggregated-research on this and especially for projects doing similar knowledge-base work on graphify or other tools. there might be tips/techniques/better tools we should evaluate before moving forward
>      - this needs to be something we automate daily as morning brief that an agent team can create/review/synthesize to improve this project
>
> 6. also review graphify's github issues/prs/discussions on some of the problems we are trying to solve as there might be some overlap or cases or techniques we are missing
>    - we should be using the gh cli to do this research and have it automated via the skill -> mise task -> python library module(s)/function protocol
>   - provide every command run on how and what was searched
>
> 7. are we properly using the existing deep extraction and reflection and generated artifacts to help in this specific task and research?
>
> 8. how can we use the pre-existing graphify native deep extraction to understand what are missing gaps in our design or to provide an honest assessment if this project's goal of using graphify as a knowledge base for research and understanding its dependencies or aid in research or conserve context and tokens
>    - are the communities/nodes/edges being properly connected to aid in this project?
>
> 9. are there AST tree-sitter/LSP tools/or other tools we can use to help analyze our config files better?
>
> 10. can we generate and keep in sync the following:
>    - tabular report of modular skill(s) -> mise task(s) - python library module(s)/function(s) -> graphify sdk/cli
>    - workflow/sequence diagrams of the above
>
> 11. we need to start using graphify's pr capabilities on our pr work
>
> 12. we need to find a way to create verbs/abbreviations to avoid confusion/typos/conserve context/tokens
>     - for example i am always typing this out "modular skill(s) -> mise task(s) - python library module(s)/function(s) -> graphify sdk/cli"
>       - ideally we just create a term for this that both you and i agree on and is less verbose but agents fully understand what that means
>     - worth reviewing skill: /mattpocock-skills:domain-modeling
>
> 13. add all those points as checkbox items and that the codex lane reviews if it was analyzed properly

### Quoted requirements from earlier the same session, verbatim

> we only want to use graphify's public sdk over the cli if the functionality is 1:1 and there is no loss in functionality

> we had already previously done a native full deep extraction of graphify using the claude-cli backend. did we do a reflection from that? did we run every possible step that needs agent work from that? did we generate every possible artifact from that

> we should utilize graphify's AST tree sitter and the ty LSP to help walk the codebase or help w generating diagrams/artifacts whenever possible — explain how graphify's AST tree sitter and the ty LSP could help achieve that

> specify each instance when processing this prompt that either of the following were done: 1. used the /graphify skill 2. use the graphify sdk 3. use the graphify cli 4. use any of our python library module(s)/function(s)

> create /eli5 visual artifacts explaining the entry point from each graphify cli command to - mise task -> python library module(s)/function(s) -> graphify sdk/cli - we might not have coverage to each graphify cli command yet, so note that as missing and how it would be done when implemented

> anything discovered from this that does not have a github issue should create them so we dont forget them in the future

> run another codex lane to review if what was done followed all the instructions and create a document with a numbered list of: 1. what was followed correctly 2. done incorrectly 3. vague and/or ambiguous that another human or ai llm agent could accidently do incorrectly if it were reading it cold with zero context

> run the /grilling skill until there is no ambiguity to this prompt and we have a shared understanding of what needs to be done

> i keep asking for this and it is not being done all the time, is the output style i asked for working? build a skill for this so i dont have to keep typing it out and we can keep improving the skill

> there were several more python tools we had not reviewed yet or /prototype to annotate the python code to generate the diagrams. list which of the tools have a real /prototype and which are pending or eliminated from contention

> we are on subscription plans for both claude and codex, so our concern isn't dollar amount but token spend as that is what we are using for graphify agent work. so the tokens used for graphify work is what needs to be tracked. but also generate the callflow-html for the graphify cloned repo and our python library

> we need to be able to run deep extractions on a new backend — for example if a dependency was deeply extracted on claude-cli but the claude tokens were depleted we need to be able to do it again but on the openai-cli backend if there are tokens available for the chatgpt/codex subscription plan

> our fork is a stop gap to move forward until graphify officially merges the openai-cli backend and we can stop using the fork. but let's create a github issue and keep updating it on what changes we can add to graphify to make the sdk 1:1 w the cli

---

## PART TWO — UNPROCESSED. Do not act; analyse in the next session.

Given at the end of session `kb-20260825.06`, immediately before `/clear`, with
this explicit instruction:

> context is getting full but before i run /clear add this verbatim and do not act or do anything on it besides having the next session in /kb-resume process and analyze the statements below

**Nothing below has been analysed, actioned, ticketed, or answered. It is
recorded verbatim only.** The next session reaches it via `/kb-resume`, which
reads the newest file in this directory.

Prefixed by Ray, as every prompt this round was:

```
/fable-orchestrator:orchestration
/graphify
```

### Verbatim

> 1.  should we lift the ban on graphify?
>     - i really only want one graphify source tree for common knowledge that is relevant for all projects and coding agents on this mac
>     - provide pros/cons and what features we lose/gain based on the graphify source tree vs global
>
> 2. review history/docs/github issues/branches/worktrees, we had discussed this previously to have datamodel-code-generator generate wrapper types for all model classes and enums
> - and to have a base schema for common types and enums
> - to just make it explicit and to avoid having to do this again, can we just make every function in the python library be a wrapper type that is generated by datamodel-code-generator so that we can just get this done in one swoop
>   - is this advisable? provide pros/cons on this approach or make suggestions
> - add path based and/or file type filters claude code rules and recursive AGENTS.md/CLAUDE.md instructions enforce this is the protocol for any python code including tests
>   - and maybe path based/file type based filters to enforce this protocol also or some type of deny rule
>     - so recursively under these subdirectories:
>       - python/src/kb_setup/
>       - tests/
>
> 3. i've also been starting every prompt with:
> /fable-orchestrator:orchestration
> /graphify
> - what is the best way to setup the prompt to enforce using the fable-orchestrator workflow and to force the agents to search the graphify sources first to optimize for code tranversal and project/dependencies knowledge discovery
>
> 4. the context limit is always close to 20% even before the first prompt after /kb-resume on a new session
>    - i think the MEMORY.md file is not setup properly and is injecting too much context right away
>      - for example, /kb-resume is only needed for the initial prompt after /clear. i dont think it needs to be there for every subagent or subtask/fork to read
>      - are we putting too much history into MEMORY.md that can better be injected into context at optimial times when working through a task
>    - and i keep requesting this and it is not being done. we need to have universal logging from mise task onto python library module(s)/function(s)
>      - i keep seeing commands being run that just pipe to stdout/stderro and grepping for phrases in lines read
>      - our code should be generating structured output that is machine readable so that return valuues and error codes are just enums that can be directly parsed w zero subjective reasoning needed on what the error is and how to act upon it
>        - we should be providing runbooks on how to act on error codes to automate the agent workflow(s)
>
> 5. provide an honest assessment and adversarial review of what this project is doing and ways to improve its goal and the current workflows and constant back and forth with issues and re-implementations due to miscommunication or misunderstanding
> - this should include updates to the project setup and setup for agents (claude/codex/antigravity)
>
> run the /grilling skill until there is no ambiguity to this question

### One factual note the next session should have, recorded because it was measured, not inferred

Item 4's premise about `MEMORY.md` was **independently confirmed** during the
session that received this directive, before the directive arrived — by a write
hook, not by analysis. The index at
`~/.claude/projects/<project>/memory/MEMORY.md` measured **25,227 bytes against a
24.4 KB read limit and a 17.1 KB target**, so **everything past the limit is
dropped at load, silently**. Four spent rounds were compressed (−1,276 bytes);
roughly **8 KB more** is still needed. Nothing gates it: the size is enforced
only by a hook on WRITE, so a session that merely reads memory never learns it
read a partial file.

That is a measurement, not an analysis of item 4. The rest of item 4 — and all
of items 1, 2, 3 and 5 — remains unprocessed.
