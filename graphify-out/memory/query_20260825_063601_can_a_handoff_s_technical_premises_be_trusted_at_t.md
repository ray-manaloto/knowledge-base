---
type: "query"
date: "2026-08-25T06:36:01.947288+00:00"
question: "Can a handoff's technical premises be trusted at the start of the next round?"
contributor: "graphify"
outcome: "corrected"
correction: "# A handoff's premises decay faster than its facts\n\nThree of the four premises this round inherited from the previous handoff were\nfalse by the time it started, and each was cheap to refute:\n\n- a named symbol (`_authorized_source_manifest`) that does not exist,\n- a drift (graphify b2cd3626 vs cdfb11c0) that had already been closed,\n- a build failure whose cause had been fixed after the record was written.\n\nNone was a lie when written. All three decayed because the repo moved.\n\n**The lesson: re-derive a handoff's premises before building on them, not after.**\n`/kb-resume` already reconciles branch, PR and gate claims against the repo — it\ndoes NOT reconcile the *technical* premises in the prose, and those are what a\nround's plan actually rests on. The reconciliation cost about four probes; acting\non any one of them unchecked would have cost a lane run.\n\n**The sharper form: the same decay applies to work you committed twenty minutes\nago.** This round resolved eight manifest commits with `git ls-remote --tags` and\ncommitted them. A lane then independently reported that annotated tags make that\ncommand return the TAG OBJECT. Arming it found exactly one defect among six\ntag-pinned sources — FFmpeg — which is #395 repeating after 17 days.\n\nThe catch did not come from reviewing the commit. It came from a DIFFERENT lane\nreporting a method rule, which sent me back to a decision I had already treated as\nsettled. A finding about METHOD should always be re-applied to work already done\nin that session, not only to work still ahead of it.\n"
---

# Q: Can a handoff's technical premises be trusted at the start of the next round?

## Answer

# The dependency sweep round — 2026-08-25

Ray's option-4 directive: every first-level mise.toml / pyproject.toml dependency
up to date, its source synced, and graphify's AST step run over all of them.

## What the round actually found

The sweep's premises were mostly wrong, and finding that out was most of the value.

- The handoff's `_authorized_source_manifest` symbol DOES NOT EXIST in kb_setup.
  Control-armed: `authorized` returns 10 hits elsewhere, so the probe discriminates.
- graphify was NOT drifted. Manifest, clone and installed package all agree at
  0.9.49 / cdfb11c0.
- The recorded kb-build failure's stated cause NO LONGER REPRODUCES. Armed both
  directions against `graphify_health._unaccounted_stderr`: the exact recorded line
  now filters to empty, while a real WARNING and a trailing-text variant survive.
- The three "drifts" were manifest-side only; mise.toml already pinned the newer
  pkl / typos / codex. The real upstream drift was five OTHER tools.
- Python first-level deps were already current: all 8 available updates transitive.

## What shipped

- 8 new source manifests (76 -> 84), each pinned to the version we RUN.
- The ffmpeg manifest corrected: `n9.0.1` is an ANNOTATED tag and the first commit
  stored the TAG OBJECT. Caught within the hour because a release-note lane
  independently flagged `gh api` as the required resolution route.
- antigravity-cli 1.1.20 and ty 0.0.74, both verified.
- docs/direction/2026-08-25-ray-directives.md — the primary source for the ruling
  that relaxes do-not.md #4.
- Five tickets (#483-#487) and a correction on #417.

## The rulings

- claude-cli AND openai-cli are both permitted graphify agents. do-not.md #4's
  phrasing goes. clean_env() does NOT change, and keeping the OPENAI_API_KEY strip
  is now load-bearing for a NEW reason: upstream's own comment says the CLI route
  exists to stay on OAuth, and reverting it can send the work through a metered key.
- codex flips skip -> include, manifest advanced FIRST so the registered hash
  describes bytes we actually build.
- ffmpeg is `include`: measure before excluding.
- The dependency table is a dependency x pipeline-step MATRIX, shipping v1 with
  honest UNKNOWNs rather than inventing green cells.


## Outcome

- Signal: corrected
- Correction: # A handoff's premises decay faster than its facts

Three of the four premises this round inherited from the previous handoff were
false by the time it started, and each was cheap to refute:

- a named symbol (`_authorized_source_manifest`) that does not exist,
- a drift (graphify b2cd3626 vs cdfb11c0) that had already been closed,
- a build failure whose cause had been fixed after the record was written.

None was a lie when written. All three decayed because the repo moved.

**The lesson: re-derive a handoff's premises before building on them, not after.**
`/kb-resume` already reconciles branch, PR and gate claims against the repo — it
does NOT reconcile the *technical* premises in the prose, and those are what a
round's plan actually rests on. The reconciliation cost about four probes; acting
on any one of them unchecked would have cost a lane run.

**The sharper form: the same decay applies to work you committed twenty minutes
ago.** This round resolved eight manifest commits with `git ls-remote --tags` and
committed them. A lane then independently reported that annotated tags make that
command return the TAG OBJECT. Arming it found exactly one defect among six
tag-pinned sources — FFmpeg — which is #395 repeating after 17 days.

The catch did not come from reviewing the commit. It came from a DIFFERENT lane
reporting a method rule, which sent me back to a decision I had already treated as
settled. A finding about METHOD should always be re-applied to work already done
in that session, not only to work still ahead of it.
