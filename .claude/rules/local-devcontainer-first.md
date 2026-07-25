# Local-First: Reproduce the Failure Cheaply Before Spending an Expensive Run

> **Name kept for cross-repo parity.** In the sibling dotfiles repo this rule is
> literally about devcontainers and image builds. This repo has neither — no
> `.devcontainer/`, no Dockerfile, no CI. What ports is the *principle*, and it
> ports with teeth, because this repo has its own expensive round-trip: a
> host-agent extraction pass costs real Claude tokens and a full `kb-build`
> re-clones every pinned source.

Before you spend an expensive run, ask: **can this change's failure mode be
exhibited by a cheaper probe?** If yes, do that FIRST. Spending the expensive
run to find out is the costly way to ask a cheap question.

This is the cost-tier sibling of `verify-before-advancing.md`. That rule says
*run every applicable check before advancing*; this one says *pick the cheapest
environment that can actually exhibit the failure.* `zero-skip-policy.md`
already bans "push and see if it passes" — this is the constructive half.

## The cost ladder in this repo

Cheapest first. Never reach past the first rung that can answer the question.

| Rung | Cost | Answers |
|---|---|---|
| `mise run kb-query -- "…"` / `graphify path` / `explain` | ~0, no LLM | is it already in the corpus? |
| `mise run kb-currency-check` | ~10ms, offline | is the graph stale / built by an unknown version? |
| `mise run kb-validate-chunks -- <chunk>` | seconds | is this extraction chunk well-formed? |
| `mise run lint` / `mise run test` | ~1 min | does the code hold? |
| `mise run kb-merge -- <chunk>` | minutes, no LLM | does it merge and recluster? |
| `mise run kb-build` | minutes–tens, network, no LLM | does the whole corpus reproduce from committed inputs? |
| `mise run kb-transcribe` | tens of minutes, local | audio → text |
| the `kb-extract` fan-out | **real Claude tokens, not free to redo** | semantic extraction |
| `mise run kb-artifacts` | minutes, regenerates every view | derived outputs |

## The gate

1. **Name the failure mode in one sentence.** "That manifest SHA no longer
   exists upstream." "That chunk has no edges." "The query returns code symbols
   for a prose question."
2. **Find the cheapest rung that can exhibit it.** A single-source `kb-update`
   before a full `kb-build`. A `kb-validate-chunks` before a `kb-merge`. One
   subagent on one raw file before a 20-way fan-out.
3. **Run it, with both arms** (`probes-need-a-control-arm.md`). A probe that
   has only ever passed is not evidence.
4. **Only then spend the expensive run.**

## Pick the right environment — a dirty one lies

The environment must match the one whose failure you are predicting. Measured
in the sibling repo: a version pin "failed" in the working environment and
passed in a clean one, because the working environment already had a newer
version installed. The pin was fine; the environment lied.

Here, the equivalent trap is **your working tree vs a fresh clone**:

- an extraction chunk that exists only in `.agent/` or untracked;
- a `sources/<name>/` clone advanced past its manifest SHA;
- a `graphify-out/` carrying nodes from a source you later removed.

`mise run kb-build` **from a clean tree** is the honest arm. `kb-currency-check`
catches the stale-graph half.

## What this does NOT license

- **It does not replace the full run.** A green cheap probe answers one
  question. Never skip a gate because a probe passed.
- **It does not license hand-running graphify.** A probe still goes through a
  `kb-*` task (`mise-tasks-only.md`) — the guard denies the alternative, and
  correctly.
- **It does not make a partial extraction a finished one.** One subagent on one
  file proves the prompt shape, not the corpus.

## Applies to

Every change to a corpus input (`sources/**`), every extraction run, and any
change whose failure mode is observable more cheaply than the run you were
about to start.

## See also

- `verify-before-advancing.md` — the parent gate.
- `probes-need-a-control-arm.md` — arm both directions.
- `zero-skip-policy.md` — never "run it and see".
- `persistence-gate-retry.md` — the sibling for the *other* wasted-run cause:
  a transient network failure misread as a real defect.
