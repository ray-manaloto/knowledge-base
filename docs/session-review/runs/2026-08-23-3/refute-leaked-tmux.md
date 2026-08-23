# Refutation lane: leaked-tmux-server finding (kbprobe-injected-42117 / -26809)

Status: COMPLETE. Verdict: **REFUTED on its core claim** (live leak / class reproducing / test never fixed). One clerical sub-claim survives (the item did vanish from the open lists with no note).
Date: 2026-08-18, probes run ~06:41-06:50 local.

## Verdict in one paragraph

The alive pid 28366 is NOT a leaked pytest tmux server. It is the machine's ONE default-socket tmux server, whose argv is a fossil of the client command that happened to fork it (the pytest spawn at Mon Aug 17 17:08:50). The `kbprobe-injected-26809` SESSION does not exist: `tmux ls` on that server's own socket lists 5 `omc-*`/`omx-*` sessions and no `kbprobe-*` (its 5 live `-zsh` children, started 17:08:51-52, are those sessions' panes — dotfiles/oh-my-claudecode machinery, not pytest). The test's cleanup demonstrably worked. `ps | grep tmux` is structurally incapable of producing this answer: argv shows the forking client's command line forever, not current session state. Additionally, the machine REBOOTED Aug 17 14:42:19 (pid 1 lstart), so the original 42117 server was dead before handoffs f/g/18-a were written — the item vanished from exactly the handoffs written after its referent ceased to exist (e written 14:05, f written 17:27).

## What CONFIRMED (the finding's premises)

- Item verbatim at b:261 (item 6), c:293 (item 7), d:284 (item 7), e:202 (item 8): "A test has leaked a tmux server since 2026-08-11 (`kbprobe-injected-42117`)". Origin: session-2026-08-17.md:227-228 (mtime Aug 16 21:32), which adds "teardown defect" with no session-level evidence.
- f/g/18-a: read in full; zero mentions of tmux/kbprobe/42117 under any spelling. Sweep: `grep -rn -i -e tmux -e 42117 -e 26809 .agent/plans/*.md | grep -v kbprobe` -> only session-2026-08-17.md:227; control `kbprobe` -> the 5 known files. So "vanished with no resolution note" is TRUE as bookkeeping.
- pid 28366 alive: `ps -p 28366` direct (not grep) -> STARTED Mon Aug 17 17:08:50 2026, ELAPSED 13:32:46, argv `tmux new-session -d -A -s kbprobe-injected-26809 -c .../pytest-of-rmanaloto/pytest-5/popen-gw4/test_a_spawned_pane_inherits_t0 -e PATH=/SENTINEL_INJECTED/bin /bin/sh -c printf ...`. Control: `ps -p 1` -> launchd, lstart Mon Aug 17 14:42:19 2026.
- The spawner is real, in THIS repo: tests/test_launch.py:297 `test_a_spawned_pane_inherits_the_callers_path`, line 350 `spawn(f"kbprobe-injected-{tag}", ["-e", "PATH=/SENTINEL_INJECTED/bin"])`, tag = os.getpid() (line 346).

## What REFUTED (the finding's interpretation), with the opposite-answer probes

1. **"a new pytest-spawned server ... is alive right now" — NO.** `lsof -p 28366` -> its socket is `/private/tmp/tmux-501/default` (15 lsof lines total; the unix-socket row quoted). `tmux ls` (same default socket) -> 5 sessions: omc-dotfiles-main-2026040{8,9}*, omc-graphify-chore-*, omx-dotfiles-main-1775104671426-lek7sg — **no kbprobe-* session**. Control arm: the command CAN list sessions (it listed 5). `ps -Ao pid,ppid | awk '$2==28366'` -> five `-zsh` panes started 17:08:51-52, matching the omc sessions' created times exactly; no `/bin/sh -c printf` child. So the pytest-spawned SESSION is gone; the alive process is the shared default SERVER, kept alive by 5 non-pytest sessions. A tmux server's argv freezes as the forking client's command line — the ps line is a fossil, not a leak.
2. **"the leaking test was never fixed" — NOT SUPPORTED.** The test's cleanup runs BEFORE its asserts (tests/test_launch.py:339 `tmux kill-session -t <name>`, check=False) and the pane command exits in milliseconds (printf + redirect), auto-destroying the session under default remain-on-exit. The empirical state confirms it worked this run. test_launch.py last changed 2026-08-10 (`git log --follow`: dfbda98e), i.e. unchanged since before the item was filed — "never fixed" is literally true only because there is no demonstrated defect in it to fix. The current evidence shows the OPPOSITE of a reproduction: a run whose kbprobe sessions are all gone.
3. **"vanished ... and the CLASS is reproducing" — the vanishing tracks the REBOOT, not a cover-up.** Boot 14:42:19 Aug 17 killed any server alive since 08-11. Handoffs listing the item: all written pre-reboot (e at 14:05 is the last). Handoffs omitting it: all written post-reboot (f at 17:27 onward). Undocumented, yes; mysterious, no.
4. The original probe's bound, named: `ps -Ao pid,comm,args | grep tmux` can only read argv. It cannot distinguish "server forked by client X, X's session long dead" from "X's session leaked". It also self-matches (`grep tmux` appeared in my own unfiltered run; snapshot-to-file used instead, 1,166 lines, launchd control 12).

## What remains true and worth one line somewhere

- Clerical: an open item (b#6/c#7/d#7/e#8) was dropped without a closing note. The honest close is: "moot — machine rebooted 2026-08-17 14:42, server gone; and the original 'leaked server' diagnosis misread a tmux server argv fossil for a live session; no kbprobe session exists on the only tmux server (default socket)."
- Whether the ORIGINAL 2026-08-11 42117 case was a genuinely stuck session or the same fossil misread is now unfalsifiable (that machine state died at the reboot). Nothing in the surviving record shows a session-level observation for it either.

## Contradiction with other statements in the evidence set

The handoffs' own "Background state at handoff: no background tasks... left running" lines (f, g, 18-a, and e's "verified by process tree, not pgrep") stand in tension with the finding's "alive right now". Resolution: both sides half-right — the pid IS alive (their probes never looked at OS-level tmux), but it is not leaked pytest state (the finding's probe misread argv). The defect is in the finding's probe, per probes-need-a-control-arm.md's cross-check rule. I was not given the other lanes' findings to check textually.

## Commands behind every claim (exact)

- `ps -Ao pid,lstart,comm,args > $SCRATCH/ps-snap-1.txt` (1,166 lines); `grep -in kbprobe|tmux|launchd` on the file (kbprobe: 1 real hit; tmux: same line + my own wrapper; launchd control: 12).
- `ps -p 28366 -o pid,lstart,etime,stat,comm,args` (rc=0); `ps -p 1 -o pid,lstart,comm` (control).
- `tmux ls` (default socket, rc=0, 5 sessions); `ls -la /private/tmp/tmux-501/` (one socket: `default`, Aug 17 17:08).
- `lsof -p 28366 | grep -i unix` -> `/private/tmp/tmux-501/default`.
- `ps -Ao pid,ppid,stat,lstart,args | awk '$2==28366'` (5 children; awk control: children of pid 1 = 831).
- `git -C kb grep -n -i -e kbprobe -e sentinel_injected -e spawned_pane_inherits` (7 hits, all launch.py/test_launch.py; control kb_setup in mise.toml: 45). Dotfiles same grep: rc=1, control (tmux files): 8 — the test lives HERE, not in dotfiles.
- `git log --follow -- tests/test_launch.py` (newest: dfbda98e 2026-08-10); conftest.py: no tmux/kbprobe (rc=1, file exists 8,915 bytes).
- pytest tmpdir: `pytest-5/popen-gw4/` GONE; base holds pytest-223..230 (Aug 18 02:32-03:04) — old roots pruned, consistent, tells nothing about test completion.
- Graph-first toll: `mise run kb-query -- "tmux server leak pytest" --prose` (TRUNCATED result, rc!=0; used only as the toll + returned nothing on this topic — not treated as evidence of absence).

## GitHub repos touched

_None._ (Local repos only: ray-manaloto/knowledge-base working tree + ray-manaloto/dotfiles working tree, via git grep.)

## COVERAGE

- REACHED AND ANALYSED: all 7 named handoffs in full; session-2026-08-17.md (origin item, lines 210-239); docs/direction/2026-08-18-ray-directives.md in full; tests/test_launch.py lines 260-380 (the spawning test incl. cleanup); git history of tests/test_launch.py and python/src/kb_setup/launch.py; live machine state (full ps snapshot with controls, direct pid probe, children, lsof socket, tmux ls, socket dir, pytest tmpdir base); plans-dir spelling sweep with control; tracked-file greps of both repos with controls.
- OPENED BUT NOT FINISHED: none.
- NEVER REACHED: the .jsonl transcripts (not needed — machine state settled the question, and the rules forbid reading them into context; a transcript grep for the item's first 2026-08-11 observation would be the one way to classify the ORIGINAL 42117 case, which I left unfalsifiable); why dotfiles' omc/omx machinery recreates its sessions (out of scope); the other refutation lanes' findings (not provided).
