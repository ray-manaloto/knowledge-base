# Worktree and gate preparation

On a new Git worktree, run `mise run kb-worktree-ready` first. That task calls
`kb_setup.worktree.main`: it verifies the pinned `sources/graphify` and
`sources/skillopt` clones, copies the required graph files, and syncs the locked
Python environment. A fresh worktree does not inherit those gitignored inputs.
Do not infer readiness from a clean Git tree or a successful lint run.

On a primary checkout or standalone clone, `kb-worktree-ready` intentionally
refuses because there is no donor checkout. Use `mise run kb-build` to fetch
the manifest-pinned source clones and build both graph files. This can be a
costly full build; do not trigger it automatically from a preflight. The test
gate identifies the checkout type and names the corresponding setup command.

Run the plain `mise run check` and `mise run kb-gates` before committing or
shipping, and keep their direct exit codes. The `test` task calls
`kb_setup.test_gate.main`, which refuses with `NOT_RUN` before pytest if the
clones, graph, or locked codegen dependency group are absent. Recover with
the setup command it names, then rerun the plain tasks. `UV_NO_SYNC=1`, a
focused test, or a manually installed group is diagnostic only: none proves
that the repository's normal `kb-ship` path will pass. A failing default gate
is a blocker, even when an override is green.
