# Cold review — 08d6825ffbfea01e086c3ec4600d7d2750fb45c0 (#838)

Reviewed by ref: `git show 08d6825ffbfea01e086c3ec4600d7d2750fb45c0` against parent `91a56a82`.
Lane: cold, Claude Opus 5.5 (same family as the author; the codex lane is usage-limited per #838).
No tracked file edited. Host freeze respected: no full suite, no lint/test/kb-gates. Only
targeted runs: `tests/test_real_graph_group.py` (rc 0), two `test_eval_cases.py` tests (rc 0),
a `--collect-only` mark probe over the three real-graph modules (rc 0), and a synthetic
xdist suite in `/tmp/kb838synth` at `-n 2`.

## Verdict

The mechanism is correct and it works: the four tests do carry the mark that pytest sees,
and `loadgroup` does put them on one worker one after another. The narrowed eval test is
equivalent and no longer parses the graph. **But the commit fixes a contributing factor, not
the cause. Nothing on this SHA shows the `test` gate now passes.** One central claim in the
`mise.toml` comment (and the commit body) is **false**, and an arm shows it is false in a way
that matters for this exact bug.

## Findings

### P2-1 — "Ungrouped tests schedule exactly as under `load`" is false; the group now runs FIRST (`mise.toml:468-469`, commit body "ungrouped tests schedule as before")

`LoadGroupScheduling` subclasses `LoadScopeScheduling`
(`.venv/.../xdist/scheduler/loadgroup.py:10`), not `LoadScheduling`. Ungrouped tests do each
become their own scope (`_split_scope` returns the nodeid), but LoadScope then:
- dispatches one scope at a time (`loadscope.py` `_assign_work_unit`) instead of `load`'s
  initial `node_chunksize` batches (`load.py` `schedule`, `items_per_node // 4`, min 2);
- **reorders the queue by scope size, largest first**, because `--loadscope-reorder` defaults
  to `True` (`xdist/plugin.py`, `dest="loadscopereorder", default=True`). The `real_graph`
  group (4 tests) is the only scope larger than 1, so it goes to the **head** of the queue.

Armed with a synthetic suite (xdist 3.8.0, pytest 9.1.1, `-n 2`). The grouped file was named
`test_zg.py` so it sorts LAST:

```
loadgroup:  g_a gw0 | f1 gw1 | g_b gw0 | f3 gw1 | f2 gw0 | f4 gw0
load:       f1 gw0 | f3 gw1 | f2 gw0 | f4 gw1 | g_a gw0 | g_b gw1
```

So under `loadgroup` the group ran first and serially on gw0, while under `load` it ran last
and split across workers. The control arm is the `load` row, and it discriminates.

Why it matters here: the group now starts at t≈0. That is when 12 workers are importing and
collecting, and (under `kb-gates`) `hk check --all` is at full load in the same batch
(`gates.py:277` `CONCURRENT_SAFE = {"lint","test","brain-audit","graph-size"}`; the real batches
are `('lint','test','brain-audit')`, then `eval` alone, re-derived via `gates._batches`).
Under `load`, `test_mcp_serve` (letter m) ran late in collection order, after much of that
peak. This change moves both bounded tests INTO the peak. Whether that helps or hurts on
balance is unmeasured. The comment's description is wrong in either case. Options: pass
`--no-loadscope-reorder`, which still leaves the group early because
`test_affected_covers_tests.py` sorts early, or measure it. Either way, rewrite the sentence.

### P2-2 — The cause is reduced, not removed; the fix is unverified against the failure it targets

- No gate record exists for this SHA: `.agent/kb/gates/` has no `gates-08d6825f…`, and neither
  does the main checkout. The commit's only evidence is the arm of its own wiring test, which
  shows the flag and mark are present. It does not show the timeouts are gone.
- The magnitude does not fit "four parses at once" as the cause. Run alone, the eval canary
  takes 11–31 s by the commit's own figure (inherited, not re-measured here). Failing a 180 s
  bound needs a slowdown of ≥6×. The host has **96 GiB RAM** (`sysctl hw.memsize` =
  103079215104), so 4 × ~4 GB parses (~16 GB) is not memory exhaustion. #838 records host load
  **19→84 on 12 cores** in the failing run, and load was 17.7 / 20.6 / 28.1 at review time with
  nothing of this branch running. That pattern points to host-wide contention: other sessions,
  11 sibling xdist workers, and `lint` in the same gate batch. At most it means 3 sibling graph
  parses.
- Under the old `load` scheduler the four tests sat in three modules far apart in collection
  order (`affected` → `eval_cases` → `mcp_serve`) and were sent in collection-order chunks. So
  "four parses at once" was the worst case, not the measured case.
- What remains after the fix: the bounded tests are still wall-clock bounds (120 s at
  `tests/test_mcp_serve.py:43`; `RETRIEVAL_TIMEOUT = 180` at `python/src/kb_setup/eval_cases.py:410`).
  They still run beside 11 workers and the `lint` gate, on a host whose load comes from outside
  the repo. The gate stays nondeterministic under load. It is just less likely to fail. A real
  fix needs one of three things: (a) run the real-graph tests in their own step after the
  `lint`/`test` batch, e.g. `-m "not real_graph"` in `test` plus a serial follow-up gate;
  (b) bound what the test actually controls (CPU time, or a handshake measured from
  server-ready) instead of wall clock; (c) at minimum, a paired A/B under recorded load before
  claiming #838 fixed. **Do not close #838 or #748 on this commit alone.**

### P3-1 — Comment overstatements (`mise.toml:461-466`)

- "instead of four parses at once on four workers" / "Under the default `load` they landed on
  separate workers" are stated as observed but read as a hypothesis (see P2-2, third bullet). The
  two `affected` tests are adjacent in collection order and would usually share one `load`
  chunk, so one worker.
- "~756 MB" CONFIRMED: `graph.json` is 756,263,781 bytes, a symlink in this worktree to the
  main checkout's graph. "~4 GB RSS and 11-31 s of CPU each" is UNVERIFIED by this lane: inherited
  and not re-measured, because of the host freeze. Label it as such, or link the measurement.
- "The bounds were not raised" CONFIRMED: the diff touches no file under `python/`;
  `LIVE_TIMEOUT_S = 120.0` and `RETRIEVAL_TIMEOUT = 180` are unchanged.
- "loadgroup sends one group to ONE worker" CONFIRMED by the synthetic arm.

### P3-2 — The narrowed test is equivalent, but it now duplicates a sibling (`tests/test_eval_cases.py:365-378` vs `:225-250`)

Equivalence holds. `run_cases` (`evals.py:1229-1283`) loops cases independently. The `slow`
filter, `_cost_skip` (`evals.py:1187-1193`), is the FIRST gate and reads only
`case.slow`/`case.live`. Each iteration appends its own `Result`, and the loop carries no
shared state. The old version asserted only on the retrieval row (no `not report.failed`), so
the other cases could never change its verdict. Measured: the narrowed test and its sibling
both run in <5 ms (`--durations=0`, "6 durations < 0.005s hidden"), so no graph parse happens.
However, `test_the_gated_retrieval_case_still_does_not_bite_on_ship` (`:246`) already runs
`run_cases([case])` on the same single case and asserts SKIP. The two now differ only in
`"--slow" in detail` vs `not report.failed`. Folding them would be cleaner. Optional.

### P3-3 — Completeness: the set of four is complete today, but the wiring test cannot detect a fifth (`tests/test_real_graph_group.py:28-33`)

Static sweep over `tests/` for real-repo `graph.json` / `graph-prose.json` loads, `kb-serve`
spawns, `graphify query/affected` against `_REPO_ROOT`, and `evals.run`/`run_cases` over the
real cases. The real-graph consumers are exactly:
`test_affected_covers_tests.py:92` (subprocess `graphify affected … --graph <real>`, 2 tests via
module `pytestmark` at `:44`), `test_eval_cases.py:388` (`evals.run(_cases())` → the
`tier1.graph-answers` real `graphify query`), and `test_mcp_serve.py:169`
(`mise run kb-serve`). The others all use `tmp_path` graphs or synthetic controls:
`test_eval_cases.py:246` and `:375` are cost-skipped, `:272` monkeypatches the arms,
`_broken_graph_canary` queries a temp "not a graph", `test_memory_serve.py:187` serves only
memory, and `test_merge_prefixes_once.py` uses tmp graphs. A `--collect-only` probe using
pytest's own `iter_markers("xdist_group")` found **4 of 52** items marked in those modules,
exactly the four intended.

The wiring test is not vacuous for those four. `_groups` was armed: a bare function gives `[]`,
a module-level single `MarkDecorator` gives `['real_graph']`, and a module list without the
group gives `[]`. Its result agrees with pytest's `iter_markers`. But `REAL_GRAPH_TESTS` is a
closed, hand-kept list, and the docstring says "Every test that loads the real aggregate
graph". A new real-graph test that lacks the mark passes this gate silently. Either soften the
docstring or derive the list, e.g. by flagging any test module that references `_REPO_ROOT`
together with `graphify-out/graph.json`.

### P3-4 — `@real_graph` nodeid suffix: no in-repo parser breaks, but a copied failing id runs nothing

xdist rewrites `item._nodeid` to `…::test_x@real_graph` under loadgroup
(`xdist/remote.py:241-255`). The only in-repo consumer of a test name in pytest output,
`kb_setup/arms.py:422`, uses a substring check (`arm.test not in out`), so the suffix does not
break it, and `arms.py:300` runs plain pytest without loadgroup anyway. Nothing in
`python/src` parses nodeids (`git grep nodeid` turned up no parser). `-x` is unaffected, since
DSession handles maxfail the same way for every scheduler. Usability trap, armed: pasting the
failure id `test_zg.py::test_a@real_graph` back into `pytest` prints "no tests ran" with
**rc 4**, while the id without the suffix gives `1 passed`. The `--lf` cache keys inherit the
suffix the same way. Worth one line in the `mise.toml` comment.

### P3-5 — The group worker now runs two UNBOUNDED subprocesses ahead of the bounded ones (`tests/test_affected_covers_tests.py:91-99`)

`subprocess.run([... "affected" ...])` has no `timeout`. This was true before the commit, but
the order inside the group follows collection order (`affected` ×2 → eval canary → kb-serve).
So if one of those calls wedges, the one worker that holds both bounded tests is wedged too,
until the task's 25 m bound fires. Consider a `timeout=` there as well.

### Note (Q5 — is the wiring task check sound?)

`test_the_test_task_schedules_by_group` `shlex`-splits `[tasks.test].run`. The forms
`--dist=loadgroup`, `-nauto`, or moving `--dist` into `addopts` would make it false-RED. That
is the safe direction. `-n 0` would pass it falsely, but nobody would write that.
`kb-ship`/`kb-gates` run the task by name (`gates.GATE_TASKS`), so checking the task string
covers the gate path.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base): the reviewed commit, and issue #838 (`gh issue view 838`)
- [pytest-dev/pytest-xdist](https://github.com/pytest-dev/pytest-xdist): read the INSTALLED 3.8.0 source in `.venv` (`scheduler/loadgroup.py`, `loadscope.py`, `load.py`, `remote.py`, `plugin.py`); no network fetch. Already a locked dependency, not a corpus source.
