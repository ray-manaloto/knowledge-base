---
kind: lesson
source: feedback_long_mac_ops_keep_turn_engaged
---

# l-long-mac-ops-keep-turn-engaged

Long local Mac operations can be reaped when launched in the background and left across an idle turn boundary.
On 2026-07-13, two land attempts were killed; the third succeeded while its log was actively polled in-turn.
Under [[delegation-discipline]], launch with a log that records the real rc and keep polling until that line appears.
Then apply [[verification-discipline]] to the file-based rc, since a killed or completed harness notice is not the tool result.
