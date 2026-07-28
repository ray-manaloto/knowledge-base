# Repo-specific smells — ADDITIONS to the spine's baseline

`mattpocock-skills:code-review` carries the Fowler baseline (*Refactoring*
ch. 3) and the two rules that bind it: **the repo overrides** a smell it
endorses, and **every smell is a judgement call**, plus **skip anything tooling
already enforces**. All of that comes from the spine. Do not restate it here and
do not paste a second copy of it into the Standards prompt.

This file is the delta: patterns that go wrong *in this repo* and that Fowler
has no name for. Paste it alongside the spine's baseline, labelled as
additions.

An earlier draft of this skill re-authored the whole Fowler list here, which is
the reinvention `use-tool-builtins.md` exists to prevent — caught by the Spec
lane reviewing this skill's own first commit. If this file ever grows a
general-purpose refactoring vocabulary again, that is the same mistake
returning.

## The additions

- **A gate verified only in the PASS direction.** A new hk step, contract, or
  check whose FAIL direction was never proved — and proved with a *realistic*
  mutation. Ask: would deleting this line keep the suite green? If yes, it is
  decoration. (`probes-need-a-control-arm.md` rule 2.)

- **A tautological probe — a test that builds its fixture with the function
  under test.** It inherits whatever the function does and so cannot detect a
  divergence between that function and the doc describing it. Measured here:
  every review-report test built its path with `report_path()` and none could
  see that the path it produced disagreed with the documented filename.

- **A bound-limited probe reported as an absence.** `-maxdepth`, `head -N`, a
  time window, a `2>/dev/null`, or a **token spelling** — a 0-result grep cited
  as evidence with no control arm.

- **A number carried without its condition.** A figure true under one
  configuration, restated as if unconditional.

- **Collapsing "could not check" into "clean".** DRIFT / SKIP / OK must stay
  distinct; a parse error, a timeout, or an unresolvable ref is *not* a pass.
  Every recorded defect in the currency engine's review was this one.

- **Inline shell logic creeping into `hk.pkl` or `mise.toml`.** A `run =` line
  that grew a loop, a conditional, or a multi-statement `&&` chain has become a
  program and belongs in `kb_setup` (`zero-bash-logic.md`).

- **A doc and the code it describes disagreeing** after a change touched either
  one (`tool-currency-and-native-first.md` rule 5). Worth flagging even when the
  code is right — a reader has to adjudicate, and usually cannot.

- **An inline lint suppression.** `noqa` / `type: ignore` / `nosec` are rejected
  outright; suppressions live in the one root `pyproject.toml` (`do-not.md` #9).

## One override the spine's baseline would otherwise trip

`kb_setup.graphify_ops.merge_chunk` is a thin seam over `graphify merge-graphs`
and reads as **Middle Man**. It is not a finding: `use-tool-builtins.md`
*requires* that shape, and the alternative is the reimplementation that rule
exists to prevent.
