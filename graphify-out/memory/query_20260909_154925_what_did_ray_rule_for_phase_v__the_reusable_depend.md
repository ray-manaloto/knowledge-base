---
type: "query"
date: "2026-09-09T15:49:25.344589+00:00"
question: "What did Ray rule for Phase V, the reusable dependency-upgrade workflow (#726), on 2026-09-09?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did Ray rule for Phase V, the reusable dependency-upgrade workflow (#726), on 2026-09-09?

## Answer

Phase V (#726, children #727–#733, #735) is the reusable dependency-upgrade workflow, settled 2026-09-09 over four /grilling rounds (16 answers) and confirmed on docs/artifacts/upgrade-workflow-grill.html. Rulings not derivable from code: all graphify-fork work happens in the existing checkout ~/dev/github/ray-manaloto/graphify (never sources/graphify/); Claude rebases inline and the unpushed Phase G commit 6ca68bd is parked on its own branch; the workflow's phase 0 searches the project, branches/worktrees, issues and plans (.planning/, .agent/plans/, ~/.claude/plans/) before any design — Ray: "ensure we never forget this"; the August DBOS/SQLite design (#638) is INPUT not constraint — re-decided, DBOS kept as direction but re-researched for best practices and audited for inefficiencies/bugs/vagueness, with currency.toml folding into that system; pins move by the owning tool with the engine's text edit only as an uninstallable-version fallback; two layers (Python engine token-free, Claude workflow for judgment); Claude builds, codex reviews cold; eight new agents whose knobs are finalised only after sources/claude-code + claude-code-docs are resynced; commit per dependency, one PR per run, one kb-build per run. The chain head is #735 then #727; U-R3 resumes after V6. Verbatim brief: docs/direction/2026-09-09-ray-directives.md.


## Outcome

- Signal: useful