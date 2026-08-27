---
name: eli5-visual
description: Explain anything as a published visual artifact instead of terminal prose — architecture, a root cause, a comparison of options, a dependency chain, a decision the reader has to make. Use this whenever an answer would otherwise be a wall of terminal text with a table or a list of options in it, whenever the user asks how something works or why something broke, whenever you are about to ask a question whose trade-offs the reader cannot see, and whenever the user says eli5, explain, visual, diagram, artifact, or asks for something to be drawn rather than described. Ray asks for this constantly and it is the house default — reach for it BEFORE writing the explanation, not after.
---

# eli5-visual — the explanation is a page, not a paragraph

Ray's standing instruction, 2026-08-24, verbatim:

> i am having a hard time understanding what any of your explanations
> …
> i want it to always be presented as a visual artifact
> showing components and their dependencies and relationships
> with architecture/workflow/sequence diagrams using the appropriate tools to show them visually
> …
> all visual artifacts should be persistent and be updated to kept in sync w the
> code/documentation as changes are made

The `eli5-visual` output style states this norm. **The norm was not enough** — it was
active and complied with roughly one time in five, because a norm has no
completion criterion and prose is always the faster next token. This skill is the
norm with a **gate** in front of it and a **checklist** behind it.

## The gate — run it before you send, not after

Before sending any substantive reply, ask one question:

> **Could a reader point at the thing I am describing?**

If the answer involves components and how they relate, an order in time, two
things being compared, or a claim about what depends on what — **the answer is a
page.** Build it first, then write three lines of terminal text around the link.

Concretely, a picture is **required** when any of these is true:

- more than two components and a relationship between them
- a before/after, or two or more options being compared
- anything ordered in time — a request path, a build, a failure cascade
- a claim about **dependencies** ("X imports Y", "nothing else reaches Z")
- a root cause with more than one hop
- **a question whose options have trade-offs the reader cannot see**

A picture is **noise** when the answer is a single fact, a command and its
output, a status line, or a yes/no with no trade-off. Do not manufacture one for
those — a page whose picture adds nothing teaches the reader to skip the pictures
that matter.

## The failure this exists to stop

These are real, from the session that produced this skill. Each one is a terminal
table that should have been a page:

| what was sent | why it needed a page |
|---|---|
| 12 CLI verbs scored against 4 SDK verdicts | a comparison — the reader has to hold 12 rows in their head to see the pattern |
| three prototype "shapes" with speed, coverage and failure modes | comparing options; the reader is choosing between them |
| a four-question audit of a pipeline | components and relationships |
| five rounds of questions with options in prose | the reader was choosing between trade-offs that existed only in paragraphs |

The tell is always the same: **you reached for a markdown table.** A markdown
table in terminal output is a page that has not been built yet. When you catch
yourself typing one with more than three rows or more than two columns of
judgment, stop and build the page.

## Ship the picture before the question

A question that needs context ships its artifact **first**. Build the page,
publish it, put the link in the `AskUserQuestion` text, and let the options
reference what the reader can now see.

This is the rule most often skipped, because a question feels urgent and a page
feels like a detour. It is backwards: the reader answering without the picture is
answering about your summary, not about the thing.

## The loading sequence — every time, no exceptions

Via the Skill tool, **before authoring**:

1. `artifact-design` — palette, type pairing, layout plan. The page must not look
   like the last page; reusing the previous page's fonts and colours is the tell
   that this step was skipped.
2. `artifact-diagramming` — draw the **mechanism, not its name**. When comparing
   options, draw the *difference*. Label every arrow.
3. `artifact-capabilities` — read it and decide. **Declaring nothing is the
   normal outcome** for an explainer, and a page that declares capabilities
   cannot be shared publicly.

Then **say which other skills you considered and did not use, and why.** Ray asked
for that list explicitly so the gaps are visible rather than silent. The usual
near-misses and why they lose:

- `dataviz` — charts of *data*, not diagrams of *mechanism*
- `design` — multi-artboard visual design, a different deliverable
- `writing-for-agents` — governs skills and AGENTS.md, not reader prose
- `eli5:eli5` (the plugin) — three lines, no persistence, no honesty rules

## Diagram tooling

Artifacts render **mermaid natively**. Use it for flowcharts, dependency graphs,
sequence and state diagrams; it is the right tool and far less error-prone than
hand-authored SVG for those shapes.

**Mermaid has broken twice here, both times silently, and both fixes are
mechanical. Copy the two blocks below rather than reasoning about them.**

### 1. The element is `<pre>`. Never `<div>`

```html
<pre class="mermaid">
flowchart LR
  A --> B
</pre>
```

`<div class="mermaid">` renders **nothing at all** — `div` collapses the
whitespace mermaid's grammar depends on. Reported by Ray as *"visual is not
working"* on two figures, 2026-08-27.

This section already said `<pre>` in plain text and **three pages were authored
with `<div>` anyway**, plus two earlier pages that had been broken since
publication and nobody noticed. Armed at the time: 13 tracked artifacts used
`<pre>` correctly against 5 using `<div>` — the repo's own precedent was right
and the author broke it. That is why the rule is now a copyable block and not a
sentence: a norm you must retype is a norm you will retype wrong.

### 2. `%%{init}%%` is NOT enough. Force the plate in CSS

Getting the element right only makes the diagram *render*. Mermaid then draws
its own SVG that **does not inherit the container's theme**, and
`themeVariables` reaches node fills but **not** edge labels, cluster titles or
sequence actors — those keep mermaid's own dark ink and vanish on a dark ground.
Ray, on the very next revision: *"this is hard to see with black background and
black text."*

Ship this beside every `.mermaid` rule, verbatim:

```css
.mermaid svg { background: #ffffff !important; max-width: 100%; height: auto; }
.mermaid svg text,
.mermaid svg .nodeLabel, .mermaid svg .edgeLabel, .mermaid svg .cluster-label,
.mermaid svg .messageText, .mermaid svg .labelText, .mermaid svg .loopText,
.mermaid svg .noteText, .mermaid svg .sequenceNumber { fill: #1b1b1b !important; color: #1b1b1b !important; }
.mermaid svg .edgeLabel rect, .mermaid svg .label-container,
.mermaid svg rect.actor { fill: #f4f4f6 !important; stroke: #8d8d94 !important; }
.mermaid svg .cluster rect { fill: #fafafa !important; stroke: #b8b8be !important; }
.mermaid svg .edgePath path, .mermaid svg line,
.mermaid svg .messageLine0, .mermaid svg .messageLine1,
.mermaid svg .actor-line { stroke: #4a4a4a !important; }
.mermaid svg marker path, .mermaid svg .arrowheadPath { fill: #4a4a4a !important; stroke: #4a4a4a !important; }
```

Keep the `%%{init: {'theme':'base','themeVariables':{…}}}%%` header too — it
still sets node fills to your palette. The CSS is the backstop for everything it
misses, and it is deliberately `!important` and theme-independent: the plate
stays light in **both** themes, so there is no dark-mode arm to get wrong.

### 3. A publish result is not evidence the diagram rendered

**Nothing in the publish output tells you a mermaid block parsed.** Both defects
above shipped green and were caught only because a human opened the page. So
after publishing a page with a diagram on it, **say so and ask** — one line is
enough: *"reload and tell me if the diagrams render."* Do not report a diagram
page as done on the strength of a successful publish.

### Inline SVG

Hand-author it only where the shape is a genuine comparison figure mermaid
cannot express. Then `artifact-diagramming`'s rules apply in full: `viewBox`,
`currentColor`, `<figure>` + `<figcaption>`, `role="img"`. Inline SVG has none of
mermaid's theme problem — it inherits `currentColor` — which is a real reason to
prefer it for a small figure.

## Persistence — the part that is usually skipped

**Artifact source lives in the repo, not the scratchpad**: `docs/artifacts/<name>.html`,
tracked. The scratchpad dies with the session and `.agent/` dies with the clone;
a diagram nobody can regenerate goes stale silently.

- **Republish the same file path** to update in place — the URL stays stable, and
  a stable URL is what makes a page citable from a doc or a handoff.
- **When the code a page describes changes, the page changes in the same commit.**
  A published architecture diagram is documentation, and this repo treats stale
  documentation as a defect.
- **A page corrected after publication says so on the page.** Never silently
  overwrite a claim someone may already have acted on.
- **A republish can deadlock.** The tool compares against the version *it* last
  handed this session, not against what is live — so a page corrected in an
  earlier session reads as "unchanged" forever from a later one. `force: true` is
  the only exit, and it needs the user's explicit say-so.

## Honesty rules, which the pictures do not soften

A picture is an argument, and an argument with an unsourced number in it is worse
than prose, because a picture is believed faster.

- Every number on a page is **measured this session**, or labelled derived or
  inherited.
- Cite `file:line` for anything read from code — and prefer citing the **symbol**
  beside it, because a dependency pin move stales every bare line number.
- If a lane or a report supplied a fact, say so and mark it unverified until
  re-read.
- A negative claim on a page ("nothing else reaches this") needs its **control
  arm** stated, or it is an opinion in a confident typeface.

## Terminal prose alongside the artifact

Short. Lead with the result. The link, the headline finding, and what you need
from the reader.

Do not restate the artifact — if the message can stand alone, the page was not
necessary; if the page is necessary, the message must not duplicate it.

## Done means

- The page exists at `docs/artifacts/<name>.html`, tracked.
- It is published, and you have **read the live bytes back** to confirm what
  shipped — a publish result is a claim, the live page is the evidence.
- Every figure has a `<figcaption>` stating what it shows.
- Every number on it was measured this session or is labelled.
- The terminal message is the link, the headline, and the ask — nothing more.
- You have named the skills you considered and did not use.

## See also

- `.claude/rules/probes-need-a-control-arm.md` — why a negative on a page owes an arm.
- `.claude/rules/verify-before-advancing.md` — read the live artifact, not the publish result.
- `docs/artifacts/` — every page this repo has published; read one before authoring
  a new one, so the new page does not look like the last page.
