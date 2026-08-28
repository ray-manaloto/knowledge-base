---
type: "query"
date: "2026-08-28T14:20:34.110555+00:00"
question: "Why did the aggregated-research plugin not install here, and what did its SessionStart hook do on a real host vs a container (slice 3)?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did the aggregated-research plugin not install here, and what did its SessionStart hook do on a real host vs a container (slice 3)?

## Answer

The aggregated-research plugin never installed from the project's enabledPlugins alone (Claude Code >=2.1.195, discover-plugins.md:486); installed by hand with the README's two commands. Its SessionStart hook then had three host-only defects, each measured on the Mac and each invisible in a container: (1) MISE_GLOBAL_CONFIG_FILE confines nothing because ~/.config/mise/config.toml is a hierarchy filename (configuration.md:15) — 8.3 GB / 408 s / rc 1; fix MISE_CEILING_PATHS=$PLUGIN_ROOT (configuration.md:633). (2) uv's git checkout under ~/Library/Caches/uv is untrusted to the mise git shim under MISE_TRUSTED_CONFIG_PATHS=$PLUGIN_ROOT — fix UV_CACHE_DIR=$DATA/uv + trust $ROOT:$DATA. (3) mise exec in a mise-activated shell keeps the old PATH under a redirected MISE_DATA_DIR — fix unset __MISE_DIFF __MISE_SESSION __MISE_ORIG_PATH. Clean cold arm with all three: rc 0, 47 s, 1.3 GB. Slice 3 (marketplace PR #1, squash 05acca22): one bin/mise-env shim for hook + wrappers, .data-dir deleted (plugins-reference.md:713), mise-OCI container CI (jdx/mise-action v4.3.0, sudo -E for apt layers, allow_builds for claude-code's postinstall, build-essential for tree-sitter-dm, base image by digest, apt pinned) with one mise oci run executing ci/acceptance.sh: marketplace add needs NO Claude auth (N2 rc=0), hook confined, CLI ran directly and via claude -p, evidence = files written with --out and checked by jq. Not done: the agent-driven INSTALL (marketplace #2).


## Outcome

- Signal: useful