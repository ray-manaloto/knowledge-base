# Does `aggregated-research` beat not having it — the baseline comparison

**Date:** 2026-08-27 · **Commit:** `574d45f1df98` · **Method:** `skill-creator`'s
loop as #509 specifies it — one realistic prompt, run **with** the skill and as a
**baseline** with no skill, same question, same model class, same repo, same turn.

The prompt is #509's test prompt 2 — *"What do other projects do about
`<problem>`?"* — instantiated as **"what do other projects do about `file:line`
citations in generated documentation going stale?"**. #509 calls this the prompt
most likely to expose a weak skill, because it has no primary source to anchor
on: the answer is a practice, not a fact.

Chosen because the round that ran it had just corrected nine stale citations
across two published artifacts, so both reports could be judged against something
real rather than on style.

## Answer

**The skill earns its keep, and not where it was expected to.** The baseline was
strong — it produced control arms, a limits section and a repos-touched
enumeration *unprompted*, because this repo's rules are eager and load into every
session. So the skill adds nothing on discipline the session already has.

What it added is **depth of source and completeness of the negative**:

| | baseline | with skill |
|---|---|---|
| sources read at a **pinned ref** | 1, and that at a default branch | **3**, at `v0.4.40` and `10.14`, with `file:line` |
| nulls carrying an explicit control arm | **0** — a prose "limits" section instead | **6**, each with its arm and a verdict |
| tracker channel checked before a null was read | no | **5 repos**, `has_issues` / `has_discussions` |
| "is it already in our corpus" checked, armed | asserted, not probed | `fiberplane` → 0, control `graphify` → **44** |
| new trap discovered | — | **1** (below) |
| decisive lead | not found | **`fiberplane/drift`** |

The single sharpest difference is that last row. The baseline returned five
sensible families of practice. The skill's run returned the same territory **and**
`fiberplane/drift` — a tool that binds a markdown doc to a file or AST symbol in a
`drift.lock`, stamps an XxHash3 of the target's normalised AST, exits 1 from
`drift check` when stale, and ships a Claude Code / Codex skill so agents re-stamp
as they edit. It is the closest published prior art to this repo's own problem,
and it came from step 4's developer index, which the baseline never ran.

## What both runs agree on, and it is actionable here

`python/src/kb_setup/citations.py` + `kb_setup.resolve` already parse `file:line`
out of authored markdown and verify the path resolves and the line is within
`line_count` (`resolve.py:660-674`).

**That is a BOUND check, not a CONTENT check.** `tiny.py:9999` is caught;
`tiny.py:2` pointing at code that moved is not. Which is exactly the defect this
round corrected by hand on two published artifacts, nine citations, off by +6 to
+77 lines.

Both runs independently named the same two cheap closures, neither needing new
code: prefer a **symbol name** over a line number in authored prose — the graph
already resolves symbols and a symbol survives edits above it — or pin the
**commit** beside the number where the coordinate is genuinely load-bearing.

## What the run changed about the skill itself

Two edits, both from evidence produced by the run rather than by review.

**Step 4 was wrong, and only an execution could show it.** P3 adopted
`/deep-research` on the strength of its shipped documentation and flagged the
adoption as unverified in its own *Not measured* section. The evaluation lane,
told to follow the skill, reported it *"could not invoke it from this subagent"* —
and the pinned harness doc says why:
*"`/deep-research` runs only when you invoke it. Before v2.1.218, Claude could
also start it on its own"* (`sources/agent-harness-docs/docs/claude-code/workflows.md:80`).

So the step now reads: **run** Firecrawl `developer-index`; **ask the user for**
`/deep-research`. Corrected on the step rather than overwritten, because the
reason for preferring the bundled workflow still stands — it is only unreachable,
not wrong.

**A new trap, measured on this run.** `command -v mkdocs` and `command -v doxygen`
both print FOUND on this host, and both are mise shims that die with
`No version is set for shim`. A `command -v` hit is not an install. Added to trap
4, beside the stale-PATH version skew it generalises.

## Not measured

- **n = 1.** One prompt, one pair of runs, no repetition. Nothing here separates
  the skill's effect from run-to-run variance, and no claim above should be read
  as a rate.
- **Test prompts 1 and 3 were not run as a pair.** Prompt 3 was run as P3 of this
  round, with no baseline beside it; prompt 1 has not been run at all.
- **Neither report's external claims were re-verified by a third party.** The
  with-skill run's own *Not measured* section is honest about which of its sources
  it inferred (mdBook's severity on a missing anchor) versus read.
- **`drift` was not installed or run** by either lane. Every claim about it is
  README-sourced at a default branch. 137 stars and a single-vendor origin are a
  real adoption risk, and adopting it is not proposed here.
- **Cost was not compared.** The with-skill run did strictly more work; whether
  the extra depth is worth the extra tokens on an ordinary question is unmeasured,
  and on a cheap question the answer is probably no.

## GitHub repos touched

- [rust-lang/mdBook](https://github.com/rust-lang/mdBook) — `RangeOrAnchor` include grammar, read at `v0.4.40`.
- [facelessuser/pymdown-extensions](https://github.com/facelessuser/pymdown-extensions) — `SnippetMissingError` on a vanished section, at `10.14`.
- [vuejs/vitepress](https://github.com/vuejs/vitepress) — `path#region` snippet grammar; warns rather than errors.
- [fiberplane/drift](https://github.com/fiberplane/drift) — AST-signature doc/code binding with a CI check; the decisive lead, and the closest prior art to this repo's problem.
- [SimonCropp/MarkdownSnippets](https://github.com/SimonCropp/MarkdownSnippets) — the generate-the-doc family.
- [flavienbwk/freshdoc](https://github.com/flavienbwk/freshdoc) — version-tagged cross-repo sync; found by the baseline only.
- [block/elasticgraph](https://github.com/block/elasticgraph) — PR #706, CI that executes README snippets; baseline only.
- [pellepelster/snex](https://github.com/pellepelster/snex) — marker-based extraction; baseline only.
- [sphinx-doc/sphinx](https://github.com/sphinx-doc/sphinx) · [nedbat/cog](https://github.com/nedbat/cog) — channels checked, sources not read.
- [the-pr-agent/pr-agent](https://github.com/the-pr-agent/pr-agent) — issue #2232, the failure in the wild.
- [zauberzeug/nicegui](https://github.com/zauberzeug/nicegui) — issue #5988, adjacent editor-anchor prior art.
- [google/gitiles](https://github.com/google/gitiles) — issue #267, permalink-to-commit; baseline only.
- [rust-lang/rust](https://github.com/rust-lang/rust) — symbol anchors in generated docs; baseline only.

**The baseline found four repos the skill's run did not** (freshdoc, elasticgraph,
snex, gitiles). Recorded because it is the honest counterweight to the table
above: the skill's run went deeper on fewer sources, which is a trade and not a
free win.
