---
type: "query"
date: "2026-07-27T21:04:55.918259+00:00"
question: "Does mise's min_version give a version ceiling that catches a self-update?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does mise's min_version give a version ceiling that catches a self-update?

## Answer

No — hard and soft are BOTH floors, and mise's schema has no ceiling key at all. hard blocks (rc=1, the task never runs); soft only warns (rc=0). Keep soft > hard or soft is inert. The consequence that matters: a mise self-update moves the installed version UP, so min_version can never fire on the drift it was added alongside — it guards the opposite direction. Catching an upward self-update is [tool.mise] in currency.toml's job, not min_version's. Shipped as min_version = { hard = '2026.7.14', soft = '2026.7.15' } in mise.toml (PR #47, 297de40). Related: mise --version prints '2026.7.15 macos-arm64 (2026-07-27)', so the currency engine's default last-whitespace-field heuristic returns the DATE — hence version_pattern; a non-matching pattern returns '' and is reported NOT CHECKED, never a silent fallback.

## Outcome

- Signal: useful