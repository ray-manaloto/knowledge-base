---
type: "query"
date: "2026-07-28T03:09:52.886643+00:00"
question: "Can skill-creator description-optimization measure a skill already installed in the same repo?"
contributor: "graphify"
outcome: "corrected"
---

# Q: Can skill-creator description-optimization measure a skill already installed in the same repo?

## Answer

No, and it fails SILENTLY behind a plausible scoreboard. run_eval clones the candidate description into .claude/commands/SKILL-skill-HASH.md then checks whether that clone name is a substring of the Skill tool call argument. With the real skill installed in the same project the model triggers THAT one instead — measured: Skill invoked with skill=goal-engineering — so the check is always False and every query records not-triggered. It reports recall 0 percent, precision 100 percent, and that precision is worthless: when nothing can fire, every should-not-trigger query passes for free. Three more traps in the same harness. (1) run_single_query sets stderr=DEVNULL, so a failing subprocess and a non-trigger are indistinguishable. (2) The subprocess does the WHOLE TASK, not just the trigger decision, so an expensive but correct trigger blows the 300s timeout and scores as a miss — it also wrote a real goal+rider pair into docs/goals as a side effect. (3) find_project_root walks up from CWD, so invoking it by cd-ing into the plugin directory resolves the project root to HOME and writes temp files into ~/.claude/commands, violating the no-user-config invariant; use PYTHONPATH and keep cwd in the repo. To get a real number, run it against a copy of the repo with the skill directory removed.

## Outcome

- Signal: corrected