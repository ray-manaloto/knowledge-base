# Refutation lane: "Quick start instructs a command the guard denies"

Finding under test: CLAUDE.md:93 (and invariant 1 at :15) instructs
`graphify install --project`, while hook_guard.py:86 denies `install`
unconditionally and mise-tasks-only.md:26 redirects that exact command to
`mise run kb-skill-refresh` (#133).

## VERDICT: NOT REFUTED — CONFIRMED, with a live probe and both control arms

## Leg-by-leg verification (all reads/probes 2026-08-18, this session)

| Leg | Claim | Verified | Evidence |
|---|---|---|---|
| 1 | CLAUDE.md:93 Quick start says `graphify install --project` | YES, line exact | Read: line 93 is `graphify install --project                    # project-scoped skill + graphify-out/` inside the `## Quick start` bash fence, no qualifier anywhere in :89-100 scoping it to humans |
| 2 | CLAUDE.md:15 invariant 1 says install only with `--project` | YES | lines 14-15: "Install only with `graphify install --project`. Never bare `graphify install`" |
| 3 | hook_guard.py:86 denies install unconditionally | YES, line exact | line 86: `"install": "NOT ALLOWED — graphify install mutates config; this KB is project-only",` in `_REDIRECT`; `install` absent from `_ALLOWED_READONLY` (:91-100); `decide()` (:142-158) matches only the SUBCOMMAND (`_GRAPHIFY_CMD` :38 captures `install`), so a trailing `--project` cannot exempt it. The only escape in code is the `mise run kb-` short-circuit (:139), which the standalone Quick start line does not contain |
| 4 | mise-tasks-only.md:26 redirects to kb-skill-refresh citing #133 | YES, line exact | line 26 is the `graphify install --project` → `mise run kb-skill-refresh` row, "(which regresses `.claude/settings.json` every run — #133)" |

## The decisive live probe (executed, not reasoned)

`uv run python -c "from kb_setup.hook_guard import decide; ..."` (2026-08-18):

- `decide('graphify install --project')` → **DENY**: "Do not run `graphify
  install` by hand. Use the mise task: NOT ALLOWED — graphify install mutates
  config; this KB is project-only. ..."
- `decide('graphify install')` → same DENY.
- CONTROL (allow direction): `decide('graphify path "A" "B"')` → `None`;
  `decide('graphify explain "concept"')` → `None`.
- CONTROL (distinct-deny direction): `decide('graphify query "x"')` → a
  DIFFERENT deny with the kb-query redirect.

The probe discriminates in both directions; the deny is not an artifact of the
probe. The original finding's probe (file reads) could NOT only have produced
this answer — the same fact reproduced by an independent route (executing the
decision function).

## The deny is live and pinned by the repo itself

- `.claude/settings.json:13-31` wires PreToolUse `Bash|Grep` →
  `uv run --project .../python kb-setup hookguard` (plus graphify's own
  `hook-guard search`). Not dead code.
- `python/src/kb_setup/eval_cases.py:84`:
  `_D("graphify install --project", _DENY, "install mutates config — never by hand")`
  — the EXACT Quick start command is a committed DENY fixture, driven through
  `decide()` by `tests/test_eval_cases.py` (:148 iterates `GUARD_FIXTURES`).
  (Control arm on my 0-hit grep of tests/test_hook_guard.py for "install":
  same file greps 35 for "graphify", 6 for "decide" — the absence there is
  real; the pin lives in the eval fixture instead.)
- `mise.toml:950` — `[tasks.kb-skill-refresh]` exists, so the redirect target
  is real.
- Transcripts: 5 of the round's `*.jsonl` (mtime >= 2026-08-17, in
  `~/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base`)
  contain the string "graphify install mutates config" (file-level count via
  `find -newermt 2026-08-17 -exec grep -l`; not disambiguated between actual
  hook firings and sessions reading hook_guard.py — either way the string
  circulates in the window).

## Honest scoping caveat (does not refute)

The guard governs Claude's Bash/Grep tool calls only; a human in a terminal is
not blocked. But root CLAUDE.md is the agent-loaded instruction file — its
primary reader is exactly the actor the guard denies, and `mise-tasks-only.md`
(+ #133: the installer regresses `.claude/settings.json` every run) says even
the human should use `kb-skill-refresh`. The contradiction stands for the file's
audience.

## Directive + handoffs (all read IN FULL)

`docs/direction/2026-08-18-ray-directives.md` and handoffs b, c, d, e, f, g,
2026-08-18-a: none mentions the Quick start line, `graphify install`, or any
ruling that would legitimise CLAUDE.md:93. No contradiction found anywhere.

## Contradicting findings / corroboration

- No other finding from the set was provided to this lane; nothing in the
  directive, the 7 handoffs, or the settled block contradicts this one.
- The repo CORROBORATES it in more places than the finding cites:
  `do-not.md` #1 ("always pass `--project`", implying the command is run) vs
  `do-not.md` #3 (never run graphify by hand at all, machine-enforced);
  `md-size-budgets.md` calls the skill tree "installer-generated
  (`graphify install --project`)" while saying it is "regenerated by
  `mise run kb-skill-refresh` rather than edited".
- Adjacent SAME-CLASS instance observed live this session (bonus lead, not this
  finding): the graphify-bundled hook's additional-context text says
  "You MUST run `graphify query ...`" — a command `_REDIRECT` denies
  (hook_guard.py:77). An instruction surface telling the agent to run a command
  the other hook refuses.

## Coverage

- REACHED AND ANALYSED: CLAUDE.md:1-100; hook_guard.py (full, 399 lines);
  mise-tasks-only.md:1-60; live `decide()` probes with both control arms;
  eval_cases.py:84 + test_eval_cases.py wiring; settings.json hook block;
  mise.toml kb-skill-refresh existence; transcript string count (5 files);
  the 2026-08-18 directive IN FULL; all 7 handoffs IN FULL.
- OPENED BUT NOT FINISHED: none.
- NEVER REACHED: GitHub issue #133's own body (the finding only claims the
  rule CITES it, which is verified from the rule text); the other findings in
  this verification set (not provided); mise-tasks-only.md:60-end (enforcement
  detail already known from the auto-loaded copy).
