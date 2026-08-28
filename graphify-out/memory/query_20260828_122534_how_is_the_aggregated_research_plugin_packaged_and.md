---
type: "query"
date: "2026-08-28T12:25:34.909567+00:00"
question: "How is the aggregated-research plugin packaged and installed (slice 2), and what did the arms find?"
contributor: "graphify"
outcome: "useful"
---

# Q: How is the aggregated-research plugin packaged and installed (slice 2), and what did the arms find?

## Answer

Plugin slice 2 (2026-08-28): the aggregated-research plugin now lives in ray-manaloto/claude-code-marketplace (main 20795c8, tag pre-reset-2026-08-27 keeps the old tree). Marketplace name is `ray-manaloto` — `claude-code-marketplace` is on Anthropic's RESERVED list (plugin-marketplaces.md:166) and refuses to load. The CLI is delivered mise-first: the plugin ships mise.toml pinning `"pipx:git+<url>" = "<sha>"` (a ref in the tool NAME is dropped by mise's pipx backend — measured, uv got the URL without @ref); the SessionStart hook runs `mise install` into $CLAUDE_PLUGIN_DATA with MISE_GLOBAL_CONFIG_FILE/MISE_SYSTEM_CONFIG_FILE pointed at the plugin's own mise.toml (without them it installed the user's whole global config: 128 tools, 2.3 GB) and MISE_TRUSTED_CONFIG_PATHS (non-interactive mise cannot prompt to trust). bin/ wrappers put `aggregated-research` and `ty` on the Bash tool's PATH; they read the data dir the hook records in ${CLAUDE_PLUGIN_ROOT}/.data-dir because Bash-tool commands do not receive ${CLAUDE_PLUGIN_DATA}. Repo K: kb_setup.plugin_validate (jsonschema via validator.evolve, claude plugin validate WITHOUT --strict — the no-version choice is a warning under --strict — findings scanned by the ❯ line prefix), marketplace registered in settings.json, local skill deleted. Arms: hook 4 s warm, 0 s no-op; live validate 5/5; #559 n=3 and n=4 (both implementer lanes wrote files themselves; the reviewer lane ran a real codex process). Host hazard: the orphaned mise git shim breaks uv's submodule step (`mise prune`).


## Outcome

- Signal: useful