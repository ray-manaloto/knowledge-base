---
kind: lesson
source: feedback_agent_spawn_liveness
---

# l-spawned-is-not-running

A successful spawn response proves submission, not that the delegated agent began executing.
The 2026-07-15 silent no-op wasted about 25 minutes, but a 2026-07-24 absence probe also falsely declared four live agents dead.
Under [[delegation-discipline]], require a first-action liveness marker and give deep reviews realistic time.
Treat missing evidence as unproven rather than dead; [[verification-discipline]] favors positive confirmation over transcript archaeology.
After a deadline, ping once and do greppable work directly because delegation is an optimization, not a dependency.
