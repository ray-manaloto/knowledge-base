---
type: "query"
date: "2026-08-07T08:12:06.373371+00:00"
question: "When a session bumps a tool pin, does a bare invocation of that tool in the same session run the new version?"
contributor: "graphify"
outcome: "useful"
---

# Q: When a session bumps a tool pin, does a bare invocation of that tool in the same session run the new version?

## Answer

NO. On this host the previously-installed version directory is injected into PATH AHEAD of the mise shims, so a bare call keeps running the OLD binary until the shell re-resolves. Measured 2026-08-07 across FOUR tools at once: graphify bare 0.9.34 vs pin 0.9.35; codex bare 0.146.1 vs pin 0.147.0; uv bare 0.11.28 vs pin 0.12.2; python via .venv 3.14.0 vs pin 3.14.7. It is NOT mise version cache -- mise cache clear was run and verified and changed nothing. It is the shell PATH, which is why restarting the session fixes it and why no file edit can. OPERATIONAL RULE: in the same session that bumps a tool, use the full path from mise which TOOL to invoke it; a bare call is measuring the old version. This had been recorded three times as three separate one-offs before being seen as one host condition.

## Outcome

- Signal: useful