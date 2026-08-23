# Refutation attempt — finding 17 (lane: contradicted)

CLAIM: `.claude/CLAUDE.md:46` states "Nine plugins are enabled in total", citing
md-size-budgets.md's skill-listing-budget section as its authority.

## Probes (all against primary artifacts in the working tree)

1. `grep -n "Nine plugins\|nine plugins\|plugins are enabled" .claude/CLAUDE.md .claude/rules/md-size-budgets.md`
   -> `.claude/CLAUDE.md:46:...all ordinary tooling. **Nine plugins are enabled in`
      `.claude/CLAUDE.md:47:total**, which is what `md-size-budgets.md` § the skill-listing budget is about.`
   -> md-size-budgets.md: NO hit for "nine" (only :85 "skill-listing budget").
   CONTROL ARM (same command shape, number-word tokens, both spellings + numerals):
   `grep -n "ten\b\|Ten\b\|nine\|Nine\|seven\|Seven\|eight\|Eight" .claude/rules/md-size-budgets.md`
   -> `109:matters here: with seven project skills plus **ten** enabled plugins' skills`
   The same probe returns "Nine" in one file and "ten"/"seven" in the other, so the
   token spelling is not a bound: it discriminates in both directions.

2. Ground truth, second route (`jq`, not grep):
   `jq -r '.enabledPlugins | length' .claude/settings.json` -> `10`
   Keys at .claude/settings.json:79-90 (verbatim): fable-orchestrator@fable-orchestrator,
   antigravity@antigravity-for-claude-code, astral@astral-sh, mattpocock-skills@mattpocock,
   pr-review-toolkit@claude-plugins-official, skill-creator@claude-plugins-official,
   claude-md-management@claude-plugins-official, mise@brentmitchell25,
   plugin-eval@claude-code-workflows, codex@openai-codex — all `true`.
   The line range 79-90 in the finding is EXACT.

3. History: `git log --oneline -S'astral@astral-sh' -- .claude/settings.json`
   -> `cd93801b` (2026-07-27 11:57:31 -0500). `.claude/CLAUDE.md` last touched
   `7c9d62c4` (2026-08-13 08:19:57 -0500). So the finding's chronology holds.
   NEW (not in the finding): `git log --oneline -S'codex@openai-codex' -- .claude/settings.json`
   -> `a2ef5d88` — codex was the 10th plugin. 2 named + 4 named + plugin-eval = 7
   explicitly named in .claude/CLAUDE.md; +astral +mattpocock = 9. "Nine" was
   arithmetically correct until `a2ef5d88` added codex; it is stale by ONE, and the
   prose never named astral/mattpocock at all.

## Refutation angle that FAILED to refute, but corrects the finding's evidence

`.claude/settings.local.json` (untracked; gitignored via
`/Users/rmanaloto/.gitignore_global:37`) contains its OWN `enabledPlugins` block:
```
"enabledPlugins": { "claude-md-management@claude-plugins-official": false,
                    "mise@brentmitchell25": false }
```
Local settings outrank project settings, so the EFFECTIVE count on this machine is
**8**, not 10 and not 9. This does not save "nine" — it makes every prose count in
the repo wrong — but it does mean the finding's phrase "Ground truth ... has 10 keys"
is the TRACKED-REPO truth, not the machine's effective truth.

## Cross-check against the other live findings

Finding 18 quotes the SAME line (md-size-budgets.md:109) for "seven project skills".
Both quotes are present on that one line — they are complementary, not contradictory.
Side-observation for 18: `ls -1d .claude/skills/*/ | wc -l` -> **12**, so that half of
line 109 is stale too.

VERDICT: not refuted.
