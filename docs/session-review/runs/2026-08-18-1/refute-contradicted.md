# Refutation — "CLAUDE.md:180 / kb-synthesist.md say opus, session-review.js dispatches fable"

Commit under test: `f772f5eb` (HEAD). Working tree: only `.codex/config.toml` modified.

## Verdict: REFUTED

The finding's *mechanical* facts are all true. Its *conclusion* — that this is a
contradiction, and that CLAUDE.md:180 and the frontmatter "were not updated to
match" — is false. Both cited artifacts already state the reconciling rule, and
one of them is load-bearing for a different consumer that would BREAK if changed.

## The facts the finding got right (verified)

- `.claude/agents/kb-synthesist.md:3` → `model: opus`  (confirmed)
- `.claude/workflows/session-review.js:511` → `agent(prompt, { ...opts, model: 'fable', effort: 'high' })`
- `.claude/workflows/session-review.js:514` → `agent(prompt, { ...opts, model: 'opus', effort: 'xhigh' })` (fallback)
- `.claude/workflows/session-review.js:561` → `{ label: 'synthesise', phase: 'Synthesise', agentType: 'kb-synthesist' }`
- `.claude/skills/kb-session-review/SKILL.md:92` → "`kb-synthesist` on **`fable`**, falling back to `opus`/`xhigh`"

## Refutation 1 — the cited line ANSWERS the finding, and the quote stopped one clause short

The finding quotes CLAUDE.md:180 as *"kb-adversarial-verifier and kb-synthesist
(opus) for judgment"*. The same line, same row, continues:

> `model` frontmatter is only step 3 of 4 in resolution
> (`CLAUDE_CODE_SUBAGENT_MODEL` and the per-invocation param outrank it), so it
> is a preferred default, not a guarantee.

`agent(prompt, {...opts, model:'fable'})` at :511 IS "the per-invocation param".
CLAUDE.md:180 does not claim kb-synthesist RUNS on opus; it claims the roster
DECLARES opus and that a per-invocation param overrides it. A doc that pre-states
the exact override mechanism is not contradicted by an instance of that override.

The original probe was a **quotation bound**: it cited the first half of a
sentence whose second half is the refutation.

## Refutation 2 — vendor primary source, already in this corpus

`sources/extractions/agent-harness-docs-docs.json:452` (label "Four-step model
resolution order", source_url https://code.claude.com/docs/en/sub-agents.md,
captured 2026-07-30):

> "Claude Code resolves a subagent's model in this order: 1 the
> CLAUDE_CODE_SUBAGENT_MODEL environment variable when set to an alias or model
> ID, 2 the per-invocation `model` parameter Claude can pass, 3 the subagent
> definition's `model` frontmatter, 4 the main conversation's model."

Step 2 outranks step 3 by design. Frontmatter is a default, not a binding.

## Refutation 3 — the frontmatter is LIVE for another consumer; "fixing" it breaks that one

`grep -n "model:" .claude/workflows/kb-tool-review.js` → **0 hits**
(control arm: the identical grep on `session-review.js` → **14 hits**, so the
probe discriminates).

`.claude/workflows/kb-tool-review.js:204` dispatches
`{ agentType: 'kb-synthesist', label: 'synthesize', phase: 'Synthesize' }` with
NO model param, so step 3 — the frontmatter `model: opus` — is what actually
resolves there. The frontmatter is therefore correct and load-bearing, not stale.
Editing it to `fable` to "match" session-review.js would silently re-tier a
different workflow.

## Refutation 4 — CLAUDE.md:180's roster claim is verifiably accurate as written

`for f in .claude/agents/*.md; do grep -E "^(name|model|effort):" ...` gives:
kb-adversarial-verifier opus/high · kb-advisor fable/high · kb-corpus-curator
sonnet/medium · kb-extraction-worker sonnet/medium · kb-synthesist opus/high ·
kb-tool-researcher sonnet/high. Exactly what CLAUDE.md:180 says the roster
declares. Nothing on that line is out of date.

## Refutation 5 — the workflow does not hide the tiering; it declares it in its own meta

`.claude/workflows/session-review.js:78-82`:
`{ title: 'Synthesise', ..., model: 'fable, falling back to opus/xhigh' }`
and :495-508 carry a comment explaining the choice and citing `kb-advisor.md`'s
"never silently become a different model" rule, with `log('FABLE UNAVAILABLE —
re-dispatching to opus at xhigh. THIS RUN FELL BACK.')` at :513. Three artifacts
(workflow meta, workflow comment, SKILL.md:92) document it. Nothing is undeclared.

## Contradiction with other findings in the set

None observed. Note the ASYMMETRY the finding did not report, which is the
interesting half: `session-review.js:436-467` dispatches
`agentType: 'kb-adversarial-verifier'` with **no** model override, and the comment
at :452-456 says routing by agentType rather than a bare model "is the house
pattern". So one of the two "judgment (opus)" agents keeps the frontmatter and one
overrides it — a *design* asymmetry worth a note, not a documentation defect.

## What would have made this a real finding

If CLAUDE.md:180 said "kb-synthesist RUNS on opus" with no resolution-order
caveat, or if kb-tool-review.js also overrode the model, the frontmatter would be
dead. Neither holds.

## Probes run

- `sed -n '175,185p' CLAUDE.md`; `grep -n "kb-synthesist" CLAUDE.md`
- `sed -n '1,20p' .claude/agents/kb-synthesist.md`
- `sed -n '490,580p' .claude/workflows/session-review.js`; `sed -n '425,475p' ...`; `sed -n '60,95p' ...`
- `grep -n "model:" .claude/workflows/session-review.js` (14) vs `... kb-tool-review.js` (0) — control arm
- `grep -rn "CLAUDE_CODE_SUBAGENT_MODEL" --include="*.md" --include="*.js" --include="*.py" --include="*.json" .`
- `mise run kb-query -- "which model does kb-synthesist run on"` → TRUNCATED, 426 AST nodes, all
  from vendored uv/codex sources. NOT evidence of absence: `.claude/workflows/*.js`
  is not AST-extracted into the graph, so the graph could not answer this. Answered
  from primary artifacts instead.

## GitHub repos touched

- [mrkhachaturov/agent-harness-docs](https://github.com/mrkhachaturov/agent-harness-docs) — the ingested Claude Code sub-agents doc carrying the four-step model resolution order.
