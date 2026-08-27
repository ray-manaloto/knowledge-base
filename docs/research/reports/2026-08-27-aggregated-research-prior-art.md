# Prior art for `aggregated-research` — does it already exist, and what folds in

**Date:** 2026-08-27 · **Phase:** P3 of the Aggregated round · **Method:** the
`aggregated-research` skill run on itself, per `#509`'s third test prompt.

## Answer

**Prior art exists, and the honest outcome is a partial retreat, not a deletion.**
Claude Code ships `/deep-research` as a **bundled workflow** that already does
step 4 of this skill's sweep better than the skill can hand-roll it — it fans out
across angles, cross-checks, **votes on each claim, and filters out claims that did
not survive**. Three published agent prompts also mechanize the negative control
this skill was built around, all of them in security tooling.

What no prior art covers is the **ordering** and the **local-first half**: nothing
found runs the corpus graph before the web, reads the shipped source at a pinned
ref, or checks `has_issues` before believing a tracker null. That is the part
`aggregated-research` keeps.

**Recommendation: keep the skill, and change step 4 from "use the developer index
then the web" to "delegate breadth to `/deep-research`, then verify its cited
claims against primary sources."** Steps 0–3 and 5 stay; step 4 stops being
hand-rolled. This is `use-tool-builtins.md` applied to the skill's own body.

## Ranked sources

### Primary — read directly

| Source | What it settles |
|---|---|
| `sources/agent-harness-docs/docs/claude-code/workflows.md:72-82` | `/deep-research` is a **built-in workflow**: "fans out web searches on a question across several angles, fetches and cross-checks the sources it finds, **votes on each claim**, and returns a cited report with claims that didn't survive cross-checking filtered out." Requires WebSearch. Runs **only when invoked** — before v2.1.218 Claude could start it unprompted. |
| `sources/agent-harness-docs/docs/claude-code/commands.md:74` | the same command in the command table, confirming it is shipped surface and not a plugin |
| `sources/mattpocock-skills/skills/engineering/research/SKILL.md` (12 lines) | the minimal shape: background agent → **primary sources only** → one cited markdown file in the repo. No control arms, no ordering, no tracker handling. |
| `sources/Attacca/plugins/attacca-core/agents/researcher.md` (22 lines) | decompose into 2–5 sub-questions · prefer primary · **cross-check load-bearing claims across ≥2 independent sources, flag anything single-sourced** · a "confidence & gaps" note. Carries its own retirement marker: *"Delete when: native deep-research workflows make ad-hoc research subagents redundant for small lookups."* |

That last line is independent corroboration of this report's recommendation,
written by someone else, before this round.

### Primary — published agent prompts that mechanize the negative control

| Source | Mechanism |
|---|---|
| [purpleailab/decepticon](https://github.com/purpleailab/decepticon) `agents/prompts/plugins/verifier.md` | `validate_workspace_finding` takes a **positive command AND an equivalent negative-control command**, both with success patterns, and refuses promotion unless `validated=true`. *"A baseline that matches a success pattern is noise, not confirmation."* The closest thing found to this repo's `kb-arms`. |
| [cybersecurityup/neurosploit](https://github.com/cybersecurityup/neurosploit) `agents_md/meta/false_positive_filter.md` | *"Default to 'not a finding'"* · per-class refutation tests · **negative-control re-test with a benign payload** — if the evidence still appears, the payload did not cause it · require reproduction twice. |
| [terrylica/cc-skills](https://github.com/terrylica/cc-skills) `plugins/crucible/skills/a-research-foundations/SKILL.md` | "6 epistemic disciplines", including **shuffled-null design** (three null types, chosen by hypothesis class) and **agent significance corrections** — *"LLM agents systematically overstate z-scores; treat agent-reported p-values as upper bounds."* |

### Secondary — not read past the result snippet

`joshuaodmark.com/papers/agent-breakage-falsification`; the KDD-2026 *Phantom
Guardrails* PDF; three replication-crisis papers surfaced by the phrase "control
arm" in its clinical-trial sense, not its probe sense.

## Candidates evaluated for folding in

**Adopted (2):**

| Tool | Why | Where it goes |
|---|---|---|
| `/deep-research` | ships in the harness, does claim-voting the skill would otherwise hand-roll, runs in the background so the session stays free | replaces the hand-rolled step 4 |
| `gh api -X GET search/issues` + `gh api repos/OWNER/REPO` | already the skill's steps 2–3; #509 measured it "the best tool, by a wide margin" | unchanged, kept |

**Rejected (9), each with the reason:**

| Tool | Rejected because |
|---|---|
| Firecrawl `developer-index` | **not rejected outright — demoted.** It earned its place in #509's run and it earned it again here: two of the three mechanized-control-arm sources above came from it and would not have come from a plain web search. It is now the *fallback* when `/deep-research` is unavailable (no WebSearch) or when the question is specifically about a repo's issues and PRs. |
| Exa | would duplicate Firecrawl on this question, as #509 already measured. Not re-derived — inherited, and labelled as inherited. |
| Context7 / `ctx7` | for library API docs. Both this question's answers were in a shipped doc and in agent prompt files, which is exactly the case `research-doc-sources.md` step 3 says it does not cover. |
| `last30days` | recency, not truth. Useful for "what are people saying"; the sweep's question class is "what is the case". |
| `repowise` | scoped to one repository by URL. The sweep's subject is usually a repo we do not own. |
| `mcp2cli` | a transport for other MCP servers, not a research surface. |
| `Explore` | in-process, read-only, over *this* repo's files. Step 0's graph query already owns that, and does it for zero LLM tokens. |
| plain `WebFetch` / `WebSearch` | subsumed by `/deep-research`, which is built on WebSearch and adds the voting. |
| the 235-plugin marketplace's `deep-research` plugin (`sources/media/marketplace-235-relevant.txt:74`) | *"Multi-agent deep research pipelines… internet research, repository analysis, schema-driven structured research"* — plausibly strong, but installing a marketplace plugin is `do-not.md` #11 territory and a Ray decision. **Recommended for evaluation, not installed.** |

**What is NOT installed that arguably should be:** nothing identified. The gap
found was the opposite — a shipped built-in (`/deep-research`) that this repo's
doctrine never names. `research-doc-sources.md`'s preference chain has four steps
and none of them is it.

## Nulls, and their control arms

Every probe in this run returned hits, so **no null is owed an arm**. One
deliberately-null probe is recorded to prove the skill emits one:

```
$ grep -rl "zzqx-nonexistent-capability" sources/ | wc -l
0
```

Control arm — same command shape, term known present:

```
$ grep -rl "control-arm" sources/media/*.md | wc -l
8
sources/media/autonomous-execution-program-20260719.md
sources/media/dotfiles-secrets-decision.md
sources/media/dotfiles-secrets-evidence.md
sources/media/dotfiles-secrets-rule.md
sources/media/dotfiles-secrets-guide.md
```

The probe discriminates, so the 0 is real.

**The narrower negative in the Answer** — *"nothing found runs the corpus graph
before the web"* — is armed the same way. The search shape that produced it was
run against a capability that certainly has prior art:

```
firecrawl_search "claude code skill changelog summarizer release notes SKILL.md"
  categories: ["developer"]  ->  5/5 substantive hits
```

including two real `SKILL.md`/`README.md` files for release-note skills. The shape
returns published skills when published skills exist; it returned none for
graph-first research ordering.

## Not measured

- **Whether `/deep-research` is invocable in this session.** It is documented as
  shipped and invocation-only; it was not run, because running it would spend the
  round's budget on a demonstration rather than on P4. The recommendation to adopt
  it therefore rests on the shipped doc, not on an execution.
- **The marketplace `deep-research` plugin's actual behaviour.** Read from a
  one-line corpus inventory entry only. Not installed, not probed.
- **`terrylica/cc-skills` beyond the one SKILL.md excerpt** the developer index
  returned inline. The `findings/methodology/*` files it cites were not opened.
- **Whether `/deep-research`'s voting mechanism would accept an unarmed null.**
  This is the one question that decides how much of `aggregated-research` survives
  the delegation, and it needs an execution to answer.
- **Any non-English or non-GitHub prior art.** The search shape is
  GitHub-and-docs-weighted by construction.

## GitHub repos touched

- [purpleailab/decepticon](https://github.com/purpleailab/decepticon) — its verifier prompt requires a positive command and an equivalent negative control before any finding is promoted; the closest published analogue to this repo's control-arm rule.
- [cybersecurityup/neurosploit](https://github.com/cybersecurityup/neurosploit) — a false-positive filter agent whose method is negative-control re-test plus mandatory reproduction.
- [terrylica/cc-skills](https://github.com/terrylica/cc-skills) — the `crucible` plugin's research-foundations skill: shuffled-null design and agent significance corrections.
- [jamie-bitflight/claude_skills](https://github.com/jamie-bitflight/claude_skills) — surfaced by the control-arm search; a skills-system reference, read only for the arm.
- [alma-oss/spirit-design-system](https://github.com/alma-oss/spirit-design-system) — surfaced by the control-arm search; a release-notes skill, read only for the arm.
- [mattpocock/mattpocock-skills](https://github.com/mattpocock/mattpocock-skills) — already a pinned source (`sources/mattpocock-skills`); its `research` skill is the minimal prior-art shape.
- [Attacca](https://github.com/Attacca) — already a pinned source (`sources/Attacca`); its `researcher` agent carries the retirement marker this report corroborates.

The three security repos are **new to this repo** and are candidates for
`sources/REGISTRY.md`; the last two are already pinned.
