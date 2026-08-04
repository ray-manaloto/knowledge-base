---
type: "query"
date: "2026-08-04T00:14:52.162280+00:00"
question: "Grilling then to-spec then to-tickets over the /clear-prep rework produced spec #143 and tickets #144-#150. What did the planning itself teach, beyond the plan?"
contributor: "graphify"
outcome: "useful"
---

# Q: Grilling then to-spec then to-tickets over the /clear-prep rework produced spec #143 and tickets #144-#150. What did the planning itself teach, beyond the plan?

## Answer

Four lessons, all measured on 2026-08-03 while running grilling -> to-spec -> to-tickets
over the /clear-prep rework.

1. A SPEC STEP CAN BE UNBUILDABLE, AND GRILLING IS WHERE THAT SURFACES. /clear-prep
step 6 asked whether "every gate result matches the recorded rc". Nothing records
one: a gate prints its exit code to a terminal, that goes to a temp file, the file
dies with the session, and an agent retypes the number into the handoff as prose.
Across 28 handoffs, 26 carry such a claim and NONE could be checked against
anything. A check with one input can only ever agree with itself. The general
form: before specifying a verification step, name the artifact it reads. If that
artifact does not exist, the step is not hard, it is impossible -- and the fix
belongs at the point the evidence is created, not at the point it is checked.

2. THE MODULE STRUCTURE WILL SLICE TICKETS HORIZONTALLY IF YOU LET IT. A design
with four clean primitives invites one ticket per primitive -- "build citations",
"build resolve" -- and each delivers nothing runnable. Slicing by CAPABILITY
instead gave seven vertical tickets that each land modules, task, tests and
mutation arms together. The check that kept the modules honest was requiring each
primitive to have TWO OR MORE CALLERS; one caller means it is not a primitive, it
is a layer with extra steps, and it should be inlined.

3. A TOOL'S OWN LISTING IS NOT THE REPO'S DECLARATION. `mise tasks ls` reports 45
tasks on this machine while mise.toml declares 41; the four extras come from the
user's GLOBAL config. A handoff naming one would have passed here and failed on
every other machine -- a false green whose blast radius is "works on my machine",
the hardest kind to reproduce. Any check that asks "does this named thing exist"
must read the repo's own declaration, never a tool's merged view. ci-local-parity
already said this; it took a concrete check design for the cost to be visible.

4. A SKILL CAN BE RIGHT ABOUT WHAT AND WRONG ABOUT WHERE. setup-matt-pocock-skills
writes docs/agents/*.md and appends to the root CLAUDE.md. Re-probed control-armed:
an identical frontmatter-less file returns rc=1 at docs/agents/ against rc=0 at
docs/ (agnix treats **/agents/*.md as an agent definition), and the appended block
takes CLAUDE.md from 200 to 214 lines, failing md_size_budget. Both gates red. The
skill's CONTENT was still valuable -- it found a real gap, since the triage
vocabulary was undocumented and three of five canonical labels did not exist. So
the resolution was to satisfy its three sections at gate-safe paths rather than
either running it or refusing it. Generalisation: when an external skill collides
with a local invariant, separate what it asks for from where it puts it; usually
only the second is wrong, and refusing the whole thing loses the first.

Also recorded: re-probe a ban before obeying it. docs/issue-tracker.md's "do not
run this skill" was written 2026-07-30; both halves were re-verified before being
relied on, and the note was narrowed from the skill to the skill's output PATHS. A
ban filed under a reason nobody can re-check is one the next session either obeys
blindly or ignores entirely.

## Outcome

- Signal: useful