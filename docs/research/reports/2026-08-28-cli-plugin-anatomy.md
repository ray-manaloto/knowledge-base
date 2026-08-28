# CLI ↔ Plugin Anatomy: firecrawl vs context7/ctx7 (and controls)

Session: research lane, `ray-manaloto/knowledge-base`, 2026-08-28.
Read-only; no tracked files modified.

## Answer, up front

**Ray's framing does not hold as stated.** The two plugins are built on
*different* architectures, and the "ctx7 CLI" is not part of the installed
`context7` Claude Code plugin at all.

- **firecrawl** — the plugin is a pure **CLI-wrapper skill set**: no `.mcp.json`
  anywhere in its tree, no bundled server code. It teaches Claude, in prose +
  tables, how to shell out to the globally-installed `firecrawl` npm CLI, with
  file-based output (`.firecrawl/*.md`/`.json`) for context-window isolation.
- **context7** (the installed `context7-marketplace` plugin) — the *opposite*
  shape: it is a **remote HTTP MCP client registration**. `.mcp.json` points at
  `https://mcp.context7.com/mcp`, auth via `CONTEXT7_API_KEY`. There is **no
  CLI binary anywhere in this plugin's tree** — `find` over its 8 files (below)
  turns up zero executables, zero `bin/`, zero shell-out instructions.
- **`ctx7`** — a real, live CLI binary **is** installed on this machine
  (`mise:npm:ctx7@0.5.8`, confirmed live below), published from the **same**
  upstream repo as the plugin (`github.com/upstash/context7`) — but it is a
  **separate npm package**, not bundled by or referenced from the
  `context7-marketplace` plugin. This repo's own `research-doc-sources.md`
  step 3 drives `ctx7` directly as a CLI (`ctx7 library` / `ctx7 docs`),
  entirely independent of the installed Claude Code plugin.

So: **firecrawl-the-plugin : firecrawl-the-CLI :: nothing in this repo's
plugin cache : ctx7-the-CLI.** The plugin that shares ctx7's upstream repo name
(`context7`) wraps the *hosted MCP server*, not the CLI. If the target pattern
for `aggregated-search` is "a plugin that teaches Claude to shell out to a
locally-installed CLI, with file-based output," **firecrawl is the model to
copy — context7-the-plugin is not**, because it isn't CLI-based at all.
`last30days` (a control, below) is the second working example of that same
CLI/script-wrapper shape, using bundled python scripts instead of a global npm
install.

---

## firecrawl plugin (`firecrawl@firecrawl`, v1.0.9)

### Tree (22 files, `find … -maxdepth 6 -type f`, `node_modules`-free — this
plugin ships none)

```
.claude-plugin/marketplace.json
.claude-plugin/plugin.json
.gitignore
.in_use/13656                              # PID lock file, live-session marker
commands/skill-gen.md
README.md
skills/firecrawl-agent/SKILL.md
skills/firecrawl-crawl/SKILL.md
skills/firecrawl-developer-index/SKILL.md
skills/firecrawl-download/SKILL.md
skills/firecrawl-interact/SKILL.md
skills/firecrawl-map/SKILL.md
skills/firecrawl-monitor/{goals.md,json-tracking.md,SKILL.md}
skills/firecrawl-parse/SKILL.md
skills/firecrawl-research-index/SKILL.md
skills/firecrawl-scrape/SKILL.md
skills/firecrawl-search/SKILL.md
skills/firecrawl/rules/install.md
skills/firecrawl/rules/security.md
skills/firecrawl/SKILL.md                  # the top-level router skill
```

No `agents/`, no `hooks/`, no `.mcp.json` anywhere in this tree — confirmed by
the same `find` that listed everything above; zero hits for either name.

### a. How the CLI gets onto the machine

**Not bundled.** `skills/firecrawl/rules/install.md` (frontmatter: package
`firecrawl-cli` on npm, source `github.com/firecrawl/cli`) instructs:

```bash
npx -y firecrawl-cli@latest init -y --browser
```

— "installs `firecrawl-cli` globally, authenticates via browser, and installs
core, build, and workflow skills." Manual fallback: `npm install -g
firecrawl-cli@latest`. **No SessionStart hook installs it** — the plugin ships
zero hooks. Verify path is `firecrawl --status` then one real
`firecrawl scrape … -o .firecrawl/install-check.md`.

On **this machine**, mise (not global npm) owns the install — see the Probe
section: resolves to `~/.local/share/mise/installs/npm-firecrawl-cli/1.23.3/bin/firecrawl`,
pinned in this repo's `mise.toml:180` as `"npm:firecrawl-cli" = "1.23.3"`. The
plugin's own instructions (global `npm install -g`) are NOT what put it there
in this repo — this repo's own mise pin is. The plugin doc and this repo's
actual mechanism diverge; both reach a working `firecrawl` on PATH.

### b. How a skill invokes it

Direct shell-out, command-table driven. The top `SKILL.md` gives a full
escalation ladder (search → scrape → map+scrape → crawl → monitor → interact)
and a table mapping "need" → exact subcommand (`search`, `scrape`, `map`,
`crawl`, `agent`, `parse`, `monitor`, `x download`). Every example pipes
through `-o <path>` — e.g.:

```bash
firecrawl search "react hooks" -o .firecrawl/search-react-hooks.json --json
firecrawl scrape "<url>" -o .firecrawl/page.md
```

Output returns to Claude **only by file**, never inline: "Unless the user
specifies to return in context, write results to `.firecrawl/` with `-o`."
Reading back is explicitly bounded: `grep`, `head`, or offset reads, never a
full read — this is `skills/firecrawl/rules/security.md`'s stated mitigation
against indirect prompt injection from untrusted web content. `.firecrawl/` is
gitignored by the plugin's own convention.

Feedback loop: `firecrawl search-feedback` after using search results (refunds
1 credit on first use); `firecrawl feedback <endpoint> <jobId>` for other
endpoints. `FIRECRAWL_NO_ENDPOINT_FEEDBACK=1` opts out and must be respected,
per the skill text.

### c. Auth

`firecrawl login --browser` (OAuth) or `firecrawl login --api-key "<key>"`.
Credentials "stored securely by the CLI" (not specified further in the
installed files — no keychain/file path named). **A keyless free tier exists**
for `search`/`scrape`/`interact` (rate-limited); `crawl`/`map`/`download`/
`agent`/`monitor`/`credit-usage`/feedback all require an account and prompt
interactive login when uncredentialed. `firecrawl --status` shows auth state +
concurrency limit + remaining credits. Auth/credit errors are documented as
**terminal for that call** — "verify config once … then report the blocking
reason and stop," not a retry target.

### d. What else is bundled

- **Commands**: one — `commands/skill-gen.md` (`/skill-gen`, generates a new
  Agent Skill from a docs URL via Firecrawl; per-plugin, not required for
  ordinary use).
- **Agents**: none in this plugin's own tree (an `agents/` grep over the
  installed tree returned nothing for firecrawl).
- **Hooks**: none.
- **MCP server**: none — confirmed absent (`.mcp.json` grep, empty).
- Two auxiliary skill families are referenced but load lazily and are
  documented as "already installed alongside this CLI skill": `firecrawl-build`
  (app integration, `.env` wiring) and `firecrawl-workflows` (research briefs,
  SEO audits) — **not present in this plugin's own installed tree**, so they
  are either a separate install path (the `init --browser` step above) or
  loaded on demand; not directly verified here (see Not measured).

### e. `--help` vs hard-coded flags (currency)

Skill text explicitly defers to the tool for anything beyond the command
table: "Run `firecrawl --help` or `firecrawl <command> --help` for full option
details… For detailed command reference, run `firecrawl <command> --help`."
The skill hard-codes only the **verb** (`search`, `scrape`, …) and the most
common flags (`-o`, `--json`, `--format`) — genuinely narrow flags (e.g. exact
`interact` step syntax) are pushed to the per-command sub-skills, which in turn
say to consult `--help`.

### f. Version coupling

**Floats.** Every install instruction says `@latest` (`npx -y
firecrawl-cli@latest init`, `npm install -g firecrawl-cli@latest`, `npx
firecrawl-cli@latest --version` as the not-found fallback). Nothing in the
plugin pins a CLI version — the plugin version (1.0.9, its own semver) and the
CLI version (1.23.3 on this machine) are unrelated numbers. This repo pins the
CLI separately via its own `mise.toml`, which is what actually fixes the
version here.

---

## context7 plugin (`context7@context7-marketplace`, v1.0.2)

### Tree (8 files, `find … -maxdepth 6 -type f`)

```
.claude-plugin/plugin.json
.in_use/13656
.in_use/81506
.mcp.json
agents/docs-researcher.md
commands/docs.md
README.md
skills/context7-mcp/SKILL.md
```

### a. How "the CLI" gets onto the machine

**It doesn't — there is no CLI in this plugin.** `plugin.json` has no `bin`,
no install script, no hook. The entire mechanism is `.mcp.json`:

```json
{
  "mcpServers": {
    "context7": {
      "type": "http",
      "url": "https://mcp.context7.com/mcp",
      "headers": { "Authorization": "${CONTEXT7_API_KEY:-}" }
    }
  }
}
```

Installing the plugin registers this HTTP MCP endpoint; nothing is downloaded
or shelled out to. Per `README.md`'s install section: `claude plugin
marketplace add upstash/context7` then `claude plugin install
context7@context7-marketplace` — plugin install only, no CLI step.

### b. How a skill invokes it

Via **MCP tool calls**, not Bash — `skills/context7-mcp/SKILL.md` names exactly
two tools: `resolve-library-id` (`libraryName`, `query`) then `query-docs`
(`libraryId`, `query`). No shell command appears anywhere in this plugin's
skill/agent/command files. Output returns as a normal MCP tool-call result
straight into context (no file-isolation convention, unlike firecrawl's
`-o`-everything rule) — there is no equivalent of firecrawl's
`skills/firecrawl/rules/security.md`.

### c. Auth

`CONTEXT7_API_KEY` env var, read by the MCP header
(`Authorization: ${CONTEXT7_API_KEY:-}`, i.e. empty/anonymous if unset).
README: "Without an API key, the plugin connects anonymously and shares the
anonymous rate limits… export it… before launching Claude Code… Restart Claude
Code after setting it."

### d. What else is bundled

- **MCP server**: yes — the *entire* mechanism (see a/b above). Required.
- **Skills**: one (`context7-mcp`), auto-triggering skill text only — required
  in the sense that it's what teaches the model to call the two tools, though
  the MCP tools would still be callable without it.
- **Agents**: one, `docs-researcher` (`model: sonnet`) — "Lightweight agent for
  fetching library documentation without cluttering your main conversation
  context." Optional / for context isolation, same two-tool procedure.
- **Commands**: one, `/context7:docs <library> [query]` — optional manual
  entry point, same two tools underneath.
- **Hooks**: none.

### e. `--help` vs hard-coded (currency) — N/A shape

There is no CLI `--help` to defer to; the "interface" is the MCP tool schema
itself (injected into the system prompt at connection time, since this is a
natively-registered server — see `research-doc-sources.md`'s note on why
per-repo mintlify MCP URLs are avoided but a genuine hosted server like this is
accepted as a documented preference trade-off). The skill/agent/command docs
all hard-code the two-call procedure (`resolve-library-id` → `query-docs`);
there's no lower-level escape hatch analogous to `firecrawl --help`.

### f. Version coupling

N/A in the CLI sense — it's a live hosted service at a fixed URL
(`mcp.context7.com`), so "version" is whatever Upstash runs server-side. The
plugin's own semver (1.0.2) tracks the *plugin* (glue files), not any backend.

---

## `ctx7` — the CLI that is NOT part of the installed plugin

Confirmed live and installed independently of the `context7-marketplace`
plugin:

```
$ command -v ctx7
/Users/rmanaloto/.local/share/mise/installs/npm-ctx7/0.5.8/bin/ctx7
$ ctx7 --version
0.5.8
$ ctx7 --help
Usage: ctx7 [options] [command]
Context7 CLI - Fetch documentation context and configure Context7
Commands:
  login | logout | whoami | setup | remove|uninstall
  library [options] <name> [query]    Resolve a library name to a Context7 library ID
  docs [options] <libraryId> <query>  Query documentation for a library
  upgrade [options]
```

**Control arm applied** (`probes-need-a-control-arm.md`): a `command -v` hit
alone can be a dead mise shim. `ctx7 --version` returned `0.5.8`, matching this
repo's own pin (`mise.toml:179`: `"npm:ctx7" = { version = "0.5.8",
minimum_release_age = "0s" }`), and `--help` printed real, tool-specific
subcommands rather than an error — the binary is live, not a stale shim.

`npm view ctx7 repository.url` → `git+https://github.com/upstash/context7.git`
— **same upstream repo as the plugin**, but a separately-published npm
artifact. This repo's `research-doc-sources.md` step 3 documents `ctx7` as a
direct two-step CLI fetcher (`ctx7 library <name> [query]` then `ctx7 docs
<libraryId> <query>`) — structurally identical to the plugin's MCP two-call
shape (`resolve-library-id`/`query-docs` ↔ `library`/`docs`), but reached via
`Bash`, not via a registered MCP server, and **entirely outside the
`context7-marketplace` plugin's own files**. Nothing in the plugin's tree
mentions `ctx7`, `npx ctx7`, or any CLI invocation.

---

## Controls

### exa (`exa@exa`, v3.4.0)

Also **MCP-first**, but the opposite pole from context7 in *hosting*: exa
**bundles the full server source** (TypeScript, `src/tools/*.ts` for
`webSearch`, `webFetch`, `deepResearchStart/Check`, `companyResearch`,
`peopleSearch`, `linkedInSearch`, `agentRun`, plus `node_modules/` and a
Vercel `api/` dir for hosting it themselves) — yet the **plugin manifest
itself still just points at a hosted HTTP endpoint**:
`plugin.json`/`mcp.json` both register `https://mcp.exa.ai/mcp?client=…`
with an `x-exa-source` header, no key required by default. The bundled
source is the *server's own repo* (this cache entry is a full clone of
`exa-labs/exa-mcp-server`), not something Claude Code runs locally — the
plugin still just talks HTTP to Exa's cloud. One skill (`skills/exa-agent/`,
name `search`) with reference docs teaches query patterns, same as context7's
`context7-mcp` skill. No CLI reachable via `Bash`.

### last30days (`last30days@last30days-skill`, v3.21.0)

The other CLI-wrapper pattern, and the closer sibling to firecrawl: the CLI is
**bundled as Python scripts inside the plugin** (`skills/last30days/scripts/
last30days.py`, `store.py`, `briefing.py`, `watchlist.py`, …) rather than
resolved from a separately-installed binary. `SKILL.md` frontmatter declares
required bins (`node`, `python3`) and a long list of **optional** API-key env
vars (`SCRAPECREATORS_API_KEY` primary, plus `OPENAI_API_KEY`, `XAI_API_KEY`,
`APIFY_API_TOKEN`, etc. — none required, each source degrades gracefully
without its key). A bundled `.venv/` ships too (bundled Python environment,
not mise-managed). Invocation is Bash-direct against the script, not a
separate global CLI product — no `npm install -g` step, no `.mcp.json`.

### mise (`mise@brentmitchell25`, v2.9.0 — disabled in this repo's
`.claude/settings.local.json`, read for the pattern only)

Different shape from all four above: a **pure reference/knowledge skill**. No
CLI wrapping, no MCP server, no bundled scripts — `skills/mise/SKILL.md` is a
long documentation reference (task definitions, tool backends, hooks,
lockfiles) that teaches Claude how to *write* `mise.toml`/use the `mise`
CLI the user already has installed elsewhere. It assumes `mise` is present on
PATH already (this repo pins it via its own toolchain) and never installs or
invokes it on the plugin's behalf.

---

## Pattern table

| axis | firecrawl | context7 (plugin) | ctx7 (CLI, NOT the plugin) | exa | last30days | mise (control) |
|---|---|---|---|---|---|---|
| (a) binary delivery | `npx firecrawl-cli@latest init` (global npm); on this machine, mise `npm:firecrawl-cli` pin instead | **none — no CLI** | separate npm pkg `ctx7`; here, mise `npm:ctx7` pin | none — hosted HTTP MCP; server source bundled but not executed locally | bundled python scripts + `.venv/` inside the plugin | none — assumes user's own `mise` install |
| (b) invocation shape | Bash, `firecrawl <verb> … -o <file>`, output isolated to files | MCP tool calls (`resolve-library-id`→`query-docs`) | Bash, `ctx7 library …` then `ctx7 docs …` | MCP tool calls, hosted | Bash, `python3 scripts/last30days.py …` | prose guidance only, no tool invocation |
| (c) auth | `firecrawl login --browser` / `--api-key`; keyless free tier for 3 verbs | `CONTEXT7_API_KEY` env, header-injected, anonymous fallback | `ctx7 login` (separate CLI-native auth, not probed live) | none required (open endpoint + header) | many **optional** keys, primary `SCRAPECREATORS_API_KEY`, degrades per-source | N/A |
| (d) bundled extras | 1 command, 0 agents, 0 hooks, 0 MCP | 1 MCP server (required), 1 skill, 1 agent, 1 command, 0 hooks | N/A (not a plugin) | 1 MCP server reg (server source also vendored, unused locally), 1 skill | scripts + assets + references, 0 agents/hooks/commands in top tree | 1 skill only |
| (e) `--help` deferral | yes, explicit, repeatedly | N/A (MCP schema is the interface) | yes (own `--help`, not referenced by any plugin doc) | N/A (MCP schema) | not verified — Not measured | N/A |
| (f) version coupling | floats (`@latest`); this repo pins separately via mise | N/A — hosted service, no version pin | pinned in this repo's `mise.toml` (`0.5.8`) | floats (hosted, plugin semver 3.4.0 unrelated) | plugin version IS script version (3.21.0, self-declared) | plugin semver only, no tool version tie |

## Every null with its arm

- **"ctx7 has no auth documented here"** — arm: `ctx7 --help` was run and its
  `login`/`logout`/`whoami` subcommands were only *listed*, not exercised (no
  live login attempted — out of scope, would touch credentials, forbidden by
  this repo's secrets rules regardless). Labeled unverified below, not a
  finding.
- **"firecrawl has no separately-versioned skill families installed here"** —
  arm: `find` over the plugin's own tree came back with **zero** files under
  `firecrawl-build`/`firecrawl-workflows`, matching the README's own hedge
  ("already installed alongside this CLI skill" — i.e., installed by the
  `init --browser` step, not shipped inside this plugin dir). Not re-run to
  confirm a separate skill install exists on this machine; treat as
  plausible-but-unconfirmed, not claimed as fact above.
- **firecrawl npm-backend not visible to `npm ls -g`** — arm: re-ran
  `mise which firecrawl`, which independently resolved to the same
  `npm-firecrawl-cli/1.23.3` path `command -v` found — two different probes
  agreeing, not a single-armed claim.

## Not measured

- Whether `firecrawl-build`/`firecrawl-workflows` skills actually exist as
  separate installed plugin/skill entries on this machine (not searched
  outside `~/.claude/plugins/cache/firecrawl/`).
- `ctx7 login`/live-auth behavior (would touch credentials; out of scope).
- Live network call to either `mcp.context7.com` or `mcp.exa.ai` to confirm
  they answer (connectivity/auth not exercised — read-only file inspection
  only, per task scope).
- The upstream `firecrawl/cli` and `upstash/context7` repo source itself
  (only the installed plugin/CLI files were read, per the task's stated
  preference for installed files).

## GitHub repos touched

- [firecrawl/firecrawl-claude-plugin](https://github.com/firecrawl/firecrawl-claude-plugin) — marketplace source for the installed `firecrawl` plugin (per `claude plugin marketplace list`; not itself fetched — installed files only).
- [firecrawl/cli](https://github.com/firecrawl/cli) — named in `skills/firecrawl/rules/install.md` frontmatter as the CLI's source; not fetched, installed docs only.
- [upstash/context7](https://github.com/upstash/context7) — marketplace source for the `context7-marketplace` plugin AND the `ctx7` npm package's `repository.url` (confirmed via `npm view ctx7 repository.url`); installed plugin files read, upstream not fetched.
- [exa-labs/exa-mcp-server](https://github.com/exa-labs/exa-mcp-server) — the exa plugin's own bundled source is a full clone of this repo (control arm); read locally from the plugin cache, not fetched from GitHub.
- [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) — the last30days plugin's own repo, per its `plugin.json`; read locally, not fetched.
- [brentmitchell25/mise-plugin](https://github.com/brentmitchell25/mise-plugin) — marketplace source for the (disabled) `mise` plugin, control; read locally, not fetched.
