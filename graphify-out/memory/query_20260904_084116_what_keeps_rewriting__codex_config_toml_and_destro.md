---
type: "query"
date: "2026-09-04T08:41:16.256350+00:00"
question: "What keeps rewriting .codex/config.toml and destroying its comments and mcp_servers block?"
contributor: "graphify"
outcome: "corrected"
correction: "The ChatGPT desktop app's \"Import from another AI app\" sync -- NOT a config\ngenerator, and not anything inside this repo or its plugin tree.\n\nTwo arms, both decisive:\n\n1. The six keys the rewrite ADDED are a verbatim copy of `.claude/settings.json`'s\n   own `env` block -- same keys, same values, same order, including\n   `OTEL_LOG_RAW_API_BODIES = \"file:.agent/telemetry/\"`, which is THIS\n   REPOSITORY'S path. No third-party tool can know it. Something read Claude\n   Code's settings and wrote them into codex's `shell_environment_policy`, which\n   is what an IMPORTER does and what a generator does not.\n\n2. Timestamps agree to the minute: recorded write `2026-09-04T08:29:51Z` =\n   03:29:51 AM CDT; ChatGPT > Settings > Import > Import history reads\n   \"Imported from Claude Code, Sep 4 2026, 3:30 AM, 12 imported\", itemised as\n   Settings 1, MCP servers 1, Sessions 10. \"MCP servers 1\" IS the `[mcp_servers]`\n   block reported destroyed. It was replaced by an import, not lost to a template.\n\n\"Keep imports in sync\" is ON, so this RECURS. It is a supported, user-enabled\nfirst-party feature -- there is nothing to uninstall and nothing to trace.\n\nWHY THREE HUNTS MISSED IT, which is the durable part. This is the third\noccurrence (#399) and the third wrong attribution; the first two refuted ELEVEN\ncandidate writers. None of the three asked \"what else on this machine READS\nClaude Code's configuration\". All three searched the repository and the plugin\ntree, because that is where a repo-shaped search looks. The writer was a\nfirst-party desktop app with a sync toggle, outside every search any of them ran.\n\nMY OWN ERROR, stated because it is the reusable one: I found the only thing on\nthe machine that MENTIONED both `shell_environment_policy` and\n`OTEL_LOG_RAW_API_BODIES` and reported it as the writer. That is a claim about\nCAPABILITY, not about AUTHORSHIP, and no probe I ran separated the two. The tell\nwas already in my own issue body -- \"nothing invokes it that I can find\", plus a\nplugin that is DISABLED. I filed that as a loose end when it was the refutation.\nA candidate that cannot be shown to have RUN is not a writer.\n"
---

# Q: What keeps rewriting .codex/config.toml and destroying its comments and mcp_servers block?

## Answer

The ChatGPT desktop app's "Import from another AI app" sync -- NOT a config
generator, and not anything inside this repo or its plugin tree.

Two arms, both decisive:

1. The six keys the rewrite ADDED are a verbatim copy of `.claude/settings.json`'s
   own `env` block -- same keys, same values, same order, including
   `OTEL_LOG_RAW_API_BODIES = "file:.agent/telemetry/"`, which is THIS
   REPOSITORY'S path. No third-party tool can know it. Something read Claude
   Code's settings and wrote them into codex's `shell_environment_policy`, which
   is what an IMPORTER does and what a generator does not.

2. Timestamps agree to the minute: recorded write `2026-09-04T08:29:51Z` =
   03:29:51 AM CDT; ChatGPT > Settings > Import > Import history reads
   "Imported from Claude Code, Sep 4 2026, 3:30 AM, 12 imported", itemised as
   Settings 1, MCP servers 1, Sessions 10. "MCP servers 1" IS the `[mcp_servers]`
   block reported destroyed. It was replaced by an import, not lost to a template.

"Keep imports in sync" is ON, so this RECURS. It is a supported, user-enabled
first-party feature -- there is nothing to uninstall and nothing to trace.

WHY THREE HUNTS MISSED IT, which is the durable part. This is the third
occurrence (#399) and the third wrong attribution; the first two refuted ELEVEN
candidate writers. None of the three asked "what else on this machine READS
Claude Code's configuration". All three searched the repository and the plugin
tree, because that is where a repo-shaped search looks. The writer was a
first-party desktop app with a sync toggle, outside every search any of them ran.

MY OWN ERROR, stated because it is the reusable one: I found the only thing on
the machine that MENTIONED both `shell_environment_policy` and
`OTEL_LOG_RAW_API_BODIES` and reported it as the writer. That is a claim about
CAPABILITY, not about AUTHORSHIP, and no probe I ran separated the two. The tell
was already in my own issue body -- "nothing invokes it that I can find", plus a
plugin that is DISABLED. I filed that as a loose end when it was the refutation.
A candidate that cannot be shown to have RUN is not a writer.


## Outcome

- Signal: corrected
- Correction: The ChatGPT desktop app's "Import from another AI app" sync -- NOT a config
generator, and not anything inside this repo or its plugin tree.

Two arms, both decisive:

1. The six keys the rewrite ADDED are a verbatim copy of `.claude/settings.json`'s
   own `env` block -- same keys, same values, same order, including
   `OTEL_LOG_RAW_API_BODIES = "file:.agent/telemetry/"`, which is THIS
   REPOSITORY'S path. No third-party tool can know it. Something read Claude
   Code's settings and wrote them into codex's `shell_environment_policy`, which
   is what an IMPORTER does and what a generator does not.

2. Timestamps agree to the minute: recorded write `2026-09-04T08:29:51Z` =
   03:29:51 AM CDT; ChatGPT > Settings > Import > Import history reads
   "Imported from Claude Code, Sep 4 2026, 3:30 AM, 12 imported", itemised as
   Settings 1, MCP servers 1, Sessions 10. "MCP servers 1" IS the `[mcp_servers]`
   block reported destroyed. It was replaced by an import, not lost to a template.

"Keep imports in sync" is ON, so this RECURS. It is a supported, user-enabled
first-party feature -- there is nothing to uninstall and nothing to trace.

WHY THREE HUNTS MISSED IT, which is the durable part. This is the third
occurrence (#399) and the third wrong attribution; the first two refuted ELEVEN
candidate writers. None of the three asked "what else on this machine READS
Claude Code's configuration". All three searched the repository and the plugin
tree, because that is where a repo-shaped search looks. The writer was a
first-party desktop app with a sync toggle, outside every search any of them ran.

MY OWN ERROR, stated because it is the reusable one: I found the only thing on
the machine that MENTIONED both `shell_environment_policy` and
`OTEL_LOG_RAW_API_BODIES` and reported it as the writer. That is a claim about
CAPABILITY, not about AUTHORSHIP, and no probe I ran separated the two. The tell
was already in my own issue body -- "nothing invokes it that I can find", plus a
plugin that is DISABLED. I filed that as a loose end when it was the refutation.
A candidate that cannot be shown to have RUN is not a writer.
