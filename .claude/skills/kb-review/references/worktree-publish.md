# Worktree and gate preparation

On a new Git worktree, run `mise run kb-worktree-ready` first. That task calls
`kb_setup.worktree.main`: it verifies the pinned `sources/graphify` and
`sources/skillopt` clones, copies the required graph files, and syncs the locked
Python environment. A fresh worktree does not inherit those gitignored inputs.
Do not infer readiness from a clean Git tree or a successful lint run.

Run the plain `mise run check` and `mise run kb-gates` before committing or
shipping, and keep their direct exit codes. The `test` task calls
`kb_setup.test_gate.main`, which refuses with `NOT_RUN` before pytest if the
clones, graph, or locked codegen dependency group are absent. Recover with
`mise run kb-worktree-ready`, then rerun the plain tasks. `UV_NO_SYNC=1`, a
focused test, or a manually installed group is diagnostic only: none proves
that the repository's normal `kb-ship` path will pass. A failing default gate
is a blocker, even when an override is green.
