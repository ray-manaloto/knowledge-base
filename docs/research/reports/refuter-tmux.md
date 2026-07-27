# Refutation probe: does `tmux new-session -e PATH=X` reach the pane?

**Claim under test** — "tmux gives the pane the PATH of the tmux CLIENT.
`tmux new-session -e PATH=X <cmd>` does NOT give the pane PATH=X; the value is
stored in the session environment but is not what the pane process gets. Not
caused by the login shell sourcing a profile."

Machine: macOS, tmux 3.7b at
`/Users/rmanaloto/.local/share/mise/installs/tmux/latest/tmux`.

Status: COMPLETE. **VERDICT: SURVIVES** (the removal is NOT a regression).

## Probe design

Distinct sentinels so client / injected / server / global / default-command are
never confused:

| sentinel | means |
|---|---|
| `/S_CLIENT` | PATH of the process that invoked the tmux client |
| `/S_INJECT` | value passed to `new-session -e PATH=` |
| `/S_SERVER` | PATH the tmux **server** was started with (own socket) |
| `/S_GLOBAL` | value set with `set-environment -g PATH` |
| `/S_DEFCMD` | via `default-command` |

Pane command is `/bin/sh -c 'printf "%s" "$PATH" > out'` — absolute interpreter,
`printf` is a shell builtin, so a nonsense PATH still works and no profile is
sourced.

Isolation: probes run on a private socket (`-L refutesock`) so the live Claude
Code server is untouched; a confirming arm is then re-run on the default server
with `refute-`-prefixed session names, killed by name only.

(results below)

## ARM B — the decisive three-way (private socket `-L refutesock`)

Server born from a client with `PATH=/S_SERVER:…`; a *second* client with
`PATH=/S_CLIENT:…` then creates the session with `-e PATH=/S_INJECT:…`.

```
env PATH="/S_SERVER:$REAL" tmux -L refutesock new-session -d -s refute-holder /bin/sh -c 'sleep 300'
tmux -L refutesock show-environment -g PATH
  -> PATH=/S_SERVER:/usr/bin:/bin:/usr/sbin:/sbin        # server global environ

env PATH="/S_CLIENT:$REAL" tmux -L refutesock new-session -d -s refute-b \
    -e "PATH=/S_INJECT:$REAL" -e "SENTINEL_CTL=hello_from_e" \
    /bin/sh -c 'printf "PANE_PATH=%s\nPANE_CTL=%s\n" "$PATH" "$SENTINEL_CTL" > b.txt'
```

`b.txt`:

```
PANE_PATH=/S_CLIENT:/usr/bin:/bin:/usr/sbin:/sbin
PANE_CTL=hello_from_e
```

Three sentinels, one winner: **the CLIENT's**. Not the injected value, not the
server's global environ.

**CONTROL ARM (positive):** `-e SENTINEL_CTL=hello_from_e` on the *same command*
arrived intact in the *same pane*. So `-e` is not broken, the syntax is not
wrong, and the pane-reporting probe can see `-e` values when they are delivered.
The probe discriminates.

Arm A (no pre-existing server, `-e PATH` + `-e SENTINEL_CTL`) gave the same
result: `PANE_PATH=/S_CLIENT…`, `PANE_CTL=hello_from_e`.

## Variation matrix — every alternative loses to the client's PATH

All on the private socket, server global environ = `/S_SERVER:…`, client PATH =
`/S_CLIENT:…`, injected = `/S_INJECT:…`.

| arm | variation | pane PATH | `-e` non-PATH var reached pane? |
|---|---|---|---|
| A | no pre-existing server, `-d`, argv cmd | `/S_CLIENT…` | **yes** (`hello_from_e`) |
| B | pre-existing server (`/S_SERVER`), `-d`, argv cmd | `/S_CLIENT…` | **yes** |
| C | as B + an arbitrary client var `FOO_CLIENT` | `/S_CLIENT…` | yes; `FOO_CLIENT` **empty** |
| D | `set-environment -g PATH=/S_GLOBAL` first, no `-e` | `/S_CLIENT…` | n/a |
| E | command given as ONE STRING, not argv | `/S_CLIENT…` | n/a |
| F | `set -g default-command <wrapper>`, no explicit cmd | `/S_CLIENT…` | n/a |
| G5 | pane process is `python3 -c` (**not a shell**) | `/S_CLIENT…` | **yes** |
| G6 | negative control: **no `-e` at all**, client=`/S_NOINJECT` | `/S_NOINJECT…` | n/a |
| H | `zsh -lic` (login+interactive, profile really runs) | contains `/S_CLIENT`, **no `/S_INJECT`** | n/a |

### Arm C is the sharpest one

```
env PATH=/S_CLIENT:… FOO_CLIENT=from_client_env tmux -L refutesock new-session -d -s refute-c \
    -e "PATH=/S_INJECT:…" -e "SENTINEL_CTL=hello_from_e" /bin/sh -c '…'
->  PATH=[/S_CLIENT:/usr/bin:/bin:/usr/sbin:/sbin]
    CTL=[hello_from_e]
    FOO_CLIENT=[]                      <-- arbitrary client vars do NOT leak in

tmux -L refutesock show-environment -t refute-c PATH
->  PATH=/S_INJECT:/usr/bin:/bin:/usr/sbin:/sbin     <-- stored, but not what the pane got
tmux -L refutesock show-environment -t refute-c SENTINEL_CTL
->  SENTINEL_CTL=hello_from_e
```

So this is not "tmux passes the client's whole environment". `FOO_CLIENT` did
not survive; **PATH specifically** is taken from the client and overwrites the
session-environment value. And `show-environment` proves the injected value IS
stored — exactly the claim's "stored in the session environment but is not what
the pane's process gets".

### The "not the login shell" half — three independent arms

* `/bin/sh -c` (non-interactive, non-login; `$ENV` confirmed **unset** in the
  probing shell so bash-as-sh sources nothing) — client PATH.
* `python3 -c` (**arm G5**) — the pane process is not a shell at all, so no
  profile can exist. Still client PATH, and `-e SENTINEL_CTL` still arrived:

  ```
  PATH=/S_CLIENT:/usr/bin:/bin:/usr/sbin:/sbin
  CTL=hello_from_e
  ```

* `zsh -lic` (**arm H**) — a real login+interactive shell that really does run
  the profile. `HAS_INJECT=no`, `HAS_CLIENT=yes`. The profile *prepends* entries
  but the injected value is absent from the final PATH entirely, i.e. the
  profile is not the thing that removed it — it was never there.

**Negative control (G6):** with no `-e` at all, the pane's PATH is byte-for-byte
the client's (`/S_NOINJECT:…`). So the pane always tracks the client, and adding
`-e PATH=` changes nothing about that.

## ARM J — attached (no `-d`), real pty via `script(1)`

```
env PATH="/S_CLIENT_ATT:$REAL" /usr/bin/script -q /dev/null \
  tmux -L refutesock new-session -s refute-j -e "PATH=/S_INJECT:$REAL" \
       -e "SENTINEL_CTL=hello_from_e" /usr/bin/python3 -c '…'
->  PATH=/S_CLIENT_ATT:/usr/bin:/bin:/usr/sbin:/sbin
    CTL=hello_from_e
```

A *third distinct* client sentinel, and the pane tracked it. Detached vs attached
makes no difference.

## ARM K — the REAL default server (where the live Claude Code session runs)

```
tmux show-environment -g PATH
->  PATH=/opt/homebrew/opt/llvm/bin:…/editorconfig-checker/3.8.0/bin:…   # server's, hours old

env PATH="/S_CLIENT_REAL:$REAL" tmux new-session -d -s refute-real \
    -e "PATH=/S_INJECT_REAL:$REAL" -e "SENTINEL_CTL=hello_from_e" /usr/bin/python3 -c '…'
->  PATH=/S_CLIENT_REAL:/usr/bin:/bin:/usr/sbin:/sbin
    CTL=hello_from_e
```

The server's global PATH here contains `editorconfig-checker`, which the probing
client's PATH does not — a natural discriminator confirming server ≠ client. The
pane got neither the server's nor the injected one. Session killed by name;
`kb` and `knowledge-base` untouched.

## ARMS L / M — the control arm that proves `-e PATH` is NOT broken

The source (below) says the client's PATH replaces the session's *only if the
client has one*. So strip it:

```
env -i HOME=$HOME TERM=xterm tmux -L refutesock new-session -d -s refute-l \
    -e "PATH=/S_INJECT_WINS:$REAL" -e "SENTINEL_CTL=hello_from_e" /usr/bin/python3 -c '…'
->  PATH=/S_INJECT_WINS:/usr/bin:/bin:/usr/sbin:/sbin     <-- THE INJECTED VALUE WINS
    CTL=hello_from_e

# and with no -e either, falling back to the global session env:
tmux -L refutesock set-environment -g PATH "/S_GLOBAL_WINS:$REAL"
env -i HOME=$HOME TERM=xterm tmux -L refutesock new-session -d -s refute-m /usr/bin/python3 -c '…'
->  PATH=/S_GLOBAL_WINS:/usr/bin:/bin:/usr/sbin:/sbin
```

**This is the decisive control.** The probe can produce *both* answers, and it
produces "injected wins" in exactly the case the source predicts. So the earlier
failures are not a broken probe, a wrong flag, or bad quoting — `-e PATH=` is
honoured, and then unconditionally clobbered by the client's PATH.

## tmux's own source — at the exact installed tag `3.7b`

`https://raw.githubusercontent.com/tmux/tmux/3.7b/spawn.c`

```
 41: * - PATH variable, comes from the client if any, otherwise from the session
 42: *   environment;
...
327	/*
328	 * Then the PATH environment variable. The session one is replaced from
329	 * the client if there is one because otherwise running "tmux new
330	 * myprogram" wouldn't work if myprogram isn't in the session's path.
331	 */
332	if (c != NULL && c->session == NULL) { /* only unattached clients */
333		ee = environ_find(c->environ, "PATH");
334		if (ee != NULL)
335			environ_set(child, "PATH", 0, "%s", ee->value);
336	}
```

Preceded (master line numbering, identical code) by:

```
391	/* Create an environment for this pane. */
392	child = environ_for_session(s, 0);
393	if (sc->environ != NULL)
394		environ_copy(sc->environ, child);
```

**The ORDER is the whole story.** The session environment — which is where
`new-session -e` lands — is written into the child *first*, then the client's
`PATH` overwrites it. Documented, intentional, and PATH is the only variable
treated this way (arm C: `FOO_CLIENT` did not leak).

`update-environment` does **not** contain `PATH` (13 entries, all X11/SSH/Kerberos),
so nothing re-adds it on attach either.

## VERDICT: **SURVIVES**

All three sentences of the claim hold on tmux 3.7b on this machine:

1. *"the pane process inherits the PATH of the tmux CLIENT"* — yes, empirically
   (arms A, B, C, E, F, G5, G6, J, K, with four distinct client sentinels) and
   by tmux's own source comment.
2. *"`-e PATH=X` does not give the pane PATH=X; it is stored in the session
   environment but is not what the pane's process gets"* — exactly right, and
   `show-environment -t <sess> PATH` returning `/S_INJECT…` while the pane held
   `/S_CLIENT…` is the literal demonstration.
3. *"not caused by the login shell sourcing a profile"* — right. The override
   happens in `spawn_pane()` before any exec; arms with `python3 -c` (no shell),
   `/bin/sh -c` (no profile, `$ENV` unset) and `zsh -lic` (profile really runs)
   all agree, and `zsh -lic` shows the injected value is *absent*, not
   *overwritten*.

**One precision the claim omits** (does not falsify it, but is worth carrying as
the fact's CONDITION): the override is conditional on
`c != NULL && c->session == NULL && client has a PATH`. If the client has no
PATH, `-e PATH=` wins (arm L). This is why the claim is true *here*:
`cc_main` spawns tmux with `env = {**os.environ, "PATH": checked.path}`
(`launch.py:527`), so the client always has a PATH.

## Is the `launch_argv` change a regression? No.

`launch.py:527` — `env = {**os.environ, "PATH": checked.path}`, then
`subprocess.run(argv_out, env=env)`. The removed `-e PATH={path}` carried the
**same** `checked.path` the client already carries. Per spawn.c the client's
value wins, so the `-e` was writing a value that was then overwritten by an
identical value: a no-op. Removing it changes no observable behaviour, and the
delivery mechanism that actually works (the client env) is untouched.

Caveat, unchanged by either version: `new-session -A` on an **existing** session
attaches instead of spawning, and `update-environment` has no `PATH`, so an old
session keeps its old PATH. Neither the old nor the new code addresses that.

## Control arms run (a result without its control is an opinion)

* **Positive on `-e`**: `-e SENTINEL_CTL=hello_from_e` delivered to the pane in
  every arm that asked for it → `-e` and the probe both work.
* **Positive on `-e PATH` specifically**: arm L, `env -i` client → injected PATH
  reached the pane. The mechanism is functional; it is *outranked*, not broken.
* **Negative**: arm G6, no `-e` at all → pane PATH == client PATH byte-for-byte.
* **Server ≠ client**: arm B (`/S_SERVER` vs `/S_CLIENT`) and arm K (server's
  real PATH contains `editorconfig-checker`, client's does not).
* **Shell ≠ cause**: `python3 -c` (no shell) vs `/bin/sh -c` vs `zsh -lic`, all
  identical on the deciding fact.
* **Bad-probe check**: arms G/I first returned empty; that was `capture-pane`
  scrolling, not a result — diagnosed and replaced with file-writing probes
  rather than reported as a finding.

## Cleanup

Private socket server `refutesock` gone, stale socket file removed. Default
server still has exactly `kb` and `knowledge-base`; no `refute-*` session
remains. `tmux kill-server` was never run on the default socket.

## GitHub repos touched

- [tmux/tmux](https://github.com/tmux/tmux) — `spawn.c` at tag `3.7b` and
  `master`; the authoritative statement that a pane's PATH comes from the client.
