---
type: "query"
date: "2026-07-22T19:04:40.113980+00:00"
question: "What patterns keep a long-running agent working autonomously for hours without stalling (for the orchestrator/Workflow design)?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["blog_longrun_test_oracle", "blog_longrun_changelog_memory", "blog_migration_doc", "blog_dynwf_intro_doc", "blog_loops_doc"]
---

# Q: What patterns keep a long-running agent working autonomously for hours without stalling (for the orchestrator/Workflow design)?

## Answer

Test oracle (reference impl/quantifiable target/test suite) for progress without a human; well-scoped tasks with clear success criteria; CLAUDE.md plan + progress/CHANGELOG.md as cross-session memory recording FAILED approaches; commit+push after every unit (git durability); tmux/SLURM detached execution; reduce permission interruptions (pre-approve safe tools, non-interactive) so it never stalls; 'the queue writes itself' — failures auto-become the next work item (self-feeding verification loop); dynamic workflows fan tens-to-hundreds of subagents over hours-days and verify before returning; token multiplication is the core cost constraint on parallelization.

## Outcome

- Signal: useful

## Source Nodes

- blog_longrun_test_oracle
- blog_longrun_changelog_memory
- blog_migration_doc
- blog_dynwf_intro_doc
- blog_loops_doc