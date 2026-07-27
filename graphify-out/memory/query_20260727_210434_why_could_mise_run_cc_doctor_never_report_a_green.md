---
type: "query"
date: "2026-07-27T21:04:34.639599+00:00"
question: "Why could mise run cc-doctor never report a green graphify check?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why could mise run cc-doctor never report a green graphify check?

## Answer

Because doctor_main judged os.environ['PATH'] — its OWN process PATH, not the session's. mise mangles PATH twice on the way to that process: 'mise run' injects every tool install dir, then 'uv' resolves to a mise shim which re-prepends them. Measured: the session held 37 entries / 0 install dirs; the doctor process held 192 / 154. A launcher that judges its own environment is judging the thing it was launched by, so the check could only ever fail. Fix: session_path() in python/src/kb_setup/launch.py — --path if given, else the session located via Claude Code's exported CLAUDE_PID with its environment read from the OS, else UNKNOWN with the reason. It never falls back to our own PATH; that fallback WAS the bug. Shipped in PR #47 (3f9fea4).

## Outcome

- Signal: useful