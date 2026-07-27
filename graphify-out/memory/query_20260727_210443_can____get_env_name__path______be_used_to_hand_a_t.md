---
type: "query"
date: "2026-07-27T21:04:43.410506+00:00"
question: "Can {{ get_env(name='PATH') }} be used to hand a task the session's real PATH?"
contributor: "graphify"
outcome: "useful"
---

# Q: Can {{ get_env(name='PATH') }} be used to hand a task the session's real PATH?

## Answer

No — and it is the trap, because it is documented, well-cited, and looks exactly right. mise binds get_env to PRISTINE_ENV, which reverses __MISE_DIFF and therefore REMOVES every path mise added. Under an activated shell those removed paths are precisely the tool install dirs a drift check exists to hunt, so get_env launders the evidence. Measured from one caller PATH carrying a sentinel plus a stale install dir: activated shell -> 0 install dirs surviving; env -i -> 1 intact. The published proof that made get_env look correct had used env -i, where the diff is empty and the laundering cannot show. Both mise.toml [tasks.cc-doctor] and python/src/kb_setup/launch.py carry 'do not simplify this to get_env' notes with the measurement.

## Outcome

- Signal: useful