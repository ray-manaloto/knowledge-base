# Cold review of 1183afaaa88eb878401d4dca69341569636a9190 (fix/kb-748-serve-cpu-bound)

Range: `683463b5..1183afaaa88eb878401d4dca69341569636a9190` (4cdd0f61, 1183afaa). Reviewer: cold lane, Claude Opus 5.5.
Read by ref, no tracked file edited. Scratch probes are under /tmp/kb748rev/.

## What I ran (all serial)

- `uv run pytest tests/test_mcp_serve.py -q -k "not actually_answers"`: 18 passed, rc 0 (load 10-14). Durations: starved 8.49 s, runaway 2.09 s, clean-exit 1.55 s, wedged 1.05 s.
- `uv run pytest tests/test_cpu_bounded.py tests/test_evals.py -q`: all passed.
- Arms run through a pytest plugin that monkeypatches at configure time (/tmp/kb748rev/arm.py, trace.py, cadence.py), plus an orphan fake (/tmp/kb748rev/orphan.py).
- Process-group probe: a throwaway `raw = true` mise task running `uv run python` (/tmp/kb748rev/miseproj).

## Findings

### P1: the CPU bound has no backstop once the leader exits while a descendant still holds stdout. Wait is unbounded. `python/src/kb_setup/mcp_probe.py:156-163,177-187,262`
With `bound=` set, `deadline = inf` (`mcp_probe.py:262`). After `proc` exits, `CpuWatch.verdict()` returns None every time (`evals.py:387-389`), so `_sample` never fires. The only remaining exit from `await_id` is the EOF sentinel, and it never comes while any descendant holds the stdout pipe. Neither the stall rule nor the CPU budget is enforced in that state, so a wedged or spinning orphan is waited on forever.
`run_command_cpu_bounded` covers exactly this case with `_collect_after_exit` (capped at `stall_window`, `evals.py:392-407`). The probe has no equivalent. So the `CpuWatch` docstring claim, "the runaway/wedge rules and the zombie guard exist once" (`evals.py:363-367`), is true of the zombie guard but not of the descendant-holds-the-pipe bound.

**Measured** with /tmp/kb748rev/orphan.py. The leader reads `initialize`, spawns a sleeping child that inherits stdout, and exits 0:
- `timeout=3`: returns in 3.0 s, "timed out waiting for reply id=1".
- `bound=CpuBound(30, stall_window=1, min_progress=0.2)`: returns in **20.1 s**, exactly the child's sleep. The detail is "exited rc=0 before answering", and no stall verdict ever fired. With an infinite sleep it would never return. The only outer bound is `[tasks.test]`'s 25 m timeout.

The scenario is real in this stack. `mcp_serve._run_inheriting`'s docstring (`mcp_serve.py:285-289`) records an orphaned graphify-mcp "still bound to the client's file descriptors" after its waiting parent died. Here the leader is `mise`, and its death is not forwarded the way kb-setup's is.
Fix shape: when `self._watch` is set and `proc.returncode is not None` with no EOF, allow at most `stall_window` more for the sentinel, then fail with the `_collect_after_exit` wording. `_shutdown`'s killpg then reaps the descendant, which stayed in the group.

### P2: `test_a_clean_exit_is_not_misread_as_a_stall` passes only because of an incidental 1 s sampling granularity. Its fixture is a genuine stall under its own bound. `tests/test_mcp_serve.py:271-286`
The fake sleeps 1.2 s after `initialize`. Python startup costs ~0.02 CPU-s (measured with `ps -o time`: 0:00.02 at 0.3/0.6/0.9 s), which is below `min_progress=0.05`. So while it is alive it makes no progress for longer than `stall_window=0.5`, and an honest verdict while alive is "stalled".
The test passes only because the first sample happens at ~1.0 s, not at `tick`=0.5 s (see P3-a). The slow `ps` then ends at ~1.5 s, after the child has exited at ~1.2 s plus startup. Traced: a single `verdict()` call at t=1.00 s, with `returncode=0` already set when judged.
**Armed:**
- Shorten the queue `get` to 0.1 s so the 0.5 s tick is honoured (/tmp/kb748rev/cadence.py). The test FAILS: "stalled: 0.02 CPU-s in the last 1s", 2/2 runs.
- Removing the zombie guard also fails it ("0.00 CPU-s ... 0.0 total", arm.py `unguarded`). So the guard IS reached at idle and the test is not vacuous.
- But the test is timing-fragile. If the child's startup is delayed by more than ~0.3 s (routine at the loads #748 is about), it is still alive at the 1.5 s judgement and the test fails with a correct "stalled".

Fix: give the fake a CPU-progressing wait (spin to `process_time() >= 0.3` before exiting), or set `min_progress` well below startup cost. Then "alive" can never be a stall, and only the post-exit sample is under test.

### P2: the starved-server test's CPU arm can flake "stalled" at high host load, which is the condition #748 is about. `tests/test_mcp_serve.py:289-300`
`CpuBound(30, stall_window=1, min_progress=0.05)` under `_Throttle(duty=0.25, period=0.5)` needs ≥0.05 CPU-s per ~1-2 s window. Measured this run, it took ~5.5 s for 1.5 CPU-s + startup, so the delivered share is ~0.28 at load ~11. That share scales with `cores/load` once the run queue saturates. On 12 cores at load ≳70-130 it drops under ~0.05 CPU-s/s and the arm reports "stalled". #838 recorded load 206.
This test is not in the `real_graph` xdist group, so it runs concurrently with the full suite. The wall-bound control has the opposite exposure: it needs the delivered share to stay ≲0.45 for 1.5 CPU-s to miss 3 s, which is safe today.
Suggest `stall_window=5`, or a lower `min_progress`. That keeps the wedge discriminable (a wedge is 0.0) and removes the load sensitivity.

### P3-a: sampling cadence is quantised by the 1 s queue `get`, not by `tick`. `mcp_probe.py:161-165`
`_sample()` is only re-evaluated after `self._lines.get(timeout=min(remaining, 1.0))` returns. With `deadline=inf` that is 1.0 s, so the effective interval is `max(tick, ~1 s)`. That is harmless for the live arm (tick 10 s) but it differs from what the tests' `stall_window=0.5/1` imply, and P2 above depends on it. Use `min(remaining, 1.0, self._next_sample - now)` to make the cadence explicit.

### P3-b: a due verdict is checked before already-queued lines are drained. `mcp_probe.py:161-162`
A reply that is already in the queue loses to a verdict that becomes due on the same iteration. The realistic case: a server that answers at ~budget CPU-s, where the next sample sees it just over budget. The window is narrow and only reachable near the budget, but the order inverts "answered" into "exceeded".

### P3-c: the runaway test can report "stalled" instead of "exceeded CPU budget" under extreme load. `tests/test_mcp_serve.py:262-268`
`min_progress=0.1` per 1 s. An unthrottled spinner gets below 0.1 CPU-s/s once load passes ~10x the core count. That is rare, but it is the #838 high-water mark.

### P3-d: stale or loose prose
- `mise.toml:466-467` still describes "kb-serve's 120 s, the eval canary's 180 s" as live wall-clock bounds. Both are now CPU bounds. Either mark it historical or update it.
- `tests/test_mcp_serve.py:47-48` says "spent ~28.4 CPU-s **to its first reply**". The evidence table (`2026-10-02-kb-748-evidence.md:17`) attributes ~28.4 to the whole arm (init + 10 tools). One of the two is mis-scoped. Unverifiable here because it needs the graph.
- `evals.py:363-367` ("exist once"): see P1.
- `tests/test_mcp_serve.py:39` (`from test_cpu_bounded import _Throttle`) is a cross-test-module import of a private helper. It works under pytest's default prepend import mode, because `tests/` has `conftest.py` and no `__init__.py`. It would break under `--import-mode=importlib` or if a `tests/__init__.py` were added. Move `_Throttle` into `conftest.py` or a `tests/_helpers.py`.
- The 6x ratio claim: 180/28.4 = 6.3x for this arm, against the canary's 180/31.7 = 5.7x. "The same ratio" is loose but fine.

## Questions answered (no defect)

1. **Refactor equivalence (#838 path): unchanged.** The old order was `communicate(tick)` → sample → `poll()` → collect-if-exited → `_judge`. The new order is `communicate(watch.tick)` → `verdict()` (sample, then `poll()`, then `_judge` only if alive) → `returncode is not None` → collect. `_Progress` is still created right after `Popen`, and `tick` is the same expression. `test_cpu_bounded.py` and `test_evals.py` are all green, and they still call `run_command_cpu_bounded` directly, so the same path is exercised.
2. **One watch spanning three awaits: fine.** The stall clock and budget are cumulative over the group, which is what the bound means. An idle-but-healthy server is never judged while we are waiting on IT: `_handshake` sends `tools/list`/`resources/list` immediately after each reply, so no await covers a period where the server is idle by design. One new exposure versus the old 120 s wall: lock waits are now judged as a wedge after 60 s of no CPU. That covers mise's install lock and uv's venv lock contended by sibling xdist workers. Previously up to ~90 s of such waiting was tolerated. Arguably correct, but worth knowing.
3. **EOF/`_exit_detail` interplay: correct when EOF arrives** (verdict None after exit, then the sentinel, then the rc). Not correct when it does not arrive: see P1.
4. **A stalled verdict does not leave the server running.** `_handshake` returns, then `finally: _shutdown(proc)` → killpg SIGTERM, then SIGKILL. After the wedged, runaway and starved tests, `pgrep -fl "wedged.py|runaway.py"` returned rc 1. Control arm: a live process carrying `wedged.py` in argv was found, rc 0, so the probe discriminates.
5. **Process group: one group.** A `raw = true` mise task running `uv run python` was started with `start_new_session=True`. mise (pid 1112, pgid 1112) → uv (pgid 1112) → python (pgid 1112, sid 1112). Neither mise nor uv re-groups. `kb-setup serve`'s `_run_inheriting` uses a plain `Popen` with no `start_new_session`, `setsid` or `process_group` (grep of `mcp_serve.py`), so graphify-mcp inherits the group. Group CPU therefore counts graphify-mcp, consistent with the evidence doc's ~28 CPU-s. Caveat: I did not run the real kb-serve, per the brief.
6. **Fake-script escaping is correct.** `"\\n"` inside the non-raw triple-quoted string becomes the two-character `\n` inside the child's string literal, a newline. The slow worker answers all three requests (the starved CPU arm passed).
7. **The wiring test discriminates.** `seen.get("bound") == CpuBound(180)` and `"timeout" not in seen`. Reverting `_live_probe` to `timeout=120` fails both assertions. This is trivially true from the code; I did not re-run that mutation.
8. **`test_memory_serve` is out of scope, defensibly.** It probes `uv run kb-setup serve-memory` over the small work-memory store, with no `graph.json` load, so its 120 s wall bound has ~2 orders of magnitude of headroom over a sub-second server. It is the same residual class (wall bound under host load), but nothing has fired. A follow-on issue is reasonable. Changing it in this PR is not required.
9. **Evidence doc (`docs/research/reports/2026-10-02-kb-748-evidence.md`).** The test list matches the four new fake-server tests, and "under 1 CPU-s per 60 s" matches the defaults (`evals.py:265-271`). The measured table and the inherited failure loads need the graph, so I did not re-verify them. The doc labels the failure section as inherited, correctly. "A busy host does not [fail it]" is too strong given P2 on the starved test's own parameters, and given that the live arm's 1 CPU-s/60 s floor only trips at loads in the hundreds.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base): the reviewed branch (`mcp_probe.py`, `evals.py`, `mcp_serve.py`, `tests/test_mcp_serve.py`, `tests/test_cpu_bounded.py`, `tests/test_memory_serve.py`, `mise.toml`, the #748 evidence doc)
