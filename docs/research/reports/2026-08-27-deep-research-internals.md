# `/deep-research` internals — fact-finding

Commit: `03e07cc45f89`. Date: 2026-08-27. Agent: deep-research-internals.

> **Promoted 2026-08-29** from `.agent/kb/reports/agents/deep-research-internals.md`
> per `agent-report-persistence.md` rule 1b: this report is now load-bearing —
> ticket #572 cites its four constants for the "spine" budgets file, and #585/#586
> (the spine dispatch/verify loop and its tuning pass) consume that file. `.agent/`
> is gitignored and does not survive a fresh clone, so a citation to the original
> path was a citation only one machine could open. This copy is verbatim; nothing
> below was re-derived or edited for the promotion.

## 1. Is the script on disk?

**Yes — as a verbatim, UNMINIFIED JS source string embedded in the CLI binary.**

- `command -v claude` → `/Users/rmanaloto/.local/bin/claude` → symlink →
  `/Users/rmanaloto/.local/share/claude/versions/2.1.247`, which `file` reports as
  `Mach-O 64-bit executable arm64` (a Bun single-file binary, not a directory).
- `~/.claude/workflows` — **does not exist** (`ls` → No such file or directory).
- `/private/tmp/claude-501/bundled-skills/2.1.247/d1b9316df820c91c5f7b7a160ea3d338/`
  contains only `verify/` and `artifact-capabilities/`. **No deep-research there.**
  (Bundled *skills* are extracted to disk on demand; bundled *workflows* are not —
  `op()`/`up()` extract only skills with `files`.)

### Control arms on the binary grep

| probe | count |
|---|---|
| `grep -ac 'deep-research' $BIN` | **8** |
| `grep -ac 'WebSearch' $BIN` (known-present control) | 55 |
| `grep -ac 'zzzqqqnotastring' $BIN` (known-absent control) | **0** |

Probe discriminates. Eight byte offsets: `175090508, 176549820, 193025632,
193025876, 193028618, 193048551, 193549383, 204875735`.

**The docs string "Fan out web searches on a question" returns 0** — that phrasing
is the docs site's, not the binary's. The binary's own description string is:

> `Deep research harness — fan-out web searches, fetch sources, adversarially verify claims, synthesize a cited report.`

### Registration site

`FFr()` calls `Lar(<source-template-literal>, {name, description, whenToUse, phases}, {disableModelInvocation: $Ms})`.
`initBundledWorkflows()` (`NMs`) calls `FFr()`.

Header comment inside the source, verbatim:

```
// deep-research: Scope → pipeline(Search → URL-dedup → Fetch+Extract) → 3-vote Verify → Synthesize
// Ported from bughunter architecture. WebSearch/WebFetch instead of git/grep.
// Question is passed via Workflow({name: 'deep-research', args: '<question>'}).
```

Full extracted source saved to the scratchpad at `.../scratchpad/dr.txt` (~24 KB region
from offset 193025900). It is a Workflow-DSL script using `phase()`, `agent()`,
`parallel()`, `pipeline()`, `log()`.

## 2. Phases

The `phases` metadata array (`NFr`), verbatim:

| # | title | detail |
|---|---|---|
| 0 | **Scope** | Decompose question (from args) into 5 search angles |
| 1 | **Search** | 5 parallel WebSearch agents, one per angle |
| 2 | **Fetch** | URL-dedup, fetch top 15 sources, extract falsifiable claims |
| 3 | **Verify** | 3-vote adversarial verification per claim (need 2/3 refutes to kill) |
| 4 | **Synthesize** | Merge semantic dupes, rank by confidence, cite sources |

### The four constants (verbatim from source)

```js
const VOTES_PER_CLAIM = 3
const REFUTATIONS_REQUIRED = 2
const MAX_FETCH = 15
const MAX_VERIFY_CLAIMS = 25
```

Fan-out width: the **prompt** asks for 5 angles; the **schema** allows
`minItems: 3, maxItems: 6`. So 3–6, prompted to 5.

Search results per angle: `SEARCH_SCHEMA.results maxItems: 6`, prompt asks "top 4-6".
Claims per source: `EXTRACT_SCHEMA.claims maxItems: 5`, prompt asks 2-5.

### Structure (not a phase barrier between Search and Fetch)

`pipeline(scope.angles, searchFn, fetchFn)` — searchers stream into the dedup+fetch
stage as they complete; **no barrier**. The barrier before `Verify` is explicit and
commented: *"Barrier here is intentional — claim pool must be fully assembled before
ranking/verification."*

Budget accounting is a shared mutable `fetchSlots = MAX_FETCH` decremented in the
dedup stage; once exhausted, only `relevance: "high"` results still pass
(`if (fetchSlots <= 0 && relRank[r.relevance] >= 1) budgetDropped.push(...)`).

Claim ranking before verify: sort by `importance` (central/supporting/tangential)
then `sourceQuality` (primary/secondary/blog/forum/unreliable), `.slice(0, 25)`.

`agentCalls` self-reported as: `1 + angles + sources + (voted * 3) + 1`.

## 3. Tools the agents get

- **Scope agent**: no tool named; pure decomposition, structured output only.
- **Search agents**: `"Use WebSearch with the query above (or a refined version)."`
- **Fetch/Extract agents**: `"Use WebFetch to retrieve the page content."`
- **Verifier agents**: `"WebSearch for contradicting evidence"`.
- **Synthesis agent**: no tool named.

So: **WebSearch and WebFetch**. Nothing else is named in any prompt. Corroborated by
the enterprise setting `disableBundledSkills`, whose description reads:
*"Disables Claude Code's bundled skills and workflows (deep-research and similar).
Use where WebFetch/WebSearch aren't available."*

## 4. The voting / filtering mechanism — verbatim

Each of the top-25 claims gets `VOTES_PER_CLAIM = 3` **independent adversarial
verifier agents**, run via nested `parallel()`. Each verifier returns
`VERDICT_SCHEMA = { refuted: boolean, evidence: string, confidence: high|medium|low, counterSource?: string }`.

The verifier prompt is adversarial by construction:

```
"Be SKEPTICAL. Try to REFUTE this claim. ≥2/3 refutations kill it."
...
"**refuted=false** ONLY if: claim is well-supported, current, and source quality matches claim strength."
"Default to refuted=true if uncertain."
```

Its 5-point checklist: quote actually supports the claim? · WebSearch for
contradicting evidence · source quality sufficient for claim strength ·
outdated? · marketing/press-release/cherry-picked benchmark/forum speculation?

**The tally is three-outcome, not binary** (this is the part worth copying):

```js
const valid   = verdicts.filter(Boolean)          // a vote can be null: user-skip or agent error
const refuted = valid.filter(v => v.refuted).length
const errored = VOTES_PER_CLAIM - valid.length
const survives  = valid.length >= REFUTATIONS_REQUIRED && refuted < REFUTATIONS_REQUIRED
const isRefuted = refuted >= REFUTATIONS_REQUIRED
// otherwise → unverified
```

Its own comment: *"Three outcomes (go/ccissue/69883 — infra failure must not read as
'refuted'): survives — quorum of valid votes AND fewer than REFUTATIONS_REQUIRED
refuting · isRefuted — ≥REFUTATIONS_REQUIRED refute votes (adjudicated against on
merit) · otherwise — unverified: too few valid votes to adjudicate (verifier agents
errored)."*

So: **not majority, not unanimity — a refutation quorum of 2, plus a validity quorum
of 2.** A claim with 2 valid votes and 1 errored, both non-refuting, survives. A claim
with only 1 valid vote is `unverified`, never `confirmed` and never `killed`.

All three buckets reach the output. `killed` → `refuted[]` with a `vote: "N-M"` string;
`unverified` → `unverified[]` with `erroredVotes`/`validVotes`. The synthesis prompt is
handed a "Refuted claims (for transparency)" block and an "Unverified claims" block, and
is instructed to mention the unverified count in caveats.

Confidence is assigned twice: per-verdict by each voter, and per-finding by the
synthesizer — *"high (multiple primary sources, unanimous votes), medium (secondary
sources or split votes), low (single source or blog-quality)."*

Degenerate paths are handled explicitly rather than by throwing: zero ranked claims,
zero confirmed (with an all-errored branch that says *"This is an infrastructure
failure, not a research finding"*), and a null synthesis report (returns confirmed
claims unmerged rather than discarding the run).

### Security machinery worth noting (it is ~40 lines of the script)

The sandbox is *"a bare ECMAScript realm — no URL global"*, so URL host/path parsing is a
hand-written regex `URL_HOST_PATTERN` with commented reasoning about
`evil.com\@trusted.com` and `x@trusted.com@evil.com`. Progress labels made from
web-controlled host/title go through `LABEL_STRIP` (C0/C1 controls, bidi
overrides, zero-width, the whole double-quote lookalike family) + `STRICT_HOST` +
a 40-codepoint cap with the ellipsis placed *inside* the quotes. A bare
`fetch:<host>` label is emitted only when the host is verbatim clean ASCII;
anything else routes through `quotedLabel`.

## 5. Invocation constraint — can a subagent invoke it?

**No. Explicitly not — the refusal message names workers.**

Registration: `{disableModelInvocation: $Ms}` where

```js
function $Ms(){ if (we(DMs,!1)) return !1; return !0 }
var DMs = "tengu_sorrel_avocet"
```

`we(gate, default=false)` is the feature-gate read. So `disableModelInvocation`
resolves **true** unless the `tengu_sorrel_avocet` gate is enabled for the account.

The Skill-tool gate `Uir(e, {commandName, userTypedThisTurn, isMainSession, permissionContext})`:

```js
if (e.disableModelInvocation && !r)   // r = userTypedThisTurn
  return { reason: "disable_model_invocation",
           message: `Skill ${n} cannot be used with ${ri} tool due to disable-model-invocation. ...
                     Do not replicate this skill's workflow by other means — it is reserved for
                     explicit user invocation.`,
           errorCode: 4 }
```

and the message helper `yOt`:

> `It cannot be invoked via the Skill tool in this session, by the coordinator or by workers — the user can run /<name> by typing it themselves.`

**"by the coordinator or by workers"** — workers are subagents. The check is on
`userTypedThisTurn`, not on `isMainSession`; `isMainSession` is used only for the
separate allowlist check. So neither the main thread programmatically nor any
subagent can invoke it; the only unlock is the user literally typing
`/deep-research` in that turn (or the `tengu_sorrel_avocet` gate flipping).

Reinforced independently in the system prompt (`aqr`, joined with newline):

```
Do not call the AgentTool unless the user requested it
Do not use workflows or deep-research unless the user requested it
```

Consistent with the primary source already in the corpus,
`sources/agent-harness-docs/docs/claude-code/workflows.md:80`:
*"/deep-research runs only when you invoke it. Before v2.1.218, Claude could also start it on its own."*
The mechanism behind that sentence is the `disableModelInvocation` default flip above.

`userInvocable` defaults `true`, so it remains typeable; `isHidden = !userInvocable` → visible.

Note the harness also blocks the workaround: *"Do not replicate this skill's workflow
by other means."* Building our own equivalent plugin is a different thing from
invoking theirs — but the refusal text is worth knowing before we quote it.

## GitHub repos touched

_None._ All findings come from the local Claude Code binary
`/Users/rmanaloto/.local/share/claude/versions/2.1.247` and the already-pinned corpus
source `sources/agent-harness-docs/`.
