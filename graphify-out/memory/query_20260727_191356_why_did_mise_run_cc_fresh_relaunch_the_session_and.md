---
type: "query"
date: "2026-07-27T19:13:56.335720+00:00"
question: "Why did mise run cc-fresh relaunch the session and still leave a dirty PATH?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did mise run cc-fresh relaunch the session and still leave a dirty PATH?

## Answer

Because clean_path strips /mise/installs/ entries, after which tmux can only resolve to a mise SHIM — and a shim re-enters mise, which prepends all 154 install dirs back. The cleaning routes the launch through the thing that undoes it. Measured: env PATH=$CLEAN <install-dir>/node -> installs=0; the same via <shims>/node -> installs=154; through tmux, bare tmux gives server+pane installs=154 while $(mise which tmux) gives 0. Unsetting __MISE_DIFF/__MISE_ORIG_PATH/__MISE_SESSION/__MISE_ENV_CACHE_KEY/MISE_ENV_CACHE does NOT help — re-injection is what a shim IS. Fix: shim_free()/Binaries.resolve() in kb_setup.launch (PR #45). The old test missed it because it asserted a sentinel REACHED the pane; a shim prepends rather than discards, so that test passes identically at installs=154 and 0 — only an ABSENCE assertion on install dirs can see it.

## Outcome

- Signal: useful