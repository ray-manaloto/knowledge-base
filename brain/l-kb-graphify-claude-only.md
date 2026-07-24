---
kind: lesson
source: feedback_kb_graphify_claude_only
---

# l-kb-graphify-claude-only

As of 2026-07-22, KB graphify prose work belongs only to Claude Code host-agent workflows.
Strip every non-Claude backend trigger, since blocking Gemini alone can fall through to Bedrock via AWS_REGION.
All graphify mutations must use the repository's mise tasks, while direct use is limited to documented read-only commands.
Because claude-cli labeling issue #2076 returns unparsable prose, use the deterministic hub labeler by default.
Apply [[delegation-discipline]] and [[routing-doctrine]] together so backend and task routing stay machine-enforced.
