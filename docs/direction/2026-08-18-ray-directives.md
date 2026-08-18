# Directives — 2026-08-18 (Ray, verbatim)

**Stored verbatim**, following `docs/direction/2026-08-17-ray-directives.md`, because
this directive's own first complaint is that requirements get lost between sessions.
Do not paraphrase, summarise, or "clean up" the text below — it is the artifact.
Analysis, status and open questions go in the sections *after* the verbatim block,
never inside it.

**This file must stay under `docs/direction/**`** — that path is formatter-exempt in
`hk.pkl` precisely because a spell-checker "fixing" a verbatim record edits what
someone said.

---

## VERBATIM

> /clear-prep
> option 1 but then we have to do the following:
>
> you are still not following instructions and losing requirements/instructions between sessions that /clear-prep is having issues w the handoff files
>
> we cannot do any graphify work on old stale versions as this will cause us to run on versions that could have outdated functionality or bugs
> - we need to enforce this can never happen again
> - right now the latest version is 0.9.46
> - our python library needs to handle and take into account that the graphify version will keep getting new versions as we keep working
>
> we need a full session review workflow sweep to aggregate all the issues and requirements missed and anything vague an agent can miss and fix all of these so we stop compounding mistakes and making it hard to get back to moving forward
> the list of issues need to be durably stored as github issues and/or remapped to a wayfinder map
>
> and we need to enforce reviewing all pr reivews from bots instead of ignoring them
>
> and we need to start getting ready to run /clear-prep once the context is at 20% (which right now is 200K tokens)
> - so that the handoff doesnt have to handle too much
> - and we need to enforce smaller tasks that can fit into this token budget
>
> and we ensure we dont lose any pending work on git worktrees and/or branches of from the backup directory
>
> and we need to ensure that all documentation and code is in a state that if a subscription plan gets depleted a humand and/or another ai llm agent can take over understanding current state, pending issues/tasks, gotchas, etc
>
> we need to prioritize what issues to fix right away that will prevent mistakes for us to move forward
> if possible fixing the issues in parallel if the chance of conflict is zero or can be pre-planned
>
> we need to enforce a zero tolerance on repeating mistakes
>
> we need to enforce not doing any work until all critical currency dependencies are up to date

The `option 1` above is Ray's answer to a question about **scope drift** in the corpus
run: *"Run it and let the gate refuse + retry"* — the staging gate already catches every
drifted chunk, so nothing wrong can merge; run the 58 chunks, let refused chunks fail,
then re-run just those.

---

## The ordering this directive imposes

The last line is a **gate on everything else**, and it is stated as one: *"not doing any
work until all critical currency dependencies are up to date."* So the sequence is not a
preference:

1. **Currency first.** `mise run kb-currency-check`, run 2026-08-18, reports **eight**
   pins behind upstream, not one: graphify `0.9.45 -> 0.9.46`, mise `2026.8.3 -> 2026.8.6`,
   hk `1.54.1 -> 1.55.0`, uv `0.12.3 -> 0.12.5`, ruff `0.16.2 -> 0.16.3`,
   ty `0.0.69 -> 0.0.72`, doppler `3.76.1 -> 3.76.5`, fnox `1.32.0 -> 1.33.0`. A ninth,
   `skillopt`, is pinned to a VCS revision and reports **NOT CHECKED** — unknown, not
   fine. Nothing else starts until these are resolved.
2. Then the session-review sweep, whose output is **durable GitHub issues** (and/or a
   wayfinder map), not a report.
3. Then the prioritised fixes, in parallel where conflict is provably zero.

## What each item is asking for, and what already exists

| # | Directive | Status here |
|---|---|---|
| 1 | `/clear-prep` loses requirements between sessions | The handoff is `.agent/plans/session-*.md`, which is **gitignored** — it does not survive a clone. That is a candidate root cause and is not yet fixed. |
| 2 | Never run graphify work on a stale version; the library must expect new versions continuously | `currency.toml` tracks graphify and `kb-currency-check` is offline+fast and DID report the drift — but nothing BLOCKS work on a stale pin, which is the gap this directive names. `kb_setup.currency.apply` is [recorded as unreachable for graphify](../../graphify-out/memory) — bump by hand. |
| 3 | Full session-review sweep → durable issues / wayfinder map | The workflow was rebuilt and committed this session (`.claude/workflows/session-review.js` + `kb-session-review` skill). It has **not been run** yet. |
| 4 | Review ALL PR bot reviews instead of ignoring them | Today CodeRabbit is **advisory and non-blocking** (`kb_setup.pr._ADVISORY_CHECKS`), and `Repowise / code health` was made advisory on #336. Reported, but routinely not acted on. |
| 5 | Prepare `/clear-prep` at 20% context (~200K of a 1M window); enforce smaller tasks | Nothing measures remaining context or bounds task size today. |
| 6 | Lose no pending work on worktrees / branches / the backup directory | Three worktrees exist under `../worktrees/`, plus ~20 local branches. Not audited this session. |
| 7 | Docs + code must let a human or another agent take over cold | Partly true (rules, skills, `docs/`), but the handoff being gitignored (item 1) directly undermines it. |
| 8 | Prioritise the issues that prevent further mistakes; parallelise where conflict is zero | Depends on item 3's output. |
| 9 | Zero tolerance on repeating mistakes | This session repeated two known classes: a wait condition satisfied by pre-existing state, and `git add -A` sweeping derived output into a commit. Both are already written down. |
| 10 | No work until critical currency deps are current | Blocks items 2–8. **Start here.** |

## Rulings, given by Ray 2026-08-18 in the same exchange

These were asked as `AskUserQuestion` and answered; they are recorded here rather than
left in a transcript, which is the whole subject of item 1.

- **Item 5 — the `/clear-prep` trigger is BOTH, whichever fires first.** The session
  token budget (exactly readable from inside a turn) AND an estimate of the 1M context
  window. Ray chose both over either, so a threshold that one measure misses is still
  caught by the other. Neither may be silently dropped for being harder to measure.
- **Item 3 — the sweep's output is GITHUB ISSUES.** Filed with `gh`, labelled and
  prioritised, so they survive any session and any clone. A wayfinder map may be layered
  on later; it is not a substitute, and `/mattpocock-skills:wayfinder` cannot be
  model-invoked so only Ray can produce one.
- **Item 10 — currency means ALL EIGHT pins, in one sweep**, not graphify alone. Ray
  chose the widest option explicitly, over "graphify first" and over "graphify plus the
  gate toolchain". So the gate does not lift until every pin above is resolved, and
  `skillopt`'s NOT-CHECKED state is part of that resolution rather than an exception.
