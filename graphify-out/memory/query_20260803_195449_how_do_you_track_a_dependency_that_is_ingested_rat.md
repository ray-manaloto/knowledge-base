---
type: "query"
date: "2026-08-03T19:54:49.718606+00:00"
question: "How do you track a dependency that is INGESTED rather than installed, without a permanent false red?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you track a dependency that is INGESTED rather than installed, without a permanent false red?

## Answer

currency.toml's third tool class: source_only = true. The engine assumed every tracked tool has a binary on PATH — _check_resolution reports a missing binary as DRIFT (correctly, for something that SHOULD be installed), so declaring microsoft/SkillOpt any other way emits 'skillopt is not installed on this host' on every session forever. SkillOpt has no binary and no [tools] pin: its Claude Code plugin (SkillOpt-Sleep) is fetched by git-subdir and needs no pip install. source_only skips every binary/pin check and keeps what matters: manifest ref+commit readable, the on-disk clone at the pinned commit (ABSENT clone is BLIND not DRIFT, since sources/<name>/ is gitignored and refetched by kb-build), the new-release probe off github, and the watch items. status.pinned carries the manifest ref so upstream.probe gets a real 'current'. Auto-apply is refused in currency.apply with the real remedy named (mise run kb-update -- <name>), because a source advances by moving its manifest, not by editing a mise pin that does not exist. Reusable for the other 32 pinned sources.

## Outcome

- Signal: useful