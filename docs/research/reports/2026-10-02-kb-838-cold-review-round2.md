# Cold review, round 2 — #838 CPU-bounded canary

Reviewed commit: `3ef3ad5391b507951eb1d83b11d79681d7f8e47e`, delta `165fc87207c20d7c2d4500efab7a32318bbe8aa5..3ef3ad5391b507951eb1d83b11d79681d7f8e47e`.
Reviewer: Claude Opus 5.5 (same family as the author; noted, not hidden).

## Progress log (incremental)

- Read diff (evals.py +140, eval_cases.py +18, tests/test_cpu_bounded.py +170, 2 reports).
- `eval` task: mise `timeout = 25m`, invoked by gates via `mise run eval` — so the outer wall cap is 25 min.
- PROBE: macOS `ps -A -o pgid=,time=` reports an unreaped zombie leader as `0:00.00` (it had used 0.5 CPU-s) -> `group_cpu_seconds` returns 0.0, not None.
- PROBE: `os.killpg` on a group whose only member is a zombie raises **PermissionError (EPERM)** on macOS; after reaping it raises ProcessLookupError. `_kill_group` suppresses only ProcessLookupError.
- REPRO: slow `ps` (0.5 s, monkeypatched delay) + a command that exits just after a window boundary -> 3/5 runs `run_command_cpu_bounded` RAISED PermissionError for a command that succeeded with rc 0 'done'. `run_cases` turns that into FAIL "probe raised PermissionError".
- REPRO: parent exits while a `start_new_session` grandchild holds stdout -> the unreaped parent is a zombie, sampled as 0.0 -> "stalled" -> killpg EPERM -> RAISED (macOS). On Linux killpg would succeed and `_kill_group`'s bare `proc.communicate()` would block until the escaped grandchild closes the pipe.
- MEASURED: runaway, budget 3 / window 1 -> killed at 4.24 s wall, 3.9 CPU-s. Scaled to 180/60 that is ~240 s.
- MEASURED: `_Throttle` delivered duty: nominal 0.25 -> 0.305, nominal 0.06 -> 0.137 (pgrep runs while the target is CONTinued).
- MEASURED: output survives `communicate(timeout=)` retries (200 KB stdout + stderr + tail, window 0.4 s, 1.5 CPU-s): rc 0, all present.
- RAN: `uv run pytest tests/test_cpu_bounded.py -q` rc 0 (8 passed); `uv run pytest tests/test_evals.py -q` rc 0.

## Findings

### P1-1 — An exit between the window timeout and the `ps` sample turns a SUCCESSFUL command into an exception (macOS) or a false "stalled" (`python/src/kb_setup/evals.py:283-302, 360-387`)

Chain, every link run:
1. `communicate(timeout=stall_window)` raises at T; the command exits at T+δ, before `ps` runs. Nothing reaps it, so it is a **zombie**.
2. macOS `ps -A -o pgid=,time=` lists a zombie with `time = 0:00.00` (probed: a child that burned 0.5 CPU-s showed `6666 0:00.00 ZN`). `group_cpu_seconds` therefore returns **0.0**, not None — contradicting its own docstring at `:286` ("None means no live process in that group was seen"). The `used is None -> poll() -> continue` guard at `:362-364` never fires for this case.
3. `0.0 - last < min_progress` -> verdict "stalled" (`:368`).
4. `_kill_group` -> `os.killpg` on a zombie-only group raises **PermissionError (EPERM)** on macOS (probed; only ProcessLookupError is suppressed, `:385-386`). The function RAISES instead of returning its documented rc tuple. `run_cases` (`evals.py:1416-1419`) converts that into FAIL "probe raised PermissionError".

Reproduced 3/5 with a 0.5 s delay injected before the real `group_cpu_seconds` (standing in for `ps` under load) and a command that spins just past one window: each of the 3 RAISED for a command whose real result was `(0, 'done')`. Probability per run is roughly ps-latency / stall_window on the final window — small on an idle host, and largest under exactly the load #838 is about (the canary only crosses a window boundary when the host is slow). Every ship gate then fails on a healthy query, which is the failure #838 set out to remove.

Fix shape: before acting on ANY verdict, `if proc.poll() is not None: continue` (let `communicate` reap and return the real rc/output); and suppress `PermissionError` in `_kill_group` (or filter zombies via `stat=` in the `ps` call). No test covers the exit-between-samples path; arm it with a delayed-`ps` fixture like the one above.

### P2-1 — A pipe held by a descendant that left the group: crash on macOS, unbounded block on Linux (`evals.py:383-387`)

If the command's leader exits while a descendant that called `setsid`/`start_new_session` holds stdout, the zombie leader samples as 0.0 -> "stalled" -> killpg EPERM (reproduced). On Linux (killpg on a zombie group succeeds) `_kill_group`'s bare `proc.communicate()` then waits, with no timeout, for the escaped descendant to close the pipe — an unbounded wait inside the function whose docstring says it refuses to "wait blind". graphify query does not do this today, so P2 not P1; the docstring claim at `:331-334` that "a group sample covers any the command forks" is true only for descendants that stay in the group. Bound the final `communicate` (timeout, then close the pipes) and say so.

### P2-2 — "on an idle host it is no looser" is false: the CPU bound kills a runaway at ~240 s, not 180 s (`python/src/kb_setup/eval_cases.py:412-418`)

`used > cpu_budget` is sampled once per 60 s window. A single-threaded runaway on an idle host has used ≤180 CPU-s at the 180 s sample (CPU ≤ wall), so it passes that sample and dies at the 240 s one. Measured at scale: budget 3, window 1 -> killed at 4.24 s wall / 3.9 CPU-s. Because 180 is an exact multiple of 60, this is the MAXIMUM overshoot — 33 % looser than the wall bound it replaced. `evals.py`'s own docstring admits "overshoot by up to one window's worth of CPU", so the two comments contradict each other. Either reword the eval_cases comment, or make the bound tight (e.g. also set `RLIMIT_CPU` on the leader via `preexec_fn`/`process_group`+`resource` — kernel-enforced, zero overshoot for the single-process query — and keep the group poll for descendants and stalls).

### P3-1 — Evidence report's "duty" column is nominal, not delivered (`docs/research/reports/2026-10-02-kb-838-evidence.md:60-64`)

`_Throttle` runs `pgrep` while the targets are CONTinued, so every period grants them extra run time. Measured: nominal 0.25 -> 0.305 delivered, nominal 0.06 -> **0.137** delivered. The report's own number agrees: 31.7 CPU-s / 222.7 s = 0.142, not 0.06 (0.06 would need ~528 s). The conclusion survives (old wall bound fails at ~14 %, new bound passes) but the row should say "nominal 0.06 (~0.14 delivered)". Same inaccuracy in `tests/test_cpu_bounded.py:133` ("~6 s of wall" — measured ~4.9 s for 1.5 CPU-s).

### P3-2 — The throttle control arm's margin shrinks as `pgrep` slows (`tests/test_cpu_bounded.py:49-68, 141`)

Delivered duty rises with `pgrep` latency (runtime per cycle = 0.125 s + pgrep time). Under heavy host load the control (`wall bound must FAIL at 3 s`) needs delivered duty < 0.5; at 0.305 today the margin is ~1.6x. Host starvation of the spinner partly compensates, so this is a flake risk, not a vacuity — the control arm correctly fails loudly if the throttle matches nothing (an unthrottled 1.5 CPU-s spin finishes well under 3 s). Sampling pids, then SIGSTOP immediately, then sleeping the FULL off-time would remove the drift.

### P3-3 — One `ps` hiccup kills a healthy canary with rc -3 (`evals.py:362-365`)

A single `ps` timeout (10 s) or OSError while the command runs fails closed immediately. Fail-closed is right; a single retry before `-3` would make it robust under the load this change targets. Untested (no test reaches `-3`).

### P3-4 — `RLIMIT_CPU` justification is slightly mis-stated (`evals.py:331-336`)

`RLIMIT_CPU` is inherited, so each descendant IS bounded individually; what it cannot do is bound the AGGREGATE. "blind to descendants" overstates. The choice of `ps` polling is still defensible (no psutil in `uv.lock`; stall detection needs polling anyway), but the strongest design is both: `RLIMIT_CPU` for an exact, zero-overshoot per-process cap plus the group poll for aggregate/stall (see P2-2).

### Checked and found sound

- `communicate(timeout=)` retry: no output lost (measured, 200 KB + stderr + tail across ~4 retries).
- pgid == pid under `start_new_session=True` (setsid makes the child its own group leader).
- `ps` time parse covers macOS `m:ss.cc` / `mmm:ss.cc` / `h:mm:ss.cc` and procps `[dd-]hh:mm:ss`; `-A -o pgid=,time=` valid on both. Linux's whole-second resolution is harmless at the production 1 CPU-s/60 s floor (floor(b)-floor(a) ≥ floor(b-a)) but would make the sub-second unit-test thresholds flaky on Linux (none run there today).
- `last = 0.0` start is correct; first-window false stall needs <1 CPU-s in 60 s — a 12-core host at load 206 still gives ~3.5 CPU-s/min. A heavily paging host is the residual risk (major-fault wait is not CPU), unmeasured.
- "single-threaded never accrues more CPU than wall": true; if graphify used threads, CPU > wall makes the budget STRICTER, never looser. graphify's query path threading not measured (no 31 CPU-s run, per the shared-host instruction).
- Wall ceiling: 180 windows × 60 s = 3 h by the progress rule, but the `eval` task carries `timeout = 25m` and gates call it through `mise run eval` (`gates.py:476-478`).
- Descendant test cleanup: grandchild shares the group and dies with killpg; no orphan observed (`pgrep` clean afterwards). Throttle `pgrep -f <uuid>` cannot match pytest or pgrep itself.
- Case-wiring test discriminates (monkeypatched wall path `pytest.fail`s).
- Promoted cold-review report: 2×P2 / 5×P3 count in the README row matches the file.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the reviewed delta, `evals.py`, `eval_cases.py`, `gates.py`, tests, `mise.toml`
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — installed package source in `.venv`, grepped for thread/process pools in the query path
