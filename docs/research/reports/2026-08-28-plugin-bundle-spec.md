# What a Claude Code plugin can bundle — research for `aggregated-search`/`aggregated-research`

Purpose: ground the design of an `aggregated-research` plugin (modelled on a plugin
that wraps a CLI) in the real Claude Code plugin surface, so the plugin.json/
marketplace.json we write doesn't invent capabilities that don't exist.

Route used: direct file reads of the pinned local clone
`sources/claude-code-docs/content/en/docs/claude-code/{plugins,plugins-reference,
plugin-marketplaces,plugin-dependencies}.md` (SHA `6b2327de2c214ef0e77bb6509af899f931bfd99b`,
`sources/claude-code-docs.manifest`). `graphify path`/`explain` were tried first
(control-armed: same generic-token BFS flood on any English-phrase query against
this corpus — it indexes code AST, not doc prose; the docs corpus itself has no
`--prose` graph built) and abandoned in favor of direct reads, which the research
chain permits once graph orientation is unproductive.

## Answer (headline)

A plugin is a self-contained directory: skills, agents, hooks, MCP servers, LSP
servers, monitors, themes, output styles, a `bin/` PATH addition, and default
settings — nine component types total, all auto-discovered from conventional
directories or declared via `plugin.json` path fields (`plugins.md:163-186`,
`plugins-reference.md:13-14`). None of that requires an external CLI to be
installed beforehand *except* LSP servers, which explicitly require the binary
pre-installed (`plugins-reference.md:259-261`). For a wrapped-CLI plugin like
`aggregated-search`, the two real options are: (a) bundle the CLI's own binary
under `bin/` (if small/pure and licensable), or (b) ship a `SessionStart` hook
that installs/checks for the CLI into `${CLAUDE_PLUGIN_DATA}` (persists across
plugin updates) and have skills/agents shell out to it. There is **no**
postinstall/build hook — Node dependency install explicitly runs
`--ignore-scripts` (`plugins-reference.md:794-802`) — so any CLI needing a native
build step cannot be bundled through the automatic dependency path.

**Version pinning claim CONFIRMED, and the 9-month-stale finding is directly
supported by the docs, not just plausible:** setting an explicit `version` in
`plugin.json` means "users only receive updates when you bump this field...
Pushing new commits without bumping it has no effect" (`plugins-reference.md:1316`).
Omitting `version` gives commit-SHA versioning instead, where "users get updates
whenever the source's resolved commit changes" (`plugins-reference.md:1317`). So:
if `aggregated-search`'s manifest carries a fixed `"version": "1.0.0"` and
upstream commits without bumping it, installed copies never update — this is
the exact mechanism, confirmed at `plugins-reference.md:1300-1320` (Version
management) and `plugin-marketplaces.md:922-925` (Warning block, same claim
independently stated at the marketplace-entry layer).

## Component inventory

| Type | Default path | Loaded how | Doc cite |
|---|---|---|---|
| Skills | `skills/<name>/SKILL.md`, or flat `.md` in `commands/`, or single root `SKILL.md` | Auto-discovered; namespaced `/plugin-name:skill-name` | `plugins-reference.md:17-43`, `plugins.md:79-97,186` |
| Agents | `agents/*.md` | Auto-discovered; appear in @-mention typeahead as `plugin:agent-name`. Supports `name,description,model,effort,maxTurns,tools,disallowedTools,skills,memory,background,isolation` frontmatter. **`hooks`, `mcpServers`, `permissionMode` explicitly NOT supported for plugin-shipped agents** (security) | `plugins-reference.md:45-72` |
| Hooks | `hooks/hooks.json`, or inline `plugin.json` | JSON event-matcher config; 5 hook types (`command`,`http`,`mcp_tool`,`prompt`,`agent`); fires on 30 lifecycle events | `plugins-reference.md:74-146` |
| MCP servers | `.mcp.json`, or inline `plugin.json.mcpServers` | Standard MCP config (`command`/`args`/`env` or `url`/`headers`); autostart when plugin enabled | `plugins-reference.md:148-181` |
| LSP servers | `.lsp.json`, or inline `plugin.json.lspServers` | Maps extensions to a language-server command. **Binary must be pre-installed by the user** — plugin only configures the connection | `plugins-reference.md:183-271` |
| Monitors (experimental) | `monitors/monitors.json`, or `plugin.json.experimental.monitors` | Persistent background shell process per session; each stdout line becomes a Claude notification. Interactive-CLI-only | `plugins-reference.md:273-321` |
| Themes (experimental) | `themes/*.json`, or `plugin.json.experimental.themes` | Color palette JSON, read-only until user copies it | `plugins-reference.md:323-339` |
| Output styles | `output-styles/*.md` | Replaces default; loaded when plugin enabled | `plugins-reference.md:523-534` (row), `plugins.md:301` |
| `bin/` executables | `bin/` | Every file here is added to the Bash tool's `PATH` while the plugin is enabled — invokable as a bare command | `plugins-reference.md:869-870,903` |
| `settings.json` | plugin root | Default settings applied on enable. **Only `agent` and `subagentStatusLine` keys are supported**, everything else silently ignored | `plugins.md:267-279` |
| Channels | `plugin.json.channels` | Binds a named channel (Telegram/Slack/Discord-style message injection) to one of the plugin's own `mcpServers` entries | `plugins-reference.md:606-633` |
| Workflows | `workflows/*.js` | Script files; path field `workflows` replaces default | `plugins-reference.md:530` (row), `plugins-reference.md:858-859` (dir listing) |
| `CLAUDE.md` at plugin root | — | **Explicitly NOT loaded as project context.** "Plugins contribute context through skills, agents, and hooks rather than CLAUDE.md" | `plugins-reference.md:886` |

## External-CLI dependency mechanisms — the (b) question

No dedicated "install this external binary" primitive exists. What's actually
available, in order of how the docs present it:

1. **Bundle the binary directly under `bin/`.** Simplest, but the binary ships
   *inside* the plugin's git/zip source, so it must be small, licensable to
   redistribute, and cross-platform (or per-OS conditional logic in a wrapper
   script) — `plugins-reference.md:869-870,903`.
2. **`.mcp.json` `command`/`args` pointing at `${CLAUDE_PLUGIN_ROOT}/servers/...`
   or a system binary (e.g. `npx`)** — the plugin *configures* how to invoke a
   tool, it doesn't install it — `plugins-reference.md:156-174`.
3. **`.lsp.json` `command`** — same shape, explicit user-must-install-first
   warning: "Users installing your plugin must have the language server binary
   installed on their machine" — `plugins.md:243`, `plugins-reference.md:259-261`.
4. **`node_modules` auto-install (Node/Bun ONLY, not a general installer).**
   When a plugin ships `package.json` + a supported lockfile (`bun.lock`,
   `bun.lockb`, `npm-shrinkwrap.json`, `package-lock.json` — `yarn.lock`/
   `pnpm-lock.yaml` are explicitly SKIPPED because those tools support
   resolution-time hooks that bypass `--ignore-scripts`), Claude Code runs
   `npm ci --ignore-scripts` / `bun install --frozen-lockfile --ignore-scripts`
   into the cached copy on install/update, bounded to 60s, and this **cannot be
   turned off** — `plugins-reference.md:784-809`. `--ignore-scripts` means no
   `preinstall`/`install`/`postinstall` runs, so a package needing a native
   build step **downloads but does not compile**.
5. **`SessionStart` hook + `${CLAUDE_PLUGIN_DATA}` (the actual answer for
   Python deps, or anything `--ignore-scripts` can't finish).** This is the
   documented pattern for "dependencies the automatic install can't provide,
   such as packages that need their lifecycle scripts to build, Python
   dependencies, or a plugin locked with Yarn or pnpm" — install them from a
   `SessionStart` hook into the persistent data directory
   (`${CLAUDE_PLUGIN_DATA}` = `~/.claude/plugins/data/{id}/`, survives plugin
   updates, created on first reference) — `plugins-reference.md:718-747,
   811`. Worked example given in the docs is exactly this shape: a
   `SessionStart` hook `diff`s the bundled `package.json` against a copy in
   `${CLAUDE_PLUGIN_DATA}`, and re-runs `npm install` there when they differ —
   `plugins-reference.md:726-745`.
6. **`command` plugin source (marketplace-level, not per-CLI-dependency, but
   directly relevant to a "wraps a CLI" plugin).** A marketplace entry can
   point at `{source: "command", command: "my-tool claude-plugin-path"}`: a
   *locally installed tool* produces the plugin directory itself, re-run once
   per session so plugin content tracks the tool's own state. This requires
   Claude Code v2.1.229+, needs explicit one-time user acceptance of the exact
   command string (or `--yes` non-interactively), and is never installed as a
   transitive dependency of another plugin — `plugin-marketplaces.md:499-561`.
   This is the closest thing to "the plugin's content is generated by the
   external CLI it wraps," but it presupposes the CLI is *already* on the
   user's machine, same as `.mcp.json`/`.lsp.json`.

**No mechanism downloads and installs an arbitrary external CLI binary from
inside a plugin's own install flow.** Every path above is either "bundle it
yourself" (`bin/`), "declare where it lives and hope the user installed it"
(MCP/LSP `command`), or "run a script yourself at session start" (the
`SessionStart` + `${CLAUDE_PLUGIN_DATA}` pattern) — never a first-class
"depends on system binary X, auto-fetch it" field.

## Cross-plugin dependencies (c)

`plugin.json.dependencies` is an array of bare plugin-name strings or
`{name, version?, marketplace?}` objects (`plugins-reference.md:451-454,
539`, full mechanics in `plugin-dependencies.md`):

- **Resolution scope**: a dependency resolves within the *same* marketplace as
  the declaring plugin by default. Cross-marketplace requires the **target**
  marketplace to be named in the declaring plugin's *own root marketplace's*
  `allowCrossMarketplaceDependenciesOn` array — trust does not chain through
  intermediate marketplaces (`plugin-dependencies.md:79-104`,
  `plugin-marketplaces.md:187`).
- **Version constraints**: semver ranges (`~2.1.0`, `^2.0`, `>=1.4`, `=2.1.0`),
  resolved against git tags of the form `{plugin-name}--v{version}` on the
  dependency's own repo (or the marketplace repo for a relative-path source);
  `claude plugin tag --push` is the tagging tool (`plugin-dependencies.md:23-49,
  106-134`).
- **Transitive install/enable**: installing/enabling a plugin transitively
  installs/enables its dependencies at the same scope; disabling is blocked
  if another enabled plugin still needs it, with the CLI printing a
  ready-to-run chained disable command (`plugin-dependencies.md:154-179`).
- **Bundle pattern**: a manifest can consist of *only* `name` + `dependencies`
  — a zero-component "meta-plugin" purely for team-wide bundled installs
  (`plugin-dependencies.md:50-77`). Directly relevant if `aggregated-search`
  and `aggregated-research` end up as two plugins under one umbrella install.
- **Conflict resolution**: multiple constrainers intersect ranges; incompatible
  ranges fail with `range-conflict`; `npm`/`archive`/`command`-sourced deps are
  checked at load time but not tag-resolved (`plugin-dependencies.md:140-150,
  206-217`).

## Version pinning semantics (d) — confirmed from the docs

Full resolution order, applies to every source type except `command`
(`plugins-reference.md:1298-1310`):

1. `version` in the plugin's own `plugin.json` (wins even over a value set in
   the marketplace entry — "Claude Code always uses the `plugin.json` value
   without warning, so a stale manifest version can mask a version you set in
   `marketplace.json`" — `plugin-marketplaces.md:925`)
2. `version` in the marketplace entry
3. git commit SHA of the source (`github`/`url`/`git-subdir`/relative-path in
   a git-hosted marketplace)
4. SHA-256 digest for `archive` sources (first 12 chars if no `sha256` pin set)
5. `"unknown"` for `npm` sources or a local dir not inside a git repo

`command` sources are the one exception: version is **always** a content hash
of what the command produced (`<explicit-version>-<hash>` if `plugin.json` also
sets one), so the marketplace entry's `version` field is ignored entirely for
that source type (`plugins-reference.md:1310`).

**The stale-pin failure mode, in the docs' own words** (`plugins-reference.md:1316`,
`plugin-marketplaces.md:922-925`): *"If you declare `"version": "1.0.0"` in
`plugin.json` and push new commits without changing that string, existing
users of those sources keep the cached copy, because Claude Code sees the
same version."* `/plugin update` reports "already at the latest version" —
this is a silent-stale trap, not a warned one. For a plugin under active
development (which `aggregated-search`/`aggregated-research` will be, given
it's modelled on wrapping a CLI whose own version moves), the docs' own
recommendation table (`plugins-reference.md:1312-1320`) names commit-SHA
versioning ("omit `version` from both `plugin.json` and the marketplace
entry") as **"Best for: Internal or team plugins under active development"**
— i.e. the fix for the 9-month-stale finding is architectural (don't set
`version`), not procedural (remember to bump it).

## Cannot bundle

| Cannot bundle | Doc line |
|---|---|
| `CLAUDE.md` at plugin root loaded as project context | `plugins-reference.md:886` |
| `hooks`, `mcpServers`, `permissionMode` on a plugin-shipped **agent** ("for security reasons") | `plugins-reference.md:68` |
| A native-build npm/Bun dependency that needs its lifecycle script to run — the auto-install always passes `--ignore-scripts` | `plugins-reference.md:801-802,811` |
| Yarn- or pnpm-locked Node dependencies via the automatic install (skipped outright; docs say "have your own hook install these instead") | `plugins-reference.md:795,811` |
| Any file the plugin references outside its own directory via `../` — copied plugins can't reach it, only the plugin's own tree is copied to the cache | `plugins-reference.md:813-815`, `plugin-marketplaces.md:115,1357-1363` |
| Symlinks pointing outside the enclosing marketplace — "skipped for security" | `plugins-reference.md:817-825` |
| Turning off the automatic Node dependency install ("no setting or environment variable disables it") | `plugins-reference.md:809` |
| `${user_config.*}` substitution into any field that runs through a shell (shell-form hook commands, Monitor commands, MCP `headersHelper`) — rejected with an error, not silently interpolated, to prevent shell injection from a configured value | `plugins-reference.md:582-589` |
| A monitor command referencing `${user_config.*}` at all — rejected outright (monitor commands run through a shell) | `plugins-reference.md:319` |
| An archive plugin source larger than 256 MiB, or a `command` source's printed directory larger than 256 MiB / >20,000 entries | `plugin-marketplaces.md:471`, `plugins-reference.md:533` |
| A `command` source ever installed automatically as another plugin's dependency — the user must accept and install it themselves first | `plugin-marketplaces.md:546`, `plugin-dependencies.md:137` |
| Installing a language server itself — LSP plugins only configure the connection; "you must install the language server binary separately" | `plugins-reference.md:259-261` |

## Discrepancy found: the installed `plugin-dev` skill's own doc is stale on path-merge semantics

`~/.claude/plugins/cache/claude-plugins-official/plugin-dev/{b819188d2eea,e33a9ec0973a,unknown}/skills/plugin-structure/SKILL.md`
states: *"Custom paths supplement defaults—they don't replace them. Components
in both default directories and custom paths will load."* for `commands` and
`agents` path fields. The primary docs directly contradict this:
`plugins-reference.md:635-641,639` — **"Replaces the default: `commands`,
`agents`, `workflows`, `outputStyles`, `experimental.themes`,
`experimental.monitors`. ... Adds to the default: `skills`."** Only `skills` is
additive; `commands`/`agents` custom paths *replace* the default directory scan
unless you explicitly re-list it (`"commands": ["./commands/", "./extras/"]`).
This matters directly for `aggregated-search`/`aggregated-research`: if the
plugin declares a custom `agents` path expecting the default `agents/` folder
to still load alongside it, agents will silently disappear. Not independently
re-verified against a live `claude plugin validate` run (see Not measured).

## Every null with its arm

- **schemastore schema fetch**: `curl -sL https://json.schemastore.org/claude-code-plugin.json` → HTTP 404 (bogus). Control: `curl -sL https://json.schemastore.org/claude-code-marketplace.json` → HTTP 200, and a deliberately bogus schemastore path (`.../this-does-not-exist-bogus.json`) → HTTP 404. So the plugin-manifest schema is genuinely absent from schemastore under that exact filename (not a probe failure) — the marketplace schema exists and its declared top-level keys (`$schema, allowCrossMarketplaceDependenciesOn, description, forceRemoveDeletedPlugins, metadata, name, owner, plugins, version`) match the prose doc, with one field the prose doc's "Optional fields" table (`plugin-marketplaces.md:179-190`) does **not** mention: `forceRemoveDeletedPlugins` — present in the schema, undocumented in the markdown page as of this repo's pinned SHA. Flag as a schema/doc gap, not independently explained.
- **`graphify query` for this topic**: returned a 272-node BFS flood of unrelated code symbols (pytest internals, a Rust `vfox` plugin crate) for the phrase "what can a Claude Code plugin bundle" — control: the corpus is 492,654 nodes, overwhelmingly AST from unrelated pinned source repos, and this repo's own doc rule (`.claude/rules/probes-need-a-control-arm.md` "The graph is a probe too") predicts exactly this failure mode for a prose question against an AST-dominant graph with no `--prose` variant built for the docs corpus specifically. Not re-tried with `--idf`/`--prose` flags (out of scope for this 20-min bound) — a follow-up ingesting `claude-code-docs` more granularly, or running `--prose`, was not attempted.

## Not measured

- Did not run `claude plugin validate ./<scratch-plugin>` against a hand-built test plugin to independently confirm the path-merge discrepancy above (would need to actually scaffold a plugin, out of the research/read-only scope given).
- Did not fetch `~/.claude/plugins/cache/claude-plugins-official/plugin-dev/*/skills/plugin-structure/references/*` (only `SKILL.md`'s first 150 lines) — the `references/` subdirectory may hold more current material than `SKILL.md` itself.
- Did not run `claude plugin eval --help` or the eval-case format in depth (mentioned in `claude plugin --help` output above but not researched — may matter for testing `aggregated-search` before submission).
- Did not verify `claude plugin details <name>`'s token-cost estimate mechanism live against a real plugin (description only, from docs).
- `sub-agents.md`, `hooks.md`, `mcp.md` primary pages were not separately read in full — content was cross-referenced only through `plugins-reference.md`'s summaries of each. If the aggregated-research plugin design needs the full hook-type semantics (`prompt`/`agent` hook types especially) or MCP transport details beyond stdio, read those pages directly before writing the manifest.
- `discover-plugins.md` and `plugin-hints.md` were located but not read — relevant to how `aggregated-search` would be *discovered/recommended*, not to what it can bundle; out of this task's scope.

## GitHub repos touched

- [thevibeworks/claude-code-docs](https://github.com/thevibeworks/claude-code-docs) — pinned mirror of Anthropic's Claude Code docs; primary source for all plugin/marketplace/dependency semantics cited above (`sources/claude-code-docs.manifest`, commit `6b2327de2c214ef0e77bb6509af899f931bfd99b`).
- [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) — home of the `plugin-dev` plugin whose bundled `plugin-structure` skill was read (and found stale) via the local plugin cache.
