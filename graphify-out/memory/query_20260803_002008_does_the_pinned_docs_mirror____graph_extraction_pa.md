---
type: "query"
date: "2026-08-03T00:20:08.779775+00:00"
question: "Does the pinned docs-mirror -> graph extraction path actually work, and what does a claude-code doc file cost to extract?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does the pinned docs-mirror -> graph extraction path actually work, and what does a claude-code doc file cost to extract?

## Answer

YES, proven 2026-08-02 on docs/claude-code/plugins.md read from the pinned clone (HEAD == manifest commit 03853a01). Both arms: discriminator 'plugin-dir' 0 -> 9 in graph-prose.json (control: 'wayfinder' 952, so the grep discriminates); before, the top hits came from mattpocock's ADR (confident, wrong source), after, the top 4 are all [src=plugins.md]. 47 nodes/65 edges. NOTE #84 was already CLOSED while its stated closing condition had never been performed — an issue closed on intent rather than evidence. COST: 161,582 subagent tokens for 3,340 words, 4m15s. Two-point fit vs the 8-file aihero pilot gives cost = 135,346 fixed per file + 7.9 tokens/word, i.e. 84% FIXED — a 4.4x larger file cost only 1.15x more. Remaining 169 files project to ~28.2M tokens / ~72 min at 10 concurrent. The inherited ~24M was roughly right; a linear-in-words correction to ~134M was 5x too high.

## Outcome

- Signal: useful