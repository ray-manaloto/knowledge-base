# Currency run — claude-code — 2026-08-05T23:35:21+00:00

**Verdict:** claude-code 2.1.220 → v2.1.222: 2 question(s) for review

Related: [[tool-currency-log]] · [[claude-code]]

## Step 1 — in sync?

Pinned `2.1.220` · resolved `2.1.222`

| check | status | detail |
|---|---|---|
| version | drift | claude on PATH is 2.1.222 but the reviewed version is 2.1.220 — it self-updated. Review the releases between them, then bump `expected` in currency.toml to record that you have |

## Steps 2-3 — upstream

- Latest (github): `v2.1.222`
- GitHub release: `v2.1.222`
- Reachable: yes

### Release notes

```text
## v2.1.221

## What's changed

- [VSCode] Added Focus view: a chat-menu toggle that hides tool activity behind an expandable per-turn summary with a live running-tool indicator, toggled with `Ctrl+Alt+F` or the "Claude Code: Toggle Focus view" command
- Added `mode: "mask"` for sandbox credential files on Linux and WSL — sandboxed commands read a sentinel copy (the whole file, or just the spans captured by an `extract` regex) while the sandbox proxy substitutes the real value on egress; on macOS file masking falls back to `deny`
- Added warnings to `claude plugin validate` when a marketplace or plugin name would be rejected by Claude Desktop's managed marketplace sync
- Added a `prompt-audit` subcommand to the `claude-api` skill for auditing prompts and tool descriptions for patterns written for older models
- Fixed a Bash tool permission-check bypass where zsh could execute hidden commands in `[[ ]]` regex conditionals; affected commands now prompt for permission
- Fixed PowerShell permission checks mishandling paths containing quote characters on Windows; such paths now prompt for approval
- Fixed the thinking toggle having no effect for the rest of a session that started with t

… (truncated)
```

### Features to consider adopting

_**Could not tell.** The release notes are non-empty but match no changelog format this scan understands (no `Added`/`Highlights` section, no `feat:` prefixes, no adoption phrases), so this is **not** a report of zero features — read the notes by hand._

## Step 4 — tracked issues and watch items

| item | state | updated | comments | moved? |
|---|---|---|---|---|
| local:sessionend-hooks-share-a-1.5s-budget | local | — | 0 | no |
| local:goal-evaluator-model-is-not-always-haiku | local | — | 0 | no |
| local:nested-project-skills-are-not-loaded-at-startup | local | — | 0 | no |
| local:permissionrequest-now-fires-where-nobody-can-be-asked | local | — | 0 | no |

## Step 5 — decision

Gates passed:

- ✅ patch-level bump
- ✅ latest version has a readable GitHub release
- ✅ no breaking/removal/deprecation marker
- ✅ extras unchanged

### Gate: no tracked issue moved

**4 local watch item(s) must be re-probed against this release. Done?**

- Detail: local:sessionend-hooks-share-a-1.5s-budget: hooks.md gained this on 2026-07-30 (#76): "`SessionEnd` hooks share a 1.5-second budget; if your settings set a longer per-hook `timeout`, Claude Code raises the budget to match, up to 60 seconds." THE TIMEOUT IS LOAD-BEARING, and not for the reason it looks. Without any `timeout` our SessionEnd `brain-transcript-audit` would get **1.5s** — a transcript scan cannot finish in that, and a killed SessionEnd hook is silent, so the failure mode is an audit that simply stops existing. The declared number is what buys the budget. `.claude/settings.json` declared **120**, which the documented ceiling can never grant; lowered to **60** so the config states what it can actually get. Do not read the change as a reduction — the effective budget is identical, and 60 is the documented maximum. Do not delete the field to "use the default": that is the one edit that would silently cost the audit ~58 of its 60 seconds. Re-probe on each docs review: if the ceiling moves, this number moves with it.; local:goal-evaluator-model-is-not-always-haiku: goal.md, same 2026-07-30 revision. Was "defaults to Haiku"; now "defaults to Haiku ON THE CLAUDE API; on a third-party provider, check your provider page", plus a new `ANTHROPIC_DEFAULT_HAIKU_MODEL` override whose scope is GLOBAL — it also rebinds the `haiku` alias and background functionality such as conversation summarization. Why it is tracked rather than absorbed: the goal-engineering skill's central rule is that a clause must be settleable by "a Haiku-class reader, given the transcript and nothing else". That phrasing survives — it is now a FLOOR rather than a description of the deployed model. The risk this guards against is the inverse of the obvious one: not that the evaluator is weaker than assumed, but that someone observes a smart evaluator judging a vague clause correctly and concludes the clause was fine. Consequence for recorded outcomes: `kb-goal-outcome` results are conditional on the evaluator that produced them. A `stalled` under one model is not evidence about another (`verify-before-advancing.md`, "carry a fact's CONDITION"). UNCHANGED and re-verified the same day, which is the reason the skill needed no structural edit: the transcript-only/no-tools constraint (quoted verbatim in `references/rubric.md`), the **4,000-character** cap (`goal.py:GOAL_CHAR_CAP`), one goal per session, "setting a goal starts a turn with the condition as the directive" (T12's entire basis), the turn-clause bound, the `clear` aliases and the resume semantics.; local:nested-project-skills-are-not-loaded-at-startup: skills.md, same 2026-07-30 revision, and it REVERSED a claim rather than refining one. Was: "Claude Code also discovers skills from nested `.claude/skills/` directories on demand." Now: they "aren't loaded at startup … Until then, those skills don't appear in autocomplete and can't be invoked by name" — they load only once Claude reads or edits a file inside that subdirectory. NO IMPACT HERE, stated so the next session does not re-derive it: every skill in this repo lives at the repo-root `.claude/skills/`, which loads at startup. Recorded because the failure it now describes is invisible — a nested skill is not missing, it is merely un-invocable until an unrelated file read happens to arm it, so "the skill did not fire" would read as a description problem. Same revision, no action: `/verify` records its own recipe to `.claude/skills/verify/SKILL.md` (v2.1.200+, edit behaviour narrowed in v2.1.205), and the cloud-session doc anchor moved from `claude-code-on-the-web` to `cloud-environments`.; local:permissionrequest-now-fires-where-nobody-can-be-asked: hooks.md, same 2026-07-30 revision. Was: "Runs when the user is shown a permission dialog." Now it also runs in sessions that CANNOT show one — background subagents in non-interactive mode — and "if no hook returns a decision, it denies the tool call." Tracked because the old sentence made the event sound unreachable in headless work, so a `PermissionRequest` hook would look like the wrong tool for gating an unattended lane. It is now the opposite: in headless mode the DEFAULT is deny, and a hook is what can allow. This repo registers no `PermissionRequest` hook (its three PreToolUse guards are the enforcement layer, `mise-tasks-only.md`), so nothing changes today. NOT changed, control-armed the same day because the graph records a standing disagreement about it: the "Claude Code overrides the hook and ends the turn after 8 consecutive blocks" Stop-hook cap is still present — 1 occurrence in both the 2026-07-27 baseline and the current page, against a bogus term at 0. goal.md still never mentions a cap. The unreconciled-doc-disagreement node stays TRUE; do not re-derive it.
- Recommended: Re-probe each against the new version, then record the result in currency.toml — an untested local finding is folklore, not a finding.
- **Answer:** Yes — handle in this round (Ray, 2026-08-05, AskUserQuestion). All
  four re-probed against the live pages, results appended to each watch item in
  `currency.toml`:
  - `sessionend-hooks-share-a-1.5s-budget`: mechanism intact, ceiling still 60;
    two new facts — a `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` override, and
    plugin-provided hook timeouts do NOT raise the budget (ours is
    settings-declared, unaffected). No config change.
  - `goal-evaluator-model-is-not-always-haiku`: goal.md's fingerprint held this
    review — checked, unchanged.
  - `nested-project-skills-are-not-loaded-at-startup`: skills.md moved AGAIN in
    exactly this area — nested skills now carry invocable directory-qualified
    names on collision (≥2.1.203); the "can't be invoked by name" sentence is
    stale. Still no impact (all skills repo-root).
  - `permissionrequest-now-fires-where-nobody-can-be-asked`: claim intact
    verbatim at hooks.md:1744; the 8-consecutive-blocks cap still 1 occurrence
    vs control 0.

  Docs baseline rolled for all three pages
  (`kb-setup currency docs-reviewed --tool claude-code`) after the re-read; the
  changed pages re-enter the corpus via `mise run kb-update -- agent-harness-docs`
  once the round's `kb-build` finished (one graph, one writer at a time).

### Gate: step 1 currently green

**The current install is already out of sync. Fix that before bumping?**

- Detail: version: claude on PATH is 2.1.222 but the reviewed version is 2.1.220 — it self-updated. Review the releases between them, then bump `expected` in currency.toml to record that you have
- Recommended: Resolve the drift first — bumping on top of an unknown state makes the result unattributable.
- **Answer:** Resolved (Ray, 2026-08-05: handle in this round). Both releases
  between 2.1.220 and 2.1.222 reviewed from the run's own fetched notes. What
  reaches this repo, checked rather than assumed: the zsh `[[ ]]` hidden-command
  permission bypass fix and the PreToolUse-auto-ALLOW-in-background fix are both
  on the permissions surface our guards live on, but `kb_setup.hook_guard` is a
  DENY-direction guard, so neither changes its behaviour; Remote Control
  auto-start can no longer be enabled by repo-local settings (this repo never
  set it); "Removed ultraplan" touches nothing here (`/ultrareview` is a
  different, still-shipping command). `expected` bumped 2.1.220 → 2.1.222 to
  record the review.

## Step 6 — process note

This page is the immutable record of ONE run — a later run writes its own new
page rather than rewriting this one. Annotate it freely with review notes;
nothing here is regenerated.
