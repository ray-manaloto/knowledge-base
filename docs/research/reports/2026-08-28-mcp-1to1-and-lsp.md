# MCP 1:1-with-CLI feasibility, and ty/pyrefly LSP integration

Research lane, read-only on the repo. All probes run in
`/private/tmp/.../scratchpad/mcp-probe/` (gitignored scratch, not committed).
Graph queried first per `research-doc-sources.md` step 0 (see "Graph control
arm" below) — it returned only unrelated code from other ingested sources, so
this answer is external research, sourced from PyPI/GitHub/deps.dev APIs and
this repo's own `sources/claude-code-docs` mirror.

## Answer (headline)

- **MCP spec: current revision is `2026-07-28`** (confirmed two ways: GitHub's
  `schema/` directory listing, and `mcp` 2.1.1's own `LATEST_PROTOCOL_VERSION`
  constant, live-probed). The **python-sdk (`mcp` on PyPI) is on 2.1.1**
  (released 2026-08-25), which implements that revision.
- **1:1 is achievable and the right shape is (i): hand-register one `@mcp.tool`
  wrapper per verb, calling the SAME function the CLI calls** — not a
  CLI-framework-introspecting generator. `aggregated-research`'s CLI
  (`python/src/kb_setup/research/cli.py:9-46`) is a bare argv router with no
  Click/Typer/argparse framework underneath (confirmed by reading the file:
  no such import, just `sys.argv` slicing and an `if verb not in _VERBS`
  dispatch to `kb_setup.cli.main`). The generator libraries that exist
  (`click-mcp`, `mcp-cli`) introspect a **Click** app's command tree — there is
  no Click tree here to introspect, so they don't apply, and even where they
  would, they add a source of drift (a second library owning the schema)
  rather than removing one.
- **mcp 2.x renamed `FastMCP` → `MCPServer`.** `from mcp.server.fastmcp import
  FastMCP` raises `ModuleNotFoundError` on 2.1.1 with a migration pointer
  (probed live, see prototype transcript). The plugin should target
  `from mcp.server.mcpserver import MCPServer` (mcp ≥2.0) or pin `mcp<2` and
  keep using `FastMCP` — a real compatibility decision, not a naming footnote.
- **Transport: stdio for the plugin.** Per this repo's own
  `research-doc-sources.md`, native MCP registration injects the tool
  schema into every conversation's system prompt — the reason this repo
  prefers `mcp2cli` for one-off calls. A plugin's `.mcp.json` supports stdio
  (child process), SSE, and HTTP (`command`/`type: "sse"`/`type: "http"` —
  see the plugin's own `mcp-integration` skill, cited below); stdio is the
  right default for a locally-installed CLI wrapper — no separate service to
  run or auth, matches how `.mcp.json` already registers other local-process
  servers in this ecosystem.
- **`ty` already ships an LSP server**: `ty server` (subcommand, confirmed via
  `--help`), pinned here at `0.0.74` (`sources/ty.manifest`,
  `pyproject.toml` `[dependency-groups] dev`). **`pyrefly` also ships one**:
  `pyrefly lsp` (subcommand, confirmed via `--help`), latest GitHub release
  `1.2.0` (2026-08-01), repo pushed 2026-08-28 (actively maintained, 6,908
  stars, not archived). Both fit the plugin `.lsp.json` schema directly
  (`command` + `extensionToLanguage`, both required; stdio is the only
  transport Claude Code actually runs regardless of what `transport` says).

## PART A — MCP 1:1

### A1. Spec version and python-sdk state

- GitHub `modelcontextprotocol/modelcontextprotocol` `schema/` directory
  (`https://api.github.com/repos/modelcontextprotocol/modelcontextprotocol/contents/schema`):
  `['2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25', '2026-07-28',
  'draft']` — newest non-draft is **`2026-07-28`**.
- `mcp` on PyPI: latest is **`2.1.1`**, published 2026-08-25T16:13:59Z
  (`https://pypi.org/pypi/mcp/json`, `info.version`). Release history shows
  the project runs **two parallel lines** — `1.29.x` and `2.x` — with `1.29.1`
  (2026-08-24) and `2.0.1` (2026-08-26) both shipping after `2.1.0`/`2.1.1`;
  pip/uv dependency resolution picks `2.1.1` as latest by version-ordering
  regardless of upload date.
- Installed and introspected `mcp==2.1.1` directly (not from a changelog):
  `mcp.types.LATEST_PROTOCOL_VERSION == '2026-07-28'` — matches the schema
  directory's newest entry, so the sdk claim and the spec-repo claim
  cross-verify each other (a genuine cross-check, not two readings of one
  source).
- `requires_python: >=3.10` for `mcp` (this repo pins Python 3.14 in
  `pyproject.toml`, well inside range — not measured further here since
  `mise install` already runs Python 3.14 successfully for other deps).

### A2. The 1:1 mechanism

**(i) Hand-register `@mcp.tool` (or `MCPServer.tool()` on mcp 2.x) wrappers
around the verb functions, sharing one function and one schema.** This is
what the prototype below demonstrates. For `aggregated-research`, each verb
(today: `trackers`) already returns a msgspec `Struct`
(`kb_setup/generated/research_record.py` — `AdapterRecord`, generated from a
schema, `Struct` types are `msgspec.Struct` not pydantic). The MCP tool
wrapper would be: import the verb's Python entrypoint (not the CLI's argv
router — that's just an `if verb in _VERBS` dispatcher, nothing to share
there), register it once with `@mcp.tool()`, and let both the CLI's
`kb_setup.cli.main(["research-trackers", ...])` path and the MCP tool call
the same underlying function. **Open question, not measured this session:**
whether `MCPServer.tool()`'s schema generation (built on pydantic in both 1.x
`FastMCP` and 2.x `MCPServer`) accepts a `msgspec.Struct` return type
directly, or needs a `msgspec.to_builtins()` conversion at the tool-function
boundary. Cheap to test in a follow-up (~10 min), flagged rather than
guessed.

**(ii) CLI-framework-introspecting generators — do not apply here.**
Searched PyPI + GitHub:

| Package | PyPI | Latest | Repo pushed | Stars | What it does |
|---|---|---|---|---|---|
| `click-mcp` | 200 (exists) | 0.6.1 | 2026-07-20 | 14 | `@click_mcp` decorator converts a **Click** app's command tree into MCP tools automatically |
| `mcp-cli` | 200 (exists) | 0.20.1 | not checked | not checked | "A cli for the Model Context Provider" — an MCP **client** CLI, not a CLI→MCP generator (name is a false-positive match) |
| `typer-mcp` | 404 (absent) | — | — | — | does not exist on PyPI |
| `argparse-mcp` | 404 (absent) | — | — | — | does not exist on PyPI |

`fastmcp` (the standalone `jlowin/fastmcp` project, PyPI `fastmcp==3.4.7`,
distinct from the `mcp` package's bundled server) supports generating tools
`from_openapi`/`from_fastapi` (mentioned in its README) but nothing
CLI-framework-shaped was found there either — not read in full, flagged as
**not measured** rather than asserted absent.

None of this matters for `aggregated-research` specifically: the CLI has no
Click/Typer/argparse object to introspect (confirmed by reading
`cli.py:9-46` — it's `sys.argv` slicing), so a generator has nothing to
generate from. **Recommendation: (i), by construction — there is no (ii) to
choose here.**

**(iii) Generate the CLI from the MCP tool definitions (the reverse)** — this
repo already uses the reverse-direction tool for it: `mcp2cli`
(`research-doc-sources.md` names it as the preferred one-off MCP caller), and
the installed plugin ships `mcp2cli:convert` / `mcp2cli:mcp-codegen` skills
specifically for turning an *existing* MCP server into a CLI. That is the
opposite of this repo's shape (CLI exists first, MCP surface is being added
on top), so it answers a different question than the one asked, but it is the
concrete tool for "MCP-first, CLI-generated" if the direction ever reverses.

### Prototype: ran a live round trip

`proto_server.py` (18 lines of substance) registers one tool via
`MCPServer.tool()` wrapping a plain function; `client_probe.py` drives it over
stdio with the SDK's own client. Full transcript:

```
$ uv run --quiet --with "mcp[cli]==2.1.1" python client_probe.py
TOOLS: ['trackers']
SCHEMA: {'properties': {'query': {'title': 'Query', 'type': 'string'}, 'limit': {'default': 5, 'title': 'Limit', 'type': 'integer'}}, 'required': ['query'], 'type': 'object', 'title': 'trackersArguments'}
CALL RESULT: [TextContent(type='text', text='{\n  "query": "aggregated-research",\n  "limit": 3,\n  "results": [\n    "tracker-0",\n    "tracker-1",\n    "tracker-2"\n  ]\n}', annotations=None, meta=None)]
```

Two real defects surfaced and were fixed live (recorded because they are the
actual 2.x migration cost, not hypothetical):
1. `from mcp.server.fastmcp import FastMCP` → `ModuleNotFoundError` on 2.1.1,
   with the SDK's own error message pointing at
   `from mcp.server.mcpserver import MCPServer` (or pin `mcp<2`).
2. `Tool.inputSchema` → `Tool.input_schema` (snake_case rename on the client
   result type too).

### A3. Transport for the plugin's MCP

This repo's own `.claude/rules/research-doc-sources.md` states the cost
explicitly: native MCP registration "injects every tool's JSON schema into
Claude's system prompt for every conversation, forever — even conversations
that never call the tool." That is the standing argument for `mcp2cli`-first
generally; it applies here too, but Ray's question is about the **plugin's**
MCP surface specifically (for other consumers, not just this session), where
registration is the point.

The installed `plugin-dev:mcp-integration` skill documents three transports
for a plugin's `.mcp.json`:
(`/Users/rmanaloto/.claude/plugins/cache/claude-plugins-official/plugin-dev/e33a9ec0973a/skills/mcp-integration/SKILL.md:67-129`)
- **stdio** (local child process) — "Best for local tools and custom
  servers."
- **SSE** (`"type": "sse", "url": "..."`)
- **HTTP** (`"type": "http", "url": "..."`)

For `aggregated-research` — a locally-installed uv package, no auth, no
hosted service — **stdio** is the fit: `command: "uv", args: ["run",
"aggregated-research-mcp"]` (or similar), no separate deployment, and this
repo's own `.mcp.json` already registers two servers this way for comparison
(`graphify` and `repowise` are actually both `type: "http"` in this repo's
current `.mcp.json` — those are hosted third-party services, a different
case from a locally-installed CLI).

## PART B — LSP

### B4. `ty` and `pyrefly`

**`ty`**: ships `ty server` — confirmed live:
```
$ uv run --with "ty==0.0.74" ty --help
Commands:
  check    Check a project for type errors
  server   Start the language server
  ...
$ uv run --with "ty==0.0.74" ty server --help
Start the language server
Usage: ty server
```
Already pinned in this repo: `pyproject.toml` `[dependency-groups] dev`
`ty==0.0.74`, tracked in `sources/ty.manifest` (astral-sh/ty, tag `0.0.74`,
commit `00199f0aaa6a8cd264fea08eae4f3c3fe4451c17`). It's already an installed,
already-vetted binary — no new install step for the LSP entry beyond pointing
at the same pin.

**`pyrefly`**: `facebook/pyrefly` — `pushed_at: 2026-08-28T05:52:45Z`,
`stargazers_count: 6908`, `archived: false` (`gh api repos/facebook/pyrefly`).
Latest GitHub release: `1.2.0`, published 2026-08-01
(`gh api repos/facebook/pyrefly/releases/latest`). Not currently pinned
anywhere in this repo. Install path: **not** `mise ls-remote pyrefly` — that
errors (`pyrefly not found in mise tool registry`, control-armed against
`mise ls-remote ty` which correctly lists `0.0.71..0.0.75`). The working mise
backend is **`pipx:pyrefly`** — `mise ls-remote pipx:pyrefly` lists
`0.64.1, 1.0.0, 1.1.0, 1.1.1, 1.2.0`, matching the GitHub release. Ships
`pyrefly lsp` — confirmed live:
```
$ uv tool run --from pyrefly==1.2.0 pyrefly --help
Commands:
  ...
  lsp          Start an LSP server
  tsp          Start a TSP server
  ...
$ uv tool run --from pyrefly==1.2.0 pyrefly lsp --help
Start an LSP server
Usage: pyrefly lsp [OPTIONS]
  --indexing-mode <INDEXING_MODE>  [default: lazy-non-blocking-background]
```

### B5. The `.lsp.json` shape and the pre-install rule

Read verbatim from this repo's own ingested docs mirror,
`sources/claude-code-docs/content/en/docs/claude-code/plugins-reference.md:189-270`
(the file whose manifest — `sources/claude-code-docs.manifest` —
specifically states it's the mirror `currency.toml` reads release notes
from, so it's the primary source, not a secondary one).

Required fields: `command`, `extensionToLanguage`. Optional: `args`,
`transport` (`stdio` default — **"Claude Code accepts `socket` but runs every
server over stdio, so the stdout protocol rules apply to all servers"**,
`plugins-reference.md:236`), `env`, `initializationOptions`, `settings`,
`workspaceFolder`, `startupTimeout`, `shutdownTimeout`, `restartOnCrash`
(default `true`), `maxRestarts`, `diagnostics` (default `true`).

**The pre-install rule, cited verbatim** (`plugins-reference.md:258-261`):
> "**You must install the language server binary separately.** LSP plugins
> configure how Claude Code connects to a language server, but they don't
> include the server itself. If you see `Executable not found in $PATH` in
> the `/plugin` Errors tab, install the required binary for your language."

This matters concretely here: both `ty` and `pyrefly` resolve via `mise`
(project-scoped, per this repo's `mise-first` convention) — `ty` is already
pinned, `pyrefly` would need a new `mise.toml` entry (`pipx:pyrefly`) plus a
`currency.toml` `[tool.pyrefly]` block per this repo's currency-tracking
convention, in the SAME change that adds the `.lsp.json` entry (per
`tool-currency-and-native-first.md`).

Also relevant: `plugins-reference.md:251` — **"Multiple servers for the same
extension… the first server registered handles files with that extension and
the others never start."** Both `ty` and `pyrefly` claim `.py`. Registering
both in the same `.lsp.json` under the same `extensionToLanguage: {".py":
"python"}` key means only one actually runs; they'd need either (a) only one
registered, or (b) Claude Code's documented per-plugin precedence understood
before shipping both (not tested this session — the doc names the behavior
but a live two-server conflict wasn't reproduced here; flagged, not
measured).

### B5 draft entries

```json
{
  "python-ty": {
    "command": "ty",
    "args": ["server"],
    "extensionToLanguage": { ".py": "python" }
  }
}
```
```json
{
  "python-pyrefly": {
    "command": "pyrefly",
    "args": ["lsp"],
    "extensionToLanguage": { ".py": "python" }
  }
}
```
Both binaries must resolve on `PATH` (per the pre-install rule above) — via
mise shims once `pyrefly` is pinned the same way `ty` already is. Shipping
BOTH under `.py` is the documented-conflict case above; ship one, or gate the
other behind a user-config toggle, is a decision for Ray/the plugin author,
not settled by this research.

## Every null with its arm

- `typer-mcp` / `argparse-mcp` on PyPI: `404`, control-armed against
  `click-mcp`/`mcp-cli` (`200`) and against the bogus-package control
  (`this-package-does-not-exist-zzz-xyz-99999` → `404`) — the probe
  discriminates real-absent from a broken query.
- `mise ls-remote pyrefly`: errors "not found in mise tool registry",
  control-armed against `mise ls-remote ty` (lists versions correctly) —
  confirms the error is pyrefly-specific (no direct-name mise backend), not a
  broken `mise ls-remote` invocation. `pipx:pyrefly` resolves correctly,
  which is the positive arm proving the null wasn't a mise-wide fault.
- Initial graph query for "MCP server FastMCP python-sdk aggregated-research
  CLI" returned 263 nodes, all irrelevant (codex-rs, pkl-server, basic_memory
  — unrelated ingested sources), truncated at 64/263 shown. Not control-armed
  against a known-present term in the same query shape (budget did not allow
  a second full graph round-trip within the ~25 min bound) — reported as "the
  graph does not carry this answer" on the strength of relevance-inspection
  of the 64 shown nodes, not a verified-empty result. Flagged as the one
  weaker claim in this report.

## Not measured

- Whether `MCPServer.tool()` (mcp 2.x) accepts a `msgspec.Struct` return type
  directly vs. requiring `msgspec.to_builtins()` conversion at the boundary.
- `mcp-cli`'s actual feature set beyond its PyPI summary (it is an MCP
  *client*, not a generator — established from the name, not from reading its
  source).
- `fastmcp` (jlowin/fastmcp, the standalone 3.4.7 package)'s full feature set
  beyond the `from_openapi`/`from_fastapi` mention in its README header.
- Live reproduction of the documented "first LSP registered wins" conflict
  for two servers claiming `.py`.
- `mcp2cli`'s exact conversion mechanics (only its purpose, from its skill
  descriptions in this session's system reminder, and its role per
  `research-doc-sources.md`).

## GitHub repos touched

- [modelcontextprotocol/modelcontextprotocol](https://github.com/modelcontextprotocol/modelcontextprotocol) — spec `schema/` directory listing, current revision `2026-07-28`
- [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) — the `mcp` PyPI package's upstream repo (referenced, not directly fetched — version data came from PyPI/deps.dev and the installed package itself)
- [jlowin/fastmcp](https://github.com/jlowin/fastmcp) — standalone FastMCP project (`fastmcp` PyPI package, distinct from `mcp.server.fastmcp`), README skim for `from_openapi`/`from_fastapi`
- [crowecawcaw/click-mcp](https://github.com/crowecawcaw/click-mcp) — CLI(Click)→MCP generator, README read in full, repo metadata pulled
- [facebook/pyrefly](https://github.com/facebook/pyrefly) — repo metadata, latest release, `--help`/`lsp --help` probed against the installed binary
- [astral-sh/ty](https://github.com/astral-sh/ty) — already an ingested source here (`sources/ty.manifest`); `server` subcommand probed against the pinned `0.0.74` binary
