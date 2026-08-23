# Refutation lane — finding: "Nine GitHub issues from the directive's addendum should have been filed but were not"

Claim (verbatim): *Nine GitHub issues from the directive's addendum should have
been filed but were not; session filed only 1 issue while carrying 9+ directive
requirements.*
Evidence offered: *Directive §3 lines 301–355 (third addendum items 1, 4, 5, 6, 7)
+ current `gh issue list` shows no issues for currency roster, gitleaks,
kingfisher, rumdl, universal logger, schema dedup, or context trigger.*

## Verdict: REFUTED

The load-bearing word is **"should"**. The primary artifact the finding cites
says the opposite, *inside the line range the finding itself quotes*.

### Probe 1 — read the cited range's own second line

```
$ grep -n "THIRD ADDENDUM\|NEXT session\|DELIBERATELY NOT ANALYSED\|analyzed after\|below items need to be prioritized" docs/direction/2026-08-18-ray-directives.md
292:## THIRD ADDENDUM — VERBATIM (Ray, at /clear-prep, 2026-08-18)
294:**Stored verbatim and DELIBERATELY NOT ANALYSED in the session that received it.**
295:Ray's own instruction: *"but just store this verbatim so it is analyzed after
297:prioritisation are the NEXT session's work, fed by a full session-review sweep
301:> below items need to be prioritized and add github issues if they have not been filed yet and prioritized with the eventual aggregation/triage of github issues
302:> - but just store this verbatim so it is analyzed after /clear instead of in this session
```

`sed -n '294,303p'`, verbatim:

```
**Stored verbatim and DELIBERATELY NOT ANALYSED in the session that received it.**
Ray's own instruction: *"but just store this verbatim so it is analyzed after
/clear instead of in this session"*. The analysis, the issue filing and the
prioritisation are the NEXT session's work, fed by a full session-review sweep
and the issue aggregation/triage this addendum asks for. Anything below that
reads like a task is a task for that round, not this one.

> below items need to be prioritized and add github issues if they have not been filed yet and prioritized with the eventual aggregation/triage of github issues
> - but just store this verbatim so it is analyzed after /clear instead of in this session
```

The finding cited **lines 301–355** and evidently stopped at 301. Line **302 is
inside its own bound** and is Ray's verbatim deferral. This is the classic
bounded-read failure: the refuting bytes sit one line past where the reader
stopped, within the range they quoted.

### Probe 2 — the addendum did not exist for most of the session

The addendum was delivered at `/clear-prep` and committed as `7b91b572`:

```
7b91b572 2026-08-18T15:05:18-05:00  docs(direction): store Ray's /clear-prep addendum verbatim, unanalysed
6fc28270 2026-08-18T15:06:39-05:00  chore(memory): record the session-review seam round   <- last commit of the round
```

= **20:05:18Z** and **20:06:39Z**. The addendum entered the repo **81 seconds
before the session's final commit**. "Nine issues should have been filed" from a
document that existed for ~1 minute, against an explicit instruction not to
analyse it in that session, is not a defect — it is compliance.

### Probe 3 — at least one addendum item was SHIPPED, not deferred

Addendum item *"track the last session/transcripts … but provide the ability to
rerun a datetime range or specific session"* was **implemented in the reviewed
session**, not left unfiled:

- `python/src/kb_setup/session_select.py` — `--current | --sessions <id>… |
  --last N | --since <ISO> [--until <ISO>]` (`_VALUE_FLAGS` at :356, window
  resolution at :295–312).
- commits `15866968` (19:06Z) *feat(session-select): resolve WHICH sessions a
  review covers, deterministically* and `7914e97b` (19:20Z) *feat(session-review):
  take a resolved session list*.

This also **contradicts set finding #24** ("Session-review tracking mechanism …
was not implemented; next session cannot identify pending work without re-running
the entire workflow").

### Probe 4 — control-armed keyword sweep of the issue backlog

`gh issue list --state all --limit 400` → 210 rows.

| token | hits | token | hits |
|---|---|---|---|
| currency | 11 | rumdl | 0 |
| roster | 1 | kingfisher | 0 |
| gitleaks | 1 | logger | 0 |
| schema | 1 | antigravity | 0 |
| dedup | 1 | session-review | 4 |
| triage | 2 | clear-prep | 3 |

Control arm: `graphify` → **30** hits; `zzznonexistent` → **0**. The probe
discriminates.

So the *absence* half of the evidence is broadly true for kingfisher / rumdl /
logger / antigravity — but absence is only a defect if filing was owed **now**,
and probes 1–3 show it was explicitly owed to the NEXT round.

### What survives

Only the descriptive half: the reviewed session filed one issue (#346,
2026-08-18T19:51:06Z) and several addendum topics have no issue yet. That is a
true statement about the backlog and a correct input for the *next* round's
aggregation/triage pass. It is not a finding against the reviewed session.
