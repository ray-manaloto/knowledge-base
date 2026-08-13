---
type: "query"
date: "2026-08-11T03:42:24.142719+00:00"
question: "How should Codex and Claude Code plugins and skills become critical versioned dependencies across dotfiles and knowledge-base?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["skills_list_excludes_plugin_skills_when_workspace_codex_plugins_disabled()", "Plugins", "SkillsListResponse", "parity.py"]
---

# Q: How should Codex and Claude Code plugins and skills become critical versioned dependencies across dotfiles and knowledge-base?

## Answer

Knowledge-base owns the reusable kb_setup.currency engine, shared dependency profile, source manifests, research extractions, release-note receipts, and compatibility probes; each consumer repo owns desired membership, surface-specific adaptations and apply authority. Extend currency config with plugin and skill identities rather than building a second engine. Use native claude plugin list/update/validate/eval and codex plugin list/marketplace commands as adapters; use gh skill list and gh skill update --dry-run for project skills. Treat gh skill rc=0 with no GitHub metadata as NOT CHECKED, not current. Track explicit plugin version plus source commit and content hashes because unchanged version with changed upstream bytes is a provenance anomaly. Current adopted plugin sources in knowledge-base drift from active marketplace commits for fable-orchestrator, last30days, mattpocock and skillopt; wshobson agents matches. Several active plugin repositories have no knowledge-base source manifest. Require current and candidate harness compatibility, exact component discovery, hook and MCP trust diff, negative mutation arms, and full repository gates before updating.

## Outcome

- Signal: useful

## Source Nodes

- skills_list_excludes_plugin_skills_when_workspace_codex_plugins_disabled()
- Plugins
- SkillsListResponse
- parity.py