---
type: "query"
date: "2026-08-07T16:38:51.893514+00:00"
question: "Does graphify 0.9.35 supersede kb_setup.chunks.collision_issues, i.e. do its own shrink guards catch a basename source_file collision?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does graphify 0.9.35 supersede kb_setup.chunks.collision_issues, i.e. do its own shrink guards catch a basename source_file collision?

## Answer

No, and a source read alone gets the SCOPE wrong. There are TWO upstream guards. build_merge excuses a lost node on the SAME predicate that dropped it (_kept build.py:1639 vs _explained :1851, same new_sem_sources set), so it can never fire on this class. to_json has a SECOND, COUNT-based guard that refuses a net node-count DROP — and a small 2-vs-3-node reproduction trips it (rc=1, nothing written), which reads as upstream covers this. It does not: the real failure is a net GAIN, because the aggressor chunk adds its own nodes while destroying another sources. PR #197 printed +796 with the total rising 681. Reproduced at 5-vs-3 on the real 342,266-node graph: NOTHING refused, rc=0, 3 nodes destroyed, reported only by our own merge-line arithmetic. Graph restored byte-identical afterwards.

## Outcome

- Signal: useful