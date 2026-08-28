---
paths:
  - "hk.pkl"
  - "**/CLAUDE.md"
  - ".claude/rules/*.md"
  - ".claude/skills/**/SKILL.md"
---

# Markdown Size Budgets: By Load Class, and Only One Figure Is Anthropic's

Instruction-markdown budgets differ **by load class**, because the only thing
that justifies a size limit is **when the bytes are spent**. Enforced by
`kb-setup md-budget` (hk step `md_size_budget`) — the SHARED engine
(`python/src/kb_setup/md_budget.py`) that the sibling dotfiles repo also
consumes, on the `kb_setup.currency` precedent: one implementation, not two
that drift.

This rule is `paths:`-scoped, and legitimately so: its trigger genuinely *is* a
file — you only need it when editing `hk.pkl` or an instruction doc. That is the
test (below), applied to itself.

## The one documented figure

> "**Size**: target under 200 lines per CLAUDE.md file. Longer files consume
> more context and reduce adherence."
> — <https://code.claude.com/docs/en/memory> § Write effective instructions

It is a **soft guideline about a gradient, not a cliff**. The same page:

> "**CLAUDE.md files are loaded in full regardless of length**, though shorter
> files produce better adherence."

**Nothing truncates a CLAUDE.md at any size.** The 200-line/25KB *hard*
truncation applies to auto-memory `MEMORY.md` only — a file this repo does not
commit.

## Why this rule exists: a real number, enforced against the wrong vendor

The predecessor gate enforced **200 lines AND 12,000 bytes** on every
`CLAUDE.md`/`AGENTS.md`, captioned "max 12000 chars **per Claude Code memory
docs**".

**The number is real. The citation was wrong.** 12,000 is **Windsurf's** limit:

> Workspace `.devin/rules/*.md` … **Limited to 12,000 characters per file.**
> `AGENTS.md` — Any directory in your workspace — **Processed by the same Rules
> engine**.
> — <https://docs.windsurf.com/windsurf/cascade/memories>

agnix enforces it as **AGM-003** (Category: `agents-md`, Tool: `windsurf`,
Source type: `vendor_docs`). In Anthropic's corpus the figure has **0 hits**
(control-armed: 5 for MEMORY.md's cap, 12 for `"200 lines"`) — so it was
attributed to the wrong vendor, applied to the wrong files, and duplicated a
check agnix already owns.

The lesson is not "someone invented a number" — it is that **a true fact
travelled without its source** until nobody could tell whose rule it was.

### The correction that nearly wasn't made

The session that first wrote this rule concluded the figure was **fabricated**,
having grepped Anthropic's corpus with a proper control arm and found nothing.
The probe was sound; the *report* dropped its bound. "Not in Anthropic's docs"
became "not documented anywhere" — but the probe never searched Windsurf, so it
could not have found it. Only `agnix --strict` failing surfaced the truth.

**A control arm proves a probe works INSIDE its bound. It says nothing outside
it.** That is `probes-need-a-control-arm.md` rule 3, violated while holding the
rule — which is why it is recorded rather than quietly fixed.

## The budgets

| Class | Load semantics (documented) | Lines | Bytes |
|---|---|---|---|
| `eager_root` — root `CLAUDE.md` (+ any `@import` closure), `.claude/CLAUDE.md` | "loaded in full at launch" | **200** | 24,000 |
| `rule_unscoped` — `.claude/rules/*.md` with no `paths:` | "loaded at launch with the same priority as `.claude/CLAUDE.md`" | **200** | 24,000 |
| `nested` — subdirectory `CLAUDE.md` + closure | "included when Claude reads files in those subdirectories"; not re-injected after `/compact` | **400** | 32,000 |
| `rule_scoped` — `.claude/rules/*.md` with `paths:` | "only load into context when Claude works with matching files" | **400** | 32,000 |
| `skill` — `.claude/skills/**/SKILL.md` | on invocation/relevance only | **500** | 32,000 |

This repo is **Claude-only**; its `AGENTS.md` (tracked, 51 lines, codex's minimum)
is a SIBLING of `CLAUDE.md`, not an `@import` stub, so no budget counts it and
AGM-003's 12,000-char ceiling never binds here — but the shared engine still must
not re-adopt the figure, and a test pins that. (This line said "ships no
`AGENTS.md`" until the 2026-08-23 session review read it against `git ls-files`.)

Plus the skill-listing budget — **two** mechanisms, recorded here as one until
2026-07-30 (#76 docs review; `skills.md` § *Skill descriptions are cut short*):

1. **A per-entry cap.** The **combined** `description` **and** `when_to_use` text
   is capped at **1,536 chars** — not `description` alone — "regardless of
   budget", and is configurable via `skillListingMaxDescChars`. Put the key use
   case first; it is the tail that is lost.
2. **A whole-listing budget scaling at 1% of the model's context window.** On
   overflow Claude Code "drops descriptions starting with the skills you invoke
   least" — so **a short description can lose its keywords purely because OTHER
   skills exist**, with nothing about that skill having changed. Raise it with
   `skillListingBudgetFraction` / `SLASH_COMMAND_TOOL_CHAR_BUDGET`, or set
   low-priority entries to `name-only` in `skillOverrides` to free room.

The listing always keeps every skill **name**; what goes is the description,
which is exactly what model-invocation matches on. So the failure is silent and
presents as a badly-written description rather than a full budget.

**Measure it rather than reasoning about it:** `/doctor` estimates the listing's
context cost and names its biggest contributors, and the Skills row in
`/context` reports the size **after** the budget is applied — what the model
actually received. An overflow also writes a warning to the `--debug` log.

Calling the per-entry cap "the only real cliff" was wrong in the direction that
matters here: with seven project skills plus enabled-plugin skills stacked on
top — **ten** on 2026-08-03 (it was five when this paragraph was written, and
PR #139 doubled it), **19** declared / **17** effective as of 2026-08-28
(`.claude/CLAUDE.md` § Cross-vendor orchestration carries the re-derive
commands) — the *listing* budget is the one this repo can plausibly hit, and no
per-skill edit would ever explain the symptom. **Re-measure rather than
trusting this number**: `/doctor` estimates the listing's cost and names its
biggest contributors, and `/context`'s Skills row shows the size after the
budget is applied. A count in prose is stale the moment someone enables a
plugin.

**The byte ceilings are ours**, not Anthropic's — anti-gaming backstops (a line
cap alone admits 200 × 400-char lines), sized never to bind before the
documented line limit. Label them as self-imposed. Do not re-attribute them
upstream; that error is the whole reason this file exists.

## Measurement rules

- **Budget the `@import` closure, not the file.** "Splitting into @path imports
  helps organization but doesn't reduce context, since imported files load at
  launch." A per-file cap is evadable by splitting — which the docs explicitly
  call a non-reduction.
- **The import directive is replaced, not added.** Counting it makes a closure
  201 lines and fails a file legitimately at 200.
- **Only `CLAUDE.md` is an entry point.** "Claude Code reads CLAUDE.md, not
  AGENTS.md."
- **HTML comments are free in `CLAUDE.md`** ("stripped before the content is
  injected... without spending context tokens") — but that sentence says
  *CLAUDE.md files*. For rules and skills it is **undocumented**, so they pay
  full price. Never take a discount you cannot cite.
- **`.claude/skills/graphify/**` is exempt.** It is installer-generated
  (`graphify install --project`), >700 lines, and regenerated by
  `mise run kb-skill-refresh` rather than edited.

  **"Never hand-edited" was true until PR #190** and is the sentence that cost
  something: that PR hand-added a paragraph to `references/query.md` recording
  0.9.34's direction-respecting `path`, and the first `kb-skill-refresh` run
  destroyed it silently — the installer rewrites the whole tree, so the `git
  diff` read as a routine regeneration. Local additions now live in
  `kb_setup.currency.skill.ADDENDA`, are re-applied after every install, and
  **fail the run loudly** when their anchor is gone. Do not hand-edit this tree;
  add an addendum, or the next refresh eats it.

## Scoping: the trigger test (this is the load-bearing part)

Path-scoped rules "trigger when Claude **reads** files matching the pattern".
So scoping is safe only when the rule's trigger genuinely *is* reading a file.

- **File-triggered → safe to scope.** `ci-local-parity`. This rule.
- **Behaviour-triggered → MUST stay eager.** `zero-skip-policy` (fires when a
  warning is about to be dismissed), `clean-git-state` (fires when validation is
  about to run), `do-not`, `verify-before-advancing`, `clarify-before-acting`,
  `probes-need-a-control-arm`, `ai-cli-invocation`. No glob predicts a decision.
- **Creation-triggered → CANNOT be scoped.** `zero-bash-logic` governs files
  that do not exist yet; `omc-directory-conventions` governs *where to create*
  an artifact. You never read the file first, so the rule would be absent
  exactly when it is needed.
- **Behaviour-triggered but niche → a skill, not a rule.** "For task-specific
  instructions that don't need to be in context all the time, use skills
  instead, which only load when you invoke them or when Claude determines
  they're relevant." Skills load on *relevance*, which is the only mechanism
  that tracks a behavioural trigger.

**This was found the hard way:** `zero-skip-policy` and `clean-git-state` were
both `paths:`-scoped in dotfiles until 2026-07-15 — so the rules forbidding
skipped warnings and dirty-tree validation were silently absent from any
session that didn't touch the listed files. Un-scoping them *raises* eager
context, and that is correct: a judgment rule that is cheap and absent is worth
less than one that is costly and present.

The lever for eager context is therefore **trimming, not scoping** — cut what
Claude can derive from the codebase (directory layouts, dependency lists,
architecture overviews) and keep pitfalls, rationale, and conventions that
differ from tool defaults.

## Applies to

Every tracked `CLAUDE.md`, `.claude/rules/*.md`, and
`.claude/skills/**/SKILL.md`.

## See also

- `python/src/kb_setup/md_budget.py` — the enforcer, and its full provenance.
- `probes-need-a-control-arm.md` — why "0 hits" needed a control.
- `use-tool-builtins.md` — the parent principle: check the source before
  inventing; here, before *enforcing*.
