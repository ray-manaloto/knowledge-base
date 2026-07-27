---
type: "query"
date: "2026-07-27T17:51:49.381351+00:00"
question: "Why did the verified-PATH launcher still leave a session resolving graphify through a frozen mise install dir?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did the verified-PATH launcher still leave a session resolving graphify through a frozen mise install dir?

## Answer

tmux hands a new pane the CLIENT's PATH and discards 'new-session -e PATH='; the injected value IS stored in the session environment but is not what the pane process gets. Control arms: '-e FOOBAR=' arrives intact (so -e is not broken, PATH is specifically overridden), an arbitrary client var does NOT leak in (so it is not the whole client env), a 'python3 -c' pane command (not a shell) still gets the client PATH (so no login profile is involved). The override is conditional on the client HAVING a PATH: under 'env -i', -e PATH= wins. Durable fix is not PATH hygiene at all but kb_setup.graphify_env.graphify_exe(), resolving via 'mise which' so corpus correctness never depends on PATH order. Also: 'new-session -A' on an EXISTING session attaches instead of spawning and update-environment has no PATH, so an old server keeps its birth PATH - that is what 'mise run cc-fresh' exists to clear.

## Outcome

- Signal: useful