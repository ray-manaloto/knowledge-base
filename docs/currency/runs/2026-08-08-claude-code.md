# Currency run — claude-code — 2026-08-08T06:38:15+00:00

**Verdict:** claude-code 2.1.224 → v2.1.226: 3 question(s) for review

Related: [[tool-currency-log]] · [[claude-code]]

## Step 1 — in sync?

Pinned `2.1.224` · resolved `2.1.226`

| check | status | detail |
|---|---|---|
| version | drift | claude on PATH is 2.1.226 but the reviewed version is 2.1.224 — it self-updated. Review the releases between them, then bump `expected` in currency.toml to record that you have |

## Steps 2-3 — upstream

- Latest (github): `v2.1.226`
- GitHub release: `v2.1.226`
- Reachable: yes

### Release notes

```text
## v2.1.225

## What's changed

- Added gateway spend-limit support to Claude Code's usage warning; the limit-reached message now names the cap, its reset time, and the operator's message (requires the gateway on 2.1.225)
- Added a workspace trust prompt to `claude agents` for untrusted directories, matching the behavior of `claude`
- Fixed a transient 401 replacing a long-lived `CLAUDE_CODE_OAUTH_TOKEN` with a stored login's short-lived token, breaking headless sessions until restart
- Fixed MCP OAuth servers on macOS intermittently failing with a burst of 401 errors, as if never authenticated, after a keychain read timed out
- Fixed auto mode counting a safety-filter refusal of its own permission check toward the consecutive-block limit; the action is still denied, but the model is now told to move on rather than retry
- Fixed cross-session messages staying parked without a notice or expiry in headless sessions and during startup
- Fixed conversation history breaking on Remote Control session resume after very large conversations were compacted
- Fixed hovering over a session in another project in the agents list changing the directory the next agent starts in

… (truncated)
```

### Features to consider adopting

_Advisory — these did not block the bump. Skim for a new capability worth a config change._

- SendMessage can now start a conversation with your Remote Control sessions on other machines by name (`ListAgents` shows them as `name [ref]`), instead of only replying after they message you first

_**This list may be incomplete.** At least one release in this span uses a changelog format the scan could not read, so features announced there are missing from the list above — read those notes by hand._

## Step 4 — tracked issues and watch items

| item | state | updated | comments | moved? |
|---|---|---|---|---|
| local:sessionend-hooks-share-a-1.5s-budget | local | — | 0 | no |
| local:goal-evaluator-model-is-not-always-haiku | local | — | 0 | no |
| local:nested-project-skills-are-not-loaded-at-startup | local | — | 0 | no |
| local:permissionrequest-now-fires-where-nobody-can-be-asked | local | — | 0 | no |
| local:2-1-223-review | local | — | 0 | no |
| local:2-1-224-review | local | — | 0 | no |

## Step 5 — decision

Gates passed:

- ✅ patch-level bump
- ✅ latest version has a readable GitHub release
- ✅ extras unchanged

### Gate: no breaking/removal/deprecation marker

**The release notes flag a breaking change. Adopt it anyway?**

- Detail: Markers found: breaking.
- Recommended: Read the notes; plan a rebuild and a re-verify before adopting.
- **Answer:** _not yet answered_

### Gate: no tracked issue moved

**6 local watch item(s) must be re-probed against this release. Done?**

- Detail: local:sessionend-hooks-share-a-1.5s-budget: hooks.md gained this on 2026-07-30 (#76): "`SessionEnd` hooks share a 1.5-second budget; if your settings set a longer per-hook `timeout`, Claude Code raises the budget to match, up to 60 seconds." THE TIMEOUT IS LOAD-BEARING, and not for the reason it looks. Without any `timeout` our SessionEnd `brain-transcript-audit` would get **1.5s** — a transcript scan cannot finish in that, and a killed SessionEnd hook is silent, so the failure mode is an audit that simply stops existing. The declared number is what buys the budget. `.claude/settings.json` declared **120**, which the documented ceiling can never grant; lowered to **60** so the config states what it can actually get. Do not read the change as a reduction — the effective budget is identical, and 60 is the documented maximum. Do not delete the field to "use the default": that is the one edit that would silently cost the audit ~58 of its 60 seconds. Re-probe on each docs review: if the ceiling moves, this number moves with it. RE-PROBED 2026-08-05 (hooks.md flagged CHANGED at the 2.1.220 -> 2.1.222 review): the mechanism holds verbatim — 1.5s shared budget, per-hook `timeout` raises it, ceiling still 60 — so the declared 60 stays correct. Two NEW facts on the same paragraph: (1) `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS` now overrides the budget explicitly — an escape hatch, not needed here; (2) "Timeouts set on plugin-provided hooks don't raise the budget" — our audit hook is declared in `.claude/settings.json` (repo settings, not a plugin), so it still buys the 60; skillopt-sleep's SessionEnd hook IS plugin-provided, but it is an async marker-append that needs no budget. No config change.; local:goal-evaluator-model-is-not-always-haiku: goal.md, same 2026-07-30 revision. Was "defaults to Haiku"; now "defaults to Haiku ON THE CLAUDE API; on a third-party provider, check your provider page", plus a new `ANTHROPIC_DEFAULT_HAIKU_MODEL` override whose scope is GLOBAL — it also rebinds the `haiku` alias and background functionality such as conversation summarization. Why it is tracked rather than absorbed: the goal-engineering skill's central rule is that a clause must be settleable by "a Haiku-class reader, given the transcript and nothing else". That phrasing survives — it is now a FLOOR rather than a description of the deployed model. The risk this guards against is the inverse of the obvious one: not that the evaluator is weaker than assumed, but that someone observes a smart evaluator judging a vague clause correctly and concludes the clause was fine. Consequence for recorded outcomes: `kb-goal-outcome` results are conditional on the evaluator that produced them. A `stalled` under one model is not evidence about another (`verify-before-advancing.md`, "carry a fact's CONDITION"). UNCHANGED and re-verified the same day, which is the reason the skill needed no structural edit: the transcript-only/no-tools constraint (quoted verbatim in `references/rubric.md`), the **4,000-character** cap (`goal.py:GOAL_CHAR_CAP`), one goal per session, "setting a goal starts a turn with the condition as the directive" (T12's entire basis), the turn-clause bound, the `clear` aliases and the resume semantics. 2026-08-05 (2.1.220 -> 2.1.222 review): goal.md's fingerprint HELD — only hooks.md and skills.md drifted — so there is nothing to re-derive; recorded so this item's silence at this review reads as "checked, unchanged" rather than "skipped".; local:nested-project-skills-are-not-loaded-at-startup: skills.md, same 2026-07-30 revision, and it REVERSED a claim rather than refining one. Was: "Claude Code also discovers skills from nested `.claude/skills/` directories on demand." Now: they "aren't loaded at startup … Until then, those skills don't appear in autocomplete and can't be invoked by name" — they load only once Claude reads or edits a file inside that subdirectory. NO IMPACT HERE, stated so the next session does not re-derive it: every skill in this repo lives at the repo-root `.claude/skills/`, which loads at startup. Recorded because the failure it now describes is invisible — a nested skill is not missing, it is merely un-invocable until an unrelated file read happens to arm it, so "the skill did not fire" would read as a description problem. Same revision, no action: `/verify` records its own recipe to `.claude/skills/verify/SKILL.md` (v2.1.200+, edit behaviour narrowed in v2.1.205), and the cloud-session doc anchor moved from `claude-code-on-the-web` to `cloud-environments`. RE-PROBED 2026-08-05 (skills.md flagged CHANGED at the 2.1.220 -> 2.1.222 review), and the page moved AGAIN in exactly this item's area — the second revision of the same claim in a week, which is why it stays tracked. Current text: nested skills load "when Claude reads or edits a file in a subdirectory"; a name collision keeps BOTH skills available, the nested one under a directory-qualified name (`apps/web:deploy`) that IS invocable; an unqualified invocation loads the project-root skill with the variant list appended (requires >= 2.1.203). So the 2026-07-30 sentence "can't be invoked by name" is now stale for collision cases — the un-invocable window is only before any file in that subdirectory has been touched. STILL NO IMPACT HERE: every skill in this repo is repo-root, loaded at startup.; local:permissionrequest-now-fires-where-nobody-can-be-asked: hooks.md, same 2026-07-30 revision. Was: "Runs when the user is shown a permission dialog." Now it also runs in sessions that CANNOT show one — background subagents in non-interactive mode — and "if no hook returns a decision, it denies the tool call." Tracked because the old sentence made the event sound unreachable in headless work, so a `PermissionRequest` hook would look like the wrong tool for gating an unattended lane. It is now the opposite: in headless mode the DEFAULT is deny, and a hook is what can allow. This repo registers no `PermissionRequest` hook (its three PreToolUse guards are the enforcement layer, `mise-tasks-only.md`), so nothing changes today. NOT changed, control-armed the same day because the graph records a standing disagreement about it: the "Claude Code overrides the hook and ends the turn after 8 consecutive blocks" Stop-hook cap is still present — 1 occurrence in both the 2026-07-27 baseline and the current page, against a bogus term at 0. goal.md still never mentions a cap. The unreconciled-doc-disagreement node stays TRUE; do not re-derive it. RE-PROBED 2026-08-05 (hooks.md flagged CHANGED at the 2.1.220 -> 2.1.222 review): the claim is intact verbatim — "background subagents in non-interactive mode … if no hook returns a decision, it denies the tool call" (hooks.md:1744). The 8-consecutive-blocks Stop cap: still exactly 1 occurrence against a bogus term at 0, so the standing disagreement stands. Still no `PermissionRequest` hook here; nothing changes.; local:2-1-223-review: REVIEWED 2026-08-06, which is why `expected` moved 2.1.222 -> 2.1.223. The field's own rule is that the review IS the gap analysis, so this records what the review found rather than only that it happened. Read from the 2.1.223 entry in this repo's own pinned mirror (`sources/agent-harness-docs/docs/claude-code/changelog.md`, advanced to `75886c4142` in the same change) rather than from a fetch — the corpus is the source, which is the whole point of the mirror. THREE ITEMS TOUCH THIS REPO, none requiring a change: 1. Two Bash permission-bypass fixes — "a crafted command could hide parts of itself from permission checks" and commands "padded with tabs or invisible Unicode". Same CLASS as `kb_setup.hook_guard`, which parses Bash to redirect raw `graphify` calls. NOT a defect for us: that guard is documented as a redirect, not a sandbox (`$(...)`, `sh -c`, `eval` and aliases pass by design), so hiding bytes from it buys an evader nothing they could not get by typing `sh -c`. Recorded because the next reader will meet these two lines and reasonably wonder. 2. "Fixed workflow scripts being able to use dynamic `import()` to run code outside the workflow sandbox" — this repo runs `.claude/workflows/kb-extract.js`, which uses no dynamic import. Fix inherited, nothing to do. 3. `/review` became an alias of `/code-review`. Does not touch `kb-review`, which is this repo's own skill and gate. NOT applicable: the `strictKnownMarketplaces` owner-wildcard entries (managed settings, which this repo does not write — `do-not.md` #11), and the `CLAUDE_CODE_DISABLE_1M_CONTEXT` widening (a session-model behaviour, not config here).; local:2-1-224-review: REVIEWED 2026-08-07, which is why `expected` moved 2.1.223 -> 2.1.224. Same rule as the entry above: the review IS the gap analysis, so this records what it found. READ FROM THE GITHUB RELEASE API, NOT THE MIRROR, and that is a deviation worth stating. `sources/agent-harness-docs/docs/claude-code/changelog.md` is the preferred source, but its pin predates this release — control-armed, 2.1.224 -> 0 hits while 2.1.223 -> 1, so the mirror is genuinely behind rather than the grep being wrong. Advancing it (`mise run kb-update -- agent-harness-docs`) is the follow-up, NOT done here. THE ONE ITEM THAT TOUCHES AN INVARIANT — checked, no change made: `ANTHROPIC_BEDROCK_REGION_PREFIX` is new: it selects a Bedrock cross-region inference profile over the `AWS_REGION`-derived one. It is worth a paragraph because it is the exact shape that defeats `graphify_env.clean_env()`: that function strips Bedrock triggers BY NAME while deliberately KEEPING `ANTHROPIC_*` as the Claude path, so a Bedrock-selecting variable named `ANTHROPIC_...` would walk straight through it. It does not, and the probe discriminates. Against the INSTALLED graphify 0.9.35: `ANTHROPIC_BEDROCK_REGION_PREFIX` -> 0 hits, control `ANTHROPIC_API_KEY` -> 4 in `llm.py`. graphify's bedrock path reads only `AWS_REGION` / `AWS_DEFAULT_REGION` / `AWS_PROFILE` (`llm.py:1655-1656`), all three already in `_STRIP_BACKEND_ENV`. It is a Claude Code variable; `detect_backend()` cannot see it. DELIBERATELY NOT ADDED to `_STRIP_BACKEND_ENV`. Stripping a name nothing reads is cargo-cult — it would make the list a record of what we feared rather than of what flips a backend, and every future reader would have to re-derive why it is there. THREE ITEMS THAT MATTER HERE, none requiring a change: 1. The 200-subagent-per-session spawn cap is REMOVED. Directly relevant: a long session previously refused new agents, which bites `kb-extract` fan-outs and multi-round `kb-review`. 2. Plugin install records were silently corrupted when one plugin is installed in multiple projects — FIXED. This repo enables 10 project-scope plugins and the sibling dotfiles repo has its own, so we were in scope for it. 3. New `archive` plugin source (zip over HTTPS, optional SHA-256 pinning). A candidate fix for the standing complaint that `skillopt`'s pin `main` cannot be compared with upstream `v0.2.0`, so its drift reports UNKNOWN every session. Evaluating it is a separate piece of work, not this bump. NOT applicable, armed rather than assumed: the >200-char project-path session-dir collision — this project's path is 56 characters.
- Recommended: Re-probe each against the new version, then record the result in currency.toml — an untested local finding is folklore, not a finding.
- **Answer:** _not yet answered_

### Gate: step 1 currently green

**The current install is already out of sync. Fix that before bumping?**

- Detail: version: claude on PATH is 2.1.226 but the reviewed version is 2.1.224 — it self-updated. Review the releases between them, then bump `expected` in currency.toml to record that you have
- Recommended: Resolve the drift first — bumping on top of an unknown state makes the result unattributable.
- **Answer:** _not yet answered_

## Step 6 — process note

This page is the immutable record of ONE run — a later run writes its own new
page rather than rewriting this one. Annotate it freely with review notes;
nothing here is regenerated.
