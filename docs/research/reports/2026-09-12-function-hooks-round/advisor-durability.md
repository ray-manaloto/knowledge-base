# Advisor durability — research in progress

**Agent:** `kb-codex-astra-advisor`
**Started:** 2026-09-12
**Directive (Ray, 2026-09-12, verbatim):** "but have kb-codex-astra-advisor review
its agent definition and optimize it for long running work and durable results
and/or a way to resume / research what claude provides, using claude graphify
sources and 'claude --help'"

Status: IN PROGRESS. Written incrementally. Sections appear as they are established.

---

## 1. CAN WE EDIT `fable-advisor`? — ESTABLISHED: NO

`fable-advisor` is a **plugin-provided, user-global** agent. Measured
2026-09-12 with `find ~/.claude/plugins -name "*advisor*" -maxdepth 6`:

```
/Users/rmanaloto/.claude/plugins/cache/fable-orchestrator/fable-orchestrator/1.21.0/agents/fable-advisor.md
/Users/rmanaloto/.claude/plugins/marketplaces/fable-orchestrator/agents/fable-advisor.md
/Users/rmanaloto/.claude/plugins/marketplaces/fable-orchestrator.bak/agents/fable-advisor.md
```

Control arm for the probe: the same `find` shape with `-name "*.md"` over the
same root returned **7,541** files, so the probe reads the tree and
discriminates — the three hits are a real positive, not an artifact of a
readable-but-empty search.

Both live paths are under `/Users/rmanaloto/.claude/`, which
`.claude/rules/do-not.md` entry 11 forbids this repo from mutating:

> **Do NOT intentionally MUTATE user, global, or system configuration as part
> of repository work — from an agent session, ever.** No writing to
> `~/.claude`, `~/.gemini`, `~/.codex/config.toml`, or any other
> global/system/user config. This repo edits PROJECT settings only.

A plugin cache is additionally **regenerated on update** — an edit there is
erased by the next plugin bump even if the rule permitted it.

**Consequence for the deliverable:** the answer cannot be "edit fable-advisor".
The live options are (a) a repo-local agent under
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/agents/`, and
(b) per-spawn prompt instructions. Detail and recommendation below.

---

## 2. THE REPO-LOCAL ROSTER — MEASURED 2026-09-12

`ls /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/agents/*.md | wc -l` -> **9**

| agent | bytes | codex twin |
|---|---|---|
| kb-adversarial-verifier.md | 5834 | yes |
| kb-advisor.md | 4050 | yes |
| kb-codex-advisor.md | 7091 | yes |
| kb-codex-astra-advisor.md | 9729 | yes |
| kb-codex-astra-reviewer.md | 15760 | yes |
| kb-corpus-curator.md | 4862 | yes |
| kb-extraction-worker.md | 3609 | yes |
| kb-synthesist.md | 4677 | yes |
| kb-tool-researcher.md | 6347 | yes |

All 9 have a `.codex/agents/*.toml` twin. Nothing generates one from the other.

---

_(further sections appended as established)_

## 3. 🔴 SUBAGENT RESUME EXISTS — THE HEADLINE FINDING

**A subagent that went idle does NOT have to be re-run.** It can be resumed,
retaining its full conversation history including every tool call and result.

Source (pinned, in this repo):
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/sources/claude-code-docs/content/en/docs/claude-code/agent-sdk/subagents.md`

`:390-392`
> ## Resume subagents
> You can resume a subagent to continue where it left off rather than starting
> fresh. A resumed subagent retains its full conversation history, including all
> previous tool calls, results, and reasoning.

`:396`
> When a subagent completes, the Agent tool result includes a text block
> containing `agentId: <id>`. The built-in `Explore` and `Plan` agents are
> one-shot and don't return an `agentId`, so use a custom agent or
> `general-purpose` when you need to resume.

`:400`
> **Resume the session**: pass `resume: sessionId` in the second query's
> options, and include the agent ID in your prompt. Each `query()` call starts a
> new session by default, and you must resume the same session to access the
> subagent's transcript.

`:530`
> Subagent transcripts are stored in separate files and persist independently of
> the main conversation.

`:156` — and this one bears directly on THIS agent's own `maxTurns: 40`:
> `maxTurns` … Maximum number of agentic turns before the agent stops. When the
> agent reaches the limit, **Claude Code returns its output marked as partial,
> and you can resume the agent to continue.** The partial marking requires
> Claude Code v2.1.246 or later.

Installed `claude --version` = **2.1.269**, so the partial-marking floor is met.

`:203` — the other half of the idle mystery:
> An API error that ends the subagent early, such as a rate limit, is **never
> delivered as its result.**

That single line is the most likely mechanism behind the three recorded
"advisor went idle without reporting" events. It is not a lost report; it is a
result that the harness structurally cannot deliver. **No amount of "write the
verdict before returning" prose fixes the delivery path — but a file on disk
survives it, which is exactly why the file convention works.**

### Control arm for this probe
`grep -c "^#"` on the same file returned **23** headings, and `wc -l` **728**,
so the file is present and readable. An earlier grep of the same file for the
literal graph label *"Subagent transcripts persist separately"* returned zero —
that label is an **extraction node label**, living in
`sources/extractions/claude-code-docs-2026-09-01-docs.json:9869`, not prose in
the doc. The doc's own wording at `:530` is *"stored in separate files and
persist independently"*. A zero against the doc was a term-spelling miss, not an
absence.

## 4. THE MEASURED GAP IN OUR OWN DEFINITIONS

`grep -c` over each of the 9 definitions for persistence-shaped instructions
and for the literal `.agent/kb/reports` path (control arm: the same loop for a
term known absent returned 0 for all 9, so the loop discriminates):

| agent | persistence instruction | names `.agent/kb/reports` | `tools:` line | can it write at all? |
|---|---|---|---|---|
| kb-adversarial-verifier | **0** | **no** | `Bash, Read, Grep, Glob, Write, Edit` (`:6`) | yes, unused |
| kb-advisor | **0** | **no** | `Bash, Read, Grep, Glob` (`:6`) | **no Write tool** |
| kb-codex-advisor | 5 | yes | `Bash, Read, Grep, Glob, Write` (`:4`) | yes |
| kb-codex-astra-advisor | 7 | yes | `Bash, Read, Grep, Glob, Write` (`:4`) | yes |
| kb-codex-astra-reviewer | 4 | **no** | `Bash, Read, Grep, Glob, Write` (`:4`) | yes |
| kb-corpus-curator | **0** | **no** | **absent** (inherits all) | yes, unused |
| kb-extraction-worker | 2 | **no** | `Read, Write, Grep, Glob` (`:6`) | yes |
| kb-synthesist | **0** | **no** | `Bash, Read, Grep, Glob, Write, Edit` (`:6`) | yes, unused |
| kb-tool-researcher | 1 | yes | **absent** (inherits all) | yes |

**Four of nine — `kb-adversarial-verifier`, `kb-advisor`, `kb-corpus-curator`,
`kb-synthesist` — carry NO persistence instruction at all**, and three of those
four hold `Write` (or inherit it) and simply never use it. Five of nine never
name the reports path.

### 🔴 A RECORDED FACT IS WRONG

The work-memory entry `always-consult-fable-advisor-before-codex-implementer.md`
says, verbatim: *"`kb-advisor` (has Write) is the reliable substitute"*.

Measured 2026-09-12, `.claude/agents/kb-advisor.md:6` reads:

```
tools: Bash, Read, Grep, Glob
```

**`Write` is absent.** `kb-advisor` is the ONE advisor in the roster that cannot
call the Write tool, and it is the one the memory recommends as the durable
substitute. It can still persist via a `Bash` heredoc, so the recommendation is
recoverable — but not by the route the memory names. The file has not been
touched since 2026-08-13 (mtime), and the memory was written 2026-08-29, so the
memory was wrong when written rather than overtaken.


## 5. WHAT CLAUDE CODE PROVIDES — the capability table

Installed: `claude --version` -> **2.1.269 (Claude Code)**, measured 2026-09-12.
Pinned doc source: `sources/claude-code.manifest` -> `ref = v2.1.258`,
`commit = aef74afe01f65b602258d6102b0da9730ac6f0aa`.

| mechanism | what it does | helps a lane that went idle? | citation |
|---|---|---|---|
| **`SendMessage` to a completed subagent** | **auto-resumes it in the background with no new `Agent` invocation** | **YES — this is the primary answer** | `sources/claude-code-docs/content/en/docs/claude-code/sub-agents.md:1041` |
| **Subagent resume (full history)** | resumed subagent retains every prior tool call, result and reasoning; picks up exactly where it stopped | YES | same file `:1021-1023` |
| **`agentId` returned on completion** | Claude receives the agent's id; it is the resume handle | YES — required for resume | same file `:1025`; SDK form `agent-sdk/subagents.md:396` |
| **`maxTurns` partial return** | at the limit, output is returned **marked partial** with a hint to continue via `SendMessage`, instead of appearing finished | YES — converts a silent stop into a resumable partial | `agent-sdk/subagents.md:156`; shipped **2.1.246** (`sources/claude-code/CHANGELOG.md:343`) |
| **Separate subagent transcripts on disk** | stored in separate files, persist independently of the main conversation | YES — readable even if the result never arrives | `agent-sdk/subagents.md:530` |
| **`/tasks`** | lists everything backgrounded in the session, **including subagents that have finished**; check on, attach to, or stop each | YES | `docs/claude-code/agents.md:54` |
| **@-mention typeahead** | named background subagents appear with their status | partially — tells you it is alive | `docs/claude-code/agents.md:53` |
| **Rate-limit / server-error partial return** | subagents cut off by a rate limit or server error return their **partial work** instead of silently failing | YES | `CHANGELOG.md:1481`, shipped **2.1.199** |
| `claude --bg` / `agents` / `attach` / `logs` / `stop` / `rm` / `respawn` | manage background **SESSIONS** (top-level `claude` processes) | **NO — wrong layer.** These do not address subagents spawned inside a session | `claude --help`; `claude agents --help` |
| `claude --resume` / `-c` / `--fork-session` / `--session-id` | resume a **conversation/session** | NO — session layer, not subagent layer | `claude --help` |
| `--no-session-persistence` | **disables** saving to disk; only with `--print` | n/a — confirms persistence is the DEFAULT | `claude --help` |
| `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` | caps concurrent subagents (default 20) | no — but explains a fan-out that appears stalled | `CHANGELOG.md:1023` |

### 🔴 The layer distinction that decides the recommendation

`claude --bg`, `claude agents`, `claude attach`, `claude logs`, `claude respawn`
are **background SESSION** management — whole `claude` processes. A lane spawned
by the Agent tool *inside* a session is a **subagent**, a different layer with a
different toolkit (`/tasks`, `SendMessage`, `agentId`). The docs say so
explicitly at `docs/claude-code/agents.md:53`: *"Despite the similar name,
`/agents` is separate from `claude agents`."* Reaching for the session tools to
rescue an idle subagent is the natural mistake and it does not work.

### 🔴 The recorded belief is OUT OF DATE, and by a wide margin

Work-memory `subagent-lanes-go-idle-without-reporting.md` (2026-08-25 → 08-29)
records lanes going idle and a resend recovering them only ~2 times in 4. Two
upstream fixes bear on that, and **both predate or postdate it in ways that
matter**:

- `CHANGELOG.md:1481`, version **2.1.199**, tag date **2026-07-02**
  (`git for-each-ref` in `sources/claude-code`): *"Fixed subagents cut off by a
  rate limit or server error silently failing instead of returning their partial
  work to the parent."* This shipped **~8 weeks BEFORE** the recorded incidents,
  so it is NOT their explanation.
- `CHANGELOG.md:343`, version **2.1.246**: the `maxTurns` partial return with a
  `SendMessage` hint. I could **not date this tag** — the local clone at
  `sources/claude-code` has only tags up to v2.1.199 fetched (`git rev-parse
  v2.1.246^{commit}` -> `fatal: Needed a single revision`, while
  `v2.1.199^{commit}` -> `125d63feaec6e89708d95bbb4ed7dae0f62eb39f`, and a
  deliberately bogus `v9.9.9` errors differently — so the probe discriminates
  and the absence is a fetch gap, not a missing tag upstream). **UNVERIFIED
  whether 2.1.246 predates the incidents.**

The memory's own later self-correction is the one that survives contact with the
docs: *"Lanes here are SLOW, not dead"*, and *"the reliable recovery is the
agent's TRANSCRIPT on disk, not a resend"*. The docs now supply the mechanism
the memory was missing — `sub-agents.md:1041`, a completed subagent
**auto-resumes** on `SendMessage`; and `:1043`, a subagent **you cancelled**
returns a refusal instead. That asymmetry is almost certainly the "2 of 4"
the memory measured without being able to explain.


## 6. 🔴 THE GAP IN THIS AGENT'S OWN DEFINITION — it persists at the END, not incrementally

`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/agents/kb-codex-astra-advisor.md:157-164`
currently reads, verbatim:

```
## Write the verdict to disk BEFORE you return

An advisor lane in this repo went idle without reporting, and its verdict
survived only because it had been told to write to disk first. As soon as the
lane returns, `Write` the verdict to
`.agent/kb/reports/agents/kb-codex-astra-advisor.md` (per
`agent-report-persistence.md`) **before** composing your reply. If you are killed
or go idle after that point, nothing is lost.
```

**"As soon as the lane returns" is an END-OF-RUN instruction.** This agent's own
budget is `maxTurns: 40` and a consult is bounded at 1800s polled in sub-600s
slices — so there are up to ~20 polls plus graph reads *before* the lane returns
anything. Killed at poll 12, this definition has written **nothing**, because
nothing has been written yet by construction.

That directly contradicts the repo's own rule,
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/rules/agent-report-persistence.md`
rule 3:

> **Instruct agents to persist INCREMENTALLY, not at the end.** … Two agents
> that held everything in memory died silently after ~40 minutes and left
> **nothing** … An agent that dies having written 13 of 20 sources leaves 13.
> Durable capture must be incremental, never end-of-run.

So the agent most explicitly written for durability is following the
end-of-run pattern that rule exists to forbid. The same reading applies to
`kb-codex-advisor.md` and `kb-codex-astra-reviewer.md`, which carry the same
"before you return" framing.

Second gap, smaller: the definition tells the agent to *say so* when approaching
`maxTurns`, but never tells the CALLER that a partial return is **resumable** —
which, per `sub-agents.md:1027` and `:1041`, it is.


## 7. THE CODEX CONSULT — ran clean, verdict quoted

Lane: `mise run kb-codex -- --model gpt-6-astra --effort xhigh --sandbox read-only
--timeout 1500 --output <path>`, launched as a harness background run and polled.
**rc 0. No refusal, no capacity error, no timeout.** It returned a substantive
4,136-byte verdict.

Its verdict, first line verbatim:

> **Choose (b): a caller-owned recovery protocol, recorded in the repo-local
> persistence rule. Caller verification and resume are load-bearing. No Astra
> definition change or mise task is needed.**

Its deciding risk, verbatim:

> The deciding risk is **termination before the child saves its verdict or
> delivers a result**. A child-side instruction cannot guarantee execution after
> that termination.

Its failure-mode table, verbatim:

| Failure mode | What "write first" covers | Required recovery |
|---|---|---|
| **Finished, report undelivered** | Preserves a verdict already written successfully. | Caller reads it. If missing or incomplete, `SendMessage` resumes the completed agent to persist/resend. |
| **`maxTurns` reached** | Preserves checkpoints already written; an end-only write may never execute. | Treat output as partial. Resume the same agent using its returned ID and retained history. |
| **API error ends the agent** | Preserves only material successfully written before failure. | Recover checkpoints and available transcripts. The error is **never delivered as its result**; neither a completion result nor resumability is established by the supplied evidence. |

Its own stated limits, verbatim:

> **Not verified:** which failure class caused the three incidents, whether an
> API-failed instance remains messageable, or whether nested work survives that
> failure. No recovery probe was run. Graph health remains unverified because the
> mise query failed on filesystem permissions and the direct query was
> hook-blocked; root `findings.md` was absent. No files were changed.

### 🔴 WHERE I DO NOT SIMPLY RELAY THIS LANE

Its clause *"No Astra definition change … is needed"* **rests on how I framed the
definition to it.** My prompt told it the body *"already says: write the verdict
to `.agent/kb/reports/agents/<name>.md` BEFORE composing the reply."* I did not
tell it that "before composing your reply" is an **end-of-run** write, nor that
`agent-report-persistence.md` rule 3 forbids exactly that. The lane reasoned
correctly from what it was given; it was not asked the question section 6 above
answers. So its "(b) only" should be read as **"(b) is load-bearing"**, which it
argues well, and **not** as "the definition is fine" — my own direct read of
`kb-codex-astra-advisor.md:157-164` says it is not.

Its own table concedes the point in the `maxTurns` row: *"an end-only write may
never execute."*

### The one citation of its I verified independently

It said to insert after item 3 in `agent-report-persistence.md:73`. Measured:
`grep -n "Instruct agents to persist INCREMENTALLY"` -> **line 73**. The citation
resolves exactly.

## 8. THE RECOMMENDATION

**Both halves, and the caller half is the load-bearing one.** The child-side fix
alone cannot survive the failure it is aimed at — that is the Astra lane's
deciding risk and it is correct.

### (A) CALLER-SIDE — load-bearing. Add to `.claude/rules/agent-report-persistence.md` after line 84 (end of rule 3)

Use the Astra lane's block, which is quoted in full in section 7's source file
and reproduced here ready to paste:

```markdown
3b. **The caller owns recovery.** Give each consult a unique run ID and
    report path in its spawn prompt, overriding any default path. Require
    the run ID, PARTIAL/COMPLETE status, remaining work, and any nested
    task/session IDs and raw-output paths alongside the verbatim report.
    Record the Claude agent ID/name when available.

    On idle, partial, or missing delivery, read the report. Accept only
    this run's substantive COMPLETE verdict; existence, placeholders and
    idle notifications prove no completion. For a completed or maxTurns
    agent with a usable ID/name, use SendMessage(to=<Claude ID/name>):
    "Continue this consult; inspect <report>, finish remaining work,
    persist the verdict and resend it. Reuse existing nested work."
    Await and verify the result; sending is not receipt.

    An API error is a failure, never a verdict. Recover saved artifacts;
    do not presume resumability. Inspect any resume response. Before
    redispatch, establish that prior work stopped and carry its checkpoint
    into a fresh run. Honor user cancellation. Preserve the original
    deadline and retry budget across resumes; do not reset them.
```

This is grounded in `sub-agents.md:1041` (a completed subagent auto-resumes on
`SendMessage`) and `:1043` (one you cancelled refuses), which together explain
the memory's unexplained "2 of 4".

### (B) CHILD-SIDE — the smaller, still-real fix. Replace `kb-codex-astra-advisor.md:157-164`

The current heading promises durability and delivers an end-of-run write.
Replacement, same length class so the size budget is unaffected:

```markdown
## Write to disk AS YOU GO, not when you return

An advisor lane here went idle without reporting, and its verdict survived only
because it had been written first. "Before you return" is not enough: a consult
is ~20 polls long, and killed at poll 12 an end-of-run instruction has written
nothing. `agent-report-persistence.md` rule 3 forbids exactly that shape.

Create `.agent/kb/reports/agents/kb-codex-astra-advisor.md` in your FIRST turn,
with the question and the constraints. Append each graph finding, the launched
argv, and every poll result as you get it. Append the lane's verdict the moment
it lands, before composing any reply.

If you stop at `maxTurns`, your output is returned marked PARTIAL and you are
resumable — say which sections are settled and which are not, so the caller's
`SendMessage` resume picks up rather than restarts.
```

Apply the same change to `kb-codex-advisor.md` and `kb-codex-astra-reviewer.md`,
which carry the same "before you return" framing.

**Remember this is a TWO-FILE change**: each has a `.codex/agents/*.toml` twin
and nothing generates one from the other. The twin's matching text is at
`.codex/agents/kb-codex-astra-advisor.toml:214-218`.

### (C) THE FOUR AGENTS WITH NO INSTRUCTION AT ALL

`kb-adversarial-verifier`, `kb-advisor`, `kb-corpus-curator`, `kb-synthesist`.
This is the largest measured gap and the cheapest to close. Each needs one line
naming its report path. `kb-advisor` additionally needs either `Write` added to
its `tools:` line (`kb-advisor.md:6`) or an explicit instruction to persist via
a Bash heredoc — today it is the only advisor that cannot call `Write`.

### What I do NOT recommend

- **Editing `fable-advisor`.** Forbidden (section 1) and erased by the next
  plugin update regardless.
- **A new mise task.** The Astra lane is right that nothing here needs one; the
  mechanisms are `SendMessage` and a file path, both already available.
- **Changing `maxTurns: 40`, the absent `model:`/`effort:`, or the twin's model
  pin.** All are load-bearing for reasons documented in the twin at
  `.codex/agents/kb-codex-astra-advisor.toml:9-30`.

## 9. COULD NOT ESTABLISH

1. **Which failure class caused the three recorded idle events.** The rate-limit
   silent-failure fix (2.1.199) shipped 2026-07-02, ~8 weeks BEFORE them, so it
   is not the explanation. The memory's own correction — *"lanes are SLOW, not
   dead"* — remains the best-supported reading, but it is not proven.
2. **The release date of 2.1.246** (the `maxTurns` partial return). The local
   clone `sources/claude-code` has tags only to v2.1.199;
   `git rev-parse v2.1.246^{commit}` -> `fatal: Needed a single revision`, while
   `v2.1.199^{commit}` resolves and a bogus `v9.9.9` errors differently. The
   probe discriminates, so this is a fetch gap, not an upstream absence.
3. **Whether an API-failed subagent remains messageable.** `agent-sdk/subagents.md:203`
   says the error is never delivered as a result; it does not say whether the
   instance can still be resumed. No arm was run — running one means deliberately
   inducing an API failure.
4. **The codex lane's sandbox banner.** `--sandbox read-only` was passed
   explicitly and the lane reported *"No files were changed"*, but the captured
   output file holds only the final message, so the banner's `sandbox:` line —
   the one valid observable — was **not captured**. Treat the sandbox as
   asserted-by-flag, not observed.
5. **The five research surfaces the task named** — `/last30days:last30days`,
   `/firecrawl:firecrawl-search`, `/firecrawl:firecrawl-developer-index`,
   `/exa:search`, `/context7:docs` — **were not reachable from this lane.** This
   agent's frontmatter declares `tools: Bash, Read, Grep, Glob, Write`
   (`kb-codex-astra-advisor.md:4`); no MCP or Skill tool is in that set, so those
   surfaces are absent by construction, not skipped by choice. They remain
   genuinely untouched and a lane with the right tool grant should still run them.
6. **No recovery probe was run.** Nothing here dispatched a lane, let it go idle,
   and then recovered it by `SendMessage`. The whole resume mechanism is
   documented-and-cited, **not arm-tested**. That is the single most valuable
   arm still owed, and per `probes-need-a-control-arm.md` it should be run before
   this protocol is trusted in anger.

## GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — `CHANGELOG.md` at pinned `v2.1.258` / `aef74afe01f65b602258d6102b0da9730ac6f0aa`; the subagent partial-return and resume entries.
- [thevibeworks/claude-code-docs](https://github.com/thevibeworks/claude-code-docs) — `content/en/docs/claude-code/sub-agents.md`, `agent-sdk/subagents.md`, `agents.md`; the resume, transcript-persistence and background-vs-session semantics. Pinned as `sources/claude-code-docs.manifest`, `ref = main`, `commit = 1e8a2c489fc9d10df612b4ce19e6a9ad1e555d36`. **NOTE: a third-party MIRROR of the Claude Code docs site, not an Anthropic-owned repo** — an earlier draft of this line misattributed it to `anthropics/`, which would have made every doc citation above look first-party.
- [openai/codex](https://github.com/openai/codex) — referenced via `.codex/agents/kb-codex-astra-advisor.toml:9-30` for the `role.rs:191-192` effort-clobber rationale; not re-read this round.

---

# 🔴 CORRECTION ROUND — prior art found by `kb-recall-work`, and it INVERTS part of §8

Added after the team lead raised `kb-recall-work` to a standing precondition. My
first pass ran `kb-recall`/`kb-recall-work` but **read only the summary counts,
never the report file** — the exact failure the lead named. Reading
`.agent/kb/recall/{advisor-lane,agent-definition,subagent-idle}.md` surfaced
prior art that changes the recommendation.

## C1. This work has an OPEN TICKET — `#520`, and it has been CORRECTED TWICE

`gh issue view 520 -R ray-manaloto/knowledge-base` — **OPEN**, opened 2026-08-26,
3 comments. Title: *"Lane reports lag by hours and read-only lanes have no
channel that does not — an idle lane is not a dead one."*

Its three unchecked boxes are, almost verbatim, the three things §8 proposed:

- [ ] *"Determine whether this is a harness defect or a prompt-shape effect."*
- [ ] *"Make the incremental-write instruction **structural** rather than typed:
  a standing clause the dispatch always carries."*
- [ ] *"Consider a `kb-*` task that reads the on-disk report by convention, so
  recovering a silent lane is one command instead of an `ls` and a guess."*

**So §8 is not a new proposal. It is an unimplemented ticket from 2026-08-26.**
The right framing for Ray is "here is why #520 has not landed", not "here is an
idea".

### 🔴 The Astra lane's "no mise task is needed" is now contradicted by prior art

Its verdict said *"No Astra definition change or mise task is needed."* #520's
third box explicitly asks for a `kb-*` task that reads the on-disk report by
convention. The lane could not have known — **I did not give it #520, because I
had not read the recall report yet.** That is my defect, not the lane's.

## C2. 🔴 The "delivery fails 14 of 14" claim is RETRACTED UPSTREAM — lanes are LATE, not lost

#520's body measured *"8 of 8"* then *"14 of 14 across two sessions"* returning
nothing. **Both comments retract it.**

Second correction, verbatim: *"Every lane this session eventually reported back
**with a full structured summary**. They arrived in a batch, roughly **1–2
hours** after each lane went `idle` in `ListAgents`."* Counted **11 of 13
reported. Not 1 of 10.**

And the diagnosis, verbatim: *"a **timing** observation being read as a
**delivery** failure … An orchestrator that polls, sees `idle`, sees no message,
and concludes 'dead' is **measuring latency and calling it loss**."*

**This changes why incremental writes matter.** #520's surviving point, verbatim:
*"Incremental disk writes remain worth mandating — not as a rescue from silence,
but because they make a lane's work **usable before its report arrives**. Every
finding acted on in this round came off disk hours before the corresponding
summary landed. That is a real speedup, not a workaround."*

My §6 argued incremental persistence as insurance against death. The measured
reason is better and different: **latency**. Same change, stronger and more
honest justification.

## C3. 🔴 `kb-advisor` HAS NO WRITE TOOL — third independent confirmation, and the memory is still wrong

This is now established three ways:

1. **Measured by me today**: `.claude/agents/kb-advisor.md:6` -> `tools: Bash, Read, Grep, Glob`.
2. **#520 comment 1, 2026-08-26, verbatim**: *"Read-only agent types have no
   incremental fallback: `premise-verifier`, `kb-advisor` and the `*-reviewer`
   types have no Write tool by design, so the disk-write mitigation cannot be
   given to them at all. When one of those returns nothing, its findings are
   genuinely gone."*
3. **#520 comment 2, surviving point 2, verbatim**: *"Read-only agent types still
   have no fallback channel. `premise-verifier`, `kb-advisor` and the
   `*-reviewer` types cannot be told to write incrementally."*

**The work-memory file `always-consult-fable-advisor-before-codex-implementer.md`
still says `kb-advisor` "(has Write)" and recommends it as the reliable
substitute for that reason.** It was wrong when written (2026-08-29), it
contradicts a ticket comment written three days earlier, and it was restated back
to me as fact in this round's own task brief. **That memory file needs
correcting — it is actively routing work to the one advisor that cannot persist.**

Note the one nuance: `kb-advisor` does hold **`Bash`**, so it can write via a
heredoc. #520's "cannot be told to write incrementally" is true of the `Write`
tool and slightly overstated as an absolute. `premise-verifier` and the
`*-reviewer` types are the genuinely unrecoverable ones.

## C4. THE RECOMMENDATION, REVISED

The ordering in §8 was wrong. Corrected priority:

1. **🔴 FIRST — fix the wrong memory (C3).** It is one file, it is actively
   misrouting, and it costs nothing. Nothing else on this list matters if the
   next session reads "kb-advisor has Write" and dispatches accordingly.
2. **SECOND — `kb-advisor.md:6` gets `Write`**, or an explicit heredoc
   instruction. This is #520's *"the real defect and the original issue's most
   durable point"*, open since 2026-08-26.
3. **THIRD — the child-side incremental change (§8B)**, justified by **latency**
   (C2) rather than death. Applies to `kb-codex-astra-advisor.md:157-164` and its
   two siblings, each a two-file change with its `.codex/agents/*.toml` twin.
4. **FOURTH — the caller-side protocol (§8A)** and the `kb-*` recovery task
   (#520's third box). The Astra lane's block is still good text; its "no task
   needed" clause should be dropped.
5. **`docs/research/reports/2026-08-06-roster-synthesis.md:304-306`** already
   states the roster-wide convention: *"**Every findings-bearing agent persists
   incrementally** to `.agent/kb/reports/agents/<name>.md` — already in
   kb-tool-researcher; should be stated in all defs."* Written 2026-08-06; my
   measurement today says **4 of 9 still do not**. So this is a *third*
   independent statement of the same unimplemented recommendation.

## C5. WHAT THE RECALL PROBES ACTUALLY RETURNED (so the numbers are not inherited)

| topic | tracked_files | issues | plans | memory | report |
|---|---|---|---|---|---|
| `advisor lane` | 280 / 3427 | 39 / 969 | 145 / 218 | 166 / 426 | `.agent/kb/recall/advisor-lane.md` (112 KB) |
| `agent definition` | 255 / 3427 | 49 / 969 | 25 / 218 | 106 / 426 | `.agent/kb/recall/agent-definition.md` (110 KB) |
| `subagent idle` | 103 / 3427 | 10 / 969 | 53 / 218 | 34 / 426 | `.agent/kb/recall/subagent-idle.md` (101 KB) |
| `agent durability` (first pass) | 42 / 3427 | 5 / 969 | 7 / 218 | 100 / 426 | `.agent/kb/recall/agent-durability.md` (102 KB) |

Note the two-to-three-word discipline paying off: `"agent durability"` matched
**42** tracked files and **5** issues; `"advisor lane"` matched **280** and
**39**, and **`subagent idle` is the one that found #520**. My first-pass topic
was the weakest of the four — it ran, it did not refuse, and it returned the
wrong neighbourhood.

## C6. ADDITIONAL OPEN TICKETS THIS TOUCHES (not previously cited)

- **`#520`** (open) — the parent ticket for all of this.
- **`#744`** (open) — *"kb-lane-verify: verify a lane's REAL model/effort/flags
  against what we configured."* Directly owns my §9.4 UNVERIFIED (the codex
  sandbox banner was not captured).
- **`#324`** (open) — *".codex/agents/*.toml drop the model: field, so per-agent
  model routing does not carry over."* Bears on the two-file twin change.
- **`#750`** (open) — *"kb-review: a receipt's lane field is a claim, not a
  record."* Same class as #744.
- **dotfiles `#298`** (open, **2026-09-12 — today**) — *"Agent spawn/liveness is
  unreliable in BOTH directions — dead agents look alive, live agents look
  dead."* The sibling repo is working the same problem right now.
