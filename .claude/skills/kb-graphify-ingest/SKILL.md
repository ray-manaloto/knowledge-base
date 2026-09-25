---
name: kb-graphify-ingest
description: >-
  Ingest prose or document sources through the KB's managed Graphify
  subscription-CLI route. Use for NORMAL per-source extraction requests, for
  DEEP native corpus extraction, or when migrating an old kb-extract Workflow
  call. This skill preserves full prompts, raw captures, receipts, cache
  provenance, sourceFile, capturedAt, kind, note, and graph metadata.
---

# kb-graphify-ingest

Use the mise tasks below. Never invoke raw graphify, a provider SDK, or the
retired `kb-extract` Workflow. These routes use authenticated subscription CLIs
only and refuse provider API credentials.

Inspect the live interface without starting extraction:

```bash
mise run kb-graphify-ingest -- --help
mise run kb-graphify-native-extract -- --help
```

## NORMAL: one or more explicit prose sources

Write a request JSON inside the worktree. Every caller-controlled runtime path
must stay in its assigned family:

- runs: `.agent/kb/graphify-ingest/runs/`
- cache: `.agent/kb/graphify-ingest/cache/`
- scratch chunks: `.agent/kb/graphify-ingest/scratch/`

Example:

```json
{
  "capturedAt": "2026-09-14",
  "scratchDir": ".agent/kb/graphify-ingest/scratch/my-run",
  "cacheRoot": ".agent/kb/graphify-ingest/cache/semantic",
  "backend": "claude-cli",
  "model": "opus",
  "effort": "xhigh",
  "timeoutSeconds": 300,
  "sources": [
    {
      "key": "source_key",
      "path": "/absolute/path/to/complete-source.md",
      "url": "https://example.test/source",
      "kind": "doc",
      "note": "optional reviewed context",
      "sourceFile": "source-name/complete-source.md"
    }
  ]
}
```

Then run:

```bash
mise run kb-graphify-ingest -- /absolute/path/to/request.json
```

`capturedAt` is required and must be a real canonical `YYYY-MM-DD` date.
`key` is one lowercase filesystem-safe component. `sourceFile`, when set, is
a canonical POSIX relative path: no absolute path, backslash, `.`, `..`,
duplicate separator, or trailing separator. Supported kinds are `article`,
`doc`, `designdoc`, `research_json`, `inventory`, and
`article_partial`.

Defaults are `claude-cli / opus / xhigh`. For Codex use
`openai-cli / gpt-5.6-sol / high`. Explicit `model` and `effort` selections
flow through Graphify's public execution-profile validator. A compatible warm
cache may satisfy a source without a provider call; its producer receipt remains
in the returned cache evidence. A miss records raw stdout/stderr and a durable
Graphify receipt before semantic output is accepted.

Successful chunks are written beneath the requested scratch directory. Assemble
them with the existing task:

```bash
mise run kb-assemble -- <name> .agent/kb/graphify-ingest/scratch/my-run/*.json
```

For a cold/warm acceptance case, freeze the request and each source's SHA-256
before running the task. Check that every source key is lowercase and listed in
the frozen request before a paid call. On cold success, copy and hash each
chunk and finalized producer receipt before starting a warm replay. A matching
warm run must produce byte-identical chunks, retain the original producer
receipts, and create no new extraction attempts. A changed request or source
needs a separately frozen attempt; an incomplete or failed pair is not a pass.

## DEEP: one pinned corpus through the native public SDK pipeline

Use the existing native output root and make the backend selection explicit:

```bash
mise run kb-graphify-native-extract -- \
  --target sources/graphify \
  --out .agent/kb/native-extract \
  --backend claude-cli \
  --model opus \
  --effort xhigh
```

For Codex, select `--backend openai-cli --model gpt-5.6-sol --effort high`.
Optional `--token-budget` and `--max-concurrency` tune the managed deep
extractor. Omit model/effort to use the same backend defaults shown above.
`--dry-run` previews the route without a provider call.

DEEP uses Graphify's public detect, AST, semantic extraction, build, cluster,
hub-label, and serialization APIs. The source corpus root selects input bytes;
the knowledge-base root remains the project and run-context identity. Claude
uses the KB cwd. Isolated OpenAI execution uses a temporary neutral child cwd
with `--ignore-user-config` while receipts retain the KB project identity.
