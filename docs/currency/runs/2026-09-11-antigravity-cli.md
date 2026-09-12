# Currency run — antigravity-cli — 2026-09-11T07:34:51+00:00

**Verdict:** antigravity-cli 1.2.0 → 1.2.1: auto-applying (6/6 gates)

Related: [[tool-currency-log]] · [[antigravity-cli]]

## Step 1 — in sync?

Pinned `1.2.0` · resolved `1.2.0`

| check | status | detail |
|---|---|---|
| version | ok | agy on PATH is the reviewed 1.2.0 (~/.local/share/mise/installs/antigravity-cli/1.2.0/agy) |
| manifest | skip | sources/antigravity-cli.manifest pins 1.2.0; the local clone could not resolve that ref (no clone, no `.git`, no such tag, or git unavailable), so `commit` was NOT checked — run `mise run kb-build` |

## Steps 2-3 — upstream

- Latest (github): `1.2.1`
- GitHub release: `1.2.1`
- Reachable: yes

### Release notes

```text
## 1.2.1

- Added support for `excludeDefaultComponents: true` in custom agent Markdown frontmatter, allowing custom agents to opt out of default prompt sections and built-in tools while preserving post-invocation hooks.
- Improved model API error resilience and diagnostics: transient `genai.APIError` failures (`502`, `503`, `504`, per-minute `429` rate limits, and mid-stream interruptions) automatically retry in-process with exponential backoff while preserving completed tool call outputs, and unrecovered `503` and `429` responses surface clear user-facing error messages.
- Improved MCP and provider tool schema validation to preserve open object schemas (such as `{"type": "object"}` or explicit `additionalProperties: true`) instead of rejecting undeclared arguments on schemas that allow them.
- Improved per-turn responsiveness and reduced memory usage when opening large conversations.
- Fixed `--continue` starting a brand-new conversation when launched from a subdirectory, after a crash, or while another session is open in the same workspace; it now falls back to the most recent non-empty conversation in the current workspace or its parent/child directories.

… (truncated)
```

### Features to consider adopting

_Advisory — these did not block the bump. Skim for a new capability worth a config change._

- Added support for `excludeDefaultComponents: true` in custom agent Markdown frontmatter, allowing custom agents to opt out of default prompt sections and built-in tools while preserving post-invocation hooks.

## Step 4 — tracked issues and watch items

_No watch items configured for this tool._

## Step 5 — decision

Gates passed:

- ✅ versions are readable and move forward
- ✅ latest version has a readable GitHub release
- ✅ no breaking/removal/deprecation marker
- ✅ extras unchanged
- ✅ no tracked issue moved
- ✅ step 1 currently green

_No residual ambiguity — nothing needed a human decision._

## Step 6 — process note

This page is the immutable record of ONE run — a later run writes its own new
page rather than rewriting this one. Annotate it freely with review notes;
nothing here is regenerated.
