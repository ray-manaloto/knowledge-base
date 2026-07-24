---
kind: lesson
source: feedback_codex_worktree
---

# l-codex-reads-cwd-not-worktree

Codex read-only file access resolves from its current working directory, not an intended worktree.
In devcontainer Debates 1 and 2, it read old main-branch vscode code and produced invalid findings.
Send work to [[lane-codex]] only after changing into the worktree, or embed every relevant file in the prompt.
Under [[delegation-discipline]], verify the files referenced in its answer before accepting the analysis.
