# res-skillsurvey — empirical survey of multi-skill families on this machine

Question being settled: should `/goal` tooling ship as ONE skill, TWO
(`goal-author` + `goal-audit`), or THREE (those two plus an orchestrating
wrapper)? Evidence gathered from skills already installed locally.

Status: COMPLETE

**Verdict:** a wrapper skill is a *real mechanism* — but only omc's `deep-dive`
actually uses it (a literal `Skill("…")` call in the body). Every other
cross-skill link on this machine, including both plugins the lead named, is
prose naming a target. The cheap shipped form of a wrapper is **7 lines with
`disable-model-invocation: true`**.

## 1. The inventory

### 1a. The structural surprise: "skill" ≠ "SKILL.md"

Claude Code's skill picker lists `antigravity:delegate`, `antigravity:review`,
`fable-orchestrator:doctor`, etc. as *skills*. **On disk they are not skills.**
They are `commands/*.md` — plugin slash commands — and the plugin ships exactly
ONE `skills/<name>/SKILL.md`.

```
/Users/rmanaloto/.claude/plugins/cache/antigravity-for-claude-code/antigravity/0.20.0/
  skills/antigravity/SKILL.md          <- 384 lines, the ONLY skill
  commands/{cancel,cloud-run-debug,delegate,media,research,result,review,setup,status}.md
  agents/…                             <- subagent definitions
```

So the shape people call "umbrella skill + focused skills" is, in the two
plugins the lead named, actually **one fat skill + many thin commands + some
subagents**. That is a different mechanism with different invocation rules.

### 1b. Family table

| Family | Skills (SKILL.md) | Commands | Agents | Umbrella? | Lines |
|---|---|---|---|---|---|
| `antigravity` v0.20.0 | `antigravity` (1) | cancel 10, cloud-run-debug 63, delegate 44, media 51, research 25, result 13, review 22, setup 15, status 14 | `antigravity-delegate` | `antigravity` SKILL.md | **384** skill; commands 10–63 |
| `fable-orchestrator` v1.14.0 | `orchestration` (1) | doctor 19, setup 131 | codex-implementer, codex-reviewer, fable-advisor, grok-implementer, grok-researcher, grok-reviewer | `orchestration` SKILL.md | **140** skill |
| `astral` v0.1.0 | `ruff` 134, `ty` 135, `uv` 182 | — | — | **none** — three peers, no umbrella | 134/135/182 |
| `mattpocock-skills` v1.2.0 | 41 SKILL.md | — | — | **no single umbrella**; several *thin wrapper* skills (below) | 7–140 |
| this repo (`knowledge-base`) | `graphify`, `kb-curator`, `orchestrator-routing`, `tool-currency` | — | — | see §5 | see §5 |

Paths: `/Users/rmanaloto/.claude/plugins/cache/{antigravity-for-claude-code/antigravity/0.20.0, fable-orchestrator/fable-orchestrator/1.14.0, astral-sh/astral/0.1.0, mattpocock/mattpocock-skills/1.2.0}`.

`astral` is the clean counter-example: a three-skill family (`ruff`/`ty`/`uv`)
that ships **no umbrella at all** — see §4 for how it disambiguates.

## 2. How the umbrella actually delegates

**Verdict up front: neither umbrella delegates to a sibling skill. Neither one
even names a sibling skill.** Both delegate — but downward, to *bash wrappers*
and *subagents*, never sideways to another SKILL.md. The sideways reference,
where it exists, runs child → umbrella, in prose.

### 2a. `antigravity` (384 lines) — delegates to Bash + one subagent

Zero references to any slash command or SKILL.md sibling. A grep for
`^/`, `/antigravity`, `Skill tool`, `skills/`, `SKILL.md` over
`skills/antigravity/SKILL.md` returns only four hits, all of them unrelated
filesystem paths (`~/.gemini/antigravity-cli/…`, lines 129, 134, 296, 378).

What it *does* invoke, all Bash:

> `skills/antigravity/SKILL.md:68-70`
> ```bash
> agy-delegate [options] "the task prompt"
> ```

> `skills/antigravity/SKILL.md:242` — `agy-media ./meeting.wav "decisions and owners"`
> `skills/antigravity/SKILL.md:215` — `ROOT=agy-delegate`
> `skills/antigravity/SKILL.md:370` — `agy-cost-compare --tier flash "the task prompt"`

The single sideways handoff is to a **subagent**, not a skill:

> `skills/antigravity/SKILL.md:87-89`
> "**Two ways to delegate.** Call the wrapper directly (above), or — when you
> want file generation to happen entirely on Gemini with **zero Claude tokens
> spent writing** — hand the unit to the **`antigravity-delegate` subagent**
> (its only file-acting tool is the wrapper; it returns a digest for you to
> verify). Either way, *you* still own verification."

**The reference direction is inverted.** It is the thin *command* that points
at the fat skill:

> `commands/delegate.md:6-7`
> "Delegate the following task to Antigravity (`agy` / Gemini) via the plugin
> wrapper, **following the `antigravity` skill's Cost discipline and
> Verification gates**."

And commands cross-reference *each other* in prose, for the human/model to run:

> `commands/delegate.md:42`
> "then check `/antigravity:status` and collect with `/antigravity:result <id>`."

No frontmatter declares any of this. `commands/delegate.md:1-4` carries only
`description` and `argument-hint`; `skills/antigravity/SKILL.md:1-5` carries
only `name`, `description`, `version`. **There is no dependency key, no
`allowed-tools`, nothing machine-readable linking them.** The relationship is
100% prose, and it is followed only because the model reads it.

Content duplication: **partial and deliberate.** `commands/delegate.md:12-23`
re-states the `--yolo` / exit-15 rule that `SKILL.md:152-160` already covers, in
compressed form — the command is executable-at-a-glance while the skill holds
the reasoning. That is duplication of *rules*, not of the doctrine.

### 2b. `fable-orchestrator` (140 lines) — delegates to subagents via the Agent tool

Even starker: a grep of `skills/orchestration/SKILL.md` for
`doctor|/fable-orchestrator|setup|Skill tool|SKILL` returns **`(none)`**. The
umbrella skill does not know its own plugin's two commands exist.

Its delegation targets are all **agents**, and the table has a literal
`Invoke` column:

> `skills/orchestration/SKILL.md:38-44`
> ```
> | Lane | Producer | Invoke | Route here when |
> | Implementation | Grok 4.5 | `grok-implementer` agent | All implementation in **grok** mode … |
> | Implementation | GPT-5.6 Sol (high reasoning) | `codex-implementer` agent | All implementation in **codex** mode. … |
> | Research | Grok 4.5 | `grok-researcher` agent | … |
> | Review | Grok 4.5 / GPT-5.6 Sol | `grok-reviewer` / `codex-reviewer` agents | … |
> | Judgment | Fable 5 | `fable-advisor` agent | … |
> ```

Those six names resolve to real files in `agents/` (`codex-implementer.md`,
`codex-reviewer.md`, `fable-advisor.md`, `grok-implementer.md`,
`grok-researcher.md`, `grok-reviewer.md`) and are invoked through the **Agent
tool**, which the skill names explicitly:

> `skills/orchestration/SKILL.md:52`
> "If both CLI lanes are unavailable, the final fallback is ALWAYS a Claude Opus
> subagent (Agent tool, `model: "opus"`)."

> `skills/orchestration/SKILL.md:101`
> "Where the harness's Workflow tool is available, propose orchestrating the
> fan-out through it instead … It requires the user's explicit opt-in — ask,
> don't assume."

Frontmatter: `skills/orchestration/SKILL.md:1-4` is `name` + `description`
only. No `allowed-tools`, no dependency declaration. The agents are found by
*name resolution at Agent-tool call time*, not by anything the skill declares.

### 2c. The one family that DOES have skill→skill delegation: mattpocock

`mattpocock-skills` ships the wrapper pattern the lead is asking about, and it
is startlingly small. Two complete files:

> `skills/productivity/grill-me/SKILL.md` (7 lines, entire file)
> ```
> ---
> name: grill-me
> description: A relentless interview to sharpen a plan or design.
> disable-model-invocation: true
> ---
>
> Run a `/grilling` session.
> ```

> `skills/engineering/grill-with-docs/SKILL.md` (7 lines, entire file)
> ```
> ---
> name: grill-with-docs
> description: A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go.
> disable-model-invocation: true
> ---
>
> Run a `/grilling` session, using the `/domain-modeling` skill.
> ```

That is the whole wrapper: a **slash-command reference in prose**. Same shape in
the orchestrating skill:

> `skills/engineering/implement/SKILL.md:7-15`
> ```
> Implement the work described by the user in the spec or tickets.
>
> Use /tdd where possible, at pre-agreed seams.
> …
> Once done, use /code-review to review the work.
> ```

So `implement` (15 lines) orchestrates `tdd` (36 lines) and `code-review` (89
lines) purely by naming their slash commands. And `tdd` points back:

> `skills/engineering/tdd/SKILL.md:36`
> "**Refactoring is not part of the loop.** It belongs to the review stage (see
> the `code-review` skill), not the red → green implementation cycle."

**Nothing in any of these is a tool call.** There is no `Skill(...)` invocation,
no Bash, no frontmatter dependency. Every single cross-skill link on this
machine — in all three families — is **prose naming a target and trusting the
model to follow it.**

### 2d. The ONE real orchestrator on this machine: omc `deep-dive`

`omc/oh-my-claudecode` is the single family that invokes another skill through
an **actual tool call**, and it says so in imperative caps:

> `omc/oh-my-claudecode/4.15.7/skills/deep-dive/SKILL.md:326`
> "Action: Invoke `Skill("oh-my-claudecode:plan")` with `--consensus --direct`
> flags and the spec file path (`spec_path` from state) as context. … When
> consensus completes and produces a plan in `.omc/plans/`, invoke
> `Skill("oh-my-claudecode:autopilot")` with the consensus plan as Phase 0+1
> output"

> `omc/oh-my-claudecode/4.15.7/skills/deep-dive/SKILL.md:345`
> "**IMPORTANT:** On execution selection, **MUST** invoke the chosen skill via
> `Skill()` with explicit `spec_path`. Do NOT implement directly. The deep-dive
> skill is a requirements pipeline, not an execution agent."

This is the proof that a wrapper CAN be real: `Skill()` is a callable tool and a
skill body can name it. Note the caveat — **omc is not enabled in this repo**
(`.claude/rules/notepad-enforcement.md` says so explicitly), so this is
precedent, not a live dependency.

And note what `deep-dive` had to do: it *also* declares a machine-looking
pipeline in frontmatter…

> `omc/oh-my-claudecode/4.15.7/skills/deep-dive/SKILL.md:10-13`
> ```yaml
> pipeline: [deep-dive, plan, autopilot]
> next-skill: plan
> next-skill-args: --consensus --direct
> handoff: .omc/specs/deep-dive-{slug}.md
> ```

…and then **restates the whole handoff as prose instructions at :326 and :345
anyway**. That is the tell: the frontmatter keys are decorative. Claude Code
does not read `pipeline`/`next-skill`/`handoff`; the body has to do the work.

## 3. Frontmatter survey

Frequency across all 1,799 `SKILL.md` files in `/Users/rmanaloto/.claude/plugins/cache`
(counts are inflated by multiple cached versions of the same plugin; treat as
rank order, not census):

| key | count | Claude Code honors it? |
|---|---|---|
| `description` | 1798 | **yes** — the invocation surface |
| `name` | 1758 | **yes** |
| `license` | 205 | no (metadata) |
| `trigger` | 200 | no (invented) |
| `aliases` | 198 | no (invented) |
| `argument-hint` | 176 | yes (commands) |
| `allowed-tools` | 116 | **yes** |
| `level` | 96 | no |
| `version` | 94 | no |
| `user-invocable` | 93 | **no — invented; the real key is `disable-model-invocation`** |
| `validation_gates` / `execution_mode` / `metadata` | 90/90/89 | no |
| `pre_execution_contract` | 70 | no |
| `paths` | 65 | (rules, not skills) |
| `disable-model-invocation` | 51 | **yes** |
| `agent` | 45 | no |
| `invocation` | 30 | no |
| `task_dependencies` | 25 | no |
| `pipeline` / `handoff` | 9 / 9 | **no — omc only** |
| `handoff-policy` | 6 | no — omc only |
| `next-skill` / `next-skill-args` | 3 / 3 | **no — omc `deep-dive` only** |
| `dependencies` | 2 | **no — and both are claudelint TEST FIXTURES**, not real skills (`pdugan20-plugins/claudelint/0.{6,7}.0/tests/fixtures/skills/valid/SKILL.md:8`) |
| `model` | 2 | yes |
| `disallowed-tools` | 2 | yes |

**Composition-supporting frontmatter does not exist.** The only keys that look
like it (`next-skill`, `pipeline`, `handoff`, `dependencies`) are invented by
exactly one plugin (omc) plus a linter's test fixture. The supported keys that
actually bear on multi-skill design are two, and neither declares a
relationship:

- `description` — the *only* routing mechanism between sibling skills.
- `disable-model-invocation: true` — removes a skill from the model's reach
  entirely, which is how families stop siblings competing (see §4).

Caution for this repo: `tool-currency/SKILL.md:15` uses `user-invocable: true`.
That key appears 93× in the cache but **is not a Claude Code key** — the real
one is `disable-model-invocation`. It is almost certainly a no-op.

## 4. Description-overlap evidence

Three distinct disambiguation techniques are in the wild. None of them is
"write a routing sentence in an umbrella".

### 4a. astral — disjoint vocabulary, no umbrella, no cross-reference

> `astral-sh/astral/0.1.0/skills/ruff/SKILL.md:2-4`
> "Guide for using **ruff**, the extremely fast Python **linter and formatter**.
> Use this when **linting, formatting, or fixing** Python code."

> `astral-sh/astral/0.1.0/skills/ty/SKILL.md:2-5`
> "Guide for using **ty**, the extremely fast Python **type checker and language
> server**. Use this when **type checking** Python code…"

> `astral-sh/astral/0.1.0/skills/uv/SKILL.md:2-4`
> "Guide for using **uv**, the Python **package and project manager**. Use this
> when working with Python projects, scripts, packages, or tools."

Three peers, zero umbrella, zero "use X not Y". Each description leads with a
**distinct binary name** and a **non-overlapping verb set** (lint/format vs
type-check vs install/manage). The overlap problem is solved by *never creating
it*. Note the cost: these are three tools, not three phases of one workflow —
the technique only works when the vocabulary is genuinely disjoint.

### 4b. mattpocock — remove the sibling from the model's reach entirely

Where the vocabulary *does* overlap, the family does not disambiguate the
descriptions. It **deletes one from the competition**:

> `skills/productivity/grilling/SKILL.md:2-3` (model-invocable, no flag)
> "Grill the user relentlessly about a plan, decision, or idea. Use when the
> user wants to stress-test their thinking, or uses any 'grill' trigger phrases."

> `skills/productivity/grill-me/SKILL.md:2-4`
> "A relentless interview to sharpen a plan or design.
> `disable-model-invocation: true`"

> `skills/engineering/grill-with-docs/SKILL.md:2-4`
> "A relentless interview to sharpen a plan or design, which also creates docs
> (ADR's and glossary) as we go.
> `disable-model-invocation: true`"

Three descriptions that would collide catastrophically — and only ONE of them
is in the model's index. The other two are user-typed slash commands only. That
is the technique, and **23 of the family's 41 skills carry the flag.**

The family documents this as deliberate design:

> `skills/productivity/writing-great-skills/SKILL.md:15-18`
> "A **model-invoked** skill keeps a **description**, so the agent can fire it
> autonomously _and_ other skills can reach it… It contributes to **context
> load** — the description sits in the window every turn.
> A **user-invoked** skill strips the description from the agent's reach: only
> you, typing its name, can invoke it — **and no other skill can**. Zero context
> load…
> Pick model-invocation only when the agent must reach the skill on its own, or
> another skill must."

And it names the wrapper pattern explicitly, including its invocation mode:

> `skills/productivity/writing-great-skills/SKILL.md:20`
> "When user-invoked skills multiply past what you can remember, that piled-up
> cognitive load is cured by a **router skill**: one user-invoked skill that
> names the others and when to reach for each."

Its split criteria are directly on point for the `goal-*` decision:

> `skills/productivity/writing-great-skills/SKILL.md:48-51`
> "**Granularity** is how finely you divide skills, and each cut spends one of
> the two loads, so split only when the cut earns it. Two cuts:
> - **By invocation** — split off a **model-invoked** skill when you have a
>   distinct **leading word** that should trigger it on its own, or another
>   skill must reach it. You pay **context load** for the new always-loaded
>   **description**, so that independent reach has to be worth it.
> - **By sequence** — split a run of **steps** when the steps still ahead …
>   tempt the agent to rush the one in front of it (**premature completion**)."

### 4c. omc — an explicit negative-routing block in the body

The heavyweight approach: a dedicated `<Do_Not_Use_When>` section naming the
sibling to prefer.

> `omc/oh-my-claudecode/4.15.7/skills/deep-dive/SKILL.md:30-31`
> ```
> <Do_Not_Use_When>
> - User already knows the root cause and just needs requirements gathering — use `/deep-interview` directly
> ```

This costs body lines, not description lines — and it appears in the family
whose skills are 290–802 lines. It is affordable there and would not be here.

### 4d. What this predicts for three `goal-*` skills

Three model-invocable descriptions all containing "goal", "completion
condition", and "audit" **would** compete: astral's technique is unavailable
(the vocabulary is inherently shared), and omc's is expensive. The shipped
answer for exactly this case is 4b — **at most one model-invocable description
in the cluster; any wrapper is `disable-model-invocation: true`.**

## 5. This repo's own four skills

| Skill | Lines | Frontmatter keys | Model-invocable | References another skill? |
|---|---|---|---|---|
| `graphify` | **714** | `name`, `description` | yes | no — points at 8 `references/*.md` siblings |
| `kb-curator` | 189 | `name`, `description` (block `>-`) | yes | **no skill** — points at a *Workflow* and mise tasks |
| `tool-currency` | 128 | `name`, `description`, `user-invocable: true` | (intended no; key is a no-op) | no |
| `orchestrator-routing` | 125 | `name`, `description` | yes | **no skill** — points at plugin *agents* and a *command* |

Paths: `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/skills/<name>/SKILL.md`.

**No skill in this repo references another skill by name.** Verified by grep for
`kb-curator|tool-currency|orchestrator-routing|.claude/skills|SKILL.md|Skill(`
across all four: the only hits are each file's own `name:` line, its own H1, and
`graphify/SKILL.md:219` pointing at its own `references/extraction-spec.md`.

### How `kb-curator` relates to `graphify`

Not as a child skill and not by reference. `kb-curator` is a **workflow layer
over a document**, and it says so:

> `kb-curator/SKILL.md:22-23`
> "**Read `docs/graphify-reference.md` first** for the graphify mental model;
> this skill is the workflow on top of it."

Its delegation targets are all **mise tasks and one saved Workflow** — genuinely
machine-executable, unlike every prose skill-link in §2:

> `kb-curator/SKILL.md:45`
> "| host-agent extract N sources | the **`kb-extract` saved workflow**
> (`.claude/workflows/kb-extract.js`) | ~~an inline one-off Workflow~~ |"

> `kb-curator/SKILL.md:33` — "**1. NEVER run graphify by hand — every graphify
> operation is a mise task.**"

So this repo's existing answer to "how do two related skills compose" is:
**they don't — they share a doc and a task surface.** `graphify` (the vendored
tool skill) and `kb-curator` (the workflow) coexist with no link at all.

### `orchestrator-routing` and `tool-currency`

`orchestrator-routing` points *outward* at plugin machinery, never at a sibling
skill — and the one cross-plugin pointer is a **slash command in prose**, the
same weak form as §2:

> `orchestrator-routing/SKILL.md:21-24`
> "- **codex lane** — `fable-orchestrator`'s `codex-implementer` (GPT-5.6 Sol, high reasoning).
> - **antigravity lane** — the `antigravity` plugin's `/antigravity:delegate` …
> - **Claude fallback** — a Claude Opus subagent (Agent tool, `model: "opus"`)…"

`tool-currency` points at **rules and tasks**, never a skill:

> `tool-currency/SKILL.md:81` — "`.claude/rules/do-not.md` #9; the same rule applies here"
> `tool-currency/SKILL.md:94` — "`mise run kb-ship` — the only sanctioned way to open a PR here."

## 6. Size reality check

Population: 54 SKILL.md files across the families surveyed (mattpocock ×41,
astral ×3, this repo ×4, antigravity, fable-orchestrator, anthropic
skill-creator, omc ×3).

```
N = 54    min = 7    median = 92    max = 802
over 500 lines: 3 of 54 (6%)
```

The guidance:

> `anthropic-agent-skills/claude-api/9d2f1ae18723/skills/skill-creator/SKILL.md:90`
> "**SKILL.md body** - In context whenever skill triggers (<500 lines ideal)"

> `…/skill-creator/SKILL.md:96`
> "Keep SKILL.md under 500 lines; if you're approaching this limit, add an
> additional layer of hierarchy along with clear pointers about where the model
> using the skill should go next to follow up."

**Shipped skills hold to it easily — and then some.** The median is **92 lines,
one-fifth of the ceiling.** The 500-line rule is not the binding constraint
anyone is straining against; it is a distant guardrail. The three violators:

| skill | lines | note |
|---|---|---|
| `omc/deep-interview` | 802 | omc, not enabled here |
| **`kb/graphify`** | **714** | **this repo — the largest skill surveyed after one omc file** |
| `omc/deep-dive` | 536 | omc |

`graphify` at 714 already applies the prescribed cure (8 `references/*.md`
files, 874 further lines) and is still 214 over. This repo's other three skills
(125/128/189) sit comfortably in the mainstream.

Selected reference points, smallest first: `grill-me` 7 · `grill-with-docs` 7 ·
`grilling` 12 · `research` 12 · `implement` 15 · `tdd` 36 · `code-review` 89 ·
`orchestrator-routing` 125 · `astral/ruff` 134 · `fable/orchestration` 140 ·
`kb-curator` 189 · `antigravity` 384 · `skill-creator` 485.

**A working wrapper skill costs 7 lines.** That is the measured floor, twice
(`grill-me`, `grill-with-docs`).

## GitHub repos touched

- [mattpocock/skills](https://github.com/mattpocock/skills) — the 41-skill family; source of the wrapper pattern (`grill-me`, `grill-with-docs`), the `disable-model-invocation` disambiguation technique, and the `writing-great-skills` authoring doctrine (router skills, when-to-split, invocation trade-off). Declared at `mattpocock/mattpocock-skills/1.2.0/.claude-plugin/plugin.json:9`.
- [astral-sh/astral](https://github.com/astral-sh) — `ruff`/`ty`/`uv`, the three-peer no-umbrella family and the disjoint-vocabulary technique.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — vendored as this repo's `graphify` skill (714 lines + 8 references), the size outlier.

Plugins surveyed with no public repo URL discoverable from the cache without a
network call: `antigravity-for-claude-code` (antigravity), `fable-orchestrator`,
`omc/oh-my-claudecode`, `anthropic-agent-skills` (skill-creator),
`pdugan20-plugins/claudelint`.

