---
type: "query"
date: "2026-09-03T18:43:21.743356+00:00"
question: "How should a lane wait on a long-running command, and how do I check whether one is alive?"
contributor: "graphify"
outcome: "corrected"
correction: "A POINT-IN-TIME PROCESS CHECK IS NOT A STATE, AND IT FAILS IN BOTH DIRECTIONS.\nMeasured three times in one session, 2026-09-03 - twice by a lane, once by me.\n\nDIRECTION 1 - \"waiting\" when nothing was running. Two lanes ended a turn with\n\"I'll wait for the monitor notification\". In one case the process had already\nexited and the work sat uncommitted for ~20 minutes; in the other the first\nattempt had died leaving a 0-byte log. Neither lane was lazy: both had armed a\ncorrect Monitor. The defect was treating an ARMED-BUT-UNRESOLVED wait as\nequivalent to STILL-RUNNING, when the artifact was theirs to read at any moment.\n\nDIRECTION 2 - \"dead\" when it was running. I then checked `pgrep` myself, found\nnothing, and told the user the lane was dead. It was not: the lane had relaunched\nseconds earlier and I sampled the gap between relaunch-returning and codex\nforking. The 0-byte log I cited as proof belonged to the PREVIOUS, genuinely dead\nattempt - both files carried the same mtime, which is what made the wrong reading\nlook confirmed. The lane pushed back with a live `ps` tree and was right.\n\nTHE GENERALISATION: liveness is a claim about an interval, and `pgrep` answers\nabout an instant. A single negative sample proves nothing when the thing you are\nsampling can restart; a single \"still waiting\" proves nothing when the thing you\nare waiting on can exit. Both readings need a SECOND observation separated in\ntime, or an artifact that accumulates - a growing log, an rc file, a mtime that\nmoves.\n\nWHAT TO DO INSTEAD:\n- Read the artifact, never the notification. A background task's completion\n  notice carries the WRAPPER's exit code, not the task's; a foreground run that\n  has exited leaves no notice at all. Both fail silently and look like patience.\n- Before declaring a process dead, sample twice, or check whether an output file's\n  size or mtime is moving. `ps -o etime,stat` on a PID is stronger than `pgrep -fl`\n  on a pattern, because a truncated argv can hide the match you are grepping for.\n- THE BRIEFING IS THE FIX. Both lane stalls traced to my dispatch wording, which\n  said what to produce and never said how to wait. A dispatch whose output is a\n  FILE should say: run it in the foreground, bound it with the Bash tool's own\n  timeout parameter, and read the file. Reserve background+Monitor for genuinely\n  remote waits.\n"
---

# Q: How should a lane wait on a long-running command, and how do I check whether one is alive?

## Answer

A POINT-IN-TIME PROCESS CHECK IS NOT A STATE, AND IT FAILS IN BOTH DIRECTIONS.
Measured three times in one session, 2026-09-03 - twice by a lane, once by me.

DIRECTION 1 - "waiting" when nothing was running. Two lanes ended a turn with
"I'll wait for the monitor notification". In one case the process had already
exited and the work sat uncommitted for ~20 minutes; in the other the first
attempt had died leaving a 0-byte log. Neither lane was lazy: both had armed a
correct Monitor. The defect was treating an ARMED-BUT-UNRESOLVED wait as
equivalent to STILL-RUNNING, when the artifact was theirs to read at any moment.

DIRECTION 2 - "dead" when it was running. I then checked `pgrep` myself, found
nothing, and told the user the lane was dead. It was not: the lane had relaunched
seconds earlier and I sampled the gap between relaunch-returning and codex
forking. The 0-byte log I cited as proof belonged to the PREVIOUS, genuinely dead
attempt - both files carried the same mtime, which is what made the wrong reading
look confirmed. The lane pushed back with a live `ps` tree and was right.

THE GENERALISATION: liveness is a claim about an interval, and `pgrep` answers
about an instant. A single negative sample proves nothing when the thing you are
sampling can restart; a single "still waiting" proves nothing when the thing you
are waiting on can exit. Both readings need a SECOND observation separated in
time, or an artifact that accumulates - a growing log, an rc file, a mtime that
moves.

WHAT TO DO INSTEAD:
- Read the artifact, never the notification. A background task's completion
  notice carries the WRAPPER's exit code, not the task's; a foreground run that
  has exited leaves no notice at all. Both fail silently and look like patience.
- Before declaring a process dead, sample twice, or check whether an output file's
  size or mtime is moving. `ps -o etime,stat` on a PID is stronger than `pgrep -fl`
  on a pattern, because a truncated argv can hide the match you are grepping for.
- THE BRIEFING IS THE FIX. Both lane stalls traced to my dispatch wording, which
  said what to produce and never said how to wait. A dispatch whose output is a
  FILE should say: run it in the foreground, bound it with the Bash tool's own
  timeout parameter, and read the file. Reserve background+Monitor for genuinely
  remote waits.


## Outcome

- Signal: corrected
- Correction: A POINT-IN-TIME PROCESS CHECK IS NOT A STATE, AND IT FAILS IN BOTH DIRECTIONS.
Measured three times in one session, 2026-09-03 - twice by a lane, once by me.

DIRECTION 1 - "waiting" when nothing was running. Two lanes ended a turn with
"I'll wait for the monitor notification". In one case the process had already
exited and the work sat uncommitted for ~20 minutes; in the other the first
attempt had died leaving a 0-byte log. Neither lane was lazy: both had armed a
correct Monitor. The defect was treating an ARMED-BUT-UNRESOLVED wait as
equivalent to STILL-RUNNING, when the artifact was theirs to read at any moment.

DIRECTION 2 - "dead" when it was running. I then checked `pgrep` myself, found
nothing, and told the user the lane was dead. It was not: the lane had relaunched
seconds earlier and I sampled the gap between relaunch-returning and codex
forking. The 0-byte log I cited as proof belonged to the PREVIOUS, genuinely dead
attempt - both files carried the same mtime, which is what made the wrong reading
look confirmed. The lane pushed back with a live `ps` tree and was right.

THE GENERALISATION: liveness is a claim about an interval, and `pgrep` answers
about an instant. A single negative sample proves nothing when the thing you are
sampling can restart; a single "still waiting" proves nothing when the thing you
are waiting on can exit. Both readings need a SECOND observation separated in
time, or an artifact that accumulates - a growing log, an rc file, a mtime that
moves.

WHAT TO DO INSTEAD:
- Read the artifact, never the notification. A background task's completion
  notice carries the WRAPPER's exit code, not the task's; a foreground run that
  has exited leaves no notice at all. Both fail silently and look like patience.
- Before declaring a process dead, sample twice, or check whether an output file's
  size or mtime is moving. `ps -o etime,stat` on a PID is stronger than `pgrep -fl`
  on a pattern, because a truncated argv can hide the match you are grepping for.
- THE BRIEFING IS THE FIX. Both lane stalls traced to my dispatch wording, which
  said what to produce and never said how to wait. A dispatch whose output is a
  FILE should say: run it in the foreground, bound it with the Bash tool's own
  timeout parameter, and read the file. Reserve background+Monitor for genuinely
  remote waits.
