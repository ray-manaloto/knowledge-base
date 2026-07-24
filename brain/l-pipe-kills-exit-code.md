---
kind: lesson
source: feedback_pipe_kills_exit_code
---

# l-pipe-kills-exit-code

A pipeline or trailing shell command reports the last command's status and can hide the gate that mattered.
PR #68 followed a local hk failure masked by tail returning zero, so CI exposed an error already present in the log.
Use pipefail, or capture the gate output and its rc before inspecting the log separately.
Under [[verification-discipline]], trust the recorded tool rc and positive result lines, never a wrapper notification alone.
