# The smell baseline

A fixed set of Fowler code smells (*Refactoring*, ch. 3) the Standards lane
carries **on top of** whatever this repo documents. It applies even when the
repo documents nothing about the surface in question.

Paste this file into the Standards sub-agent's prompt in full. It has no other
access to it — a sub-agent that is told "apply the smell baseline" without being
given the baseline will invent one, and an invented standard is unreviewable.

## The two rules that bind it

1. **The repo overrides.** A documented standard in this repo's rule files or
   `CLAUDE.md` always wins. Where the repo endorses something the baseline would
   flag, suppress the smell — do not report it as a finding and do not report it
   as a tension. This repo's rules were written against real incidents; the
   baseline is a generic heuristic. The specific beats the generic.

   The live example: `kb_setup.graphify_ops.merge_chunk` is a thin seam over
   `graphify merge-graphs`, which reads as **Middle Man**. It is not a finding —
   `use-tool-builtins.md` requires exactly that shape, and the alternative is the
   reimplementation that rule exists to prevent.

2. **Always a judgement call.** Each smell is a labelled heuristic — report it as
   "possible Feature Envy", never as a violation. A documented-standard breach
   can be hard; a smell never is.

And one rule that binds both: **skip anything tooling already enforces.** ruff,
ty, taplo, rumdl, gitleaks, typos, pkl, and the `no_lint_skip` /
`md_size_budget` / `hook_guard` steps all run in `mise run lint`. Re-reporting
what a linter already fails on wastes the lens on ground that is already covered
— and, worse, makes the lane look productive while finding nothing new.

## The smells

Each reads *what it is* → *how to fix*. Match against the diff, not the
codebase — this is a review of a change.

- **Mysterious Name** — a function, variable, or type whose name doesn't reveal
  what it does or holds. → Rename it. If no honest name comes, the design is
  murky and the rename is not the fix.
- **Duplicated Code** — the same logic shape in more than one hunk or file in
  the change. → Extract the shared shape, call it from both.
- **Feature Envy** — a method reaching into another object's data more than its
  own. → Move the method onto the data it envies.
- **Data Clumps** — the same few fields or params keep travelling together, a
  type wanting to be born. → Bundle them into one type, pass that.
- **Primitive Obsession** — a primitive or string standing in for a domain
  concept that deserves its own type. → Give the concept its own small type.
- **Repeated Switches** — the same `switch`/`if`-cascade on the same type recurs
  across the change. → Replace with polymorphism, or one map both sites share.
- **Shotgun Surgery** — one logical change forces scattered edits across many
  files. → Gather what changes together into one module.
- **Divergent Change** — one file or module edited for several unrelated
  reasons. → Split so each module changes for one reason.
- **Speculative Generality** — abstraction, parameters, or hooks added for needs
  the spec doesn't have. → Delete it; inline back until a real need shows.
- **Message Chains** — long `a.b().c().d()` navigation the caller shouldn't
  depend on. → Hide the walk behind one method on the first object.
- **Middle Man** — a class or function that mostly just delegates onward. → Cut
  it, call the real target direct. **See rule 1** — a deliberate seam over a
  tool's native command is not this.
- **Refused Bequest** — a subclass or implementer that ignores or overrides most
  of what it inherits. → Drop the inheritance, use composition.

## This repo's own recurring smells

Not Fowler's, but they are what actually goes wrong here, and the Standards lane
should look for them by name:

- **A gate verified only in the PASS direction.** New hk step, new contract, new
  check — was the FAIL direction proved, with a *realistic* mutation?
  (`probes-need-a-control-arm.md` rule 2.)
- **A bound-limited probe reported as an absence.** `-maxdepth`, `head -N`, a
  literal token spelling, a `2>/dev/null`. A 0-result search cited as evidence
  without a control arm is a finding.
- **A number carried without its condition.** A figure that is true under some
  configuration, restated as if unconditional.
- **Inline shell logic creeping into `hk.pkl` or `mise.toml`.** A `run =` line
  that grew a loop, a conditional, or a multi-statement `&&` chain has become a
  program and belongs in `kb_setup`.
- **A doc and the code it describes disagreeing** after a change touched one of
  them. `tool-currency-and-native-first.md` rule 5.
