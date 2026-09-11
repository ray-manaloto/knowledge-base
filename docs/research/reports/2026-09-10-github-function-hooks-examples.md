# GitHub as a source of examples — function hooks / Claude Mods (2026-09-10)

Branch `feat/728-kb-fork-rebase` @ `2c792de5f049`. Read-only research; the only file written is this report.

Two jobs: (1) exhaust the `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` GitHub search and every adjacent one; (2) specify the reusable mise task + `kb_setup` module that makes "use GitHub as a source of examples" repeatable.

Extends — does not duplicate — `.agent/kb/reports/agents/function-hooks-research.md` (read in full first). That report established the mechanism from `anthropics/claude-code`'s own `mods/` tree, the `sec-default`/`diff`/`telemetry` built-ins, the tier model, the `classic.*` seam, and the 2.1.251 binary-strings finding. **This report is about what is NEW beside it: third-party code in the wild.**

## Control arms — run BEFORE any zero is believed

Tooling: `gh api -X GET search/code` throughout, never `gh search code` (measured in this repo: `gh search` returns `[]` on failure, making a rate limit indistinguishable from a zero).

Auth: `gh auth status` → authenticated as `sortakool` via `GITHUB_TOKEN`, scopes include `repo`. Rate limits at start: `code_search` 10/10 remaining (limit 10/min), `search` 30/30 (limit 30/min), `core` 4949.

**Three-armed, one command shape, all run 2026-09-10:**

| Arm | Query | `total_count` | Verdict |
|---|---|---|---|
| **A — positive control** | `CLAUDE_CODE_ENABLE_TOOL_SEARCH` | **10** (`omnigent-ai/omnigent`, `next-bin/cc-helper`, `nice-and-precise/tebra-content-os`, …) | the probe CAN return hits |
| **B — negative control** | `CLAUDE_CODE_ENABLE_ZZQQXX_NOT_A_REAL_FLAG` | **0**, `incomplete_results: false` | the probe CAN return a real zero |
| **Target** | `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` | **65**, `incomplete_results: false` | discriminating, and non-empty |

Arm B matters as much as arm A: without it, a zero anywhere below could be a silently-filtered index rather than an absence. Every zero reported in this document was measured with both arms already green in the same minute, and `incomplete_results` is reported alongside each — GitHub sets it `true` when it timed out mid-scan, which is a THIRD outcome distinct from "hits" and "none".

## Job 1 — the literal query, exhausted

`gh api -X GET search/code -f q='CLAUDE_CODE_ENABLE_FUNCTION_HOOKS' -f per_page=100` → **65 hits across 22 distinct repositories**, one page, nothing truncated.

| Repo | Hits | What it is |
|---|---:|---|
| `lossless-claude/lcm` | 14 | TS hook suite + changesets + tests |
| `cam-douglas/hermes-playground` | 7 | a `.mjs` function hook + captured run data |
| `noopz/commonplace` | 5 | `hooks/register.ts` + `hooks/hooks.json` — a real mod |
| `ray-amjad/awesome-claude-code-function-hooks` | 4 | **a dedicated awesome-list, with shipped example plugins** |
| `mahuebel/segmem` | 4 | `hooks/hooks.ts` + a design doc |
| `dodi-hq/dodi-skills` | 4 | `dodi-dev/hooks/hooks.js` + specs |
| `wandercom/kindex` | 3 | docs + a Python installer |
| `pleaseai/honmoon` | 3 | `packages/claude-plugin/hooks/honmoon.ts` |
| `djnsty23/claude-auto-dev` | 3 | `plugins/autodev-core/hooks/fn/autodev-fn.mjs` + a validator |
| `davila7/claude-code-templates` | 3 | the aitmpl.com blog source (already known via the site) |
| `yonatangross/orchestkit` | 2 | `scripts/validate-fn-hooks-canary.sh` |
| `phate45/claude-patching` | 2 | **`patches/2.1.260/env-vars.json` — a versioned env-var diff** |
| `amitray007/claude-code-schema` | 2 | `output/environment.catalog.json` — an env-var catalog |
| 9 more, 1 hit each | 9 | `xkazm04/ai-registry`, `SApplefeld/claude-kit`, `renchris/claude-infrastructure`, `n0rvyn/indie-toolkit`, `JoshuaOliphant/claude-plugins`, `gillisandrew/dotfiles`, `cwschroeder/buzz-agent-comms`, `conorluddy/tokenblast.cc`, `bsamiee/Rasm` |

### Adjacent searches — what each produced

Reported honestly including the failures, because two of them teach how this index behaves.

| Query | `total` | Verdict |
|---|---:|---|
| `plugin_function_hooks` | **0**, incomplete=false | **An informative zero.** This is one of the internal symbol strings the prior report recovered from the 2.1.251 binary (`plugin_function_hooks_worker/_load/_register_tool`). It appears in **no public source on GitHub** — the string exists only inside the compiled bundle. Control-armed by arms A/B above in the same minute. |
| `plugin-types` | 288,256 | **Useless — tokenizer noise.** GitHub's legacy code index splits on `-`, so this matched every `eslint-plugin-types`, `fusion-plugin-types`, etc. A hyphenated term is not a search term here. |
| `sec-default` | 3,768 | Same failure: matched `dns-security-profile`, `docker-sec`, FreeRADIUS dictionaries. Bare hyphenated names cannot be searched literally on this API. |
| `filename:hooks.json modules register` | 69 | **The productive shape.** A function-hook plugin's fingerprint is `hooks/hooks.json` containing `{"modules": [...]}`. Mostly noise (`async_hooks.json` from vendored Node docs) but it surfaced the three Anthropic built-ins plus **four third-party plugins the literal query missed**. |
| `filename:register.ts claude next tier` | 15 | Surfaced `anthropics/claude-code` `mods/sec-default/hooks/register.ts` and `noopz/commonplace` `hooks/register.ts`. |
| `"claude-code" "next.to" tier append` | 78 | Mostly noise (`next.to` matched React/Next.js code), but it surfaced two files that matter — see below. |

**Two lessons about the tool, not the topic**, worth carrying into Job 2: a hyphenated or dotted token cannot be searched literally on `/search/code`, and quoting does not fix it; and `filename:`/`path:` qualifiers are what make a query discriminating. A design that hands users a raw query string and no qualifier support will mostly return noise.

### 🔴 The single most valuable find — the `/plugin-types` declaration file

`asgeirtj/system_prompts_leaks` → `Anthropic/claude-code/skills/plugin-authoring/reference/claude-code.d.ts`.

The prior report listed this as an open gap, verbatim: *"The `/plugin-types` declarations mentioned in `mods/README.md` … were NOT located or fetched this session — flagged as a lead for a follow-up, not as 'does not exist.'"* **It exists, and GitHub search found it.** It is the authoritative TypeScript surface — the full event catalog and `$` interface — which is exactly what closes the prior report's "full event catalog: only what three mods happened to touch" limitation.

**Provenance, stated plainly before anything is quoted from it.** `asgeirtj/system_prompts_leaks` is a third-party scrape repo, not Anthropic's. I checked for an official copy and there is none: `gh api repos/anthropics/claude-code/contents/skills` → **HTTP 404**; the public `mods/` tree today is still exactly `README.md`, `diff/`, `sec-default/`, `telemetry/`. So this file is *unofficial hosting of official generated output*. What makes it trustworthy is that it is **self-identifying and locally reproducible**: its first line reads `// Written by Claude Code 2.1.267.` — the exact version `claude --version` reports in this session — and the file itself says it is written by `/plugin-types` and should be regenerated rather than edited. **Anyone here can regenerate it locally and diff, which is the control arm I could not run under a read-only brief.** Treat it as high-confidence-but-reproducible-on-demand, not as primary.

Permalink, pinned to a SHA so it cannot rot: `https://github.com/asgeirtj/system_prompts_leaks/blob/f475e8b2b11ca7540a37234a451e9f085471bd94/Anthropic/claude-code/skills/plugin-authoring/reference/claude-code.d.ts` (blob sha `36aec298dd76c950b774045707427e26c46bd799`, 302,096 bytes, 7,966 lines).

## What contradicts the existing report

Three findings from the declaration file correct or close claims in `function-hooks-research.md`. All three are quoted from the file both ways.

### 1. 🔴 There are FIVE tiers, not three — and the correction changes the enforcement story

The prior report says, from `sec-default/README.md`: *"plugins sit in three tiers — `prepend` … `user` … `append`"*, and lists as unverified *"Whether `next.to(e, tier)` can target arbitrary tiers or only `"append"` / the two named tiers observed (`user`, `prepend`, `append` were the only three tier names seen)."*

The declaration file states it outright (`claude-code.d.ts:6110`):

```ts
const TIERS: readonly ["prepend", "user", "append", "builtin", "core"];
```

with the doc comment (`:6093-6099`): *"One of the chain's five tiers (TIERS), outermost first… `prepend` and `append` are the managed plugins an administrator lists, `user` everything a person installs, `builtin` the plugins bundled in the binary, `core` the engine's innermost link."*

**Settled: five tiers.** The prior report was not wrong about what it read — `sec-default/README.md` genuinely describes only the three tiers a *plugin author* can be seated in. `builtin` and `core` are below all plugins and are not seatable, which is why a plugin-facing README omits them. Both documents are accurate about different scopes; the d.ts is the wider one.

### 2. 🔴 `next.to()` can target three tiers, and is *structurally forbidden* from targeting two

`claude-code.d.ts:6018`, with its comment at `:6014-6017`:

```ts
/**
 * A tier `next.to(e, tier)` may name: one a floor can reach past a tier of
 * less authority to, so never `prepend` or `user`, which nothing skips to.
 */
export type TargetTier = Exclude<Tier, 'prepend' | 'user'>;
```

So `next.to()` may name `append`, `builtin`, or `core` — never `prepend` or `user`. **This is the type system enforcing the authority direction**: you can only ever skip *inward*, toward the engine, never outward toward a higher-authority tier. The prior report's central enforcement claim — that a `prepend`-tier hook calling `next.to(e, "append")` makes user-tier hooks unreachable — is **confirmed, and is now shown to be a designed invariant rather than an emergent trick**. It also answers the open question directly: not arbitrary tiers, and not only `"append"`.

### 3. `classic.*` — the prior report's inference was half right, and the half that was wrong matters

The prior report inferred from binary strings: *"`classic.*` … is very likely a WILDCARD pattern over these literal classic names (`PreToolUse`, `PostToolUse`, etc.), not a separately-named bridge event."*

The declarations show the names ARE prefixed (`:678-681`):

```ts
/**
 * The name of a classic hook event as a function-hooks event: the settings
 * hook's own name under `classic` (`classic.Stop`, `classic.PreToolUse`).
 */
export type ClassicEventName = `classic.${ClassicHookEvent}`;
```

and `:2649-2650` defines the wildcard separately: *"Every event (`*`), or every event under a namespace (`classic.*`: each one whose name starts with `classic.`)."*

**Settled: both halves exist and they are different things.** `classic.PreToolUse` is a real, distinctly-named event (the classic name *namespaced*, not the bare literal `"PreToolUse"` the binary strings suggested); `classic.*` is a namespace wildcard over them. The prior report's reading of the compiled string table — that `"PreToolUse"` appears in the same dispatch as `"tool.call"` — is not contradicted, but the *event identifier a hook registers* is `classic.PreToolUse`, not `PreToolUse`. **A hook written from the prior report's inference would register the wrong name and silently never fire.**

One further detail the same block gives, load-bearing for this repo: `:689` and `:823` — *"`classic.PreToolUse` alone differs: its `e` is ToolCallEnvelope"* and *"`classic.PreToolUse` keeps its `allow` / `ask` / `deny` result"*. The one classic event this repo's entire guard stack depends on is the one special-cased to share `tool.call`'s envelope.

### The event catalog the prior report could not obtain

66 distinct dotted names are declared as properties in the file. They span both engine events and `$` capability calls — the file's own model is that a call on `$` **is** an event other hooks can intercept, so the two sets deliberately overlap:

`agent.list` `agent.offer` `agent.spawn` `attribution.text` `audio.play` `audio.speak` `command.describe` `command.list` `command.register` `command.run` `engine.create` `env.get` `env.set` `fs.ancestors` `fs.exists` `fs.list` `fs.read` `fs.stat` `fs.write` `http.fetch` `mcp.call` `model.classify` `model.complete` `model.fork` `process.run` `prompt.context` `prompt.section` `prompt.submit` `session.compact` `session.cwd` `session.id` `session.messages` `session.model` `session.repo` `session.receive` `session.start` `session.surface` `session.turnCount` `session.usage` `settings.read` `skill.prompt` `store.delete` `store.get` `store.keys` `store.set` `tool.call` `tool.describe` `tool.list` `tool.register` `turn.abort` `turn.complete` `turn.start` `turn.step` `ui.close` `ui.input` `ui.invalidate` `ui.log` `ui.message` `ui.notice` `ui.open` `ui.press` `ui.render` `ui.resolve` `ui.select` `ui.status` `ui.toast`

**Bound on this figure, stated because it is a bound:** 66 is what a property-key grep over the declarations returns, not a number the file states about itself. The prior report relayed claudefa.st's *"20 engine events and 15 `$` nouns"*; those are plainly counting different things (namespaces, or engine-only events). Do not treat 66 as "66 engine events" — it is the size of the dotted-name surface, events and capabilities together, plus the `classic.*` family on top.

## The other indexes — and why searching only code would have missed most of this

**Repositories index** (`search/repositories`, `q='claude function hooks'` → 20; `q='function-hooks claude in:name,description'` → 5). Five repos exist whose *entire purpose* is function hooks:

| Repo | ★ | Pushed | What it is |
|---|---:|---|---|
| `Monte9/claude-function-hooks` | 1 | 2026-09-03 | *"A reference implementation of the Function Hooks algebra proposed for Claude Code"* — and see its issue tracker below, which is the best critique of the semantics anywhere |
| `cvuijst/cc-function-hooks-poc` | 1 | 2026-09-05 | POC explicitly citing `anthropics/claude-code#91870` |
| `productowner-ro/claude-function-hooks` | 0 | 2026-09-05 | reference for JS/TS functions wrapping the engine |
| `scriptease/claude-code-redact-plugin` | 0 | 2026-09-05 | *"An example plugin project using the new functional hooks"* |
| `ray-amjad/awesome-claude-code-function-hooks` | 1 | 2026-09-05 | an awesome-list with shipped plugins (`secret-redactor`, `vercel-deploy-status`) |

🔴 **Four of those five never appeared in the code index at all.** Only `ray-amjad/...` overlapped. That is the concrete, measured case for the brief's instruction to search more than one index — a code-only search would have found 20% of the dedicated projects.

**Issues index** (`search/issues`): `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` → **29**; `repo:anthropics/claude-code function hooks` → 1,030 (mostly the tokenizer matching "hooks" broadly, but the top results are genuine).

### 🔴 The most useful single find for THIS repo: `anthropics/claude-code#92469`

*"/plugin-types omits the op events session.authorize and flag.value that the hooks load line lists (2.1.263)"* — open, author `bsamiee`, `author_association: NONE`, created 2026-09-06.

Two reasons it matters more than anything else found:

1. **It bounds the declaration file I just quoted.** The generated `claude-code.d.ts` is *not* a complete event catalog — it demonstrably omits `session.authorize` and `flag.value`, both of which the runtime carries. **My 66-name catalog above inherits that omission.** Anyone treating the d.ts as exhaustive will conclude a real event does not exist.
2. **It contains a verbatim runtime load line**, which is a *better* source than the declarations and comes from an observable this repo can reproduce: `~/.claude/debug/<session>.txt` under `claude --debug`, printing `hooks module <name> loaded (worker, environment 1); events: tool.call,ui.render,…` — **54 events, named by the engine itself at load time.**

🔴 **That load line answers the prior report's open question directly.** It listed as unverified: *"Whether there is any CLI-observable proof line … that function hooks are active, beyond a mod's own visible side effect."* **There is one**: `claude --debug` writes `hooks module <name> loaded (worker, environment 1); events: …` to the session debug log. That is a positive, greppable, non-destructive proof-of-enablement signal — cheaper and more direct than the `/plugin-types`-writes-files candidate the prior report proposed from claudefa.st.

One discrepancy I did NOT settle: the runtime load line spells the filesystem ops `fs.readFile`, `fs.writeFile`, `fs.listDir`, while the 2.1.267 declarations I grepped spell them `fs.read`, `fs.write`, `fs.list`. That is either a rename between 2.1.263 and 2.1.267, or a deliberate split between the op-event name and the `$` method name. **Unresolved — flagged, not guessed.**

### `anthropics/claude-code#92533` — a real, bisected isolation bug that would bite this repo specifically

*"Any function-hook `tool.call` on Bash breaks Agent isolation: 'worktree' — every Bash call refused"*, open, author `navidemad`. Registering **any** `tool.call` hook on `Bash` — *"even a pure passthrough `next(e)` with no logic"* — causes every Bash call in a subagent spawned with `Agent(isolation: "worktree")` to be refused with *"The working-directory isolation context for this agent was lost"*. Read/Edit and MCP keep working; only Bash breaks. The reporter bisected it headless with `claude -p --output-format json` and observed 6 failed retries.

**Why this one is load-bearing here and not just interesting:** this repo's entire guard stack (`kb_setup.hook_guard`, `check_first`, `graph_first`, `absent_binary`, `secret_guard`) is a `PreToolUse` matcher on `Bash|Grep`. The obvious migration — reimplement those five guards as a function-hook `tool.call` hook on Bash — lands **exactly** on this bug, and this repo runs worktree-isolated subagents routinely. A migration attempt would look like the guards broke, not like a platform bug.

Corroborating artifact found independently in the code index: `cam-douglas/hermes-playground` carries `projects/gland/data/92533.json` plus `passthrough-ok.json` and `stripped.json` — captured reproduction data for this exact issue number, alongside a working hook at `projects/gland/hook/gland.mjs`.

### Other issues worth keeping

- `anthropics/claude-code#92440` — `agent.offer` doc comment and example disagree with the runtime (`offered` vs the real field). A doc-vs-runtime defect in the same generated surface.
- `anthropics/claude-code#92675` — *"Plugin-native PreToolUse hooks (auto-discovered via hooks/hooks.json)"*.
- `Monte9/claude-function-hooks#1/#2/#3` — **the sharpest semantic critique found anywhere**, and all three cut against a naive reading of the algebra: *"Matchers bind once at dispatch entry, and `e` is passed by reference"* (#1); *"The §6.4 guard covers one synchronous tick, and `next.origin` is called…"* (#2); *"`deny` has no engine meaning, and `next()` twice runs the side effect…"* (#3). **#3 is directly relevant to the prior report's enforcement thesis** — it asserts `deny` is not an engine-level primitive at all, which if true qualifies the prior report's *"returning `{ deny: <reason> }` … DENIES the event outright."* I did not adjudicate this; it is a third-party assertion about an unreleased API and belongs in front of whoever designs the migration.
- `lossless-claude/lcm#376`/`#377` — *"function-hooks module replaces PostToolUse, UserPromptSubmit…"*, both closed/merged. A real project that has **already completed** the classic-to-function-hooks migration this repo would be contemplating.
- `pleaseai/honmoon#90` — *"add Claude Code function-hooks module with fail-c[losed]…"* — closed. Fail-closed design in third-party code.
- `yonatangross/orchestkit#3993` — *"scope the modules-key ban to shipped hooks.json"* — a project that had to write a rule about the `modules` key.

### Remaining adjacent queries, for completeness

| Query | `total` | Verdict |
|---|---:|---|
| `claude.mods` | **0**, incomplete=false | Real zero. "Claude Mods" is the announced product NAME; it is not a code identifier anywhere public. |
| `path:.claude/mods` | 5 | **All five are a false positive** — `nikolaj-lat/World-Puppeteer`, an FFXIV roleplay project using `.claude/mods/` for character-instruction JSON. **`.claude/mods/` is NOT the function-hook convention.** The real on-disk shape is a plugin directory: `.claude-plugin/plugin.json` + `hooks/hooks.json` + the TS module. |
| `"tool.call" "prompt.submit" "agent.spawn"` | 95 | Mostly Moonshot/Kimi harness forks with unrelated event buses of their own. It did re-surface `anthropics/claude-code` `mods/sec-default/README.md` and the `claude-code.d.ts`, so it discriminated — it just has a namespace collision with every other agent framework's event names. |
| discussions: `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` | **0** | Real zero — control arm `claude code hooks` returned **2,069** discussions in the same minute. No GitHub Discussion anywhere mentions the flag. |

## 🔴 The single most useful example found: `ray-amjad/awesome-claude-code-function-hooks`

Pinned: `https://github.com/ray-amjad/awesome-claude-code-function-hooks/tree/b559942ec757e1f28b6a901ce1be79a23aa52c7d` — MIT, 1★, pushed 2026-09-05.

It is not a link list. It is **a working plugin marketplace** (`.claude-plugin/marketplace.json`) shipping two complete, tested function-hook plugins:

```
plugins/secret-redactor/.claude-plugin/plugin.json
plugins/secret-redactor/hooks/hooks.json          -> {"modules": ["./redact.ts"]}
plugins/secret-redactor/hooks/redact.ts           366 lines
plugins/secret-redactor/test/detect.test.mts
plugins/secret-redactor/tsconfig.json
plugins/vercel-deploy-status/hooks/deploy-status.tsx   (JSX — a UI hook)
plugins/vercel-deploy-status/hooks/queue.ts
```

**Why this one over the other 21 repos:** it is the only find that is simultaneously (a) complete and runnable, (b) tested, (c) MIT-licensed so it can actually be borrowed from, (d) a *marketplace* so it demonstrates distribution, and (e) **a direct functional analogue of something this repo already owns** — `secret-redactor` is `kb_setup.secret_guard`'s job done at the function-hook layer.

The shape of `redact.ts` (`:318-361`), which is the part worth stealing:

```ts
export const register: Register = (on, options) => {
  on('prompt.submit', async ($, e, next) => {
    …
    $.ui.toast(`secret-redactor: hid ${hidden - before} value(s) from the prompt`)
    return next({ ...e, text })          // mutate the event, then continue
  })
  on('tool.call', async ($, e, next) => {
    const r = await next(input)          // redact inbound, await, then …
    …                                    // … restore on the way back out
    if (cfg.notify) $.ui.notice(e.tool_use_id, `secret-redactor: hid …`)
  })
  on('prompt.context', async ($, e, next) => { const r = await next(e); … })
}
```

**That `tool.call` body is the thing this repo's guards structurally cannot do today.** `kb_setup.secret_guard` is a `PreToolUse` command hook: it sees the call, returns allow/deny, and is finished. A function hook wraps `next()`, so it can transform the request going in *and* the result coming back — bidirectional. This repo's secret invariant is currently "refuse the command"; the function-hook equivalent could be "let it run, redact the output", which is a strictly different and in some cases better answer.

Two further facts from its README worth carrying, both independently useful:

1. **It documents user-scope enablement** (`~/.claude/settings.json` `env` block) as the recommended path. **This repo cannot follow that** — `do-not.md` #11 forbids writing `~/.claude`. The per-run form it also gives, `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude`, is the only one compatible with this repo's invariants. The prior report's guess — that `.claude/settings.json`'s project `env` block would work — is neither confirmed nor refuted by this README, which recommends *user* scope without saying project scope fails.
2. 🔴 **"The type declarations are not in git. Claude Code writes them, and every release rewrites them, so a checked-in copy goes stale and lies to you."** This is an independent third party reaching the same conclusion my provenance caveat reached about the leaked `claude-code.d.ts`: **regenerate with `/plugin-types`, never cite a checked-in copy.** It also means the file I quoted is exactly the artifact its own ecosystem says not to trust from a repo — which is why every claim I drew from it is stated as reproducible-on-demand.

### Other examples worth keeping, by category

**Complete working hooks (code you can read):**

| Repo | File | Note |
|---|---|---|
| `noopz/commonplace` | `hooks/register.ts`, `hooks/hooks.json`, `scripts/lib/module-gate.ts` + its test | 3★, pushed 2026-09-05. Has a **module gate** with a test — a project that built a guard around the loader. |
| `bsamiee/Rasm` | `.claude/plugins/function-hooks/hooks/hooks.json`, `.claude/settings.json` | pushed **2026-09-10** (today). Author `bsamiee` is the reporter of `#92469` — a practitioner deep enough to bisect a declarations-vs-runtime mismatch. |
| `mahuebel/segmem` | `hooks/hooks.ts`, `docs/design-function-hooks.md` | design doc beside the implementation |
| `pleaseai/honmoon` | `packages/claude-plugin/hooks/honmoon.ts` | shipped via PR #90, "fail-closed" in the title |
| `djnsty23/claude-auto-dev` | `plugins/autodev-core/hooks/fn/autodev-fn.mjs`, `tooling/validate.js`, `docs/function-hooks/README.md` | `.mjs` rather than TS, plus a validator |
| `dodi-hq/dodi-skills` | `dodi-dev/hooks/hooks.js`, `docs/specs/2026-09-05-no-reentry-rule-design.md` | ships a **no-reentry rule** spec — directly relevant to guard design |
| `cam-douglas/hermes-playground` | `projects/gland/hook/gland.mjs` + `data/92533.json`, `passthrough-ok.json`, `stripped.json` | **captured reproduction data for issue #92533** |
| `jfrog/claude-plugin` | `hooks/hooks.json` | a **corporate vendor** shipping the shape |
| `lossless-claude/lcm` | `hooks/lcm-hooks.ts`, `src/hooks/session-claim.ts`, 6 test files under `test/hooks/` | the **most mature** — a completed classic→function-hooks migration with a real test suite |

**Reference implementations / critique:** `Monte9/claude-function-hooks` (`dbb6219c246d9f26dabee535535b565e0f2b07de`) — "reference implementation of the Function Hooks algebra", and its three open issues are the sharpest available critique of the semantics.

**Version archaeology (relevant to the prior report's unresolved 2.1.266 question):** `phate45/claude-patching` ships `patches/2.1.260/env-vars.json` and `patches/2.1.260/env-diff-2.1.246.json` — a *versioned env-var diff series*. `amitray007/claude-code-schema` ships `output/environment.catalog.json`. **Together these are the artifact that could settle exactly which release introduced the `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` string** — the question the prior report left open between "renamed in 2.1.266" and "constructed dynamically". I did not run that diff; it is a concrete, cheap next step and I am naming it rather than claiming it.

### 🔴 Version archaeology — the prior report's open question, SETTLED and the third-party claim REFUTED

The prior report could not resolve aitmpl.com's claim that *"The feature exists in Claude Code binary version **2.1.266**, verified through binary analysis"*, and left two explanations live.

`phate45/claude-patching` publishes a per-version scan of every `CLAUDE_CODE_*`/`ANTHROPIC_*` string in the shipped bundle, plus machine-readable diffs. Its `patches/` tree holds 77 versions; the two straddling the question are `2.1.246` and `2.1.260`.

```
$ jq -c 'select(.name=="CLAUDE_CODE_ENABLE_FUNCTION_HOOKS")
        | {change, occurrences, previousOccurrences, forms}' env-diff-2.1.246.json
{"change":"added","occurrences":5,"previousOccurrences":null,
 "forms":["other","property","string"]}
```

**Control arm, same command shape, same two files:** `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` appears **0** times in the 2.1.246 scan and 5 times in the 2.1.260 scan, while `CLAUDE_CODE_ENABLE_TELEMETRY` — a flag known present in both — appears **1 and 1**. So the scanner discriminates, and the zero on 2.1.246 is an absence, not a broken probe.

**Settled: the literal env-var string was introduced in `(2.1.246, 2.1.260]`, and it is a plain `string` form in the bundle (not dynamically constructed).**

Two consequences:

1. **aitmpl.com's "2.1.266" is wrong** — the string was already in 2.1.260, six versions earlier. The prior report was right to distrust it and right that the feature predates the claim; this narrows *by how much* with an independent, control-armed source.
2. **It also closes the prior report's own either/or.** That report offered *"(a) renamed later, possibly exactly 2.1.266 … or (b) the check is constructed dynamically and evades a plain `strings` scan."* **(b) is refuted** — `forms: ["string"]` means it IS a plain literal, so a `strings` scan that misses it in 2.1.251 means it genuinely was not there yet. Combining that report's 2.1.251 finding with this one narrows the window further, to **`(2.1.251, 2.1.260]`** — tighter than either source alone. That combination inherits the prior report's 2.1.251 scan, which I did not re-run; the `(2.1.246, 2.1.260]` bound is what I measured myself today.

---

# Job 2 — the reusable capability

> *"we need to start actually using github as a source of information on how to find examples"* — Ray, today. A standing instruction, so it becomes **skill → mise task → `kb_setup` module**, per `zero-bash-logic.md` and `mise-tasks-only.md`.

## Does `kb-research-codesearch` already cover it? — **No. It covers about a quarter, and the quarter it covers is the valuable one.**

I read `python/src/kb_setup/research/codesearch.py` (592 lines) in full before proposing anything, per `use-tool-builtins.md`. The honest answer is that it is a **good module aimed at a different target**.

**It does not search GitHub.** Its backend is grep.app's unauthenticated MCP endpoint (`https://mcp.grep.app`, one stateless JSON-RPC `tools/call` to a tool named `searchGitHub`) over `httpx2`. The name is about the *subject* (GitHub-hosted code), not the *API*.

| Capability today's research needed | `codesearch.py` | Evidence |
|---|---|---|
| Search GitHub's own indexes | ✗ — grep.app only | `_ENDPOINT = "https://mcp.grep.app"` |
| More than one result | ✗ — **at most one, by design** | premise `G1`, verified 7/7; `_HIT_RE` anchored `\A`; a second hit is silently absorbed as snippet text |
| Repos / issues / discussions indexes | ✗ — code only | today: 4 of 5 dedicated repos, and both top issues, were invisible to code search |
| Qualifier support (`filename:`, `path:`, `repo:`) | ✗ — `query`/`repo`/`language` only | and qualifiers are what make a query discriminating (finding 4 below) |
| Pagination | ✗ | no `page`/`per_page` |
| Rate-limit vs zero | partial | transport/HTTP failures → `Rc.NOT_RUN`, correctly distinct from zero — but there is no rate-limit budget model because grep.app is unauthenticated |
| `incomplete_results` (a timed-out scan) | ✗ — no such concept upstream | GitHub's third outcome, unmodelled |
| SHA-pinned permalinks | ✗ | `Hit.url` is passed through; `Hit.date` is documented as observation time, not commit time |
| Corpus feed (`sources/REGISTRY.md`) | ✗ | prints/writes an `AdapterRecord` and stops |
| **Control-armed null** | ✅ **and it is excellent** | `_null_record` re-runs a known-good query *keeping the caller's own filters*, records an `Arm{command, result, discriminates}`; `validate()` refuses a record that is neither hits nor a corroborated null |
| **A refusing contract** | ✅ | `validate()` raises unless exactly one outcome is present; an unparsable body is `Rc.NOT_RUN`, never a plausible empty success |
| **Hermetic test seam** | ✅ | `httpx2.MockTransport` |

**So: extend the CONTRACT, not the module.** The `AdapterRecord` shape, the `Arm`/`Null` control-arm machinery, the `Rc.NOT_RUN`-vs-zero discipline and the `MockTransport` seam are exactly right and should be reused verbatim. What cannot be retrofitted is `G1` — "one query, one hit" is load-bearing inside `_parse_hits` *and* inside `validate()`, and it is irreconcilable with 100-per-page pagination across four indexes. Forcing both into one module produces a module whose invariants contradict each other.

## What I measured about GitHub's API today, that any spec must handle

These are not design opinions; each is a measurement from this session.

1. **Four separate rate budgets, and the relevant one is tiny.** `code_search` **10/min**; `search` (repos/issues/users) **30/min**; `core` 5,000/hr; GraphQL separate. Measured via `gh api rate_limit`. A naive fan-out over a dozen queries exhausts code search in one turn.
2. **`incomplete_results: true` is a third outcome.** GitHub sets it when the scan timed out. It is neither "hits" nor "none", and reporting such a result as complete is a false negative with a green face.
3. **Different indexes genuinely disagree** — measured, not assumed: code → 22 repos; repositories → 5 dedicated projects of which **4 appeared in no code result**; issues → the two single most valuable artifacts of the day; discussions → a control-armed real zero.
4. **The legacy code tokenizer splits on `-` and `.`, and quoting does not fix it.** `plugin-types` → 288,256 junk; `sec-default` → 3,768 junk. `filename:`/`path:` qualifiers are the fix. **A tool that accepts a bare query string and no qualifiers will mostly return noise** — this is the single most important usability finding for the spec.
5. **`html_url` is branch-pinned and rots.** The SHA is one extra call (`repos/{r}/commits` → `.[0].sha`), and each content item already carries its own blob `sha`. I pinned every permalink in this report by hand; a tool must do it or its examples decay.
6. **Code search requires auth** (unauthenticated → 401), so an unauthenticated run degrades to a silent "no results" unless handled explicitly.
7. **`gh search code` must never be used** — it returns `[]` on failure, making a rate limit indistinguishable from a zero. This repo already knows this (memory `gh-search-returns-empty-not-an-error`); it held again today and is why every query above went through `gh api -X GET`.

---

## Correction to my own earlier section of this report

Above, under "Other issues worth keeping", I wrote that `Monte9/claude-function-hooks#3` *"asserts `deny` is not an engine-level primitive at all, which if true qualifies the prior report's [claim]"*. **I read the title and not the body. That is wrong, and it is wrong in the direction that would have misled a design pass.**

Reading the body: the issue's evidence is `grep -rn deny src/` returning empty — **that is `Monte9`'s OWN `src/`**, i.e. the reference implementation, not Claude Code. The issue is a fidelity complaint against a third-party reimplementation plus a design argument (*"Koa's whole appeal is that the engine knows one thing: was `next` called. Adding `deny` to the engine grows it"*), not a finding about Anthropic's engine. **It says nothing about whether `{deny: …}` works in real Claude Code**, and the prior report's claim — sourced from `sec-default`'s shipped code, which really does return `{ deny: TOOL_REGISTER_REFUSAL }` — stands unqualified by it.

What the issue IS worth reading for is its failure catalogue, which applies to any middleware chain of this shape and is good design input: `{deny: ""}` / `{deny: 0}` / `{deny: null}` block while `if (r.deny)` reads as allowed; a hook that calls `next(e)` **and** returns `{deny}` runs the real action while every visible signal says blocked; `next()` called twice runs the bottom implementation twice. Its proposed fix — *"make `next` a single-use token the engine tracks per hook"* — is a real hardening idea.

**All three `Monte9` issues are therefore about a reference implementation, not the platform.** Downgrade them from "critique of the semantics" to "critique of one reimplementation, with transferable failure modes." My earlier paragraph is superseded by this one.

## The closest available precedent: a migration that already happened

`lossless-claude/lcm#377` (**closed, merged**) — *"function-hooks module replaces PostToolUse, UserPromptSubmit and Stop"*. This is the single most transferable artifact for anyone here contemplating the same move, because it is a completed classic→function-hooks migration in a real project with a test suite.

Its mapping, verbatim from the PR body:

- **`tool.call` replaces `PostToolUse` + `PostToolUseFailure`** — one after-placement hook awaits the tool and reads `isError` on the result.
- **`prompt.submit` + `prompt.section` replace `UserPromptSubmit`.**
- **`turn.complete` replaces the `Stop` snapshot.**

Three details worth more than the mapping:

1. **Coexistence is explicit and event-scoped:** *"While the module is loaded it owns four events and the matching command hooks go silent; without the flag nothing changes."* So classic and function hooks do not double-fire — the module *takes ownership* of its events. That is the answer to "will my existing `PreToolUse` guards run twice during a migration": no, but also they stop running for the events the module claims, which is a cutover, not a parallel run.
2. 🔴 **The hooks module has no Node and no SQLite**, so lcm had to keep a daemon and POST to it: *"Chosen over a rewrite of the extractors because the module runs without Node or SQLite: the daemon has to write."* The declaration file says the same thing (`claude-code.d.ts:13-15`: *"A hooks module runs in an environment of its own: no DOM, no Node."*). **This is decisive for this repo**: `kb_setup`'s guards are Python invoked via `uv run`. A function hook **cannot** call them in-process — it would need a subprocess capability (`$.process.run`) or a daemon, which gives back much of the cost the classic hook already pays. That is a real argument against migrating this repo's guard stack, and it comes from a project that hit it in practice.
3. It moved a ~1 KB instruction *"into the system prompt's `memory` section once per session instead of riding on every prompt"* — a token-cost win that is only available at the function-hook layer.

## The specification — codex lane verdict (`gpt-5.6-sol`, `xhigh`), relayed verbatim

Run via `mise run kb-codex -- --model gpt-5.6-sol --effort xhigh`. **The first attempt failed** — `ERROR: Selected model is at capacity` after 116,510 tokens — and was retried once, which succeeded. Recording the failure because a lane's own success is part of its evidence.

> **B — add `research/ghsearch.py` as a sibling and share only backend-neutral helpers. The deciding risk is silent false completeness: GitHub's paginated, multi-index outcomes cannot safely coexist with `codesearch.py`'s load-bearing one-hit invariant.**
>
> ### Specification
>
> - **Capability chain:** synchronized `github-examples` skill → `mise run kb-research-ghsearch` → `uv run kb-setup research-ghsearch`; add `ghsearch` to `aggregated-research`. Leave `codesearch.py` semantically unchanged. Extract only timestamping, secret-free command rendering, report writing, and arm validation into `research/common.py`.
>
> - **Inputs:**
>
>   ```text
>   mise run kb-research-ghsearch -- \
>     --query code='filename:hooks.json modules register' \
>     --query repositories='modules register in:name,description' \
>     --query issues='"modules register" is:issue' \
>     --query discussions='"modules register"' \
>     [--limit 100] [--out PATH] [--report PATH] \
>     [--register] [--manifest OWNER/REPO]
>   ```
>
>   `--query INDEX=QUERY` is repeatable; index is `code|repositories|issues|discussions`. The standing skill supplies all four unless explicitly narrowed. Queries — including `filename:`, `path:`, `repo:`, and `language:` — are preserved verbatim and URL-encoded, never retokenized. GitHub supports query qualifiers and up to 100 code results per page; discussions use GraphQL `search(type: DISCUSSION)`.
>
> - **New generated contract:** add `schemas/github-search-record.schema.json`; do not stretch the current `AdapterRecord` schema. It must contain all four probe entries, including omitted indexes as `not_requested`, with:
>
>   ```text
>   status = hits | corroborated_zero | bounded | incomplete |
>            rate_limited | auth_failed | not_run | not_requested
>   total_count, fetched_count, pages_fetched, incomplete_results,
>   rate_limit{resource,remaining,reset,retry_after}, control_arm
>   ```
>
>   Overall rc is `0` only when every requested probe is `hits`, `bounded`, or `corroborated_zero`. `incomplete_results:true`, GraphQL partial data/errors, control failure, auth failure, or mid-pagination failure returns `Rc.NOT_RUN`; partial hits remain quarantined evidence.
>
> - **Reports:** every attempt writes atomic JSON plus Markdown under `.agent/kb/reports/ghsearch/<run-id>.{json,md}`, including failures. `--out` and `--report` override those paths. `--publish` is permitted only for a successful record and writes `docs/research/reports/<date>-<slug>.md`. Markdown must end with the required `## GitHub repos touched` section from `research-repo-enumeration.md`.
>
> - **Authentication and test seam:** use `httpx2` directly for REST and GraphQL. Obtain the token once through an injected `TokenProvider`; production runs `gh auth token`, tests provide a fake. Never use `gh api` as the transport and never serialize/log the token. Thus API behavior remains testable with `httpx2.MockTransport`, while `gh` retains credential ownership. Empty provider output or `401` is `auth_failed`; `403/429` plus rate headers/message is `rate_limited`, never zero.
>
> - **Control arm:** maintain one versioned known-positive query and expected stable identity per index. Run it through the same token, endpoint, decoder, and pagination path. A zero is valid only when its primary response is schema-valid, complete, `total_count=0`, and that index's control contains the expected identity. Otherwise refuse with `Rc.NOT_RUN`; never return a bare empty list.
>
> - **Permalinks:** for every repository, resolve its default-branch commit once. For each code hit, resolve the response ref, fetch the path at that commit, verify its returned blob SHA equals the search item's blob SHA, then emit `https://github.com/OWNER/REPO/blob/<commit-sha>/<path>`. Any mismatch is `pin_failed`/`Rc.NOT_RUN`. Issue/discussion records preserve stable URL, node ID/number, `updated_at`, and an observed snapshot.
>
> - **Corpus:** `--register` deduplicates canonical repo URLs and appends missing successful-hit repos to `sources/REGISTRY.md` as `T2/pending`, citing the report. `--manifest OWNER/REPO` delegates to existing `manifest.add()` (`python/src/kb_setup/manifest.py:463`), extended to accept and validate the already-recorded commit SHA — never re-resolve moving HEAD. Selected issue/discussion bodies should be promoted as provenance-bearing Markdown under `sources/media/` and passed through the existing Graphify extraction path; `ghsearch` should not invent graph chunks itself.
>
> Evidence limitation: both sanctioned graph query and recall failed before execution because mise could not create its temporary file (`tool purgatory cleanup failed: Operation not permitted`); direct `graphify query` was correctly blocked by the repository hook. Firecrawl was also DNS-blocked, so current GitHub contracts were verified through official docs via the web fallback.

### My assessment of that verdict, where I can check it against what I measured

**The verdict is well-founded and I agree with B.** Its deciding risk — *silent false completeness* — is the same failure this repo already has a rule for (`probes-need-a-control-arm.md`), and my measurements support it independently: `G1` is asserted in `_parse_hits`'s docstring *and* enforced in `validate()`, so pagination cannot be added without rewriting both.

Points where its spec is confirmed by something I ran today, rather than reasoned:

- The `--query INDEX=QUERY` shape with **verbatim, un-retokenized** qualifiers is the right call — finding 4 (the `-`/`.` tokenizer split) is exactly why a bare query string is inadequate, and `filename:hooks.json modules register` is the query that actually found the third-party plugins.
- The four statuses `incomplete | rate_limited | auth_failed | not_requested` map onto real outcomes I hit or could have hit: `incomplete_results` is a real field I read on every call; `code_search` at 10/min is genuinely easy to exhaust.
- `--register` writing `T2/pending` rows matches `sources/REGISTRY.md`'s actual legend (`pending → manifest → code → prose → done`, tiers `T1/T2/T3`), which I checked.

Two caveats I am adding, which the lane did not have the evidence to state:

1. **Its permalink scheme is stricter than what I did, and it is right to be.** I pinned by taking `repos/{r}/commits → .[0].sha`. Codex requires additionally *verifying the blob SHA at that commit matches the search item's blob SHA* before emitting the URL. That closes a real hole in my method: the newest commit may have changed the file since the index scanned it, so my permalinks are pinned-but-not-verified. **Treat every permalink in this report as pinned to a commit that existed today, not as verified to contain the quoted bytes.**
2. **The lane could not verify against this repo's own graph** — it reports `mise` failing to create a temp file and `graphify query` correctly blocked by the hook. So its claims about `manifest.add()` at `manifest.py:463` and about the schema layout are **derived from what I pasted into the prompt, not independently read.** `manifest.py:463` in particular is a line citation I did not verify and neither did it.

**Caveat 2, updated after checking:** I verified the citation rather than leaving it flagged. `python/src/kb_setup/manifest.py:463` is exactly `def add(sources_dir: Path, source: NewSource, *, force: bool = False) -> Manifest:`, and its docstring reads *"Create `sources/<stem>.manifest` for a new repo, **SHA-pinned at upstream HEAD**."* So the citation is right **and the concern behind it is real**: `add()` resolves upstream HEAD today, which is precisely the moving target codex says to bypass. Its instruction — extend `add()` to accept an already-recorded commit SHA rather than re-resolving — is well-aimed at the actual code. The schema-layout claims remain unverified by either of us.

## What I could not verify

- **Every permalink here is commit-pinned but not blob-verified.** I resolved each repo's newest commit SHA and built the URL from it; I did not confirm the file at that commit still contains the bytes GitHub's index matched. Codex's spec closes this; my method does not.
- **`claude-code.d.ts` is quoted from an unofficial mirror.** No official copy exists (`repos/anthropics/claude-code/contents/skills` → 404). It self-identifies as `// Written by Claude Code 2.1.267.` and is reproducible locally via `/plugin-types`, but **I did not run `/plugin-types` to confirm** — read-only brief, and it writes files. That is the one control arm this finding is missing, and it is cheap for whoever acts on this.
- **My 66-name event catalog is known-incomplete**, by `anthropics/claude-code#92469`'s own account (`session.authorize` and `flag.value` are omitted by the generator). It is also a property-key grep, not a figure the file states about itself.
- **`fs.read`/`fs.write`/`fs.list` (2.1.267 declarations) vs `fs.readFile`/`fs.writeFile`/`fs.listDir` (2.1.263 runtime load line)** — unresolved whether this is a rename between versions or an op-name/method-name split. Not guessed.
- **Whether `.claude/settings.json`'s project `env` block enables the flag** remains untested — as in the prior report. The awesome-list recommends *user* scope (`~/.claude/settings.json`), which `do-not.md` #11 forbids here; it does not say project scope fails.
- **`(2.1.251, 2.1.260]` inherits a number I did not re-measure.** The `(2.1.246, 2.1.260]` half is mine and control-armed today; the 2.1.251 half comes from the prior report's binary-strings pass.
- **The codex lane could not reach this repo's graph** (mise temp-file failure; `graphify query` correctly hook-blocked), so its spec rests on what I pasted, not on independent reading. Its first run also failed at capacity before the retry succeeded.
- **I did not exhaust the 22 code-hit repos.** I read the highest-value ones. `wandercom/kindex`, `SApplefeld/claude-kit`, `n0rvyn/indie-toolkit`, `xkazm04/ai-registry`, `renchris/claude-infrastructure`, `conorluddy/tokenblast.cc`, `cwschroeder/buzz-agent-comms`, `JoshuaOliphant/claude-plugins`, `gillisandrew/dotfiles`, `amitray007/claude-code-schema`, `conceptadev/skills`, `backthread/backthread` and `jfrog/claude-plugin` were identified but not read.
- **Rate limits were never hit**, so no `rate_limited` path was exercised live. `code_search` read 10/10 remaining at every check. **The rate-limit-vs-zero distinction in Job 2's spec is therefore designed, not observed** — I could not arm it.

## GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — the `mods/` tree (still `README.md`, `diff/`, `sec-default/`, `telemetry/`), issues #91870, #92440, #92469, #92533, #92675; `contents/skills` probed and 404.
- [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) — the `/plugin-types` `claude-code.d.ts` for 2.1.267; the tier model, `TargetTier`, `ClassicEventName` and the event catalog all come from here.
- [ray-amjad/awesome-claude-code-function-hooks](https://github.com/ray-amjad/awesome-claude-code-function-hooks) — **the most useful example**; MIT marketplace with `secret-redactor` and `vercel-deploy-status`.
- [lossless-claude/lcm](https://github.com/lossless-claude/lcm) — a completed classic→function-hooks migration (#376, #377, #386, #393); the no-Node/no-SQLite constraint.
- [Monte9/claude-function-hooks](https://github.com/Monte9/claude-function-hooks) — reference implementation; issues #1–#3 (a critique of *that* implementation, corrected above).
- [phate45/claude-patching](https://github.com/phate45/claude-patching) — per-version env-var scans; settled the introduction window.
- [amitray007/claude-code-schema](https://github.com/amitray007/claude-code-schema) — env-var catalog; identified, not read.
- [noopz/commonplace](https://github.com/noopz/commonplace) — `hooks/register.ts` + a tested module gate.
- [bsamiee/Rasm](https://github.com/bsamiee/Rasm) — `.claude/plugins/function-hooks/`; author reported #92469.
- [mahuebel/segmem](https://github.com/mahuebel/segmem), [pleaseai/honmoon](https://github.com/pleaseai/honmoon), [djnsty23/claude-auto-dev](https://github.com/djnsty23/claude-auto-dev), [dodi-hq/dodi-skills](https://github.com/dodi-hq/dodi-skills), [cam-douglas/hermes-playground](https://github.com/cam-douglas/hermes-playground) — working third-party hooks; hermes carries #92533 repro data.
- [jfrog/claude-plugin](https://github.com/jfrog/claude-plugin), [conceptadev/skills](https://github.com/conceptadev/skills), [backthread/backthread](https://github.com/backthread/backthread) — `hooks/hooks.json` shape; identified, not read.
- [cvuijst/cc-function-hooks-poc](https://github.com/cvuijst/cc-function-hooks-poc), [productowner-ro/claude-function-hooks](https://github.com/productowner-ro/claude-function-hooks), [scriptease/claude-code-redact-plugin](https://github.com/scriptease/claude-code-redact-plugin) — dedicated projects from the repositories index; identified, not read.
- [yonatangross/orchestkit](https://github.com/yonatangross/orchestkit) — `validate-fn-hooks-canary.sh`, `.claude/rules/hooks-development.md`, issue #3993.
- [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) — aitmpl.com's source; its 2.1.266 claim is refuted above.
- [nikolaj-lat/World-Puppeteer](https://github.com/nikolaj-lat/World-Puppeteer) — the `.claude/mods/` false positive.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — `research/codesearch.py`, `manifest.py`, `sources/REGISTRY.md`, `schemas/`, the prior report.

**Registry action (per `research-repo-enumeration.md`):** none of the function-hook repos above currently has a `sources/*.manifest` or a `sources/REGISTRY.md` row. The strongest candidates for registration are `ray-amjad/awesome-claude-code-function-hooks` (MIT, complete, tested) and `lossless-claude/lcm` (the completed migration). I did **not** append them — the brief is read-only and the tree must stay clean. This is a flagged, unperformed action, not a completed one.
