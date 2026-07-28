Goal Engineering: how I brief coding agents using paired goal+rider documents 

- 
- 
- 

 Greg Ceccarelli 
 Book a call 

 Course 
 Writing 
 Products 
 greg.md 
 SpecStory ↗ 
 Book a call 

 - 01 Goal Engineering 

- 02 Where this fits 

- 03 Worked example: deadreckon 's Coherent pass 

- 04 Worked example: findunmet 's Liveness round 

- 05 The skill, and trying this tomorrow 

- 06 The full goal-rider-author skill 

 Browse the corpus 
 All deadreckon goal+rider pairs → 

 By 
 
 gregce 
 May 18, 2026 

 Cited in these notes 
 
 - 
 deadreckon 
 open 

 - 
 findunmet 
 private 

 Field notes 
 
# Goal Engineering .

 By gregce · May 18, 2026 · How I brief coding agents using paired goal+rider documents

 Contents 
 - 01 Goal Engineering 

- 02 Where this fits 

- 03 Worked example: deadreckon 's Coherent pass 

- 04 Worked example: findunmet 's Liveness round 

- 05 The skill, and trying this tomorrow 

- 06 The full goal-rider-author skill 

 TL;DR. Two markdown files per round of agent work: a goal (under 4,000 characters) and a rider (unbounded, with phases and named tests). The agent reads both, executes against them, and commits its work alongside them. The pair lives in docs/goals/ forever.

 Jump straight to a worked example or the copyable Claude Code skill that drafts the pair.

 Read time: 10 minutes if you skim, 25 if you open every quoted file.

 If you have been using Claude Code, Cursor, or Codex for a while, the following arc will feel familiar. You typed a few prompts. The agent shipped something impressive. Then it shipped something wrong and you had to figure out what you meant. Then your prompts started referencing files and conventions and prior decisions. Then your prompts were the size of an architecture document and they still did not quite land.

 What follows is the practice I switched to instead. Think of it as a flight plan for one round of agent work: a small set of checked-in documents that say where the round is going, what it can touch, and how it will know it has landed. Skim the diagram below for the shape of a round; the rest of these notes is what each box hides.

 It is late on May 12, 2026. I am at my desk, briefing the next round of work on deadreckon , the open-source Rust CLI I am building. The trigger I type into Claude Code is one sentence, with a typo, sent to a skill I wrote a few days earlier:

 /goal-rider-author
<command-args>I would like to create a goal and rider to evaluate this
against the original unmet needs and how it currently works to figure out
additional hardening and usability imrprovements</command-args>

 That is what a round of work begins with for me now: a one-sentence trigger and a skill that turns it into two markdown documents the agent reads before it touches the code.

 I stopped writing prompts like I used to in early May 2026. 11 I started writing two markdown files per round, checked into the repo. The first is a goal : short, capped, the spine of one round of work. The second is a rider : unbounded, typically 10 to 35 KB, the prescriptive detail. The agent (Claude Code, Codex CLI, whatever) reads both, executes against them, and commits its work alongside them.

 A prompt is the unit of one chat turn. A round is the unit I think in now. One round is one goal+rider pair, eleven phases, and one architecture-doc update at the end. The pair is the brief that opens the round; everything else is the round playing out.

 The brief is a committed file with a sha: you can git diff it, your teammates can comment on it in a PR, and the agent can re-read it as many times as the round needs. The shift is from thinking turn-by-turn to thinking artifact-by-artifact.

 This sits in a recent lineage. Prompt engineering taught the field how to ask. Context engineering, named in June 2025 by Walden Yan, 1 Tobi Lütke, 2 and Andrej Karpathy, 3 taught it what to put in the window. Drew Breunig 4 and Anthropic 5 codified it. Goal engineering points at a third axis: how to specify the end-state of one round so an agent can drive there on its own. The next section sets all three side-by-side with Kieran Klaassen's compound engineering in a table.

 The pair lives in docs/goals/ forever, named by minute-precise timestamps, so ls docs/goals/ is the project's authoring order at a glance.

 I have used this approach across two projects for the last eight days. 6 7 

 The first is deadreckon , a Rust CLI I'm building, open source at github.com/gregce/deadreckon . It is a harness around whichever coding agent you already use (Claude Code, Codex, Cursor). Its job is to let you start a long agent run, walk away, and trust the result when you come back.

 deadreckon exists to make goal engineering even simpler than it already is. The goal+rider says what "done" looks like; deadreckon automates the rest of the round, turning your plain-English "done" into executable checks, running the agent in an isolated git worktree, and keeping the loop going until the checks pass.

 The headline feature is dr-gate , a separate watchdog process that decides when a run is finished. Codex's /goal and Claude Code's /goal both lean on an LLM-as-judge inside the same harness: the agent (or a sibling model) is asked whether it's done, which is opinion, not evidence. dr-gate instead re-runs the goal's executable checks itself and signs the result with a secret the agent process cannot read. 9 The agent cannot forge a signature it has never seen, so the only path to "done" is real evidence an independent process can re-verify.

 If the goal+rider is the flight plan, dr-gate is the altimeter that will not take the pilot's word for it. deadreckon exists so this survives an overnight run with no human watching.

 The second is findunmet , a consumer-grade research product. Type a topic; an agent reads across Reddit, X, YouTube, TikTok, Hacker News, Polymarket, GitHub, and the open web, and returns a cited synthesis of what people are complaining about, trying, and paying for. The codebase is private. Between them, 37 goal+rider pairs and roughly 500 commits.

 Every quoted line in these notes is a file you can read. The deadreckon paths are public. The findunmet paths are real, just not browsable from the outside.

 My hope, after Nicholas Carlini's How I Use AI (the piece these notes are openly modeled on), is to exhaust you with examples.

## What prompts can't do

 A prompt is a single utterance. 10 It scrolls off. You cannot grep for it in three weeks. 12 You cannot diff it against the version that shipped last Tuesday. You cannot point a reviewer at it.

 A prompt has no integration matrix and no out-of-scope list, so the next round tends to re-litigate scope. A prompt cannot fail a build.

 A goal+rider pair is a checked-in artifact. It has a sha. It is reviewable in a PR. It carries the posture : tier, schema-stability promises, the explicit "no V1 invention" guard that keeps an agent from inventing scope under pressure.

 The cost is that I have to write the documents. The benefit is that one minute of careful authoring deletes ten minutes of mid-run intervention.

 Across the two repos here, I have not yet had to abort a run because the agent misunderstood scope. I have aborted runs because the depth tests caught a thin slice. That is the point.

## The shape of the pair

 Both documents live at:

 <project>/docs/goals/<YYYY-MM-DD>-<HHMM>-<project>-<topic>-{goal,rider}.md

 The <HHMM> is the local 24-hour authoring time. Two pairs in the same minute sort alphabetically by topic. The pair shares one timestamp; never split them across minutes, or the alphabetical sort breaks.

 Here is one real pair, listed:

 $ ls docs/goals/ | grep 2026-05-17-2130
2026-05-17-2130-findunmet-run-liveness-goal.md
2026-05-17-2130-findunmet-run-liveness-rider.md

 The goal for that pair is 3,991 characters. The rider is 31 KB. Together they specify twelve phases, name 47 depth tests, define a stage-aware Vercel-cron watchdog, and pin a failure_reason regex that becomes a depth-tested spec.

 The work landed across 13 commits between May 17, 2026 at 22:31 and May 18, 2026 at 00:46. For this pair every commit message ends with (rider PN) ; not every project of mine uses the suffix in the subject line, but findunmet does, so the rider→commit trace is one git log --grep away.

 I'll show you what a real drafting session looks like, then break the goal and rider down piece by piece.

## How I draft a pair

 The skill (whose source is in §06) does roughly ninety seconds of pre-work before writing a line of output. It reads the project's architecture doc, the most recent goal+rider pair in docs/goals/ , the CHANGELOG, the V1-CANDIDATES list, and any source files at HEAD the new pair will quote by name. For the May 12, 2026 audit round, the one read that mattered most was /Users/gdc/deadreckon/docs/AS-BUILT-ARCHITECTURE.md . That is the document the round would later close against at P11.

 Then it drafted the goal, opening:

 GOAL: Audit deadreckon at /Users/gdc/deadreckon/ against the 25 original unmet needs and the as-built reality, then close the highest-leverage hardening + usability gaps the audit surfaces. The product is at alpha ; AS-BUILT §22 names ten scaffolding-thin items... Headline word: Hardening .

 A one-sentence follow-up from me (typo included: "This is good but i want to allow network access by default" ) produced a surgical edit to the rider's posture section, and we committed. Nineteen turns, two hours, three pairs that day.

## The goal: 4,000 characters, no exceptions

 The cap is not arbitrary; it is the limit Codex's /goal command enforces on the objective text you pass it. 8 Claude Code matched the same number twelve days later. Either harness will refuse longer text and tell you to "put longer instructions in a file and refer to that file in the goal" — which is exactly what the rider is.

 The cap matters in practice because it forces me to decide what the goal is before I write it. I run wc -c on the goal file as a pre-commit habit; prior precedents in the corpus run 3,929 to 4,112 characters. Anything past 4,100 is a sign the goal is doing work that belongs in the rider.

 Here is the opening of the run-liveness goal, written the evening of May 17, 2026. Don't try to follow every term; the shape is the lesson: an opening verb, the current pain named with specific file paths, and a single headline word at the end.

 GOAL: Detect and recover from stage-subprocess hangs automatically, and kill sandboxes the moment a run reaches a terminal status. Current pain: claude subprocesses sometimes write their output and never exit (runner blocks in cmd.Wait() ); only rank has a heartbeat (cr-iter P6), so seed/fetch/report hangs are invisible until the 5-minute outer window trips; and even when a run does terminate, no one kills the sandbox. The last week has been manual refund-run.mjs calls plus orphan sandboxes burning credits. Headline word: Liveness .

 Three things to notice. The GOAL line starts with a verb ( detect and recover ), not with "we should consider improving." The current pain is named with file paths and function names: cmd.Wait() , refund-run.mjs . The agent reads this and grounds itself in HEAD, not in an abstract description.

 And there is a headline word . Every goal in my corpus picks one: Liveness , Coherent , Friendliness , Self-documenting , Default mode , Multi-agent , Single authority . The headline word is the test of whether the goal is one round. If I cannot pick a single word, the scope is too wide and I split the round in two.

 Below the headline comes a five-section skeleton, in this order:

 **Read first.** absolute paths to architecture doc, the rider, exemplars
**Posture.** what does NOT change this round (schema, tier, push policy)
[domain body] modes, verbs, contracts; the "what to build"
**Phases.** eleven, in the rider; each: depth test → implement → green → commit
**Verification.** observable commands and assertions; the exit criteria
**Stop when** a single sentence tying verification to a final commit

 Read-first is non-negotiable. The agent reads the architecture doc, the rider, the exemplars, and the prior riders in docs/goals/ before it writes a line of code. If I cannot point at the documents that ground the round, the round is not ready to start.

 Posture is where most goal-engineering bugs hide.

 Posture is a list of things the round will not do. Look at the run-liveness posture:

 Posture. Alpha. No DB schema changes — heartbeats reuse system_log{phase,heartbeat:true} . No new runner deps. No sandbox template rebuild (v3 still TLS-blocked; hot-patches keep v2 current). Edits inside /Users/gdc/findunmet/ . No git push .

 Six sentences. Five of them are negations.

 No schema changes. No new deps. No rebuild. No push. Inside this directory. The last one names the explicit blocker (v3 TLS) and the workaround in production.

 An autonomous agent under pressure will invent solutions. Posture is the fence that keeps it from inventing one outside this round.

## The rider: unbounded, prescriptive

 The rider opens by citing the goal's absolute path and listing the prior riders whose invariants compose forward:

 This rider holds the prescriptive constraints for the goal at
 /Users/gdc/findunmet/docs/goals/2026-05-17-2130- findunmet -run-liveness-goal.md .
It supersedes nothing in prior riders (notably
 2026-05-17-1521- findunmet -multi-iter-cockpit-rider.md , whose P6 ranked
heartbeat is the template for the rest of this work).

 That second sentence is doing serious work. It tells the agent: the new helper is an extraction of an existing one. Half the implementation is a refactor, not a green-field write. The rider names the source file and line range ( emitRankHeartbeats in runner/rank.go:33-77 ) and says "generalize the body."

 This is goal engineering as code review in advance.

 A typical rider carries roughly a dozen named sections — Posture, Data model, Algorithms, Verb signatures, Phases, Integration matrix, Out-of-scope, Dependencies, and a few project-specific ones. The skill ships a validator that greps for the headers and counts the phase blocks. If grep -c '^### P[0-9]' rider.md is not 11, the rider is not done.

## Eleven phases, depth tests first

 I call them depth tests because each test pins one specific behavior, named precisely. (Some people call them characterization tests or behavioral tests; same idea.) Each rider has eleven phases, P1 through P11.

 The eleven is a target, not a religion. Some pairs are 9. The run-liveness pair stretched to 12 because P11 split into sandbox-kill and watchdog work.

 Every phase follows the same loop:

- Write the named depth tests first . Watch them fail.

- Implement the slice that makes them pass.

- Run the project's full build+test+lint+fmt command. Green on every commit.

- Make one conventional-commit local commit. The message ends (rider PN) .

- Append one line to CHANGELOG.md .

 The depth tests are named in the rider . Here are the actual tests for the run-liveness P5 (stall-guard helper):

 - stallguard_kills_after_no_output_growth_in_threshold_window
- stallguard_does_not_kill_during_steady_output_growth
- stallguard_sigterm_then_sigkill_after_grace_period
- stallguard_sets_killed_true_and_kill_reason_no_output_threshold_seconds
- stallguard_first_byte_grace_does_not_kill_before_any_stdout_growth
- stallguard_respects_outer_timeout_as_upper_bound
- stallguard_returns_stdout_and_stderr_collected_pre_kill

 Read those test names aloud. Each one is a behavioral assertion you could defend in a code review.

 They are written in the rider before the implementation exists. The autonomous agent's first action in P5 is to create runner/stallguard_test.go with seven failing tests. Only then can it implement.

 The check is mechanical: grep -c '^ fn ' (Rust) or grep -c '^func Test_' (Go) on the test file enforces presence.

 Phase P11 is doc-only. No depth test. It updates the architecture doc with a new top-level section and adds the milestone line to CHANGELOG.md . Most of my architecture docs have a what's shipped vs thin section near the top: a two-column inventory of what works today versus what is half-built. P11 is where items move from the thin column to the shipped column.

 That honesty rule means the architecture doc never lies about what's done.

## Files, not fields

 Persistent per-feature state lives in files inside the working tree, not as new fields on a long-lived struct.

 The run-liveness rider invents /tmp/run/stage.current , a one-line sidecar file the runner writes atomically (write to .tmp , os.Rename into place) before entering each stage. The entrypoint trap reads it on exit-1 to attribute the failure.

 It would have been "easier" to add a currentStage field to the in-memory runner state. That field would have died with the runner; the file survives the crash, and os.Rename makes locking unnecessary. The rider specifies the write protocol explicitly because the agent will otherwise reach for a mutex.

 The same posture is enforced for findunmet 's database. No DB schema changes appears in 14 of 15 findunmet riders. The one exception was the original schema-creation pair. When a phase reveals it needs a schema change, the rider says: stop, log it to docs/V1-CANDIDATES.md , do not silently expand scope.

## V1-CANDIDATES.md, the overflow valve

 Every project has a docs/V1-CANDIDATES.md .

 Anything an in-flight rider proves it should not do this round goes there. It is the pressure-relief valve that keeps the eleven-phase loop honest.

 Examples actually written into V1-CANDIDATES during the run-liveness round:

 - Per-stage timeout reduction. The existing 20/45/30/30-minute outer caps stay; stall-guard catches stalls inside the cap.
- Per-fetch-query stall guard. Fetch goroutines are individually short.
- Email notification on watchdog refund. Email plumbing belongs to the pricing rider's Surface E follow-up.
- UI: "stage stalled" toast in the cockpit. The existing failed card is enough for alpha.
- Backfill of existing `failure_reason` values to new shape. Historical rows keep their existing strings.

 Each of those is a real engineering decision that could otherwise have eaten four hours.

 Naming them in the Out of scope section of the rider is what makes the round shippable in a day instead of a week. The V1 file is the durable home for them. The rider's Out-of-scope section is the local copy.

## Friendliness as a verifiable contract

 Both projects share a five-bullet contract for user-facing surfaces, lifted verbatim across riders:

- Auto-detect, don't ask (the obvious case is the default).

- Preflight + preview before any state change.

- Refuse with try: <command> lines.

- Rollback is one command.

- Lifecycle hints after every action.

 Each bullet is exercised by a depth test in the rider that introduces it. The try: lines are checked by a parameterized test that fires every refusal code and asserts its recovery hint is present and non-empty. The contract is a build gate.

## The headline word, again

 Each goal picks one. It names the state of the world after the round , not the work done during it. Coherent is a posture the codebase will hold afterward; Single authority is the property the architecture will gain; Liveness is what the runs would feel like once a hung stage detected itself and a terminal status cleaned up its sandbox.

 Before that round, runs would sometimes hang and quietly chew through sandbox credits before I noticed. The Liveness round made the hangs visible. Liveness was the test of done.

## Why this works

 Claude Opus running unattended for an hour can land 12 commits, write 40 tests, and refactor across 8 files. The bottleneck is the human, specifying what the round is .

 Goal engineering moves that specification work from inside the run (where every misunderstanding costs an LLM round-trip) to before the run (where misunderstanding costs nothing because the agent hasn't started yet).

 The cap forces decisions. The rider forces precision. The phases force sequencing. The depth tests force testability. The P11 architecture-doc update forces honesty about what shipped.

 It travels. I have run this pattern across Rust, TypeScript, Go, Python, and mixed stacks. The toolchain commands differ. The shape doesn't.

## What a skeptic would say

 Five objections worth taking seriously, with the most honest answer I have for each.

 "Eight days, two projects, both yours. This is a journal entry, not a methodology." 

 Correct. These are field notes, not a study. The only claim is that this is what I do, with the artifacts public so you can judge the shape for yourself.

 "This is TDD with a glossary." 

 Mostly true: writing tests first, keeping scope vertical, deferring non-essentials, and updating an architecture doc are the moves Kent Beck described in 1999. The narrower novel claim is that the checked-in pair , not the practice, is what makes the round survive an unattended overnight agent.

 "You shipped fast because you're solo on greenfield Rust and Next.js." 

 True. Both projects are alpha, both solo, no migrations, no on-call, no CODEOWNERS . Whether the pair survives a multi-owner repo with a real review process is unknown; this should not pretend otherwise. The closest evidence I have is that the same pair briefs Codex, Claude Code, Cursor, and a human reviewer without modification (§02). That is a partial answer at best.

 " dr-gate is theater. An agent that writes the tests also writes tests that pass." 

 The objection conflates two layers. dr-gate runs the checks compiled from def-done , which I wrote in plain English before the agent started; the agent doesn't author the gate's spec and cannot forge the signing nonce. The residual risk is that I underspecify done, not that the agent grades itself. The rider's depth tests are a separate layer the agent does write; a human still reads those names before merging. dr-gate 's narrower job is making sure the agent can't say done when my pre-declared checks haven't returned green.

 "Headline word, posture, V1-CANDIDATES — this is ceremony for an audience of one." 

 Partly fair. The vocabulary is for my own consistency across rounds, not for readers to adopt. If you copy anything, copy the artifacts (a checked-in pair, named tests, a closed architecture doc) and leave the ritual behind.

 A sixth objection worth flagging in passing: the goal cap is borrowed from Codex's MAX_THREAD_GOAL_OBJECTIVE_CHARS , not derived from first principles. Fair. The defensible claim is that some hard cap forces the round to be one round; the specific number is a Schelling point, not a discovery.

 Next: how this fits beside prompt, context, and compound engineering. Then two worked examples, the skill that drafts these pairs, and how to try it tomorrow on your own project.

- Walden Yan, Don't Build Multi-Agents , June 12, 2026. The Cognition AI post that first framed context engineering as a field: naive multi-agent setups fragment context, and the fix is to make every action carry the full trace of prior decisions. The post calls context engineering "the #1 job of agent builders". See cognition.ai/blog/dont-build-multi-agents . ↩ 

- Tobi Lütke, X post, June 19, 2025. "I really like the term 'context engineering' over prompt engineering. It describes the core skill better: the art of providing all the context for the task to be plausibly solvable by the LLM." See x.com/tobi/status/1935533422589399127 . ↩ 

- Andrej Karpathy, X post, June 25, 2025. Karpathy's amplifier post, six days after Lütke: "+1 for 'context engineering' over 'prompt engineering'. … context engineering is the delicate art and science of filling the context window with just the right information for the next step." Took the term mainstream. See x.com/karpathy/status/1937902205765607626 . ↩ 

- Drew Breunig, Why "Context Engineering" Matters , July 24, 2025. Argues the term marks the birth of a new field rather than a rebrand, and catalogs the failure modes (poisoning, distraction, confusion, conflict) the field has to address. Breunig is writing the O'Reilly Context Engineering Handbook . See dbreunig.com/2025/07/24/why-the-term-context-engineering-matters.html . ↩ 

- Anthropic Applied AI Team, Effective Context Engineering for AI Agents , September 29, 2025. The canonical reference defining context engineering as curating the optimal set of tokens during inference, with production patterns (e.g., keep 3-5 most-used tools always loaded; dynamic discovery beyond 10). See anthropic.com/engineering/effective-context-engineering-for-ai-agents . ↩ 

- Codex CLI v0.128.0, April 30, 2026. OpenAI shipped the first /goal slash command in the Codex CLI on April 30, 2026 (initially behind [features] goals = true in config.toml ). The command sets a session-scoped completion condition; the agent plans, edits, runs tests, and iterates until it judges the condition met or hits the configured token budget. See Slash commands in Codex CLI and Follow a goal . ↩ 

- Claude Code v2.1.139, May 12, 2026. Anthropic added /goal to Claude Code on May 12, 2026, 12 days after Codex. It's implemented as a session-scoped, prompt-based Stop hook: each time Claude finishes a turn, the condition plus the conversation so far are sent to the configured small fast model (Haiku by default), which returns a yes/no decision and a short reason; the hook blocks stopping until the answer is yes. Conditions are subject to the same cap as Codex (see fn 8); works in -p and Remote Control. See Keep Claude working toward a goal . ↩ 

- The 4,000-character cap, Codex source. Defined in codex-rs/protocol/src/protocol.rs as pub const MAX_THREAD_GOAL_OBJECTIVE_CHARS: usize = 4_000; and enforced by codex-rs/tui/src/chatwidget/goal_validation.rs , which rejects longer text with the message "Put longer instructions in a file and refer to that file in the goal, for example: /goal follow the instructions in docs/goal.md " . The rider is that file. See openai/codex protocol.rs and goal_validation.rs . ↩ 

- dr-gate mechanics. At startup, dr-gate generates a per-run nonce and holds it in its own memory. The agent process is spawned as a child with no read access to that memory. When the agent claims completion, dr-gate independently re-runs the goal's executable checks (tests, file shape, scripts). Only if those pass does it sign a work-complete marker with the nonce; promotion of the run to a reviewable artifact requires that signature. The contrast with a same-harness LLM-as-judge is the contrast between a signed receipt and a verbal claim. See github.com/gregce/deadreckon . ↩ 

- Prompt engineering, canonical references. The technical substrate is Brown et al., Language Models are Few-Shot Learners , 2020 (the GPT-3 paper that established in-context learning as the medium prompts work in). The widely-cited codification as practice is Lilian Weng's survey, Prompt Engineering , March 15, 2023. See arxiv.org/abs/2005.14165 and lilianweng.github.io/posts/2023-03-15-prompt-engineering . ↩ 

- How much I had written prompts before I stopped. Roughly 23,641 sessions and 285,167 messages across 160 projects over 186 active days in the year leading up to this shift, averaging 12 messages per session. Writing prompts well was the work, until the artifact below replaced it. ↩ 

- The "can't grep" claim has an exception. SpecStory captures every prompt-and-response turn from Cursor, Claude Code, Codex, Windsurf, and Cline into searchable history files; you can grep for what you typed three weeks ago. The argument here isn't that prompts vanish from disk — SpecStory shows they don't have to — it's that even a grep-able prompt isn't a checked-in artifact a reviewer can diff against last Tuesday's version. Disclosure: I work at SpecStory. ↩ 

 02 / where this fits 
 
## Where this fits

 Four named disciplines. Each operates on a different unit of work. None of them are mutually exclusive.

 Discipline 
 Unit 
 Output 
 Read by 
 Compounds? 

 | Prompt engineering 
 | One chat turn 
 | The prompt text 
 | One LLM call 
 | No 

 | Context engineering 
 | One inference call 
 | An assembled context window 
 | One LLM call 
 | Indirectly, via retrieval and memory layers 

 | Compound engineering 
 | The project 
 | Captured lessons (solution docs, defaults, hooks) 
 | All future agent runs 
 | Yes. The whole point. 

 | Goal engineering 
 | One round 
 | A committed goal+rider pair 
 | The agent now, then humans, then future rounds 
 | Yes. Each pair joins the corpus the next pair reads. 

## Both compound. The difference is what compounds.

 Compound engineering compounds lessons . Goal engineering compounds promises .

 Compound engineering captures lessons from finished work. Klaassen's plugin 8 (16,000+ GitHub stars, fifty-plus subagents, eight chained slash commands from /ce-strategy through /ce-product-pulse ) is designed to make one session smarter for the next. Parallel persona reviewers grade the diff. The /ce-compound step writes a structured solution doc to docs/solutions/<category>/ , with frontmatter the next round's learnings-researcher can search. The unit is a finished feature on its way to a PR. The artifact is hindsight, distilled.

 Goal engineering captures promises made up front. No chained slash commands, no panel of persona reviewers. Two markdown files (the goal and the rider), authored before the round begins, with eleven phases and named depth tests written down in advance. After P11 ships, the architecture doc, the CHANGELOG, the V1-CANDIDATES file, and the new goal+rider pair join the corpus the next pair will read. The next goal almost writes itself, because the prior round's V1-CANDIDATES list is the obvious starting point.

 They stack cleanly. The skill that drafts goal+rider pairs (in §06) reads prior pairs in docs/goals/ , the architecture doc, the V1-CANDIDATES list, and the recent CHANGELOG, and grounds the new pair in what came before. Compound engineering's docs/solutions/ lessons feed exactly this pre-work. Goal engineering's P11 closure feeds compound engineering's substrate. The corpus grows from both ends.

 Where they diverge is sharper than that.

- The cap. A goal must fit inside the Codex /goal limit (see §01). Compound engineering's plans can run as long as the planner wants. The cap is the part of the practice that teaches you what one round actually is.

- The order. Compound engineering writes its learning doc after the work is done. The goal+rider is the test of done , written before any code, then used to judge whether the work landed.

- The verdict. Compound engineering's review is persona-agent consensus with confidence gating. Goal engineering's verdict is a set of commands a human can paste into a terminal ( cargo test && cargo clippy , grep -c '^func Test_' , an architecture-doc section that didn't exist this morning). Opinions versus evidence; pair either with dr-gate (§01) for a signed receipt.

- The portability. Two markdown files brief Codex, Claude Code, Cursor, or a human reviewer next quarter without modification. Compound engineering travels with its plugin; the loop is the product. The pair is just the spec, and any harness can run it.

 Said most simply: compound engineering looks backward and ships forward. Goal engineering ships a promise and proves it landed.

## What goal engineering does that the others don't

 Three things.

 The unit is one round, and the round has a hard cap. Compound engineering doesn't bound the round; the project compounds, but a single round can sprawl. Context engineering doesn't bound the unit at all; an inference call is whatever the agent decides to put in the window. Prompt engineering bounds at one turn but has no notion of "round." Goal engineering says: a round is a capped goal plus a rider plus eleven phases. It ends when the four verification commands return green and the architecture doc has section N. Anything else is a different round.

 The brief is a promise. A prompt vanishes after the turn. A context window vanishes after the call. A compound-engineering solution-doc gets written after something is learned. I write the goal+rider before the round starts, and it stays as that round's spec for as long as the repo exists. Three weeks from now, git log --grep "rider P5" returns the one commit that landed P5 against a spec you can still read at HEAD.

 The spec is project-scoped, not session-scoped. Most harnesses now ship a session-scoped completion contract (in Codex and Claude Code, the /goal slash command is the surface). It tells the harness when to stop for this thread . That contract lives until the thread ends, then it is gone. The goal+rider is the project-scoped artifact that surrounds it. The goal fits inside /goal because of the cap. The rider holds what won't fit in one sentence: the eleven phases, the named depth tests, the posture, the V1-CANDIDATES list, the architecture-doc closure at P11. Both are useful. The slash command is the runtime. The pair is the spec. The pair compounds; the slash command does not.

 That third property is what makes the approach travel. The same pair that briefs Codex briefs Claude, briefs Cursor, briefs a human reviewer next quarter. The harness changes; the artifact doesn't.

## Brief attributions

 Context engineering was named in June 2025 by Walden Yan, 1 Tobi Lütke, 2 and Andrej Karpathy, 3 then codified by Drew Breunig 4 and Anthropic. 5 

 Compound engineering was named by Kieran Klaassen at Every in January 2026, growing out of building Cora. 8 The canonical loop is Plan → Work → Assess → Compound, with roughly 80% of effort in planning and review and 20% in execution.

 Goal engineering is what I am calling this practice. The first goal+rider in my corpus is dated May 10, 2026; the drafting skill went up two days earlier.

- Kieran Klaassen, Compound Engineering , Every, January 17, 2026. "Each unit of engineering work should make subsequent units easier, not harder." The practice grew out of building Cora at Every; the canonical loop is Plan → Work → Assess → Compound, with the public plugin extending it on either end via `/ce-strategy` and `/ce-product-pulse`. Roughly 80% of effort goes to planning and review, 20% to execution. The plugin (Every Inc, ~16,900 GitHub stars as of May 2026) ships 50+ subagents and 38+ skills for Claude Code, Codex, and Cursor. See every.to/guides/compound-engineering , Compound Engineering: The Definitive Guide , and the plugin at github.com/EveryInc/compound-engineering-plugin . ↩ 

 03 / example coherence 
 
## Worked example: deadreckon 's Coherent pass

 The test of done for a goal-engineering round: does the artifact become precedent? This pair did. Every deadreckon rider after it points back at "Coherent" when it says "follow the editorial bar." 

 On the evening of May 13, 2026, deadreckon had grown from one verb ( run ) to fifteen over four days. A new orchestration surface had shipped ( orchestrate , plan , fork , merge , history ) along with a third interactive TUI. Each verb had its own colour calls, kv-block layout, confirmation prompt, flag vocabulary.

 I sat down and counted. The audit at docs/design/USER-FACING-MATRIX.md came back with 108 numbered inconsistencies. That audit became the spec. The round was: land all 108 fixes in one editorial pass without changing a single byte of internal state.

 The pair: 2026-05-13-1900-deadreckon-coherence-goal.md and 2026-05-13-1900-deadreckon-coherence-rider.md . Headline word: Coherent .

## What the goal preserved

 The goal opens with the audit as the spine:

 GOAL: Make every user-facing surface of deadreckon say the same word, colour it the same, print on the same stream, respond to the same flag the same way. Keep the visual fun: the deadreckoning cyan banner, the * ^ . - course strip, magenta IDs, the spend gauge gradient, the step glyphs ○ ● ◐ ✗ ↷ ◉ ↶ . The audit at docs/design/USER-FACING-MATRIX.md lists 108 inconsistencies; unpushed orchestration commits add five verbs ( orchestrate , plan , fork , merge , history ) and a third TUI (plan attach) that need the same model. One glossary, one style helper, one prompt builder, one kv-block, one palette, one truth for --force / --all / --branch / --max-spend / --strategy . Headline: Coherent .

 Halfway through, the goal names every visual flourish that has to survive the refactor: the cyan banner, the course strip, the magenta IDs, the spend gauge gradient, the seven Unicode step glyphs.

 That list is not decoration. It is the agent's permission slip: change everything except these. 

 Without that list, an agent doing an editorial pass eventually decides the cyan banner is "inconsistent" and removes it. Removing it improves the audit metric.

 The posture line carries the structural promise:

 Posture. Stays alpha . No PipelineState schema changes. No RunStatus / ChainStatus / PlanTaskStatus variant renames; the displayed string changes via one status_label() . No git push . Larger renames go to docs/V1-CANDIDATES.md .

 One status_label() function is the engineering move: the variant names in the type system stay, the displayed strings flow through one helper. That single sentence shapes the rider's first phase.

 The body of the goal is unusual: it is a flag-rename diff written in prose, six lines.

 Flag truth. --force splits into --escalate (kill), --overwrite (dest), --anyway (override). --all stays cross-project; cleanup/chain take --all-scopes ; status takes --global . --budget-cap becomes --max-spend on doc . --branch splits: --branch-name on run , --into on apply / finish . --strategy collides three ways today; rename apply to --git-strategy and rename chain branch-policy value merge to linear-merge . Aliases kept one alpha.

 Six sentences specifying eight flag renames, three flag splits, one aliasing rule.

 The rider expands each into a phase with depth tests. The goal carries the decisions. The rider carries the mechanics.

 The verification section is mostly grep tests and golden files:

- Every status string in main.rs flows through status_label() ; zero direct ANSI codes outside ui.rs (grep tests).

- deadreckoning banner, course strip, step glyphs, gauge gradient render byte-for-byte as today (goldens).

- status latest on completed/failed/running runs shares one kv layout (golden).

- chain show and chain attach snapshot share one header at six-decimal precision.

 Byte-for-byte goldens for the visual flourishes. That is how you preserve personality through a refactor: pin the bytes. 

## What the rider added

 The rider opens by recording the audit anchor and committing to extend it to unpushed commits:

 Every fix below cites the audit ID (S1-S4, V1-V17, F1-F15, C1-C11, O1-O17, T1-T14, L1-L3, P1-P24, Q1-Q5, R1-R15, CH1-CH6, J1-J3, D1-D2) from docs/design/USER-FACING-MATRIX.md . When the matrix and the rider disagree, the matrix wins; update the rider in the same commit.

 The matrix wins. Update the rider in the same commit. 

 That is goal engineering in practice: the rider is the spec, but the audit is the ground truth, and any divergence gets reconciled in the same commit. No stale specs.

 The rider's "Visual identity preserved" subsection is a particularly useful block. It names every flourish, cites the line number in main.rs , gives the cadence (200 ms per tick), specifies the tier change (T9 fix: all three TUIs share the cadence after the rider), and pins it to a golden:

 The * ^ . - ASCII course strip rendered by deadreckoning_course_ascii ( main.rs:6633-6652 ), used at full width in the run-TUI footer and at width 18 in cli_wait_status_line ( 6622-6631 ). Cadence: 200 ms per tick (run TUI), kept identical for chain and plan TUIs after this rider (T9 fix).

 Read that as a code review checklist for the agent. It can't lose track of the cadence. It can't refactor the helper out of existence. It can't decide width 18 was arbitrary.

## How Codex received the brief

 This pair ran on OpenAI's Codex CLI. The session lasted 11 hours and 24 minutes across 2,217 events.

 Codex has a feature called the active thread goal . Every turn, the harness silently re-injects the original goal text into the conversation along with a built-in completion audit. The agent does not get to forget what round it is in.

 How it works: at the start of every turn, Codex sends a role=developer message that wraps the goal in an <untrusted_objective> envelope. Then comes the audit:

 Before deciding that the goal is achieved, perform a completion audit against the actual current state. Restate the objective as concrete deliverables. Map every requirement, file, command, test, and gate to real evidence. Do not accept proxy signals as completion. Treat uncertainty as not achieved. Do more verification or continue the work.

 The agent's first response, before touching any code, was one sentence in the commentary channel:

 I'll first ground this in the repo state: read the matrix/rider/architecture/style docs, inspect the current branch and worktree, then choose the next concrete implementation slice from what is still missing.

 Then five parallel reads: git status --short --branch , the audit matrix, the coherence rider, AS-BUILT §26, the impeccable STYLE.md. After that, work.

 The rider doesn't just brief one round. It survives every turn inside the round, with a completion audit attached. That is what checked-in buys you. The harness can re-read the spec as many times as the round needs.

## What landed

 The Coherent pass touched 11 phases and roughly 30 commits. A representative slice (each sha links to the commit on GitHub):

- 90dc320 feat(tui): name shared coherence palette 

- b891302 fix: centralize status tones 

- 0af7f45 fix: align lifecycle help wording 

- 2e4c576 fix: centralize ansi styling helpers 

- ecd9135 test: cover chain header parity 

- beaff1e test: cover history grep scope flags 

- f678fa8 test: cover status kv layout parity 

- 8b83eea test: cover visual identity helpers 

- 4ac5caf fix: centralize error line rendering 

 Two patterns in those messages. Centralize : half the work was moving scattered logic to one helper. Cover ... parity : tests named for the property they enforce, not the artifact they exercise.

## What I would do differently

 The rider's Visual-identity block listed eight flourishes and was right about all of them, but it should have made the list machine-checkable: a golden file per flourish, regenerated from the rider before each phase. As written, the agent had to read the prose and act faithfully. It did. Pinning each one to a named golden would have made the pattern mechanical, the way the depth tests are.

 The flag-rename block in the goal was one paragraph of prose; it worked, but it was harder to verify than the rest of the goal. A small table (old flag, new flag, deprecation alias, expiry milestone) would have read in three seconds and tested in fewer. The next goal that does a flag pass uses the table.

 The opener already said this round became precedent; what this section adds is the two corrections I'd ship next time, not a re-victory lap.

 04 / example liveness 
 
## Worked example: findunmet 's Liveness round

 The point of this round wasn't to land perfect numbers. It was to land the contract — four layers, one regex, one sidecar, one kill helper — so future rounds could move the numbers without re-litigating the architecture. The numbers will move; the contract holds. 

 For the week ending May 17, 2026, my mornings looked like this. Open the dashboard. Find two runs sitting in running status with their last event four hours stale. Open Supabase, run node scripts/refund-run.mjs <id> for each. Open the E2B console. Find three orphan sandboxes from runs that had completed two days ago. Kill them. Watch the credit gauge tick back up by twenty dollars.

 findunmet runs research jobs inside ephemeral E2B sandboxes. Each run is four stages (seed, fetch, rank, report). Each stage spawns a claude subprocess inside the sandbox that streams tokens into Markdown files.

 That subprocess was the problem. It would occasionally write all its output and then never exit. The runner blocked in cmd.Wait() . Only rank emitted heartbeats. Seed, fetch, and report hangs were invisible until the 5-minute outer window tripped. The watchdog refunded the user. The sandbox kept running. The credits kept burning.

 The pair: 2026-05-17-2130- findunmet -run-liveness-{goal,rider}.md . Headline word: Liveness .

## The four-layer contract

 The goal expressed the round as four layers under one contract:

- Stage heartbeats. seed/fetch-per-iter/rank-per-iter/report emit system_log{phase,heartbeat:true,iteration?,elapsed_ms} every 30s.

- Output-stall kill. runClaudeWithStallGuard samples stdout every 10s; no growth past per-stage threshold (seed 90s, fetch 180s, rank 240s, report 90s; calibrated from event-gap data, conservative margin) → SIGTERM, 5s grace, SIGKILL. First-byte grace: clock starts only after first stdout byte.

- Diagnosable failure_reason. Every terminal write follows <stage>: <cause> ( rank: killed (no_output_240s) , entrypoint: trap exit=1 stage=fetch ).

- Sandbox cleanup on terminal. Every run that reaches completed | failed | refunded | cancelled calls killSandbox(sandbox_id) exactly once.

 Four bullets. Each is a phase or a phase pair in the rider. Each is a single observable claim the goal can be tested against.

 The thresholds (90 / 180 / 240 / 90 seconds) appear in the goal and in the rider's algorithm section and in the rider's integration matrix and in runner/stallguard.go after P5 lands. One number, four places, all in lockstep.

## Threshold calibration as a section

 The rider includes a calibration table I would not have written six pairs earlier:

 | Stage | Signal observed | p50 | p95 | p99 | max | Stall-guard threshold |
| seed | stage duration | 37s | 44s | — | 46s | 90s (≈2× max) |
| fetch | per-query lifetime | 91s | 121s| 167s| 521s| 180s (≈1.1× p99) |
| rank | stage duration | 219s| 352s| — | 367s| 240s (covers TTFT) |
| report | inter-chunk gap | 19s | 33s | 41s | 44s | 90s (≈2× max) |

 After the table I wrote two paragraphs explaining why the chosen threshold is conservative against the upper-bound signal, and which way a false positive versus a false negative pushes the system.

 A false-positive kill costs a few minutes of refundable compute. A false negative costs a forever-hung run. So I sized against the upper bound. I committed to re-calibrate after 50 production runs.

 Without that paragraph, the numbers look arbitrary. With it, they are decisions. Three weeks from now, future me will not change those numbers without re-reading the data.

## Stage attribution by sidecar

 The most interesting move in the rider is the sidecar file:

### /tmp/run/stage.current — active-stage sidecar

 A one-line file the runner writes/atomically-replaces before entering each stage. The entrypoint trap reads it on exit-1 to attribute the failure.

 Write protocol: write to /tmp/run/stage.current.tmp , os.Rename into place. Single writer (the runner main goroutine). Single reader (entrypoint trap on exit). No locking needed; rename is atomic on the same filesystem.

 The entrypoint trap is a bash one-liner in e2b-template-v2/helpers/entrypoint.sh . It runs when the sandbox process exits with code 1.

 Before this rider it posted reason: "entrypoint trap exit=1" to /api/runs/[id]/lifecycle-fail . The dashboard rendered that as a useless failed card.

 After the rider, it reads /tmp/run/stage.current and posts stage: "fetch:2" , which becomes failure_reason = "entrypoint: trap exit=1 stage=fetch" . The dashboard now names the failing stage.

 Files-not-fields. The data lives in a file so the trap, which runs after the runner is dead , can still read it.

## The failure_reason regex as a spec

 Every terminal write to runs.failure_reason follows the regex:

 ^(seed|fetch|rank|report|entrypoint|watchdog|provision|unknown): .+

 The regex is a depth test.

 tests/unit/failure-reason-shape.test.ts enumerates every writer and asserts the regex holds. Changing the regex changes the spec; the agent cannot quietly relax it. Cap is 500 chars; truncate the suffix, not the prefix.

 That eight-token disjunction is a working glossary. Before the rider, the dashboard showed failure_reason values like Error: connection reset , entrypoint trap exit=1 , Watchdog refunded after 5m stall . After the rider, every value starts with one of eight stage names. The dashboard groups them by cause and colours them by stage.

 The shape is the user experience. 

## Twelve phases that landed in commits

## Twelve phases, one closure

 The rider broke this into twelve phases (P1 extract heartbeat helper, P2–P4 wire into seed/fetch/report, P5 stall-guard helper, P6 wire it, P7 the sidecar, P8 lifecycle-fail accepts structured failure_reason , P9 watchdog moves to Vercel cron, P10 stage-aware thresholds, P11 idempotent killSandbox , P12 the doc closure). Each phase landed as one commit with a (rider P{N}) suffix in the subject, so git log --grep "rider P5" returns the one commit that landed the stall-guard helper. Three weeks from now, someone wondering why runner/stallguard.go exists follows the suffix to the rider, reads the algorithm section, and gets the calibration table that explains 240 seconds.

 P12 closed the round with §20 in AS-BUILT-ARCHITECTURE.md (heartbeats, stall-guard, sidecar, failure-reason contract, cron watchdog, sandbox cleanup), moved watchdog as managed cron from thin to shipped, added one Run liveness (alpha) — May 17, 2026 block to the CHANGELOG, and dropped one bullet from V1-CANDIDATES. Three documents in agreement; two stale entries gone; 47 new tests. Round finished.

## What I would do differently

 The rider committed to twelve phases instead of eleven because P11 split sandbox-kill from watchdog. I should have written it as eleven from the start, with sandbox-kill folded into the P9 watchdog work, since both paths share killSandbox . The extra phase added one commit and one CHANGELOG line. It did not improve traceability.

 I should have caught one calibration mistake at author time. The report inter-chunk gap data (max 44s, threshold 90s) was the right ratio. But the report stage runs claude in a different mode than the others; the threshold should probably have been 60s. I noticed two weeks later.

 A pre-author stage-by-stage check the assumption holds paragraph would have caught it; the next liveness rider does this.

 The opener said this: the contract holds, the numbers will move. P5's report-stage threshold is one of those numbers.

 05 / skill 
 
## The skill, and trying this tomorrow

 The drafting work is itself a Claude Code skill.

 It lives at ~/.agents/skills/goal-rider-author/SKILL.md . It is 414 lines. The interesting parts are the pre-work order, the two recipes, the checklist, and the validation steps.

 The full text is in the next section. You can copy it, drop it into your own .agents/skills/ directory, and trigger it on phrases like draft a goal that addresses X or new goal for the next agentic turn .

### A small chronology

 I wrote this skill on May 9, 2026. At that point, Codex CLI had shipped /goal (April 30, 2026) and Claude Code had not. So the first job of the skill was the reverse of what its name suggests: I used Claude Code, with this skill, to draft goals that I then pasted into Codex's /goal runner to execute. Claude wrote the brief. Codex did the work.

 Three days later, on May 12, 2026, Claude Code shipped its own /goal and the workflow collapsed into one tool. The skill itself didn't change; it still drafts the same paired documents. The point isn't which harness runs the goal. The point is that the goal+rider pair travels. The same files that brief Codex brief Claude, brief a Cursor agent, brief a human reviewer.

 That portability is what let the approach survive a tool boundary in its first week.

## How the skill thinks

 When invoked, the skill does not start drafting. It does pre-work, in this order:

- Read the project's architecture doc ( AS-BUILT-ARCHITECTURE.md , ARCHITECTURE.md , or whatever the project uses). Look for the what's shipped vs thin section.

- Read the two most recent goal+rider pairs in docs/goals/ . Absorb voice and section conventions; their invariants compose forward.

- git log --oneline -30 -- docs/goals/ and git log --oneline -30 . Cadence and conventional-commit format.

- Source code at HEAD for any data structures, file paths, or function names that will be quoted in the rider. Verify they match HEAD before citing.

- Research or pain-point reports the project has (unmet-needs docs, retros). They ground the ergonomics in real pain.

 If the project has no prior pairs, the skill asks the user for a pointer instead of inventing one. That is the key line. Half of the bad rider drafts I've seen from other people were a model inventing a precedent that didn't exist.

## The validator

 Before the skill declares a pair done, it runs:

 PROJECT=<absolute path to project root>
DATE=$(date +%Y-%m-%d)
HHMM=$(date +%H%M)
GOAL=$PROJECT/docs/goals/$DATE-$HHMM-$SLUG-$TOPIC-goal.md
RIDER=$PROJECT/docs/goals/$DATE-$HHMM-$SLUG-$TOPIC-rider.md

# 1. Goal must be under 4000 chars
wc -c "$GOAL" # expect ≤4000

# 2. Rider must have ≥11 phase headers
grep -c '^### P[0-9]' "$RIDER" # expect = 11

# 3. Rider must have the standard top-level sections
for section in "Posture" "Phases" "Out of scope" "Dependencies" \
 "Engineering invariants" "Process invariants"; do
 grep -q "^## $section" "$RIDER" || echo "MISSING: $section"
done

# 4. Both files cite each other's absolute paths
grep -F "$RIDER" "$GOAL" || echo "goal does not reference rider"
grep -F "$GOAL" "$RIDER" || echo "rider does not reference goal"

# 5. Stage and commit
cd "$PROJECT" && git add "$GOAL" "$RIDER" && git status

 Five checks. Each is mechanical. Each catches a real failure I've made.

## How to try this on your own project tomorrow

 Start with one round.

 Pick something you actually need to land this week, not a toy. The right size is one feature, two to five files, half a day to a day of agent runtime. 

 Sketch the goal first, in a text file you'll delete. Try to keep it under the cap (the validator below checks). If you can't, narrow the scope until you can. The narrowing is the point. The cap is a forcing function; it teaches you what one round looks like.

 Pick a headline word.

 If you can't, you're still trying to do two rounds.

 Now write the goal properly, into docs/goals/<YYYY-MM-DD>-<HHMM>-<project>-<topic>-goal.md . Use the skeleton from the overview: Read first, Posture, domain body, Phases, Verification, Stop when. Put absolute paths under Read first. Put negations under Posture.

 Then write the rider. The rider is the long one. Use these top-level sections in this order:

 ## Posture (decided — do not redesign)
## Data model (files, not fields)
## Algorithms
## Verb signatures
## Phases (eleven)
## Integration matrix
## Error-footer canonical pairs
## Out of scope (explicitly not in this milestone)
## Dependencies
## Engineering invariants (do not violate)
## Process invariants

 For each of P1 through P11, list the depth tests first , then the implementation slice. Tests by name.

 The names should read as behavioral assertions: lifecycle_fail_truncates_suffix_not_prefix_when_over_cap , not test_lifecycle_fail_5 .

 Run the validator. Commit the pair as docs(goals): add <topic> goal+rider . Then hand it to the agent.

## What happens in the run

 The agent reads the Read-first list, then the goal, then the rider.

 It runs Phase 1: writes the depth tests, watches them fail, implements the slice, runs the project's build+test+lint+fmt, commits, appends one line to CHANGELOG. Then Phase 2. Then Phase 3.

 Here is the real shape of one Codex run from May 14, 2026. The deadreckon Coherence rider had landed in the corpus the previous evening. I started a Codex thread, attached the goal with /goal , and pasted the goal body. Within seconds, before writing a line of code, Codex fired five parallel reads:

 git status --short --branch
sed -n '1,220p' docs/design/USER-FACING-MATRIX.md
sed -n '1,260p' docs/goals/2026-05-13-1900-deadreckon-coherence-rider.md
sed -n '/^## 26\./,/^## 27\./p' docs/AS-BUILT-ARCHITECT.md
sed -n '1,220p' /Users/gdc/impeccable/STYLE.md

 Notice the fourth line. There's a typo in the architecture doc path ( AS-BUILT-ARCHITECT.md should be AS-BUILT-ARCHITECTURE.md ). The goal itself had the typo. The agent read the wrong filename, got an empty result, and moved on. The pattern doesn't depend on the agent being smarter than its inputs. It depends on the rider being the spec, not the path.

 Eleven hours and twenty-four minutes later, the session had landed the Coherence pass across roughly thirty conventional commits. The agent never re-asked what the round was. The <untrusted_objective> envelope plus the completion audit kept the round in working memory for every turn.

 Watch the first phase. If the depth tests are wrong (too coarse, missing the case you cared about), kill the run, fix the rider, and restart. Better to lose one phase to a rider patch than to ship eleven phases that miss the property you wanted. After the first phase looks right, walk away.

## What you'll find on the other side

 The artifact you get back has five shipped parts beyond the code:

- 11 commits with rider-traceable messages.

- 30 to 80 depth tests, each named after the behavior it pins.

- One new section in your architecture doc.

- One new milestone block in your CHANGELOG.

- The docs/V1-CANDIDATES.md file longer, with the explicit list of what didn't ship and why.

 That last one is the useful part. Every round leaves a list of the next round's candidates, ranked by the thinking you did while you were in this round; the next goal almost writes itself.

## When this doesn't work

 This isn't for you if your "round" is fifteen minutes of polish, a hot-fix, or a tiny PR. The brief overhead only amortizes against rounds that would otherwise run for hours of agent time across multiple files; a five-line CSS tweak doesn't need eleven phases. The right size is one feature, two to five files, half a day to a day of agent runtime .

 Three softer gating concerns:

 The pattern wants a real architecture doc and a real CHANGELOG. If your project has neither, write a small AS-BUILT first; one round, one rider, one phase to describe what's shipped vs thin . Two live examples to crib from: deadreckon 's AS-BUILT-ARCHITECTURE.md and its CHANGELOG.md . Every deadreckon rider closes against the first at P11 and adds one milestone block to the second.

 The pattern wants depth tests to be cheap. If your test suite takes 40 minutes to run, the phase loop breaks down. Get a 30-second fast lane first.

 The pattern is a per-round unit, not a roadmap. It does not replace the work of figuring out what to build ; it replaces the work of figuring out how this round will know it's done .

 Now write one. The round is the unit.

 06 / skill source 
 
## The full goal-rider-author skill

 The complete skill text follows.

 Save it to ~/.agents/skills/goal-rider-author/SKILL.md (or your project's .agents/skills/ directory) and Claude Code will pick it up next launch. The skill is licensed Apache-2.0. Copy it, fork it, rewrite it for your own toolchain.

 Copy skill source 
 Download .md 

 ---
name: goal-rider-author
description: Draft a goal+rider document pair to brief the next agentic turn on a project. Two documents — a ≤4000-char goal (the spine) and an unbounded rider (the prescriptive detail with eleven phases and depth-tests-first discipline). Run when user says "draft a goal", "new goal", "write a goal+rider", "goal+rider for the next agentic turn", "rider for X", or anything in the shape of "brief the next agent on Y".
license: Apache-2.0
metadata:
 author: SpecStory, Inc.
 version: "1.0.0"
 argument-hint: "<topic for the new goal>"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Goal & Rider Author

A two-document pattern for briefing an autonomous coding agent
(Claude Code, Codex CLI, or any agentic harness) on the next round of
work. The **goal**
is the ≤4000-char spine: what to do, what to read first, the posture,
the verification, the stop conditions. The **rider** holds the
prescriptive detail: data schemas, phase plans, depth-test names,
verb signatures, error footers, out-of-scope lists.

The pattern's superpower is that the goal stays small enough to paste
into a Codex `/goal` or a Claude run prompt, while the rider can be
arbitrarily detailed without bloating the executor's working memory.

This skill is project-agnostic. It works for any codebase that has a
`docs/goals/` (or equivalent) directory, conventional commits, and
some form of AS-BUILT / architecture doc. Substitute the project's
own toolchain commands wherever the templates say
`<project's ... command>`.

## When to invoke

The user is about to start a new round of agentic work and wants
goal+rider files written into a project's `docs/goals/` directory.
Triggers include "draft a goal that addresses X", "write a goal+rider
for Y", "new goal for the next agentic turn", "rider for X".

## Pre-work — do not skip

Before drafting, gather context. Read in this order, skipping items
the project doesn't have:

1. **Project architecture doc** — `AS-BUILT-ARCHITECTURE.md`,
 `ARCHITECTURE.md`, `docs/architecture.md`, or whatever the project
 uses. Look for a "what's shipped vs thin" section if one exists;
 it grounds the goal in reality.
2. **Prior goal+rider pairs** in `docs/goals/` (or wherever the
 project keeps them). Their invariants compose forward; do not
 duplicate verbatim. Skim the most recent two pairs to absorb
 voice and section conventions.
3. **Recent commits**: `git log --oneline -30 -- docs/goals/` and
 `git log --oneline -30`. Reveals delivery cadence and the
 conventional-commit format the project uses.
4. **Source code at HEAD** for any data structures, file paths, or
 function names you'll quote in the rider. Verify they match HEAD
 before citing.
5. **Research or pain-point reports** the project has (e.g.,
 unmet-needs, user-research, retro docs). They ground the
 ergonomics in real pain.

If you can't find prior pairs or an architecture doc, **ask the user**
for a pointer — don't invent one.

## Goal document recipe (≤4000 chars)

**Path:** `<project>/docs/goals/<YYYY-MM-DD>-<HHMM>-<project-slug>-<topic>-goal.md`

The `<HHMM>` is the local 24-hour clock time when the file is created
(e.g., `1444` for 2:44 PM). It makes `ls docs/goals/` sort in true
authoring order rather than alphabetical by topic. When two pairs land
within the same minute, secondary alphabetical sort handles the tiebreak;
that's fine.

**Hard cap:** `wc -c <file>` must be ≤4000 (prior precedents: 3929–4112).
Re-check after every edit pass. Note the `-HHMM-` insert costs ~5 chars
per internal rider reference, so leave a small buffer when riders cross-cite.

**Skeleton** — fill each section, cut to fit:

```markdown
GOAL: <one-sentence headline>. <one paragraph: current pain → what the goal lands → headline word (Friendliness / Multi-agent / Self-documenting / Default mode / …)>.

**Read first.**

- `<absolute path to project architecture doc>` — substrate; one line.
- `<absolute path to the rider being written>` — schemas, signatures, depth tests.
- `<absolute paths to exemplars or research reports>` — grounding.
- Prior riders in `<absolute path to docs/goals/>` — invariants hold.

**Posture.** Stays `<tier>`. No `<struct>` schema changes (if applicable). No `git push`. Edits inside `<project root>`. Major architectural decisions → `<V1-CANDIDATES path>`.

<DOMAIN BODY — one or two of these, depending on the goal:>

**<N> modes / verbs / artifacts, auto-resolved.**

- **`<name>`** — <one line of behavior>.

**New verbs.**

- `<verb> <args>` — <one line>.

**Friendliness as a verifiable contract.**

- Auto-detect, don't ask (the obvious case is the default).
- Preflight + preview before any state change.
- Refuse with `try: <command>` lines.
- Rollback is one command.
- Lifecycle hints after every action.

**Phases.** Eleven (P1–P11) in the rider. Each: depth test first → implement → `<project's build+test+lint+fmt command>` green → conventional-commit → CHANGELOG. P11 adds a `<new section>` to the project architecture doc.

**Verification.**

- Commands green every commit; every rider depth test present and passing.
- <Smoke 1>: <verifiable command + assertion>.
- <Smoke 2>: <verifiable command + assertion>.
- No edits outside `<project>`. No `git push`. No schema changes.

**Stop when** verification passes, AS-BUILT updated, CHANGELOG has a "<Milestone name> (alpha)" section, committed locally.
```

**Trim priority when over budget:**

1. Drop parenthetical detail that's already in the rider.
2. Shorten Read-first descriptions to bare absolute paths.
3. Compress Posture to one or two lines.
4. Cut verification smoke bullets to two.
5. Drop cross-rider "do not preempt" notes; those live in the rider.

## Rider document recipe (no char cap; typically 10–35K)

**Path:** `<project>/docs/goals/<YYYY-MM-DD>-<HHMM>-<project-slug>-<topic>-rider.md`

Use the **same** `<YYYY-MM-DD>-<HHMM>` prefix as the matching goal so
the pair sorts together. Author the goal first, then mirror its
timestamp on the rider — never split them across minutes.

**Skeleton:**

```markdown
# <project> — <Slug> Rider (<short framing>)

This rider holds the prescriptive constraints for the goal at
`<absolute path to goal>`. It supersedes nothing in prior riders
(<list dated rider filenames>) — their invariants still apply.
This rider adds <one-line summary of what's new>.

**All paths absolute.** Source `<project root>`, runtime `<runtime root>`.

## Posture (decided — do not redesign)

- **Maturity stays `<tier>`** (alpha / beta / stable; mirrors what
 the project calls the current milestone).
- **No `<struct>` schema changes** (if applicable). State lives in
 files at `<path>`.
- **<Other domain-specific invariants — be explicit>.**
- **No `git push`.** Phased local commits only.
- **No V1 / next-tier invention.** If a phase reveals a major
 architectural decision, log it in `<V1-CANDIDATES path>` (or
 equivalent) and continue.
- **Edits stay inside `<project root>`.**

## Data model (files, not fields)

<JSON schemas for any new file-based state. One block per file.
Inline-comment each field if the meaning isn't obvious.>

## <Algorithms / Mode resolution / Detection rules>

<Pseudocode for non-obvious logic. The rider IS the spec — match it
in the implementation.>

## Verb signatures

```
<verb> <args>
 [--flag] # description
 [--other-flag <type>] # description
```

For each verb: refusal cases table.

## Phases (eleven)

Each phase: write the named depth test(s) **first** and watch them
fail; implement; green on
`<project's build+test+lint+fmt command, green on each commit>`;
conventional-commit local commit; one-line CHANGELOG entry.

### P1 — <name>

- <bulleted prescriptions>

Depth tests (in `<test path>`):
- `snake_case_descriptive_name_that_would_have_caught_the_thin_behavior`
- `another_named_test`

### P2 — <name>

...

### P11 — Architecture doc update + CHANGELOG (doc only; no depth test)

- Insert a new top-level section into `<architecture doc path>`:
 ```
 ## NN. <Section title>

 NN.1 <subsection>
 NN.2 <subsection>
 ...
 ```
- If the architecture doc has a "what's shipped vs thin" section,
 update it:
 - Add to the "shipped" side: <items this rider lands>.
 - Note explicitly whether this rider closes prior thin items or
 only adds capability.
- Append to `<CHANGELOG path>`:
 ```
 ## <Milestone name> (<tier>) — <YYYY-MM-DD>

 - <bullet>
 ```

## Integration matrix (when multi-mode or multi-verb)

| <axis> | <feature 1> | <feature 2> | … |
|---|---|---|---|
| ... | ... | ... | ... |

## Error-footer canonical pairs

| Error | `try:` |
|---|---|
| `<terse description>` | `<one specific command or fix>` |

(Parameterized over a depth test so every error case is exercised.)

## Config additions (when relevant)

```toml
[defaults]
<new_knob> = "<default>"
```

## Out of scope (explicitly not in this milestone)

- <one bullet per V1-candidate scope item>
- <…>

## Dependencies (Tier 1 / 2 / 3 policy)

Tier 1 (utility, free): <list with one-line justification each>.
Tier 2 (architectural, log to `DEPENDENCIES.md`): <list or "none expected">.
Tier 3 (blocked): same blocks as prior riders.

## Engineering invariants (do not violate)

- **No `<struct>` schema changes.**
- **One depth test before each phase implementation.** A phase whose
 tests were never red is suspect.
- **<Domain-specific invariants>.**
- **No silent expansion.** Anything beyond P1–P11 goes into
 `V1-CANDIDATES.md`.
- **<Spec-pinning invariants>**: e.g., "the preview block format is
 depth-tested; changing whitespace changes the spec."

## Process invariants

- Phased local commits only. No `git push`.
- Each phase ends with the relevant depth tests passing and a
 CHANGELOG entry naming the SHA.
- After P11, optionally capture a demo (asciinema cast / screenshots /
 short video) under `<project>/<demo-path>`. Skip when the change
 isn't user-visible.
- If a phase reveals a V1-architecture decision, stop and log it in
 `V1-CANDIDATES.md`; do not silently expand scope.
```

## Discipline checklist (the invariants this skill carries)

1. **Two documents, two budgets.** Goal ≤4000 chars; rider unbounded.
 Run `wc -c` on the goal before declaring done.
2. **Timestamped filenames.** Both goal and rider are named
 `<YYYY-MM-DD>-<HHMM>-<project-slug>-<topic>-{goal,rider}.md`. The
 `<HHMM>` is the local 24-hour authoring time (e.g., `1444`). The
 pair shares one timestamp so they sort together; never split them
 across minutes. This makes `ls docs/goals/` chronological.
3. **Phased local commits only.** Never tell the executor to `git push`.
4. **Files-not-fields.** When the project has persistent state
 structs (DB schema, config struct, state machine), durable
 per-feature state should live in files inside the working tree
 (`<some>/<name>.json`) rather than as new struct fields. Schema
 changes are last-resort. Skip this invariant for projects without
 such structs.
5. **Depth tests first.** Each phase's named tests are written and
 watched fail before implementation. List them by name in the rider
 so a `grep -c '^ fn '` enforces presence.
6. **Architecture-doc discipline.** P11 always updates whatever
 architecture / as-built doc the project keeps, plus CHANGELOG. If
 there's a "what's shipped vs thin" section, the thin list is
 honest — only remove items the rider actually closes.
7. **V1 candidates.** Anything out of scope goes to
 `docs/V1-CANDIDATES.md`, not silently expanded scope.
8. **Conventional commits, scoped.** `docs(goals): add <topic> goal+rider`
 for the goal-rider commit itself. `feat(<scope>):` / `fix(<scope>):`
 / `chore(<scope>):` for execution commits.
9. **Frontmatter mirrors the project's own convention** for any
 human-readable artifacts. If the project has prior impl docs
 under `docs/implementation/` or similar, match their frontmatter
 shape (Date / Status / Commit span / Owner / …). If not, propose
 a minimal frontmatter and stick to it across riders.
10. **Friendliness is verifiable.** Auto-detect, preflight + preview,
 refuse with `try: <command>`, one-command rollback, lifecycle
 hints. Each is exercised by a depth test.
11. **Judgment in markdown, invariants in code.** When the project
 has a skill / prompt-template / config-driven prompt mechanism,
 prefer that over a hardcoded const so users can tune voice or
 behavior without a rebuild. (Project-specific; skip if no such
 mechanism exists.)

## Anti-patterns to avoid

- Inventing V1 architecture inside an alpha rider.
- Schema changes without a stated strong reason.
- Backwards-compatibility shims for code that no caller uses.
- Comments explaining WHAT the code does (well-named identifiers
 already do that).
- Half-finished implementations ("we'll finish in P12").
- Duplicating invariants from prior riders verbatim — just say
 "invariants hold" and reference them.
- Depth tests written after implementation.
- Stop conditions that don't tie to verification ("stop when it
 feels done" is not a stop condition).
- Inventing CLI verbs not in the goal.
- Adding emojis to written artifacts.
- "TODO: maybe add X" lines — either it's in scope (P-numbered) or
 it's a V1 candidate.

## Standard 11-phase shape

A typical rider has these phases (adapt the names; eleven is a target,
not a hard rule — fewer or more is fine if the structure earns it):

- **P1**: Data model / plumbing — new module / file path / frontmatter
 helpers. No behavior change yet.
- **P2–P3**: Foundation — new primitive types, base mechanism.
- **P4–P8**: Feature implementation — one phase per major slice; each
 phase ships with end-to-end depth tests.
- **P9**: Integration with prior verbs / modes / state machines.
- **P10**: Cross-cutting friendliness pass — flags like `--quiet` /
 `--plain`, error-footer routing, post-action hints, help-text
 grouping.
- **P11**: Architecture-doc update + CHANGELOG + (optional) demo
 capture (doc-only; no depth test).

## Commit message for the goal-rider pair itself

```
docs(goals): add <topic> goal+rider (<one-line headline>)

<2–3 sentence summary: what the goal is for; what the rider prescribes;
what's explicitly out of scope. Mention named depth-test discipline,
files-not-fields posture (if applicable), V1 invention guard.>
```

Add the project's standard `Co-Authored-By:` footer if it uses one.

## Validation steps (run before declaring done)

```bash
PROJECT=<absolute path to project root>
DATE=$(date +%Y-%m-%d)
HHMM=$(date +%H%M)
PROJECT_SLUG=<short project name>
TOPIC=<short topic slug>
GOAL=$PROJECT/docs/goals/$DATE-$HHMM-$PROJECT_SLUG-$TOPIC-goal.md
RIDER=$PROJECT/docs/goals/$DATE-$HHMM-$PROJECT_SLUG-$TOPIC-rider.md

# 1. Goal must be under 4000 chars
wc -c "$GOAL" # expect ≤4000

# 2. Rider must have ≥11 phase headers
grep -c '^### P[0-9]' "$RIDER" # expect = 11

# 3. Rider must have the standard top-level sections
for section in "Posture" "Phases" "Out of scope" "Dependencies" \
 "Engineering invariants" "Process invariants"; do
 grep -q "^## $section" "$RIDER" || echo "MISSING: $section"
done

# 4. Both files cite each other's absolute paths
grep -F "$RIDER" "$GOAL" || echo "goal does not reference rider"
grep -F "$GOAL" "$RIDER" || echo "rider does not reference goal"

# 5. Stage and commit
cd "$PROJECT" && git add "$GOAL" "$RIDER" && git status
```

## Reference exemplars to mine

Before drafting, read at least one recent goal+rider pair from the
target project, if any exist. Look in `docs/goals/`, `docs/specs/`,
`docs/planning/`, or similar.

If the project has no prior pairs, suggest the user create one from
this template and treat it as the baseline. Optionally, ask whether
they want to point you at an exemplar from another project to crib
voice and shape from.

The discipline travels: the pattern works the same across Rust, Go,
TypeScript, Python, and mixed stacks. Only the toolchain commands
(`<project's build+test+lint+fmt command>`) change.