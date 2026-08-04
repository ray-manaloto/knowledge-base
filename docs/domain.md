# Domain docs

How the mattpocock engineering skills should consume this repo's domain
documentation while exploring the codebase. **Single-context** layout — there are
no monorepo signals here (no workspace file, no `packages/`), so there is one
context and no `CONTEXT-MAP.md`.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the glossary of domain terms.
- **`docs/adr/`** — architecture decision records touching the area in question.

**Neither exists today, and that is not a gap to fill upfront.** Proceed
silently; do not flag their absence and do not scaffold them. `/domain-modeling`
creates them lazily, when a term or a decision actually needs resolving. An empty
`CONTEXT.md` nobody maintains is worse than none, because the next reader trusts
it.

## This repo already has a domain vocabulary — it is just not in `CONTEXT.md`

Read it before inventing language:

| Where | What it defines |
| --- | --- |
| root `CLAUDE.md` | the two verbs (**query** / **add**), source kinds, what is derived vs committed |
| `.claude/rules/*.md` | the operating vocabulary — control arm, fail-closed, DRIFT/SKIP/OK, eager vs scoped |
| `docs/graphify-reference.md` | the graphify mental model this whole repo is built on |
| `docs/issue-tracker.md` | tracker conventions and the wayfinding vocabulary |
| the knowledge graph itself | `mise run kb-query -- "<question>"` — deterministic, source-cited, zero LLM tokens |

**Query the graph before the filesystem.** That is this repo's whole premise, and
its source is `CLAUDE.md` § graphify, which puts `graphify query` first for
codebase questions and the wiki ahead of raw source browsing. The
sibling ordering for the **network** is `research-doc-sources.md` step 0, whose
own scope is "before any network call" — cite it for a doc fetch, not for reading
a local file. Two orderings, two sources; using one rule's authority for the
other's claim is how a correctly-cited fact ends up wrong where it is applied.

Control-arm an empty result before concluding the corpus lacks something: a miss
is more often a term-spelling mismatch against extracted node labels than a real
absence.

## Use the established vocabulary

When output names a concept — an issue title, a test name, a proposal — use the
term as this repo uses it. A few that have specific, non-obvious meanings here,
where a synonym would be wrong rather than merely different:

- a **control arm** is the opposite-direction probe that proves a check can fail,
  not a general sanity check;
- a **gate** blocks; an **advisory** never does, and calling one the other
  misrepresents what a green run means;
- **derived** means rebuildable from committed inputs, so "the graph" is not an
  artifact anyone should be asked to commit;
- a **receipt** is the commit-keyed proof a review happened, not the review.

If the concept you need has no term here, that is a signal: either you are
inventing language the project does not use, or there is a real gap worth noting
for `/domain-modeling`.

## Flag conflicts rather than overriding them

There are no ADRs yet, but the equivalent authority exists and is stricter:
`.claude/rules/do-not.md` carries the project invariants, and several are
machine-enforced by the `kb_setup.hook_guard` PreToolUse guard. If output would
contradict a rule file, surface it explicitly rather than quietly working around
it:

> _Contradicts `do-not.md` #4 (no non-Claude backend touches the corpus) — but
> worth reopening because…_

A rule that is merely inconvenient is still the decision until it is changed on
the record.

## Why this file is not at `docs/agents/domain.md`

Where `setup-matt-pocock-skills` would have put it. `agnix` rejects any
`**/agents/*.md` lacking YAML frontmatter, so that path fails
`mise run lint-docs`. Re-probed and control-armed 2026-08-03 — see
`docs/triage-labels.md` for the measurement.

## See also

- `docs/issue-tracker.md` — where issues live.
- `docs/triage-labels.md` — the triage vocabulary.
- `.claude/rules/research-doc-sources.md` — the graph-first research chain.
