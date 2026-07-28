# res-skilldocs — Anthropic's documented guidance on Agent Skill granularity & composition

**Question served:** ship `/goal` completion-condition tooling as ONE skill, TWO
(`goal-author` + `goal-audit`), or THREE (those two + an orchestrating wrapper)?

**Status:** COMPLETE.

## Pages fetched (all verbatim copies under `.agent/kb/raw/`)

Enumerated from `https://code.claude.com/docs/llms.txt` (HTTP 200, 178 lines).

| URL | HTTP | local file |
|---|---|---|
| `https://code.claude.com/docs/llms.txt` | 200 | `llms.txt.md` |
| `https://code.claude.com/docs/en/skills.md` | 200 | `cc_skills.md` |
| `https://code.claude.com/docs/en/plugins.md` | 200 | `cc_plugins.md` |
| `https://code.claude.com/docs/en/plugins-reference.md` | 200 | `cc_plugins-reference.md` |
| `https://code.claude.com/docs/en/features-overview.md` | 200 | `cc_features-overview.md` |
| `https://code.claude.com/docs/en/context-window.md` | 200 | `cc_context-window.md` |
| `https://code.claude.com/docs/en/commands.md` | 200 | `cc_commands.md` |
| `https://code.claude.com/docs/en/goal.md` | 200 | `cc_goal.md` |
| `https://code.claude.com/docs/en/glossary.md` | 200 | `cc_glossary.md` |
| `https://code.claude.com/docs/en/claude-directory.md` | 200 | `cc_claude-directory.md` |
| `https://code.claude.com/docs/en/large-codebases.md` | 200 | `cc_large-codebases.md` |
| `https://code.claude.com/docs/en/best-practices.md` | 200 | `cc_best-practices.md` |
| `https://code.claude.com/docs/en/discover-plugins.md` | 200 | `cc_discover-plugins.md` |
| `https://code.claude.com/docs/en/plugin-marketplaces.md` | 200 | `cc_plugin-marketplaces.md` |
| `https://code.claude.com/docs/en/sub-agents.md` | 200 | `cc_sub-agents.md` |
| `https://code.claude.com/docs/en/debug-your-config.md` | 200 | `cc_debug-your-config.md` |
| `https://code.claude.com/docs/en/monitoring-usage.md` | 200 | `cc_monitoring-usage.md` |
| `https://code.claude.com/docs/en/slash-commands.md` | 200 | `cc_slash-commands.md` (**alias of skills.md** — byte-for-byte same skill content) |
| `https://code.claude.com/docs/en/settings.md` | 200 | `cc_settings.md` |
| `https://code.claude.com/docs/en/agent-sdk/skills.md` | 200 | `cc_agent-sdk_skills.md` |
| `https://code.claude.com/docs/en/agent-sdk/plugins.md` | 200 | `cc_agent-sdk_plugins.md` |
| `https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices.md` | 200 | `plat_skills_best-practices.md` |
| `https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview.md` | 200 | `plat_skills_overview.md` |
| `https://platform.claude.com/docs/llms.txt` | 200 | `plat_llms.txt.md` |

**Reported 404s (probed, not guessed-away).** Control arm: `/docs/en/skills.md` → 200
on the same command shape, so the probe discriminates.

| URL | HTTP |
|---|---|
| `https://code.claude.com/docs/en/agent-skills.md` | **404** |
| `https://code.claude.com/docs/en/skill-authoring.md` | **404** |
| `https://code.claude.com/docs/en/skill-authoring-best-practices.md` | **404** |

`code.claude.com/docs/llms.txt` lists **no** page whose title is about authoring
skills beyond `/docs/en/skills.md`. The canonical authoring-guidance page is on a
**different host** and is reachable only via a link at the bottom of
`code.claude.com/docs/en/skills.md`:

> **[Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)**: writing guidance that applies across Claude products
> — `code.claude.com/docs/en/skills.md`, "Related resources"

No `anthropic.com/engineering` post is linked from `llms.txt` or from any fetched
page (grep for `anthropic.com/` across all fetched pages → 0 hits). The blog links
that *are* present point at `claude.com/blog/...` and `agentskills.io`, not
`anthropic.com/engineering`.

---

## 1. Skill granularity

### What IS documented

**A size budget, stated twice, on both hosts:**

> Keep `SKILL.md` under 500 lines. Move detailed reference material to separate files.
> — `code.claude.com/docs/en/skills.md`, "Add supporting files"

> * Keep SKILL.md body under 500 lines for optimal performance
> * Split content into separate files when approaching this limit
> — `platform.claude.com/.../best-practices.md`, "Progressive disclosure patterns"

> Keep SKILL.md body under 500 lines for optimal performance. If your content exceeds this, split it into separate files using the progressive disclosure patterns described earlier.
> — `platform.claude.com/.../best-practices.md`, "Token budgets"

**Note the direction of the split.** Every documented remedy for an oversized
skill is "split into **separate files**", never "split into separate skills".

**When to create a skill at all:**

> Create a skill when you keep pasting the same instructions, checklist, or multi-step procedure into chat, or when a section of CLAUDE.md has grown into a procedure rather than a fact.
> — `code.claude.com/docs/en/skills.md`, intro

**The one-description rule (bears on one-capability-per-skill):**

> Each Skill has exactly one description field. The description is critical for skill selection: Claude uses it to choose the right Skill from potentially 100+ available Skills. Your description must provide enough detail for Claude to know when to select this Skill, while the rest of SKILL.md provides the implementation details.
> — `platform.claude.com/.../best-practices.md`, "Writing effective descriptions"

**Multiple procedures inside ONE skill is a documented, named pattern:**

> ### Conditional workflow pattern
>
> Guide Claude through decision points:
>
> ```markdown
> ## Document modification workflow
>
> 1. Determine the modification type:
>
>    **Creating new content?** → Follow "Creation workflow" below
>    **Editing existing content?** → Follow "Editing workflow" below
> ```
> — `platform.claude.com/.../best-practices.md`, "Conditional workflow pattern"

with the escape hatch being **files, not skills**:

> If workflows become large or complicated with many steps, consider pushing them into separate files and tell Claude to read the appropriate file based on the task at hand.
> — `platform.claude.com/.../best-practices.md`, Tip under "Conditional workflow pattern"

**Consolidation is named as an outcome to aim for — the only "too many skills" text found:**

> To find which skills go unused, enable the OpenTelemetry [logs exporter](/docs/en/monitoring-usage) and set `OTEL_LOG_TOOL_DETAILS=1` so skill names are recorded verbatim instead of redacted. The [`skill_activated` event](/docs/en/monitoring-usage#skill-activated-event) records every invocation in its `skill.name` attribute, and `invocation_trigger` records whether a command, Claude, or a nested skill invoked it, which tells you what to consolidate or retire.
> — `code.claude.com/docs/en/large-codebases.md`

### NOT COVERED

- No numeric or qualitative rule for "one skill per capability."
- No page says "prefer N small skills" or "prefer one large skill."
- No stated threshold at which a skill is "doing too much" other than the
  500-line SKILL.md body budget — which is a *file-size* budget resolved by
  splitting into **files**, not by splitting into skills.

---

## 2. Skill composition — can one skill invoke another?

### Short answer

**No authoring mechanism for skill→skill invocation is documented anywhere.** There
is no frontmatter field that declares a skill dependency, no documented `Skill(...)`
call convention for a SKILL.md body, and no page that describes "invoke skill X" in
a skill body as a supported pattern. At the same time, the **runtime demonstrably
supports it** — one telemetry page names `"nested-skill"` as a first-class
invocation trigger. Both facts are below, verbatim.

### DOCUMENTED — the `Skill` tool exists and is a normal tool

> To extend Claude with reusable prompt-based workflows, write a [skill](/docs/en/skills), which runs through the existing `Skill` tool rather than adding a new tool entry.
> — `code.claude.com/docs/en/tools-reference.md`

> \| `Skill` \| Executes a [skill](/docs/en/skills#control-who-invokes-a-skill) within the main conversation \| Yes \|
> — `code.claude.com/docs/en/tools-reference.md`, tool table (third column = requires permission)

It is permission-addressable per skill:

> **Allow or deny specific skills** using [permission rules](/docs/en/permissions):
> ```
> # Allow only specific skills
> Skill(commit)
> Skill(review-pr *)
> ```
> — `code.claude.com/docs/en/skills.md`, "Restrict Claude's skill access"

### DOCUMENTED — the runtime records a `nested-skill` invocation trigger

This is the strongest evidence that skill→skill invocation is a real, supported
runtime path:

> * `invocation_trigger`: How the skill was triggered (`"user-slash"`, `"claude-proactive"`, or `"nested-skill"`)
> — `code.claude.com/docs/en/monitoring-usage.md`, "skill\_activated event"

> The [`skill_activated` event](/docs/en/monitoring-usage#skill-activated-event) records every invocation in its `skill.name` attribute, and `invocation_trigger` records whether a command, Claude, or a nested skill invoked it, which tells you what to consolidate or retire.
> — `code.claude.com/docs/en/large-codebases.md`

**INFERENCE:** a `"nested-skill"` trigger value can only be emitted if a skill's
execution caused another skill to load. So nesting *happens* and Anthropic *measures*
it. But it is documented only as an observability category, never as an authoring
instruction, and no page tells you how to cause it deliberately or whether it is
reliable.

### DOCUMENTED — subagents can invoke skills through the Skill tool

> This field controls which skills are preloaded, not which skills the subagent can access: without it, the subagent can still discover and invoke project, user, and plugin skills through the Skill tool during execution.
> — `code.claude.com/docs/en/sub-agents.md`, "Preload skills into subagents"

> **In subagents:** Skills work differently in subagents. Instead of on-demand loading, skills listed in the subagent's `skills` field are fully preloaded into its context at launch. Subagents can still discover and invoke unlisted project, user, and plugin skills through the Skill tool.
> — `code.claude.com/docs/en/features-overview.md`, "Skills" tab

Combined with a forked skill (`context: fork`, which runs the SKILL.md body *as* a
subagent prompt), this is the closest thing to a documented composition chain —
**INFERENCE**, assembled from two pages, not stated anywhere as a pattern.

### DOCUMENTED — the two composition mechanisms Anthropic DOES name

Both are skill↔**subagent**, never skill↔skill:

> **They can combine.** A subagent can preload specific skills (`skills:` field). A skill can run in isolated context using `context: fork`.
> — `code.claude.com/docs/en/features-overview.md`, "Skill vs Subagent"

> \| **Skill + Subagent** \| A skill spawns subagents for parallel work \| `/audit` skill kicks off security, performance, and style subagents that work in isolated context \|
> — `code.claude.com/docs/en/features-overview.md`, "Combine features"

**That `/audit` row is the documented shape of an orchestrating skill: one skill
that fans out to SUBAGENTS. It is not a skill that calls other skills.**

The formal skill↔subagent contract:

> \| Approach \| System prompt \| Task \| Also loads \|
> \| Skill with `context: fork` \| From agent type \| SKILL.md content \| CLAUDE.md, except when the agent is Explore or Plan \|
> \| Subagent with `skills` field \| Subagent's markdown body \| Claude's delegation message \| Preloaded skills + CLAUDE.md \|
> — `code.claude.com/docs/en/skills.md`, "Run skills in a subagent"

### DOCUMENTED — user-side stacking (composition by the human, not by a skill)

> You can also stack several skills at the start of one message. Typing `/write-tests /fix-issue 123` loads both skills and passes the trailing text `123` as `$ARGUMENTS` to each of them.
>
> Claude Code expands the first skill plus up to five more stacked after it. Expansion stops at the first token that isn't an inline user-invocable skill, so a skill that runs as a [forked subagent](#run-skills-in-a-subagent), such as [`/code-review`](/docs/en/code-review#review-a-diff-locally), or one whose arguments may themselves start with a slash command, such as `/loop`, also ends the run there.
> — `code.claude.com/docs/en/skills.md`, "Pass arguments to skills"

Note the trap for a 3-skill design: **a forked skill terminates stacking**, so
`/goal-author /goal-audit` would silently stop expanding if the first one forks.

### NOT COVERED (explicitly)

- **No frontmatter field declares a skill dependency.** The full frontmatter table
  in `code.claude.com/docs/en/skills.md` lists: `name`, `description`, `when_to_use`,
  `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`,
  `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context`, `agent`,
  `background`, `hooks`, `paths`, `shell`. **There is no `skills:`, `requires:`,
  `uses:`, or `depends-on:` field for a skill.** (`skills:` exists only on a
  *subagent* definition.)
- **No page states whether "invoke skill X" written in a SKILL.md body is honored.**
  It is prose the model may or may not act on — the docs neither bless nor forbid it.
- **`wrapper skill`, `umbrella skill`, `meta-skill` → 0 hits** across
  `skills.md`, `best-practices.md`, `overview.md`, `features-overview.md`.
  (Control arm: `orchestrat` on the same files → 2 hits, so the grep discriminates.)

---

## 3. Progressive disclosure vs splitting

### The loading model, verbatim

> ### Level 1: Metadata (always loaded)
>
> Claude loads this metadata at startup and includes it in the system prompt. The `description` is what Claude matches your request against when determining whether to trigger the Skill, so it must say both what the Skill does and when to use it. **This lightweight approach means you can install many Skills without context penalty: until a Skill is triggered, only its name and description occupy context.**
> — `platform.claude.com/.../overview.md` (emphasis in the phrasing is the source's own claim)

> ### Level 2: Instructions (loaded when triggered)
> When you request something that matches a Skill's description, Claude reads SKILL.md from the filesystem using bash. Only then does this content enter the context window.
> — `platform.claude.com/.../overview.md`

> ### Level 3: Resources and code (loaded as needed)
> Claude accesses these files only when referenced.
> — `platform.claude.com/.../overview.md`

> \| Level \| When loaded \| Token cost \| Content \|
> \| **Level 1: Metadata** \| Always (at startup) \| ~100 tokens per Skill \| `name` and `description` from YAML frontmatter \|
> \| **Level 2: Instructions** \| When Skill is triggered \| Under 5k tokens \| SKILL.md body with instructions and guidance \|
> \| **Level 3+: Resources** \| As needed \| None until accessed \| Bundled files. Reference files load into context when read. Scripts run through bash, and only their output enters context \|
> — `platform.claude.com/.../overview.md`

> * **No practical limit on bundled content:** Files don't consume context until accessed, so Skills can include comprehensive API documentation, large datasets, or extensive examples. There's no context penalty for bundled content that isn't used.
> — `platform.claude.com/.../overview.md`, "The Skills architecture"

Claude Code's own restatement, with the per-skill cost quantified differently:

> In a regular session, skill descriptions are loaded into context so Claude knows what's available, but full skill content only loads when invoked.
> — `code.claude.com/docs/en/skills.md`, note under "Control who invokes a skill"

> 'Skill descriptions' … 'One-line descriptions of available skills so Claude knows what it can invoke. Full skill content loads only when Claude actually uses one. Skills with `disable-model-invocation: true` are not in this list.'
> — `code.claude.com/docs/en/context-window.md`

### CONFLICT worth reporting — "no context penalty" vs a hard budget

The platform overview says installing many Skills carries no context penalty. The
Claude Code page says the listing is budgeted and **descriptions get truncated when
you have many skills**:

> Claude Code loads a listing of skill names and descriptions into context so Claude knows what's available. The listing always contains every skill name, but **if you have many skills, Claude Code shortens descriptions to fit the listing's character budget, which can strip the keywords Claude needs to match your request.** The budget scales at 1% of the model's context window. When the listing overflows, Claude Code drops descriptions starting with the skills you invoke least, so the skills you use most keep their full text.
> — `code.claude.com/docs/en/skills.md`, "Skill descriptions are cut short"

> the combined `description` and `when_to_use` text is truncated at 1,536 characters in the skill listing to reduce context usage
> — `code.claude.com/docs/en/skills.md`, frontmatter table, `description` row

**These two pages disagree in emphasis.** Both are reported. `platform` describes
the architecture in the abstract ("~100 tokens per Skill", no penalty); `code.claude.com`
describes the shipped Claude Code implementation, where the listing is capped at 1%
of the context window and *overflow degrades triggering*. For a decision about adding
N skills to a real Claude Code repo, the `code.claude.com` statement is the operative one.

### Does that argue for ONE skill with `references/`?

The docs never phrase it as skills-vs-files, but every remedy they give for size is
a **file** split inside one skill:

> SKILL.md serves as an overview that points Claude to detailed materials as needed, like a table of contents in an onboarding guide.
> — `platform.claude.com/.../best-practices.md`, "Progressive disclosure patterns"

> #### Pattern 2: Domain-specific organization
> For Skills with multiple domains, organize content by domain to avoid loading irrelevant context. When a user asks about sales metrics, Claude only needs to read sales-related schemas, not finance or marketing data. This keeps token usage low and context focused.
> — `platform.claude.com/.../best-practices.md`

**"Multiple domains → one skill, reference files per domain" is the closest the docs
come to answering the split question, and it points at one skill.**

But nesting has a documented limit that constrains how deep a wrapper can go:

> **Keep references one level deep from SKILL.md**. All reference files should link directly from SKILL.md to ensure Claude reads complete files when needed.
>
> Claude may partially read files when they're referenced from other referenced files. When encountering nested references, Claude might use commands like `head -100` to preview content rather than reading entire files, resulting in incomplete information.
> — `platform.claude.com/.../best-practices.md`, "Avoid deeply nested references"

**INFERENCE:** this is about *files*, not skills. It is not evidence about a wrapper
skill. It is, however, the one place the docs say indirection degrades fidelity.

Compaction adds a cost that is per-invoked-skill and favors fewer, invoked skills:

> \| Invoked skill bodies \| Re-injected, capped at 5,000 tokens per skill and 25,000 tokens total; oldest dropped first \|
> — `code.claude.com/docs/en/context-window.md`

> When the conversation is summarized to free context, Claude Code re-attaches the most recent invocation of each skill after the summary, keeping the first 5,000 tokens of each. Re-attached skills share a combined budget of 25,000 tokens.
> — `code.claude.com/docs/en/skills.md`, "Skill content lifecycle"

And a skill body is not free once loaded:

> Keep the body itself concise. Once a skill loads, its content [stays in context across turns](#skill-content-lifecycle), so every line is a recurring token cost.
> — `code.claude.com/docs/en/skills.md`, "Types of skill content"

---

## 4. Description / triggering

### How Claude chooses

> The `description` field enables Skill discovery and should include both what the Skill does and when to use it.
> — `platform.claude.com/.../best-practices.md`

> Each Skill has exactly one description field. The description is critical for skill selection: Claude uses it to choose the right Skill from potentially 100+ available Skills.
> — `platform.claude.com/.../best-practices.md`

> **How Claude chooses skills:** Claude matches your task against skill descriptions to decide which are relevant. **If descriptions are vague or overlap, Claude may load the wrong skill or miss one that would help.** To tell Claude to use a specific skill, invoke it with `/<name>`.
> — `code.claude.com/docs/en/features-overview.md`, "Skills" tab

**That is the only sentence in the entire corpus that directly addresses overlapping
skill descriptions, and it says overlap causes mis-selection.**

> Every feature you add consumes some of Claude's context. Too much can fill up your context window, but it can also add noise that makes Claude less effective; skills may not trigger correctly, or Claude may lose track of your conventions.
> — `code.claude.com/docs/en/features-overview.md`, "Understand context costs"

### Documented remedies (all point at sharpening ONE description, or manual invocation)

> ### Skill triggers too often
> 1. Make the description more specific
> 2. Add `disable-model-invocation: true` if you only want manual invocation
> — `code.claude.com/docs/en/skills.md`, Troubleshooting

> ### Skill not triggering
> 1. Check the description includes keywords users would naturally say
> — `code.claude.com/docs/en/skills.md`, Troubleshooting

> **Avoid:** … Inconsistent patterns within your skill collection
> — `platform.claude.com/.../best-practices.md`, "Naming conventions"

> * **Description tuning**: generates should-trigger and should-not-trigger prompts, measures the hit rate, and proposes description edits when the skill activates on the wrong requests
> — `code.claude.com/docs/en/skills.md`, "Run evals with skill-creator"

> Always write in third person. The description is injected into the system prompt, and inconsistent point-of-view can cause discovery problems.
> — `platform.claude.com/.../best-practices.md`

### NOT COVERED

No documented disambiguation algorithm, tie-break rule, or priority ordering between
two *differently named* skills whose descriptions overlap. The only documented
precedence rules are for **same-name** collisions across scopes
(`managed > user > project`, plugin skills namespaced) — a different problem.

---

## 5. Plugins vs skills

The plugin decision is documented purely as **distribution**, never as granularity:

> \| **Standalone** (`.claude/` directory) \| `/hello` \| Personal workflows, project-specific customizations, quick experiments \|
> \| **Plugins** (self-contained directories with skills, agents, hooks, or a `.claude-plugin/plugin.json` manifest) \| `/plugin-name:hello` \| Sharing with teammates, distributing to community, versioned releases, reusable across projects \|
> — `code.claude.com/docs/en/plugins.md`, "When to use plugins vs standalone configuration"

> **Use standalone configuration when**:
> * You're customizing Claude Code for a single project
> * The configuration is personal and doesn't need to be shared
> * You're experimenting with skills or hooks before packaging them
> * You want short skill names like `/hello` or `/deploy`
>
> **Use plugins when**:
> * You want to share functionality with your team or community
> * You need the same skills/agents across multiple projects
> * You want version control and easy updates for your extensions
> * You're distributing through a marketplace
> * You're okay with namespaced skills like `/my-plugin:hello`
> — `code.claude.com/docs/en/plugins.md`

> Start with standalone configuration in `.claude/` for quick iteration, then convert to a plugin when you're ready to share.
> — `code.claude.com/docs/en/plugins.md`, Tip

> \| A second repository needs the same setup \| Package it as a [plugin](/docs/en/plugins) \|
> — `code.claude.com/docs/en/features-overview.md`, "Match features to your goal"

### NOT COVERED

**There is no count threshold** ("N related skills → make it a plugin"). Nothing in
any fetched page says a set of related capabilities *becomes* a plugin at some size.
Plugins are about sharing, versioning, and namespacing — full stop.

---

## 6. Explicit anti-patterns

Everything the docs actually warn against, verbatim:

1. **Vague or generic skill names**
   > **Avoid:** Vague names: `helper`, `utils`, `tools` · Overly generic: `documents`, `data`, `files` · Reserved words … · Inconsistent patterns within your skill collection
   > — `platform.claude.com/.../best-practices.md`

2. **Vague descriptions**
   > Avoid vague descriptions like these: `description: Helps with documents` / `description: Processes data` / `description: Does stuff with files`
   > — `platform.claude.com/.../best-practices.md`

3. **Offering too many options**
   > ### Avoid offering too many options
   > Don't present multiple approaches unless necessary:
   > **Bad example: Too many choices** (confusing): "You can use pypdf, or pdfplumber, or PyMuPDF, or pdf2image, or…"
   > **Good example: Provide a default** (with escape hatch)
   > — `platform.claude.com/.../best-practices.md`, "Anti-patterns to avoid"

4. **Deeply nested references** (files)
   > **Keep references one level deep from SKILL.md**… Claude might use commands like `head -100` to preview content rather than reading entire files, resulting in incomplete information.
   > — `platform.claude.com/.../best-practices.md`

5. **Verbosity / over-explaining**
   > The context window is a public good. Your Skill shares the context window with everything else Claude needs to know, including: … Other Skills' metadata …
   > **Default assumption:** Claude is already very smart. Only add context Claude doesn't already have.
   > — `platform.claude.com/.../best-practices.md`, "Concise is key"

6. **Overlapping descriptions** (see §4)
   > If descriptions are vague or overlap, Claude may load the wrong skill or miss one that would help.
   > — `code.claude.com/docs/en/features-overview.md`

7. **A guideline-only skill under `context: fork`**
   > `context: fork` only makes sense for skills with explicit instructions. If your skill contains guidelines like "use these API conventions" without a task, the subagent receives the guidelines but no actionable prompt, and returns without meaningful output.
   > — `code.claude.com/docs/en/skills.md`, Warning

8. **Accumulating unused skills** — the only "prune your collection" statement
   > … `invocation_trigger` records whether a command, Claude, or a nested skill invoked it, **which tells you what to consolidate or retire.**
   > — `code.claude.com/docs/en/large-codebases.md`

### NOT COVERED

- **No warning against "too many skills"** as such — only the listing-budget
  degradation in §3 and the consolidate/retire hint above.
- **No warning against wrapper skills**, because wrapper skills are not mentioned
  at all (grep: 0 hits, control-armed).
- **No warning against splitting one capability across skills.**

---

## Bottom line

**The docs do not decide 1-vs-2-vs-3 for you. There is no Anthropic guidance on
skill-count granularity.** What they do supply is a one-sided set of constraints,
and every one of them cuts against the 3-skill wrapper design:

- **Rule out THREE.** A wrapper skill's whole job is skill→skill invocation, and
  **no authoring mechanism for that is documented** — no dependency frontmatter, no
  documented call convention, no page saying a SKILL.md body's "invoke skill X" is
  honored. The only evidence it works at all is a telemetry enum value
  (`invocation_trigger: "nested-skill"`). The documented orchestration shape is
  skill→**subagents** (`/audit` fans out to subagents), not skill→skills. Building
  on an undocumented mechanism when a documented one exists is the choice the docs
  won't back.
- **TWO is defensible only if the two descriptions do not overlap** — "If descriptions
  are vague or overlap, Claude may load the wrong skill or miss one that would help."
  Two skills named `goal-author`/`goal-audit` over the same `/goal` subject matter is
  precisely the overlap case that sentence describes.
- **ONE is what the documented patterns support.** Two procedures under one skill is
  the named **"Conditional workflow pattern"** ("Creating new content? → … Editing
  existing content? → …"), with the documented escape hatch being *separate files*,
  not separate skills; **Pattern 2 (domain-specific organization)** puts multiple
  domains in one skill with one reference file each; and the only size rule is
  "SKILL.md body under 500 lines → split into files."

**INFERENCE (mine, labeled):** one skill — `goal-conditions` or similar — with a
conditional-workflow branch at the top (author vs audit) and one-level-deep
`references/authoring.md` / `references/auditing.md`. That is the shape every
documented pattern points at; the 2- and 3-skill options each require a mechanism or
a tolerance the docs never grant.

## GitHub repos touched

- [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) — linked from `code.claude.com/docs/en/skills.md` as the home of the `skill-creator` plugin (the documented eval/description-tuning loop); read as a link target only, not cloned.

