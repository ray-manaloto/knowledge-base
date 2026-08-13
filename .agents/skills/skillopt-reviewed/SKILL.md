---
name: skillopt-reviewed
description: "Stage a SkillOpt mock or handoff cycle from a fully reviewed, content-addressed, redacted session-review ledger. Use only when the reviewed packet and project target descriptor already exist."
argument-hint: "<packet.json> <target.json> <mock|handoff> <trusted-receipt-sha256>"
---

# SkillOpt reviewed adapter

This is a thin workflow boundary. It never reads transcripts, harvests native
sessions, uses a network backend, schedules a run, or adopts a proposal.

Run exactly:

```bash
mise run kb-skillopt-reviewed -- $ARGUMENTS
```

The adapter accepts only artifacts cross-bound to the separately supplied,
trusted review-receipt digest. It writes only under `.agent/skillopt` and
returns an explicitly unverified typed receipt. A handoff return means external
work is pending; it is not completion or permission to adopt the staged result.
