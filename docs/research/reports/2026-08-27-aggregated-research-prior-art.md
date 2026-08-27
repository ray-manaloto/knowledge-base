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

---

## ADDENDUM, 2026-08-27 — the discovery sweep this report did not do

**Added after publication rather than rewritten**, because the counts above are
already committed and someone may have read them.

**The `AGG-SELF: 11 prior-art tool(s) evaluated` line overstates what happened.**
Of those 11, exactly **one** was discovered — the marketplace `deep-research`
plugin, from a single line of a corpus inventory. The other ten were the candidate
list the round's rider handed over: firecrawl, exa, context7, last30days,
repowise, mcp2cli, Explore, `gh api`, WebFetch/WebSearch, graphify's verbs.

So this report answered *"which already-installed things should fold in?"* It did
not answer #509's actual ask, which is broader and worth quoting against itself:

> *"Ray also asked that the skill re-run itself to discover more research tooling
> — i.e. one of its own worked examples should be 'what other CLIs, MCP servers,
> or skills would answer this class of question', so the tool list stays current
> rather than frozen at what was installed the day it was written."*

Frozen at what was installed is exactly what the report above is. Ray caught it.

Two lanes then ran the sweep properly, both following the skill:
`.agent/kb/reports/agents/tooling-sweep-local.md` (143 lines) and
`tooling-sweep-world.md` (106 lines).

### What the local sweep found — the gap is not a missing plugin

**Seven research-capable lanes are already installed, already paid for, and were
named nowhere in the skill.** Armed: `grep -ci` over `SKILL.md` returned **0** for
`exa`, `last30days`, `antigravity`, `adversarial`, `premise-verifier`, `repowise`
and `WebSearch`, against a control of `kb-query` **2** and `ctx7` **1** — so the
zeroes are absences, not a broken grep.

Two of them close holes the skill itself documents: `antigravity:research` is a
subagent-reachable substitute for `/deep-research`, which step 4 records as
unreachable; and `kb-adversarial-verifier` is the control-arm rule as an
executable lane. Both are now named in the skill.

**Of 219 marketplace entries read in full, nothing is a must-install.** The read
was exhaustive rather than keyword-filtered on purpose, and that paid: two
candidates (`graph-query-mcp`, `writ`) carry none of research/search/docs/knowledge
in their names and a keyword pass would have missed both — which is precisely how
the original run saw three entries out of 219.

### What the world sweep found — four real gaps, and one refuted premise

**Refuted first: academic and paper search is NOT a gap.** The brief named it as
one; `firecrawl_research_search_papers` is installed and returned three real arXiv
records on the first call. Every arXiv/OpenAlex MCP server was rejected as a
duplicate of a working tool.

| # | candidate | capability this stack lacks | cost |
|---|---|---|---|
| 1 | **`lychee`** (3,865★, Apache-2.0, pushed 2026-08-25) | verifies a cited URL still resolves. **551 unique external URLs** in tracked markdown, unchecked. `aqua:lycheeverse/lychee` → 0.24.2 | one mise pin + one task |
| 2 | **`mcp.grep.app`** | regex source search across ~1M public repos; handshake measured live, no auth | register, or `mcp2cli` first |
| 3 | **`deps.dev`** | package-registry metadata as a first-class source | keyless, no install |
| 4 | **Chroma Package Search** | grep/read the real source of a published package version, six registries | API key, pricing unpublished |

The official **MCP Registry** is added to the skill as a *discovery source*, not an
install: `curl registry.modelcontextprotocol.io/v0/servers?search=` is the cheapest
"does an MCP for X exist" probe, with the caveat its own null carries — it
under-covers hosted servers, so a 0 there is not an absence (grep.app is live and
unregistered).

**Rejected classes, one line each:** every web-search wrapper (Firecrawl covers
it); every persistent-memory plugin — including `basic-memory`, which is already
*in* this corpus — because that is graphify's job and adopting one forks it;
`grace-marketplace` and eight other code-knowledge-graph plugins as graphify peers;
twelve debate/panel plugins, which *"produce opinions, not armed nulls — the exact
failure mode this skill was built against"*; ~90 orchestration frameworks, since
`fable-orchestrator` occupies that slot.

### Bounds both sweeps inherited, stated

- The marketplace corpus file is itself a **filtered** view: its header records
  `TOTAL: 2263 | STRONG-relevant: 235 | BEYOND agent*/ai* front: 219`. The 16
  `agent*`/`ai*` entries are absent from the file, and the other 2,028 were cut by
  a relevance judgement made elsewhere and not re-derived.
- **Nothing was installed and nothing was run end to end.** grep.app was proven to
  handshake, not to answer a real question; Chroma's tools were never called.
- Directory counts quoted by the world sweep (claude-plugins.dev's plugin/skill
  totals) are secondary and unverified.

### Adopting any of these is Ray's call

`do-not.md` #11 — project scope only, never a write to `~/.claude`. Both sweeps
recommend and hand back.
