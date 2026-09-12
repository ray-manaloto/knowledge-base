# Function Hooks — source sweep + loss audit

Lead: `kb-codex-astra-advisor`. Started 2026-09-12.
Repo HEAD at start: `4cdd8bfb` (branch `feat/754-plugin-types-contract`).

**STATUS: IN PROGRESS — written incrementally, per `agent-report-persistence.md` rule 3.**

## Phase 0 — graph grounding (done)

`mise run kb-query -- "..." --prose --idf` over 11,330 prose nodes.

- Query for function-hook terms returns ONLY the **legacy** hook system
  (`PreToolUse`, `PostToolUse`, `MCP tool hooks`, `plugins-reference.md` "Plugin hooks").
- **Control arm:** the same command shape on `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS`
  ranked `CLAUDE_CODE_ENABLE_APPEND_SUBAGENT_PROMPT` first at **18.14**
  (`claude-code-docs/.../env-vars.md`) — a real env var, so the probe discriminates.
  `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` itself scores nowhere.
- **Conclusion: the corpus contains ZERO function-hooks material.** Every source in
  the ingestion plan below is net-new to the graph.

## Phase 1 — issue 91870 harvest (done)

`gh api repos/anthropics/claude-code/issues/91870` + `/comments --paginate`.
Title *"Function Hooks - make plugins 10x more powerful"*, **open**, author `poteat`,
created 2026-09-03T18:00:23Z, updated 2026-09-12T00:40:29Z, **161 comments** (all fetched, 580 KB).
Body 174 lines; comments 3,127 lines. 38 distinct URLs harvested.

(sections 1-5 follow as they are established)

### 1a. Asset classification — the ROUTE mattered

`curl -sIL` on all 21 `user-attachments/assets/…` URLs returned **403 `application/xml`**
for every one — the S3 error body, because a HEAD is not covered by the signed redirect.
That is a probe that can only fail (`probes-need-a-control-arm.md` rule 4); it is NOT
evidence the assets are gone. **Changed the route** to the markdown structure itself,
which is unambiguous and durable:

- a URL inside `<img src="…">` is a **thumbnail image**;
- a URL on a **bare line** (GitHub auto-embeds these as a video player), which is also
  the `<a href>` target of the matching thumbnail, is a **video**.

**The `private-user-images.githubusercontent.com` signed-JWT SVG in the directive is
resolved.** The durable reference for it is the asset id below — the body renders it via
`<img src="https://github.com/user-attachments/assets/f8f305e5-…">` at `91870-body.md:167`,
`alt="spinning 3d onion model"` (the five-tier onion). No expired URL needs to be chased.

#### The 9 VIDEOS (these are what Ray wants transcribed)

| # | asset id | thumbnail caption | what the body says it shows |
|---|---|---|---|
| V1 | `6e354c92-d71e-4882-bcce-c5f76883d40a` | A hook as a function. | hooks as TypeScript functions, full type definitions **and LSP support** |
| V2 | `7b8a3fda-c6b3-40f9-853b-22a86c7cba9d` | A hook that says no. | restricting behaviour, for safety and control |
| V3 | `ea09f465-d147-4884-947e-fb32c39649fa` | Plugins can draw now. | hooking **components**, modifying their props, wrapping returned render nodes |
| V4 | `26177745-89fa-466b-a2f6-4649369ec7e2` | Admin control as a hook. | admins remove affordances from **`$`** so plugins below cannot invoke that side-effect |
| V5 | `3a45eadd-9d40-405b-b044-4683f3dd3a36` | Order is nesting. | plugins nest like middleware; first registered wraps the rest |
| V6 | `7f01bbee-1de2-46f9-b75d-5bc68cf4dbfc` | Press a plugin's button. | one hook on **`ui.press`** sees the same button in terminal AND desktop app |
| V7 | `c7e3243f-9af0-445d-aa75-12c4d20ac9bc` | Every event at once. | a single hook on **`*`** sees every event, including every plugin's own `$` calls |
| V8 | `44601a4e-a4b4-4e0b-b1d2-4621293b8150` | One sentence. One plugin. | Claude writes, validates and loads a plugin that redacts secrets **before the model reads them** |
| V9 | `9a3abf85-0df2-4975-ac7c-0424a8dff5d2` | Change what Claude Code shows. | Claude Code **Desktop** plugin hiding sensitive values until hover |

Images (not for transcription, but worth archiving as evidence): `2fad9a87` (hero),
`6b624978` `ec1ac1b6` `14592d0b` `62fcaf64` `63550ca2` `35ecb6a6` `aa9b84cf` `7cefbf7a`
`7c64337f` (thumbnails), `f8f305e5` (the five-tier onion), `e3a93cbe` (endpoint managed settings).

## Phase 2 — the four-index GitHub sweep (done)

`gh api -X GET search/...` on `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS`, four indexes separately.
The team-lead's warning is confirmed by measurement: **the indexes disagree wildly.**

| index | total | `incomplete_results` | note |
|---|---|---|---|
| repositories | **1** | false | only `scriptease/claude-code-redact-plugin` |
| issues/PRs | **38** | false | the richest index by value |
| code | **106** | false | 32 distinct repos |
| discussions (GraphQL) | **0** | — | **control-armed**, see below |

**Control arm for the discussions zero:** the same GraphQL shape with
`query: "claude code plugin", type: DISCUSSION` returns `discussionCount = 3501`
with real URLs. The probe discriminates, so **0 is a true zero**, not an outage.
`incomplete_results` was `false` on all three REST indexes, so none of those is a
rate-limited zero either.

**Repositories-index result is near-useless (1 hit) while code returns 32 repos and
issues returns 38 items.** A repositories-only or code-only sweep would have missed
almost everything; this is the 2026-09-10 finding reproducing exactly.

## 🔴 Phase 2a — PRIOR ART ALREADY EXISTS, in the SIBLING repo

The code index returned **`ray-manaloto/dotfiles`** and **`ray-manaloto/knowledge-base`**
as hits on our own search term. Checking locally:

`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/research/kb/reports/agents/`
already holds **nine** function-hooks reports, all dated 2026-09-11/12:

| file | lines |
|---|---|
| `2026-09-11-fnhook-harvest.md` | 1,099 |
| `2026-09-11-fnhooks-examples-review.md` | 597 |
| `2026-09-11-fnhooks-codesearch.md` | 440 |
| `2026-09-11-fnhooks-aitmpl.md` | 315 |
| `2026-09-11-fnhooks-upstream-91870.md` | 308 |
| `2026-09-11-function-hooks-firing-probe.md` | (13.5 KB) |
| `2026-09-11-function-hooks-worktree-bash-probe.md` | (12.8 KB) |
| `2026-09-11-function-hooks-retrieval-advisory.md` | (11.2 KB) |
| `2026-09-12-function-hook-gate-substrate.md` | (26.1 KB) |

Plus `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/.claude/types/claude-code.d.ts`
— **347,960 bytes** of generated declarations, committed there.

**This IS the loss, and it is structural rather than factual.** The research was done,
in dotfiles, and **none of it reached this repo's graph** — Phase 0's control-armed
query returns zero function-hooks material from 11,330 prose nodes. The corpus cannot
answer a question the organisation has already answered nine times.

## Phase 3 — the aitmpl pages: both collapse into ONE repo

**`www.aitmpl.com` IS `davila7/claude-code-templates`** (its own JSON-LD names
`sameAs: ["https://github.com/davila7/claude-code-templates"]`). Both of Ray's URLs
are rendered from files in that repo, so scraping the SPA is the wrong route:

- the blog post → `dashboard/public/blog/function-hooks-claude-code/index.html`
- the `/function-hooks/` page → an Astro SPA that fetches `components.json`;
  the components themselves are `cli-tool/components/function-hooks/**`.

`https://www.aitmpl.com/counts.json` reports **`"function-hooks": 10`**, and
`components.json` yields exactly 10. **All ten enumerated, with their in-repo paths**
at `davila7/claude-code-templates@ec126b9ded118ba66c2125fa39eb5b0e87d701bd`:

| # | component | path under `cli-tool/components/function-hooks/` | hooks it uses |
|---|---|---|---|
| 1 | `admin-capability-lockdown` | `enterprise/admin-capability-lockdown.ts` | `engine.create`, `plugin.register`, `tool.call` |
| 2 | `websearch-to-exa` | `integrations/websearch-to-exa.ts` | `tool.call` (replaces a core tool) |
| 3 | `universal-audit-log` | `observability/universal-audit-log.ts` | `*` |
| 4 | `npm-to-pnpm-rewriter` | `productivity/npm-to-pnpm-rewriter.ts` | `tool.call` (forwards modified event) |
| 5 | `webfetch-cache` | `productivity/webfetch-cache.ts` | `tool.call` (short-circuit + TTL) |
| 6 | `block-destructive-commands` | `security/block-destructive-commands.ts` | `tool.call` (Bash matcher) |
| 7 | `large-edit-confirmation` | `security/large-edit-confirmation.ts` | `tool.call` (files + permissions primitives) |
| 8 | `protected-paths-guard` | `security/protected-paths-guard.ts` | `tool.call` (array matcher) |
| 9 | `secret-redactor` | `security/secret-redactor.ts` | `tool.call` |
| 10 | `tool-timing-badge` | `ui/tool-timing-badge.**tsx**` | `tool.call` + **`ui.render`, using JSX** |

Each has a sibling `.json` manifest at the same path, and a copy under
`dashboard/public/component-content/function-hooks/`.

### 🔴 The caveat that must travel WITH these examples

The page states it itself, verbatim:

> *"Function hooks are an Anthropic proposal under community review, not a shipped
> Claude Code feature. **Every API name in these components is provisional** and comes
> from the proposal's architecture doc and demo videos."*

So these ten are **inferred from the PDF and the videos, not from the shipped API**.
Ingesting them without that condition attached would seed the graph with provisional
names that may already disagree with `mods/` and with what `/plugin-types` emits.
They remain worth ingesting — as *community interpretation*, which is a different
claim from *the API*. Carry the condition, per `verify-before-advancing.md`.

**New surface these 10 reveal** (names only, provisional): nouns `http`, `process`,
`network`, `files`, `permissions` on `$`; a `shellPolicy` with `"deny"` default and a
`"guardrail"` mode; `plugin.register` as a hookable event; `ui.render` returning JSX.

## 🔴 Phase 4 — THE DIRECTIVE'S PROPOSED VIDEO COMMAND DOES NOT WORK

Ray's directive proposes `mise run kb-add -- <yt-url>` then `mise run kb-transcribe`.
**For these videos and for the PDF that path fails**, and the reason is in graphify's
own source, not in the videos.

`graphify/ingest.py:65-82`, `_detect_url_type`, tests in this order:

```
:68  twitter.com / x.com  -> "tweet"
:70  arxiv.org            -> "arxiv"
:72  "github.com" in lower -> "github"     <-- matches FIRST
:74  youtube.com/youtu.be -> "youtube"
:78  path.endswith(".pdf") -> "pdf"        <-- UNREACHABLE for any github.com URL
:80  .png/.jpg/...        -> "image"
:82  fallback             -> "webpage"
```

Every asset in the issue is hosted at `https://github.com/user-attachments/…`, so
**all of them classify as `"github"`**, and `ingest.py:250-256` sends `"github"` down
the `else:` branch to `_fetch_webpage`, which runs `safe_fetch_text` + markdownify.

Two consequences, both measured by reading the code:

1. **The 9 videos** would be fetched as *text* — `_fetch_webpage` on an MP4 byte
   stream. There is no `.mp4` branch anywhere in `_detect_url_type`; only YouTube
   reaches `download_audio`.
2. **The architecture PDF** `…/files/31802150/EXTERNAL.Function.Hooks.Core.Architecture.pdf`
   also contains `github.com`, so it hits `:72` and **never reaches the `.pdf` branch at
   `:78`** — despite ending in `.pdf`. It would be markdownified as HTML too.

**The videos ARE fetchable — this is a classifier problem, not an access problem.**
Control-armed both ways: `curl -sIL` (HEAD) → **403** `application/xml` for all 21
assets, but a plain ranged **GET → HTTP 206, `content_type: video/mp4`**, and `file(1)`
on the bytes says `ISO Media, MP4 Base Media v1`. The HEAD was the broken instrument.

**Sizes independently corroborate the video/image split I derived from the markdown:**

| group | count | bytes each | the body's own claim |
|---|---|---|---|
| Basic + Advanced | 7 | 4.07–4.12 MB | *"Each Basic and Advanced video is 60 seconds"* |
| Case Study | 2 | 9.79 MB, 8.32 MB | *"the full Case Study videos are around 2 minutes"* |

Two independent routes (markdown structure, byte size) agree, so the classification is
not resting on one probe.

### The route that DOES work

`mise run kb-transcribe` takes a **local file**, and graphify's
`transcribe.py:11` declares
`VIDEO_EXTENSIONS = {'.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v', '.mp3', '.wav', '.m4a', '.ogg'}`
— **`.mp4` is accepted directly**, no audio extraction needed. So only the *fetch* step
has to change:

```bash
# 1. fetch by hand — kb-add CANNOT do this one (see above)
curl -L -o raw/fh-v1-a-hook-as-a-function.mp4 \
  https://github.com/user-attachments/assets/6e354c92-d71e-4882-bcce-c5f76883d40a
# 2. local faster-whisper, no key, no LLM
mise run kb-transcribe -- raw/fh-v1-a-hook-as-a-function.mp4
# 3. host-agent extract the transcript -> sources/extractions/, then
mise run kb-merge -- sources/extractions/<chunk>.json
# 4. commit the transcript under sources/media/ (non-refetchable; signed-URL host)
```

**UNVERIFIED:** I did not RUN the transcribe — I am scoped to advice, and the lead asked
for a plan rather than implementation. The claim `.mp4` is accepted rests on reading
`transcribe.py:11`, not on a transcribed file. Recommend one video as the cheap arm
(`local-devcontainer-first.md`) before committing to all nine.

**Worth filing upstream / locally:** `_detect_url_type` ordering is a real defect for any
GitHub-hosted PDF or media asset. A `.pdf`/media extension check belongs *before* the
`github.com` host check.

## 3. THE MANIFEST RESYNC — confirmed by reading the tree

Current `sources/claude-code.manifest`:
`ref = v2.1.258`, `commit = aef74afe01f65b602258d6102b0da9730ac6f0aa`, `kind = docs`.

**Pin to:**

```
ref = v2.1.269
commit = df52d04a4e65195c1621fe6222e0564bcccb1804
```

Resolved via `gh api repos/anthropics/claude-code/git/refs/tags/v2.1.269` → `object.type`
is `commit` (a lightweight tag, so no peel needed — the tag object SHA *is* the commit
SHA here; do not assume that for other tags, cf. *the engine peels annotated tags*).
v2.1.269 is the newest tag and the newest release, published 2026-09-11T19:17:55Z, and
it matches the installed binary 2.1.269.

### `mods/` at that SHA — READ, not assumed

`gh api repos/anthropics/claude-code/contents/mods?ref=df52d04a…` returns:

```
file  1659  README.md
dir      0  diff
dir      0  sec-default
dir      0  telemetry
```

Recursive tree: **580 blobs, 247,235 bytes** — `diff` 489 files, `telemetry` 63,
`sec-default` 27, plus the top README. Each mod carries
`.claude-plugin/plugin.json`, `README.md`, `hooks/hooks.json`, `hooks/index.ts`,
`hooks/register.ts`.

**Control arm:** the same call at the CURRENT pin `aef74afe…` returns
**HTTP 404 `Not Found`**. So `mods/` genuinely does not exist at v2.1.258 and the
resync is what gains it — the probe discriminates in both directions.

### What `mods/README.md` states (verbatim, high-value)

> *"A mod is a Claude Code plugin whose behaviour lives in a hooks module: one
> `register(on, options)` entry that hooks the engine's events as functions
> `($, e, next)`. These three ship inside Claude Code; this folder is their source,
> published as it is built into the binary."*

| mod | what it does | **seating** |
|---|---|---|
| `sec-default` | keeps an org's classic hooks, prompt content, managed settings and tool policy out of reach of user-installed plugins; **adds no policy of its own** | **Outermost**, on a machine with managed settings or for a Team/Enterprise org, *unless managed `prependPlugins` says otherwise* |
| `diff` | `/diff`: uncommitted changes in a pane beside the transcript, refreshed as Claude edits | Built in |
| `telemetry` | adds **`$.telemetry`** (`log`, `mark`) **in the `engine.create` fold** so a plugin can record a first-party analytics row; sends nothing where analytics are off | Built in |

Also stated there, each new to us:

- declarations are imported as **`import type … from 'claude-code'`** — that is the
  module specifier `/plugin-types` writes against;
- **`claude --plugin-dir mods/diff`** runs a mod from source;
- *"hooks modules load only where function hooks are enabled, and the API these mods are
  written against **may change between releases without notice**"*;
- they are **not listed in the repository's marketplace**.

**`prependPlugins` is a managed-settings key** we had no record of, and it is the
mechanism by which admin seating is decided. That is a DECIDES-grade fact for anyone
reasoning about whether a guard can be displaced.

## 4. REPO SWEEP

All verified live via `gh api repos/<r>` (any 404 would have printed `NOT FOUND`; none did).

| repo | ★ | pushed | worth ingesting? |
|---|---|---|---|
| [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) | — | — | **YES, highest** — IS aitmpl.com; carries the blog post AND all 10 examples |
| [Monte9/claude-function-hooks](https://github.com/Monte9/claude-function-hooks) | 1 | 2026-09-03 | **YES** — *"reference implementation of the Function Hooks algebra"*; its 3 open issues are the sharpest semantics analysis found anywhere |
| [amitray007/claude-code-schema](https://github.com/amitray007/claude-code-schema) | 2 | 2026-09-12 | **YES** — machine-readable versioned schema of settings/env-vars/CLI flags **auto-generated per release** |
| [ray-amjad/awesome-claude-code-function-hooks](https://github.com/ray-amjad/awesome-claude-code-function-hooks) | 1 | 2026-09-10 | **YES** — the curated list; same author as the YouTube video below |
| [phate45/claude-patching](https://github.com/phate45/claude-patching) | 4 | 2026-09-04 | **YES** — `patches/2.1.260/env-vars.json` + `env-diff-2.1.246.json`, env vars extracted from the binary |
| [AdityaRon/claude-code-harness](https://github.com/AdityaRon/claude-code-harness) | 4 | 2026-09-11 | YES — machine-level security/audit/context hooks |
| [cvuijst/cc-function-hooks-poc](https://github.com/cvuijst/cc-function-hooks-poc) | 1 | 2026-09-05 | YES — PoC against the API |
| [scriptease/claude-code-redact-plugin](https://github.com/scriptease/claude-code-redact-plugin) | 0 | 2026-09-05 | MAYBE — the ONLY repositories-index hit; small |
| [noopz/commonplace](https://github.com/noopz/commonplace) | 3 | 2026-09-05 | MAYBE — real `hooks/register.ts` + `module-gate.ts` |
| [mahuebel/segmem](https://github.com/mahuebel/segmem) | 0 | 2026-09-11 | MAYBE — `docs/design-function-hooks.md` |
| [diegorv/claude-functions-hook](https://github.com/diegorv/claude-functions-hook) | 0 | 2026-09-10 | MAYBE — no description |
| [indexable-inc/index](https://github.com/indexable-inc/index) | 29 | 2026-09-12 | MAYBE — `packages/claude-code/env-registry.tsv` |
| [lossless-claude/lcm](https://github.com/lossless-claude/lcm) | — | — | MAYBE — `docs/hook-protocol.md`, migrated off PostToolUse/UserPromptSubmit/Stop |
| [get-bb/bb](https://github.com/get-bb/bb) | 3581 | 2026-09-12 | NOISE for this purpose — large agent IDE, mentions the flag only incidentally |
| [PromptSign/spec](https://github.com/PromptSign/spec) · [cwschroeder/buzz-agent-comms](https://github.com/cwschroeder/buzz-agent-comms) | 0 | — | NOISE — tangential mentions |

### An external VIDEO source the directive did not name

**`https://www.youtube.com/watch?v=B-YQANvDOq0`** — *"Anthropic Just Dropped the Biggest
Claude Code Update Yet"*, by **Ray Amjad** (`@RAmjad`), 2026-09-11. Found via the code
index (`pavani06/long-running-agents` vendored its transcript), not via any link in the
issue. Verified live by oEmbed (**control arm:** a bogus 11-char video id returns
**HTTP 400**, the real one returns **200** + JSON metadata).

🔴 **This is the ONE video for which the directive's command is correct as written** —
it is a `youtube.com` URL, so it matches `ingest.py:74` and reaches `download_audio`.
The nine GitHub-hosted ones do not (Phase 4).

```bash
mise run kb-add -- 'https://www.youtube.com/watch?v=B-YQANvDOq0'
mise run kb-transcribe -- raw/<downloaded>.m4a
```

## 1. WHAT WE MISSED — the loss audit (my direct reading of the SHIPPED source)

Everything below is read from `mods/` at `df52d04a…` — **shipped code built into the
binary**, which outranks the proposal PDF, the videos, and every community
interpretation. Ranked DECIDES / SHAPES / CONTEXT.

### 🔴 DECIDES

**D1. "Claude Mods" is the product name; we have been using only the engineering term.**
`91870-body.md:7`: *"from a product perspective, we are going to be calling this
functionality **'Claude Mods'**. The engineering term of art 'function hook' will still
exist as the documented implementation primitive Mods are built on."* Anything we name,
document or search for on "function hooks" alone will miss the product-facing half.
Same line: **"We're now committed to shipping … on the scale of weeks"** — this is no
longer a proposal that might not land.

**D2. The event taxonomy is ~40 events, not a handful.** Our established list names
`tool.call` and nothing else. Counted across body + 161 comments:
`tool.call` (85), `engine.create` (18), `prompt.submit` (15), `session.start` (13),
`agent.spawn` (11), `ui.render` (10), `ui.log` (10), `plugin.register` (10),
`ui.press` (8), `model.complete` (8), `tool.check` (6), `model.fork` (6),
`agent.list` (5), `prompt.context` (4), `ui.select`/`ui.input`/`tool.register` (3),
`session.authorize`, `prompt.section`, `model.classify`, **`hook.error`**, `agent.offer` (3),
`ui.toast`, `ui.status`, `tool.list`, `tool.describe`, `session.compact`, `agent.complete` (2)…
**Confirmed in shipped code** (`mods/sec-default/hooks/register.ts`): `classic.*`,
`prompt.section`, `prompt.context`, `skill.prompt`, `attribution.text`, `settings.read`,
`tool.describe`, `command.describe`, `agent.offer`, `agent.spawn`, `tool.register`, `tool.list`.

**D3. Wildcards are NAMESPACED, not just `*`.** `sec-default/hooks/register.ts:29`
registers **`on('classic.*', …)`** — a prefix glob over the legacy-hook namespace. Our
model had only the single `*` from the issue body. A guard reasoning about "which hooks
can see my event" must account for prefix globs.

**D4. A hook can read its CALLER's tier, and the shipped security mod makes authority
decisions on it.** `sec-default/hooks/register.ts:41-42`:
`const isOrgs = next.origin.tier === 'prepend' || next.origin.tier === 'append'`, and
`:47` `next.origin.tier === 'user'`. So **`next.origin.tier`** is a first-class value with
at least `'prepend' | 'user' | 'append'`.
🔴 **This is where the risk concentrates.** `Monte9/claude-function-hooks` issue #2 is
titled *"The §6.4 guard covers one synchronous tick, and **`next.origin` is caller-supplied**"*.
If `next.origin` is caller-supplied in the shipped engine, the built-in security mod's
authority check is spoofable. The mod's own doc comment says *"Provenance is the event's
pinned `provider`"* — naming **`e.provider`**, a different field from `next.origin`.
**UNVERIFIED: whether the shipped engine pins `next.origin` or trusts the caller.** That
single question decides whether admin seating is enforcement or decoration, and nothing
in the corpus I fetched settles it.

**D5. `{ deny: <message> }` IS a real return shape in shipped code** —
`sec-default/hooks/register.ts:55`: `return isRefused ? { deny: TOOL_REGISTER_REFUSAL } : next(e)`.
Monte9 issue #3 says *"`deny` has no engine meaning"*; that is a claim about the
**proposal**, and the shipped built-in uses it. Do not carry Monte9's claim forward as a
fact about the shipped API.

**D6. `$` is EXTENDED by folding over `engine.create`, and the pattern is exact.**
`mods/telemetry/hooks/register.ts:15-19`:
```ts
on('engine.create', async ($, e, next) => {
  const beneath = await next(e)              // the $ built by everything BELOW
  return { ...beneath, telemetry: telemetryOf({ … }) }
})
```
So `engine.create` **returns the `$` object itself**; a mod adds a noun by spreading
`beneath`. Confirmed `$` nouns: **`session`** (`authorize`, `id`, `model`), **`env`** (`get`),
**`http`** (`fetch`), **`settings`** (`read`). A capability a mod adds is visible only to
mods seated *outside* it — that is the whole security model, and it is a fold, not a registry.

**D7. `prependPlugins` is the managed-settings key that decides seating.**
`mods/README.md`: `sec-default` is seated *"Outermost, on a machine with managed settings
or for a Team or Enterprise organization, **unless managed `prependPlugins` says
otherwise**"*. We had no record of this key. It is the lever that determines whether any
guard is actually outermost.

**D8. The declarations' module specifier is `'claude-code'`.** Every mod opens
`import type { On } from 'claude-code'` (and `diff` also imports `ResultOf`,
`SessionMessage`, `Timer`). `mods/README.md` states these are *"the declarations
`/plugin-types` writes"*. That names the exact import our own generated-declarations work
must target.

**D9. `register`'s second parameter is OPTIONAL in practice.** `mods/README.md` documents
`register(on, options)`, yet **all three shipped mods declare `export function register(on: On)`**
— one parameter. So `options` exists in the contract and is unused by every shipped
example; treat any claim about its contents as UNVERIFIED.

**D10. The API is explicitly unstable.** `mods/README.md`: *"the API these mods are written
against **may change between releases without notice**"*, and mods *"load only where
function hooks are enabled"*. Any contract we pin needs a version condition attached.

### 🟡 SHAPES

**S1. A second live upstream defect we did not have: `anthropics/claude-code#92440`** —
*"`agent.offer` doc comment and example say `offered`, `AgentOfferResult` declares
`isOffered` (2.1.263 /plugin-types)"*. A generated-declaration mismatch, same family as the
`agentId`/`agent_id` finding, in the same generated file.

**S2. `hook.error` is an event.** Appears 3× in the corpus. Its existence means hook
failure is **observable and hookable**, which complicates "a broken hook is SKIPPED":
skipped silently, or skipped with a `hook.error` dispatch? **UNVERIFIED** — I did not find
the settling text.

**S3. UI hooks are real and cross-surface.** `ui.render` returns **JSX**
(aitmpl's `tool-timing-badge.**tsx**`), and the body claims one `ui.press` hook sees the
same button *"in the terminal and in the desktop app"*. Claude Code **Desktop** is in scope.

**S4. The `diff` mod is a large worked example** — 489 files for one pane. It shows
`session.start` binding the engine once, a command registration that is *refused because
the built-in holds it*, timers, panes and polling. It is the best available evidence of
what a non-trivial mod actually costs.

**S5. A cheat-sheet of affordances exists as an IMAGE**, not text —
`user-attachments/assets/2fad9a87-…` (2400×1600), described in the body as *"a cheat sheet
reference that enumerates some affordances on **v267/v268**"*. It needs vision, not
whisper. It is the densest single artifact in the issue and is **not** covered by the
transcribe path.

**S6. The five-tier onion is the `f8f305e5-…` animation**, and the body ties it to the PDF:
*"Read the 'Function Hooks: Core Architecture' doc below to figure out what this little
animation represents."* This resolves the directive's expired signed-JWT SVG.

**S7. New/undocumented env vars surface in `telemetry`** —
`CLAUDE_CODE_USE_MANTLE`, `CLAUDE_CODE_USE_FOUNDRY`, `CLAUDE_CODE_USE_ANTHROPIC_AWS`,
`CLAUDE_CODE_USE_ANTHROPIC_GOOGLE_CLOUD`, alongside `DISABLE_TELEMETRY`, `DO_NOT_TRACK`,
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, `CLAUDE_CODE_CUSTOM_OAUTH_URL`, `USER_TYPE`.

### ⬜ CONTEXT

**C1.** `hooks.json` uses a **`"modules"` array** (`["./register.ts"]`) — a third-party repo
(`yonatangross/orchestkit#3993`) has already had to *"scope the modules-key ban to shipped
hooks.json"*, so the key is contested in the ecosystem.
**C2.** `claude --plugin-dir mods/diff` runs a mod from source — a cheap local probe path.
**C3.** The three mods are *"not listed in this repository's marketplace"*.
**C4.** `sec-default` *"adds no policy of its own"* — it only protects existing org controls.

## 2. INGESTION PLAN

Ordered cheapest-first (`local-devcontainer-first.md`). Everything in group A is
**free — AST/doc extraction, no LLM**. Group B costs whisper time. Group C costs Claude tokens.

### A. Repo manifests (free, deterministic, reproducible)

| # | source | type | command | why |
|---|---|---|---|---|
| A0 | `anthropics/claude-code` **RESYNC** | repo | edit `sources/claude-code.manifest` to `ref = v2.1.269` / `commit = df52d04a4e65195c1621fe6222e0564bcccb1804`, then `mise run kb-build` | gains `mods/` — 580 files of **shipped** mod source, the only authoritative API we have. `mods/` is 404 at the current pin |
| A1 | `davila7/claude-code-templates` | repo | `mise run kb-manifest-add -- https://github.com/davila7/claude-code-templates` | **covers BOTH aitmpl URLs at once**: the blog post (`dashboard/public/blog/function-hooks-claude-code/index.html`) and all 10 examples (`cli-tool/components/function-hooks/**`) |
| A2 | `Monte9/claude-function-hooks` | repo | `mise run kb-manifest-add -- https://github.com/Monte9/claude-function-hooks` | reference implementation of the algebra; its 3 issues are the sharpest semantics analysis anywhere |
| A3 | `amitray007/claude-code-schema` | repo | `mise run kb-manifest-add -- https://github.com/amitray007/claude-code-schema` | machine-readable settings/env-var/CLI schema **auto-generated per release** — directly answers "what changed between 2.1.258 and 2.1.269" |
| A4 | `ray-amjad/awesome-claude-code-function-hooks` | repo | `mise run kb-manifest-add -- https://github.com/ray-amjad/awesome-claude-code-function-hooks` | the curated list; same author as the YouTube video (B1) |
| A5 | `phate45/claude-patching` | repo | `mise run kb-manifest-add -- https://github.com/phate45/claude-patching` | `patches/2.1.260/env-vars.json` + `env-diff-2.1.246.json`, env vars extracted from the binary |
| A6 | `AdityaRon/claude-code-harness` | repo | `mise run kb-manifest-add -- https://github.com/AdityaRon/claude-code-harness` | machine-level security/audit/context hooks — closest to our own guard surface |
| A7 | `cvuijst/cc-function-hooks-poc` | repo | `mise run kb-manifest-add -- https://github.com/cvuijst/cc-function-hooks-poc` | PoC written against the API |
| A8 | `scriptease/claude-code-redact-plugin` | repo | `mise run kb-manifest-add -- https://github.com/scriptease/claude-code-redact-plugin` | the only repositories-index hit; small, cheap |

Optional, lower value: `noopz/commonplace`, `mahuebel/segmem`, `diegorv/claude-functions-hook`,
`indexable-inc/index`, `lossless-claude/lcm`.

### B. VIDEOS — two different paths, and only one matches the directive

**B1 — YouTube (the directive's command works here):**

```bash
mise run kb-add -- 'https://www.youtube.com/watch?v=B-YQANvDOq0'
mise run kb-transcribe -- raw/<downloaded>.m4a
```
*"Anthropic Just Dropped the Biggest Claude Code Update Yet"* — Ray Amjad, 2026-09-11.

**B2–B10 — the 9 issue videos (`kb-add` CANNOT fetch these; see Phase 4):**

```bash
# fetch by hand, then transcribe locally
curl -L -o raw/fh-<n>-<slug>.mp4 https://github.com/user-attachments/assets/<id>
mise run kb-transcribe -- raw/fh-<n>-<slug>.mp4
```

| id | asset | slug | MB |
|---|---|---|---|
| B2 | `6e354c92-d71e-4882-bcce-c5f76883d40a` | `a-hook-as-a-function` | 4.10 |
| B3 | `7b8a3fda-c6b3-40f9-853b-22a86c7cba9d` | `a-hook-that-says-no` | 4.12 |
| B4 | `ea09f465-d147-4884-947e-fb32c39649fa` | `plugins-can-draw-now` | 4.07 |
| B5 | `26177745-89fa-466b-a2f6-4649369ec7e2` | `admin-control-as-a-hook` | 4.11 |
| B6 | `3a45eadd-9d40-405b-b044-4683f3dd3a36` | `order-is-nesting` | 4.12 |
| B7 | `7f01bbee-1de2-46f9-b75d-5bc68cf4dbfc` | `press-a-plugins-button` | 4.09 |
| B8 | `c7e3243f-9af0-445d-aa75-12c4d20ac9bc` | `every-event-at-once` | 4.12 |
| B9 | `44601a4e-a4b4-4e0b-b1d2-4621293b8150` | `one-sentence-one-plugin` (case study) | 9.79 |
| B10 | `9a3abf85-0df2-4975-ac7c-0424a8dff5d2` | `change-what-cc-shows` (case study) | 8.32 |

**Run B2 alone first as the cheap arm** — it proves the mp4→whisper path before spending
the other eight (`local-devcontainer-first.md`). Transcripts then go to `sources/media/`
(committed; the host serves signed URLs, so these are non-refetchable by definition).

### C. PDF + the cheat-sheet image (neither is covered by the two paths above)

| source | why it is special | route |
|---|---|---|
| `…/files/31802150/EXTERNAL.Function.Hooks.Core.Architecture.pdf` | `kb-add` misclassifies it as `"github"` and would markdownify it (Phase 4) | `curl -L -o raw/fh-core-architecture.pdf <url>`, then host-agent extract → `sources/extractions/` → `mise run kb-merge` |
| `…/assets/2fad9a87-…` the **v267/v268 affordance cheat sheet** | it is an **image**, 2400×1600 — whisper cannot read it and no extraction path here does OCR | needs a vision read by the host agent; this is the densest single artifact in the issue |

### D. Close the loop (mandatory, `kb-curator` MANDATE)

```bash
mise run kb-label
mise run kb-remember -- --question "…" --answer-file A.md --outcome useful
mise run kb-reflect
```

## 1b. WHAT WE MISSED — from `poteat`'s own comments (Anthropic, the proposal author)

`poteat` wrote **25 of the 161 comments**; the next most frequent commenter is
`deafsquad` at 9. These are the authoritative statements in the thread and several
directly extend or correct our established list. Quoted verbatim, attributed by login
and date.

### 🔴 DECIDES

**D11. A whole SECOND hook shape exists: streaming hooks are async generators.**
poteat, 2026-09-11 (comment `5638914414`): *"for hooks which stream data - such as
`turn.step`, you must actually pass in an **async generator** instead of a normal
callback… **This is the only hook that may yield in this way.**"* With his example:
```ts
on('turn.step', async function* ($, e, next) {
  const stream = next(e)
  for await (const chunk of stream) {
    yield chunk.kind === 'text' ? { kind: 'text', index: chunk.index, text: rot13(chunk.text) } : chunk
  }
  return stream.result
})
```
Our entire model assumed one callback shape. **`turn.step` is a new event and a new
signature**, and any type/contract work that assumes `($, e, next) => result` is wrong
for it.

**D12. Ordering inside the user tier is a TOPO-SORT over declared plugin dependencies.**
poteat, same comment: *"plugins may already declare dependencies, and within the user
tier, this controls the order - i.e. if plugin A declares a dependency on plugin B, then
A is registered before B. It's a **topo-sort**, going with the user's stated order insofar
as it's compatible with the plugins' declared order (some deterministic greedy algo,
tbd)."* We had "registration order" and nothing about dependency-driven reordering.
Note **`tbd`** — the algorithm is not settled.

**D13. A hook CANNOT reorder itself; the admin owns order.** Same comment: *"that's not
really possible - **the org admin controls plugin order**."* Combined with D7
(`prependPlugins`), this is the full seating story.

**D14. `next.trace` exists and is a deliberate security hazard.** poteat, 2026-09-06
(`5560061162`): *"`next.trace`, among other things, **enumerates `e` snapshots across the
chain below you** - useful for understanding the chain, timing, latency metrics… I'm
thinking `next.trace` is deep and scary enough (but useful!) that it ought be logged in
the validation step and present as **usage-metadata on `plugin.register`**, so you may…
decline to register a non-managed plugin which reads from it."*
🔴 **This is the single most important security fact in the thread for us.** A plugin
reading `next.trace` can see every event snapshot below it — including data an inner hook
redacted. The mitigation is *proposed, not shipped*.

**D15. Declarative error handling was PROPOSED AND REJECTED.** The community asked for
`{ onError: "deny" }`. poteat, 2026-09-06: *"I'm still not convinced. **I don't believe in
representing code as JSON.** A try-catch provably catches all instances of
`$.doesnt.exist`, just write a try-catch."* So there is **no declarative fail-closed
switch**; a mod that must fail closed writes its own try/catch.
This sharpens our "a broken hook is SKIPPED": the remedy he offers is
*"if you were really paranoid you could set up your own org hook and read off of a
`next.trace` to have 100% confidence that all of your desired hooks did run, and if that
entry isn't present on the trace, **kill the session**."* That is a workaround, not a
guarantee — and it depends on `next.trace`, the very API he wants to restrict (D14).

**D16. Org-managed plugins are seated at the BOTTOM for redaction, not the top.**
poteat, 2026-09-06: *"org-managed appending forces your plugin(s) to be on the bottom, so
this hook has the **first call to define what the engine is returning** for every tool
call, such that higher hooks cannot receive the data you elided."* He is explicit that
higher hooks *"may manipulate in other ways… but none of this puts back the data you
removed"* — **except via `next.trace`**, which he flags in the same comment. So
`prepend`/`append` is not simply "admin on top"; redaction wants `append` (innermost).

### 🟡 SHAPES

**S8. `$.fs` is PLANNED, not shipped.** poteat, 2026-09-06: *"we **plan for** a `$.fs` to
exist. It can read anything by default and your org admin can restrict it via their own
logic."* With a worked `on("fs.readFile", …)` admin example. Treat `$.fs` as future.

**S9. `$.tool.check` is a real, usable affordance** — poteat's example:
`const { decision } = await $.tool.check({ tool: "Read", input: { file_path: e.path } })`,
then `decision === "allow"`. A hook can ask the engine's own permission system.

**S10. `plugin validate` is SYNTACTIC ONLY.** poteat, 2026-09-06: *"`validate` only
syntactically checks your plugin"* — it *"checks the spelling of `$`, not the existence of
the noun"* (the community phrasing he endorsed). A deeper dependency-aware check is only
*"perhaps"*. **Do not treat a passing `validate` as evidence a mod's `$` usage resolves.**

**S11. `next.signal` marks an abandoned dispatch.** poteat, 2026-09-11: *"`next.signal` is
merely a signal that the dispatch has been abandoned, the host will not be doing anything
with your return value."* Downstream promises stay owned by their plugins and may *"float
arbitrarily (this is how timers work)"*.

**S12. A plugin may depend on another plugin's `$` additions.** poteat, 2026-09-06:
*"because `engine.create` exists, you could e.g. declare a dependency on a different
plugin (which provides its own utilities on `$`), and use those."*

## 🔴 1c. TWO OF OUR ESTABLISHED FACTS ARE WRONG OR BADLY INCOMPLETE

These are the highest-value items in this report. Both come from `poteat` directly.

### 🔴 X1. `next.to()` does NOT skip immediately — and multiple requests INTERSECT

Our established fact: *"`next.to()` skips inward only."* True, and so incomplete that it
gives the wrong answer for any chain with more than one hook in a tier.

poteat, 2026-09-07 (comment `5574036379`), verbatim:

> *"if you're a prepend plugin, and you call `next.to(e, "core")`, **you'll still run
> prepend plugins below you** (which could themselves just call `next`, or e.g.
> `next.to(e, "builtin")` - then, when we exhaust the prepend tier, **we take the
> intersection of the declared tiers to run, i.e. the lowest one** - so if one prepend
> plugin said to skip to `"core"`, and one said to skip to `"builtin"`, we would skip to
> `"core"` and not run `"builtin"`."*

Three consequences we did not have:

1. **A skip is deferred to the end of your own tier**, not applied at the call.
2. **Skips COMBINE by taking the lowest (most skipping) request** across the tier.
3. So **one plugin in a tier can suppress a tier for everyone else in it**, and a hook
   cannot tell from its own call what will actually be skipped.

Any guard reasoning "my hook is in the `append` tier so it will run" is unsound: a single
`prepend` peer calling `next.to(e, "core")` removes `builtin` **and** `append`.

He also confirms the five tiers verbatim — **`[prepend] [user] [append] [builtin] [core]`**
— so that part of our list holds, and states the purpose: *"important for org admins to be
able to easily 'disable' classes of hooks in the user tier, in a programmatic way."*

### 🔴 X2. `deny` does NOT stop the tool running, and `deny: ""` still denies

poteat, 2026-09-04 (comment `5546290346`), verbatim:

> *"The return of 'deny' here is **not somehow making the tool not get called**. To make
> the tool not get called, **don't call `next(e)`**. The return value is what we tell the
> model happened - when you hook onto `tool.call`, **you are responsible for calling the
> tool**… Our logic for determining 'did the chain say it denied it or not' is merely
> **`const approved = result.deny === undefined`**."*

So:

- `deny` is a **message to the model**, not an engine-level block;
- **`{ deny: "" }` DENIES** — an empty string is `!== undefined`. A falsy-check bug here
  fails open in one direction and closed in the other;
- **not calling `next(e)` is the only actual block.**

This reconciles the contradiction I flagged earlier between `Monte9` issue #3
(*"`deny` has no engine meaning"*) and `sec-default` shipping `{ deny: … }`: **both are
right.** `deny` has no *blocking* meaning; it has a reporting meaning, and the built-in
uses it correctly *alongside* not calling `next`.

And directly answering Monte9 issue #3's other half — poteat, same comment:
> *"`next(e)` called twice… This is **completely supported**; for example if you want to
> do a retry, backoff, etc… it runs the chain below twice."*
**Intended behaviour, not a defect.** Do not carry Monte9's framing forward.

### 🔴 X3. Isolation is a REAL boundary, and its mechanism is named

poteat, 2026-09-04: *"It's a boundary! The current design is a **Bun Worker** surrounding
the entire plugin realm, with each plugin then having a **`node:vm` wrapper** - that's not
part of the contract though, the contract is merely that you don't get access to ambients.
So it **is** mechanically the case that you cannot `import fs`."*
The *contract* is "no ambients"; the *mechanism* is Bun Worker + `node:vm` and is
explicitly **not** contractual. Carry the condition, not just the fact.

### 🟡 X4. Classic shell hooks get a 1:1 compatibility layer

poteat, 2026-09-07: *"Our internal prototype now introduces a **`classic.PreToolUse`**
event (and the others, **1:1**), which 'wraps' the core shell hooks you already have
configured, and has the **same in/out data interface**."* Plus *"type-safe glob matching on
`on`"* where *"`e` is a union of all classic hooks"*. This is what `sec-default`'s
`on('classic.*', …)` is hooking, and it means our existing shell-hook guard stack has a
migration path rather than a cliff.

### 🟡 X5. A surface declares what is hookable — some components are NOT

poteat, 2026-09-04: *"a surface declares a set of components that acts as the grammar or
substrate of that surface… our internal **'permission request component' is simply not
something you can hook into, because the surface does not declare it as being hookable**."*
So render hooking is bounded by a declared grammar, and the human-approval path is
deliberately outside it. He also states the consent model plainly: *"It's not within our
prerogative to limit the functionality of what plugins can do; you (or your admin) are
giving consent by installing the plugin in the first place."*

### ⬜ X6. Naming is still moving

poteat, 2026-09-07: *"I'm renaming our internal prototype from `fs.readFile` to `fs.read`
now, because it's internal, and it's **pre-contract**."* Event names in the thread may
already be stale — prefer `mods/` at a pinned SHA over any comment.

## 🔴 1d. THE AUTHORITATIVE SURFACE — the generated `.d.ts` at 2.1.269

The strongest evidence in this whole sweep is a file we already have and had not mined:
`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/.claude/types/claude-code.d.ts`,
**9,192 lines**, whose first line reads `// Written by Claude Code 2.1.269.` — the exact
version we are proposing to pin. It outranks the issue comments, which are dated and
pre-contract.

### 🔴 X7. `next.trace` and `.catch` BOTH SHIPPED — the comments' "proposed" status is stale

Control-armed against the three shipped mods: `next.trace` → **rc 1, ABSENT**;
`next.origin` → **rc 0, present** (positive control); a bogus token → **rc 1** (negative
control); `on(…).catch` → **rc 1, ABSENT**. So the probe discriminates, and the mods
genuinely do not use them.

**But absence from three mods is not absence from the API**, and the `.d.ts` settles it:

- `next.trace` is declared — `:3138` `readonly trace: readonly TraceEntry<N, Args<N>, GlobNextResult<N>>[];`
  (also `:3858`, `:6761`, `:6850`), with `:4328` and `:7005` describing what an entry names.
- `.catch` is declared — `:5328` *"Sets the handler run when the hook throws or overruns
  its budget"*.
- `err.budget` is real — `:3173` `readonly budget: number;`, and `:3160` *"`budget` is the
  handler's own grace."*

poteat floated both as undecided on 2026-09-06/08 (*"I'm not sure yet; it's complicated"*).
**They landed.** This is the clearest case in the sweep of a comment being true when
written and false now — carry the date with the claim.

Same correction applies to **`$.fs`**: poteat said *"we **plan for** a `$.fs` to exist"*
on 2026-09-06; it is used 7× in the shipped mods. It shipped.

### 🔴 X8. "A broken hook is SKIPPED" — CONFIRMED, and materially incomplete

`claude-code.d.ts:2413-2415`, verbatim:

> *"At every one, a hook that fails (**throws, overruns its budget, answers a wrong
> shape**) is skipped: the hooks beneath and core run in its place, **or its last `next`
> result stands**; **the failure is reported, naming it**."*

Three things our one-line version was missing:

1. **Three distinct failure modes**, not one — a throw, a **budget overrun**, and
   **answering the wrong shape**. A type error at runtime is a skip.
2. **Two different outcomes** depending on *when* it failed — before `next` → beneath and
   core run in its place; after `next` → **its last `next` result stands**.
3. **The failure is REPORTED, naming the hook.** It is not silent. Anyone who read our
   note as "fails invisibly" would build the wrong mitigation.

### 🔴 X9. The failure taxonomy is a 7-member union, and it is worth knowing whole

`claude-code.d.ts:7528` —
`export type TraceOutcome = 'caught' | 'expired' | 'kept' | 'passed' | 'rejected' | 'returned' | 'skipped';`

Per `:7516-7527`:

| outcome | meaning |
|---|---|
| `returned` | its result stood |
| `passed` | it returned, by reference, what its last `next()` resolved to |
| `skipped` | it failed **before** `next`, **or** a `next.to` above continued beneath its tier (`reason` says which) — beneath ran in its place |
| `kept` | it failed **after** `next`, and that run's result stands |
| `expired` | its budget ran out |
| `caught` | it threw or its budget ran out, and its **`.catch` handler's result stands** |
| `rejected` | the link rejected; the **deepest** such entry is where the rejection came from |

🔴 Note `skipped` conflates **a failure** with **a `next.to` skip from above**, and only
`reason` distinguishes them. A guard auditing "did my hook run" must read `reason`, not
just the outcome.

### 🟡 X10. `engine.create` hooks have NO budget

`claude-code.d.ts:5323` — *"register() returned and one on `engine.create`, whose hook has
no budget"*. So the one hook that builds `$` is unbounded, while every other hook is
budgeted. `:904` adds that for a component *"a throw or an overrun unmounts the instance"*.

### 🟡 X11. `tool.call`'s contract, verbatim (`:2419-2423`)

> *"`next(e)` runs the hooks beneath, then core (the permission prompt, the tool itself).
> Return `{ deny: reason }` to refuse or `{ result }` to answer yourself; a hook that
> returns while its `next` is pending **aborts what runs beneath**. **The managed-settings
> hooks run first: their deny is the call's result.**"*

`{ result }` — answering the call yourself — is a return shape we did not have. And
*"managed-settings hooks run first: their deny is the call's result"* is the admin
override stated as a guarantee.

### 🟡 X12. The `$` extension is TYPED as an open record

`claude-code.d.ts:2405` —
`export type EngineCreateResult = Partial<EngineInterface> & { readonly [noun: string]: unknown };`
That is D6's fold with a type: a mod returns a partial engine plus **arbitrary new nouns**.

### 🟡 X13. The rendering surface, stated exactly

`.d.ts` header: the globals are **`h` and `Fragment`** (what JSX compiles against) plus the
JSX namespace and *"the environment's web APIs (URL, TextEncoder, AbortController,
crypto.subtle, …)"*. *"A hooks module runs in an environment of its own: **no DOM, no
Node**."* Elements are **not globals** — *"they come from the surface's table,
`const { Box, Text } = $.ui.resolve(e)`"*. That is X5's "surface declares the grammar",
made concrete.

### ⬜ X14. `register`'s signature, confirmed

`.d.ts` header: `export const register: Register = (on, options) => { … }`, and a `.js`
form via `/** @type {import('claude-code').Register} */`. So **JS modules are supported**,
not only TS. `prependPlugins` appears **0** times in the `.d.ts` — consistent with it being
a *managed-settings* key rather than part of the hooks API.

### 🔴 The meta-finding

**All of X7–X14 were derivable from a file already on this machine, in the sibling repo,
before this sweep started.** The nine dotfiles reports and this 9,192-line declaration
are the single richest function-hooks source we have, and the knowledge-base graph
contains none of it (Phase 0, control-armed). Ingesting *that* is worth more than any
external repo in section 2.

## 🔴 CORRECTION TO THIS REPORT — my S2 was wrong

**S2 above claimed *"`hook.error` is an event"*. It is not.** The Astra lane caught it, and
I re-derived the check rather than taking the lane's word:

- `91870-comments.md:2163` is `frsorrentino`, 2026-09-06, **asking for one**: *"the ask
  becomes an explicit `hook.error` event in the engine, separate from deny… raised for
  launch failures, schema rejections and the registered `timeout` alike"*.
- `hook.error` appears **0 times** in `claude-code.d.ts` at 2.1.269.

I inferred existence from a **frequency count** of an event-shaped token (3 hits) without
checking whether the hits were declarations or requests. That is measuring a proxy for the
thing — the exact failure my own notes warn about. **Every name in my D2 event list is a
token count and carries the same risk**; Astra's S1 below is the provenance-labelled
inventory and supersedes my D2 wherever they disagree.

The substantive point survives in better form: line 2634 states the real gap —
*"A hook killed by its own timeout cannot detect its death, because the thing that would
notice is the thing that got killed."* That was true when written; the shipped `.catch`
(X7, `:5328`, *"when the hook throws **or overruns its budget**"*) is the answer that
landed afterwards.

## 5. THE ASTRA LANE — status and integration

**The lane RAN and SUCCEEDED.** `mise run kb-codex -- --model gpt-6-astra --effort xhigh
--sandbox read-only --timeout 1800`, banner reported `sandbox: read-only` and
`workdir: …/knowledge-base`; **`LANE_RC=0`**; verdict written to
`.agent/kb/raw/fh/astra-verdict.md`, **462 lines / 56,205 bytes**, ~12 min wall.
No refusal, no capacity error, no rc 124.

**One earlier attempt FAILED and is reported rather than hidden:** the first launch ran
with cwd set to the scratchpad, so mise resolved a different config and died with
`mise ERROR no task kb-codex found`. It nonetheless reported **`exit code 0`**, because the
invocation ended in `| tail -40` — the pipe-masking trap `verify-before-advancing.md`
names, reproduced here live. The relaunch captured a real rc via a redirect.

**What the lane had, and did NOT have.** I gave it the issue body, all 161 comments and the
`mods/` tree. I did **not** give it `claude-code.d.ts` (I found that later, in dotfiles).
So where the lane says `.catch`, `next.trace` and `tool.check` are *proposed/UNVERIFIED*,
that is correct **for its corpus** and is superseded by X7 above — not a disagreement.

Where the lane and I disagree on a fact, **the lane is right twice**:
1. `hook.error` — corrected above.
2. **`options` = the manifest's `userConfig`** — I marked it UNVERIFIED; the lane found it
   stated in the pinned source at
   `mods/diff/hooks/backend/installed-backend-probes.ts:10-12`, which also requires
   `register` to be a **plain exported function**. That supersedes my D9.

The lane's full verdict is reproduced verbatim below, per `agent-report-persistence.md`.
Its own labelling convention — **SOURCE** (pinned mod source), **STAFF** (attributed
`poteat`), **REPORT** (community, not independently reproduced), **INFERRED** — is worth
preserving; it is stricter than mine.

### The lane's findings that most change a decision, and that I did NOT have

- **Noun withholding is NOT a policy over core tools.** Removing `fs` at `engine.create`
  blocked plugin filesystem calls **while the model's own `Write` tool still wrote the
  file** (`91870-comments.md:1523`). A guard built on withholding does not constrain
  `Write`, shell subprocesses or MCP servers.
- **A managed `prependPlugins` REPLACES the whole prepend list** — an admin adding their
  own array can silently remove `sec-default` unless they name `sec-default@builtin`
  (`mods/sec-default/README.md:45-55`). Directly contradicts an additive reading of D7.
- **Module capability-resolution failure unloads the module while its declared
  withholdings REMAIN** — *"retained withholding is not retained guard execution"*; one
  unresolved `classic.PreToolUse` registration removed all four handlers in that module
  (`:2688-2715`).
- **`$[expression]` is rejected** by static analysis, as is passing `$` to a helper — so
  code must keep literal `$` calls at their call sites (`:1294-1296`, `:1525-1527`).
- **`{deny:""}` behaviour CHANGED between 2.1.260 (allowed) and 2.1.261 (blocked)** — my X2
  quoted the presence rule correctly but missed that it is a *change*.
- **Two dispatches can share the same tool-use ID** — IDs are not exactly-once receipts.
- **A prepended `next.to(…,"core")` can skip an appended redactor, and nobody answered
  that** (`:2636-2642`, `:2717-2719`). This is the unresolved security question.
- **`tool.check` is NOT in 2.1.267 declarations** (`sirmaelstrom`, `:3075-3080`) despite
  poteat's design examples — so my S9 is weaker than I stated.
- **A rollout flag can leave a plugin loaded with its hooks module inactive** (`:1927-1933`)
  — installation success does not prove hook activation.

---

# APPENDIX — the Astra lane's verdict, VERBATIM

`gpt-6-astra` / `xhigh` / `--sandbox read-only` / `--timeout 1800`, `LANE_RC=0`.
Corpus given to it: `91870-body.md`, `91870-comments.md` (all 161), `mods/` at `df52d04a`.
It did NOT have `claude-code.d.ts` — see section 5.

Its own method note, reproduced because it matters: *"this was an offline source audit, not a new runtime probe. Required graph orientation was unavailable: the direct command was blocked by the repository hook, and the mise wrapper failed read-only temporary-file creation… No graph-health or runtime-validation claim is made."* The graph work in Phase 0 is mine, run outside the lane.

---

# A. Loss audit

**Correction to established claim #3: “a broken hook is SKIPPED” is too broad.** The corpus supports skipping failed **event invocations**, but also reports module unloading with **declared capability withholdings retained**. Those are different failure policies. A valid hook that returns without calling `next` is also an intentional replacement, not necessarily a broken hook. `91870-comments.md:2132–2143,2688–2715`.

**The most consequential later staff clarification:** abandoning a dispatch does **not** stop the plugin’s work. `next.signal` indicates that the host has abandoned the return value; plugins can continue calling `$`. This changes cancellation, timeout, resource cleanup, and concurrent-guard designs. **`poteat`, September 11:** `91870-comments.md:3115–3119`.

All file anchors below are relative to [`.agent/kb/raw/fh/`](/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agent/kb/raw/fh). I read the complete issue body, all **161 comments**, the required files for all three mods, and the relevant implementations and types. **SOURCE** means the pinned mod source; **STAFF** means an attributed `poteat` statement; **REPORT** means a community member’s account, not independently reproduced here. **INFERRED** identifies my design conclusion. Linked artifacts were not fetched.

## DECIDES — findings that change architecture or enforcement decisions

### D1. Failure handling is more specific—and less settled—than “skip broken hooks”

| Case | What this corpus establishes |
|---|---|
| Unhandled throw | **STAFF:** the September 3 proposal initially redispatched with **all plugins absent**, then changed toward catching, logging, and routing around the failed hook. Do not preserve the first answer as the final design. `91870-comments.md:669–678,769–778`. |
| Throw before `next` | **REPORT, `deafsquad`, 2.1.260:** the engine runs what is beneath the failed hook. The outer hook receives the normal downstream result, without a failure field distinguishing that execution. Failure is recorded in `--debug-file`. `91870-comments.md:1513–1519`. |
| Throw after `next` | **REPORT, `frsorrentino`, 2.1.260:** the debug message says the failed hook is skipped and **its last `next()` run’s result stands**. This is materially different from always rerunning the tool. `91870-comments.md:1341–1344`. |
| Invalid return or invalid input to `next` | **STAFF:** both are skip causes, alongside throws and excessive runtime. **REPORT:** `{}`, `undefined`, and `{text:"ok"}` from a `tool.call` hook that never calls `next` cause fallback execution. `91870-comments.md:2080–2086,2134–2143`. |
| Async budget overrun | **REPORT, `deafsquad` and `42tahara`, 2.1.263:** a 10,000 ms budget produces a named error and the tool proceeds through fallback. A wait using `next.signal` can observe rejection. This is historical measured behavior, not a verified v2.1.269 timeout contract. `91870-comments.md:2397–2403,2646–2670`. |
| Non-yielding infinite/busy loop | **REPORT, `42tahara`, 2.1.263:** an unanswered worker heartbeat produces a **5,000 ms** wedged-worker failure; the hook is skipped and the tool runs. This is a separate mechanism from the async budget. `91870-comments.md:2653–2668`. |
| Module capability-resolution failure | **REPORT, `Spencer-Morley`, 2.1.263:** the module unloads, while its declared withholdings remain. One unresolved `classic.PreToolUse` registration caused all four handlers in that module to disappear. **Retained withholding is not retained guard execution.** `91870-comments.md:2688–2715`. |
| Runtime absent because rollout is disabled | **REPORT, `cwschroeder`, 2.1.261:** the plugin loads, while its hooks module remains inactive; the debug record names the rollout flag. Installation success does not prove hook activation. `91870-comments.md:1927–1933`. |

**The staff position on configurable failure behavior evolved.**

- **September 5–6:** `poteat` argued against a separate JSON-style failure declaration and recommended code-level `try/catch`. `91870-comments.md:2074–2086,2283–2287`.
- **September 8:** he proposed **`on(...).catch(($, e, err) => …)`**, including execution after timeout or throw, a small additional grace budget, possible `err.budget`, and possibly information about whether `next` had run. The catch handler could itself time out and be skipped. **This is a proposal, not demonstrated shipped behavior in the supplied source.** `91870-comments.md:2824–2853`.
- Earlier proposed exceptions to ordinary `next` behavior included invalid arguments, using `next` after the handler settled, reaching bottom with no working implementation, and cancellation. Those were explicitly tentative. `91870-comments.md:772–778`.

**INFERRED:** enforcement tooling needs separate states for **inactive module, failed registration, retained withholding, skipped invocation, explicit refusal, and successful replacement**. A single “hook healthy” boolean loses distinctions the corpus demonstrates. `91870-comments.md:1927–1939,2134–2143,2688–2715`.

### D2. `next` controls execution; the returned verdict describes execution

**STAFF:** when intercepting `tool.call`, the plugin assumes responsibility for invoking the tool—or providing its replacement. Returning `{deny: …}` does not reverse an effect already performed. `poteat` explicitly says the engine cannot infer whether the effect “really happened,” because a mod may replace a local operation with another implementation, such as an HTTP-backed read. `91870-comments.md:1796–1806`.

Consequences:

1. **A late deny can misreport reality.** `gbrussich52` reproduced `await next(e); return {deny:"late"}` on 2.1.263: the file was written while the model received a rejection. This matches the staff-described responsibility boundary. `91870-comments.md:2429–2431`.

2. **Repeated `next(e)` is supported intentionally.** `poteat` names retry and backoff as uses. `gbrussich52` reports two actual tool dispatches with the **same tool-use ID**. **INFERRED:** IDs cannot safely be treated as exactly-once execution receipts. `91870-comments.md:1796–1800,2429–2431`.

3. **Not calling `next` is insufficient by itself to block safely.** A handler must return an accepted event-specific result. Invalid `tool.call` results cause route-around; a deliberate replacement must also satisfy the tool’s output schema. `91870-comments.md:2134–2143`.

4. **Empty-denial behavior changed.** `{deny:""}` reportedly allowed execution on 2.1.260, then blocked on 2.1.261. The later staff explanation uses presence—`result.deny === undefined`—rather than truthiness. Do not retain the older falsy-denial behavior as current. `91870-comments.md:1665–1677,1802–1806,2129–2143`.

5. **An empty object is not universally invalid.** The pinned diff mod intentionally returns `{}` after handling `command.run`. Result validity is **event-specific**, not one universal deny/result envelope. `mods/diff/hooks/register.ts:475–495`.

### D3. `$` is a mediated plugin capability interface, not an automatic sandbox for the agent’s effects

**STAFF:** lack of ambient I/O is an execution boundary, not merely a lint convention. `poteat` describes a Bun Worker around the plugin realm and a `node:vm` wrapper per plugin, while explicitly excluding that implementation arrangement from the contract. The contract is that plugins do not get ambient access such as importing `fs`. `91870-comments.md:1781–1786`.

This supersedes two community generalizations:

- `deafsquad`’s earlier **“the isolation is a linter”** criticism is not the final staff description. `91870-comments.md:848–850,1784–1786`.
- His earlier claim that **each module has its own worker** should not be used as an isolation guarantee; the later staff description specifies a different arrangement and says implementation details are not contractual. `91870-comments.md:1530,1786`.

**REPORT, `deafsquad`, 2.1.260:** `process`, `Bun`, `require`, `fetch`, `WebSocket`, `Worker`, and other ambient escape routes were unavailable; non-relative I/O imports were rejected. This supports a JS-level boundary, not an OS process sandbox against runtime vulnerabilities. `91870-comments.md:1756`.

**Critical scope limitation:** removing `fs` during `engine.create` blocked plugin filesystem calls while the model’s own `Write` tool still wrote the file. **This is a community runtime report, not a staff guarantee**, but it directly refutes interpreting noun withholding as automatically restricting every core tool effect. `91870-comments.md:1523`.

**INFERRED:** a policy against file writes must account for the tool paths that produce them. Withholding a plugin noun alone does not establish a policy over `Write`, shell subprocesses, and MCP servers. The thread’s repeated claim that typed Bash arguments eliminate shell-string bypasses is also unsupported: the command remains a shell string. `91870-comments.md:559,1123–1127,1406–1410,1523`.

A particularly useful pinned-source warning: the diff mod labels its `process.run` use read-only, yet its child environment deliberately permits a partial clone to **lazy-fetch** during Git reads. **INFERRED:** “read-only command” does not imply “no network”; a `$` audit sees the process invocation, not necessarily each child-process effect. `mods/diff/README.md:40–43`; `mods/diff/hooks/git/argv/git-child-env/git-child-env.ts:1–8`.

### D4. `$` parameterization, extension, and consumption have concrete constraints

**What parameterization means here**

- Admins can remove nouns during construction and intercept individual capability methods to allow, deny, rewrite, or audit operations. `91870-body.md:79,118`; `91870-comments.md:2244–2266`.
- **STAFF intent:** filesystem access should be broad by default, with administrators narrowing it by cwd or the model’s `Read` policy. This differs from `deafsquad`’s historical report of a project-fenced filesystem on 2.1.260. Treat it as an evolving boundary, not a contradiction that can be resolved by assuming either applies to every build. `91870-comments.md:1530,2246–2266`.
- Being listed in a capability registry does **not** prove availability in every hook. `yonatangross` reports `$.ui.log` absent inside `engine.create`. `91870-comments.md:2758`.

**How to extend `$`, generalized from telemetry**

The pinned telemetry mod:

1. Hooks `engine.create`.
2. Awaits `next(e)` to obtain the interface beneath it.
3. Constructs a new noun whose implementations close over selected methods of that lower interface.
4. Returns `{...beneath, telemetry: …}` without replacing existing nouns.  
   `mods/telemetry/hooks/register.ts:14–45`.

Its new methods call `beneath.session`, `beneath.http`, and `beneath.env` **later**, after the fold has finished. This is a concrete solution to composing a new capability out of existing capabilities. `mods/telemetry/hooks/register.ts:6–10,20–43`.

**Ordering nuance:** the telemetry README says the new noun is handed to plugins **above** it. “Downstream consumer” must not be confused with “registered later.” Construction unfolds from the inner interface outward. `mods/telemetry/README.md:3–5,34–35`.

**Replacement is different from extension.** `muloka` reports that returning a replacement `store` noun causes rejection—“to change what a method does, hook the method”—while adding `jj` succeeds. `91870-comments.md:2347–2355`.

**Type extension is separate from runtime extension.**

- The diff mod declares an `EngineInterface.telemetry` augmentation for standalone compilation. `mods/diff/hooks/telemetry-noun.d.ts:1–11,46–55`.
- That declaration does not make the runtime noun exist; its own comment explicitly says absent-provider calls throw. `mods/diff/hooks/telemetry-noun.d.ts:5–7`.
- `muloka` reports that `/plugin-types` on 2.1.263 did not collect plugin-added noun declarations, despite the architecture document’s stated intent. Automatic provider-declaration aggregation remains **UNVERIFIED** here. `91870-comments.md:2359–2363`.

**A provider need not know its caller.** Telemetry’s type documentation explicitly says the noun cannot see its caller, so callers include their identity in the event name. **INFERRED:** do not assume a custom noun’s implementation receives `next.origin` or automatic caller attribution. `mods/telemetry/hooks/telemetry-types/telemetry.ts:13–18`.

### D5. Static capability analysis changes how code must be structured

**STAFF:** arbitrary `$[expression]` access is rejected both during startup registration and manual validation. `91870-comments.md:1294–1296`.

**REPORT, 2.1.260:** source scanning rejects passing `$` to a helper, testing `$` with a logical expression, and other manipulations outside the allowed call spelling. `91870-comments.md:1525–1527`.

**SOURCE:** the diff mod demonstrates an allowed architectural pattern: create helper-facing closures such as `readFile: path => $.fs.read(path)`, while keeping literal `$` calls at their original call sites. Its `Host` type is then used by later hooks, timers, and UI actions. `mods/diff/hooks/register.ts:421–442`; `mods/diff/hooks/host/host.ts:14–18`.

**`validate` does not certify capability existence.**

- `poteat` explains that syntax-only validation accommodates dependencies that add nouns, and proposes dependency-aware checking as a possible improvement. `91870-comments.md:2242–2244`.
- `yonatangross` reports that nonexistent but syntactically valid names pass validation; it does not execute the real fold or reproduce skip behavior. `91870-comments.md:2733–2754`.

**INFERRED:** tooling needs separate evidence for syntax validation, typechecking, actual capability availability, and execution through the real engine. None substitutes for all the others. `91870-comments.md:2190–2209,2244,2619–2621,2752`.

### D6. `register`’s `options` parameter carries manifest `userConfig`

This is stated directly in the pinned source:

> “the options `register` receives are the manifest’s userConfig”

`mods/diff/hooks/backend/installed-backend-probes.ts:10–12`.

The same comment says the scanner requires `register` itself to be a **plain exported function**. The shipped diff mod’s implementation follows that form. `mods/diff/hooks/backend/installed-backend-probes.ts:10–12`; `mods/diff/hooks/register.ts:30–32`.

**INFERRED:** `options` is configuration input, not a channel for injecting executable backend probes or an alternate host implementation. That is why the diff source provides a separate compile-time backend-probe collection. `mods/diff/hooks/backend/installed-backend-probes.ts:4–15`.

**UNVERIFIED:** the exact `options` TypeScript type, defaulting rules, secret handling, and configuration-refresh lifetime. These mods do not consume a second parameter; the available source only identifies it as `userConfig`. `mods/diff/hooks/register.ts:32`; `mods/sec-default/hooks/register.ts:17`; `mods/telemetry/hooks/register.ts:14`.

### D7. Ordering is authority, but dependency direction and managed seating matter

**STAFF, September 11:** within the user tier, if **A depends on B, A registers before B**. Ordering is a topological sort honoring the user’s stated order where compatible; the exact deterministic algorithm was still TBD. This is **dependent-before-dependency**, an important distinction from ordinary initialization expectations. `91870-comments.md:3083–3092`.

**INFERRED:** this aligns with a capability provider being constructed beneath its consumers during `engine.create`. It also means a mod manager cannot implement an ordinary dependency-first loader and assume equivalent behavior. `91870-comments.md:3090`; `mods/telemetry/README.md:3–5`.

Additional authority rules:

- Registration order means configured order, **not installation chronology**. `poteat`: `91870-comments.md:226–229`.
- A downstream plugin cannot unregister or inhibit the already-enclosing admin hook. Refusals can be observed by an enclosing audit hook through `next`’s result. `poteat`: `91870-comments.md:180–189`.
- A hook cannot dynamically move itself to the bottom. `poteat` explicitly rules that out. `91870-comments.md:3094–3111`.
- Tier skipping preserves remaining hooks in the current managed tier; their requested skips combine to the **furthest inward target**. A request for core dominates another request for builtin. This extends “inward only” with the actual composition rule. `91870-comments.md:2595–2599`.
- **SOURCE:** `next.to` is refused outside managed tiers; loading `sec-default` through `--plugin-dir` cannot confer its managed authority. `mods/sec-default/README.md:42–55`.

**What “Outermost” means for `sec-default`**

The CLI normally seats it **first in prepend**, when hooks modules load on a machine with managed settings or for a Team/Enterprise organization. However, a managed `prependPlugins` setting replaces the **whole prepend list**. The administrator must name `sec-default@builtin`, choose its position, or intentionally omit it. `mods/sec-default/README.md:45–55`.

**INFERRED:** tooling that merely adds its own managed `prependPlugins` array can accidentally remove the default protection. The configuration must be treated as replacement, not additive registration. `mods/sec-default/README.md:49–52`.

**Can a user escape?** Inside the managed chain, lower-tier code lacks the relevant authority. Outside that chain, `poteat` explicitly says this work does not prevent editing local management files or running an unmanaged installation; those controls require endpoint management and OS support. `91870-comments.md:1298–1302`; `mods/sec-default/README.md:53–55`.

### D8. `sec-default` protects specific policy surfaces; it is not a universal tool guard

The source makes these distinctions:

| Surface | Protection |
|---|---|
| `classic.*` | Skip user-tier interception so configured classic hooks receive the protected input and their answers stand. `mods/sec-default/hooks/register.ts:20`; `mods/sec-default/README.md:26`. |
| `prompt.section`, `prompt.context`, `skill.prompt`, `attribution.text` | Skip user-tier rewriting. A user mod still retains `prompt.submit` and additive context. `mods/sec-default/hooks/register.ts:22–25`; `mods/sec-default/README.md:27`. |
| `settings.read` | Skip user-tier rewriting, including the security mod’s own reads. `mods/sec-default/hooks/register.ts:27`; `mods/sec-default/README.md:28`. |
| Describing tools/commands and offering/spawning agents | Protect subjects whose pinned provider belongs to managed tiers. A missing or unexpected provider also takes the protective branch. `mods/sec-default/hooks/register.ts:29–32`; `mods/sec-default/hooks/past-users/past-users.ts:8–22`. |
| `tool.register` | Managed callers skip users; user callers are refused when an `allowedMcpServers` array exists, including an empty array. `mods/sec-default/hooks/register.ts:34–49`; `mods/sec-default/hooks/policy/has-mcp-allowlist.ts:3–11`. |
| `tool.list` | Obtain both managed-only and ordinary listings; preserve managed-server tools from the former and other tools from the latter. On unreadable policy or a refusal from either listing, retain the managed listing whole. `mods/sec-default/hooks/register.ts:52–59`; `mods/sec-default/hooks/policy/managed-tools-restored/managed-tools-restored.ts:17–32`. |
| `tool.call`, `tool.check`, execution/UI/I/O surfaces generally | Explicitly pass through. The mod does not add its own general execution policy. `mods/sec-default/README.md:32`. |

Two further design details:

- **Caller identity and subject provenance are different:** `next.origin.tier` governs the caller-sensitive registration decision; pinned `e.provider.tier` governs who supplied a tool, command, or agent. `mods/sec-default/hooks/register.ts:29–49`; `mods/sec-default/hooks/past-users/provided/provided.ts:1–8`.
- Policy reads share a **500 ms** memo window, including rejected reads. The source explicitly says changes can wait that long to be observed. `mods/sec-default/hooks/policy/policy-memo-ms.ts:1–7`; `mods/sec-default/hooks/policy/create-policy-memo/create-policy-memo.ts:3–26`.

**INFERRED:** the built-in’s local fail-closed decisions do not establish that the engine will fail closed if the whole hook times out or its module never becomes active. Those are distinct layers. `mods/sec-default/hooks/policy/decided-by-policy.ts:3–15`; `91870-comments.md:2688–2699`.

### D9. Redaction has both a placement problem and an introspection problem

**STAFF:** managed appending places a redactor near the core result, letting it remove data before higher plugins receive that result. `91870-comments.md:2269–2279`.

But `poteat` identifies **`next.trace` snapshots as an additional sensitive surface** and proposes listing trace usage in validation and `plugin.register` metadata so administrators can reject untrusted readers. `91870-comments.md:2281`.

**UNRESOLVED:** a prepended `next.to(...,"core")` can skip an appended redactor. `Spencer-Morley` asks for separate placement and skip authority, or an unskippable floor; the corpus does not contain a direct resolution of that request. `91870-comments.md:2636–2642,2717–2719`.

**INFERRED:** “the result was redacted” is insufficient evidence for “no plugin saw the original.” Placement, skipped tiers, trace access, and other readable capabilities must all be considered. `91870-comments.md:2279–2281,2638–2640,2793`.

### D10. Component hooks expose declared surfaces, not arbitrary React internals

**STAFF:** each surface declares:

- its primitive element vocabulary; and
- its product components that can be wrapped, modified, or replaced.

The internal **permission-request component is not declared hookable**. `91870-comments.md:1788–1794`.

The body additionally specifies changing component props or wrapping returned render nodes. `91870-body.md:69–71`.

Concrete surfaces in this corpus:

| Component/element | Evidence and limit |
|---|---|
| `PromptHint` | Actual diff render hook reads viewport width and delegates. `mods/diff/hooks/register.ts:447–453`. |
| `Pane` | Actual diff hook filters `requestId`, checks the surface, resolves elements, reads focus/body width, and returns its own pane rendering. `mods/diff/hooks/register.ts:455–473`. |
| `AbovePrompt` | `TweedBeetle` reports a working terminal hook on 2.1.261 rendering links and a button. `91870-comments.md:2063–2065`. |
| `ToolUse`, `AskUserQuestion` | Named as render targets in community discussion of the architecture document; the supplied mod implementation does not exercise them. `91870-comments.md:1165,1881,2063`. |
| `Box`, `Text`, `Button`, `Select` | The diff mod obtains these through `$.ui.resolve(e)`; these are elements, not four additional event names. `mods/diff/hooks/register.ts:460–468`. |
| `Link` | Community report describes an HTTPS/localhost URL restriction and terminal rendering. Current universal URL rules are **UNVERIFIED**. `91870-comments.md:2063–2065`. |

**Surface parity is not universal.** The pinned diff types say terminal and desktop supply all four required elements, while mobile lacks `Select`; the implementation excludes mobile. `mods/diff/hooks/views/kit/ui/ui.ts:3–13`; `mods/diff/hooks/is-on-pane-surface/is-on-pane-surface.ts:3–12`.

**Independent redraw is concretely supported by the mod design.** Timers and callbacks mutate mod state, then invalidate `ui.render`; the pane is not confined to the original tool dispatch. `mods/diff/hooks/register.ts:108–119,164–190,325–383`; `mods/diff/hooks/host/host.ts:77–100`.

**Originating a question:** `poteat` says there ought to be `$.ui.ask`; no supplied built-in uses it. Headless fallback and subagent interaction semantics remain **UNVERIFIED**. `91870-comments.md:1879–1885,2070–2074,2104`.

### D11. Concurrency is programmable; cancellation is cooperative

The community’s broad claim that all function-hook work must serialize was later corrected by staff:

- Start `next(e)` early, perform local work, then join the result: work can overlap.
- A transform of the downstream result must await that result.
- Parallel **guards** should use a checking surface such as the proposed `tool.check`, because `tool.call`’s core is the actual execution.  
  **`poteat`:** `91870-comments.md:3019–3039`.

**Do not convert this into a shipped `tool.check` guarantee.** `sirmaelstrom` could not find it in 2.1.267 declarations. The pinned `sec-default` README names it as a pass-through event, but supplies no implementation or signature. `91870-comments.md:3075–3080`; `mods/sec-default/README.md:32`.

**Abandonment does not cancel outstanding work automatically.** Plugins still own it, may continue calling `$`, and may keep floating asynchronously; `next.signal` says the return value is no longer wanted. `poteat`: `91870-comments.md:3115–3119`.

**INFERRED:** concurrent guards need explicit ownership of downstream promises and cancellation-aware I/O. The final comment asks who observes a downstream rejection occurring after an outer deny; it receives no answer in this corpus. `91870-comments.md:3122–3127`.

### D12. Subagent visibility, identity, and completion are separate capabilities

**STAFF:** `tool.call` sees calls made inside subagents in the internal prototype. `91870-comments.md:2290–2295`.

That does **not** settle all launch routes:

- **REPORT, `jdainsworthsnb`:** a background-dispatched agent’s `tool.call` was visible, but `agent.spawn`, `turn.start`, and `turn.step` did not fire for it; `agent.list` was empty, and session metadata matched the parent. The report used an ordinary Agent-tool dispatch as a positive control. `91870-comments.md:1820–1857`.
- **REPORT, `frsorrentino`, 2.1.260:** `AgentSpawnInput` pinned `tool_use_id`, `fork`, `parentModel`, and `permissionMode`; rewritable fields included `model`, `subagentType`, `prompt`, `background`, and `cwd`, but not effort. A plugin-originated `$.agent.spawn()` resolved with `{model,text,isError}`. `91870-comments.md:1380–1384`.
- The same author requested guaranteed `agent.complete` coverage for every spawn route, including aborts, fatal errors, workflow agents, forks, teammates, and background sessions. The corpus does not establish that guarantee. `91870-comments.md:1325–1329`.

**INFERRED:** the established `agentId` field answers a naming question; it does not by itself prove complete dispatch ancestry, spawn coverage, or completion accounting. The independent gaps above still require validation. `91870-comments.md:1327,1830–1857,2812–2819`.

Other isolation/concurrency details:

- **REPORT, `deafsquad`, 2.1.260:** simultaneous engine tool calls both entered a guard while another invocation was active. Re-entry suppression followed dispatch lineage rather than a global “hook busy” flag. `91870-comments.md:1521`.
- **REPORT, `muloka`, 2.1.263:** nested dispatch suppressed the **provider plugin’s own hooks**, so its custom noun behaved differently when called by itself versus another plugin. The pinned telemetry implementation supplies a different construction pattern over captured lower capabilities, but does not prove that re-entry semantics changed. `91870-comments.md:2345–2357`; `mods/telemetry/hooks/register.ts:15–44`.
- **Worktree metadata:** `muloka` found `session.repo` insufficient for Jujutsu workspaces and reported that its `root` describes the main worktree. The pinned diff mod independently resolves working-tree top, worktree Git directory, and common Git directory. `91870-comments.md:2326–2343`; `mods/diff/hooks/git/probes/repository-of/repository-of.ts:6–35`.

## SHAPES — findings that determine implementation and tooling

### S1. Complete event-name inventory found in this corpus

**This is a provenance-labelled inventory, not a claim that one build exposes every name below.** The only explicit historical full registries in the comments describe **2.1.263**; later source adds or renames surfaces. `91870-comments.md:2761–2791`; `mods/diff/README.md:28–43`; `mods/sec-default/README.md:26–38`.

#### Historical engine-event registry: all 20 names

`Spencer-Morley` corrected his initial truncated extraction and published this complete list; `yonatangross` independently identified the omitted `ui.select`. **REPORT, static extraction:** `91870-comments.md:2756,2761–2777`.

| Family | Exact names | Anchor |
|---|---|---|
| Compatibility | `PreToolUse` | `91870-comments.md:2773` |
| Tools | `tool.call`, `tool.describe` | `91870-comments.md:2773–2775` |
| Rendering/interactions | `ui.render`, `ui.resolve`, `ui.press`, `ui.input`, `ui.select` | `91870-comments.md:2773` |
| Agents | `agent.offer`, `agent.spawn` | `91870-comments.md:2774` |
| Prompts | `prompt.submit`, `prompt.section`, `prompt.context` | `91870-comments.md:2774` |
| Skills/attribution | `skill.prompt`, `attribution.text` | `91870-comments.md:2775` |
| Session | `session.start` | `91870-comments.md:2775` |
| Turns | `turn.start`, `turn.step`, `turn.complete` | `91870-comments.md:2775–2776` |
| Construction | `engine.create` | `91870-comments.md:2776` |

#### Historical capability-operation registry: all 36 names

These were published separately from the engine-event array. The issue body says wildcard observation includes plugin calls on `$`. **Do not omit these from an audit just because they are described as capabilities.** `91870-body.md:116–118`; `91870-comments.md:2779–2789`.

| Family | Exact names | Anchor |
|---|---|---|
| Model | `model.complete`, `model.classify`, `model.fork` | `91870-comments.md:2782` |
| Audio | `audio.play`, `audio.speak` | `91870-comments.md:2782` |
| MCP | `mcp.call` | `91870-comments.md:2782` |
| Session | `session.cwd`, `session.model`, `session.turnCount`, `session.id`, `session.messages`, `session.repo`, `session.surface`, `session.authorize` | `91870-comments.md:2783–2784` |
| Turn/flags | `turn.abort`, `flag.value` | `91870-comments.md:2784` |
| Tool inventory | `tool.list`, `tool.register` | `91870-comments.md:2785` |
| Agent inventory | `agent.list` | `91870-comments.md:2785` |
| UI effects | `ui.toast`, `ui.status`, `ui.log`, `ui.notice`, `ui.invalidate` | `91870-comments.md:2785–2786` |
| Filesystem | `fs.readFile`, `fs.writeFile`, `fs.listDir`, `fs.exists`, `fs.stat`, `fs.ancestors` | `91870-comments.md:2786–2787` |
| Persistence | `store.get`, `store.set`, `store.delete`, `store.keys` | `91870-comments.md:2787` |
| External execution/I/O | `http.fetch`, `process.run` | `91870-comments.md:2787–2788` |

#### Additional names in the pinned mods or later staff discussion

| Exact names | Evidence/status |
|---|---|
| `command.run` | Actual registrations for `diff`, `clear`, and `resume`. `mods/diff/hooks/register.ts:475–512`. |
| `command.register` | Actual capability call. `mods/diff/hooks/register.ts:439`. |
| `command.describe` | Actual registration. `mods/sec-default/hooks/register.ts:30`. |
| `settings.read` | Actual registration and capability call with `{source:"policy"}`. `mods/sec-default/hooks/register.ts:27,45`; `mods/sec-default/hooks/policy/source.ts:1–4`. |
| `fs.read`, `fs.list` | Actual current-source calls replacing historical spellings. `mods/diff/hooks/register.ts:428–430`. |
| `ui.open`, `ui.close` | Actual current-source calls. `mods/diff/hooks/register.ts:437–438`. |
| `env.get` | Actual lower-interface calls in `engine.create`. `mods/telemetry/hooks/register.ts:24–42`. |
| `telemetry.log`, `telemetry.mark` | Plugin-defined noun operations and actual consumer calls. `mods/diff/hooks/register.ts:440–441`; `mods/telemetry/hooks/telemetry-types/telemetry.ts:11–50`. |
| `clock.now`, `clock.after`, `clock.every`, `clock.sleep` | Actual affordance calls. **The source proves these methods exist; it does not separately prove every clock helper can be registered as an intercepted event.** `mods/diff/hooks/register.ts:423–426`; `mods/diff/hooks/host/host.ts:19–37`. |
| `tool.check` | Staff’s forthcoming checking surface; named in pinned README, unused by these implementations. Full runtime contract **UNVERIFIED**. `91870-comments.md:3026–3039,3080`; `mods/sec-default/README.md:32`. |
| `plugin.register` | Staff calls it a core concept and wants static-effect metadata on it; concrete full signature and shipped coverage **UNVERIFIED** here. `91870-comments.md:479–480,2281`. |
| `ui.ask` | Staff intent, not demonstrated implementation. `91870-comments.md:2070–2074`. |
| `audit.record`, `jj.ctx` | Community-created custom events demonstrated by `muloka`; not core names. `91870-comments.md:2347–2353`. |

#### Wildcards and compatibility names

- **`*`** observes all events, including plugin `$` calls. `91870-body.md:116–118`.
- **`classic.*`** is an actual pinned-source registration. **`classic.PreToolUse`** is explicitly named by staff as part of a 1:1 compatibility family. `mods/sec-default/hooks/register.ts:20`; `91870-comments.md:2581–2593`.
- **`prompt.*`, `turn.*`, `session.*`, `ui.*`, `fs.*`, `store.*`, `clock.*`, `model.*`, `audio.*`** occur as family spellings. They are not additional concrete event names. `91870-comments.md:1321`; `mods/sec-default/README.md:32`.
- Concrete **classic lifecycle names** found: `PreToolUse`, `PostToolUse`, `SessionStart`, `UserPromptSubmit`, `SessionEnd`, `PermissionRequest`, `Stop`, `PreCompact`, `PostCompact`, `SubagentStop`, `ConfigChange`, `FileChanged`, `Notification`, `PostToolUseFailure`, `StopFailure`, `SubagentStart`, `PreModelSwitch`, `PostModelSwitch`, `PermissionDenied`. The comments do not individually demonstrate all of their `classic.<name>` counterparts. `91870-comments.md:12,89–95,280,576,620,719–726,1725–1748`.

#### Requested or illustrative names that must not become “supported events”

| Names | Status and anchor |
|---|---|
| `schedule`, `session.focus`, `session.blur`, `session.title`, `terminal.title` | Community requests. `91870-comments.md:271,655–664`. |
| `turn.tools` | Proposed batch-level event. `91870-comments.md:341`. |
| `permissions.classify`, `permissions.decide` | Proposed permission interfaces. `91870-comments.md:364,1131`. |
| `model.call` | Proposed spelling; the historical registry instead lists `model.complete`. `91870-comments.md:986,2782`. |
| `ui.update` | Requested independent update primitive. `91870-comments.md:1110–1117`. |
| `agent.complete`, `session.rateLimits`, `session.context`, `session.resume` | Requested lifecycle/accounting interfaces. `91870-comments.md:1327–1333`. |
| `dispatch.current`, `session.platform`, `session.compact`, `hook.error` | Requested identity, portability, compaction, and failure interfaces. `91870-comments.md:1838,1941,1866,2163`. |
| `perm.allowed`, `proc.spawn`, `process.spawn`, `fs.write` | Illustrative/proposed spellings, not established names in the supplied registries. `91870-comments.md:109,168,792–798,1979`. |
| `banana.PreToolUse`, `zzz.nope`, `zzz.not.an.event`, `doesnt.exist`, `whatever` | Deliberately nonexistent validation examples or placeholders. `91870-comments.md:2285,2748–2752,2851`. |

### S2. `turn.step` has a distinct streaming contract

**STAFF, September 11:** a `turn.step` handler must be an **async generator**, can transform each streamed chunk, and returns the downstream stream’s final result. The example preserves non-text chunks and text indices. `poteat` says this is the only hook that yields this way. `91870-comments.md:3094–3111`.

**INFERRED:** a generic hook adapter that assumes every handler returns a promise is incomplete. It needs a streaming path that preserves both yielded values and terminal results. `91870-comments.md:3096–3108`.

### S3. Prompt rewriting, context, commands, and turn blocking are distinct surfaces

- **STAFF:** when a tool input is rewritten, the model retains what it originally requested for prompt-cache reasons. A contextual explanation should tell it what changed. Requiring such context was supported as an idea, not established as a shipped type invariant. `91870-comments.md:238–243,369–370`.
- **SOURCE:** diff appends to `prompt.submit`’s returned `context` array, preserving existing context; it leaves a dropped prompt alone and consumes its armed file only after acceptance. `mods/diff/hooks/register.ts:554–566`.
- **REPORT, `muloka`:** `prompt.context` receives named text blocks, including `claudeMd`, and can run once or twice per headless turn. **INFERRED:** external reads/injections there should tolerate repeated execution. `91870-comments.md:2365–2367`; also `91870-comments.md:1930`.
- **STAFF:** `prompt.submit` is deliberately for direct model text. Commands/skills belong on **`command.run`**; `poteat` committed to improving the error message accordingly. This supersedes the earlier “no command door” assumption. `91870-comments.md:2379–2386,2968–2972`.
- **REPORT:** `turn.complete` could append display text but could not implement classic Stop’s blocking behavior. Current parity remains **UNVERIFIED**; the pinned diff mod only observes and delegates. `91870-comments.md:1339,1937`; `mods/diff/hooks/register.ts:546–552`.

### S4. Classic hooks have an address inside the new model

**REPORT, `gbrussich52`, 2.1.261:** personal settings’ Pre/PostToolUse hooks execute inside `tool.call`’s `next(e)`; when the function hook refuses before delegating, those classic hooks do not run. `91870-comments.md:2145–2155`.

**STAFF, later:** `classic.*` wraps existing shell hooks with the same input/output interface. The pinned security mod actually registers that wildcard. `91870-comments.md:2581–2593`; `mods/sec-default/hooks/register.ts:20`.

The transition matters: on 2.1.263, `Spencer-Morley` found `classic.PreToolUse` unresolved while bare `PreToolUse` worked. The pinned mod source is evidence of the later API expectation, not grounds to erase the earlier incompatibility. `91870-comments.md:2703–2719`; `mods/sec-default/hooks/register.ts:20`.

### S5. Persistent state and concurrency remain the mod’s responsibility

- **REPORT, `frsorrentino`:** store data was a per-plugin JSON file under `~/.claude/plugins/store/`, with machine scope and no compare-and-set. That is a historical report, not a complete current storage contract. `91870-comments.md:1337,1383`.
- **SOURCE:** diff keeps mutable session/UI state in the `register` closure; it implements refresh exclusion, a queued refresh flag, generation-based stale-result protection, timer cancellation, and redraw coalescing itself. `mods/diff/hooks/register.ts:32–49,108–119,145–157,193–255`.
- **SOURCE:** telemetry serializes its outbound rows with a promise queue and catches failures on the queue tail so one rejected send does not poison later sends. The individual caller still receives its own rejection. `mods/telemetry/hooks/telemetry-of/telemetry-of.ts:17–18,59–71`.

**INFERRED:** shared in-process state reduces filesystem IPC, but does not supply atomicity, cross-session locking, or race-free refreshes automatically. `91870-comments.md:1337,1383`; `mods/diff/hooks/register.ts:193–255`.

### S6. Telemetry is an internal optional provider, not a general external analytics SDK

The pinned README is explicit:

- The CLI seats telemetry only on **internal builds** where its own analytics are enabled.
- `session.authorize` exists only there.
- The folder is not intended to be loaded standalone with `--plugin-dir`.
- Consumers should treat the missing noun as “no analytics here.”  
  `mods/telemetry/README.md:43–51`.

Its operational contract:

- One POST per call, no batching or retry; each call rechecks the environment and obtains fresh authorization. `mods/telemetry/README.md:9–20`; `mods/telemetry/hooks/telemetry-of/telemetry-of.ts:20–56`.
- `log` produces `tengu_plugin_<event>`; `mark` produces `tengu_feature_<kind>`. `mods/telemetry/README.md:5–9`.
- Event/key tokens have a 64-character pattern limit; at most **16 properties** and **32 Choice members**; values are finite numbers, booleans, or explicitly enumerated Choice strings. `mods/telemetry/hooks/entries/token/token.ts:1–5`; `mods/telemetry/hooks/entries/prop-limit/prop-limit.ts:1–4`; `mods/telemetry/hooks/entries/choices-limit/choices-limit.ts:1–4`; `mods/telemetry/hooks/entries/checked-value/checked-value.ts:17–64`.
- `mark` requires a reason for `sad`/`bad` and forbids it for `ok`; the TypeScript `reason?` field alone does not enforce that relationship. Runtime validation does. `mods/telemetry/hooks/telemetry-types/mark-entry/mark-entry.ts:7–11`; `mods/telemetry/hooks/entries/checked-mark.ts:30–45`.
- `DISABLE_TELEMETRY` and `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` treat any nonempty value, **including `"0"`**, as set; `DO_NOT_TRACK` and provider switches use truthy spellings. `mods/telemetry/hooks/is-analytics-off/is-analytics-off.ts:16–31`; `mods/telemetry/hooks/is-analytics-off/is-env-set/is-env-set.ts:1–9`; `mods/telemetry/hooks/is-analytics-off/is-env-truthy/is-env-truthy.ts:1–9`.
- Diff deliberately catches both synchronous missing-noun errors and asynchronous telemetry rejection, dropping the row. **INFERRED:** this optional analytics path is unsuitable as proof of mandatory audit delivery. `mods/diff/hooks/record/safely/safely.ts:1–10`.

### S7. API churn is explicitly permitted; several important changes are visible

| Change | Evidence |
|---|---|
| `fs.readFile` → `fs.read` | Staff announces the rename as “pre-contract”; later source uses `fs.read`. `91870-comments.md:2572–2577`; `mods/diff/hooks/register.ts:430`. |
| `fs.listDir` → source usage of `fs.list` | Historical registry versus pinned call site. A general migration policy is not supplied. `91870-comments.md:2786–2787`; `mods/diff/hooks/register.ts:429`. |
| `next.origin`: string → object with tier | Staff announces the change; pinned security source uses `.tier`. `91870-comments.md:2844–2849`; `mods/sec-default/hooks/register.ts:35–43`. |
| Bare compatibility event → `classic.*` family | Historical runtime discrepancy versus staff plan and pinned registration. `91870-comments.md:2703–2719`; `mods/sec-default/hooks/register.ts:20`. |
| Error handling design | Whole-chain fallback → individual route-around → proposed registration-level `.catch`. `91870-comments.md:674,770,2851–2853`. |
| Declaration and static registries grow | Historical lists omitted/newly exposed operations; generated counts varied by version and environment. Treating an old list as complete is unsafe. `91870-comments.md:1376,2359–2363,2756–2791`. |

**SOURCE:** APIs may change between releases **without notice** during early access. The three published mods are not marketplace entries; their built-in copies are the relevant deployment artifacts. `mods/README.md:21–24`.

### S8. Performance claims require separating dispatch, work, and ordering

- **STAFF:** `poteat` reported an internal p99 around **50 μs per hook**. No benchmark harness or stable performance guarantee accompanies that claim. `91870-comments.md:483–484`.
- **REPORT:** pass-through hooks were inexpensive, but eight sequential 300 ms waits took roughly 2.4 seconds, compared with roughly 640 ms for parallel command hooks on one Windows machine. `91870-comments.md:1489–1503`.
- The author of the original “1.9 seconds per tool call” claim retracted it because classic hooks ran in parallel. Other comments also retract universal Windows spawn estimates. `91870-comments.md:816–823,1455–1474,1651–1654`.
- The staff concurrency recipe later narrows the unavoidable serialization to work that actually depends on downstream results; it does not make early execution of `tool.call` safe for parallel vetoes. `91870-comments.md:3024–3039`.

**INFERRED:** benchmark the intended control flow and actual policy work; multiplying a dispatch benchmark or a process-start figure by hook count is not a reliable migration forecast. `91870-comments.md:502–504,1503,3024–3039`.

## CONTEXT — roadmap and evidence-quality facts

1. **Shipping commitment:** on September 9, `poteat` committed to shipping on a timescale of **weeks**, while still iterating. No exact release date was promised. `91870-body.md:1–13`.

2. **Migration of core features:** staff intends to move additional existing Claude Code features into mods. The published three are a starting set, not the intended endpoint. `91870-body.md:9`.

3. **Cross-surface ambition:** supporting any surface powered by the binary was described as `poteat`’s **personal goal**, not a delivered parity guarantee. `91870-comments.md:674–676`.

4. **No new dependency/signing system promised:** existing plugin dependency/version mechanisms were intended to remain unchanged. A new signature or runtime byte-integrity guarantee was not committed. `91870-comments.md:1287–1292`.

5. **Observability commitments remain qualified:** staff wanted good OTEL support on day one and bespoke HTTP export; `next.trace` was proposed to expose timings and immutable event/return snapshots below the caller. Neither statement establishes durable audit delivery or a shipped trace contract. `91870-comments.md:1306–1308,1351–1364`.

6. **Public testing machinery was not promised:** staff prioritized narrow types, but only said he would consider exposing the composition mechanism. The later community request for real dispatch testing remained unresolved. `91870-comments.md:1360–1364,2616–2621`.

7. **Minimal syntax is deliberate:** `poteat` prefers direct continuations over separate before/after/around combinator spellings. Community ordering metadata or a mod manager was suggested as the likely ecosystem answer, not announced as an Anthropic product. `91870-comments.md:3090–3092,3113`.

8. **Several apparently strong findings were withdrawn.** The supposed 8,000-character/200-line live context cap came from unreachable constants; “two rewrites cause neither to apply” came from trusting model text; a model detour after denial was withdrawn as too weakly sampled. Those must not enter the graph as unqualified facts. `91870-comments.md:2011–2038,1631–1649,2416–2427`.

# B. Third-party artifacts

**Ingestion judgments below are INFERRED priorities.** Descriptions are what the commenters say; repository contents were not inspected.

| Artifact / URL | What it is; ingestion judgment | Evidence |
|---|---|---|
| [AdityaRon/claude-code-harness](https://github.com/AdityaRon/claude-code-harness) | Existing security/audit/context command-hook stack. **YES**, as a migration baseline with documented limitations. | `91870-comments.md:11–20` |
| [Monte9/claude-function-hooks](https://github.com/Monte9/claude-function-hooks) | Independent executable interpretation of the architecture, initially 17 tests. **YES, high value**, clearly labelled third-party semantics. | `91870-comments.md:781–813` |
| [Monte9 prototype issues/repros](https://github.com/Monte9/claude-function-hooks/issues) | Adversarial matcher, continuation, re-entry, and immutability cases. **YES**, paired with the later real-engine corrections. | `91870-comments.md:1007–1056,1660–1679` |
| [cvuijst/cc-function-hooks-poc](https://github.com/cvuijst/cc-function-hooks-poc) | Working inbox watcher, API catalogue, sandbox notes, debug evidence. **YES, highest practical priority.** | `91870-comments.md:2044–2053` |
| [cwschroeder/buzz-agent-comms](https://github.com/cwschroeder/buzz-agent-comms) | Team-channel coordination plugin; explored deterministic publication and completion gates. **YES**, for completion/lifecycle requirements. | `91870-comments.md:1924–1943` |
| [akshaypimprikar/pragma](https://github.com/akshaypimprikar/pragma) | iOS workflow plugin with ten deterministic PR gates currently invoked by an agent turn. **YES, secondary**, as a governance migration case. | `91870-comments.md:2801–2806` |
| [PromptSign/spec](https://github.com/PromptSign/spec) | Signing/verification for skills, agent definitions, and instructions. **YES, high value**, for artifact identity and load-time integrity. | `91870-comments.md:3042–3053` |
| [microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit) | Named source of `agt-governance`; commenter describes an audit-integrity failure blocking its own diagnostic path. **YES**, targeted recovery-design study. URL expands the owner/repo given in the comment. | `91870-comments.md:1814` |
| [get-bb/bb](https://github.com/get-bb/bb) | IDE cited for user-authored extensions. **NOISE for this API audit**; optional comparative UX research. | `91870-comments.md:508–526` |
| [GNU Emacs advice documentation](https://ftp.gnu.org/old-gnu/Manuals/elisp-manual-21-2.8/html_node/elisp_212.html) | Prior-art reference for wrapping functions. **YES, low priority**, for conceptual lineage; not Claude runtime evidence. | `91870-comments.md:3056–3068,3113` |
| [lyricalpolymath’s UX ideas](https://x.com/lyricalpolymath/status/2095615161088319939?s=20) | UI feature wishlist. **NOISE** for implementation semantics. | `91870-comments.md:514–525` |

Named or inline artifacts without a supplied repository URL:

| Artifact / available locator | Judgment | Evidence |
|---|---|---|
| [OrchestKit discussion](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5530551063) | **YES if source becomes available:** large TypeScript hook bundle and CI registration-closure tests. | `91870-comments.md:161–177` |
| [HOE — Hook Overhead Elimination](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5531626481) | **YES, targeted:** resident dispatcher, shared state, cross-realm forwarding; preserve later performance retractions. | `91870-comments.md:430–475,816–844` |
| [fable-director discussion](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5540419526) | **YES:** cost governance, usage splits, missing agent completion, persistent budget state. | `91870-comments.md:1320–1386` |
| [HarnessKit discussion](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5552061734) | **DEFER:** named project, little inspectable artifact detail. | `91870-comments.md:1999–2008` |
| [Anchorwatch discussion](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5573650378) | **YES if source supplied:** guardrails plugin and migration/test requirements. | `91870-comments.md:2558–2569` |
| [Inline typed-slot HookPipeline proposal](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5543504218) | **LOW VALUE / speculative:** alternative composition design, not a measured Claude implementation. | `91870-comments.md:1551–1588` |
| [Jujutsu/provider probes](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5560929565) | **YES, high value if attached:** custom-noun self-consumption, VCS metadata, generated-type gaps. | `91870-comments.md:2321–2372` |
| [Transcript redactor](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5575582198) | **YES if code/repros supplied:** allowlist-based redaction with a post-transform leakage check. Present numbers are author claims. | `91870-comments.md:2608–2613` |
| [numbat / hookify / ai-plugins / remember / claude-security inventory](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5534842139) | **DEFER:** named tools in a benchmark table, without resolvable repository identities in this corpus. | `91870-comments.md:959–980` |
| [latex-style-check proposal](https://github.com/anthropics/claude-code/issues/91870#issuecomment-5571001352) | **NOISE as an existing implementation:** proposed mod, not an attached artifact. | `91870-comments.md:2454–2472` |

The anonymous dashboards, brain services, private guards, and comparative references to pluggy/WordPress/Drupal/Kong/SES/Atom are useful **requirements or prior art**, but do not identify additional fetchable implementations here. Placeholder URLs such as `example.com` and `policy.internal` are not artifacts. `91870-comments.md:850,898,919,1762–1777,2056–2065,2831–2839`.

# C. Open questions / unresolved risks

| Risk | Unanswered or only partly answered |
|---|---|
| **Recovery and failure contract** | Did registration `.catch`, grace budgets, typed failures, and external hook-health events ship? How does the runtime treat a failed `engine.create` across all failure modes? Staff proposal and community requests do not establish the complete contract. `91870-comments.md:2851–2853,2670,2697–2699`. |
| **Late rejection ownership** | Who observes a downstream promise rejection after the outer hook has returned a deny? This is the thread’s final unanswered question. `91870-comments.md:3122–3127`. |
| **Durable audit evidence** | Are records durably committed before execution? What survives process death, partial effects, retries, or a swallowed exception? `alhe99` and `DolphusCY` asked directly. `91870-comments.md:1062–1100`. |
| **All agent routes and terminal states** | Complete identity/ancestry, guaranteed completion after errors/aborts, workflow/fork/teammate coverage, effort control, and usage accounting remain unsettled. `91870-comments.md:1325–1333,1820–1857,2812–2819`. |
| **Guard placement versus skip authority** | Can a near-core redactor remain compulsory when a managed outer hook skips tiers? No documented floor or separate authority/placement mechanism is established. `91870-comments.md:2636–2642`. |
| **Real CI execution harness** | No supplied public dispatcher import or CLI synthetic-event runner exercises actual skip, continuation, cancellation, and streaming behavior. Static validation explicitly does not do this. `91870-comments.md:2616–2621,2752,2983`. |
| **State scope and atomicity** | Cross-session/cwd/machine storage, compare-and-set, locks, and module-state lifetimes across resume/config changes remain incompletely specified. `91870-comments.md:174,1116–1117,1337,1383`. |
| **Context and cost control** | Free context-window/quota access, full usage on completions, model-call billing, direct compaction, and a blocking turn-completion equivalent remain unconfirmed. `91870-comments.md:1325–1339,1864–1868,2386–2395`. |
| **Artifact integrity at use time** | Plugin root/digest metadata, skill-load interception, documented host-owned cache files, and protection against reviewed bytes changing before use were requested without a subsequent answer. `91870-comments.md:3042–3053`. |
| **Mandatory installation and recovery** | Repository-required hooks, a non-plugin function-hook authoring path, and a documented safe mode outside a broken guard’s chain remain unanswered. `91870-comments.md:1814–1816,2370,2985`. |
| **UI coverage and headless behavior** | Images/media, Desktop-native chat coverage, focus events, and an ask operation’s headless fallback remain unverified. `91870-comments.md:1113–1114,1767–1773,2104`. |
| **Contract versioning and discovery** | No established contract-version pin, automatic collection of custom noun declarations, complete current event catalogue, or specified dependency-cycle/conflict behavior is supplied. `91870-comments.md:2359–2363,2863–2867,3090`. |
| **Rewrite and permission interaction** | A current end-to-end contract for rewritten tool inputs versus classifier/permission evaluation was explicitly requested and not answered. Parsed Bash intent/argv requests likewise remain requests. `91870-comments.md:1982–1986,2907–2910`. |

*Method limitation:* this was an offline source audit, not a new runtime probe. Required graph orientation was unavailable: the direct command was blocked by the repository hook, and the mise wrapper failed read-only temporary-file creation with `Operation not permitted`, also reporting a tool-purgatory cleanup warning. No graph-health or runtime-validation claim is made.


---

# ADDENDUM — repos the Astra lane surfaced that my searches did not

These come from the issue comments, not from the four-index sweep, and are additive to
section 4:

| repo | why | lane anchor |
|---|---|---|
| [akshaypimprikar/pragma](https://github.com/akshaypimprikar/pragma) | iOS workflow plugin, ten deterministic PR gates currently run by an agent turn — a governance-migration case | `:2801-2806` |
| [microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit) | source of `agt-governance`; an audit-integrity failure that blocked its own diagnostic path | `:1814` |
| [PromptSign/spec](https://github.com/PromptSign/spec) | signing/verification for skills and agent definitions — load-time artifact integrity | `:3042-3053` |

Discussed in the thread with **no fetchable repository** (do not chase these as URLs):
OrchestKit's hook bundle, **HOE (Hook Overhead Elimination)**, fable-director, HarnessKit,
Anchorwatch's guardrails plugin, a transcript redactor, and a Jujutsu/provider probe set.
The lane marks each with the comment permalink; several are worth requesting from their
authors rather than searching for.

# WHAT I COULD NOT VERIFY

Stated explicitly rather than filled in:

1. **I did not run any ingestion command.** Every `mise run …` in section 2 is proposed.
   The `kb-add`-cannot-fetch finding rests on reading `graphify/ingest.py:65-82` and
   `:230-256`, not on a failed run.
2. **I did not transcribe a video.** `.mp4` acceptance rests on `transcribe.py:11`.
3. **I did not open the architecture PDF.** I established only that `kb-add` would
   misclassify it. Its contents are unread by me; the lane read only what the comments
   quote of it.
4. **I did not read the cheat-sheet image.** It needs a vision read; I have only the body's
   description of it (*"affordances on v267/v268"*).
5. **Whether the shipped engine pins `next.origin` or trusts the caller** (D4/X-risk) — the
   single most security-relevant open question here. `poteat` said on 2026-09-08 he was
   *changing it from a string to an object*; the object form is shipped, but nothing I read
   states whether it is forgeable.
6. **`tool.check`'s shipped status is contested**: `tool.check` appears 10× in the 2.1.269
   `.d.ts`, while `sirmaelstrom` reported it absent from 2.1.267 declarations. Two versions
   apart, so both may be true; I did not reconcile them against a 2.1.267 file.
7. **My D2 event list is a TOKEN-FREQUENCY count**, not a declaration inventory — see the
   correction above. Astra's S1 is the provenance-labelled version and should be preferred.
8. **`incomplete_results` was `false` on all three REST searches**, so none was a truncated
   or rate-limited zero; the discussions zero is control-armed. I did **not** arm the
   question of whether a *rate limit* would read as a zero here.
9. **The nine dotfiles reports were located and sized but not read line by line.** I
   verified their existence, dates and line counts; their contents may already contain
   findings I re-derived.

## GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — issue 91870 body + all 161 comments; tags/releases; the `mods/` tree at v2.1.269; issues 92533 and 92440.
- [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) — IS aitmpl.com; the blog post and all 10 function-hook example components.
- [Monte9/claude-function-hooks](https://github.com/Monte9/claude-function-hooks) — reference implementation; its three open semantics issues.
- [ray-amjad/awesome-claude-code-function-hooks](https://github.com/ray-amjad/awesome-claude-code-function-hooks) — curated list; same author as the YouTube video.
- [amitray007/claude-code-schema](https://github.com/amitray007/claude-code-schema) — per-release machine-readable config schema.
- [phate45/claude-patching](https://github.com/phate45/claude-patching) — env vars extracted from the binary per version.
- [AdityaRon/claude-code-harness](https://github.com/AdityaRon/claude-code-harness) — security/audit/context hook stack.
- [cvuijst/cc-function-hooks-poc](https://github.com/cvuijst/cc-function-hooks-poc) — PoC against the API.
- [scriptease/claude-code-redact-plugin](https://github.com/scriptease/claude-code-redact-plugin) — the sole repositories-index hit.
- [pavani06/long-running-agents](https://github.com/pavani06/long-running-agents) — vendored the YouTube transcript that revealed the video.
- [noopz/commonplace](https://github.com/noopz/commonplace) · [mahuebel/segmem](https://github.com/mahuebel/segmem) · [diegorv/claude-functions-hook](https://github.com/diegorv/claude-functions-hook) · [lossless-claude/lcm](https://github.com/lossless-claude/lcm) · [indexable-inc/index](https://github.com/indexable-inc/index) — code-index hits with real hook modules or env registries.
- [djnsty23/claude-auto-dev](https://github.com/djnsty23/claude-auto-dev) · [pleaseai/honmoon](https://github.com/pleaseai/honmoon) · [dodi-hq/dodi-skills](https://github.com/dodi-hq/dodi-skills) · [yonatangross/orchestkit](https://github.com/yonatangross/orchestkit) · [anchorwatch-dev/anchorwatch](https://github.com/anchorwatch-dev/anchorwatch) · [cam-douglas/hermes-playground](https://github.com/cam-douglas/hermes-playground) · [JoshuaOliphant/claude-plugins](https://github.com/JoshuaOliphant/claude-plugins) · [n0rvyn/indie-toolkit](https://github.com/n0rvyn/indie-toolkit) — issues/code-index hits showing ecosystem migration.
- [get-bb/bb](https://github.com/get-bb/bb) · [PromptSign/spec](https://github.com/PromptSign/spec) · [cwschroeder/buzz-agent-comms](https://github.com/cwschroeder/buzz-agent-comms) · [akshaypimprikar/pragma](https://github.com/akshaypimprikar/pragma) · [microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit) — named in comments; mostly tangential, listed for completeness.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — the nine prior-art reports and the 2.1.269 `claude-code.d.ts`.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo; issues 753 and 757.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — `ingest.py` / `transcribe.py` read from the installed package to establish the URL-classifier defect.

**STATUS: COMPLETE.**
