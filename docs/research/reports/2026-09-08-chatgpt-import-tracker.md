# Desktop import/sync: GitHub tracker research

**NOT SUFFICIENT.** Settings alone does not close the independent MCP import path that can rewrite the same `<repo>/.codex/config.toml`. **Confidence: high for the inspected public backend; moderate for this exact installed desktop build.** The closed desktop frontend and its bundled backend SHA were not inspected. The owner's separate `Settings 1` / `MCP servers 1` import records and observed `.mcp.json` translation fit the public implementation. A different bundled implementation, or an explicit frontend contract proving that Settings also gates MCP writes despite MCP remaining checked, would change the app-specific conclusion.

**Additional categories:** for the repository's `.codex/**`, uncheck **MCP servers, Agents, and Hooks** to close the additional direct project-file writers established below. **Plugins must also be unchecked if the boundary includes `~/.codex/**`**; its importer installs into the Codex home and enables the plugin there. For that broader boundary, **Instructions and Chats must also be unchecked**. Standalone Skills payloads go to `.agents/skills`; the sources reviewed do not establish that leaving Skills selected produces zero import bookkeeping writes in `.codex`.

**An exhaustive desktop checkbox set guaranteeing ALL writes stop is CANNOT DETERMINE.** The three project categories above are a source-backed list of known direct writers, not a certification of the closed frontend's complete effects. If the requirement is zero automatic-import activity without relying on unknown metadata behavior, turn **Automatic sync OFF**; alternatively deselect every remaining category, including Skills, and keep future categories off. These are conservative controls, not a tested guarantee that a running app never writes runtime state. No setting was changed by this lane.

Research date: 2026-09-08 UTC. GitHub source pinned to `6ab3ae532346a7e900bcef8323a0a18f3764b504` (current `openai/codex` main when retrieved). This research used GitHub REST and GraphQL directly, not `gh search`. No tracked file was edited; work is in this report and its adjacent ignored evidence directory.

## Evidence

Owner-provided local evidence: the 2026-09-08 event imported Settings 1, MCP servers 1, and Sessions 8; the owner reports 145 lines of cited TOML comments lost. Those observations were supplied to this lane and were not independently reproduced.

### Independent MCP import and comment loss — primary implementation

1. [The import dispatcher](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/service.rs#L194) processes the supplied item list. `Config` calls `import_config` at line 207; `McpServerConfig` separately calls `import_mcp_server_config` at line 328. The MCP branch does not require a Config item in the same request. The UI-to-enum mapping is inferred from the owner's category names and import history, not claimed as inspected frontend code.
2. [MCP import](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/service.rs#L602) chooses `$CODEX_HOME/config.toml` for home scope or `<repo>/.codex/config.toml` for repository scope. It reads optional source settings for MCP options, builds MCP entries, parses the existing file, adds missing server names, and writes the whole file when entries were added. Reading source settings here does **not** mean executing the Settings import category.
3. [MCP source reading](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/mcp.rs#L74) reads `.mcp.json` and applicable `.claude.json` entries; [MCP conversion](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/mcp.rs#L69) constructs a `mcp_servers` table. This matches the owner's reported destination.
4. [MCP merge](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/config_values.rs#L40) preserves existing server entries and adds absent names. [The TOML writer](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/config_values.rs#L77) serializes a `toml::Value` with `toml::to_string_pretty` and uses `fs::write` on the whole file. **Code-derived conclusion:** comments are not retained through the value-only parse/serialize operation, even though existing keys survive. The Settings writer uses the same helper.
5. A server already present is not merged again by this path. An empty migration or no newly added names produces no config write. This is a conditional writer, not proof that every sync tick rewrites the file. A new importable MCP server is a counterexample to Settings-only protection.

### Which category can write where?

Paths below describe the inspected backend's **direct import payloads**. `$CODEX_HOME` is conventionally `~/.codex`, but can be relocated. Repository and home scopes must not be conflated.

| UI category (backend mapping where inferred) | Repository-scope destination | Home-scope destination / effect | Consequence |
|---|---|---|---|
| Settings (`Config`) | `.codex/config.toml` | `$CODEX_HOME/config.toml` | Already unchecked. [Source](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/service.rs#L553) |
| MCP servers (`McpServerConfig`) | `.codex/config.toml` | `$CODEX_HOME/config.toml` | **Uncheck additionally** for either boundary. [Source](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/service.rs#L602) |
| Agents (`Subagents`) | `.codex/agents/*.toml` | `$CODEX_HOME/agents/*.toml` | **Uncheck additionally** for all project `.codex/**` payload writes. [Destination](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/service.rs#L640); [writer](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/subagents.rs#L57) |
| Hooks | `.codex/hooks.json` and `.codex/hooks/**` | `$CODEX_HOME/hooks.json` and `hooks/**` | **Uncheck additionally** for all project `.codex/**` payload writes. [Destination](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/service.rs#L658); [writer](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/hooks_common.rs#L13) |
| Plugins | Repo cwd participates in source/config discovery, but the inspected installation targets Codex home; a project config write is **not established** here | Plugin cache/data under `$CODEX_HOME/plugins/`; user plugin enablement | **Uncheck** for a boundary including home `.codex`; deselect conservatively if plugin imports are unwanted. Bundled MCP remains part of the plugin channel according to the owner's UI subtitle. [Import](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/plugins.rs#L86); [cache root](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/core-plugins/src/store.rs#L107); [user enablement](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/core-plugins/src/manager.rs#L2243) |
| Instructions (`AgentsMd`) | `AGENTS.md`, outside project `.codex` | `$CODEX_HOME/AGENTS.md` | **Uncheck for home `.codex/**`**; no direct project `.codex` payload write in this branch. [Source](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/service.rs#L748) |
| Chats (`Sessions`) | A project-associated chat is not evidence its files reside in project `.codex` | Import ledger at `$CODEX_HOME/external_agent_session_imports.json`; imported thread storage also exists | **Uncheck for home `.codex/**`**. [Ledger writer](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/sessions/ledger.rs#L393); [desktop import report #39568](https://github.com/openai/codex/issues/39568) |
| Skills | `.agents/skills/**` | Sibling `.agents/skills/**`, normally `~/.agents/skills/**` | No direct standalone-skill payload write to `.codex` in this branch. **No guarantee about frontend bookkeeping.** [Repo destination](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/service.rs#L701); [home destination](https://github.com/openai/codex/blob/6ab3ae532346a7e900bcef8323a0a18f3764b504/codex-rs/external-agent-migration/src/service.rs#L464) |

Existing-target conditions also matter: agent imports skip existing target files; hook imports skip a nonempty target hook file; instructions and skill imports similarly avoid replacing existing populated targets. These conditions do not disable future writes for newly detected content. Disabling standalone MCP or Skills does not, by itself, establish that the separately selected Plugins category is disabled.

The backend enum also contains Commands and Memory. They were not separately listed in the owner's current UI; no frontend grouping for them is asserted here. The owner's future-category switch is already off. This is another reason to distinguish the verified path map from an exhaustive desktop no-write contract.

### Tracker findings and rejected false positives

| Primary tracker item | What was actually established | What it does not establish |
|---|---|---|
| [codex #39568](https://github.com/openai/codex/issues/39568), open, 2026-08-20 | Firsthand Windows report explicitly names Settings → Import and Keep imports in sync, reproduces empty `externalAgentConfig/detect`, and successful explicit `SESSIONS` import. Zero comments at fetch. | No Settings/MCP checkbox interaction test; reporter's diagnosis is not a maintainer contract. |
| [codex #40147](https://github.com/openai/codex/issues/40147), open, 2026-08-22 | Firsthand ChatGPT desktop/macOS report of imported skill path rewriting, with `external-agent-import-sync-enabled` and destination `~/.agents/skills`. Its comments point to the public migration crate, which led to the pinned code above. | Not an MCP toggle test. The comments propose external fork fixes; their authors have association NONE. No merged OpenAI fix is claimed. |
| [codex #39923](https://github.com/openai/codex/issues/39923), open, 2026-08-21 | User reports import-related Windows instability and undeletable imported skills after disabling automatic synchronization. Zero comments at fetch. | Disabling sync is not demonstrated to undo earlier imports. This report does not certify the master switch against every writer. |
| [codex #24515](https://github.com/openai/codex/issues/24515), open, 2026-05-26 | CLI 0.133.0 user report of accepted Claude migration overwriting user-level config keys. | Different surface and trigger. Its sole comment is unaffiliated proposed TypeScript, not product implementation. |
| [codex #41371](https://github.com/openai/codex/issues/41371) | CLI `/import` can retain stale hook wiring according to reporter. | Does not show desktop Settings gating Hooks. |
| [codex #19372](https://github.com/openai/codex/issues/19372) | Older CLI user report of Claude marketplace mirroring into home `.codex` caches. | Not proof of the current desktop checkbox implementation, nor a project config write. |
| [codex #42116](https://github.com/openai/codex/issues/42116) | User reports a desktop startup `config/batchWrite` losing unmanaged keys. | Its loss of keys and startup trigger differ from this owner's comment-only loss during import. Not used to attribute the owner's event. |
| [codex-plugin-cc PR #701](https://github.com/openai/codex-plugin-cc/pull/701), **unmerged** when fetched | Proposed `/codex:transfer` fix uses completion notifications and session-import ledger fallback. Organization search located this additional OpenAI repo. | This is an external client of the import RPC, not the desktop category controller. |

Q13 (Cowork tools) and Q14 (Bundled skills and MCP servers) returned issues #26338 and #26351, respectively. Their issue bodies and all fetched comments (13 and 3) concern workspace roots and startup lag; no category-gating contract was found. GitHub's lexical matching must not be treated as a literal UI quotation merely because the query used quotes.

The nonempty discussion searches D03, D05, and D10 returned cross-device VS Code sync, the Python SDK v1 beta, and model/session isolation respectively. Their fetched bodies did not answer the importer question. The narrow PR searches returned unrelated session-list/resume and MCP-client PRs. Broad search hits were retained for discovery; their totals are not counts of relevant findings.

### Claim-by-claim status and limits

| Claim / question | Status |
|---|---|
| Can MCP import write config without a Settings/Config import item? | **Asked successfully; yes in pinned source.** |
| Is Settings the only migration writer of project config.toml? | **Asked successfully; the answer is no** in pinned source. Desktop application is an explicitly qualified inference. |
| Did the public tracker provide a maintainer-verified exhaustive desktop category/path contract? | **Not found in the reviewed evidence.** This is bounded by queries/pages below, not a claim that none exists anywhere. |
| Do exact supplied query strings have zero matching issues/PRs or discussions? | **Asked successfully; answer is no matches only for the zero-count rows below**, each with a successful matching-scope control. No semantic absence claim is inferred. |
| Was a GitHub API search never successfully asked? | **None.** All 59 searches including controls returned successfully; no rate limit or HTTP error was converted to zero. |
| Is the installed desktop's exact frontend/bundled code certified? | **Not tested / not inspected.** A pinned backend source path plus local observations supports the finding, but is not a live post-toggle reproduction. |
| Does disabling automatic import prevent all runtime writes by the app? | **Not established.** Import controls are not a filesystem write lock. |

The report is research, not a runtime verification receipt. No import RPC was executed, no application preferences were changed, no test server was added to `.mcp.json`, and no tracked files were edited. To remove the desktop-build uncertainty, a separate authorized experiment can use a disposable repository, Settings off, MCP on, a newly importable inert MCP entry, and file-change attribution; a stronger control repeats with MCP off. No such experiment was conducted in this tracker lane.

Local graph orientation was **warning-bearing and truncated**. Required command: `mise exec -- graphify query "Does the ChatGPT desktop import automatic sync rewrite .codex/config.toml when Settings is unchecked but MCP servers or Plugins remain selected?"`; exit 0. Messages retained: `mise WARN tool purgatory cleanup failed: Operation not permitted (os error 1)` and `[graphify] note: this graph uses the pre-#1504 node-ID scheme; rebuild with graphify extract --force to get path-qualified IDs (fixes same-name-file collisions).` It reported 359146 graph nodes, 344 matched, 66 shown, **278 omitted** at ~2000 tokens. The graph was not used as answer authority; live GitHub source was the fallback. No graph build/install was run. No receipt or source-enrollment operation was attempted.

One `web.run` corroborating open of the pinned service.rs GitHub HTML URL failed with **Cache miss**; that surface was never successfully fetched. The same source had already been fetched successfully through GitHub's Contents API (S02) and retained with its content/blob metadata. A separate web open of issue #39568 succeeded. Neither was a search or a zero-result claim.

## Every GitHub search query, result count, and control

**Method:** issue/PR searches used `gh api --include -X GET search/issues -f q='<query>' -f per_page=100`; the preliminary C00 used `per_page=5` without `--include`. Return code and HTTP status were checked before JSON parsing. `total_count` was required. No `jq` fallback or `gh search` was used. Discussion searches used `gh api --include graphql` with `search(query:$q,type:DISCUSSION,first:100)`, requiring a successful response with no GraphQL errors and recording `discussionCount` and `pageInfo.hasNextPage`.

**59 searches total:** 45 topic queries and 14 positive controls, counting C00. Every REST response reported `incomplete_results=false`; all API searches succeeded. A returned page smaller than total_count is explicitly shown below. Broad queries were not fully paginated or exhaustively reviewed. GitHub result ranking and index coverage remain limits even when `incomplete_results=false`.

Each row's complete raw HTTP response and parsed result is under `import-sync-tracker-evidence/<ID>.http.txt` and `<ID>.json`; the machine-readable ledger is `query-ledger.jsonl`. C00's tool display truncated item bodies, but retained total_count and incomplete_results; C01 immediately supplied an equivalent quoted, explicit-scope positive control with retained raw evidence. Counts describe GitHub lexical search results, not verified relevant issue counts.

| ID | Exact query | Total / returned | Control and outcome |
|---|---|---:|---|
| C00 | `repo:openai/codex config.toml` | 3494 / 5 | Positive unquoted control; exit 0; incomplete_results=false. |
| C01 | `repo:openai/codex "config.toml" in:title,body,comments` | 3494 / 100 | Positive control: hits. |
| Q01 | `repo:openai/codex "import from another AI app" in:title,body,comments` | 0 / 0 | C01 = 3494 hits. Asked: no matches. |
| Q02 | `repo:openai/codex "keep imports in sync" in:title,body,comments` | 1 / 1 | C01 = 3494 hits. Asked: nonzero hits; relevance assessed separately. |
| Q03 | `repo:openai/codex "automatic sync" in:title,body,comments` | 29 / 29 | C01 = 3494 hits. Asked: nonzero hits; relevance assessed separately. |
| Q04 | `repo:openai/codex "content to sync" in:title,body,comments` | 3 / 3 | C01 = 3494 hits. Asked: nonzero hits; relevance assessed separately. |
| Q05 | `repo:openai/codex "config.toml" "overwritten" in:title,body,comments` | 46 / 46 | C01 = 3494 hits. Asked: nonzero hits; relevance assessed separately. |
| Q06 | `repo:openai/codex "config.toml" "rewritten" in:title,body,comments` | 88 / 88 | C02 = 1518 hits. Asked: nonzero hits; relevance assessed separately. |
| C02 | `repo:openai/codex "config.toml" "mcp" in:title,body,comments` | 1518 / 100 | Positive control: hits. |
| Q07 | `repo:openai/codex "comments stripped" in:title,body,comments` | 0 / 0 | C01 = 3494 hits. Asked: no matches. |
| Q08 | `repo:openai/codex "settings import" in:title,body,comments` | 32 / 32 | C01 = 3494 hits. Asked: nonzero hits; relevance assessed separately. |
| Q09 | `repo:openai/codex "claude" "import" in:title,body,comments` | 152 / 100 | C02 = 1518 hits. Asked: nonzero hits; relevance assessed separately. |
| Q10 | `repo:openai/codex "mcp servers" "import" in:title,body,comments` | 137 / 100 | C02 = 1518 hits. Asked: nonzero hits; relevance assessed separately. |
| Q11 | `repo:openai/codex "shell_environment_policy" "import" in:title,body,comments` | 9 / 9 | C02 = 1518 hits. Asked: nonzero hits; relevance assessed separately. |
| Q12 | `repo:openai/codex "sync" "comments" in:title,body,comments` | 88 / 88 | C02 = 1518 hits. Asked: nonzero hits; relevance assessed separately. |
| Q13 | `repo:openai/codex "Cowork tools" in:title,body,comments` | 1 / 1 | C01 = 3494 hits. Asked: nonzero hits; relevance assessed separately. |
| Q14 | `repo:openai/codex "Bundled skills and MCP servers" in:title,body,comments` | 1 / 1 | C01 = 3494 hits. Asked: nonzero hits; relevance assessed separately. |
| C03 | `repo:openai/codex is:pr "mcp" in:title,body,comments` | 282 / 100 | Positive control: hits. |
| Q15 | `repo:openai/codex is:pr "externalAgentConfig" in:title,body,comments` | 0 / 0 | C03 = 282 hits. Asked: no matches. |
| Q16 | `repo:openai/codex is:pr "migration" "claude" in:title,body,comments` | 1 / 1 | C03 = 282 hits. Asked: nonzero hits; relevance assessed separately. |
| C04 | `repo:openai/codex is:pr "mcp" "server" in:title,body,comments` | 180 / 100 | Positive control: hits. |
| C05 | `org:openai "config.toml" in:title,body,comments` | 3590 / 100 | Positive control: hits. |
| Q17 | `org:openai "import from another AI app" in:title,body,comments` | 0 / 0 | C05 = 3590 hits. Asked: no matches. |
| Q18 | `org:openai "keep imports in sync" in:title,body,comments` | 1 / 1 | C05 = 3590 hits. Asked: nonzero hits; relevance assessed separately. |
| Q19 | `repo:openai/codex "config.toml" "comments" "import" in:title,body,comments` | 28 / 28 | C02 = 1518 hits. Asked: nonzero hits; relevance assessed separately. |
| C06 | `repo:openai/codex "config.toml" "mcp" "server" in:title,body,comments` | 1368 / 100 | Positive control: hits. |
| C07 | `repo:openai/openai-python "OpenAI" in:title,body,comments` | 2422 / 100 | Positive control: hits. |
| Q20 | `repo:openai/openai-python "automatic sync" in:title,body,comments` | 0 / 0 | C07 = 2422 hits. Asked: no matches. |
| Q21 | `repo:openai/openai-python "settings import" in:title,body,comments` | 7 / 7 | C07 = 2422 hits. Asked: nonzero hits; relevance assessed separately. |
| Q22 | `repo:openai/openai-python "config.toml" in:title,body,comments` | 1 / 1 | C07 = 2422 hits. Asked: nonzero hits; relevance assessed separately. |
| C08 | `repo:openai/codex-universal "Docker" in:title,body,comments` | 34 / 34 | Positive control: hits. |
| Q23 | `repo:openai/codex-universal "automatic sync" in:title,body,comments` | 0 / 0 | C08 = 34 hits. Asked: no matches. |
| Q24 | `repo:openai/codex-universal "settings import" in:title,body,comments` | 0 / 0 | C08 = 34 hits. Asked: no matches. |
| Q25 | `repo:openai/codex-universal "config.toml" in:title,body,comments` | 2 / 2 | C08 = 34 hits. Asked: nonzero hits; relevance assessed separately. |
| DC1 | `repo:openai/codex "MCP"` | 105 / 100 | Positive control: hits. hasNextPage=true. |
| D01 | `repo:openai/codex "import from another AI app"` | 0 / 0 | DC1 = 105 hits. Asked: no matches. hasNextPage=false. |
| D02 | `repo:openai/codex "keep imports in sync"` | 0 / 0 | DC1 = 105 hits. Asked: no matches. hasNextPage=false. |
| D03 | `repo:openai/codex "automatic sync"` | 1 / 1 | DC1 = 105 hits. Asked: nonzero hits; relevance assessed separately. hasNextPage=false. |
| D04 | `repo:openai/codex "settings import"` | 0 / 0 | DC1 = 105 hits. Asked: no matches. hasNextPage=false. |
| DC2 | `repo:openai/openai-python "OpenAI"` | 97 / 97 | Positive control: hits. hasNextPage=false. |
| D05 | `repo:openai/openai-python "automatic sync"` | 1 / 1 | DC2 = 97 hits. Asked: nonzero hits; relevance assessed separately. hasNextPage=false. |
| D06 | `repo:openai/openai-python "settings import"` | 0 / 0 | DC2 = 97 hits. Asked: no matches. hasNextPage=false. |
| Q26 | `repo:openai/codex is:pr "external-agent-migration" in:title,body,comments` | 0 / 0 | C03 = 282 hits. Asked: no matches. |
| Q27 | `repo:openai/codex is:pr "import" "claude" in:title,body,comments` | 1 / 1 | C04 = 180 hits. Asked: nonzero hits; relevance assessed separately. |
| Q28 | `repo:openai/codex "config.toml" "comments" "stripped" in:title,body,comments` | 5 / 5 | C06 = 1368 hits. Asked: nonzero hits; relevance assessed separately. |
| Q29 | `repo:openai/codex "config.toml" "comments" "removed" in:title,body,comments` | 62 / 62 | C06 = 1368 hits. Asked: nonzero hits; relevance assessed separately. |
| Q30 | `repo:openai/codex "MCP" "import" "sync" in:title,body,comments` | 46 / 46 | C06 = 1368 hits. Asked: nonzero hits; relevance assessed separately. |
| Q31 | `repo:openai/codex "external-agent-import-sync" in:title,body,comments` | 2 / 2 | C01 = 3494 hits. Asked: nonzero hits; relevance assessed separately. |
| Q32 | `org:openai "externalAgentConfig" in:title,body,comments` | 10 / 10 | C05 = 3590 hits. Asked: nonzero hits; relevance assessed separately. |
| C09 | `repo:openai/codex-plugin-cc "transfer" in:title,body,comments` | 38 / 38 | Positive control: hits. |
| Q33 | `repo:openai/codex-plugin-cc "automatic sync" in:title,body,comments` | 0 / 0 | C09 = 38 hits. Asked: no matches. |
| Q34 | `repo:openai/codex-plugin-cc "content to sync" in:title,body,comments` | 0 / 0 | C09 = 38 hits. Asked: no matches. |
| Q35 | `repo:openai/codex-plugin-cc "settings import" in:title,body,comments` | 0 / 0 | C09 = 38 hits. Asked: no matches. |
| DC3 | `org:openai "MCP"` | 113 / 100 | Positive control: hits. hasNextPage=true. |
| D07 | `org:openai "import from another AI app"` | 0 / 0 | DC3 = 113 hits. Asked: no matches. hasNextPage=false. |
| D08 | `org:openai "keep imports in sync"` | 0 / 0 | DC3 = 113 hits. Asked: no matches. hasNextPage=false. |
| D09 | `repo:openai/codex "content to sync"` | 0 / 0 | DC1 = 105 hits. Asked: no matches. hasNextPage=false. |
| D10 | `repo:openai/codex "config.toml" "overwritten"` | 1 / 1 | DC4 = 18 hits. Asked: nonzero hits; relevance assessed separately. hasNextPage=false. |
| DC4 | `repo:openai/codex "config.toml" "MCP"` | 18 / 18 | Positive control: hits. hasNextPage=false. |

### Direct fetch audit

Direct issue/comment/repository/source fetches are not searches, so result counts and search controls are not applicable. All API fetches are recorded in the retained incremental journal below and in raw `<ID>.http.txt` files. Source responses include the Git blob SHA and Base64 contents. S00 identifies the pinned main commit; S01 lists the migration crate; S02–S18 retrieve the inspected implementation and the plugin/session paths it calls. Directory responses are discovery only, not proof of implementation behavior.

- **E01** fetch `repos/openai/codex/issues/24515` — HTTP 200; object fetched; evidence `E01.http.txt`. Fetch, not a search; result count/control not applicable.
- **E01C** fetch `repos/openai/codex/issues/24515/comments?per_page=100` — HTTP 200; 1 records; evidence `E01C.http.txt`. Fetch, not a search; result count/control not applicable.
- **E02** fetch `repos/openai/codex/issues/39568` — HTTP 200; object fetched; evidence `E02.http.txt`. Fetch, not a search; result count/control not applicable.
- **E02C** fetch `repos/openai/codex/issues/39568/comments?per_page=100` — HTTP 200; 0 records; evidence `E02C.http.txt`. Fetch, not a search; result count/control not applicable.
- **E03** fetch `repos/openai/codex/issues/40147` — HTTP 200; object fetched; evidence `E03.http.txt`. Fetch, not a search; result count/control not applicable.
- **E03C** fetch `repos/openai/codex/issues/40147/comments?per_page=100` — HTTP 200; 5 records; evidence `E03C.http.txt`. Fetch, not a search; result count/control not applicable.
- **E04** fetch `repos/openai/codex/issues/41371` — HTTP 200; object fetched; evidence `E04.http.txt`. Fetch, not a search; result count/control not applicable.
- **E04C** fetch `repos/openai/codex/issues/41371/comments?per_page=100` — HTTP 200; 1 records; evidence `E04C.http.txt`. Fetch, not a search; result count/control not applicable.
- **E05** fetch `repos/openai/codex/issues/19372` — HTTP 200; object fetched; evidence `E05.http.txt`. Fetch, not a search; result count/control not applicable.
- **E05C** fetch `repos/openai/codex/issues/19372/comments?per_page=100` — HTTP 200; 0 records; evidence `E05C.http.txt`. Fetch, not a search; result count/control not applicable.
- **R01** fetch `repos/openai/codex` — HTTP 200; object fetched; evidence `R01.http.txt`. Fetch, not a search; result count/control not applicable.
- **R02** fetch `repos/openai/openai-python` — HTTP 200; object fetched; evidence `R02.http.txt`. Fetch, not a search; result count/control not applicable.
- **R03** fetch `repos/openai/codex-universal` — HTTP 200; object fetched; evidence `R03.http.txt`. Fetch, not a search; result count/control not applicable.
- **S00** fetch `repos/openai/codex/commits/main` — HTTP 200; object fetched; evidence `S00.http.txt`. Fetch, not a search; result count/control not applicable.
- **S01** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src?ref=main` — HTTP 200; 31 records; evidence `S01.http.txt`. Fetch, not a search; result count/control not applicable.
- **S02** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/service.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S02.http.txt`. Fetch, not a search; result count/control not applicable.
- **S03** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/mcp.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S03.http.txt`. Fetch, not a search; result count/control not applicable.
- **S04** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/config_values.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S04.http.txt`. Fetch, not a search; result count/control not applicable.
- **S05** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/plugins.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S05.http.txt`. Fetch, not a search; result count/control not applicable.
- **S06** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/subagents.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S06.http.txt`. Fetch, not a search; result count/control not applicable.
- **S07** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/hooks_cla.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S07.http.txt`. Fetch, not a search; result count/control not applicable.
- **S08** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/scope.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S08.http.txt`. Fetch, not a search; result count/control not applicable.
- **S09** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/model.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S09.http.txt`. Fetch, not a search; result count/control not applicable.
- **S10** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/source_cla.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S10.http.txt`. Fetch, not a search; result count/control not applicable.
- **S11** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/hooks_common.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S11.http.txt`. Fetch, not a search; result count/control not applicable.
- **S12** fetch `repos/openai/codex/contents/codex-rs/core-plugins/src?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; 67 records; evidence `S12.http.txt`. Fetch, not a search; result count/control not applicable.
- **S13** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/sessions?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; 14 records; evidence `S13.http.txt`. Fetch, not a search; result count/control not applicable.
- **E06** fetch `repos/openai/codex/issues/39923` — HTTP 200; object fetched; evidence `E06.http.txt`. Fetch, not a search; result count/control not applicable.
- **E06C** fetch `repos/openai/codex/issues/39923/comments?per_page=100` — HTTP 200; 0 records; evidence `E06C.http.txt`. Fetch, not a search; result count/control not applicable.
- **S14** fetch `repos/openai/codex/contents/codex-rs/core-plugins/src/manager.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S14.http.txt`. Fetch, not a search; result count/control not applicable.
- **S15** fetch `repos/openai/codex/contents/codex-rs/core-plugins/src/store.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S15.http.txt`. Fetch, not a search; result count/control not applicable.
- **S16** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/sessions/ledger.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S16.http.txt`. Fetch, not a search; result count/control not applicable.
- **S17** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/sessions/mod.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S17.http.txt`. Fetch, not a search; result count/control not applicable.
- **E07** fetch `repos/openai/codex-plugin-cc/pulls/701` — HTTP 200; object fetched; evidence `E07.http.txt`. Fetch, not a search; result count/control not applicable.
- **R04** fetch `repos/openai/codex-plugin-cc` — HTTP 200; object fetched; evidence `R04.http.txt`. Fetch, not a search; result count/control not applicable.
- **E08C** fetch `repos/openai/codex/issues/26338/comments?per_page=100` — HTTP 200; 13 records; evidence `E08C.http.txt`. Fetch, not a search; result count/control not applicable.
- **E09C** fetch `repos/openai/codex/issues/26351/comments?per_page=100` — HTTP 200; 3 records; evidence `E09C.http.txt`. Fetch, not a search; result count/control not applicable.
- **E10** fetch `repos/openai/codex/issues/42116` — HTTP 200; object fetched; evidence `E10.http.txt`. Fetch, not a search; result count/control not applicable.
- **E10C** fetch `repos/openai/codex/issues/42116/comments?per_page=100` — HTTP 200; 0 records; evidence `E10C.http.txt`. Fetch, not a search; result count/control not applicable.
- **S18** fetch `repos/openai/codex/contents/codex-rs/external-agent-migration/src/lib.rs?ref=6ab3ae532346a7e900bcef8323a0a18f3764b504` — HTTP 200; object fetched; evidence `S18.http.txt`. Fetch, not a search; result count/control not applicable.

The original incremental report is preserved at `import-sync-tracker-evidence/incremental-journal.md`. All exact queries, warnings, and intermediate relevance decisions survive consolidation. Workspace status initially showed `sources/codex-docs.manifest` modified and later became clean during this lane; this lane never wrote that file or any tracked path. No commit, push, issue comment, or other message to a third party was made.

Final artifact checks: all 58 retained search rows plus preliminary C00 are present; all 18 zero-count searches have a positive matching-scope control; no retained API response has an HTTP failure; all 15 downloaded source-file contents match their Git blob SHA. These validate evidence handling, not the installed desktop behavior.

## GitHub repos touched

- `openai/codex` — primary issue/PR/discussion tracker; direct issue/comment reads; pinned public external-agent migration and plugin/session implementation that establishes independent MCP writes and category destinations.
- `openai/openai-python` — requested alternate tracker; repository metadata, issue/PR searches, and discussion searches with working repo-specific controls; no relevant desktop import contract established in reviewed results.
- `openai/codex-universal` — requested alternate tracker; Docker-environment repository metadata and issue/PR searches with working control; API reports discussions disabled, so no discussion absence was inferred from a failed search.
- `openai/codex-plugin-cc` — discovered by organization-wide RPC search; transfer-related issues/PRs, direct unmerged PR #701 and repository metadata; focused desktop-UI phrase searches controlled by known transfer hits. API reports discussions disabled.
